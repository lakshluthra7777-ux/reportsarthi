# Home screen after login: every family member with their latest report at a glance.

import os

from flask import Blueprint, flash, g, redirect, render_template, url_for

from database import get_db
from helpers import login_required
from sample_data import load_sample_data

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    # For each profile: how many reports, the latest report, and its out-of-range count.
    profiles = db.execute(
        "SELECT p.*,"
        " (SELECT COUNT(*) FROM reports r WHERE r.profile_id = p.id) AS report_count,"
        " (SELECT r.id FROM reports r WHERE r.profile_id = p.id"
        "   ORDER BY r.report_date DESC, r.id DESC LIMIT 1) AS latest_id,"
        " (SELECT r.report_date FROM reports r WHERE r.profile_id = p.id"
        "   ORDER BY r.report_date DESC, r.id DESC LIMIT 1) AS latest_date"
        " FROM profiles p WHERE p.user_id = ? ORDER BY p.id",
        (g.user["id"],),
    ).fetchall()

    cards = []
    for profile in profiles:
        flagged, critical = 0, 0
        if profile["latest_id"]:
            counts = db.execute(
                "SELECT SUM(status != 'normal' AND status != 'unknown') AS flagged,"
                " SUM(critical) AS critical FROM results WHERE report_id = ?",
                (profile["latest_id"],),
            ).fetchone()
            flagged, critical = counts["flagged"] or 0, counts["critical"] or 0
        cards.append({**dict(profile), "flagged": flagged, "critical": critical})

    recent = db.execute(
        "SELECT r.id, r.lab_name, r.report_date, p.name AS profile_name,"
        " (SELECT COUNT(*) FROM results x WHERE x.report_id = r.id) AS tests,"
        " (SELECT COUNT(*) FROM results x WHERE x.report_id = r.id"
        "   AND x.status NOT IN ('normal', 'unknown')) AS flagged"
        " FROM reports r JOIN profiles p ON p.id = r.profile_id"
        " WHERE p.user_id = ? ORDER BY r.created_at DESC, r.id DESC LIMIT 5",
        (g.user["id"],),
    ).fetchall()

    total_reports = sum(card["report_count"] for card in cards)
    return render_template(
        "dashboard.html", cards=cards, recent=recent, total_reports=total_reports,
        ai_enabled=bool(os.environ.get("GEMINI_API_KEY")),
    )


@bp.route("/dashboard/sample-data", methods=["POST"])
@login_required
def sample_data():
    """Add sample family members and reports to an empty account (for demos, no API key needed)."""
    db = get_db()
    report_count = db.execute(
        "SELECT COUNT(*) FROM reports r JOIN profiles p ON p.id = r.profile_id WHERE p.user_id = ?",
        (g.user["id"],),
    ).fetchone()[0]
    if report_count:
        flash("Sample data can only be loaded into an account with no reports.", "error")
    else:
        load_sample_data(db, g.user["id"])
        flash("Sample family and reports loaded. Open a report to explore.", "success")
    return redirect(url_for("dashboard.dashboard"))
