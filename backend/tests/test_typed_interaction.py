from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main
from app.semantic import ExtractedFact,SemanticExtraction,SemanticOutcome


client=TestClient(main.app)
STORY="Mummy papa mila ke around 4 lakh yearly kamate hain aur main VIT Vellore mein second year BTech kar rahi hoon."


def provider_outcome():
 facts=[
  ExtractedFact(concept="annual_household_income",value=400000,normalized_value=400000,unit="INR",period="annual",approximate=True,confidence=.96,source_span="around 4 lakh yearly",explicit=True),
  ExtractedFact(concept="college_name",value="VIT Vellore",normalized_value="VIT Vellore",unit=None,period="unknown",approximate=False,confidence=.98,source_span="VIT Vellore",explicit=True),
  ExtractedFact(concept="course_name",value="BTech",normalized_value="BTech",unit=None,period="unknown",approximate=False,confidence=.98,source_span="BTech",explicit=True),
  ExtractedFact(concept="year_of_study",value=2,normalized_value=2,unit=None,period="unknown",approximate=False,confidence=.98,source_span="second year",explicit=True),
  ExtractedFact(concept="student_status",value="active",normalized_value="active",unit=None,period="unknown",approximate=False,confidence=.96,source_span="second year BTech kar rahi hoon",explicit=True),
 ]
 extraction=SemanticExtraction(facts=facts,uncertainties=[],unmapped_information=[],clarification_needed=False,clarification_reason=None,language_detected="hi-en")
 return SemanticOutcome(extraction=extraction,provider="sarvam-105b",semantic_success=True,candidate_fact_count=len(facts))


def create_application():
 response=client.post("/api/applications")
 assert response.status_code==201
 return response.json()["application_id"]


def test_typed_story_uses_provider_and_writes_only_to_active_application(monkeypatch):
 active=create_application()
 legacy="demo-01"
 before_legacy=main.repo.exists(legacy)
 calls=[]
 def extract(text,context):
  calls.append((text,context))
  return provider_outcome()
 monkeypatch.setattr(main.semantic_pipeline.provider,"extract_semantic_facts",extract)
 monkeypatch.setattr(main.provider,"generate_response",lambda *_:"Understood.")

 response=client.post("/api/interactions/text",json={"application_id":active,"text":STORY,"language_mode":"bn-en"})
 body=response.json()

 assert response.status_code==200 and calls[0][0]==STORY
 assert calls[0][1]["language_mode"]=="bn-en"
 assert body["application_id"]==active and body["application"]["application_id"]==active
 assert {fact["concept"] for fact in body["applied_facts"]}=={"annual_household_income","college_name","course_name","year_of_study","student_status"}
 income=next(fact for fact in body["applied_facts"] if fact["concept"]=="annual_household_income")
 assert income["normalized_value"]==400000 and income["status"]=="UNCERTAIN"
 assert all(fact["interpretation_provider"]=="sarvam-105b" for fact in body["applied_facts"])
 assert main.repo.exists(legacy)==before_legacy


def test_typed_and_speech_transcript_share_equivalent_semantic_ingestion(monkeypatch):
 typed_id=create_application();speech_id=create_application();calls=[]
 def extract(text,context):
  calls.append((text,context))
  return provider_outcome()
 monkeypatch.setattr(main.semantic_pipeline.provider,"extract_semantic_facts",extract)
 monkeypatch.setattr(main.provider,"generate_response",lambda *_:"Understood.")
 monkeypatch.setattr(main,"speech",SimpleNamespace(
  transcribe=lambda *_:SimpleNamespace(text=STORY,detected_language="hi-IN"),
  synthesize=lambda *_:b"RIFF",
 ))
 typed=client.post("/api/interactions/text",json={"application_id":typed_id,"text":STORY,"language_mode":"hi-en"}).json()
 spoken=client.post("/api/interactions/speech",data={"session_id":speech_id,"language":"hi-en"},files={"file":("voice.webm",b"audio","audio/webm")}).json()

 canonical=lambda facts:{(fact["concept"],str(fact["normalized_value"]),fact["status"]) for fact in facts}
 assert canonical(typed["applied_facts"])==canonical(spoken["applied_facts"])
 assert {fact["source_type"] for fact in typed["applied_facts"]}=={"user_statement"}
 assert {fact["source_type"] for fact in spoken["applied_facts"]}=={"speech_transcript"}
 assert len(calls)==2


def test_supported_no_fact_provider_result_is_visible_without_rule_fallback(monkeypatch):
 active=create_application()
 empty=SemanticExtraction(facts=[],uncertainties=[],unmapped_information=["No scholarship concepts"],clarification_needed=False,clarification_reason=None,language_detected="en")
 monkeypatch.setattr(main.semantic_pipeline.provider,"extract_semantic_facts",lambda *_:SemanticOutcome(extraction=empty,provider="sarvam-105b",semantic_success=True,candidate_fact_count=0))
 response=client.post("/api/interactions/text",json={"application_id":active,"text":"My favourite colour is blue.","language_mode":"te-en"})
 body=response.json()
 assert response.status_code==200 and not body["applied_facts"]
 assert body["semantic"]["fallback_used"] is False
 assert "couldn't map any of it" in body["response_text"]


def test_typed_interaction_rejects_missing_unknown_application_and_blank_input():
 assert client.post("/api/interactions/text",json={"text":"I study at VIT.","language_mode":"hi-en"}).status_code==422
 assert client.post("/api/interactions/text",json={"application_id":"not-an-application","text":"I study at VIT.","language_mode":"hi-en"}).status_code==404
 active=create_application()
 assert client.post("/api/interactions/text",json={"application_id":active,"text":"   ","language_mode":"hi-en"}).status_code==422
