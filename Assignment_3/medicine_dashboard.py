from flask import Flask, flash, redirect, render_template, request, url_for

from calendar_service import CalendarService
import medicine_db
from medicine_config import FLASK_SECRET_KEY
from medicine_reminder import run_due_notifications
from medicine_service import MedicineValidationError, add_medicine_from_form
from openfda_client import OpenFDAError, search_medicines
from telegram_service import TelegramService


app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY


medicine_db.init_db()


@app.route("/")
def root():
    return redirect(url_for("medicines"))


@app.route("/medicines")
def medicines():
    return render_template(
        "medicine_list.html",
        medicines=medicine_db.list_medicines(),
        notification_logs=medicine_db.list_notification_logs(),
        calendar_status=CalendarService().status(),
        telegram_status=TelegramService().status(),
    )


@app.route("/medicines/search")
def search():
    query = (request.args.get("q") or "").strip()
    results = []
    error = None

    if query:
        try:
            results = search_medicines(query)
        except OpenFDAError as exc:
            error = str(exc)
        except Exception as exc:
            error = f"Could not reach openFDA: {exc}"

    return render_template(
        "medicine_search.html",
        query=query,
        results=results,
        error=error,
    )


@app.route("/medicines/add", methods=["POST"])
def add_medicine():
    try:
        medicine_id = add_medicine_from_form(request.form)
    except MedicineValidationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("search", q=request.form.get("brand_name", "")))
    except Exception as exc:
        flash(f"Could not add medicine: {exc}", "error")
        return redirect(url_for("search", q=request.form.get("brand_name", "")))

    flash("Medicine added, schedule saved, and calendar events prepared.", "success")
    return redirect(url_for("medicine_detail", medicine_id=medicine_id))


@app.route("/medicines/<int:medicine_id>")
def medicine_detail(medicine_id):
    medicine = medicine_db.get_medicine(medicine_id)
    if not medicine:
        flash("Medicine not found.", "error")
        return redirect(url_for("medicines"))

    medicine["schedules"] = medicine_db.list_schedules(medicine_id)
    medicine["calendar_events"] = medicine_db.list_calendar_events(medicine_id)
    return render_template("medicine_detail.html", medicine=medicine)


@app.route("/medicines/<int:medicine_id>/delete", methods=["POST"])
def delete_medicine(medicine_id):
    medicine_db.delete_medicine(medicine_id)
    flash("Medicine removed from the dashboard.", "success")
    return redirect(url_for("medicines"))


@app.route("/notifications/run", methods=["POST"])
def run_notifications():
    sent = run_due_notifications()
    if sent:
        flash(f"Sent {len(sent)} due notification(s).", "success")
    else:
        flash("No medicine reminders are due right now.", "info")
    return redirect(url_for("medicines"))


@app.route("/health")
def health():
    return {
        "ok": True,
        "calendar": CalendarService().status(),
        "telegram": TelegramService().status(),
    }


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8081)
