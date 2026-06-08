import uuid
from datetime import datetime, timedelta

from medicine_config import (
    CALENDAR_DRY_RUN,
    GOOGLE_CALENDAR_ID,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    SMARTBOX_TIMEZONE,
)


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


class CalendarService:
    def __init__(self):
        self._service = None
        self.reason = ""
        self.dry_run = CALENDAR_DRY_RUN

        if self.dry_run:
            self.reason = "dry run enabled"
            return

        if not GOOGLE_SERVICE_ACCOUNT_FILE:
            self.dry_run = True
            self.reason = "GOOGLE_SERVICE_ACCOUNT_FILE is not configured"
            return

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            self.dry_run = True
            self.reason = "Google Calendar libraries are not installed"
            return

        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=SCOPES,
        )
        self._service = build("calendar", "v3", credentials=credentials)

    def status(self):
        return {
            "dry_run": self.dry_run,
            "reason": self.reason,
            "calendar_id": GOOGLE_CALENDAR_ID,
        }

    def create_event(self, event_body):
        if self.dry_run:
            return {
                "id": f"dry-run-{uuid.uuid4().hex[:12]}",
                "status": "dry_run",
                "payload": event_body,
            }

        created = (
            self._service.events()
            .insert(calendarId=GOOGLE_CALENDAR_ID, body=event_body)
            .execute()
        )
        return {
            "id": created["id"],
            "status": "created",
            "payload": event_body,
        }

    def create_medicine_events(self, medicine, schedule):
        events = []

        expiry_body = build_expiry_event(medicine)
        expiry_result = self.create_event(expiry_body)
        events.append(
            {
                "medicine_id": medicine["id"],
                "schedule_id": None,
                "event_type": "expiry",
                "calendar_event_id": expiry_result["id"],
                "status": expiry_result["status"],
                "payload": expiry_result["payload"],
            }
        )

        for dose_time in split_dose_times(schedule["dose_times"]):
            dose_body = build_dose_event(medicine, schedule, dose_time)
            dose_result = self.create_event(dose_body)
            events.append(
                {
                    "medicine_id": medicine["id"],
                    "schedule_id": schedule["id"],
                    "event_type": "dose",
                    "calendar_event_id": dose_result["id"],
                    "status": dose_result["status"],
                    "payload": dose_result["payload"],
                }
            )

        return events


def split_dose_times(dose_times):
    return [part.strip() for part in dose_times.split(",") if part.strip()]


def build_expiry_event(medicine):
    expiry_date = medicine["expiry_date"]
    end_date = (datetime.strptime(expiry_date, "%Y-%m-%d") + timedelta(days=1)).date()
    return {
        "summary": f"Medicine expiry: {medicine['brand_name']}",
        "description": (
            f"{medicine['brand_name']} expires today.\n"
            f"Generic name: {medicine.get('generic_name') or 'N/A'}\n"
            f"Manufacturer: {medicine.get('manufacturer') or 'N/A'}"
        ),
        "start": {"date": expiry_date},
        "end": {"date": end_date.isoformat()},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 60}],
        },
    }


def build_dose_event(medicine, schedule, dose_time):
    start_date = schedule["start_date"]
    end_date = schedule.get("end_date") or medicine["expiry_date"]
    start_dt = f"{start_date}T{dose_time}:00"

    parsed = datetime.strptime(start_dt, "%Y-%m-%dT%H:%M:%S")
    end_dt = parsed + timedelta(minutes=15)

    recurrence = []
    if end_date:
        until = end_date.replace("-", "") + "T235959Z"
        recurrence.append(f"RRULE:FREQ=DAILY;UNTIL={until}")

    return {
        "summary": f"Take {medicine['brand_name']}",
        "description": (
            f"Dose: {schedule['dose_amount']}\n"
            f"Instructions: {schedule.get('instructions') or 'N/A'}\n"
            f"Expiry date: {medicine['expiry_date']}"
        ),
        "start": {
            "dateTime": start_dt,
            "timeZone": SMARTBOX_TIMEZONE,
        },
        "end": {
            "dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": SMARTBOX_TIMEZONE,
        },
        "recurrence": recurrence,
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 10}],
        },
    }
