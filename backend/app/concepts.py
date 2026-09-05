REGISTRY = {
 "full_name":["Full Name","Applicant Name"], "date_of_birth":["Date of Birth","DOB"],
 "college_name":["College","Institution Name","University","Educational Institution"],
 "course_name":["Course","Programme"], "year_of_study":["Year of Study","Academic Year"],
 "student_status":["Student Status","Enrollment Status"],
 "household_income":["Household Income Observation","Family Income Observation"],
 "annual_household_income":["Annual Family Income","Gross Household Income","Gross Parental Income p.a.","Aggregate Annual Household Earnings","Family Income","Household Income"],
 "state_of_domicile":["Domicile State","Permanent State","State of Permanent Residence","Permanent Domicile"],
 "category":["Category","Social Category"], "bank_account_holder_name":["Bank Account Holder Name","Account Holder"],
 "income_certificate":["Income Certificate"], "student_certificate":["Student Certificate","Bonafide Certificate"], "domicile_certificate":["Domicile Certificate"]}
ALIASES={a.casefold(): c for c, aliases in REGISTRY.items() for a in [c,*aliases]}
def canonical_concept(label: str): return ALIASES.get(label.strip().casefold())
LANGUAGES={"hi-en":"Hindi / Hinglish","te-en":"Telugu + English","bn-en":"Bengali + English"}

QUESTION_TEXTS = {
    "hi-en": {
        "full_name": "Aapka poora naam kya hai?",
        "date_of_birth": "Aapki date of birth kya hai?",
        "college_name": "Aap kis college ya university mein padhte hain?",
        "course_name": "Aap kaunsa course kar rahe hain?",
        "year_of_study": "Aap college ke kaunse year mein hain?",
        "annual_household_income": "Aapke parivar ki exact annual income kitni hai?",
        "state_of_domicile": "Aapka permanent domicile state kaunsa hai?",
        "category": "Aapki category kya hai?",
        "bank_account_holder_name": "Bank account holder ka naam kya hai?",
        "income_certificate": "Kripya apna income certificate provide karein.",
        "student_certificate": "Kripya apna student certificate provide karein.",
        "domicile_certificate": "Kripya apna domicile certificate provide karein.",
    },
    "te-en": {
        "full_name": "Mee full name enti?",
        "date_of_birth": "Mee date of birth eppudu?",
        "college_name": "Meeru ye college lo chaduvutunnaru?",
        "course_name": "Meeru ye course chestunnaru?",
        "year_of_study": "Meeru college lo ye year lo unnaru?",
        "annual_household_income": "Mee family exact annual income entha?",
        "state_of_domicile": "Mee permanent domicile state edi?",
        "category": "Mee category enti?",
        "bank_account_holder_name": "Bank account holder name enti?",
        "income_certificate": "Dayachesi income certificate provide cheyandi.",
        "student_certificate": "Dayachesi student certificate provide cheyandi.",
        "domicile_certificate": "Dayachesi domicile certificate provide cheyandi.",
    },
    "bn-en": {
        "full_name": "Apanar full name ki?",
        "date_of_birth": "Apanar date of birth kobe?",
        "college_name": "Apni kon college-e porchen?",
        "course_name": "Apni kon course korchen?",
        "year_of_study": "Apni college-er kon year-e porchen?",
        "annual_household_income": "Apanar family-r exact annual income koto?",
        "state_of_domicile": "Apanar permanent domicile state konta?",
        "category": "Apanar category ki?",
        "bank_account_holder_name": "Bank account holder-er naam ki?",
        "income_certificate": "Doya kore income certificate provide korun.",
        "student_certificate": "Doya kore student certificate provide korun.",
        "domicile_certificate": "Doya kore domicile certificate provide korun.",
    },
}
