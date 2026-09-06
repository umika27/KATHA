from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI,UploadFile,File,Form,HTTPException,Depends
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .models import *
from .workflow import scholarship_requirements
from .core import resolve_all,questions,preflight
from .services import RuleBasedSemanticExtractionService,BasicDocumentService,SarvamSpeechService,SpeechServiceError,build_document_pipeline
from .document_ai import check_if_expired
from .sarvam_service import SarvamService
from .semantic_pipeline import SemanticPipeline
from .store import SQLiteLikeJsonRepository
from .fixtures import fixture
from .concepts import LANGUAGES
from .config import settings

app=FastAPI(title="KATHA Core",version="0.1.0")
app.add_middleware(CORSMiddleware,allow_origins=list(settings.cors_origins),allow_methods=["*"],allow_headers=["*"])
audio_dir=Path("data/audio");audio_dir.mkdir(parents=True,exist_ok=True);app.mount("/api/audio",StaticFiles(directory=audio_dir),name="audio")
repo=SQLiteLikeJsonRepository(); extractor=RuleBasedSemanticExtractionService(); provider=SarvamService(); document_pipeline=build_document_pipeline(settings,provider.client if provider.configured else None); docs=document_pipeline.fallback; speech=SarvamSpeechService(settings,provider.client) if provider.configured else SarvamSpeechService(settings);semantic_pipeline=SemanticPipeline(provider,extractor);reqs=scholarship_requirements()
class Interaction(BaseModel):
 application_id:str|None=None
 session_id:str|None=None
 language_mode:str|None=None
 language:str|None=None
 text:str
class QuestionInteraction(Interaction): question_concept:str; question_text:str
class CorrectionIn(BaseModel): session_id:str; heard_value:str; corrected_value:str; concept:str; language:str="hi-en"; verified:bool=True
class AnswerIn(BaseModel): session_id:str; concept:str; value:str|int|float|bool; approximate:bool=False
class IncomePeriodIn(BaseModel): application_id:str; fact_id:str; period:str
class TTSIn(BaseModel): application_id:str|None=None; text:str; language_mode:str|None=None; language:str|None=None

TTS_LANG={"hi-en":"hi-IN","te-en":"te-IN","bn-en":"bn-IN"}

def state(id):
 s=repo.get(id); resolutions=resolve_all(reqs,s); pf=preflight(reqs,resolutions); qs=questions(reqs,resolutions,s)
 return {"application_id":id,"session_id":id,"application":{"id":id,"program_id":"educational-support-scholarship","application_type":"student_scholarship","title":"KATHA Educational Support Scholarship","requirements":[r.model_dump() for r in reqs],"readiness":pf["status"],"resolved_count":pf["resolved"],"missing_count":pf["missing"],"uncertain_count":pf["uncertain"],"conflict_count":pf["conflicts"]},"facts":[f.model_dump() for f in s.facts],"evidence":[e.model_dump() for e in s.evidence],"resolutions":[r.model_dump() for r in resolutions],"questions":[q.model_dump() for q in qs],"next_question":qs[0].question if qs else None,"preflight":pf,"corrections":[c.model_dump() for c in s.corrections],"pending_documents":[d.model_dump() for d in s.pending_documents]}
@app.get("/api/health")
def health(): return {"status":"ok","languages":LANGUAGES,"speech_available":speech.available,"database":"sqlite"}
@app.get("/api/config")
def public_config():
 return {"languages":LANGUAGES,"sarvamConfigured":provider.configured,"speechEnabled":provider.speech_enabled,"semanticExtractionEnabled":provider.semantic_enabled,"ttsEnabled":provider.tts_enabled,"documentAIEnabled":provider.document_ai_enabled,"speech_available":provider.speech_enabled,"max_recording_seconds":28}
@app.get("/api/session/{session_id}")
def session(session_id:str): return state(session_id)
@app.post("/api/applications",status_code=201)
def create_application():
 application_id=str(uuid4());repo.create(application_id);return state(application_id)
@app.get("/api/applications/{application_id}")
def get_application(application_id:str):
 if not repo.exists(application_id):raise HTTPException(404,"Application not found")
 return state(application_id)
@app.post("/api/applications/{application_id}/reset")
def reset_application(application_id:str):
 if not repo.exists(application_id):raise HTTPException(404,"Application not found")
 repo.reset(application_id,Session(id=application_id));return state(application_id)
@app.post("/api/interactions/text")
def interact(body:Interaction):
 return process_semantic_interaction(body,"user_statement")

def process_semantic_interaction(body:Interaction,source_type:str,question_context=None):
 application_id=body.application_id or body.session_id
 language=body.language_mode or body.language or "hi-en"
 if not application_id:raise HTTPException(422,{"code":"missing_application_id","message":"No active application was provided."})
 if not repo.exists(application_id):raise HTTPException(404,{"code":"application_not_found","message":"The active application no longer exists. Create a new application and try again."})
 if language not in LANGUAGES:raise HTTPException(422,{"code":"unsupported_language","message":"Unsupported language mode."})
 text=body.text.strip()
 if not text:raise HTTPException(422,{"code":"invalid_input","message":"Tell KATHA something about your scholarship application first."})
 s=repo.get(application_id);before=resolve_all(reqs,s);normalized,facts,ignored,outcome=semantic_pipeline.extract(text,s,reqs,before,language,source_type,question_context)
 if question_context:
  expected=question_context["concept"]
  compatible={"household_income","annual_household_income"} if expected in {"household_income","annual_household_income"} else {expected}
  rejected=[f for f in facts if f.concept not in compatible]
  ignored.extend({"fact":f.model_dump(mode="json"),"reason":"does_not_answer_current_question"} for f in rejected)
  facts=[f for f in facts if f.concept in compatible]
  if expected=="household_income":
   period=next((f.period for f in facts if f.period in {"monthly","annual"}),None)
   if not period:
    low=text.casefold()
    if any(w in low for w in ["month","mahine","mahina","monthly"]):period="monthly"
    elif any(w in low for w in ["year","annual","saal","yearly","per year"]):period="annual"
   if period:
    facts=apply_income_period(s,question_context.get("fact_id"),period,save=False)
 s.facts.extend(facts);repo.save(s);result=state(application_id)
 fallback=f"I understood {len(facts)} detail(s)." if facts else "I could not safely extract a new fact. You can answer the next question."
 if not facts and outcome.semantic_success and not outcome.fallback_used:
  fallback="I understood your message, but I couldn't map any of it to the information this scholarship needs yet."
 response_text=fallback if outcome.fallback_used or not facts else provider.generate_response({"applied_facts":[{"concept":f.concept,"value":f.normalized_value,"status":f.status,"approximate":f.precision==Precision.approximate} for f in facts],"next_question":result["next_question"],"preflight":result["preflight"]},fallback,language)
 return {"application_id":application_id,"session_id":application_id,"normalized_text":normalized,"semantic":outcome.model_dump(mode="json"),"applied_facts":[f.model_dump() for f in facts],"ignored_facts":ignored,"extracted_candidate_facts":[f.model_dump() for f in facts],"application":result,"application_summary":result["application"],"next_question":result["questions"][0] if result["questions"] else None,"response_text":response_text}
@app.post("/api/interactions/speech")
async def speech_interact(session_id:str=Form(...),language:str=Form("hi-en"),file:UploadFile=File(...)):
 if language not in LANGUAGES: raise HTTPException(422,"Unsupported language")
 content=await file.read()
 if len(content)>15_000_000: raise HTTPException(413,"Audio file is too large.")
 try: result=speech.transcribe(content,file.filename or "recording.webm",file.content_type)
 except SpeechServiceError as exc: raise HTTPException(503,{"code":exc.code,"message":str(exc),"retryable":exc.retryable}) from exc
 typed=process_semantic_interaction(Interaction(application_id=session_id,language_mode=language,text=result.text),"speech_transcript");audio_url=None;tts_error=None
 try:
  audio=speech.synthesize(typed["response_text"],TTS_LANG[language]);name=f"{uuid4()}.wav";(audio_dir/name).write_bytes(audio);audio_url=f"/api/audio/{name}"
 except SpeechServiceError as exc: tts_error={"code":exc.code,"message":str(exc)}
 return {"session_id":session_id,"transcript":result.text,"detected_language":result.detected_language,"semantic":typed["semantic"],"applied_facts":typed["applied_facts"],"ignored_facts":typed["ignored_facts"],"candidate_facts":typed["applied_facts"],"application":typed["application"],"application_summary":typed["application_summary"],"next_question":typed["next_question"],"response_text":typed["response_text"],"audio_url":audio_url,"tts_error":tts_error}
@app.post("/api/interactions/answer/text")
def answer_text(body:QuestionInteraction):
 return process_question_answer(body,"questionnaire_typed")
def process_question_answer(body:QuestionInteraction,source_type:str):
 application_id=body.application_id or body.session_id
 if not application_id or not repo.exists(application_id):raise HTTPException(404,{"code":"application_not_found","message":"The active application no longer exists."})
 current=state(application_id)["questions"]
 active=next((q for q in current if q["concept"]==body.question_concept and (not body.question_text or q["question"].strip()==body.question_text.strip() or body.question_text.strip() in q.get("localized_questions",{}).values() or q["concept"]==body.question_concept)),None)
 if not active:raise HTTPException(409,{"code":"question_changed","message":"The application has moved to a different question. Please answer the current question."})
 return process_semantic_interaction(body,source_type,{"concept":body.question_concept,"question":active["question"],"type":active["type"],"fact_id":active.get("fact_id"),"known_value":active.get("known_value"),"missing_qualifier":active.get("missing_qualifier")})
@app.post("/api/interactions/answer/speech")
async def answer_speech(application_id:str=Form(...),question_concept:str=Form(...),question_text:str=Form(...),language_mode:str=Form("hi-en"),file:UploadFile=File(...)):
 content=await file.read()
 if not content:raise HTTPException(422,{"code":"no_audio","message":"No audio was captured. Try again or type your answer."})
 if len(content)>15_000_000:raise HTTPException(413,{"code":"audio_too_large","message":"The recording is too large."})
 try:transcribed=speech.transcribe(content,file.filename or "answer.webm",file.content_type)
 except SpeechServiceError as exc:raise HTTPException(503,{"code":exc.code,"message":"Couldn't hear that. Try again or type your answer.","retryable":exc.retryable}) from exc
 result=process_question_answer(QuestionInteraction(application_id=application_id,question_concept=question_concept,question_text=question_text,language_mode=language_mode,text=transcribed.text),"questionnaire_speech")
 audio_url=None;tts_error=None
 try:
  if result.get("response_text") and speech.available:
   audio=speech.synthesize(result["response_text"],TTS_LANG.get(language_mode,"hi-IN"))
   name=f"{uuid4()}.wav";(audio_dir/name).write_bytes(audio);audio_url=f"/api/audio/{name}"
 except SpeechServiceError as exc: tts_error={"code":exc.code,"message":str(exc)}
 return {**result,"transcript":transcribed.text,"detected_language":transcribed.detected_language,"audio_url":audio_url,"tts_error":tts_error}
@app.post("/api/tts")
def tts(body:TTSIn):
 language=body.language_mode or body.language or "hi-en";text=body.text.strip()
 if body.application_id and not repo.exists(body.application_id):raise HTTPException(404,{"code":"application_not_found","message":"The active application no longer exists."})
 if not text:raise HTTPException(422,{"code":"invalid_input","message":"There is no text to speak."})
 if language not in LANGUAGES:raise HTTPException(422,{"code":"unsupported_language","message":"Audio is unavailable for this language mode."})
 try: audio=speech.synthesize(text,TTS_LANG[language])
 except SpeechServiceError as exc: raise HTTPException(503,{"code":exc.code,"message":str(exc),"retryable":exc.retryable}) from exc
 if not audio:raise HTTPException(502,{"code":"empty_audio","message":"Audio generation returned no playable content."})
 return Response(audio,media_type="audio/wav",headers={"Cache-Control":"no-store","Content-Disposition":"inline"})
@app.post("/api/answers")
def answer(body:AnswerIn):
 if body.concept not in {r.concept for r in reqs}: raise HTTPException(422,"Unknown concept")
 s=repo.get(body.session_id);s.facts.append(Fact(id=str(uuid4()),concept=body.concept,value=body.value,normalized_value=body.value,status=Status.STATED,source_type="user",precision=Precision.approximate if body.approximate else Precision.exact));repo.save(s);return state(body.session_id)
@app.post("/api/clarifications/income-period")
def clarify_income_period(body:IncomePeriodIn):
 if body.period not in {"monthly","annual"}:raise HTTPException(422,{"code":"invalid_income_period","message":"Choose monthly or annual, or edit the amount."})
 if not repo.exists(body.application_id):raise HTTPException(404,{"code":"application_not_found","message":"The active application no longer exists."})
 s=repo.get(body.application_id);apply_income_period(s,body.fact_id,body.period);return state(body.application_id)
def apply_income_period(s:Session,fact_id:str|None,period:str,save=True):
 target_id=fact_id or next((f.id for f in reversed(s.facts) if f.concept=="household_income"),None)
 observation=next((f for f in s.facts if f.id==target_id and f.concept=="household_income"),None)
 if not observation:raise HTTPException(404,{"code":"income_observation_not_found","message":"That income observation no longer exists."})
 observation.period=period;observation.status=Status.STATED;observation.updated_at=now()
 amount=float(observation.normalized_value);annual=amount if period=="annual" else amount*12;derived=period=="monthly"
 fact=Fact(id=str(uuid4()),concept="annual_household_income",value=int(annual) if annual.is_integer() else annual,normalized_value=int(annual) if annual.is_integer() else annual,data_type="number",source_type="derived" if derived else "user_clarification",source_id=observation.id,status=Status.DERIVED if derived else Status.STATED,confidence=observation.confidence,precision=observation.precision,unit="INR",period="annual",source_span=observation.source_span,explicit=True,interpretation_provider=observation.interpretation_provider,derived_from_fact_ids=[observation.id],derivation=f"{observation.normalized_value} × 12" if derived else "User clarified the stated amount is annual.")
 if save:s.facts.append(fact);repo.save(s)
 return [fact]
@app.post("/api/access-point/interact")
def access_interact(body:Interaction):
 result=interact(body); st=result["application"]; pf=st["preflight"]
 return {"session_id":result["application_id"],"ui_state":"READY" if pf["status"]=="READY" else "RESULT","response_text":result["response_text"],"application_status":"READY" if pf["status"]=="READY" else "IN_PROGRESS","resolved":pf["resolved"],"missing":pf["missing"],"uncertain":pf["uncertain"],"conflicts":pf["conflicts"],"next_question":st["next_question"],"tts_audio_url":None}
@app.post("/api/corrections")
def correction(body:CorrectionIn):
 if body.concept not in {r.concept for r in reqs}: raise HTTPException(422,"Unknown concept")
 s=repo.get(body.session_id)
 for c in s.corrections:
  if c.heard_value.casefold()==body.heard_value.casefold() and c.concept==body.concept: c.corrected_value=body.corrected_value;c.verified=body.verified;c.usage_count+=1;memory=c;break
 else:
  memory=CorrectionMemory(**body.model_dump(exclude={"session_id"}));s.corrections.append(memory)
 s.facts.append(Fact(id=str(uuid4()),concept=body.concept,value=body.corrected_value,normalized_value=body.corrected_value,status=Status.STATED,source_type="user_correction",confidence=1.0,source_span=body.corrected_value,explicit=True));repo.save(s)
 return {"correction":memory,"application":state(body.session_id)}
def apply_accepted_candidate(s: Session, candidate: DocumentReviewCandidate, field_ids: list[str]|None=None, overrides: dict[str, Any]|None=None):
 overrides = overrides or {}
 eid = str(uuid4())
 doc_type = candidate.document_type
 issue_date = next((f.issue_date for f in candidate.fields if f.issue_date), None)
 expiry_date = next((f.expiry_date for f in candidate.fields if f.expiry_date), None)
 financial_year = next((f.financial_year for f in candidate.fields if f.financial_year), None)
 is_expired = any(f.is_expired for f in candidate.fields) or check_if_expired(expiry_date)
 first_field = candidate.fields[0] if candidate.fields else None
 ev = Evidence(
  id=eid,
  type=doc_type,
  filename=candidate.filename,
  source="demo_fixture" if candidate.provider=="demo-fixture" else "upload",
  verification_state="EXPIRED" if is_expired else "VERIFIED",
  uploaded_at=now(),
  issue_date=issue_date,
  expiry_date=expiry_date,
  financial_year=financial_year,
  is_expired=is_expired,
  source_page=first_field.page_number if first_field else 1,
  source_text=first_field.source_span if first_field else None,
  provider=candidate.provider,
  confidence=first_field.confidence if first_field else 0.95,
  document_id=candidate.document_id,
  raw_text=candidate.raw_text[:2000] if candidate.raw_text else None
 )
 ids = []
 for f in candidate.fields:
  if field_ids is not None and f.id not in field_ids:
   continue
  if f.concept == doc_type:
   continue
  is_edited = f.concept in overrides and overrides[f.concept] != f.normalized_value
  if is_edited:
   val = overrides[f.concept]
   norm_val = val
   src_type = "user_edited_document"
   status = Status.STATED
   derivation = f"Edited from document value '{f.value}'"
  else:
   val = f.value
   norm_val = f.normalized_value if f.normalized_value is not None else f.value
   src_type = "document"
   status = Status.VERIFIED if not is_expired else Status.UNCERTAIN
   derivation = None
  fact = Fact(
   id=str(uuid4()),
   concept=f.concept,
   value=val,
   normalized_value=norm_val,
   data_type=f.data_type,
   source_type=src_type,
   source_id=eid,
   status=status,
   confidence=f.confidence,
   precision=Precision.exact,
   unit=f.unit,
   period=f.period,
   source_span=f.source_span,
   explicit=True,
   interpretation_provider=candidate.provider,
   derivation=derivation
  )
  s.facts.append(fact)
  ids.append(fact.id)
 proof_fact = Fact(
  id=str(uuid4()),
  concept=doc_type,
  value=not is_expired,
  normalized_value=not is_expired,
  status=Status.VERIFIED if not is_expired else Status.UNCERTAIN,
  source_type="document",
  source_id=eid,
  source_span=f"Verified {doc_type}: {candidate.filename}"
 )
 s.facts.append(proof_fact)
 ids.append(proof_fact.id)
 ev.extracted_facts = ids
 s.evidence.append(ev)
 s.pending_documents = [p for p in s.pending_documents if p.document_id != candidate.document_id]
 return ev, ids

class UploadSecurityContext:
 def __init__(self,allow_trusted_auto_accept:bool=False):
  self.allow_trusted_auto_accept=allow_trusted_auto_accept

def get_upload_security_context()->UploadSecurityContext:
 # Normal production and applicant-facing requests NEVER allow auto-accept bypass
 return UploadSecurityContext(allow_trusted_auto_accept=False)

@app.post("/api/documents/upload")
async def upload(session_id:str=Form(...),document_type:str=Form(...),file:UploadFile|None=File(None),fixture_mode:bool=Form(False),auto_accept:bool=Form(False),sec:UploadSecurityContext=Depends(get_upload_security_context)):
 if not repo.exists(session_id): raise HTTPException(404,{"code":"application_not_found","message":"The active application no longer exists."})
 if document_type not in docs.FIXTURES: raise HTTPException(422,"Unsupported document type")
 raw=await file.read() if file else b""
 if len(raw)>15_000_000: raise HTTPException(413,{"code":"file_too_large","message":"Document file is too large."})
 is_real_file=bool(file and len(raw)>0)
 fn=file.filename if file else f"fixture_{document_type}.txt"
 ct=file.content_type if file else "text/plain"
 is_fixture=not is_real_file
 try:
  candidate=document_pipeline.extract(raw,fn,ct,document_type,fixture_mode=is_fixture)
 except ValueError as exc:
  raise HTTPException(422,{"code":"unsupported_document","message":str(exc)}) from exc
 except Exception as exc:
  raise HTTPException(503,{"code":"document_ai_failed","message":"Couldn't read this document. Try another file or format."}) from exc
 if not candidate.fields:
  return {"status":"UNKNOWN","message":"No supported facts could be extracted from this document; nothing was verified.","extracted_facts":[],"candidate":candidate.model_dump(mode="json")}
 s=repo.get(session_id)
 # INVARIANT: A normal applicant-facing request must NEVER be able to bypass candidate review
 # and directly create VERIFIED evidence merely by supplying client-controlled parameters.
 # Real document uploads ALWAYS require candidate review.
 # Trusted auto-accept is isolated behind server-side dependency injection for test fixture compatibility.
 if sec.allow_trusted_auto_accept and not is_real_file and (fixture_mode or auto_accept):
  ev,ids=apply_accepted_candidate(s,candidate)
  repo.save(s)
  return {"status":"VERIFIED","evidence":ev.model_dump(mode="json"),"extracted_facts":[f.model_dump() for f in s.facts if f.id in ids],"application":state(session_id)}
 s.pending_documents=[p for p in s.pending_documents if p.document_type!=document_type]+[candidate]
 repo.save(s)
 return {"status":"REVIEW_REQUIRED","message":f"KATHA found {len([f for f in candidate.fields if f.concept!=document_type])} detail(s) in this document. Please review.","candidate":candidate.model_dump(mode="json"),"application":state(session_id)}

@app.post("/api/documents/candidates/accept")
def accept_candidate(body:AcceptCandidateIn):
 if not repo.exists(body.application_id): raise HTTPException(404,{"code":"application_not_found","message":"The active application no longer exists."})
 s=repo.get(body.application_id)
 candidate=next((p for p in s.pending_documents if p.document_id==body.document_id),None)
 if not candidate: raise HTTPException(404,{"code":"candidate_not_found","message":"Pending document review candidate not found."})
 ev,ids=apply_accepted_candidate(s,candidate,body.field_ids,body.overrides)
 repo.save(s)
 return {"status":"ACCEPTED","evidence":ev.model_dump(mode="json"),"extracted_facts":[f.model_dump() for f in s.facts if f.id in ids],"application":state(body.application_id)}

@app.post("/api/documents/candidates/ignore")
def ignore_candidate(body:IgnoreCandidateIn):
 if not repo.exists(body.application_id): raise HTTPException(404,{"code":"application_not_found","message":"The active application no longer exists."})
 s=repo.get(body.application_id)
 s.pending_documents=[p for p in s.pending_documents if p.document_id!=body.document_id]
 repo.save(s)
 return {"status":"IGNORED","application":state(body.application_id)}

@app.delete("/api/documents/{application_id}/{evidence_id}")
@app.post("/api/documents/remove")
def remove_evidence(application_id:str,evidence_id:str|None=None,body:dict|None=None):
 app_id=application_id or (body.get("application_id") if body else None)
 ev_id=evidence_id or (body.get("evidence_id") if body else None)
 if not app_id or not repo.exists(app_id): raise HTTPException(404,{"code":"application_not_found","message":"The active application no longer exists."})
 s=repo.get(app_id)
 s.evidence=[e for e in s.evidence if e.id!=ev_id]
 s.facts=[f for f in s.facts if f.source_id!=ev_id]
 repo.save(s)
 return {"status":"REMOVED","application":state(app_id)}

@app.post("/api/conflicts/resolve")
def resolve_conflict(body:ConflictResolveIn):
 if not repo.exists(body.application_id): raise HTTPException(404,{"code":"application_not_found","message":"The active application no longer exists."})
 s=repo.get(body.application_id)
 choice=body.resolution_choice
 def _match(c:str)->bool:
  return c==body.concept or (body.concept in {"household_income","annual_household_income"} and c in {"household_income","annual_household_income"})
 if choice=="use_document":
  doc_fact=next((f for f in s.facts if _match(f.concept) and (f.status==Status.VERIFIED or f.source_type=="document")),None)
  for f in s.facts:
   if _match(f.concept) and f.source_type in {"user","user_statement","speech_transcript","questionnaire_typed","questionnaire_speech","user_correction"}:
    f.derivation="superseded_by_document"
  if doc_fact:
   s.facts.append(Fact(id=str(uuid4()),concept=doc_fact.concept,value=doc_fact.value,normalized_value=doc_fact.normalized_value,status=Status.VERIFIED,source_type="user_reconciliation",source_id=doc_fact.source_id,derivation=f"User reconciled conflict by accepting document value {doc_fact.value}"))
 elif choice=="keep_statement":
  for f in s.facts:
   if _match(f.concept) and (f.status==Status.VERIFIED or f.source_type=="document"):
    f.status=Status.UNCERTAIN
    f.derivation="disputed_by_user"
 elif choice=="edit":
  for f in s.facts:
   if _match(f.concept) and f.source_type in {"user","user_statement","speech_transcript","questionnaire_typed","questionnaire_speech","user_correction"}:
    f.derivation="superseded_by_correction"
  s.facts.append(Fact(id=str(uuid4()),concept=body.concept,value=body.custom_value,normalized_value=body.custom_value,status=Status.STATED,source_type="user_correction",confidence=1.0,derivation="User corrected value during conflict resolution"))
 elif choice=="replace_document":
  target_ev_id=body.evidence_id or next((f.source_id for f in s.facts if _match(f.concept) and f.source_id),None)
  if target_ev_id:
   s.evidence=[e for e in s.evidence if e.id!=target_ev_id]
   s.facts=[f for f in s.facts if f.source_id!=target_ev_id]
 repo.save(s)
 return {"status":"RESOLVED","application":state(body.application_id)}
@app.post("/api/demo/reset/{session_id}")
def reset(session_id:str,scenario:str="partial"):
 scenario=scenario.replace("_","-")
 if scenario not in {"initial","partial","conflict","missing-proof","ready"}: raise HTTPException(422,"Unknown scenario")
 repo.reset(session_id,fixture(scenario,session_id));return state(session_id)
