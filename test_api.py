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
    """Happy path: booking succeeds, returns meetLink, start, end."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    start_iso = future_time.isoformat()

    mock_available.return_value = True
    mock_create.return_value = (
        {"id": "test_event_123"},
        "https://meet.google.com/abc-defg-hij",
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
    mock_create.return_value = ({"id": "ev"}, "https://meet.google.com/abc")
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

@patch("email_service._send_smtp_message")
def test_submit_form_endpoint(mock_smtp):
    """POST /submit-form accepts email and flexible arbitrary fields."""
    mock_smtp.return_value = True

    payload = {
        "email": "client@enterprise.com",
        "company": "Acme Corp",
        "budget": "$10,000",
        "projectScope": "Custom AI Automation Workflow",
        "timeline": "3 weeks",
    }

    response = client.post("/submit-form", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["message"] == "Form submitted successfully."

def test_submit_form_invalid_email():
    """POST /submit-form rejects missing or invalid email."""
    response = client.post("/submit-form", json={"company": "Acme Corp"})
    assert response.status_code == 422

