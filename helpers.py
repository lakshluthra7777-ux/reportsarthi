# Small helpers shared by several route modules.

import functools
import json
import re

from flask import abort, flash, g, redirect, url_for

from database import get_db
from ranges import decide_status, parse_number


def login_required(view):
    """Decorator: send the visitor to the login page if they are not logged in."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please log in first.", "error")
            return redirect(url_for("auth.login"))
        return view(**kwargs)
    return wrapped_view


def get_own_profile(profile_id):
    """Fetch a family profile that belongs to the logged-in user, or show 404."""
    profile = get_db().execute(
        "SELECT * FROM profiles WHERE id = ? AND user_id = ?", (profile_id, g.user["id"])
    ).fetchone()
    if profile is None:
        abort(404)
    return profile


def get_own_report(report_id):
    """Fetch a report (with its profile's details) owned by the logged-in user, or 404."""
    report = get_db().execute(
        "SELECT r.*, p.name AS profile_name, p.relation, p.sex, p.birth_year"
        " FROM reports r JOIN profiles p ON p.id = r.profile_id"
        " WHERE r.id = ? AND p.user_id = ?",
        (report_id, g.user["id"]),
    ).fetchone()
    if report is None:
        abort(404)
    return report


def save_report(db, profile_id, file_name, language, data):
    """Save an AI-read report and its test results in one transaction. Returns the report id.

    `data` has the shape produced by ai.read_report().
    """
    report_id = db.execute(
        "INSERT INTO reports (profile_id, file_name, lab_name, report_date, language, summary,"
        " doctor_questions) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (profile_id, file_name, data["lab_name"], data["report_date"], language,
         data["summary"], json.dumps(data["doctor_questions"])),
    ).lastrowid
    for test in data["tests"]:
        db.execute(
            "INSERT INTO results (report_id, name, canonical_name, category, value_text, value_num,"
            " unit, ref_low, ref_high, ref_text, status, critical, explanation, corrected)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (report_id, test["name"], test["canonical_name"], test["category"], test["value_text"],
             test["value_num"], test["unit"], test["ref_low"], test["ref_high"], test["ref_text"],
             test["status"], int(test["critical"]), test["explanation"], int(test.get("corrected", 0))),
        )
    db.commit()
    return report_id


def report_details(db, report):
    """Everything the report page shows about one report's results.

    Used by both the patient's page and the doctor's shared page, so they always agree.
    """
    results = db.execute(
        "SELECT * FROM results WHERE report_id = ? ORDER BY category, id", (report["id"],)
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
        (report["profile_id"], report["report_date"], report["report_date"], report["id"]),
    ):
        previous[row["canonical_name"]] = row  # later rows overwrite earlier: keeps the latest

    # Health score: the percentage of checked tests that are in the normal range.
    # Tests with no range ("unknown") are left out, so they neither help nor hurt.
    checked = counts["normal"] + counts["flagged"]
    score = round(counts["normal"] * 100 / checked) if checked else None

    # Per-category summary for the chips under the score: (name, flagged count).
    category_flags = [
        (name, sum(1 for r in rows if r["status"] in ("low", "high", "abnormal")))
        for name, rows in categories.items()
    ]
    return {"categories": categories, "counts": counts, "previous": previous,
            "total": len(results), "score": score, "category_flags": category_flags}


def pdf_file_name(report):
    """A safe file name like 'ReportSaathi_Sunita_2026-09-05.pdf'.

    Only letters, numbers, '-' and '_' are kept, so a name like 'Ram/Shyam' can't create
    a strange path when the browser saves the file.
    """
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", report["profile_name"]).strip("_") or "Report"
    return f"ReportSaathi_{name}_{report['report_date']}.pdf"


def get_own_pending(pending_id):
    """Fetch a report waiting for review that belongs to the logged-in user, or 404."""
    pending = get_db().execute(
        "SELECT pr.*, p.name AS profile_name FROM pending_reports pr"
        " JOIN profiles p ON p.id = pr.profile_id WHERE pr.id = ? AND p.user_id = ?",
        (pending_id, g.user["id"]),
    ).fetchone()
    if pending is None:
        abort(404)
    return pending


# ---------- Fixing values the AI misread ----------

def format_number(number):
    """Show a stored limit in a form box: None -> "", 12.0 -> "12", 0.45 -> "0.45"."""
    if number is None:
        return ""
    return str(int(number)) if float(number).is_integer() else str(number)


def apply_correction(form, key, test):
    """Read one row of the review form and return (updated test, was_changed).

    Returns (None, True) if the user ticked "remove". Fields the form doesn't send keep
    their old value. If anything changed, the status is decided again by our own code
    (decide_status), so a fixed value always gets the right low/normal/high flag.
    """
    if form.get(f"remove_{key}"):
        return None, True

    name = form.get(f"name_{key}", test["name"]).strip()[:100] or test["name"]
    value_text = form.get(f"value_{key}", test["value_text"]).strip()[:50] or test["value_text"]
    unit = form.get(f"unit_{key}", test["unit"]).strip()[:30]
    low_text = form.get(f"low_{key}", format_number(test["ref_low"])).strip()
    high_text = form.get(f"high_{key}", format_number(test["ref_high"])).strip()

    new = dict(test)
    new.update(name=name, value_text=value_text, unit=unit,
               value_num=parse_number(value_text),
               ref_low=parse_number(low_text), ref_high=parse_number(high_text))

    fields = ("name", "value_text", "unit", "ref_low", "ref_high")
    changed = any(new[field] != test[field] for field in fields)
    if not changed:
        return new, False

    if (new["ref_low"], new["ref_high"]) != (test["ref_low"], test["ref_high"]):
        # The range was edited, so rebuild the printed range text from the new numbers.
        low, high = format_number(new["ref_low"]), format_number(new["ref_high"])
        new["ref_text"] = f"{low} - {high}" if low and high else (f"< {high}" if high else (f"> {low}" if low else ""))
    new["status"] = decide_status(new["value_num"], new["ref_low"], new["ref_high"], test["status"])
    if new["status"] == "normal":
        new["critical"] = False  # a corrected value inside the range can't be urgent
    new["corrected"] = 1
    return new, True
