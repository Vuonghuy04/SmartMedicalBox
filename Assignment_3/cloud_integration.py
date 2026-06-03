import paho.mqtt.client as mqtt
import pymysql
import time
import json
import requests
from icalendar import Calendar
from datetime import datetime, timedelta, timezone

# ── MQTT Configuration (ThingsBoard) ──────────────────────────────────────────
BROKER = "mqtt.thingsboard.cloud"
PORT            = 1883
USERNAME        = "SmartBox"
TOPIC_TELEMETRY = "v1/devices/me/telemetry"
TOPIC_RPC_REQ   = "v1/devices/me/rpc/request/+"
TOPIC_RPC_RESP  = "v1/devices/me/rpc/response/{}"

# ── Database Configuration ────────────────────────────────────────────────────
DB_CONFIG = dict(host="localhost", user="pi", password="", database="IOT_LOCKBOX")

# ── Timers ────────────────────────────────────────────────────────────────────
TELEMETRY_INTERVAL = 5   # publish live sensor data every 5 seconds
ANALYTICS_INTERVAL = 30  # publish 24h analytics every 30 seconds

# == Calendar =================================================================
CALENDAR_ICAL_URL  = "https://calendar.google.com/calendar/ical/d3f4e56bb2aacfe18e1c4f197e5b1c08db4d5f1109f3be2b555cb683d826b46d%40group.calendar.google.com/private-a3157e28efdf3eae2b6d233a400664a1/basic.ics"
CALENDAR_INTERVAL  = 60   # check every 60 seconds
DOSE_WINDOW_MIN    = 5    # alert if dose is within next 5 minutes

# ── Callback functions ────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe(TOPIC_RPC_REQ)

def on_message(client, userdata, msg):
    print(msg.topic + " " + str(msg.payload))

    try:
        request_id = msg.topic.split("/")[-1]
        payload    = json.loads(msg.payload.decode())
        method     = payload.get("method", "")
        params     = payload.get("params", {})

        dbconn = pymysql.connect(**DB_CONFIG)
        cursor = dbconn.cursor()

        if method == "lock":
            cursor.execute("INSERT INTO commands (command) VALUES ('LOCK')")
            cursor.execute("INSERT INTO access_log (action, method) VALUES ('LOCK','CLOUD')")

        elif method == "unlock":
            cursor.execute("INSERT INTO commands (command) VALUES ('UNLOCK')")
            cursor.execute("INSERT INTO access_log (action, method) VALUES ('UNLOCK','CLOUD')")

        elif method == "mute_alarm":
            cursor.execute("INSERT INTO commands (command) VALUES ('MUTE')")

        elif method == "clear_all_alarms":
            cursor.execute("INSERT INTO commands (command) VALUES ('CLEAR_ALL')")

        elif method == "set_threshold":
            param = params.get("param", "").upper()
            value = params.get("value")
            if param in {"TEMP_MIN","TEMP_MAX","HUM_MIN","HUM_MAX","LDR_MAX"} and value is not None:
                cursor.execute(
                    "REPLACE INTO thresholds (param, value) VALUES (%s,%s)",
                    (param, float(value))
                )

        dbconn.commit()
        cursor.close()
        dbconn.close()

        client.publish(TOPIC_RPC_RESP.format(request_id), json.dumps({"success": True}))

    except Exception as e:
        print("RPC error:", e)

def check_upcoming_doses():
    try:
        r = requests.get(CALENDAR_ICAL_URL, timeout=10)
        if r.status_code != 200:
            print(f"Calendar fetch failed: HTTP {r.status_code}")
            return

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
                local_time = dt.astimezone().strftime('%H:%M')
                msg = f"DOSE-DUE: {summary} at {local_time}"
                print(f"[Calendar] {msg}")
                client.publish(TOPIC_TELEMETRY, json.dumps({"alarm": msg}))
                fired_doses.add(uid)
    except Exception as e:
        print(f"Calendar check error: {e}")

# ── Initialize MQTT client ────────────────────────────────────────────────────
client = mqtt.Client()
client.username_pw_set(USERNAME)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_start()

# ── Timers ────────────────────────────────────────────────────────────────────
last_telemetry = 0
last_analytics = 0
last_calendar_check = 0
fired_doses = set()

try:
    while True:
        now = time.time()

        # ── Publish live sensor data every 5 seconds ──────────────────────
        if now - last_telemetry >= TELEMETRY_INTERVAL:
            dbconn = pymysql.connect(**DB_CONFIG)
            cursor = dbconn.cursor()

            cursor.execute(
                "SELECT light, temperature, humidity FROM sensor_data "
                "ORDER BY timestamp DESC LIMIT 1"
            )
            row = cursor.fetchone()

            cursor.execute("SELECT param, value FROM thresholds")
            t = {r[0]: r[1] for r in cursor.fetchall()}

            cursor.close()
            dbconn.close()

            if row:
                light, temp, hum = row[0], row[1], row[2]

                payload = json.dumps({
                    "temperature":     float(temp),
                    "humidity":        float(hum),
                    "light":           float(light),
                    "alarm_temp":      int(temp < t.get("TEMP_MIN",15) or temp > t.get("TEMP_MAX",30)),
                    "alarm_hum":       int(hum  < t.get("HUM_MIN",40)  or hum  > t.get("HUM_MAX",70)),
                    "alarm_ldr":       int(light > t.get("LDR_MAX",25)),
                    "thresh_temp_min": float(t.get("TEMP_MIN", 15)),
                    "thresh_temp_max": float(t.get("TEMP_MAX", 30)),
                    "thresh_hum_min":  float(t.get("HUM_MIN",  40)),
                    "thresh_hum_max":  float(t.get("HUM_MAX",  70)),
                })

                print("Publishing telemetry:", payload)
                client.publish(TOPIC_TELEMETRY, payload)

            last_telemetry = now

        # ── Publish 24h analytics every 30 seconds ────────────────────────
        if now - last_analytics >= ANALYTICS_INTERVAL:
            dbconn = pymysql.connect(**DB_CONFIG)
            cursor = dbconn.cursor()

            cursor.execute("""SELECT AVG(light), AVG(temperature), AVG(humidity)
                              FROM sensor_data
                              WHERE timestamp >= NOW() - INTERVAL 24 HOUR""")
            r = cursor.fetchone()

            cursor.execute("""SELECT alarm_type, COUNT(*) FROM alarms
                              WHERE timestamp >= NOW() - INTERVAL 24 HOUR
                              GROUP BY alarm_type""")
            counts = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.close()
            dbconn.close()

            analytics = json.dumps({
                "avg_temperature_24h":     round(float(r[1] or 0), 2),
                "avg_humidity_24h":        round(float(r[2] or 0), 2),
                "avg_light_24h":           round(float(r[0] or 0), 2),
                "alarm_count_intrusion":   counts.get("UNAUTHORISED-ACCESS", 0),
                "alarm_count_temperature": counts.get("TEMPERATURE", 0),
                "alarm_count_humidity":    counts.get("HUMIDITY", 0),
                "alarm_count_wrong_pwd":   counts.get("WRONG-PASSWORD", 0),
                "total_alarms_24h":        sum(counts.values()),
            })

            print("Publishing analytics:", analytics)
            client.publish(TOPIC_TELEMETRY, analytics)
            last_analytics = now

            # ── Check calendar for upcoming doses ────────────────────────────────
            if now - last_calendar_check >= CALENDAR_INTERVAL:
                check_upcoming_doses()
                last_calendar_check = now

        time.sleep(0.1)

except KeyboardInterrupt:
    print("Program interrupted by user.")
finally:
    client.loop_stop()
    client.disconnect()
