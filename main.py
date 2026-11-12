import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, ConfigDict

from config import settings
from rate_limiter import booking_rate_limiter
import calendar_service
import email_service

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("looponics.api")

app = FastAPI(
    title="Looponics Booking & Form API",
    description="Backend API for Looponics meeting scheduling and client form submissions.",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BookCallRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Client full name")
    email: EmailStr = Field(..., description="Client email address")
    startTime: str = Field(..., description="ISO 8601 string with timezone offset (e.g. 2026-11-15T15:00:00+05:00)")
    message: Optional[str] = Field(default="", description="Optional note from client")
    website: Optional[str] = Field(default="", description="Honeypot field for bot protection")

class SubmitFormRequest(BaseModel):
    email: EmailStr = Field(..., description="Contact email address")
    model_config = ConfigDict(extra="allow")

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    """Health check endpoint for monitoring and uptime probes."""
    return {"status": "ok"}

@app.post("/book-call", status_code=status.HTTP_200_OK)
def book_call(payload: BookCallRequest, request: Request):
    """
    Handles appointment booking:
    1. Honeypot check for bots
    2. Rate limiting per client IP
    3. Validates requested time (rejects past times)
    4. Verifies host availability via Google Calendar Freebusy API
    5. Creates Calendar event with Google Meet link and attendees
    6. Sends confirmation emails via SMTP
    """
    # 1. Honeypot bot protection
    if payload.website:
        logger.warning("Honeypot triggered by request. Returning fake success.")
        # Return fake success without touching calendar or email
        fake_end = payload.startTime
        try:
            parsed_start = datetime.fromisoformat(payload.startTime)
            fake_end = (parsed_start + timedelta(minutes=settings.MEETING_MINUTES)).isoformat()
        except Exception:
            pass
        return {
            "ok": True,
            "meetLink": "https://meet.google.com/bot-trap-looponics",
            "start": payload.startTime,
            "end": fake_end,
        }

    # 2. Rate limiting (5 bookings per hour per IP)
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not booking_rate_limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many booking requests from your IP. Please wait a little while before trying again.",
        )

    # 3. Parse and validate time
    try:
        start_dt = datetime.fromisoformat(payload.startTime)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid startTime format. Must be a valid ISO 8601 string with timezone offset.",
        )

    if start_dt.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="startTime must include a timezone offset (e.g. +05:00 or Z).",
        )

    now = datetime.now(start_dt.tzinfo)
    if start_dt < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book an appointment in the past. Please select an upcoming date and time.",
        )

    end_dt = start_dt + timedelta(minutes=settings.MEETING_MINUTES)
    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()

    # 4. Check host calendar freebusy
    try:
        service = calendar_service.get_calendar_service()
        available = calendar_service.is_host_available(service, start_iso, end_iso)
    except ValueError as ve:
        logger.error(f"Configuration error: {ve}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server calendar service is not configured.",
        )
    except Exception as e:
        logger.error(f"Error checking calendar availability: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to verify calendar availability. Please try again shortly.",
        )

    if not available:
        logger.info(f"Slot {start_iso} is busy on host calendar.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The selected time slot is already booked or unavailable. Please choose another time.",
        )

    # 5. Create Calendar event with Google Meet link
    try:
        event, meet_link = calendar_service.create_booking_event(
            service=service,
            client_name=payload.name,
            client_email=payload.email,
            start_iso=start_iso,
            end_iso=end_iso,
            client_message=payload.message,
        )
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create calendar event. Please try again shortly.",
        )

    # 6. Send emails (never fail the booking if email delivery fails)
    try:
        email_service.send_booking_emails(
            client_name=payload.name,
            client_email=payload.email,
            start_iso=start_iso,
            end_iso=end_iso,
            meet_link=meet_link,
            client_message=payload.message,
        )
    except Exception as e:
        logger.error(f"Non-fatal error in send_booking_emails: {e}")

    return {
        "ok": True,
        "meetLink": meet_link,
        "start": start_iso,
        "end": end_iso,
    }

@app.post("/submit-form", status_code=status.HTTP_200_OK)
def submit_form(payload: SubmitFormRequest):
    """
    Accepts flexible form submissions (email required, any other fields optional).
    Dispatches email table to the host and calls the storage hook.
    """
    form_data: Dict[str, Any] = payload.model_dump()

    # Save to storage hook (Sheets / Database)
    email_service.save_form_submission(form_data)

    # Send email notification to host
    email_service.send_form_submission_email(form_data)

    return {
        "ok": True,
        "message": "Form submitted successfully.",
    }
