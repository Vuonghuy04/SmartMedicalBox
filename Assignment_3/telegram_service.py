import requests

from medicine_config import TELEGRAM_CHAT_ID, TELEGRAM_DRY_RUN, TELEGRAM_TOKEN


class TelegramService:
    def __init__(self):
        self.dry_run = TELEGRAM_DRY_RUN
        self.reason = ""
        if self.dry_run:
            self.reason = "dry run enabled or token/chat id missing"

    def status(self):
        return {
            "dry_run": self.dry_run,
            "chat_configured": bool(TELEGRAM_CHAT_ID),
            "token_configured": bool(TELEGRAM_TOKEN),
            "reason": self.reason,
        }

    def send_message(self, message):
        if self.dry_run:
            print(f"[Telegram dry-run] {message}")
            return {"ok": True, "status": "dry_run", "message": message}

        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10,
        )
        response.raise_for_status()
        return {"ok": True, "status": "sent", "message": message}
