from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from main import app
from rate_limiter import booking_rate_limiter

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    booking_rate_limiter.reset()
    yield
    booking_rate_limiter.reset()

def test_health_check():
    """GET /health must return 200 with status: ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch("calendar_service.get_calendar_service")
@patch("calendar_service.is_host_available")
@patch("calendar_service.create_booking_event")
@patch("email_service._send_smtp_message")
def test_book_call_happy_path(mock_smtp, mock_create, mock_available, mock_service):
    """Happy path: booking succeeds, returns bookingId, meetLink, start, end."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    start_iso = future_time.isoformat()

    mock_available.return_value = True
    mock_create.return_value = (
        {"id": "test_event_123"},
        "https://meet.google.com/abc-defg-hij",
        "test_event_123",
    )
    mock_smtp.return_value = True

    payload = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "startTime": start_iso,
        "message": "Excited to meet the Looponics team!",
        "website": "",
    }

    response = client.post("/book-call", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["bookingId"] == "test_event_123"
    assert data["meetLink"] == "https://meet.google.com/abc-defg-hij"
    assert data["start"] == start_iso
    assert "end" in data
    mock_create.assert_called_once()

@patch("calendar_service.get_calendar_service")
@patch("calendar_service.is_host_available")
def test_book_call_busy_slot(mock_available, mock_service):
    """Busy slot: returns HTTP 409 Conflict with friendly message."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    start_iso = future_time.isoformat()

    mock_available.return_value = False  # Slot is busy!

    payload = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "startTime": start_iso,
        "message": "Let's connect",
        "website": "",
    }

    response = client.post("/book-call", json=payload)
    assert response.status_code == 409
    assert "already booked or unavailable" in response.json()["detail"]

def test_book_call_past_time():
    """Past time: returns HTTP 400 Bad Request."""
    past_time = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(microsecond=0)
    start_iso = past_time.isoformat()

    payload = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "startTime": start_iso,
        "message": "Past booking",
        "website": "",
    }

    response = client.post("/book-call", json=payload)
    assert response.status_code == 400
    assert "Cannot book an appointment in the past" in response.json()["detail"]

def test_book_call_invalid_email():
    """Invalid email: returns HTTP 422 Unprocessable Entity."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    start_iso = future_time.isoformat()

    payload = {
        "name": "Jane Doe",
        "email": "not-a-valid-email",
        "startTime": start_iso,
        "website": "",
    }

    response = client.post("/book-call", json=payload)
    assert response.status_code == 422

@patch("calendar_service.get_calendar_service")
def test_book_call_honeypot(mock_service):
    """Honeypot filled: returns fake success 200 without creating anything."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    start_iso = future_time.isoformat()

    payload = {
        "name": "Spam Bot",
        "email": "bot@spammer.com",
        "startTime": start_iso,
        "website": "http://spammy-site.com",  # Honeypot filled!
    }

    response = client.post("/book-call", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["bookingId"] == "bot-trap-booking-id"
    # Calendar service was never even called
    mock_service.assert_not_called()

@patch("calendar_service.get_calendar_service")
@patch("calendar_service.is_host_available")
@patch("calendar_service.create_booking_event")
@patch("email_service._send_smtp_message")
def test_book_call_rate_limit(mock_smtp, mock_create, mock_available, mock_service):
    """Rate limit: 6th booking request from same IP within the hour returns HTTP 429."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    start_iso = future_time.isoformat()

    mock_available.return_value = True
    mock_create.return_value = ({"id": "ev"}, "https://meet.google.com/abc", "ev")
    mock_smtp.return_value = True

    payload = {
        "name": "Rapid Booker",
        "email": "user@example.com",
        "startTime": start_iso,
        "website": "",
    }

    # First 5 requests should pass
    for i in range(5):
        res = client.post("/book-call", json=payload)
        assert res.status_code == 200, f"Request {i+1} failed"

    # 6th request must be rejected with 429
    res_limit = client.post("/book-call", json=payload)
    assert res_limit.status_code == 429
    assert "Too many booking requests" in res_limit.json()["detail"]

@patch("calendar_service.get_calendar_service")
@patch("calendar_service.get_booking_by_id")
@patch("email_service._send_smtp_message")
def test_submit_form_with_booking_id(mock_smtp, mock_get_by_id, mock_service):
    """POST /submit-form successfully links to existing booking via bookingId."""
    mock_smtp.return_value = True
    mock_get_by_id.return_value = {
        "id": "book_123",
        "summary": "Looponics call with Alice",
        "start": {"dateTime": "2026-11-20T15:00:00+05:00"},
        "hangoutLink": "https://meet.google.com/abc-xyz",
    }

    payload = {
        "bookingId": "book_123",
        "email": "alice@client.com",
        "scope": "Full stack automation",
        "budget": "$12,000",
    }

    response = client.post("/submit-form", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "book_123" in data["matchedBooking"]
    assert "Looponics call with Alice" in data["matchedBooking"]

@patch("calendar_service.get_calendar_service")
@patch("calendar_service.get_booking_by_id")
@patch("calendar_service.find_recent_booking_by_email")
@patch("email_service._send_smtp_message")
def test_submit_form_fallback_email_match(mock_smtp, mock_find_email, mock_get_by_id, mock_service):
    """POST /submit-form falls back to matching by email if bookingId is missing."""
    mock_smtp.return_value = True
    mock_get_by_id.return_value = None
    mock_find_email.return_value = {
        "id": "event_from_email_match",
        "summary": "Looponics call with Bob",
        "start": {"dateTime": "2026-11-21T10:00:00+05:00"},
        "hangoutLink": "https://meet.google.com/bob-meet",
    }

    payload = {
        "email": "bob@client.com",
        "requirements": "CRM synchronization",
    }

    response = client.post("/submit-form", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "event_from_email_match" in data["matchedBooking"]
    assert "Looponics call with Bob" in data["matchedBooking"]

@patch("calendar_service.get_calendar_service")
@patch("calendar_service.get_booking_by_id")
@patch("calendar_service.find_recent_booking_by_email")
@patch("email_service._send_smtp_message")
def test_submit_form_no_matching_booking(mock_smtp, mock_find_email, mock_get_by_id, mock_service):
    """POST /submit-form states 'no matching booking found' if neither id nor email matches."""
    mock_smtp.return_value = True
    mock_get_by_id.return_value = None
    mock_find_email.return_value = None

    payload = {
        "email": "unknown@lead.com",
        "interest": "General inquiry",
    }

    response = client.post("/submit-form", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["matchedBooking"] == "no matching booking found"

def test_submit_form_invalid_email():
    """POST /submit-form rejects missing or invalid email."""
    response = client.post("/submit-form", json={"company": "Acme Corp"})
    assert response.status_code == 422
