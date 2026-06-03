import paho.mqtt.client as mqtt
import requests
import json
import time
from icalendar import Calendar
from datetime import datetime, timedelta, timezone

BROKER = "mqtt.thingsboard.cloud"
PORT = 1883
USERNAME = "104557267@student.swin.edu.au"
TOPIC_TELEMETRY = "v1/devices/me/telemetry"

CALENDAR_ICAL_URL = "https://calendar.google.com/calendar/ical/5e76a33242c624798945a5705dc147a0a28be3102d304e8291897ee81dc7368b%40group.calendar.google.com/private-a0833b019ab680a32149a360c70739ab/basic.ics"
DOSE_WINDOW_MIN = 5

client = mqtt.Client()
client.username_pw_set(USERNAME)
client.connect(BROKER, PORT, 60)
client.loop_start()

fired_doses = set()

while True:
    try:
        r = requests.get(CALENDAR_ICAL_URL, timeout=10)
        cal = Calendar.from_ical(r.text)
        now = datetime.now(timezone.utc)
        soon = now + timedelta(minutes=DOSE_WINDOW_MIN)

        for event in cal.walk('VEVENT'):
            dt = event.get('dtstart').dt
            if not isinstance(dt, datetime):
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            uid = str(event.get('uid'))
            if now <= dt <= soon and uid not in fired_doses:
                summary = str(event.get('summary') or 'Dose due')
                msg = f"DOSE-DUE: {summary} at {dt.astimezone().strftime('%H:%M')}"
                print(f"[Calendar] {msg}")
                client.publish(TOPIC_TELEMETRY, json.dumps({"alarm": msg}))
                fired_doses.add(uid)
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(30)