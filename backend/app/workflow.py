from .models import Requirement

def scholarship_requirements():
    data=[
      ("full_name","Full name",False),("date_of_birth","Date of birth",False),("student_status","Student status",True),
      ("college_name","College name",True),("course_name","Course name",False),("year_of_study","Year of study",False),
      ("annual_household_income","Annual household income",True),("state_of_domicile","State of domicile",True),
      ("category","Category",False),("bank_account_holder_name","Bank account holder name",False),
      ("income_certificate","Income certificate",True),("student_certificate","Student certificate",True),("domicile_certificate","Domicile certificate",True)]
    evidence={"student_status":["student_certificate"],"college_name":["student_certificate"],"annual_household_income":["income_certificate"],"state_of_domicile":["domicile_certificate"],"income_certificate":["income_certificate"],"student_certificate":["student_certificate"],"domicile_certificate":["domicile_certificate"]}
    return [Requirement(id=f"req-{i+1}",concept=c,label=l,description=f"Scholarship requires {l.lower()}.",proof_required=p,accepted_evidence_types=evidence.get(c,[]),validation_rule="positive_number" if c=="annual_household_income" else None,order=i+1) for i,(c,l,p) in enumerate(data)]
