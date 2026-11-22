# Register, log in, log out.

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db
from helpers import login_required

bp = Blueprint("auth", __name__)


@bp.before_app_request
def load_logged_in_user():
    """Before every request, look up the logged-in user (if any) and store it in g.user."""
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        error = None
        if not username or not password:
            error = "Username and password are required."
        elif len(username) > 30:
            error = "Username must be 30 characters or fewer."
        elif len(password) < 8:
            error = "Password must be at least 8 characters (this app stores health data)."

        if error is None:
            db = get_db()
            try:
                user_id = db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                ).lastrowid
                # Every account starts with a profile for the user themself.
                db.execute(
                    "INSERT INTO profiles (user_id, name, relation) VALUES (?, ?, 'Self')",
                    (user_id, username),
                )
                db.commit()
            except db.IntegrityError:  # UNIQUE constraint on username
                error = f"Username '{username}' is already taken."
            else:
                flash("Account created. Please log in.", "success")
                return redirect(url_for("auth.login"))

        flash(error, "error")
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        # Same message for both cases, so attackers can't find out which usernames exist.
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect username or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard.dashboard"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# ---------- Account settings ----------

@bp.route("/account")
@login_required
def account():
    stats = get_db().execute(
        "SELECT (SELECT COUNT(*) FROM profiles WHERE user_id = :u) AS profiles,"
        " (SELECT COUNT(*) FROM reports r JOIN profiles p ON p.id = r.profile_id"
        "  WHERE p.user_id = :u) AS reports",
        {"u": g.user["id"]},
    ).fetchone()
    return render_template("account.html", stats=stats)


@bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    # Always ask for the current password, so someone using an unlocked computer
    # can't take over the account.
    if not check_password_hash(g.user["password_hash"], current):
        flash("Your current password is not correct.", "error")
    elif len(new) < 8:
        flash("The new password must be at least 8 characters.", "error")
    elif new != confirm:
        flash("The two new passwords don't match.", "error")
    elif new == current:
        flash("The new password must be different from the current one.", "error")
    else:
        db = get_db()
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (generate_password_hash(new), g.user["id"]))
        db.commit()
        flash("Password changed.", "success")
    return redirect(url_for("auth.account"))


@bp.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    """Delete the user and, through ON DELETE CASCADE, every profile, report and share link."""
    if not check_password_hash(g.user["password_hash"], request.form.get("password", "")):
        flash("Password not correct. Your account was not deleted.", "error")
        return redirect(url_for("auth.account"))
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (g.user["id"],))
    db.commit()
    session.clear()
    flash("Your account and all its reports have been permanently deleted.", "success")
    return redirect(url_for("home"))
