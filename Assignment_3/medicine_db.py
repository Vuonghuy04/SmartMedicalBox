import json
import sqlite3
from contextlib import contextmanager

import pymysql

from medicine_config import DB_BACKEND, MYSQL_CONFIG, SQLITE_PATH


def _is_sqlite():
    return DB_BACKEND != "mysql"


def _placeholder():
    return "?" if _is_sqlite() else "%s"


@contextmanager
def get_connection():
    if _is_sqlite():
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
    else:
        conn = pymysql.connect(
            **MYSQL_CONFIG,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _dict_rows(rows):
    return [dict(row) for row in rows]


def _execute_schema(conn, statements):
    cursor = conn.cursor()
    for statement in statements:
        cursor.execute(statement)
    cursor.close()


def init_db():
    if _is_sqlite():
        schema = [
            """
            CREATE TABLE IF NOT EXISTS medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                openfda_set_id TEXT,
                brand_name TEXT NOT NULL,
                generic_name TEXT,
                manufacturer TEXT,
                product_type TEXT,
                route TEXT,
                substance_name TEXT,
                warnings TEXT,
                purpose TEXT,
                dosage_and_administration TEXT,
                source_json TEXT,
                expiry_date TEXT NOT NULL,
                quantity INTEGER,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS medicine_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER NOT NULL,
                dose_amount TEXT NOT NULL,
                dose_times TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                instructions TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER NOT NULL,
                schedule_id INTEGER,
                event_type TEXT NOT NULL,
                calendar_event_id TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id),
                FOREIGN KEY (schedule_id) REFERENCES medicine_schedules(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS notification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER NOT NULL,
                schedule_id INTEGER,
                event_type TEXT NOT NULL,
                due_at TEXT NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (medicine_id, schedule_id, event_type, due_at, channel)
            )
            """,
        ]
    else:
        schema = [
            """
            CREATE TABLE IF NOT EXISTS medicines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                openfda_set_id VARCHAR(255),
                brand_name VARCHAR(255) NOT NULL,
                generic_name TEXT,
                manufacturer TEXT,
                product_type VARCHAR(120),
                route TEXT,
                substance_name TEXT,
                warnings TEXT,
                purpose TEXT,
                dosage_and_administration TEXT,
                source_json LONGTEXT,
                expiry_date DATE NOT NULL,
                quantity INT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS medicine_schedules (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medicine_id INT NOT NULL,
                dose_amount VARCHAR(120) NOT NULL,
                dose_times TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                instructions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medicine_id INT NOT NULL,
                schedule_id INT,
                event_type VARCHAR(60) NOT NULL,
                calendar_event_id VARCHAR(255) NOT NULL,
                status VARCHAR(60) NOT NULL,
                payload_json LONGTEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id),
                FOREIGN KEY (schedule_id) REFERENCES medicine_schedules(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS notification_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medicine_id INT NOT NULL,
                schedule_id INT,
                event_type VARCHAR(60) NOT NULL,
                due_at VARCHAR(60) NOT NULL,
                channel VARCHAR(60) NOT NULL,
                status VARCHAR(60) NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_notification (
                    medicine_id, schedule_id, event_type, due_at, channel
                )
            )
            """,
        ]

    with get_connection() as conn:
        _execute_schema(conn, schema)


def create_medicine(medicine):
    fields = [
        "openfda_set_id",
        "brand_name",
        "generic_name",
        "manufacturer",
        "product_type",
        "route",
        "substance_name",
        "warnings",
        "purpose",
        "dosage_and_administration",
        "source_json",
        "expiry_date",
        "quantity",
        "notes",
    ]
    marker = _placeholder()
    sql = (
        f"INSERT INTO medicines ({', '.join(fields)}) "
        f"VALUES ({', '.join([marker] * len(fields))})"
    )
    values = [medicine.get(field) for field in fields]

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        medicine_id = cursor.lastrowid
        cursor.close()
        return medicine_id


def create_schedule(schedule):
    fields = [
        "medicine_id",
        "dose_amount",
        "dose_times",
        "start_date",
        "end_date",
        "instructions",
    ]
    marker = _placeholder()
    sql = (
        f"INSERT INTO medicine_schedules ({', '.join(fields)}) "
        f"VALUES ({', '.join([marker] * len(fields))})"
    )
    values = [schedule.get(field) for field in fields]

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        schedule_id = cursor.lastrowid
        cursor.close()
        return schedule_id


def create_calendar_event(event):
    marker = _placeholder()
    sql = (
        "INSERT INTO calendar_events "
        "(medicine_id, schedule_id, event_type, calendar_event_id, status, payload_json) "
        f"VALUES ({', '.join([marker] * 6)})"
    )
    values = [
        event.get("medicine_id"),
        event.get("schedule_id"),
        event.get("event_type"),
        event.get("calendar_event_id"),
        event.get("status"),
        json.dumps(event.get("payload"), default=str),
    ]
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        cursor.close()


def get_medicine(medicine_id):
    marker = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM medicines WHERE id = {marker}", [medicine_id])
        row = cursor.fetchone()
        cursor.close()
    return dict(row) if row else None


def get_schedule(schedule_id):
    marker = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM medicine_schedules WHERE id = {marker}",
            [schedule_id],
        )
        row = cursor.fetchone()
        cursor.close()
    return dict(row) if row else None


def list_schedules(medicine_id):
    marker = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT *
            FROM medicine_schedules
            WHERE medicine_id = {marker}
            ORDER BY created_at DESC
            """,
            [medicine_id],
        )
        rows = cursor.fetchall()
        cursor.close()
    return _dict_rows(rows)


def list_calendar_events(medicine_id):
    marker = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT *
            FROM calendar_events
            WHERE medicine_id = {marker}
            ORDER BY created_at DESC
            """,
            [medicine_id],
        )
        rows = cursor.fetchall()
        cursor.close()
    return _dict_rows(rows)


def list_medicines():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM medicines ORDER BY created_at DESC")
        rows = _dict_rows(cursor.fetchall())
        cursor.close()

    for medicine in rows:
        medicine["schedules"] = list_schedules(medicine["id"])
        medicine["calendar_events"] = list_calendar_events(medicine["id"])
    return rows


def list_notification_logs(limit=20):
    marker = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT n.*, m.brand_name
            FROM notification_log n
            JOIN medicines m ON m.id = n.medicine_id
            ORDER BY n.created_at DESC
            LIMIT {marker}
            """,
            [limit],
        )
        rows = cursor.fetchall()
        cursor.close()
    return _dict_rows(rows)


def notification_exists(medicine_id, schedule_id, event_type, due_at, channel):
    marker = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT id
            FROM notification_log
            WHERE medicine_id = {marker}
              AND {('schedule_id IS NULL' if schedule_id is None else 'schedule_id = ' + marker)}
              AND event_type = {marker}
              AND due_at = {marker}
              AND channel = {marker}
            LIMIT 1
            """,
            (
                [medicine_id, event_type, due_at, channel]
                if schedule_id is None
                else [medicine_id, schedule_id, event_type, due_at, channel]
            ),
        )
        exists = cursor.fetchone() is not None
        cursor.close()
    return exists


def log_notification(medicine_id, schedule_id, event_type, due_at, channel, status, message):
    marker = _placeholder()
    sql = (
        "INSERT INTO notification_log "
        "(medicine_id, schedule_id, event_type, due_at, channel, status, message) "
        f"VALUES ({', '.join([marker] * 7)})"
    )
    values = [
        medicine_id,
        schedule_id,
        event_type,
        due_at,
        channel,
        status,
        message,
    ]

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, values)
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def delete_medicine(medicine_id):
    marker = _placeholder()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM notification_log WHERE medicine_id = {marker}", [medicine_id])
        cursor.execute(f"DELETE FROM calendar_events WHERE medicine_id = {marker}", [medicine_id])
        cursor.execute(f"DELETE FROM medicine_schedules WHERE medicine_id = {marker}", [medicine_id])
        cursor.execute(f"DELETE FROM medicines WHERE id = {marker}", [medicine_id])
        cursor.close()
