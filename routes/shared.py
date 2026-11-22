# The doctor's view: a read-only report page opened from a secret share link.
# This is the only page that works WITHOUT logging in, so it checks the link carefully.

from datetime import date, datetime, timezone

from flask import Blueprint, abort, make_response, render_template

from database import get_db
from helpers import report_details

bp = Blueprint("shared", __name__, url_prefix="/s")


@bp.route("/<token>")
def view(token):
    db = get_db()
    link = db.execute("SELECT * FROM share_links WHERE token = ?", (token,)).fetchone()
    if link is None:
        abort(404)  # unknown token: don't reveal anything

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")  # same format as SQLite
    expired = link["expires_at"] <= now_utc
    if link["revoked"] or expired:
        reason = "turned off by the patient" if link["revoked"] else "expired"
        return render_template("shared_closed.html", reason=reason), 410  # 410 = Gone

    db.execute("UPDATE share_links SET views = views + 1 WHERE id = ?", (link["id"],))
    db.commit()

    report = db.execute(
        "SELECT r.*, p.name AS profile_name, p.sex, p.birth_year"
        " FROM reports r JOIN profiles p ON p.id = r.profile_id WHERE r.id = ?",
        (link["report_id"],),
    ).fetchone()
    age = date.today().year - report["birth_year"] if report["birth_year"] else None

    response = make_response(render_template(
        "shared_report.html", report=report, age=age, link=link, **report_details(db, report),
    ))
    # Don't let search engines index it, and don't send the secret URL to other sites.
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response
