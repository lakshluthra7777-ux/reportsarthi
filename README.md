# ReportSaathi: AI Lab-Report Explainer

**Problem:** Millions of people in India get blood tests every year but can't read the
reports: dozens of values, medical terms and reference ranges, and little time with a
doctor to ask questions. Families often manage reports for elderly parents, on paper or
WhatsApp, with no easy way to see whether sugar or cholesterol is getting better or worse.

**Solution:** ReportSaathi reads a lab report (a PDF or just a phone photo) with AI,
extracts every test value, flags what's outside the normal range, explains it in simple
English, Hindi or Hinglish, suggests questions to ask the doctor, and tracks each family
member's results over time with charts.

> Final Year Project, B.Tech

## Features

| Feature | How it works |
|---|---|
| Read any report | PDF, scanned PDF or phone photo sent to Google's Gemini API, which reads documents and images directly (multimodal) |
| Structured extraction | A **JSON Schema** forces the AI to return every test as name, value, unit and reference range |
| Reliable flags | Our code (`ranges.py`), not the AI, decides low/normal/high for every numeric value |
| Check before saving | **Human-in-the-loop review screen**: the user compares the AI's values with the paper report, fixes or removes rows (status updates live), then saves |
| Fix a value later | Any saved report can be corrected; corrected values are marked ✏️ |
| AI accuracy | Each report shows how many values the user had to correct, e.g. "AI accuracy 95% · 1 of 20 corrected" |
| Download as PDF | A clean A4 PDF (patient details, summary, colour-coded results table with previous values, doctor questions) built in the browser with html2pdf.js, so Hindi text works; also available from a doctor's share link |
| Share with doctor | A secret link + **QR code** opens a read-only, printable copy of one report without login; it expires (24 h / 3 days / 7 days), can be turned off, and counts views |
| Plain-language explanations | Summary, per-test explanation and doctor questions in **English, Hindi or Hinglish** |
| Urgent alerts | Values far outside the range get an URGENT badge and a red banner |
| Account settings | Edit any family member's details; change password (needs the current one); delete the account and all its data |
| Family profiles | One account manages Self, Mother, Father...; age and sex are sent to the AI for context |
| Trend charts | Tests are given standard names (e.g. "Hb" becomes "Haemoglobin") so the same test can be compared across reports; Chart.js draws them with the normal range |
| Compare with last report | Each value shows "was X on date" from the previous report |
| Ask about a report | Questions answered using only that report's results |
| Privacy by design | The uploaded file is never stored; only the extracted values are kept |
| Security | Password hashing, parameterised SQL, per-user access checks, file-type check by magic bytes, upload size limits, HttpOnly cookies |
| Demo mode | "Load sample data" adds a family with 6 reports, no API key needed |
| Testing | 66 automated pytest tests; the AI is replaced with fakes |

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask (Blueprints) |
| Database | SQLite (built-in `sqlite3`, plain SQL), 5 tables |
| AI | Gemini API (`google-genai` library, free tier): PDF and image input, structured JSON outputs |
| Frontend | HTML, CSS (no framework), Jinja2, vanilla JavaScript, Chart.js |
| Testing | pytest |

## Folder structure

```
reportsaathi/
├── app.py              # Creates the Flask app, registers blueprints, error pages
├── database.py         # SQLite connection, creates tables
├── schema.sql          # users, profiles, reports, results, questions
├── ai.py               # Gemini API: read_report() and ask_about_report()
├── ranges.py           # parse_number() and decide_status(): low / normal / high
├── helpers.py          # login_required, ownership checks, save_report()
├── sample_data.py      # Demo family and reports
├── routes/
│   ├── auth.py             # register, login, logout
│   ├── dashboard.py        # family overview, load sample data
│   ├── profiles.py         # add family member, report history, trends
│   └── reports.py          # upload, results page, ask a question, delete
├── templates/          # Jinja2 pages (all extend base.html)
├── static/             # style.css (base design), app.css (results, charts)
├── tests/test_app.py   # 66 tests
└── docs/VIVA_PREP.md   # Architecture, design decisions, report outline, viva Q&A
```

## Setup (Windows)

Requirements: Python 3.10 or newer, and a free Gemini API key from
https://aistudio.google.com (needed only to read new reports).

1. Open a terminal in the `reportsaathi` folder.
2. Create and activate a virtual environment, then install the libraries:

   ```
   py -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env`. Put your Gemini API key in `GEMINI_API_KEY`
   and any long random text in `SECRET_KEY`.
4. Run the app:

   ```
   python app.py
   ```

5. Open http://127.0.0.1:5000, register, then either upload a report or click
   **Load sample data**.

### Scanning share QR codes from a phone

Share links normally point to `127.0.0.1`, which only works on the same computer. To open
them from a phone on the same Wi-Fi:

1. Run `ipconfig` and note your PC's **IPv4 Address** (e.g. `192.168.1.5`).
2. Add to `.env`: `HOST=0.0.0.0` and `PUBLIC_URL=http://192.168.1.5:5000`.
3. Restart the app and allow Python through Windows Firewall if asked (private networks only).

Debug mode switches off automatically when `HOST` isn't `127.0.0.1`, because the debugger
would let anyone on the network run code. Use this only on a trusted home network.

## Running the tests

```
python -m pytest
```

## Limitations and future scope

- AI can misread a blurry photo. The original report should always be checked, and
  a future version could let users correct a value before saving.
- Not a medical device: it explains results, it does not diagnose.
- On Gemini's free tier, Google may use submitted content to improve its products. Demo
  with sample data or reports with names covered; a real deployment would use a paid
  tier with a data-processing agreement.
- No CSRF tokens yet (Flask-WTF would add them); HTTPS is needed when deployed.
- Future: encrypt health data at rest, share a report with a doctor through a link,
  WhatsApp upload, medicine and appointment reminders, more Indian languages,
  PostgreSQL and cloud deployment.

## Deploying on Render

The repository includes `render.yaml`, so Render can create the service automatically:

1. On https://render.com, sign in with GitHub and choose **New → Blueprint**.
2. Pick this repository. Render reads `render.yaml` (Gunicorn, Python 3.12, free plan) and generates `SECRET_KEY`.
3. When asked, paste your `GEMINI_API_KEY`. Click **Apply**.
4. The app is served at `https://<service-name>.onrender.com`. Every push to `main` redeploys it.

Note: on Render's free plan the disk is temporary, so the SQLite database is reset on every restart or redeploy,
and the service sleeps after 15 minutes without visitors (the first request then takes about a minute).
Use **Load sample family** on the dashboard for demos.
