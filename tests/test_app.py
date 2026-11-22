# Automated tests for ReportSaathi. Run with:  python -m pytest
# Each test gets a fresh, empty database in a temporary folder.
# The AI functions are replaced with fake ones, so tests never call the real API.

import io
from datetime import date

import pytest

import ai
import app as reportsaathi
from database import init_db
from ranges import decide_status, parse_number
from routes import reports
from routes.reports import detect_file_type

PDF_BYTES = b"%PDF-1.4\n% fake report for tests\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 100


@pytest.fixture
def client(tmp_path):
    reportsaathi.app.config.update(TESTING=True, DATABASE=str(tmp_path / "test.db"))
    with reportsaathi.app.app_context():
        init_db()
    return reportsaathi.app.test_client()


def register_and_login(client, username="asha", password="secret123"):
    client.post("/register", data={"username": username, "password": password})
    return client.post("/login", data={"username": username, "password": password})


def fake_ai_reply():
    """What the AI might send back for a small report, before clean_report() runs."""
    return {
        "is_lab_report": True,
        "lab_name": "City Diagnostics",
        "report_date": "2026-10-01",
        "tests": [
            {"name": "Hb", "canonical_name": "Haemoglobin", "category": "Blood Count", "value": "10.5",
             "unit": "g/dL", "ref_low": "12", "ref_high": "15", "ref_text": "12.0 - 15.0",
             "flag": "normal",  # wrong on purpose: our code must still say "low"
             "critical": False, "explanation": "Carries oxygen in the blood."},
            {"name": "Urine Sugar", "canonical_name": "Urine Sugar", "category": "Urine", "value": "Negative",
             "unit": "", "ref_low": "", "ref_high": "", "ref_text": "Negative", "flag": "normal",
             "critical": False, "explanation": "Checks for sugar in urine."},
            {"name": "", "canonical_name": "", "category": "", "value": "", "unit": "", "ref_low": "",
             "ref_high": "", "ref_text": "", "flag": "unknown", "critical": False, "explanation": ""},
        ],
        "summary": "Haemoglobin is a little low. Urine sugar is normal.",
        "doctor_questions": ["Do I need iron tablets?"],
    }


def fake_read_report(file_bytes, media_type, language, person):
    return ai.clean_report(fake_ai_reply())


def upload(client, data_bytes=PDF_BYTES, name="report.pdf", profile_id=1, language="English"):
    """Upload a file. A successful upload lands on the review screen (nothing saved yet)."""
    return client.post(
        "/reports/upload",
        data={"profile_id": str(profile_id), "language": language, "report": (io.BytesIO(data_bytes), name)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def upload_and_save(client, corrections=None, pending_id=1):
    """Upload, then click Save on the review screen (optionally with corrections typed in)."""
    upload(client)
    data = {"action": "save", **(corrections or {})}
    return client.post(f"/reports/review/{pending_id}", data=data, follow_redirects=True)


# ---------- Pages and login ----------

def test_home_page_loads(client):
    assert b"ReportSaathi" in client.get("/").data


def test_unknown_page_shows_404(client):
    assert client.get("/nope").status_code == 404


def test_register_creates_self_profile_and_welcome(client):
    register_and_login(client)
    page = client.get("/dashboard")
    assert b"Namaste, asha" in page.data
    assert b"Load sample data" in page.data
    assert b"Self" in page.data


def test_short_password_is_rejected(client):
    response = client.post("/register", data={"username": "bob", "password": "1234567"})
    assert b"at least 8 characters" in response.data


@pytest.mark.parametrize("url", ["/dashboard", "/reports/upload", "/profiles/new", "/profiles/1", "/reports/1"])
def test_pages_need_login(client, url):
    response = client.get(url)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------- Profiles ----------

def test_add_family_member(client):
    register_and_login(client)
    response = client.post(
        "/profiles/new",
        data={"name": "Sunita", "relation": "Mother", "sex": "Female", "birth_year": "1968"},
        follow_redirects=True,
    )
    assert b"Added Sunita" in response.data
    assert str(date.today().year - 1968).encode() + b" years" in response.data


def test_invalid_profile_is_rejected(client):
    register_and_login(client)
    response = client.post("/profiles/new", data={"name": "X", "relation": "Boss", "sex": "Female"})
    assert b"choose a relation" in response.data


def test_edit_family_member(client):
    register_and_login(client)
    client.post("/profiles/new", data={"name": "Sunita", "relation": "Mother", "sex": "Female", "birth_year": "1968"})
    page = client.get("/profiles/2/edit")
    assert b'value="Sunita"' in page.data and b'value="1968"' in page.data
    page = client.post("/profiles/2/edit",
                       data={"name": "Sunita Sharma", "relation": "Mother", "sex": "Female", "birth_year": "1966"},
                       follow_redirects=True)
    assert b"Saved Sunita Sharma" in page.data
    assert str(date.today().year - 1966).encode() + b" years" in page.data


def test_own_profile_stays_self(client):
    register_and_login(client)
    client.post("/profiles/1/edit", data={"name": "Asha", "relation": "Father", "sex": "Female"})
    assert b"Self" in client.get("/profiles/1").data   # relation can't be changed away from Self


def test_cannot_edit_someone_elses_profile(client):
    register_and_login(client, "asha")
    client.get("/logout")
    register_and_login(client, "ravi")
    assert client.get("/profiles/1/edit").status_code == 404


def test_change_password(client):
    register_and_login(client)
    assert b"Change password" in client.get("/account").data
    page = client.post("/account/password", follow_redirects=True, data={
        "current_password": "secret123", "new_password": "newpass456", "confirm_password": "newpass456"})
    assert b"Password changed" in page.data
    client.get("/logout")
    assert client.post("/login", data={"username": "asha", "password": "secret123"}).status_code == 200  # old fails
    assert client.post("/login", data={"username": "asha", "password": "newpass456"}).status_code == 302  # new works


@pytest.mark.parametrize("form, message", [
    ({"current_password": "wrong", "new_password": "newpass456", "confirm_password": "newpass456"}, b"not correct"),
    ({"current_password": "secret123", "new_password": "short", "confirm_password": "short"}, b"at least 8"),
    ({"current_password": "secret123", "new_password": "newpass456", "confirm_password": "other4567"}, b"don&#39;t match"),
    ({"current_password": "secret123", "new_password": "secret123", "confirm_password": "secret123"}, b"must be different"),
])
def test_change_password_rules(client, form, message):
    register_and_login(client)
    page = client.post("/account/password", data=form, follow_redirects=True)
    assert message in page.data


def test_delete_account_removes_everything(client):
    register_and_login(client)
    client.post("/dashboard/sample-data")
    page = client.post("/account/delete", data={"password": "wrong"}, follow_redirects=True)
    assert b"was not deleted" in page.data

    page = client.post("/account/delete", data={"password": "secret123"}, follow_redirects=True)
    assert b"permanently deleted" in page.data
    import sqlite3
    db = sqlite3.connect(reportsaathi.app.config["DATABASE"])
    for table in ("users", "profiles", "reports", "results"):
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0  # ON DELETE CASCADE
    assert client.get("/dashboard").status_code == 302  # logged out


def test_cannot_delete_last_profile(client):
    register_and_login(client)
    response = client.post("/profiles/1/delete", follow_redirects=True)
    assert b"at least one profile" in response.data


# ---------- Uploading and reading reports ----------

def test_upload_shows_review_before_saving(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    page = upload(client)
    assert b"Read 2 test results" in page.data           # the empty row was skipped
    assert b"Compare each value with your paper report" in page.data
    assert b'value="10.5"' in page.data
    assert client.get("/reports/1").status_code == 404   # not saved yet


def test_saving_unchanged_review(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    page = upload_and_save(client)
    assert b"Report saved with 2 results" in page.data
    assert b"City Diagnostics" in page.data
    assert b"Haemoglobin is a little low" in page.data
    assert b"LOW" in page.data                            # our code overrode the AI's "normal"
    assert b"Do I need iron tablets?" in page.data
    assert b"AI accuracy 100%" in page.data
    assert client.get("/reports/review/1").status_code == 404  # the pending copy is gone


def test_correcting_a_value_recomputes_status(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    # Row 0 is Haemoglobin: the AI read 10.5 but the paper says 13.5 (normal 12-15).
    page = upload_and_save(client, {"value_0": "13.5"})
    assert b"You corrected 1 and removed 0" in page.data
    assert b"13.5" in page.data
    assert b"NORMAL" in page.data and b">LOW<" not in page.data
    assert b"AI accuracy 50%" in page.data               # 1 of 2 values corrected
    assert b"corrected" in page.data


def test_removing_a_row_on_review(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    page = upload_and_save(client, {"remove_1": "1"})     # remove "Urine Sugar"
    assert b"Report saved with 1 results" in page.data
    assert b"Urine Sugar" not in page.data


def test_cannot_remove_every_row(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    page = upload_and_save(client, {"remove_0": "1", "remove_1": "1"})
    assert b"removed every result" in page.data


def test_discard_upload(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    upload(client)
    page = client.post("/reports/review/1", data={"action": "discard"}, follow_redirects=True)
    assert b"Nothing was saved" in page.data
    assert client.get("/reports/review/1").status_code == 404


def test_cannot_review_someone_elses_upload(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client, "asha")
    upload(client)
    client.get("/logout")
    register_and_login(client, "ravi")
    assert client.get("/reports/review/1").status_code == 404


def test_fix_value_in_saved_report(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    upload_and_save(client)
    assert b"Fix a value" in client.get("/reports/1/edit").data
    # Result id 1 is Haemoglobin. Fix its range to 10-12, so 10.5 becomes normal.
    page = client.post("/reports/1/edit", data={"low_1": "10", "high_1": "12"}, follow_redirects=True)
    assert b"1 value(s) corrected" in page.data
    assert b"10 - 12" in page.data
    assert b"AI accuracy 50%" in page.data


# ---------- Sharing with a doctor ----------

def share_token(client, report_id=1, hours="24"):
    """Create a share link and return its token (read from the database)."""
    client.post(f"/reports/{report_id}/share", data={"hours": hours})
    import sqlite3
    db = sqlite3.connect(reportsaathi.app.config["DATABASE"])
    return db.execute("SELECT token FROM share_links ORDER BY id DESC LIMIT 1").fetchone()[0]


def test_share_link_opens_without_login(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    upload_and_save(client)
    page = client.get("/reports/1")
    assert b"Share with your doctor" in page.data

    token = share_token(client)
    assert len(token) >= 30                      # long random token
    assert token.encode() in client.get("/reports/1").data  # link + QR shown to the patient

    client.get("/logout")                        # the doctor is not logged in
    shared = client.get(f"/s/{token}")
    assert shared.status_code == 200
    assert b"Shared report, read-only" in shared.data
    assert b"10.5" in shared.data and b"City Diagnostics" in shared.data
    assert shared.headers["Referrer-Policy"] == "no-referrer"
    assert b"Ask about this report" not in shared.data   # no patient-only features


def test_share_link_counts_views(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    upload_and_save(client)
    token = share_token(client)
    client.get(f"/s/{token}")
    client.get(f"/s/{token}")
    assert b"Opened 2 times" in client.get("/reports/1").data


def test_revoked_share_link_stops_working(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    upload_and_save(client)
    token = share_token(client)
    client.post("/reports/1/share/1/revoke")
    response = client.get(f"/s/{token}")
    assert response.status_code == 410
    assert b"turned off by the patient" in response.data


def test_expired_share_link_stops_working(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    upload_and_save(client)
    token = share_token(client)
    import sqlite3
    db = sqlite3.connect(reportsaathi.app.config["DATABASE"])
    db.execute("UPDATE share_links SET expires_at = datetime('now', '-1 minute')")
    db.commit()
    response = client.get(f"/s/{token}")
    assert response.status_code == 410
    assert b"expired" in response.data
    assert token.encode() not in client.get("/reports/1").data  # no longer listed as active


def test_unknown_share_token_is_404(client):
    assert client.get("/s/not-a-real-token").status_code == 404


def test_cannot_share_someone_elses_report(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client, "asha")
    upload_and_save(client)
    client.get("/logout")
    register_and_login(client, "ravi")
    assert client.post("/reports/1/share", data={"hours": "24"}).status_code == 404


# ---------- Download as PDF ----------

def test_pdf_page_has_report_and_file_name(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    upload_and_save(client)
    assert b"Download PDF" in client.get("/reports/1").data
    page = client.get("/reports/1/pdf")
    assert page.status_code == 200
    assert b"html2pdf" in page.data
    assert b"ReportSaathi_asha_2026-10-01.pdf" in page.data
    assert b"10.5" in page.data and b"Haemoglobin is a little low" in page.data
    assert b"Do I need iron tablets?" in page.data


def test_pdf_file_name_is_safe():
    from helpers import pdf_file_name
    assert pdf_file_name({"profile_name": "Ram/Shyam ..\\x", "report_date": "2026-01-02"}) == \
        "ReportSaathi_Ram_Shyam_x_2026-01-02.pdf"
    assert pdf_file_name({"profile_name": "सुनीता", "report_date": "2026-01-02"}) == \
        "ReportSaathi_Report_2026-01-02.pdf"


def test_cannot_download_someone_elses_pdf(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client, "asha")
    upload_and_save(client)
    client.get("/logout")
    register_and_login(client, "ravi")
    assert client.get("/reports/1/pdf").status_code == 404


def test_doctor_can_download_shared_pdf(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    upload_and_save(client)
    token = share_token(client)
    client.get("/logout")
    page = client.get(f"/s/{token}/pdf")
    assert page.status_code == 200
    assert b"shared with doctor" in page.data
    assert b"Do I need iron tablets?" not in page.data   # patient-only section left out
    assert page.headers["Referrer-Policy"] == "no-referrer"

    client.post("/login", data={"username": "asha", "password": "secret123"})
    client.post("/reports/1/share/1/revoke")
    client.get("/logout")
    assert client.get(f"/s/{token}/pdf").status_code == 410  # turned off: no PDF either


def test_old_database_is_migrated(tmp_path):
    """A results table from the first version (no 'corrected' column) gets the column added."""
    import sqlite3
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    # The results table exactly as version 1 created it (no "corrected" column).
    old.execute(
        "CREATE TABLE results (id INTEGER PRIMARY KEY AUTOINCREMENT, report_id INTEGER NOT NULL,"
        " name TEXT NOT NULL, canonical_name TEXT NOT NULL, category TEXT NOT NULL,"
        " value_text TEXT NOT NULL, value_num REAL, unit TEXT NOT NULL, ref_low REAL, ref_high REAL,"
        " ref_text TEXT NOT NULL, status TEXT NOT NULL, critical INTEGER NOT NULL DEFAULT 0,"
        " explanation TEXT NOT NULL)"
    )
    old.commit()
    old.close()
    reportsaathi.app.config.update(DATABASE=str(path))
    with reportsaathi.app.app_context():
        init_db()
    columns = [row[1] for row in sqlite3.connect(path).execute("PRAGMA table_info(results)")]
    assert "corrected" in columns


def test_upload_photo_is_accepted(client, monkeypatch):
    received = {}

    def fake(file_bytes, media_type, language, person):
        received["type"] = media_type
        received["language"] = language
        return ai.clean_report(fake_ai_reply())

    monkeypatch.setattr(reports, "read_report", fake)
    register_and_login(client)
    upload(client, PNG_BYTES, "photo.png", language="Hindi")
    assert received == {"type": "image/png", "language": "Hindi"}


def test_renamed_file_is_rejected(client):
    register_and_login(client)
    page = upload(client, b"MZ this is really a program", "report.pdf")
    assert b"Please upload a PDF or a photo" in page.data


def test_large_photo_is_rejected(client):
    register_and_login(client)
    big_png = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 1)
    page = upload(client, big_png, "big.png")
    assert b"Photos must be under 5 MB" in page.data


def test_ai_error_is_shown(client, monkeypatch):
    def failing(*args):
        raise ai.AIError("This doesn't look like a lab report.")

    monkeypatch.setattr(reports, "read_report", failing)
    register_and_login(client)
    page = upload(client)
    assert b"doesn&#39;t look like a lab report" in page.data


def test_cannot_upload_to_someone_elses_profile(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client, "asha")
    client.get("/logout")
    register_and_login(client, "ravi")  # ravi's own profile is id 2
    response = client.post(
        "/reports/upload",
        data={"profile_id": "1", "language": "English", "report": (io.BytesIO(PDF_BYTES), "r.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 404


def test_cannot_view_someone_elses_report(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client, "asha")
    upload_and_save(client)
    client.get("/logout")
    register_and_login(client, "ravi")
    assert client.get("/reports/1").status_code == 404


def test_ask_question_about_report(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    monkeypatch.setattr(reports, "ask_about_report",
                        lambda question, report, results, language: "Eat iron-rich foods like spinach.")
    register_and_login(client)
    upload_and_save(client)
    page = client.post("/reports/1/ask", data={"question": "What should I eat?"}, follow_redirects=True)
    assert b"What should I eat?" in page.data
    assert b"iron-rich foods" in page.data


def test_delete_report(client, monkeypatch):
    monkeypatch.setattr(reports, "read_report", fake_read_report)
    register_and_login(client)
    upload_and_save(client)
    client.post("/reports/1/delete")
    assert client.get("/reports/1").status_code == 404


# ---------- Sample data, trends and comparisons ----------

def test_sample_data_shows_trends_and_urgent_results(client):
    register_and_login(client)
    page = client.post("/dashboard/sample-data", follow_redirects=True)
    assert b"Sample family and reports loaded" in page.data
    assert b"Sunita" in page.data and b"Rajesh" in page.data
    assert b"needs attention" in page.data  # father's very high potassium

    mother = client.get("/profiles/2")
    assert b"trend-1" in mother.data       # trend charts are drawn
    assert b"HbA1c" in mother.data

    father_latest = client.get("/reports/6")
    assert b"URGENT" in father_latest.data
    assert b"was 1.1 on 2025-06-18" in father_latest.data  # creatinine compared with last report


def test_deleting_profile_deletes_their_reports(client):
    register_and_login(client)
    client.post("/dashboard/sample-data")
    client.post("/profiles/2/delete")
    assert client.get("/reports/2").status_code == 404


# ---------- Logic without the web layer ----------

@pytest.mark.parametrize("text, expected", [
    ("13.5", 13.5), ("1,50,000", 150000.0), ("< 200", 200.0), ("Negative", None), ("", None), ("1+", None),
])
def test_parse_number(text, expected):
    assert parse_number(text) == expected


def test_decide_status():
    assert decide_status(10.5, 12, 15, "normal") == "low"
    assert decide_status(16, 12, 15, "normal") == "high"
    assert decide_status(13, 12, 15, "high") == "normal"
    assert decide_status(250, None, 200, "unknown") == "high"   # range "< 200"
    assert decide_status(None, None, None, "abnormal") == "abnormal"
    assert decide_status(None, None, None, "something odd") == "unknown"


def test_clean_report_fixes_bad_date():
    reply = fake_ai_reply()
    reply["report_date"] = "12/10/2026"
    assert ai.clean_report(reply)["report_date"] == date.today().isoformat()


def test_detect_file_type():
    assert detect_file_type(PDF_BYTES) == "application/pdf"
    assert detect_file_type(PNG_BYTES) == "image/png"
    assert detect_file_type(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert detect_file_type(b"RIFF1234WEBPVP8 ") == "image/webp"
    assert detect_file_type(b"hello") is None


def test_missing_api_key_gives_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ai.AIError, match="No API key"):
        ai.read_report(PDF_BYTES, "application/pdf", "English", "Female, age 30")


# ---------- Model fallback and retries (fake Gemini client, no internet needed) ----------

def fake_gemini(monkeypatch, script):
    """Replace genai.Client with a fake that replays `script`: one entry per call,
    either an HTTP error code (int) or the string "ok". Returns the list of models called."""
    from types import SimpleNamespace
    from google.genai import errors, types
    calls = []

    def generate_content(model, contents, config):
        calls.append(model)
        step = script.pop(0)
        if step == "ok":
            return SimpleNamespace(prompt_feedback=None, text="fine",
                                   candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)])
        raise errors.APIError(step, {"error": {"code": step, "message": f"error {step}"}})

    monkeypatch.setattr(ai.genai, "Client",
                        lambda api_key, **options: SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    monkeypatch.setattr(ai.time, "sleep", lambda seconds: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return calls


def test_busy_model_is_retried_once(monkeypatch):
    calls = fake_gemini(monkeypatch, [503, "ok"])
    assert ai.ask_ai("system", "hello") == "fine"
    assert calls == [ai.MODELS[0], ai.MODELS[0]]


def test_missing_model_falls_back_to_next(monkeypatch):
    calls = fake_gemini(monkeypatch, [404, "ok"])
    assert ai.ask_ai("system", "hello") == "fine"
    assert calls == ai.MODELS[:2]


def test_all_models_busy_gives_clear_message(monkeypatch):
    fake_gemini(monkeypatch, [503] * (2 * len(ai.MODELS)))
    with pytest.raises(ai.AIError, match="very busy"):
        ai.ask_ai("system", "hello")


def test_all_models_over_limit(monkeypatch):
    fake_gemini(monkeypatch, [429] * len(ai.MODELS))
    with pytest.raises(ai.AIError, match="limit reached"):
        ai.ask_ai("system", "hello")


def test_bad_file_message_only_for_400(monkeypatch):
    fake_gemini(monkeypatch, [400])
    with pytest.raises(ai.AIError, match="couldn't open this file"):
        ai.ask_ai("system", "hello")


def test_non_report_file_is_refused(monkeypatch):
    monkeypatch.setattr(ai, "ask_ai", lambda *a, **k: {**fake_ai_reply(), "is_lab_report": False})
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with pytest.raises(ai.AIError, match="doesn't look like a lab report"):
        ai.read_report(PDF_BYTES, "application/pdf", "English", "Female, age 30")
