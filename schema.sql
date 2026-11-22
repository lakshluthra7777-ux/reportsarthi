-- ReportSaathi database schema (SQLite).
-- "IF NOT EXISTS" means running this file again will not delete existing data.
-- Child rows use ON DELETE CASCADE: deleting a profile deletes its reports and results.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- A family member whose reports are tracked (one account can manage Me, Mother, Father...).
CREATE TABLE IF NOT EXISTS profiles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    name       TEXT    NOT NULL,
    relation   TEXT    NOT NULL,              -- e.g. Self, Mother, Father
    birth_year INTEGER,
    sex        TEXT    CHECK (sex IN ('Male', 'Female', 'Other')),
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- One uploaded lab report. The file itself is NOT stored (privacy): only what was read from it.
CREATE TABLE IF NOT EXISTS reports (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id       INTEGER NOT NULL,
    file_name        TEXT    NOT NULL,
    lab_name         TEXT    NOT NULL,
    report_date      TEXT    NOT NULL,         -- YYYY-MM-DD
    language         TEXT    NOT NULL,         -- language of the explanation
    summary          TEXT    NOT NULL,
    doctor_questions TEXT    NOT NULL,         -- JSON list of strings
    created_at       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

-- One test value from a report, e.g. Haemoglobin 11.2 g/dL (13.0 - 17.0).
CREATE TABLE IF NOT EXISTS results (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id      INTEGER NOT NULL,
    name           TEXT    NOT NULL,           -- name as printed on the report
    canonical_name TEXT    NOT NULL,           -- standard name, used to match tests across reports
    category       TEXT    NOT NULL,           -- e.g. Blood Count, Diabetes, Lipid Profile
    value_text     TEXT    NOT NULL,           -- value exactly as printed, e.g. "11.2" or "Negative"
    value_num      REAL,                       -- number for charts, NULL if not a number
    unit           TEXT    NOT NULL,
    ref_low        REAL,
    ref_high       REAL,
    ref_text       TEXT    NOT NULL,           -- reference range as printed
    status         TEXT    NOT NULL CHECK (status IN ('low', 'normal', 'high', 'abnormal', 'unknown')),
    critical       INTEGER NOT NULL DEFAULT 0, -- 1 if far outside the range: see a doctor soon
    explanation    TEXT    NOT NULL,
    corrected      INTEGER NOT NULL DEFAULT 0, -- 1 if the user fixed what the AI read
    FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE
);

-- What the AI read from an upload, waiting for the user to check it on the review screen.
-- It becomes a real report (and is deleted from here) when the user clicks Save.
CREATE TABLE IF NOT EXISTS pending_reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    file_name  TEXT    NOT NULL,
    language   TEXT    NOT NULL,
    data       TEXT    NOT NULL,             -- JSON from ai.read_report()
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

-- Questions asked about a report, and the AI's answers.
CREATE TABLE IF NOT EXISTS questions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id  INTEGER NOT NULL,
    question   TEXT    NOT NULL,
    answer     TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE
);

-- Secret links that let a doctor view one report without logging in.
-- The token is long and random, so it can't be guessed; the link stops working
-- when it expires or when the patient revokes it.
CREATE TABLE IF NOT EXISTS share_links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id  INTEGER NOT NULL,
    token      TEXT    NOT NULL UNIQUE,
    expires_at TEXT    NOT NULL,           -- UTC, 'YYYY-MM-DD HH:MM:SS'
    revoked    INTEGER NOT NULL DEFAULT 0,
    views      INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_results_trend ON results (canonical_name);
CREATE INDEX IF NOT EXISTS idx_reports_profile ON reports (profile_id, report_date);
