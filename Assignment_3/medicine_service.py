import json
import re
from datetime import date, datetime

import medicine_db
from calendar_service import CalendarService, split_dose_times


class MedicineValidationError(Exception):
    pass


def _require(form, key, label):
    value = (form.get(key) or "").strip()
    if not value:
        raise MedicineValidationError(f"{label} is required.")
    return value


def _parse_date(value, label):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise MedicineValidationError(f"{label} must use YYYY-MM-DD.") from exc


def _parse_quantity(value):
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise MedicineValidationError("Quantity must be a whole number.") from exc
    if parsed < 0:
        raise MedicineValidationError("Quantity cannot be negative.")
    return parsed


def _normalize_dose_times(value):
    parts = [part.strip() for part in re.split(r"[,;\s]+", value) if part.strip()]
    if not parts:
        raise MedicineValidationError("At least one dose time is required.")
    for part in parts:
        try:
            datetime.strptime(part, "%H:%M")
        except ValueError as exc:
            raise MedicineValidationError("Dose times must use 24-hour HH:MM format.") from exc
    return ", ".join(parts)


def add_medicine_from_form(form):
    expiry_date = _parse_date(_require(form, "expiry_date", "Expiry date"), "Expiry date")
    start_date = _parse_date(
        form.get("start_date") or date.today().isoformat(),
        "Start date",
    )
    end_date_raw = (form.get("end_date") or "").strip()
    end_date = _parse_date(end_date_raw, "End date") if end_date_raw else None
    if end_date and end_date < start_date:
        raise MedicineValidationError("End date cannot be before start date.")

    dose_times = _normalize_dose_times(_require(form, "dose_times", "Dose times"))
    source_json = form.get("source_json") or "{}"
    try:
        json.loads(source_json)
    except json.JSONDecodeError:
        source_json = "{}"

    medicine = {
        "openfda_set_id": form.get("source_id"),
        "brand_name": _require(form, "brand_name", "Medicine name"),
        "generic_name": form.get("generic_name"),
        "manufacturer": form.get("manufacturer"),
        "product_type": form.get("product_type"),
        "route": form.get("route"),
        "substance_name": form.get("substance_name"),
        "warnings": form.get("warnings"),
        "purpose": form.get("purpose"),
        "dosage_and_administration": form.get("dosage_and_administration"),
        "source_json": source_json,
        "expiry_date": expiry_date,
        "quantity": _parse_quantity(form.get("quantity")),
        "notes": form.get("notes"),
    }
    medicine_id = medicine_db.create_medicine(medicine)

    schedule = {
        "medicine_id": medicine_id,
        "dose_amount": _require(form, "dose_amount", "Dose amount"),
        "dose_times": dose_times,
        "start_date": start_date,
        "end_date": end_date,
        "instructions": form.get("instructions"),
    }
    schedule_id = medicine_db.create_schedule(schedule)

    stored_medicine = medicine_db.get_medicine(medicine_id)
    stored_schedule = medicine_db.get_schedule(schedule_id)

    calendar = CalendarService()
    for event in calendar.create_medicine_events(stored_medicine, stored_schedule):
        medicine_db.create_calendar_event(event)

    return medicine_id


def calendar_preview_for_form(form):
    dose_times = _normalize_dose_times(form.get("dose_times") or "")
    return split_dose_times(dose_times)
