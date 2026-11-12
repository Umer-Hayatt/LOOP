"""
One-time script to generate Google Calendar OAuth2 refresh token.
Run this locally on your computer with credentials.json in the same folder.
"""

import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.freebusy",
]

def main():
    credentials_path = "credentials.json"

    if not os.path.exists(credentials_path):
        print("=" * 60)
        print("ERROR: credentials.json was not found in this folder.")
        print("=" * 60)
        print("How to get credentials.json:")
        print("1. Go to Google Cloud Console (https://console.cloud.google.com/).")
        print("2. Enable the Google Calendar API.")
        print("3. Configure the OAuth Consent Screen (Set Publishing status to 'In production').")
        print("4. Go to Credentials -> Create Credentials -> OAuth client ID.")
        print("5. Choose Application type: 'Desktop app'.")
        print("6. Download the JSON file and save it here as 'credentials.json'.")
        print("=" * 60)
        sys.exit(1)

    print("Starting Google OAuth local authorization flow...")
    print("A browser window will open automatically asking you to log in and authorize.")

    flow = InstalledAppFlow.from_client_secrets_file(
        credentials_path,
        scopes=SCOPES,
    )

    # access_type='offline' is required to get a refresh token
    # prompt='consent' ensures Google always returns a refresh_token
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )

    if not creds.refresh_token:
        print("\nWARNING: No refresh token returned by Google.")
        print("This happens if permissions were previously approved without prompt='consent'.")
        print("Revoke access at https://myaccount.google.com/permissions and run this script again.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("SUCCESS: Refresh token generated successfully!")
    print("=" * 60)
    print("Copy the following lines into your .env file:\n")
    print(f"GOOGLE_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print("=" * 60)

    # Prompt user if they want to automatically update or create .env
    env_file = ".env"
    answer = input("\nWould you like to automatically write/update these in your .env file? (y/n): ").strip().lower()
    if answer == "y":
        lines_to_add = {
            "GOOGLE_CLIENT_ID": creds.client_id,
            "GOOGLE_CLIENT_SECRET": creds.client_secret,
            "GOOGLE_REFRESH_TOKEN": creds.refresh_token,
        }

        existing_lines = []
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                existing_lines = f.readlines()

        updated_keys = set()
        new_lines = []
        for line in existing_lines:
            key = line.split("=")[0].strip()
            if key in lines_to_add:
                new_lines.append(f"{key}={lines_to_add[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)

        for key, val in lines_to_add.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={val}\n")

        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        print(".env updated successfully with your Google credentials!")

if __name__ == "__main__":
    main()
