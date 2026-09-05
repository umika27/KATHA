REGISTRY = {
 "full_name":["Full Name","Applicant Name"], "date_of_birth":["Date of Birth","DOB"],
 "college_name":["College","Institution Name","University","Educational Institution"],
 "course_name":["Course","Programme"], "year_of_study":["Year of Study","Academic Year"],
 "student_status":["Student Status","Enrollment Status"],
 "annual_household_income":["Annual Family Income","Gross Household Income","Gross Parental Income p.a.","Aggregate Annual Household Earnings","Family Income","Household Income"],
 "state_of_domicile":["Domicile State","Permanent State","State of Permanent Residence","Permanent Domicile"],
 "category":["Category","Social Category"], "bank_account_holder_name":["Bank Account Holder Name","Account Holder"],
 "income_certificate":["Income Certificate"], "student_certificate":["Student Certificate","Bonafide Certificate"], "domicile_certificate":["Domicile Certificate"]}
ALIASES={a.casefold(): c for c, aliases in REGISTRY.items() for a in [c,*aliases]}
def canonical_concept(label: str): return ALIASES.get(label.strip().casefold())
LANGUAGES={"hi-en":"Hindi / Hinglish","te-en":"Telugu + English","bn-en":"Bengali + English"}
