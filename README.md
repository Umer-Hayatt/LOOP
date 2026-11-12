# Looponics Backend & Booking Widget

A complete, secure, production-ready scheduling backend and embeddable website booking widget for [looponics.tech](https://looponics.tech).

---

## Features

- **Automated Calendar Scheduling**: Verifies host availability via Google Calendar Freebusy API and books events with auto-generated Google Meet video links.
- **Dual Email Notifications**: Sends branded HTML confirmation emails to the client and detailed alerts to the host via SMTP.
- **Honeypot Bot Protection**: Silent rejection of spam bots via an invisible honeypot field (`website`).
- **Sliding-Window Rate Limiting**: In-memory protection allowing a maximum of 5 booking requests per hour per IP.
- **Flexible Form Endpoint (`/submit-form`)**: Receives custom inquiry forms, sends a structured table to the host, and provides an extensible hook for Google Sheets or database storage.
- **Embeddable Vanilla Widget**: Standalone HTML/CSS/JS snippet with timezone auto-detection, responsive modal UI, and cold-start loading indicators.

---

## ⚠️ Important Google Cloud Notice

> [!WARNING]
> **Google OAuth Consent Screen Publishing Status:**
> In your Google Cloud Console OAuth Consent Screen settings, ensure the publishing status is set to **"In production"**.
> If left in "Testing" mode, Google automatically expires your `GOOGLE_REFRESH_TOKEN` every **7 days**, which will break calendar bookings after one week. Setting it to "In production" ensures the refresh token remains permanent.

---

## ⚠️ Important Render Free Tier Notice

> [!NOTE]
> **Free Tier Spin-Down / Sleep:**
> On Render's Free tier, the web service automatically spins down (goes to sleep) after 15 minutes of inactivity. When a new visitor submits a booking or loads the endpoint, Render takes approximately **30 to 60 seconds** to wake up the service.
> The booking widget in `frontend/booking-widget.html` explicitly includes a loading state and message explaining this so clients understand the brief initial wait.

---

## Quickstart (Local Development)

### 1. Prerequisites
- Python 3.11+
- Windows PowerShell

### 2. Setup Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Generate Google Refresh Token
1. Download your OAuth Client JSON file from Google Cloud Console (Application type: **Desktop app**).
2. Save it in the project root as `credentials.json`.
3. Run the one-time helper script:
```powershell
python get_refresh_token.py
```
This opens your browser, asks for permission, and outputs:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and fill in the values:
```powershell
Copy-Item .env.example .env
```
Key variables:
- `HOST_EMAIL`: Your primary host email address (e.g. `info@looponics.tech`).
- `HOST_CALENDAR_ID`: `primary` (or your specific calendar ID).
- `SMTP_USER`: Your Gmail address.
- `SMTP_PASSWORD`: A 16-character Gmail App Password (generated from Google Account Security).
- `ALLOWED_ORIGINS`: `https://looponics.tech,http://localhost:5500`.
- `TIMEZONE`: `Asia/Karachi`.
- `MEETING_MINUTES`: `30`.

### 5. Run the Local Server
```powershell
.\venv\Scripts\uvicorn main:app --reload --port 8000
```

---

## Testing with PowerShell

### Health Check:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
```

### Book a Call:
```powershell
$body = @{
    name = "Alex Morgan"
    email = "alex@example.com"
    startTime = "2026-11-20T15:00:00+05:00"
    message = "Discussing AI workflow automation"
    website = ""
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/book-call" -Method Post -ContentType "application/json" -Body $body
```

### Submit Flexible Form:
```powershell
$body = @{
    email = "partner@company.com"
    serviceRequired = "Custom Backend Development"
    timeline = "2 months"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/submit-form" -Method Post -ContentType "application/json" -Body $body
```

### Run Automated Tests:
```powershell
.\venv\Scripts\pytest -v
```

---

## File Structure

```
├── main.py                  # FastAPI application & route endpoints
├── calendar_service.py      # Google Calendar API integration & Meet links
├── email_service.py         # SMTP email dispatcher & storage hook
├── rate_limiter.py          # Sliding-window IP rate limiter
├── config.py                # Environment configuration loader
├── get_refresh_token.py     # Local Google OAuth2 authorization helper
├── requirements.txt         # Pinned production dependencies
├── render.yaml              # Render infrastructure-as-code specification
├── runtime.txt              # Pinned Python version for deployment
├── .env.example             # Documented template for environment variables
├── .gitignore               # Strict exclusion of secrets and venv
├── test_api.py              # Pytest test suite with mocked Google/SMTP services
└── frontend/
    └── booking-widget.html  # Standalone embeddable modal widget
```
