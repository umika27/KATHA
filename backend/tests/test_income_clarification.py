import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import Status
from app.semantic import ExtractedFact,SemanticExtraction,SemanticOutcome


client=TestClient(main.app)


def outcome(amount,period,approximate=False,concept=None):
 concept=concept or ("annual_household_income" if period=="annual" else "household_income")
 candidate=ExtractedFact(concept=concept,value=amount,normalized_value=amount,unit="INR",period=period,approximate=approximate,confidence=.98,source_span="family income statement",explicit=True)
 extraction=SemanticExtraction(facts=[candidate],uncertainties=[],unmapped_information=[],clarification_needed=period=="unknown",clarification_reason="income period" if period=="unknown" else None,language_detected="hi-en")
 return SemanticOutcome(extraction=extraction,provider="sarvam-105b",candidate_fact_count=1)


def application():return client.post("/api/applications").json()["application_id"]


@pytest.mark.parametrize("text,amount",[
 ("Meri ghar ki income 8000 hai",8000),
 ("Hamare ghar ki income around 10 hazaar hai",10000),
 ("Mummy papa mila ke 20,000 kamate hain",20000),
 ("Our family income is 15000",15000),
 ("My parents earn about 25k",25000),
 ("Ami family income 10000",10000),
 ("Family income 12000 undi",12000),
 ("family income is ₹4 lakh",400000),
])
def test_unqualified_income_is_preserved_and_requests_period_without_annualizing(monkeypatch,text,amount):
 app_id=application();monkeypatch.setattr(main.semantic_pipeline.provider,"extract_semantic_facts",lambda *_:outcome(amount,"unknown","around" in text or "about" in text))
 monkeypatch.setattr(main.provider,"generate_response",lambda *_:"Understood.")
 body=client.post("/api/interactions/text",json={"application_id":app_id,"language_mode":"hi-en","text":text}).json()
 observation=next(f for f in body["applied_facts"] if f["concept"]=="household_income")
 assert observation["normalized_value"]==amount and observation["period"]=="unknown" and observation["status"]=="UNCERTAIN"
 assert not any(f["concept"]=="annual_household_income" for f in body["applied_facts"])
 question=body["application"]["questions"][0]
 assert question["type"]=="clarification" and question["missing_qualifier"]=="period" and question["fact_id"]==observation["id"]
 assert sum(q["resolves_requirement_ids"]==["req-7"] for q in body["application"]["questions"])==1


@pytest.mark.parametrize("text,amount,period,annual",[
 ("Meri ghar ki income 8000 per month hai",8000,"monthly",96000),
 ("Our family earns ₹20,000 every month",20000,"monthly",240000),
 ("Parents together earn 30k monthly",30000,"monthly",360000),
 ("Meri ghar ki annual income 8000 hai",8000,"annual",8000),
])
def test_explicit_income_period_maps_or_derives_without_clarification(monkeypatch,text,amount,period,annual):
 app_id=application();monkeypatch.setattr(main.semantic_pipeline.provider,"extract_semantic_facts",lambda *_:outcome(amount,period))
 monkeypatch.setattr(main.provider,"generate_response",lambda *_:"Understood.")
 body=client.post("/api/interactions/text",json={"application_id":app_id,"language_mode":"hi-en","text":text}).json()
 annual_fact=next(f for f in body["applied_facts"] if f["concept"]=="annual_household_income")
 assert annual_fact["normalized_value"]==annual and annual_fact["period"]=="annual"
 if period=="monthly":
  observation=next(f for f in body["applied_facts"] if f["concept"]=="household_income")
  assert annual_fact["status"]=="DERIVED" and annual_fact["derived_from_fact_ids"]==[observation["id"]] and annual_fact["derivation"]==f"{amount} × 12"
 else:assert annual_fact["status"]=="STATED"
 assert not any(q["type"]=="clarification" for q in body["application"]["questions"])


def test_unknown_period_can_be_clarified_monthly_with_persistent_provenance(monkeypatch):
 app_id=application();monkeypatch.setattr(main.semantic_pipeline.provider,"extract_semantic_facts",lambda *_:outcome(8000,"unknown"))
 first=client.post("/api/interactions/text",json={"application_id":app_id,"language_mode":"hi-en","text":"Meri ghar ki income 8000 hai"}).json()
 observation=next(f for f in first["applied_facts"] if f["concept"]=="household_income")
 resolved=client.post("/api/clarifications/income-period",json={"application_id":app_id,"fact_id":observation["id"],"period":"monthly"}).json()
 original=next(f for f in resolved["facts"] if f["id"]==observation["id"]);annual=next(f for f in resolved["facts"] if f["concept"]=="annual_household_income")
 assert original["period"]=="monthly" and original["status"]=="STATED"
 assert annual["normalized_value"]==96000 and annual["status"]==Status.DERIVED and annual["source_type"]=="derived"
 assert annual["derived_from_fact_ids"]==[original["id"]] and annual["derivation"]=="8000 × 12"
 assert not any(q["type"]=="clarification" for q in resolved["questions"])
 assert client.get(f"/api/applications/{app_id}").json()["facts"]==resolved["facts"]


def test_approximate_explicit_annual_income_remains_uncertain(monkeypatch):
 app_id=application();monkeypatch.setattr(main.semantic_pipeline.provider,"extract_semantic_facts",lambda *_:outcome(400000,"annual",True))
 body=client.post("/api/interactions/text",json={"application_id":app_id,"language_mode":"hi-en","text":"Our annual household income is about ₹4 lakh"}).json()
 fact=body["applied_facts"][0]
 assert fact["concept"]=="annual_household_income" and fact["normalized_value"]==400000 and fact["status"]=="UNCERTAIN"


def test_schema_guard_downgrades_provider_annual_concept_when_period_unknown(monkeypatch):
 app_id=application();monkeypatch.setattr(main.semantic_pipeline.provider,"extract_semantic_facts",lambda *_:outcome(8000,"unknown",concept="annual_household_income"))
 body=client.post("/api/interactions/text",json={"application_id":app_id,"language_mode":"hi-en","text":"Meri ghar ki income 8000 hai"}).json()
 assert [f["concept"] for f in body["applied_facts"]]==["household_income"]
