# Family profiles: add a member, see their reports and how each test changed over time.

from datetime import date

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from database import get_db
from helpers import get_own_profile, login_required

bp = Blueprint("profiles", __name__, url_prefix="/profiles")

RELATIONS = ["Self", "Mother", "Father", "Spouse", "Son", "Daughter", "Grandparent", "Sibling", "Other"]
SEXES = ["Female", "Male", "Other"]


def read_profile_form(fixed_relation=None):
    """Read and check the family-member form. Returns (name, relation, sex, birth_year, error).

    `fixed_relation` is used for your own profile: it always stays "Self".
    """
    name = request.form.get("name", "").strip()
    relation = fixed_relation or request.form.get("relation", "")
    sex = request.form.get("sex", "")
    birth_year = request.form.get("birth_year", type=int)

    error = None
    if not name or len(name) > 50:
        error = "Please enter a name (at most 50 characters)."
    elif relation not in RELATIONS or sex not in SEXES:
        error = "Please choose a relation and sex from the lists."
    elif birth_year is not None and not 1900 <= birth_year <= date.today().year:
        error = "Please enter a valid birth year."
    return name, relation, sex, birth_year, error


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create_profile():
    if request.method == "POST":
        name, relation, sex, birth_year, error = read_profile_form()
        if error:
            flash(error, "error")
        else:
            db = get_db()
            profile_id = db.execute(
                "INSERT INTO profiles (user_id, name, relation, birth_year, sex) VALUES (?, ?, ?, ?, ?)",
                (g.user["id"], name, relation, birth_year, sex),
            ).lastrowid
            db.commit()
            flash(f"Added {name}.", "success")
            return redirect(url_for("profiles.view_profile", profile_id=profile_id))
    return render_template("profile_form.html", relations=RELATIONS, sexes=SEXES, profile=None)


@bp.route("/<int:profile_id>/edit", methods=["GET", "POST"])
@login_required
def edit_profile(profile_id):
    """Change a family member's details. Their reports stay as they are."""
    profile = get_own_profile(profile_id)
    is_self = profile["relation"] == "Self"
    if request.method == "POST":
        name, relation, sex, birth_year, error = read_profile_form("Self" if is_self else None)
        if error:
            flash(error, "error")
        else:
            db = get_db()
            db.execute(
                "UPDATE profiles SET name = ?, relation = ?, sex = ?, birth_year = ? WHERE id = ?",
                (name, relation, sex, birth_year, profile_id),
            )
            db.commit()
            flash(f"Saved {name}'s details.", "success")
            return redirect(url_for("profiles.view_profile", profile_id=profile_id))
    return render_template("profile_form.html", relations=RELATIONS, sexes=SEXES, profile=profile)


@bp.route("/<int:profile_id>")
@login_required
def view_profile(profile_id):
    profile = get_own_profile(profile_id)
    db = get_db()
    reports = db.execute(
        "SELECT r.*,"
        " (SELECT COUNT(*) FROM results x WHERE x.report_id = r.id) AS tests,"
        " (SELECT COUNT(*) FROM results x WHERE x.report_id = r.id"
        "   AND x.status NOT IN ('normal', 'unknown')) AS flagged"
        " FROM reports r WHERE r.profile_id = ? ORDER BY r.report_date DESC, r.id DESC",
        (profile_id,),
    ).fetchall()

    # Trends: every numeric test that appears in at least two reports, oldest first.
    rows = db.execute(
        "SELECT x.canonical_name, x.value_num, x.unit, x.ref_low, x.ref_high, x.status, r.report_date"
        " FROM results x JOIN reports r ON r.id = x.report_id"
        " WHERE r.profile_id = ? AND x.value_num IS NOT NULL"
        " ORDER BY x.canonical_name, r.report_date, r.id",
        (profile_id,),
    ).fetchall()
    trends = {}
    for row in rows:
        trend = trends.setdefault(row["canonical_name"], {
            "dates": [], "values": [], "unit": row["unit"],
            "low": row["ref_low"], "high": row["ref_high"], "last_status": row["status"],
        })
        trend["dates"].append(row["report_date"])
        trend["values"].append(row["value_num"])
        trend["last_status"] = row["status"]
    # Keep tests seen in at least two reports, as a list (lists keep their order in JSON).
    trend_list = [{"name": name, **t} for name, t in trends.items() if len(t["values"]) >= 2]
    # Show tests that are currently out of range first.
    trend_list.sort(key=lambda t: (t["last_status"] == "normal", t["name"]))

    age = date.today().year - profile["birth_year"] if profile["birth_year"] else None
    return render_template("profile_detail.html", profile=profile, reports=reports,
                           trends=trend_list, age=age)


@bp.route("/<int:profile_id>/delete", methods=["POST"])
@login_required
def delete_profile(profile_id):
    profile = get_own_profile(profile_id)
    db = get_db()
    remaining = db.execute(
        "SELECT COUNT(*) FROM profiles WHERE user_id = ?", (g.user["id"],)
    ).fetchone()[0]
    if remaining <= 1:
        flash("You need at least one profile.", "error")
        return redirect(url_for("profiles.view_profile", profile_id=profile_id))
    db.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))  # CASCADE removes reports
    db.commit()
    flash(f"Deleted {profile['name']} and all their reports.", "success")
    return redirect(url_for("dashboard.dashboard"))
