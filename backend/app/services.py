import re
from dataclasses import dataclass
from uuid import uuid4
from .models import Fact,Precision,Status
from .config import Settings, settings
from .sarvam_service import SarvamError, SarvamService

SpeechServiceError=SarvamError
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
  self.provider=SarvamService(config,client);self.config=config
 @property
 def available(self): return self.provider.speech_enabled
 def transcribe(self,content,filename,content_type=None):
  text,language=self.provider.transcribe_audio(content,filename,content_type);return Transcript(text,language)
 def synthesize(self,text,language_code):
  return self.provider.synthesize_speech(text,language_code)
def build_speech_service(config:Settings=settings): return SarvamSpeechService(config) if config.sarvam_api_key else UnavailableSpeechService()
class SemanticExtractionService: pass
class RuleBasedSemanticExtractionService(SemanticExtractionService):
 def extract(self,text, corrections=(), question_context=None):
  original=text; low=text.casefold(); out=[]
  for c in corrections:
   if c.verified and c.heard_value.casefold() in low: text=re.sub(re.escape(c.heard_value),c.corrected_value,text,flags=re.I); low=text.casefold(); c.usage_count+=1
  def add(concept,value,typ="string",precision=Precision.exact,**kwargs):
   fact=Fact(id=str(uuid4()),concept=concept,value=value,normalized_value=value,data_type=typ,source_type=kwargs.pop("source_type","user"),status=kwargs.pop("status",Status.STATED),precision=precision,confidence=.9,**kwargs);out.append(fact);return fact
  if "vit vellore" in low or "vit valor" in low: add("college_name","VIT Vellore" if "vit vellore" in low else "VIT Valor")
  years={"first":1,"1st":1,"second":2,"2nd":2,"third":3,"3rd":3,"fourth":4,"4th":4}
  for k,v in years.items():
   if re.search(rf"\b{k}\s+year",low): add("year_of_study",v,"integer"); break
  if "student" in low: add("student_status","active")
  m=re.search(r"(?:income[^\d]{0,25})([\d,.]+)\s*(lakh|lac)?",low)
  if m:
   value=float(m.group(1).replace(",",""))*(100000 if m.group(2) else 1); value=int(value)
   precision=Precision.approximate if any(w in low for w in ["around","approximately","lagbhag","करीब"]) else Precision.exact
   period="annual" if any(w in low for w in ["annual","yearly","per year","a year"]) else "monthly" if any(w in low for w in ["monthly","per month","every month"]) else "weekly" if any(w in low for w in ["weekly","per week","every week"]) else "unknown"
   if period=="annual":add("annual_household_income",value,"currency",precision,unit="INR",period="annual",status=Status.UNCERTAIN if precision==Precision.approximate else Status.STATED)
   else:
    observation=add("household_income",value,"currency",precision,unit="INR",period=period,status=Status.UNCERTAIN if period=="unknown" or precision==Precision.approximate else Status.STATED)
    if period in {"monthly","weekly"}:
     multiplier=12 if period=="monthly" else 52
     add("annual_household_income",value*multiplier,"currency",precision,unit="INR",period="annual",status=Status.DERIVED,source_type="derived",source_id=observation.id,derived_from_fact_ids=[observation.id],derivation=f"{value} × {multiplier}")
  if question_context and not out:
   q_concept=question_context.get("concept")
   clean=text.strip()
   if q_concept=="date_of_birth":
    from datetime import datetime
    for pattern in ("%d %B %Y","%d %b %Y","%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%B %d, %Y","%B %d %Y","%b %d, %Y","%b %d %Y"):
     try:
      parsed=datetime.strptime(clean,pattern).date().isoformat()
      add("date_of_birth",parsed,"string"); break
     except ValueError: pass
   elif q_concept=="year_of_study":
    nums={"1":1,"2":2,"3":3,"4":4,"first":1,"1st":1,"second":2,"2nd":2,"third":3,"3rd":3,"fourth":4,"4th":4}
    for k,v in nums.items():
     if re.search(rf"\b{k}\b",low):
      add("year_of_study",v,"integer"); break
   elif q_concept=="state_of_domicile":
    if len(clean)<=40 and not re.search(r"\d",clean):
     add("state_of_domicile",clean.title(),"string")
   elif q_concept=="course_name":
    if len(clean)<=40:
     add("course_name","BTech" if clean.lower() in {"btech","b.tech"} else clean.upper() if clean.lower() in {"bsc","mtech","mba","bca","mca","ba","ma"} else clean.title(),"string")
   elif q_concept=="college_name":
    add("college_name","VIT Vellore" if "vit" in low else clean.title(),"string")
   elif q_concept=="category":
    add("category",clean.upper() if clean.lower() in {"general","obc","sc","st","ews"} else clean.title(),"string")
   elif q_concept=="full_name":
    if len(clean)<=50: add("full_name",clean.title(),"string")
   elif q_concept=="bank_account_holder_name":
    if len(clean)<=50: add("bank_account_holder_name",clean.title(),"string")
   elif q_concept in ("household_income","annual_household_income"):
    period="monthly" if any(w in low for w in ["month","mahine","mahina","monthly","per month"]) else "annual" if any(w in low for w in ["year","annual","saal","yearly","per year"]) else "unknown"
    precision=Precision.approximate if any(w in low for w in ["around","approximately","lagbhag","करीब"]) else Precision.exact
    m_num=re.search(r"(?:(?:₹|rs\.?|inr)\s*)?([\d,.]+)\s*(lakh|lac|k)?",low)
    if m_num and any(c.isdigit() for c in m_num.group(1)):
     val_num=float(m_num.group(1).replace(",",""))
     if m_num.group(2) in ("lakh","lac"): val_num*=100000
     elif m_num.group(2)=="k": val_num*=1000
     value=int(val_num) if val_num.is_integer() else val_num
     if period=="annual":add("annual_household_income",value,"currency",precision,unit="INR",period="annual",status=Status.UNCERTAIN if precision==Precision.approximate else Status.STATED)
     else:
      observation=add("household_income",value,"currency",precision,unit="INR",period=period,status=Status.UNCERTAIN if period=="unknown" or precision==Precision.approximate else Status.STATED)
      if period=="monthly":
       add("annual_household_income",value*12,"currency",precision,unit="INR",period="annual",status=Status.DERIVED,source_type="derived",source_id=observation.id,derived_from_fact_ids=[observation.id],derivation=f"{value} × 12")
    elif question_context.get("known_value") and period!="unknown":
     known=question_context.get("known_value")
     add("household_income",known,"currency",precision,period=period)
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
