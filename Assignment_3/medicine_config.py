import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


# Medicine dashboard storage. SQLite is the default so the feature can be
# developed without MariaDB, Arduino, or cloud credentials.
DB_BACKEND = os.getenv("SMARTBOX_MEDICINE_DB_BACKEND", "sqlite").strip().lower()
SQLITE_PATH = os.getenv(
    "SMARTBOX_MEDICINE_SQLITE_PATH",
    str(BASE_DIR / "medicine_dashboard.db"),
)
MYSQL_CONFIG = {
    "host": os.getenv("SMARTBOX_DB_HOST", "localhost"),
    "user": os.getenv("SMARTBOX_DB_USER", "pi"),
    "password": os.getenv("SMARTBOX_DB_PASSWORD", ""),
    "database": os.getenv("SMARTBOX_DB_NAME", "IOT_LOCKBOX"),
}

# openFDA
OPENFDA_BASE_URL = os.getenv(
    "OPENFDA_BASE_URL",
    "https://api.fda.gov/drug/label.json",
)
OPENFDA_API_KEY = os.getenv("OPENFDA_API_KEY", "").strip()
OPENFDA_TIMEOUT_SECONDS = env_int("OPENFDA_TIMEOUT_SECONDS", 10)

# Google Calendar
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
SMARTBOX_TIMEZONE = os.getenv("SMARTBOX_TIMEZONE", "Australia/Sydney")
CALENDAR_DRY_RUN = env_bool(
    "SMARTBOX_CALENDAR_DRY_RUN",
    default=not bool(GOOGLE_SERVICE_ACCOUNT_FILE),
)

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_DRY_RUN = env_bool(
    "SMARTBOX_TELEGRAM_DRY_RUN",
    default=not bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID),
)

# Reminder worker
NOTIFICATION_WINDOW_MINUTES = env_int("SMARTBOX_NOTIFICATION_WINDOW_MINUTES", 10)
EXPIRY_NOTIFY_TIME = os.getenv("SMARTBOX_EXPIRY_NOTIFY_TIME", "09:00")

# Flask
FLASK_SECRET_KEY = os.getenv("SMARTBOX_FLASK_SECRET_KEY", "smartbox-dev-key")
