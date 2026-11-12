import smtplib
import logging
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
from config import settings

logger = logging.getLogger("looponics.email")

def format_datetime_for_display(iso_str: str, timezone_name: str) -> str:
    """Converts an ISO 8601 string to a human-readable string in the specified timezone."""
    try:
        dt = datetime.fromisoformat(iso_str)
        tz = ZoneInfo(timezone_name)
        dt_local = dt.astimezone(tz)
        return dt_local.strftime("%A, %B %d, %Y at %I:%M %p (%Z)")
    except Exception:
        return iso_str

def _send_smtp_message(msg: EmailMessage) -> bool:
    """Internal helper to dispatch an EmailMessage over SMTP."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured. Skipping email dispatch.")
        return False

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
            return True
    except Exception as e:
        logger.error(f"Failed to send email to {msg['To']}: {e}")
        return False

def send_booking_emails(
    client_name: str,
    client_email: str,
    start_iso: str,
    end_iso: str,
    meet_link: str,
    client_message: Optional[str] = None,
) -> None:
    """
    Sends confirmation email to client and notification email to host.
    Any failure is caught and logged so it never crashes the booking flow.
    """
    formatted_start = format_datetime_for_display(start_iso, settings.TIMEZONE)
    formatted_end = format_datetime_for_display(end_iso, settings.TIMEZONE)

    # 1. Email to Client
    try:
        client_msg = EmailMessage()
        client_msg["Subject"] = f"Confirmed: Your call with Looponics ({formatted_start})"
        client_msg["From"] = f"Looponics <{settings.SMTP_USER or settings.HOST_EMAIL}>"
        client_msg["To"] = client_email

        client_plain = f"""Hi {client_name},

Your discovery call with Looponics has been successfully scheduled!

Meeting Details:
- Date & Time: {formatted_start}
- Video Link: {meet_link}

A Google Calendar invite has also been sent to your email with the Google Meet link.

If you need to reschedule or have any questions beforehand, simply reply to this email.

Best regards,
The Looponics Team
https://looponics.tech
"""

        client_html = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; background-color: #f8fafc; padding: 24px;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
    <div style="background: #0f172a; padding: 24px; color: #ffffff;">
      <h1 style="margin: 0; font-size: 20px; font-weight: 600;">Looponics</h1>
    </div>
    <div style="padding: 24px;">
      <h2 style="margin-top: 0; color: #0f172a; font-size: 18px;">Your call is confirmed, {client_name}!</h2>
      <p style="color: #475569;">We're looking forward to speaking with you. Here are the meeting details:</p>
      
      <div style="background: #f1f5f9; border-radius: 8px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0 0 8px 0;"><strong>Date & Time:</strong> {formatted_start}</p>
        <p style="margin: 0;"><strong>Google Meet:</strong> <a href="{meet_link}" style="color: #2563eb; font-weight: 600; text-decoration: underline;">{meet_link}</a></p>
      </div>

      <p style="margin: 24px 0 0 0; text-align: center;">
        <a href="{meet_link}" style="display: inline-block; background: #2563eb; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 500;">Join Google Meet</a>
      </p>

      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 28px 0;" />
      <p style="font-size: 13px; color: #64748b; margin: 0;">A calendar invite has also been attached to your calendar. If you need to make changes, feel free to reply directly to this email.</p>
    </div>
  </div>
</body>
</html>
"""
        client_msg.set_content(client_plain)
        client_msg.add_alternative(client_html, subtype="html")
        _send_smtp_message(client_msg)
    except Exception as e:
        logger.error(f"Error preparing client confirmation email: {e}")

    # 2. Email to Host
    try:
        host_msg = EmailMessage()
        host_msg["Subject"] = f"New Booking: Call with {client_name} ({formatted_start})"
        host_msg["From"] = f"Looponics Booking <{settings.SMTP_USER or settings.HOST_EMAIL}>"
        host_msg["To"] = settings.HOST_EMAIL

        msg_body = client_message if client_message else "No message provided."

        host_plain = f"""New Booking Alert

Client: {client_name}
Email: {client_email}
Scheduled Time: {formatted_start}
Meeting Link: {meet_link}

Client Note:
{msg_body}
"""

        host_html = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; padding: 20px;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px;">
    <h2 style="margin-top: 0; color: #0f172a;">New Call Booked</h2>
    <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
      <tr><td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-weight: bold; width: 140px;">Client:</td><td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">{client_name}</td></tr>
      <tr><td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-weight: bold;">Email:</td><td style="padding: 8px; border-bottom: 1px solid #e2e8f0;"><a href="mailto:{client_email}">{client_email}</a></td></tr>
      <tr><td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-weight: bold;">Time:</td><td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">{formatted_start}</td></tr>
      <tr><td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-weight: bold;">Meet Link:</td><td style="padding: 8px; border-bottom: 1px solid #e2e8f0;"><a href="{meet_link}">{meet_link}</a></td></tr>
      <tr><td style="padding: 8px; font-weight: bold; vertical-align: top;">Client Note:</td><td style="padding: 8px; white-space: pre-wrap;">{msg_body}</td></tr>
    </table>
  </div>
</body>
</html>
"""
        host_msg.set_content(host_plain)
        host_msg.add_alternative(host_html, subtype="html")
        _send_smtp_message(host_msg)
    except Exception as e:
        logger.error(f"Error preparing host notification email: {e}")

def send_form_submission_email(form_data: Dict[str, Any]) -> bool:
    """
    Emails all submission fields to the host as a clean, readable table.
    """
    try:
        client_email = form_data.get("email", "Unknown")
        subject = f"New Form Submission: {client_email}"

        # Build clean plain-text table
        plain_lines = ["New Website Form Submission", "=" * 32]
        for key, value in form_data.items():
            plain_lines.append(f"{key}: {value}")
        plain_body = "\n".join(plain_lines)

        # Build clean HTML table
        table_rows = "".join(
            f"<tr><td style='padding: 8px; border: 1px solid #e2e8f0; font-weight: 600; background: #f8fafc; text-transform: capitalize;'>{k}</td><td style='padding: 8px; border: 1px solid #e2e8f0;'>{v}</td></tr>"
            for k, v in form_data.items()
        )

        html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; padding: 20px;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px;">
    <h2 style="margin-top: 0; color: #0f172a;">New Website Form Submission</h2>
    <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
      <thead>
        <tr style="background: #0f172a; color: #ffffff;">
          <th style="padding: 8px; text-align: left; width: 140px;">Field</th>
          <th style="padding: 8px; text-align: left;">Value</th>
        </tr>
      </thead>
      <tbody>
        {table_rows}
      </tbody>
    </table>
  </div>
</body>
</html>
"""
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"Looponics Forms <{settings.SMTP_USER or settings.HOST_EMAIL}>"
        msg["To"] = settings.HOST_EMAIL
        msg.set_content(plain_body)
        msg.add_alternative(html_body, subtype="html")

        return _send_smtp_message(msg)
    except Exception as e:
        logger.error(f"Error preparing form submission email: {e}")
        return False

def save_form_submission(form_data: Dict[str, Any]) -> None:
    """
    Hook to save form submissions to Google Sheets, database, or CRM in the future.
    Designed so storage integrations can be added in one place.
    """
    logger.info(f"Form submission recorded for email={form_data.get('email')}")
    # Future integration (e.g., Google Sheets append or PostgreSQL insert) goes here:
    # Example: google_sheets_client.append_row("Submissions", list(form_data.values()))
    pass

