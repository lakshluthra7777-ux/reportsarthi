# Sample family and reports, so the app can be demonstrated without an API key.
# Used by the "Load sample data" button on the dashboard (routes/dashboard.py).
# The values are made up but realistic; nothing here comes from a real patient.

from helpers import save_report
from ranges import decide_status


def test(name, category, value, unit, low, high, explanation, canonical=None, critical=False):
    """Build one result in the same shape that ai.clean_report() produces."""
    if low is None:
        ref_text = f"< {high}"
    elif high is None:
        ref_text = f"> {low}"
    else:
        ref_text = f"{low} - {high}"
    return {
        "name": name,
        "canonical_name": canonical or name,
        "category": category,
        "value_text": str(value),
        "value_num": float(value),
        "unit": unit,
        "ref_low": low,
        "ref_high": high,
        "ref_text": ref_text,
        "status": decide_status(float(value), low, high, "unknown"),
        "critical": critical,
        "explanation": explanation,
    }


HB = "Haemoglobin carries oxygen from your lungs to the rest of your body."
FBS = "Blood sugar after not eating for 8-10 hours. High values can point to diabetes."
HBA1C = "Your average blood sugar over the last 3 months. 5.7-6.4% is pre-diabetes; 6.5% or more suggests diabetes."
TSH = "A hormone that controls the thyroid gland. High TSH can mean an underactive thyroid."
CHOL = "Total fat-like substance in your blood. High levels raise the risk of heart disease."
LDL = "The 'bad' cholesterol that can build up in blood vessels."
HDL = "The 'good' cholesterol that helps remove other cholesterol. Higher is better."
TG = "A type of fat in the blood, often raised by sugar, refined carbs and alcohol."
CREAT = "A waste product filtered by the kidneys. High levels can mean the kidneys are under strain."
VITD = "Vitamin D keeps bones strong. Low levels are very common in India despite the sunshine."
B12 = "Vitamin B12 is needed for nerves and red blood cells. Vegetarians are often low."
PLT = "Platelets help your blood clot."
WBC = "White blood cells fight infections."
K = "Potassium keeps the heart and muscles working properly. Very high levels can affect heart rhythm."

FAMILY = [
    {
        "profile": None,  # the user's own "Self" profile
        "reports": [
            ("2026-08-14", "City Diagnostics", "self_aug.pdf",
             "Most of your results are in the normal range. Your Vitamin D and Vitamin B12 are low, "
             "which is very common and can cause tiredness, body aches or tingling. Your blood count, "
             "sugar and thyroid are normal. Ask your doctor whether you need supplements and how long "
             "to take them.",
             ["Do I need Vitamin D and B12 supplements? For how long?",
              "Should I retest these vitamins after 3 months?",
              "Could low B12 explain my tiredness?"],
             [test("Haemoglobin", "Blood Count", 13.1, "g/dL", 12.0, 15.0, HB),
              test("WBC Count", "Blood Count", 7200, "/cumm", 4000, 11000, WBC),
              test("Platelet Count", "Blood Count", 245000, "/cumm", 150000, 410000, PLT),
              test("Fasting Blood Sugar", "Diabetes", 88, "mg/dL", 70, 100, FBS),
              test("TSH", "Thyroid", 2.4, "µIU/mL", 0.4, 4.5, TSH),
              test("25-OH Vitamin D", "Vitamins", 14.2, "ng/mL", 30, 100, VITD, canonical="Vitamin D (25-OH)"),
              test("Vitamin B12", "Vitamins", 168, "pg/mL", 211, 911, B12)]),
        ],
    },
    {
        "profile": ("Sunita", "Mother", 1968, "Female"),
        "reports": [
            ("2025-03-10", "Lal PathLabs", "mummy_mar25.pdf",
             "Your fasting sugar and HbA1c are slightly above normal, in the pre-diabetes range. "
             "Haemoglobin is a little low (mild anaemia). Thyroid and cholesterol are in range.",
             ["Am I pre-diabetic?", "What diet changes can help my sugar?", "Should I take iron tablets?"],
             [test("Hb", "Blood Count", 11.2, "g/dL", 12.0, 15.0, HB, canonical="Haemoglobin"),
              test("Glucose Fasting", "Diabetes", 108, "mg/dL", 70, 100, FBS, canonical="Fasting Blood Sugar"),
              test("HbA1c", "Diabetes", 6.1, "%", None, 5.7, HBA1C),
              test("TSH", "Thyroid", 3.9, "µIU/mL", 0.4, 4.5, TSH),
              test("Total Cholesterol", "Lipid Profile", 192, "mg/dL", None, 200, CHOL)]),
            ("2025-11-22", "Lal PathLabs", "mummy_nov25.pdf",
             "Your sugar has gone up since March: HbA1c is now 6.6%, which is in the diabetes range. "
             "Haemoglobin has improved slightly. TSH is now a little above normal. Please show this "
             "report to your doctor soon to discuss sugar control.",
             ["Is my HbA1c of 6.6% diabetes?", "Do I need medicine or only diet and exercise?",
              "Should my thyroid be checked again?"],
             [test("Hb", "Blood Count", 11.8, "g/dL", 12.0, 15.0, HB, canonical="Haemoglobin"),
              test("Glucose Fasting", "Diabetes", 122, "mg/dL", 70, 100, FBS, canonical="Fasting Blood Sugar"),
              test("HbA1c", "Diabetes", 6.6, "%", None, 5.7, HBA1C),
              test("TSH", "Thyroid", 4.8, "µIU/mL", 0.4, 4.5, TSH),
              test("Total Cholesterol", "Lipid Profile", 205, "mg/dL", None, 200, CHOL)]),
            ("2026-09-05", "Metropolis", "mummy_sep26.jpg",
             "Your HbA1c has risen further to 7.2%, so blood sugar is not yet under control. "
             "Haemoglobin is now normal, which is good news. TSH is high, which may mean an "
             "underactive thyroid. Cholesterol and LDL are above the target range. Please discuss "
             "your sugar, thyroid and cholesterol with your doctor.",
             ["My HbA1c keeps rising. Should my treatment change?",
              "Is my high TSH related to my tiredness and weight gain?",
              "Do I need medicine for cholesterol?",
              "How often should I test my sugar at home?"],
             [test("Haemoglobin", "Blood Count", 12.4, "g/dL", 12.0, 15.0, HB),
              test("Fasting Plasma Glucose", "Diabetes", 138, "mg/dL", 70, 100, FBS, canonical="Fasting Blood Sugar"),
              test("Glycated Haemoglobin", "Diabetes", 7.2, "%", None, 5.7, HBA1C, canonical="HbA1c"),
              test("TSH (Ultrasensitive)", "Thyroid", 6.2, "µIU/mL", 0.4, 4.5, TSH, canonical="TSH"),
              test("Total Cholesterol", "Lipid Profile", 221, "mg/dL", None, 200, CHOL),
              test("LDL Cholesterol", "Lipid Profile", 142, "mg/dL", None, 100, LDL),
              test("HDL Cholesterol", "Lipid Profile", 46, "mg/dL", 40, None, HDL),
              test("Triglycerides", "Lipid Profile", 168, "mg/dL", None, 150, TG)]),
        ],
    },
    {
        "profile": ("Rajesh", "Father", 1965, "Male"),
        "reports": [
            ("2025-06-18", "SRL Diagnostics", "papa_jun25.pdf",
             "Your cholesterol, LDL and triglycerides are high, which increases heart risk. "
             "Kidney function (creatinine) is normal. Sugar is normal.",
             ["Do I need medicine for cholesterol?", "What foods should I avoid?",
              "How often should I repeat this test?"],
             [test("Total Cholesterol", "Lipid Profile", 238, "mg/dL", None, 200, CHOL),
              test("LDL Cholesterol", "Lipid Profile", 162, "mg/dL", None, 100, LDL),
              test("HDL Cholesterol", "Lipid Profile", 38, "mg/dL", 40, None, HDL),
              test("Triglycerides", "Lipid Profile", 210, "mg/dL", None, 150, TG),
              test("Serum Creatinine", "Kidney Function", 1.1, "mg/dL", 0.7, 1.3, CREAT, canonical="Creatinine"),
              test("Fasting Blood Sugar", "Diabetes", 96, "mg/dL", 70, 100, FBS),
              test("Potassium", "Electrolytes", 4.6, "mmol/L", 3.5, 5.1, K)]),
            ("2026-10-02", "SRL Diagnostics", "papa_oct26.pdf",
             "Good progress on cholesterol: total cholesterol and LDL have come down since last year. "
             "However, your potassium is very high and creatinine has gone up, which can affect the "
             "heart and kidneys. Please contact a doctor soon about the potassium result. "
             "Sugar is normal.",
             ["My potassium is 6.4. Do I need urgent treatment?",
              "Could any of my medicines be raising potassium?",
              "Is my kidney function getting worse?",
              "Should I keep taking my cholesterol medicine?"],
             [test("Total Cholesterol", "Lipid Profile", 198, "mg/dL", None, 200, CHOL),
              test("LDL Cholesterol", "Lipid Profile", 118, "mg/dL", None, 100, LDL),
              test("HDL Cholesterol", "Lipid Profile", 42, "mg/dL", 40, None, HDL),
              test("Triglycerides", "Lipid Profile", 160, "mg/dL", None, 150, TG),
              test("Serum Creatinine", "Kidney Function", 1.5, "mg/dL", 0.7, 1.3, CREAT, canonical="Creatinine"),
              test("Fasting Blood Sugar", "Diabetes", 99, "mg/dL", 70, 100, FBS),
              test("Potassium", "Electrolytes", 6.4, "mmol/L", 3.5, 5.1, K, critical=True)]),
        ],
    },
]


def load_sample_data(db, user_id):
    """Add the sample family members and their reports to one user's account."""
    self_profile = db.execute(
        "SELECT id FROM profiles WHERE user_id = ? AND relation = 'Self' ORDER BY id LIMIT 1", (user_id,)
    ).fetchone()
    if self_profile is None:
        self_id = db.execute(
            "INSERT INTO profiles (user_id, name, relation, sex) VALUES (?, 'Me', 'Self', 'Female')", (user_id,)
        ).lastrowid
    else:
        self_id = self_profile["id"]

    for member in FAMILY:
        if member["profile"] is None:
            profile_id = self_id
        else:
            name, relation, birth_year, sex = member["profile"]
            profile_id = db.execute(
                "INSERT INTO profiles (user_id, name, relation, birth_year, sex) VALUES (?, ?, ?, ?, ?)",
                (user_id, name, relation, birth_year, sex),
            ).lastrowid
        for report_date, lab, file_name, summary, questions, tests in member["reports"]:
            data = {"lab_name": lab, "report_date": report_date, "summary": summary,
                    "doctor_questions": questions, "tests": tests}
            save_report(db, profile_id, file_name, "English", data)  # each call commits
