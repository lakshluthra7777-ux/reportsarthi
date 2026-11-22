# Register, log in, log out.

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db

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
