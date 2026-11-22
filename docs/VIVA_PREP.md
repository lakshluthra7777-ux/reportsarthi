# ReportSaathi: Viva Preparation

## 1. Problem statement

Lab reports are written for doctors, not patients. A typical report has 20–60 values
with units and reference ranges. Patients, especially elderly people and people who
prefer Hindi, can't tell what matters, panic over small deviations, or miss serious
ones. Families keep reports on paper or in WhatsApp and can't see trends. ReportSaathi
turns a report (PDF or photo) into a clear, colour-coded explanation in the user's
language, with trends and doctor questions, while never claiming to diagnose.

## 2. Architecture

```
┌──────────────┐  HTTPS   ┌────────────────────────────────────────────────┐
│   Browser    │ ───────▶ │                Flask application               │
│ HTML/CSS/JS  │ ◀─────── │  app.py ─ registers Blueprints, error pages    │
│  Chart.js    │          │  routes/ auth · dashboard · profiles · reports │
└──────────────┘          │      │            │               │            │
                          │  helpers.py    ranges.py        ai.py          │
                          └──────┬─────────────────────────────┬───────────┘
                                 │ SQL                         │ HTTPS + API key
                                 ▼                             ▼
                        ┌──────────────────┐      ┌─────────────────────────┐
                        │ SQLite: users,   │      │ Gemini API (multimodal  │
                        │ profiles,        │      │ LLM): reads PDF/image,  │
                        │ reports, results,│      │ returns JSON that       │
                        │ questions        │      │ follows our schema      │
                        └──────────────────┘      └─────────────────────────┘
```

### Upload flow (the core pipeline)

1. **Validate:** the user picks a profile and language and uploads a file. The server checks
   that the profile belongs to them (else 404), reads the file's **magic bytes** to find its
   real type (PDF, JPEG, PNG or WEBP), and enforces size limits (20 MB total, 5 MB for photos).
2. **Extract (AI):** `ai.read_report()` base64-encodes the file as a `document` or `image`
   content block and sends it with a system prompt and **`REPORT_SCHEMA`**. The API returns
   JSON with every test's name, standard name, category, value, unit, range, flag,
   critical flag and explanation, plus a summary and doctor questions in the chosen language.
3. **Verify (our code):** `clean_report()` converts strings to numbers (`parse_number`),
   then `decide_status` compares value and range **in Python**, overriding the AI's flag
   when they disagree. Empty rows are dropped; an unreadable date becomes today's date.
4. **Store:** `save_report()` inserts the report and all results in **one transaction**.
   The file is thrown away (privacy by design).
5. **Present:** results are grouped by category, colour-coded, given a range bar and
   compared with the previous report. Trends use `canonical_name` across reports.

### ER diagram

```
USERS 1──N PROFILES 1──N REPORTS 1──N RESULTS
                            └──1──N QUESTIONS
```

| Table | Key columns |
|---|---|
| users | id, username UNIQUE, password_hash |
| profiles | id, user_id FK, name, relation, birth_year, sex (CHECK) |
| reports | id, profile_id FK, file_name, lab_name, report_date, language, summary, doctor_questions (JSON) |
| results | id, report_id FK, name, canonical_name, category, value_text, value_num, unit, ref_low, ref_high, ref_text, status (CHECK), critical, explanation |
| questions | id, report_id FK, question, answer |

`value_text` keeps the value exactly as printed ("Negative", "1,50,000"); `value_num` is
the parsed number for comparisons and charts. Indexes support trend lookups by test name
and report lists by profile and date.

## 3. Key design decisions (examiners love these)

1. **"The AI reads, our code decides."** LLMs are good at reading messy layouts and
   handwriting-like scans, but comparing 6.4 with 5.1 must be exact and repeatable. So the
   AI extracts the numbers and the range, and `ranges.decide_status()` makes the final
   low/normal/high decision. A test checks that a wrong AI flag is corrected.
2. **Structured outputs instead of parsing text.** A JSON Schema guarantees the shape of
   the reply, so every field maps straight onto a database column.
3. **Canonical names make trends possible.** Labs print "Hb", "Haemoglobin" or
   "Hemoglobin (Hb)". The prompt gives a list of standard names, so the same test is
   matched across different labs and years.
4. **Multimodal input instead of OCR.** Many Indian patients only have a phone photo.
   Gemini reads PDFs and images directly, so there is no separate OCR step
   (e.g. Tesseract) and no extra layout parsing.
5. **Context matters.** Age and sex are sent with the report, because normal ranges and
   explanations differ (e.g. haemoglobin for women vs men).
6. **Safety by design:** no diagnosis or medicine suggestions (in the prompts), a
   critical-value banner, a disclaimer on every report, "ask your doctor" questions,
   and the original value and range always shown next to the explanation.
7. **Privacy by design:** files aren't stored, every query is scoped to the logged-in
   user, and cookies are HttpOnly and SameSite.
8. **Prompt-injection defence:** the prompt tells the AI to treat text inside the
   document as data, never as instructions (a malicious PDF could contain
   "ignore your rules...").

## 4. Report outline

1. **Abstract** (200 words): the problem, the solution, the technologies, the results.
2. **Introduction:** health literacy in India; the growth of diagnostic testing; problem
   statement; objectives (extraction, explanation in local languages, trend tracking,
   safety); scope.
3. **Literature survey:**
   - Health literacy and patient understanding of lab results.
   - OCR-based extraction (Tesseract) and its limits on tables and photos.
   - Large language models and multimodal models (transformers, vision-language models).
   - Structured outputs and information extraction with LLMs.
   - Existing apps (lab apps from Indian diagnostic chains, health lockers such as ABHA/DigiLocker):
     they store PDFs but don't explain values or show trends across labs.
   - Gap: no simple tool that reads any lab's report, explains it in Hindi and tracks trends.
4. **Requirements and feasibility:** functional and non-functional requirements (privacy,
   accuracy, response time, mobile-friendly).
5. **System design:** architecture diagram, ER diagram, DFD levels 0 and 1, use cases
   (upload, view, ask, manage family), a sequence diagram of the upload pipeline.
6. **Implementation:** modules, the JSON Schema, prompt design, the status logic,
   trend queries, the UI (range bar, colour codes, charts).
7. **Testing:** the 34 automated tests (table: test, input, expected, result); manual
   testing with real reports from different labs, photos at different angles, Hindi output;
   accuracy table (values read correctly ÷ total values).
8. **Results:** screenshots; a sample report before and after; a trend chart; the Hindi explanation.
9. **Conclusion and future scope:** value correction by the user, encryption at rest,
   ABHA integration, doctor sharing, WhatsApp bot, more languages, cloud deployment.
10. **References** (IEEE format).

**Tip:** test with 5–10 real reports from family and friends (with their permission, and
with names blacked out) and record accuracy. Real numbers make the results chapter strong.

## 5. Viva questions with answers

### Problem and design

1. **What real-life problem does this solve?**
   People can't understand their lab reports, especially elderly people and Hindi speakers,
   and families can't track trends across labs and years. ReportSaathi explains each value
   in their language, flags what matters, and charts it over time.

2. **Why not just use ChatGPT or another AI chatbot?**
   A chatbot gives a one-off answer that isn't saved. My app extracts structured data,
   stores it per family member, computes flags in code, compares with past reports, draws
   trends, works with one click, and has safety rules built in.

3. **Explain your architecture.**
   Three tiers: browser → Flask (Blueprints per feature) → SQLite, with the Gemini API as an
   external service called only from the server. Business logic lives in separate modules
   (`ai.py`, `ranges.py`, `helpers.py`) so it can be unit-tested.

4. **Explain your database design.**
   Five tables in 3NF: users → profiles → reports → results, plus questions per report.
   One account manages many family members. Each result row stores both the printed value
   and a numeric value. `CHECK` constraints restrict `sex` and `status`, and foreign keys
   with `ON DELETE CASCADE` keep data consistent.

### AI

5. **How does the AI read a photo?**
   Gemini is a multimodal model: it accepts images and PDFs as input along with text.
   I base64-encode the file and send it as an `image` or `document` content block. The
   model reads the text and the table layout directly, so I don't need OCR.

6. **What are structured outputs?**
   I give the API a JSON Schema. The model's output is constrained to valid JSON of that
   exact shape, so `json.loads` always works and every field maps to a column.

7. **Why does your code decide low/high instead of the AI?**
   LLMs can make arithmetic or comparison mistakes. Comparing numbers is deterministic, so
   code does it exactly and repeatably. The AI does what it's good at: reading messy
   reports and explaining in plain language. One test feeds a wrong AI flag and checks
   that the code corrects it.

8. **What if the AI misreads a value?**
   The original printed value and range are shown next to every explanation, and the
   disclaimer asks users to check the original report. Future scope: let the user correct
   a value before saving (human-in-the-loop).

9. **What is prompt engineering in your project?**
   The system prompt defines the role (a helper, not a doctor), extraction rules (copy
   values exactly, how to read "< 200"), a list of standard test names, the language and
   script for explanations, safety rules (no diagnosis or medicines), and treating
   document text as data.

10. **What is prompt injection, and how do you handle it?**
    Text inside an input (like a PDF) trying to give the AI new instructions. The prompt
    says document text is data only; the output must follow my schema; and my code, not
    the AI, decides statuses and what is saved.

11. **How does multi-language support work?**
    The chosen language is passed into the prompt with rules about script: Devanagari for
    Hindi, Roman script for Hinglish. Test names and numbers stay as printed, so they still
    match the paper report.

12. **How do trends work across different labs?**
    The AI maps each printed name to a standard `canonical_name`. A SQL query collects each
    numeric test by canonical name across a profile's reports in date order; tests found in
    2 or more reports become Chart.js line charts with dashed normal-range lines.

13. **How do you control AI cost and time?**
    One AI call per report; results are stored and never regenerated; questions send only
    the extracted values, not the file again; and a lower effort setting is used for Q&A.

### Security and privacy

14. **Health data is sensitive. How do you protect it?**
    Files are never stored; passwords are hashed with a salt; passwords must be at least 8
    characters; every query checks ownership (404 otherwise); cookies are HttpOnly and
    SameSite; the API key stays on the server in `.env`. In production I'd add HTTPS,
    encryption at rest and CSRF tokens.

15. **Why check magic bytes instead of the file extension?**
    Extensions can be faked: `virus.exe` renamed to `report.pdf`. The first bytes of a file
    reveal its real type (`%PDF`, `FF D8 FF` for JPEG, `89 50 4E 47` for PNG).

16. **How do you stop one user from seeing another's reports?**
    `get_own_profile` and `get_own_report` join back to `user_id = g.user["id"]` and return
    404 when it doesn't match, even for uploads. Tests cover viewing and uploading to
    someone else's profile.

17. **What is XSS, and are you safe from it?**
    Injected scripts in pages. Jinja2 auto-escapes everything, including AI output, and
    chart data uses `|tojson`.

18. **What is SQL injection?**
    Malicious SQL inside user input. I use parameterised queries (`?` placeholders)
    everywhere, so input is always treated as data.

### Human-in-the-loop correction

- **What happens after upload?** The AI's result is stored in `pending_reports`, not saved as a
  report. The review screen shows every value in an editable table. The user compares with the
  paper report, fixes or removes rows, and clicks Save. Only then does `save_report()` run.
- **Why?** AI can misread a blurry photo. In healthcare a wrong number is dangerous, so a person
  confirms the data. This is called *human-in-the-loop*.
- **What happens when a value is changed?** `helpers.apply_correction()` re-parses the numbers
  and calls `decide_status()` again, so the flag is always right. The row gets `corrected = 1`.
  The JavaScript on the page uses the same rules to update the badge as the user types.
- **How do you measure AI accuracy?** Accuracy = (values read − values corrected) ÷ values read,
  shown on every report. Over 10–20 real reports this gives the accuracy table for the results chapter.
- **How did you add a column to an existing database?** `database.migrate()` checks
  `PRAGMA table_info(results)` and runs `ALTER TABLE ... ADD COLUMN corrected` if it's missing,
  a small schema migration, because `CREATE TABLE IF NOT EXISTS` never changes existing tables.

### Choice of AI

- **Why Gemini?** It has a free tier (good for a student project), reads PDFs and photos
  directly, and supports structured JSON output with a schema. All AI code is in `ai.py`,
  so switching provider changes one file only.
- **What if a model is overloaded?** `MODELS` is a list: on HTTP 503 (busy) or 429 (free
  limit reached) the request is retried on the next model, so the user rarely sees an error.
- **Privacy on the free tier:** Google may use free-tier content to improve its products,
  so demos use sample or anonymised reports. A real deployment needs a paid tier.

### Safety and ethics

19. **Is this a medical device? What about liability?**
    No. It explains results and does not diagnose or prescribe; the prompts forbid it, and
    every report shows a disclaimer. Critical values push the user to a doctor. This is an
    ethical design choice, and a real medical product would need regulatory approval.

20. **How do you handle critical values?**
    The AI marks values far outside the range as critical. They get an URGENT badge, a red
    banner telling the user to contact a doctor soon, and a "needs attention" badge on the
    family dashboard.

### Testing and implementation

21. **How did you test without spending money on the API?**
    pytest with Flask's test client, a fresh temporary database per test, and
    `monkeypatch` replacing the AI functions with fakes. 42 tests cover login, the review and correction flow, the database migration, access
    control, file validation, extraction cleaning, the status logic, sample data, trends,
    Q&A and deletion.

22. **What is a transaction, and where do you use one?**
    A group of statements that succeed or fail together. `save_report` inserts the report
    and all its results, then commits once, so a half-saved report can't exist.

23. **What is the Post/Redirect/Get pattern?**
    After a POST, redirect to a GET page, so refreshing doesn't resubmit the form. It's
    used for uploads, questions and deletes.

24. **What happens if the AI service is down?**
    `ask_ai` catches each error (bad key, rate limit, bad file, no connection, server
    error, refusal, cut-off output, invalid JSON) and raises `AIError` with a friendly
    message shown on the page. Saved reports and sample data keep working.

25. **What would you add with more time?**
    A screen to correct values before saving; encryption at rest; sharing with a doctor via
    a link that expires; an ABHA / DigiLocker integration; a WhatsApp bot for upload;
    reminders for retests; more Indian languages; deployment with HTTPS and PostgreSQL.
