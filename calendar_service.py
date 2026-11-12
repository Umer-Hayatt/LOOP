import uuid
import logging
from typing import Dict, Any, Tuple
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
) -> Tuple[Dict[str, Any], str]:
    """
    Creates a Google Calendar event with Google Meet integration and both attendees.
    Returns (event_data, meet_link).
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

    return event, meet_link

