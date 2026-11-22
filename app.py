# ReportSaathi - main Flask application.
# This file creates the app and connects the pieces. The routes live in routes/:
#   auth.py       register / login / logout
#   dashboard.py  family overview, sample data
#   profiles.py   family members, report history, trend charts
#   reports.py    upload and read reports with AI, results page, questions, share links
#   shared.py     the doctor's read-only view, opened from a share link (no login)

import os

from dotenv import load_dotenv
from flask import Flask, g, redirect, render_template, url_for

from database import close_db, init_db
from routes import auth, dashboard, profiles, reports, shared

load_dotenv()  # reads .env into environment variables

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-secret")
app.config["DATABASE"] = os.path.join(app.root_path, "reportsaathi.db")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # reject uploads bigger than 20 MB
app.config["SESSION_COOKIE_NAME"] = "reportsaathi_session"  # own cookie, separate from other local apps
app.config["SESSION_COOKIE_HTTPONLY"] = True  # JavaScript can't read the login cookie
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # cookie isn't sent on most cross-site requests
app.teardown_appcontext(close_db)  # close the DB connection after every request

for module in (auth, dashboard, profiles, reports, shared):
    app.register_blueprint(module.bp)


@app.route("/")
def home():
    if g.user:
        return redirect(url_for("dashboard.dashboard"))
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ---------- Error pages ----------

@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(413)
def file_too_large(error):
    return render_template("error.html", code=413, message="That file is too large (max 20 MB)."), 413


@app.errorhandler(500)
def server_error(error):
    return render_template("error.html", code=500, message="Something went wrong on our side."), 500


if __name__ == "__main__":
    with app.app_context():
        init_db()  # creates reportsaathi.db and any missing tables
    # HOST=0.0.0.0 in .env lets phones on the same Wi-Fi open the app (e.g. to scan a share QR).
    host = os.environ.get("HOST", "127.0.0.1")
    # Debug mode (auto-reload + error pages with a code console) is only safe on this computer:
    # anyone on the network could use the debugger console to run code, so it's off otherwise.
    app.run(host=host, debug=host in ("127.0.0.1", "localhost"))
