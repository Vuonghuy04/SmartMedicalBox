import time
from datetime import date, datetime, timedelta

import medicine_db
from medicine_config import EXPIRY_NOTIFY_TIME, NOTIFICATION_WINDOW_MINUTES
from telegram_service import TelegramService


def _parse_time(value):
    return datetime.strptime(value, "%H:%M").time()


def _parse_date(value):
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _split_times(value):
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _active_on(schedule, today):
    start = _parse_date(schedule["start_date"])
    end = _parse_date(schedule["end_date"]) if schedule.get("end_date") else None
    return start <= today and (end is None or today <= end)


def _already_logged(medicine_id, schedule_id, event_type, due_at):
    return medicine_db.notification_exists(
        medicine_id,
        schedule_id,
        event_type,
        due_at,
        "telegram",
    )


def _log(medicine_id, schedule_id, event_type, due_at, status, message):
    medicine_db.log_notification(
        medicine_id,
        schedule_id,
        event_type,
        due_at,
        "telegram",
        status,
        message,
    )


def run_due_notifications(now=None):
    medicine_db.init_db()
    now = now or datetime.now()
    today = now.date()
    window_start = now - timedelta(minutes=NOTIFICATION_WINDOW_MINUTES)
    telegram = TelegramService()
    sent = []

    for medicine in medicine_db.list_medicines():
        expiry_date = _parse_date(medicine["expiry_date"])
        if expiry_date == today:
            due_at = f"{today.isoformat()} {EXPIRY_NOTIFY_TIME}"
            if not _already_logged(medicine["id"], None, "expiry", due_at):
                message = (
                    f"Medicine expiry reminder: {medicine['brand_name']} expires today "
                    f"({medicine['expiry_date']})."
                )
                result = telegram.send_message(message)
                _log(medicine["id"], None, "expiry", due_at, result["status"], message)
                sent.append({"type": "expiry", "medicine": medicine["brand_name"]})

        for schedule in medicine.get("schedules", []):
            if not _active_on(schedule, today):
                continue
            for dose_time in _split_times(schedule["dose_times"]):
                scheduled = datetime.combine(today, _parse_time(dose_time))
                if not (window_start <= scheduled <= now):
                    continue
                due_at = scheduled.strftime("%Y-%m-%d %H:%M")
                if _already_logged(medicine["id"], schedule["id"], "dose", due_at):
                    continue
                message = (
                    f"Pill schedule reminder: take {schedule['dose_amount']} of "
                    f"{medicine['brand_name']} now."
                )
                if schedule.get("instructions"):
                    message += f" Instructions: {schedule['instructions']}"
                result = telegram.send_message(message)
                _log(
                    medicine["id"],
                    schedule["id"],
                    "dose",
                    due_at,
                    result["status"],
                    message,
                )
                sent.append(
                    {
                        "type": "dose",
                        "medicine": medicine["brand_name"],
                        "time": dose_time,
                    }
                )

    return sent


def run_loop(interval_seconds=60):
    while True:
        sent = run_due_notifications()
        if sent:
            print(f"Sent {len(sent)} medicine reminder(s).")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_loop()
