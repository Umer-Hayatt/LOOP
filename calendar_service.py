import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from config import settings

logger = logging.getLogger("looponics.calendar")

TOKEN_URI = "https://oauth2.googleapis.com/token"

def get_calendar_service():
    """
    Builds the Google Calendar API client using the refresh token.
    Runs completely headlessly without ever opening a browser.
    """
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET and settings.GOOGLE_REFRESH_TOKEN):
        raise ValueError(
            "Google Calendar credentials are not fully configured. "
            "Please ensure GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN are set in .env."
        )

    creds = Credentials(
        token=None,
        refresh_token=settings.GOOGLE_REFRESH_TOKEN,
        token_uri=TOKEN_URI,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )

    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def is_host_available(service, start_iso: str, end_iso: str) -> bool:
    """
    Queries Google Calendar freebusy API to check if the host is free between start_iso and end_iso.
    Returns True if free, False if busy.
    """
    calendar_id = settings.HOST_CALENDAR_ID
    body = {
        "timeMin": start_iso,
        "timeMax": end_iso,
        "timeZone": settings.TIMEZONE,
        "items": [{"id": calendar_id}],
    }

    freebusy_response = service.freebusy().query(body=body).execute()
    calendars = freebusy_response.get("calendars", {})
    host_calendar = calendars.get(calendar_id, {})
    busy_slots = host_calendar.get("busy", [])

    return len(busy_slots) == 0

def create_booking_event(
    service,
    client_name: str,
    client_email: str,
    start_iso: str,
    end_iso: str,
    client_message: str = "",
) -> Tuple[Dict[str, Any], str, str]:
    """
    Creates a Google Calendar event with Google Meet integration and both attendees.
    Returns (event_data, meet_link, booking_id).
    """
    calendar_id = settings.HOST_CALENDAR_ID
    request_id = str(uuid.uuid4())

    event_body = {
        "summary": f"Looponics call with {client_name}",
        "description": (
            f"Scheduled discovery call with {client_name} ({client_email}).\n\n"
            f"Client message:\n{client_message or 'No message provided.'}"
        ),
        "start": {
            "dateTime": start_iso,
        },
        "end": {
            "dateTime": end_iso,
        },
        "attendees": [
            {"email": client_email},
            {"email": settings.HOST_EMAIL},
        ],
        "conferenceData": {
            "createRequest": {
                "requestId": request_id,
                "conferenceSolutionKey": {
                    "type": "hangoutsMeet",
                },
            },
        },
    }

    event = service.events().insert(
        calendarId=calendar_id,
        body=event_body,
        conferenceDataVersion=1,
        sendUpdates="all",
    ).execute()

    meet_link = event.get("hangoutLink", "")
    if not meet_link:
        conf_data = event.get("conferenceData", {})
        for entry_point in conf_data.get("entryPoints", []):
            if entry_point.get("entryPointType") == "video":
                meet_link = entry_point.get("uri", "")
                break

    booking_id = event.get("id", "")
    return event, meet_link, booking_id

def get_booking_by_id(service, booking_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a specific calendar booking event by its event ID."""
    if not booking_id:
        return None
    try:
        return service.events().get(
            calendarId=settings.HOST_CALENDAR_ID,
            eventId=booking_id,
        ).execute()
    except Exception as e:
        logger.warning(f"Could not retrieve booking event ID {booking_id}: {e}")
        return None

def find_recent_booking_by_email(service, client_email: str) -> Optional[Dict[str, Any]]:
    """
    Searches for a recent or upcoming calendar booking event matching the client email.
    Looks back 14 days and forward 60 days.
    """
    if not client_email:
        return None
    try:
        now = datetime.now(timezone.utc)
        time_min = (now - timedelta(days=14)).isoformat()
        time_max = (now + timedelta(days=60)).isoformat()

        events_result = service.events().list(
            calendarId=settings.HOST_CALENDAR_ID,
            q=client_email,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=10,
        ).execute()

        items = events_result.get("items", [])
        for item in items:
            # Check attendees, description, or summary for email
            attendees = item.get("attendees", [])
            matches_attendee = any(
                a.get("email", "").lower() == client_email.lower() for a in attendees
            )
            in_desc = client_email.lower() in item.get("description", "").lower()
            in_summary = client_email.lower() in item.get("summary", "").lower()

            if matches_attendee or in_desc or in_summary:
                return item

        return None
    except Exception as e:
        logger.warning(f"Error searching booking for email {client_email}: {e}")
        return None

def format_booking_summary(event: Optional[Dict[str, Any]]) -> str:
    """Formats an event dictionary into a clean, human-readable summary string."""
    if not event:
        return "no matching booking found"

    summary = event.get("summary", "Discovery Call")
    start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", "Unknown time")
    booking_id = event.get("id", "")

    meet_link = event.get("hangoutLink", "")
    if not meet_link:
        conf_data = event.get("conferenceData", {})
        for ep in conf_data.get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meet_link = ep.get("uri", "")
                break

    meet_part = f" | Meet: {meet_link}" if meet_link else ""
    return f"{summary} at {start} (Booking ID: {booking_id}){meet_part}"
