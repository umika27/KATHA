from app.models import *
from app.workflow import scholarship_requirements
from app.core import resolve,resolve_all,questions,preflight
from app.concepts import canonical_concept
from app.fixtures import fixture

reqs=scholarship_requirements()
def req(c): return next(r for r in reqs if r.concept==c)
def fact(c,v,status=Status.STATED,precision=Precision.exact,source="user",source_id=None): return Fact(id=f"f-{c}-{v}",concept=c,value=v,normalized_value=v,status=status,precision=precision,source_type=source,source_id=source_id)
def test_missing(): assert resolve(req("full_name"),Session(id="x")).status==Status.MISSING
def test_stated_proof(): assert resolve(req("annual_household_income"),Session(id="x",facts=[fact("annual_household_income",400000)])).status==Status.STATED
def test_verified():
 s=Session(id="x",facts=[fact("annual_household_income",382400,Status.VERIFIED,source="document",source_id="e")],evidence=[Evidence(id="e",type="income_certificate",filename="x",source="fixture")])
 assert resolve(req("annual_household_income"),s).status==Status.VERIFIED
def test_conflict():
 s=Session(id="x",facts=[fact("annual_household_income",500000),fact("annual_household_income",382400,Status.VERIFIED,source="document",source_id="e")],evidence=[Evidence(id="e",type="income_certificate",filename="x",source="fixture")])
 assert resolve(req("annual_household_income"),s).status==Status.CONFLICT
def test_approximate_compatible():
 s=Session(id="x",facts=[fact("annual_household_income",400000,precision=Precision.approximate),fact("annual_household_income",382400,Status.VERIFIED,source="document",source_id="e")],evidence=[Evidence(id="e",type="income_certificate",filename="x",source="fixture")])
 assert resolve(req("annual_household_income"),s).status==Status.VERIFIED
def test_question_order():
 rs=resolve_all(reqs,Session(id="x",facts=[fact("annual_household_income",400000,precision=Precision.approximate)])); qs=questions(reqs,rs)
 assert qs[0].priority==1 and next(q for q in qs if q.concept=="annual_household_income").priority==3
def test_preflight_missing_proof(): assert preflight(reqs,resolve_all(reqs,fixture("missing-proof","x")))["status"]=="NOT_READY"
def test_preflight_ready(): assert preflight(reqs,resolve_all(reqs,fixture("ready","x")))["status"]=="READY"
def test_alias(): assert canonical_concept("Gross Parental Income p.a.")=="annual_household_income"
