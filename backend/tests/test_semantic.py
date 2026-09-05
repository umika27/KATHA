import json
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.config import Settings
from app.models import Evidence,Fact,Precision,Session,Status
from app.semantic import SemanticExtraction
from app.semantic_pipeline import SemanticPipeline
from app.sarvam_service import SarvamService
from app.workflow import scholarship_requirements
from app.core import questions,resolve_all,preflight

def payload(facts,language="hi-en"):
 return json.dumps({"facts":facts,"uncertainties":[],"unmapped_information":[],"clarification_needed":False,"clarification_reason":None,"language_detected":language})
def extracted(concept,value,approximate=False,span="explicit words",period=None):
 return {"concept":concept,"value":value,"normalized_value":value,"unit":"INR" if concept in {"annual_household_income","household_income"} else None,"period":period or ("annual" if concept=="annual_household_income" else "unknown"),"approximate":approximate,"confidence":.93,"source_span":span,"explicit":True}
class Chat:
 def __init__(self,contents):self.contents=list(contents);self.calls=[]
 def completions(self,**kwargs):
  self.calls.append(kwargs);content=self.contents.pop(0)
  return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
class Client:
 def __init__(self,contents):self.chat=Chat(contents)
def configured():return Settings(sarvam_api_key="test",sarvam_enabled=True,sarvam_semantic_enabled=True)
def pipeline(contents):return SemanticPipeline(SarvamService(configured(),Client(contents)))
def run(p,text="unseen natural paraphrase",session=None,language="hi-en",source="user_statement"):
 reqs=scholarship_requirements();session=session or Session(id="semantic")
 return p.extract(text,session,reqs,resolve_all(reqs,session),language,source)

def test_semantic_success_and_approximate_income_is_never_verified():
 _,facts,ignored,outcome=run(pipeline([payload([extracted("annual_household_income",400000,True)])]))
 assert not ignored and outcome.provider=="sarvam-105b"
 assert facts[0].precision==Precision.approximate and facts[0].status==Status.UNCERTAIN

def test_canonical_numeric_normalization_at_ingestion_boundary():
 raw=extracted("annual_household_income","around 400000",True);raw["normalized_value"]="around 400000"
 year=extracted("year_of_study","second year")
 _,facts,_,_=run(pipeline([payload([raw,year])]))
 by={f.concept:f.normalized_value for f in facts}
 assert by=={"annual_household_income":400000,"year_of_study":2}
def test_unknown_concept_rejected_by_schema():
 with pytest.raises(ValidationError):SemanticExtraction.model_validate_json(payload([extracted("invented_field","x")]))
def test_malformed_response_retries_then_falls_back_safely():
 _,facts,_,outcome=run(pipeline(["not-json","still-not-json"]),"Main VIT Vellore mein second year student hoon")
 assert outcome.fallback_used and outcome.fallback_reason=="malformed_response"
 assert {f.concept for f in facts}>={"college_name","year_of_study","student_status"}
def test_empty_provider_result_is_distinct_and_does_not_use_fallback():
 _,facts,_,outcome=run(pipeline([payload([])]),"I am a second year student at VIT Vellore")
 assert outcome.semantic_success and outcome.candidate_fact_count==0
 assert not facts and not outcome.fallback_used
 assert outcome.extraction.facts==[] and not outcome.fallback_facts
def test_empty_supported_facts_with_unmapped_information_is_not_a_provider_failure():
 body=json.loads(payload([]));body["unmapped_information"]=["Two monthly income components require clarification"]
 _,facts,_,outcome=run(pipeline([json.dumps(body)]),"Monthly income components")
 assert not facts and outcome.semantic_success and not outcome.fallback_used
def test_valid_candidates_survive_one_malformed_or_unknown_candidate():
 mixed=json.loads(payload([extracted("college_name","VIT Vellore"),extracted("invented_field","bad"),{"concept":"year_of_study"}]))
 p=pipeline([json.dumps(mixed)])
 _,facts,_,outcome=run(p)
 assert [f.concept for f in facts]==["college_name"]
 assert outcome.extraction.unmapped_information==["Rejected malformed candidate fact at index 1","Rejected malformed candidate fact at index 2"]
 assert p.provider.last_semantic_diagnostics["pydantic_validation"]=="partially_valid"
def test_duplicate_provider_candidates_are_applied_once():
 candidate=extracted("college_name","VIT Vellore",span="VIT Vellore")
 _,facts,ignored,_=run(pipeline([payload([candidate,candidate])]))
 assert [fact.concept for fact in facts]==["college_name"]
 assert [item["reason"] for item in ignored]==["duplicate_candidate"]
def test_actual_user_text_and_structured_schema_are_sent_to_sdk():
 text="A previously unseen supported statement";p=pipeline([payload([extracted("college_name","Example University")])])
 run(p,text)
 call=p.provider.client.chat.calls[0]
 assert call["messages"][1]=={"role":"user","content":text}
 assert call["max_tokens"]==2000 and call["temperature"]==.1 and call["reasoning_effort"] is None
 response_format=call["request_options"]["additional_body_parameters"]["response_format"]
 assert response_format["type"]=="json_schema" and response_format["json_schema"]["strict"] is True
 concept_schema=response_format["json_schema"]["schema"]["$defs"]["ExtractedFact"]["properties"]["concept"]
 assert "annual household" in concept_schema["description"].casefold()
def test_complete_fact_array_is_recovered_from_length_truncated_envelope():
 raw=payload([extracted("college_name","VIT Vellore"),extracted("year_of_study",2)])
 truncated=raw[:raw.index('], "uncertainties"')+1]
 _,facts,_,outcome=run(pipeline([truncated]))
 assert {f.concept for f in facts}=={"college_name","year_of_study"}
 assert not outcome.fallback_used
 assert "truncated" in outcome.extraction.unmapped_information[0].casefold()
def test_truncated_empty_fact_array_requests_clarification_without_fallback():
 _,facts,_,outcome=run(pipeline(['{"facts":[]']),"Unsupported monthly components")
 assert not facts and outcome.semantic_success and not outcome.fallback_used
 assert outcome.extraction.clarification_needed
def test_semantic_source_guards_reject_temporary_domicile_and_weak_student_claim():
 weak_student=extracted("student_status","true",span="because of college");weak_student["explicit"]=False
 candidates=[extracted("state_of_domicile","Haryana",span="originally from Haryana"),extracted("state_of_domicile","Tamil Nadu",span="live in Vellore"),weak_student]
 _,facts,ignored,_=run(pipeline([payload(candidates)]))
 assert [(f.concept,f.normalized_value) for f in facts]==[("state_of_domicile","Haryana")]
 assert {item["reason"] for item in ignored}=={"temporary_residence_is_not_domicile"}
 assert all(f.concept!="student_status" for f in facts)
def test_current_course_language_normalizes_student_status_to_active():
 _,facts,_,_=run(pipeline([payload([extracted("student_status","doing BTech",span="doing my second year of BTech")])]))
 assert facts[0].normalized_value=="active"
def test_student_status_ignores_malformed_provider_normalized_scalar():
 candidate=extracted("student_status","student",span="kar rahi hoon");candidate["normalized_value"]=1
 _,facts,_,_=run(pipeline([payload([candidate])]))
 assert facts[0].normalized_value=="active" and facts[0].data_type=="string"
def test_missing_key_uses_rule_fallback():
 p=SemanticPipeline(SarvamService(Settings(sarvam_api_key="",sarvam_enabled=True)))
 assert run(p,"Family income around 4 lakh")[3].fallback_used
def test_user_fact_is_not_verified_and_verified_evidence_remains_authoritative():
 session=Session(id="authority",facts=[Fact(id="doc",concept="annual_household_income",value=382400,normalized_value=382400,status=Status.VERIFIED,source_type="document",source_id="ev")],evidence=[Evidence(id="ev",type="income_certificate",filename="income.txt",source="fixture")])
 _,facts,_,_=run(pipeline([payload([extracted("annual_household_income",500000)])]),session=session)
 session.facts.extend(facts);resolution=resolve_all(scholarship_requirements(),session)[6]
 assert facts[0].status==Status.STATED and resolution.status==Status.CONFLICT
def test_multiturn_accumulates_without_overwriting():
 p=pipeline([payload([extracted("college_name","VIT Vellore")]),payload([extracted("year_of_study",2)])]);s=Session(id="turns")
 for text in ("I study at VIT Vellore","I'm in my second year"):
  _,facts,_,_=run(p,text,s);s.facts.extend(facts)
 assert {f.concept for f in s.facts}=={"college_name","year_of_study"}
@pytest.mark.parametrize("language,text",[("hi-en","Mere parents mila ke saal ka lagbhag chaar lakh kamate hain"),("te-en","VIT Vellore lo second year BTech chaduvutunnanu"),("bn-en","Ami VIT Vellore-e second year-e porchi"),("hi-en","Our combined yearly earnings are roughly four hundred thousand")])
def test_multilingual_and_unseen_paraphrases_share_schema(language,text):
 expected=[extracted("annual_household_income",400000,True)] if "income" in text.casefold() or "kamate" in text.casefold() or "earnings" in text.casefold() else [extracted("college_name","VIT Vellore"),extracted("year_of_study",2)]
 _,facts,_,_=run(pipeline([payload(expected,language)]),text,language=language)
 assert facts and all(f.concept in {r.concept for r in scholarship_requirements()} for f in facts)
def test_preflight_stays_deterministic():
 reqs=scholarship_requirements();s=Session(id="empty")
 assert preflight(reqs,resolve_all(reqs,s))["status"]=="NOT_READY"

def test_minimum_question_is_selected_by_deterministic_core():
 reqs=scholarship_requirements();s=Session(id="question")
 _,facts,_,_=run(pipeline([payload([extracted("college_name","VIT Vellore")])]),session=s)
 s.facts.extend(facts)
 selected=questions(reqs,resolve_all(reqs,s))
 assert selected and selected[0].concept=="full_name"
