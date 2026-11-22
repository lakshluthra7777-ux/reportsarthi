# Lab reports: upload (PDF or photo), view the explained results, ask questions, delete.

import json
import os
import secrets
from datetime import date

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ai import LANGUAGES, AIError, ask_about_report, read_report
from database import get_db
from helpers import (
    apply_correction, format_number, get_own_pending, get_own_profile, get_own_report,
    login_required, pdf_file_name, report_details, save_report,
)

bp = Blueprint("reports", __name__, url_prefix="/reports")

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # the AI accepts images up to 5 MB


def detect_file_type(data):
    """Work out the real file type from its first bytes ("magic numbers").

    We don't trust the file name: "virus.exe" renamed to "report.pdf" is still not a PDF.
    """
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def describe_person(profile):
    """Short description for the AI, e.g. 'Female, age 54'."""
    parts = [profile["sex"] or "Sex not given"]
    if profile["birth_year"]:
        parts.append(f"age {date.today().year - profile['birth_year']}")
    return ", ".join(parts)


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    db = get_db()
    profiles = db.execute(
        "SELECT * FROM profiles WHERE user_id = ? ORDER BY id", (g.user["id"],)
    ).fetchall()

    if request.method == "POST":
        profile_id = request.form.get("profile_id", type=int)
        language = request.form.get("language", "English")
        file = request.files.get("report")

        error = None
        if language not in LANGUAGES:
            error = "Please choose a language from the list."
        elif file is None or file.filename == "":
            error = "Please choose a file to upload."

        if error is None:
            profile = get_own_profile(profile_id)  # 404 if it isn't this user's profile
            data = file.read()
            media_type = detect_file_type(data)
            if media_type is None:
                error = "Please upload a PDF or a photo (JPG, PNG or WEBP)."
            elif media_type != "application/pdf" and len(data) > MAX_IMAGE_BYTES:
                error = "Photos must be under 5 MB. Try a smaller photo or a PDF."

        if error is None:
            try:
                report_data = read_report(data, media_type, language, describe_person(profile))
            except AIError as ai_error:
                error = str(ai_error)

        if error:
            flash(error, "error")
        else:
            # Don't save yet: keep what the AI read until the user has checked it.
            db.execute("DELETE FROM pending_reports WHERE created_at < datetime('now', '-1 day')")
            pending_id = db.execute(
                "INSERT INTO pending_reports (profile_id, file_name, language, data) VALUES (?, ?, ?, ?)",
                (profile_id, file.filename[:100], language, json.dumps(report_data)),
            ).lastrowid
            db.commit()
            flash(f"Read {len(report_data['tests'])} test results. Please check them before saving.", "success")
            return redirect(url_for("reports.review", pending_id=pending_id))

    selected = request.args.get("profile", type=int)
    return render_template("upload.html", profiles=profiles, languages=LANGUAGES, selected=selected)


@bp.route("/review/<int:pending_id>", methods=["GET", "POST"])
@login_required
def review(pending_id):
    """Human-in-the-loop step: the user checks (and fixes) what the AI read before it is saved."""
    pending = get_own_pending(pending_id)
    data = json.loads(pending["data"])
    db = get_db()

    if request.method == "POST":
        if request.form.get("action") == "discard":
            db.execute("DELETE FROM pending_reports WHERE id = ?", (pending_id,))
            db.commit()
            flash("Discarded. Nothing was saved.", "success")
            return redirect(url_for("reports.upload"))

        tests, corrected, removed = [], 0, 0
        for index, test in enumerate(data["tests"]):
            new, changed = apply_correction(request.form, index, test)
            if new is None:
                removed += 1
            else:
                tests.append(new)
                corrected += changed
        if not tests:
            flash("You removed every result. Keep at least one, or click Discard.", "error")
            return redirect(url_for("reports.review", pending_id=pending_id))

        data["tests"] = tests
        report_id = save_report(db, pending["profile_id"], pending["file_name"], pending["language"], data)
        db.execute("DELETE FROM pending_reports WHERE id = ?", (pending_id,))
        db.commit()
        note = f" You corrected {corrected} and removed {removed}." if corrected or removed else ""
        flash(f"Report saved with {len(tests)} results.{note}", "success")
        return redirect(url_for("reports.view_report", report_id=report_id))

    rows = [{**test, "key": index} for index, test in enumerate(data["tests"])]
    return render_template("review.html", mode="review", rows=rows, title=pending["profile_name"],
                           info=data, pending=pending, format_number=format_number)


@bp.route("/<int:report_id>/edit", methods=["GET", "POST"])
@login_required
def edit_report(report_id):
    """Fix a value in a report that was already saved."""
    report = get_own_report(report_id)
    db = get_db()
    rows = [dict(row) for row in db.execute(
        "SELECT * FROM results WHERE report_id = ? ORDER BY category, id", (report_id,)
    )]

    if request.method == "POST":
        updates, corrected, removed = [], 0, 0
        for row in rows:
            new, changed = apply_correction(request.form, row["id"], row)
            if new is None:
                removed += 1
            elif changed:
                corrected += 1
            updates.append((row, new, changed))
        if removed == len(rows):
            flash("You can't remove every result. Delete the whole report instead.", "error")
            return redirect(url_for("reports.edit_report", report_id=report_id))

        for row, new, changed in updates:
            if new is None:
                db.execute("DELETE FROM results WHERE id = ?", (row["id"],))
            elif changed:
                db.execute(
                    "UPDATE results SET name = ?, value_text = ?, value_num = ?, unit = ?, ref_low = ?,"
                    " ref_high = ?, ref_text = ?, status = ?, critical = ?, corrected = 1 WHERE id = ?",
                    (new["name"], new["value_text"], new["value_num"], new["unit"], new["ref_low"],
                     new["ref_high"], new["ref_text"], new["status"], int(new["critical"]), row["id"]),
                )
        db.commit()
        flash(f"Saved. {corrected} value(s) corrected, {removed} removed.", "success")
        return redirect(url_for("reports.view_report", report_id=report_id))

    for row in rows:
        row["key"] = row["id"]
    return render_template("review.html", mode="edit", rows=rows, title=report["profile_name"],
                           info=report, report=report, format_number=format_number)


@bp.route("/<int:report_id>")
@login_required
def view_report(report_id):
    report = get_own_report(report_id)
    db = get_db()
    details = report_details(db, report)  # results, counts, score... (shared with the doctor view)
    questions = db.execute(
        "SELECT * FROM questions WHERE report_id = ? ORDER BY id", (report_id,)
    ).fetchall()
    # Share links that still work, newest first.
    links = db.execute(
        "SELECT * FROM share_links WHERE report_id = ? AND revoked = 0"
        " AND expires_at > datetime('now') ORDER BY id DESC",
        (report_id,),
    ).fetchall()
    base_url = os.environ.get("PUBLIC_URL", "").rstrip("/") or request.host_url.rstrip("/")
    return render_template(
        "report_detail.html", report=report, **details,
        doctor_questions=json.loads(report["doctor_questions"]), questions=questions,
        links=links, base_url=base_url, share_choices=SHARE_HOURS,
    )


@bp.route("/<int:report_id>/pdf")
@login_required
def download_pdf(report_id):
    """A clean white version of the report; the browser turns it into a PDF and downloads it."""
    report = get_own_report(report_id)
    age = date.today().year - report["birth_year"] if report["birth_year"] else None
    return render_template(
        "report_pdf.html", report=report, age=age, for_doctor=False, now_date=date.today().isoformat(),
        doctor_questions=json.loads(report["doctor_questions"]),
        file_name=pdf_file_name(report), **report_details(get_db(), report),
    )


# ---------- Sharing with a doctor ----------

SHARE_HOURS = {24: "24 hours", 72: "3 days", 168: "7 days"}


@bp.route("/<int:report_id>/share", methods=["POST"])
@login_required
def create_share(report_id):
    """Make a secret read-only link to this report that expires after the chosen time."""
    get_own_report(report_id)  # 404 if it isn't this user's report
    hours = request.form.get("hours", type=int)
    if hours not in SHARE_HOURS:
        hours = 24
    token = secrets.token_urlsafe(24)  # 32 random characters: impossible to guess
    db = get_db()
    db.execute(
        "INSERT INTO share_links (report_id, token, expires_at) VALUES (?, ?, datetime('now', ?))",
        (report_id, token, f"+{hours} hours"),
    )
    db.commit()
    flash(f"Share link created. It works for {SHARE_HOURS[hours]}.", "success")
    return redirect(url_for("reports.view_report", report_id=report_id) + "#share")


@bp.route("/<int:report_id>/share/<int:link_id>/revoke", methods=["POST"])
@login_required
def revoke_share(report_id, link_id):
    get_own_report(report_id)
    db = get_db()
    db.execute("UPDATE share_links SET revoked = 1 WHERE id = ? AND report_id = ?", (link_id, report_id))
    db.commit()
    flash("Link turned off. It no longer opens the report.", "success")
    return redirect(url_for("reports.view_report", report_id=report_id) + "#share")


@bp.route("/<int:report_id>/ask", methods=["POST"])
@login_required
def ask(report_id):
    report = get_own_report(report_id)
    question = request.form.get("question", "").strip()
    if not question or len(question) > 300:
        flash("Please type a question (up to 300 characters).", "error")
        return redirect(url_for("reports.view_report", report_id=report_id) + "#ask")

    db = get_db()
    results = db.execute("SELECT * FROM results WHERE report_id = ?", (report_id,)).fetchall()
    try:
        answer = ask_about_report(question, report, results, report["language"])
    except AIError as error:
        flash(str(error), "error")
    else:
        db.execute(
            "INSERT INTO questions (report_id, question, answer) VALUES (?, ?, ?)",
            (report_id, question, answer),
        )
        db.commit()
    # Post/Redirect/Get, and jump back down to the questions section.
    return redirect(url_for("reports.view_report", report_id=report_id) + "#ask")


@bp.route("/<int:report_id>/delete", methods=["POST"])
@login_required
def delete_report(report_id):
    report = get_own_report(report_id)
    db = get_db()
    db.execute("DELETE FROM reports WHERE id = ?", (report_id,))  # CASCADE removes results
    db.commit()
    flash("Report deleted.", "success")
    return redirect(url_for("profiles.view_profile", profile_id=report["profile_id"]))
