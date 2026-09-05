import base64
import re
from dataclasses import dataclass
from io import BytesIO
from uuid import uuid4
from .models import Fact,Precision,Status
from .config import Settings, settings

class SpeechServiceError(RuntimeError):
 def __init__(self, code: str, message: str, retryable: bool=False): super().__init__(message); self.code=code; self.retryable=retryable
@dataclass
class Transcript:
 text: str
 detected_language: str|None=None
class SpeechService:
 @property
 def available(self): return False
 def transcribe(self,content:bytes,filename:str,content_type:str|None=None)->Transcript: raise NotImplementedError
 def synthesize(self,text:str,language_code:str)->bytes: raise NotImplementedError
class UnavailableSpeechService(SpeechService):
 def transcribe(self,*_args,**_kwargs): raise SpeechServiceError("speech_unavailable","Live speech is unavailable because SARVAM_API_KEY is not configured.")
 def synthesize(self,*_args,**_kwargs): raise SpeechServiceError("speech_unavailable","Text-to-speech is unavailable because SARVAM_API_KEY is not configured.")
class SarvamSpeechService(SpeechService):
 def __init__(self,config:Settings=settings,client=None):
  self.config=config
  if client is not None: self.client=client
  else:
   from sarvamai import SarvamAI
   self.client=SarvamAI(api_subscription_key=config.sarvam_api_key,timeout=config.sarvam_timeout_seconds)
 @property
 def available(self): return bool(self.config.sarvam_api_key)
 def transcribe(self,content,filename,content_type=None):
  if not content: raise SpeechServiceError("no_speech","The recording was empty. Please try again.")
  try:
   stream=BytesIO(content); stream.name=filename
   response=self.client.speech_to_text.transcribe(file=stream,model=self.config.sarvam_stt_model,mode=self.config.sarvam_stt_mode)
   text=(getattr(response,"transcript",None) or "").strip()
   if not text: raise SpeechServiceError("no_speech","No speech was detected. Please try again.",True)
   return Transcript(text,getattr(response,"language_code",None))
  except SpeechServiceError: raise
  except Exception as exc:
   message=str(exc).casefold();kind=type(exc).__name__
   code="authentication_failed" if kind in {"UnauthorizedError","ForbiddenError"} or any(x in message for x in ("401","403","auth","api key")) else "credits_exhausted" if kind=="PaymentRequiredError" or "402" in message else "invalid_audio" if kind in {"BadRequestError","UnprocessableEntityError","ContentTooLargeError"} else "rate_limited" if kind=="TooManyRequestsError" else "provider_timeout" if "timeout" in message else "provider_error"
   descriptions={"authentication_failed":"Sarvam rejected the API credentials.","credits_exhausted":"Sarvam credits are unavailable or exhausted.","invalid_audio":"Sarvam rejected the audio format or contents.","rate_limited":"Sarvam rate-limited the request; try again later.","provider_timeout":"Sarvam timed out while processing the audio."}
   raise SpeechServiceError(code,descriptions.get(code,"Sarvam could not process the audio. Check provider status and try again."),code in {"provider_timeout","provider_error","rate_limited"}) from exc
 def synthesize(self,text,language_code):
  try:
   response=self.client.text_to_speech.convert(text=text[:2500],target_language_code=language_code,model=self.config.sarvam_tts_model,speaker="shubh")
   audios=getattr(response,"audios",None) or []
   if not audios: raise SpeechServiceError("no_audio","Sarvam returned no audio.")
   return base64.b64decode(audios[0])
  except SpeechServiceError: raise
  except Exception as exc: raise SpeechServiceError("tts_failed","KATHA could not synthesize audio; the text response is still available.",True) from exc
def build_speech_service(config:Settings=settings): return SarvamSpeechService(config) if config.sarvam_api_key else UnavailableSpeechService()
class SemanticExtractionService: pass
class RuleBasedSemanticExtractionService(SemanticExtractionService):
 def extract(self,text, corrections=()):
  original=text; low=text.casefold(); out=[]
  for c in corrections:
   if c.verified and c.heard_value.casefold() in low: text=re.sub(re.escape(c.heard_value),c.corrected_value,text,flags=re.I); low=text.casefold(); c.usage_count+=1
  def add(concept,value,typ="string",precision=Precision.exact): out.append(Fact(id=str(uuid4()),concept=concept,value=value,normalized_value=value,data_type=typ,source_type="user",status=Status.STATED,precision=precision,confidence=.9))
  if "vit vellore" in low or "vit valor" in low: add("college_name","VIT Vellore" if "vit vellore" in low else "VIT Valor")
  years={"first":1,"1st":1,"second":2,"2nd":2,"third":3,"3rd":3,"fourth":4,"4th":4}
  for k,v in years.items():
   if re.search(rf"\b{k}\s+year",low): add("year_of_study",v,"integer"); break
  if "student" in low: add("student_status","active")
  m=re.search(r"(?:income[^\d]{0,25})([\d,.]+)\s*(lakh|lac)?",low)
  if m:
   value=float(m.group(1).replace(",",""))*(100000 if m.group(2) else 1); value=int(value)
   add("annual_household_income",value,"currency",Precision.approximate if any(w in low for w in ["around","approximately","lagbhag","करीब"]) else Precision.exact)
  return text.strip(),out
class DocumentUnderstandingService: pass
class BasicDocumentService(DocumentUnderstandingService):
 FIXTURES={"income_certificate":{"annual_household_income":382400},"student_certificate":{"student_status":"active","college_name":"VIT Vellore"},"domicile_certificate":{"state_of_domicile":"Haryana"}}
 def extract(self,document_type,text,fixture=False):
  if fixture: return self.FIXTURES.get(document_type,{})
  if not text: return {}
  if document_type=="income_certificate":
   m=re.search(r"(?:income)[^\d]{0,30}([\d,]{4,})",text,re.I); return {"annual_household_income":int(m.group(1).replace(",",""))} if m else {}
  return {}
