# Lab reports: upload (PDF or photo), view the explained results, ask questions, delete.

import json
from datetime import date

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ai import LANGUAGES, AIError, ask_about_report, read_report
from database import get_db
from helpers import (
    apply_correction, format_number, get_own_pending, get_own_profile, get_own_report,
    login_required, save_report,
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
    results = db.execute(
        "SELECT * FROM results WHERE report_id = ? ORDER BY category, id", (report_id,)
    ).fetchall()

    # Group results by category (Blood Count, Lipid Profile...) for the page.
    categories = {}
    for result in results:
        categories.setdefault(result["category"], []).append(result)

    counts = {"normal": 0, "flagged": 0, "critical": 0, "corrected": 0}
    for result in results:
        counts["corrected"] += result["corrected"]
        if result["status"] in ("low", "high", "abnormal"):
            counts["flagged"] += 1
        elif result["status"] == "normal":
            counts["normal"] += 1
        counts["critical"] += result["critical"]

    # The same test in this person's previous report, to show "was X" next to each value.
    previous = {}
    for row in db.execute(
        "SELECT x.canonical_name, x.value_text, r.report_date FROM results x"
        " JOIN reports r ON r.id = x.report_id"
        " WHERE r.profile_id = ? AND (r.report_date < ? OR (r.report_date = ? AND r.id < ?))"
        " ORDER BY r.report_date, r.id",
        (report["profile_id"], report["report_date"], report["report_date"], report_id),
    ):
        previous[row["canonical_name"]] = row  # later rows overwrite earlier: keeps the latest

    questions = db.execute(
        "SELECT * FROM questions WHERE report_id = ? ORDER BY id", (report_id,)
    ).fetchall()

    # Health score: the percentage of checked tests that are in the normal range.
    # Tests with no range ("unknown") are left out, so they neither help nor hurt.
    checked = counts["normal"] + counts["flagged"]
    score = round(counts["normal"] * 100 / checked) if checked else None

    # Per-category summary for the chips under the score: (name, flagged count).
    category_flags = [
        (name, sum(1 for r in rows if r["status"] in ("low", "high", "abnormal")))
        for name, rows in categories.items()
    ]
    return render_template(
        "report_detail.html", report=report, categories=categories, counts=counts,
        doctor_questions=json.loads(report["doctor_questions"]), previous=previous,
        questions=questions, total=len(results), score=score, category_flags=category_flags,
    )


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
