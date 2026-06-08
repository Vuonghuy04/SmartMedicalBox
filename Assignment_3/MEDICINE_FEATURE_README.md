# Medicine Dashboard and API Integration

This feature adds a hardware-safe medicine dashboard for Assignment 3.

## What it does

- Searches openFDA drug label data by brand, generic, or substance name.
- Saves selected medicine metadata locally.
- Lets the user enter the physical expiry date, quantity, dose amount, and dose times.
- Creates Google Calendar event payloads for expiry and dose schedules.
- Sends Telegram reminders for due dose and expiry notifications.

Expiry dates are entered by the user because openFDA does not know the expiry date of a specific box or bottle.

## Run locally

```powershell
cd D:\IOT\main\SmartMedicalBox
python Assignment_3\medicine_dashboard.py
```

Open:

```text
http://localhost:8081/medicines
```

By default the medicine feature uses SQLite at:

```text
Assignment_3\medicine_dashboard.db
```

## Optional environment variables

```powershell
$env:OPENFDA_API_KEY="optional-openfda-key"
$env:SMARTBOX_CALENDAR_DRY_RUN="true"
$env:SMARTBOX_TELEGRAM_DRY_RUN="true"
$env:TELEGRAM_TOKEN="your-bot-token"
$env:TELEGRAM_CHAT_ID="your-chat-id"
$env:GOOGLE_SERVICE_ACCOUNT_FILE="D:\path\to\service-account.json"
$env:GOOGLE_CALENDAR_ID="your-calendar-id"
```

Google Calendar is dry-run by default unless a service account file is configured. Share the target calendar with the service account email before disabling dry-run.

Telegram is dry-run by default unless both `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are configured. The same variables are used by `EdgeServer.py` for Telegram commands and by `medicine_reminder.py` for medicine reminders.

To send real Telegram reminders:

```powershell
$env:TELEGRAM_TOKEN="your-new-bot-token"
$env:TELEGRAM_CHAT_ID="your-chat-id"
$env:SMARTBOX_TELEGRAM_DRY_RUN="false"
python Assignment_3\medicine_reminder.py
```

## Reminder worker

The dashboard has a manual reminder check button. For continuous reminders, run:

```powershell
python Assignment_3\medicine_reminder.py
```

The worker checks saved medicine schedules and sends Telegram messages when a dose time or expiry date is due.
