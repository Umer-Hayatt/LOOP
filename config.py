import os
from typing import List
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

class Settings:
    def __init__(self):
        self.GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        self.GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        self.GOOGLE_REFRESH_TOKEN: str = os.getenv("GOOGLE_REFRESH_TOKEN", "").strip()

        self.HOST_EMAIL: str = os.getenv("HOST_EMAIL", "info@looponics.tech").strip()
        self.HOST_CALENDAR_ID: str = os.getenv("HOST_CALENDAR_ID", "primary").strip()

        self.SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
        self.SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587").strip())
        self.SMTP_USER: str = os.getenv("SMTP_USER", "").strip()
        self.SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "").strip()

        raw_origins = os.getenv(
            "ALLOWED_ORIGINS",
            "https://looponics.tech,http://localhost:5500",
        )
        self.ALLOWED_ORIGINS: List[str] = [
            origin.strip() for origin in raw_origins.split(",") if origin.strip()
        ]

        self.TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Karachi").strip()
        self.MEETING_MINUTES: int = int(os.getenv("MEETING_MINUTES", "30").strip())

    def __repr__(self) -> str:
        # Never log secrets or credentials
        return (
            f"<Settings HOST_EMAIL={self.HOST_EMAIL} "
            f"CALENDAR_ID={self.HOST_CALENDAR_ID} "
            f"TIMEZONE={self.TIMEZONE} "
            f"MEETING_MINUTES={self.MEETING_MINUTES}>"
        )

settings = Settings()
