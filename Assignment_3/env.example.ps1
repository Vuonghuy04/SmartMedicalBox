# Copy these commands into PowerShell and replace the placeholder values.
# Do not commit real tokens or service account paths.

$env:TELEGRAM_TOKEN = "replace-with-new-bot-token"
$env:TELEGRAM_CHAT_ID = "replace-with-your-chat-id"
$env:SMARTBOX_TELEGRAM_DRY_RUN = "false"

$env:GOOGLE_SERVICE_ACCOUNT_FILE = "D:\path\to\service-account.json"
$env:GOOGLE_CALENDAR_ID = "primary"
$env:SMARTBOX_CALENDAR_DRY_RUN = "false"

# Optional: use the original MariaDB/MySQL database instead of SQLite.
# $env:SMARTBOX_MEDICINE_DB_BACKEND = "mysql"
# $env:SMARTBOX_DB_HOST = "localhost"
# $env:SMARTBOX_DB_USER = "pi"
# $env:SMARTBOX_DB_PASSWORD = "replace-with-password"
# $env:SMARTBOX_DB_NAME = "IOT_LOCKBOX"
