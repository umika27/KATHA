from uuid import uuid4
from .models import *

BASE={"full_name":"Aanya Sharma","date_of_birth":"2005-04-12","college_name":"VIT Vellore","course_name":"B.Tech","year_of_study":2,"student_status":"active","annual_household_income":382400,"state_of_domicile":"Haryana","category":"General","bank_account_holder_name":"Aanya Sharma"}
DOCS={"income_certificate":{"annual_household_income":382400},"student_certificate":{"student_status":"active","college_name":"VIT Vellore"},"domicile_certificate":{"state_of_domicile":"Haryana"}}
def fixture(name,id):
 s=Session(id=id)
 values={} if name=="initial" else dict(BASE)
 if name=="partial": values={k:BASE[k] for k in list(BASE)[:7]}
 for c,v in values.items(): s.facts.append(Fact(id=str(uuid4()),concept=c,value=v,normalized_value=v,status=Status.STATED,source_type="user"))
 doc_types=[]
 if name in ("missing-proof","ready","conflict"): doc_types=["student_certificate","domicile_certificate"] + (["income_certificate"] if name in ("ready","conflict") else [])
 for typ in doc_types:
  eid=str(uuid4()); fact_ids=[]
  for c,v in DOCS[typ].items():
   f=Fact(id=str(uuid4()),concept=c,value=v,normalized_value=v,status=Status.VERIFIED,source_type="document",source_id=eid); s.facts.append(f); fact_ids.append(f.id)
  s.facts.append(Fact(id=str(uuid4()),concept=typ,value=True,normalized_value=True,status=Status.VERIFIED,source_type="document",source_id=eid))
  s.evidence.append(Evidence(id=eid,type=typ,filename=f"fictional_{typ}.txt",source="demo_fixture",extracted_facts=fact_ids))
 if name=="conflict": s.facts.append(Fact(id=str(uuid4()),concept="annual_household_income",value=500000,normalized_value=500000,status=Status.STATED,source_type="user"))
 return s
