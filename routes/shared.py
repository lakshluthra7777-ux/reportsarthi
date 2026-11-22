# The doctor's view: a read-only report page opened from a secret share link.
# These are the only pages that work WITHOUT logging in, so they check the link carefully.

from datetime import date, datetime, timezone

from flask import Blueprint, abort, make_response, render_template

from database import get_db
from helpers import pdf_file_name, report_details

bp = Blueprint("shared", __name__, url_prefix="/s")


def open_link(token):
    """Check a share link. Returns (link, report, None) if it works, or (None, None, error_response)."""
    db = get_db()
    link = db.execute("SELECT * FROM share_links WHERE token = ?", (token,)).fetchone()
    if link is None:
        abort(404)  # unknown token: don't reveal anything

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")  # same format as SQLite
    if link["revoked"] or link["expires_at"] <= now_utc:
        reason = "turned off by the patient" if link["revoked"] else "expired"
        return None, None, (render_template("shared_closed.html", reason=reason), 410)  # 410 = Gone

    report = db.execute(
        "SELECT r.*, p.name AS profile_name, p.relation, p.sex, p.birth_year"
        " FROM reports r JOIN profiles p ON p.id = r.profile_id WHERE r.id = ?",
        (link["report_id"],),
    ).fetchone()
    return link, report, None


def private_response(html):
    """Headers for pages opened by a secret link: not indexed, not cached, URL not leaked."""
    response = make_response(html)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


def age_of(report):
    return date.today().year - report["birth_year"] if report["birth_year"] else None


@bp.route("/<token>")
def view(token):
    link, report, error = open_link(token)
    if error:
        return error
    db = get_db()
    db.execute("UPDATE share_links SET views = views + 1 WHERE id = ?", (link["id"],))
    db.commit()
    return private_response(render_template(
        "shared_report.html", report=report, age=age_of(report), link=link,
        **report_details(db, report),
    ))


@bp.route("/<token>/pdf")
def pdf(token):
    """The doctor can download the shared report as a PDF too (doesn't count as another view)."""
    link, report, error = open_link(token)
    if error:
        return error
    return private_response(render_template(
        "report_pdf.html", report=report, age=age_of(report), for_doctor=True,
        now_date=date.today().isoformat(),
        doctor_questions=[], file_name=pdf_file_name(report), **report_details(get_db(), report),
    ))
