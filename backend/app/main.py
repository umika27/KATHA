from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI,UploadFile,File,Form,HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .models import *
from .workflow import scholarship_requirements
from .core import resolve_all,questions,preflight
from .services import RuleBasedSemanticExtractionService,BasicDocumentService,build_speech_service,SpeechServiceError
from .store import SQLiteLikeJsonRepository
from .fixtures import fixture
from .concepts import LANGUAGES
from .config import settings

app=FastAPI(title="KATHA Core",version="0.1.0")
app.add_middleware(CORSMiddleware,allow_origins=list(settings.cors_origins),allow_methods=["*"],allow_headers=["*"])
audio_dir=Path("data/audio");audio_dir.mkdir(parents=True,exist_ok=True);app.mount("/api/audio",StaticFiles(directory=audio_dir),name="audio")
repo=SQLiteLikeJsonRepository(); extractor=RuleBasedSemanticExtractionService(); docs=BasicDocumentService(); speech=build_speech_service(); reqs=scholarship_requirements()
class Interaction(BaseModel): session_id:str; language:str="hi-en"; text:str
class CorrectionIn(BaseModel): session_id:str; heard_value:str; corrected_value:str; concept:str; language:str="hi-en"; verified:bool=True
class AnswerIn(BaseModel): session_id:str; concept:str; value:str|int|float|bool; approximate:bool=False
class TTSIn(BaseModel): text:str; language:str="hi-en"

TTS_LANG={"hi-en":"hi-IN","te-en":"te-IN","bn-en":"bn-IN"}

def state(id):
 s=repo.get(id); resolutions=resolve_all(reqs,s); pf=preflight(reqs,resolutions); qs=questions(reqs,resolutions)
 return {"session_id":id,"application":{"id":"scholarship-demo","application_type":"student_scholarship","title":"KATHA Educational Support Scholarship","requirements":[r.model_dump() for r in reqs],"readiness":pf["status"],"resolved_count":pf["resolved"],"missing_count":pf["missing"],"uncertain_count":pf["uncertain"],"conflict_count":pf["conflicts"]},"facts":[f.model_dump() for f in s.facts],"evidence":[e.model_dump() for e in s.evidence],"resolutions":[r.model_dump() for r in resolutions],"questions":[q.model_dump() for q in qs],"next_question":qs[0].question if qs else None,"preflight":pf,"corrections":[c.model_dump() for c in s.corrections]}
@app.get("/api/health")
def health(): return {"status":"ok","languages":LANGUAGES,"speech_available":speech.available,"database":"sqlite"}
@app.get("/api/config")
def public_config(): return {"languages":LANGUAGES,"speech_available":speech.available,"stt_model":settings.sarvam_stt_model if speech.available else None,"tts_model":settings.sarvam_tts_model if speech.available else None,"max_recording_seconds":28}
@app.get("/api/session/{session_id}")
def session(session_id:str): return state(session_id)
@app.post("/api/interactions/text")
def interact(body:Interaction):
 if body.language not in LANGUAGES: raise HTTPException(422,"Unsupported language")
 s=repo.get(body.session_id); normalized,facts=extractor.extract(body.text,s.corrections); s.facts.extend(facts); repo.save(s); result=state(body.session_id)
 return {"session_id":body.session_id,"normalized_text":normalized,"extracted_candidate_facts":[f.model_dump() for f in facts],"application_summary":result["application"],"next_question":result["next_question"],"response_text":f"I understood {len(facts)} detail(s)." if facts else "I could not safely extract a new fact. You can answer the next question."}
@app.post("/api/interactions/speech")
async def speech_interact(session_id:str=Form(...),language:str=Form(...),file:UploadFile=File(...)):
 if language not in LANGUAGES: raise HTTPException(422,"Unsupported language")
 content=await file.read()
 if len(content)>15_000_000: raise HTTPException(413,"Audio file is too large.")
 try: result=speech.transcribe(content,file.filename or "recording.webm",file.content_type)
 except SpeechServiceError as exc: raise HTTPException(503,{"code":exc.code,"message":str(exc),"retryable":exc.retryable}) from exc
 typed=interact(Interaction(session_id=session_id,language=language,text=result.text));audio_url=None;tts_error=None
 try:
  audio=speech.synthesize(typed["response_text"],TTS_LANG[language]);name=f"{uuid4()}.wav";(audio_dir/name).write_bytes(audio);audio_url=f"/api/audio/{name}"
 except SpeechServiceError as exc: tts_error={"code":exc.code,"message":str(exc)}
 return {"session_id":session_id,"transcript":result.text,"detected_language":result.detected_language,"candidate_facts":typed["extracted_candidate_facts"],"application_summary":typed["application_summary"],"next_question":typed["next_question"],"response_text":typed["response_text"],"audio_url":audio_url,"tts_error":tts_error}
@app.post("/api/tts")
def tts(body:TTSIn):
 if body.language not in LANGUAGES: raise HTTPException(422,"Unsupported language")
 try: audio=speech.synthesize(body.text,TTS_LANG[body.language])
 except SpeechServiceError as exc: raise HTTPException(503,{"code":exc.code,"message":str(exc),"retryable":exc.retryable}) from exc
 return Response(audio,media_type="audio/wav",headers={"Cache-Control":"no-store"})
@app.post("/api/answers")
def answer(body:AnswerIn):
 if body.concept not in {r.concept for r in reqs}: raise HTTPException(422,"Unknown concept")
 s=repo.get(body.session_id);s.facts.append(Fact(id=str(uuid4()),concept=body.concept,value=body.value,normalized_value=body.value,status=Status.STATED,source_type="user",precision=Precision.approximate if body.approximate else Precision.exact));repo.save(s);return state(body.session_id)
@app.post("/api/access-point/interact")
def access_interact(body:Interaction):
 result=interact(body); st=state(body.session_id); pf=st["preflight"]
 return {"session_id":body.session_id,"ui_state":"READY" if pf["status"]=="READY" else "RESULT","response_text":result["response_text"],"application_status":"READY" if pf["status"]=="READY" else "IN_PROGRESS","resolved":pf["resolved"],"missing":pf["missing"],"uncertain":pf["uncertain"],"conflicts":pf["conflicts"],"next_question":st["next_question"],"tts_audio_url":None}
@app.post("/api/corrections")
def correction(body:CorrectionIn):
 s=repo.get(body.session_id)
 for c in s.corrections:
  if c.heard_value.casefold()==body.heard_value.casefold() and c.concept==body.concept: c.corrected_value=body.corrected_value;c.verified=body.verified;c.usage_count+=1;repo.save(s);return c
 c=CorrectionMemory(**body.model_dump(exclude={"session_id"}));s.corrections.append(c);repo.save(s);return c
@app.post("/api/documents/upload")
async def upload(session_id:str=Form(...),document_type:str=Form(...),fixture_mode:bool=Form(False),file:UploadFile|None=File(None)):
 if document_type not in docs.FIXTURES: raise HTTPException(422,"Unsupported document type")
 raw=await file.read() if file else b""; text=""
 if raw and (not file or file.content_type!="application/pdf"):
  text=raw.decode("utf-8",errors="ignore")
 elif raw:
  try:
   from pypdf import PdfReader
   import io
   text="\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages)
  except Exception: text=""
 extracted=docs.extract(document_type,text,fixture_mode)
 if not extracted: return {"status":"UNKNOWN","message":"No supported facts could be extracted; nothing was verified.","extracted_facts":[]}
 s=repo.get(session_id); eid=str(uuid4()); ids=[]
 for c,v in extracted.items():
  f=Fact(id=str(uuid4()),concept=c,value=v,normalized_value=v,status=Status.VERIFIED,source_type="document",source_id=eid);s.facts.append(f);ids.append(f.id)
 proof=Fact(id=str(uuid4()),concept=document_type,value=True,normalized_value=True,status=Status.VERIFIED,source_type="document",source_id=eid);s.facts.append(proof);ids.append(proof.id)
 e=Evidence(id=eid,type=document_type,filename=file.filename if file else f"fixture_{document_type}.txt",source="demo_fixture" if fixture_mode else "upload",extracted_facts=ids);s.evidence.append(e);repo.save(s)
 return {"status":"VERIFIED","evidence":e,"extracted_facts":[f for f in s.facts if f.id in ids]}
@app.post("/api/demo/reset/{session_id}")
def reset(session_id:str,scenario:str="partial"):
 scenario=scenario.replace("_","-")
 if scenario not in {"initial","partial","conflict","missing-proof","ready"}: raise HTTPException(422,"Unknown scenario")
 repo.reset(session_id,fixture(scenario,session_id));return state(session_id)
