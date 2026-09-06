import base64
import json
import logging
import time
from io import BytesIO
from typing import Any
from .config import Settings,settings
from .semantic import ExtractedFact,SemanticExtraction,SemanticOutcome

log=logging.getLogger("katha.sarvam")

class SarvamError(RuntimeError):
    def __init__(self,code:str,message:str,retryable:bool=False): super().__init__(message);self.code=code;self.retryable=retryable

class SarvamService:
    def __init__(self,config:Settings=settings,client=None):
        self.config=config
        self.last_semantic_diagnostics={}
        if client is not None:self.client=client
        elif self.configured:
            from sarvamai import SarvamAI
            self.client=SarvamAI(api_subscription_key=config.sarvam_api_key,timeout=config.sarvam_timeout_seconds)
        else:self.client=None
    @property
    def configured(self):return bool(self.config.sarvam_enabled and self.config.sarvam_api_key)
    @property
    def speech_enabled(self):return self.configured
    @property
    def semantic_enabled(self):return bool(self.configured and self.config.sarvam_semantic_enabled)
    @property
    def tts_enabled(self):return bool(self.configured and self.config.sarvam_tts_enabled)
    @property
    def document_ai_enabled(self):return bool(self.configured and self.config.sarvam_doc_ai_enabled)
    def _error(self,exc:Exception,operation:str):
        kind=type(exc).__name__;message=str(exc).casefold()
        code="authentication_failed" if kind in {"UnauthorizedError","ForbiddenError"} or any(x in message for x in ("401","403","invalid_api_key")) else "insufficient_credits" if kind=="PaymentRequiredError" or "402" in message else "unsupported_audio" if operation=="stt" and kind in {"BadRequestError","UnprocessableEntityError","ContentTooLargeError"} else "unsupported_document" if operation=="doc_ai" and kind in {"BadRequestError","UnprocessableEntityError","ContentTooLargeError"} else "rate_limited" if kind=="TooManyRequestsError" else "timeout" if "timeout" in message else "provider_unavailable"
        safe={"authentication_failed":"Sarvam authentication failed.","insufficient_credits":"Sarvam credits are unavailable.","unsupported_audio":"Sarvam could not read this audio format.","unsupported_document":"Sarvam could not read this document format.","rate_limited":"Sarvam is rate-limiting requests.","timeout":"Sarvam timed out.","provider_unavailable":"Sarvam is temporarily unavailable."}[code]
        return SarvamError(code,safe,code in {"rate_limited","timeout","provider_unavailable"})
    def _run(self,operation:str,model:str,fn):
        started=time.perf_counter()
        try:
            result=fn();log.info("sarvam_operation session=redacted operation=%s model=%s latency_ms=%d success=true",operation,model,int((time.perf_counter()-started)*1000));return result
        except SarvamError:raise
        except Exception as exc:
            log.warning("sarvam_operation session=redacted operation=%s model=%s latency_ms=%d success=false error=%s",operation,model,int((time.perf_counter()-started)*1000),type(exc).__name__);raise self._error(exc,operation) from exc
    def transcribe_audio(self,content:bytes,filename:str,content_type:str|None=None):
        if not self.speech_enabled:raise SarvamError("not_configured","Live speech is not configured.")
        if not content:raise SarvamError("unsupported_audio","The recording is empty.")
        allowed=("audio/", "video/webm", "application/octet-stream")
        if content_type and not content_type.startswith(allowed):raise SarvamError("unsupported_audio","Unsupported audio content type.")
        def call():
            stream=BytesIO(content);stream.name=filename
            response=self.client.speech_to_text.transcribe(file=stream,model=self.config.sarvam_stt_model,mode=self.config.sarvam_stt_mode,language_code="unknown")
            transcript=(getattr(response,"transcript",None) or "").strip()
            if not transcript:raise SarvamError("no_speech","No speech was detected.",True)
            return transcript,getattr(response,"language_code",None)
        return self._run("stt",self.config.sarvam_stt_model,call)
    def _semantic_prompt(self,context:dict[str,Any]):
        return """You are KATHA's semantic interpretation engine.
Extract every explicitly stated or safely normalized piece of information that maps to a provided canonical concept. User statements are candidate facts even when evidence has not been supplied. Extract all supported facts from multi-fact sentences. Emit only present facts, never null placeholder facts, and normally emit at most one fact per concept.

When current_question is present in the application context, interpret a short answer against current_question.concept and current_question.question. For example, a date answering a date_of_birth question maps to date_of_birth, a state name answering state_of_domicile maps to state_of_domicile, a course name answering course_name maps to course_name, and a person or account holder name answering full_name or bank_account_holder_name maps to full_name or bank_account_holder_name respectively. Do not require the short answer to repeat the field label. Still reject answers that cannot safely satisfy the intended concept.

Do not answer conversationally. Do not decide eligibility, verification, readiness, or proof satisfaction. Do not fabricate or silently infer consequential information. Return facts=[] only when no provided canonical concept is present.

Income period is a first-class qualifier. Extract a household/family income amount even when its period is absent. Use household_income with period=unknown when no annual/monthly/weekly period is explicit; never infer period from magnitude. Use household_income with period=monthly or weekly when explicit. Use annual_household_income only for explicitly annual/yearly/per-year income, with period=annual. Normalize Indian number constructions across supported languages, including lakh/crore and half-number forms such as 'saade chaar' meaning 4.5. The deterministic application layer performs annualization after extraction; do not annualize monthly or weekly values here. For non-income facts set period=unknown.

Normalize an explicitly annual amount to numeric INR: 'around four lakh per year' means normalized_value=400000, period=annual, and approximate=true. Normalize study year to an integer: 'second year' means 2. Preserve around, roughly, maybe, approximately, 'I think', 'not exactly known', and similar uncertainty with approximate=true. Uncertainty is not a reason to omit an otherwise supported candidate fact. Do not add multiple earnings unless explicitly represented as a combined household amount. Use unit only for a real currency or measurement unit, otherwise null. Use the shortest supporting source_span.

Permanent domicile and a temporary current residence are different. "Originally from X" or "permanent home is X" supports state_of_domicile=X; "currently live in Y for study/work" does not support domicile=Y. Never convert a temporary study/work location into domicile. A reference to a college alone does not establish student_status; require explicit student, studying, enrolled, pursuing, or course language.

CANONICAL ONTOLOGY AND APPLICATION CONTEXT:
"""+json.dumps(context,ensure_ascii=False,default=str)
    def _parse_semantic_content(self,content:str):
        recovered=False
        try:payload=json.loads(content)
        except Exception as exc:
            marker=content.find('"facts"');array_start=content.find("[",marker) if marker>=0 else -1
            try:
                raw_facts,end=json.JSONDecoder().raw_decode(content[array_start:])
                if not isinstance(raw_facts,list):raise ValueError("facts is not a list")
                payload={"facts":raw_facts,"uncertainties":[],"unmapped_information":["Provider response envelope was truncated after a complete facts array."],"clarification_needed":not raw_facts,"clarification_reason":"Please clarify the information so KATHA can map it safely." if not raw_facts else None,"language_detected":None};recovered=True
            except Exception:raise SarvamError("malformed_response","Sarvam returned invalid JSON.",True) from exc
        if not isinstance(payload,dict):raise SarvamError("malformed_response","Sarvam returned a non-object semantic result.",True)
        raw_facts=payload.get("facts")
        if not isinstance(raw_facts,list):raise SarvamError("malformed_response","Sarvam semantic facts were not an array.",True)
        try:envelope=SemanticExtraction.model_validate({**payload,"facts":[]})
        except Exception as exc:raise SarvamError("malformed_response","Sarvam returned an invalid semantic envelope.",True) from exc
        valid=[];invalid=[];empty=[]
        for index,item in enumerate(raw_facts):
            try:
                fact=ExtractedFact.model_validate(item)
                if fact.explicit and fact.value is not None:valid.append(fact)
                else:empty.append(index)
            except Exception as exc:invalid.append({"index":index,"error":type(exc).__name__})
        extraction=envelope.model_copy(update={"facts":valid,"unmapped_information":[*envelope.unmapped_information,*[f"Rejected malformed candidate fact at index {item['index']}" for item in invalid]]})
        return payload,extraction,invalid,empty,recovered
    def extract_semantic_facts(self,text:str,context:dict[str,Any]):
        if not self.semantic_enabled:raise SarvamError("not_configured","Sarvam semantic extraction is not configured.")
        schema=SemanticExtraction.model_json_schema()
        response_format={"type":"json_schema","json_schema":{"name":"katha_semantic_extraction","description":"Explicit canonical candidate facts only","strict":True,"schema":schema}}
        messages=[{"role":"system","content":self._semantic_prompt(context)},{"role":"user","content":text}]
        self.last_semantic_diagnostics={"called":False,"model":self.config.sarvam_chat_model,"structured_output_requested":True,"response_format":response_format,"json_schema":schema,"semantic_input_text_length":len(text),"semantic_input_text_preview":text[:160],"messages":[{"role":message["role"],"content":message["content"] if message["role"]=="user" else "<system prompt omitted; schema and context supplied>"} for message in messages]}
        if self.config.environment=="development":log.info("semantic_request model=%s structured_output_requested=true semantic_input_text_length=%d semantic_input_text_preview=%r",self.config.sarvam_chat_model,len(text),text[:160])
        def call():
            self.last_semantic_diagnostics["called"]=True
            response=self.client.chat.completions(model=self.config.sarvam_chat_model,messages=messages,temperature=.1,reasoning_effort=None,max_tokens=2000,request_options={"additional_body_parameters":{"response_format":response_format}})
            self.last_semantic_diagnostics["sdk_call_successful"]=True;self.last_semantic_diagnostics["completion_object_type"]=f"{type(response).__module__}.{type(response).__name__}"
            self.last_semantic_diagnostics["response_tree"]=response.model_dump(mode="json") if hasattr(response,"model_dump") else repr(response)
            choice=response.choices[0] if getattr(response,"choices",None) else None
            content=choice.message.content if choice else None
            self.last_semantic_diagnostics["finish_reason"]=getattr(choice,"finish_reason",None)
            self.last_semantic_diagnostics["raw_message_content"]=content
            if not content:raise SarvamError("malformed_response","Sarvam returned no semantic result.",True)
            payload,extraction,invalid,empty,recovered=self._parse_semantic_content(content)
            validation="recovered_complete_facts_from_truncated_envelope" if recovered else "valid" if not invalid else "partially_valid"
            self.last_semantic_diagnostics.update({"parsed_json":payload,"pydantic_validation":validation,"truncated_envelope_recovered":recovered,"invalid_candidate_facts":invalid,"omitted_empty_candidate_indexes":empty,"semantic_facts_before_ingestion":[fact.model_dump(mode="json") for fact in extraction.facts]})
            return extraction
        last=None
        for attempt in range(2):
            try:
                extraction=self._run("semantic",self.config.sarvam_chat_model,call)
                return SemanticOutcome(extraction=extraction,provider="sarvam-105b",semantic_success=True,candidate_fact_count=len(extraction.facts))
            except SarvamError as exc:
                last=exc;self.last_semantic_diagnostics.update({"semantic_success":False,"error_code":exc.code,"error_message":str(exc),"attempt":attempt+1})
                if exc.code!="malformed_response" or attempt:raise
        raise last
    def generate_response(self,state:dict[str,Any],fallback:str,language_mode:str):
        if not self.semantic_enabled:return fallback
        def call():
            response=self.client.chat.completions(model=self.config.sarvam_chat_model,messages=[{"role":"system","content":"Phrase KATHA's deterministic result concisely and warmly. Do not add facts, choose requirements, claim verification, eligibility, or submission."},{"role":"user","content":json.dumps({"language_mode":language_mode,"deterministic_state":state,"fallback":fallback},default=str)}],reasoning_effort=None,max_tokens=180)
            return (response.choices[0].message.content or "").strip() or fallback
        try:return self._run("response",self.config.sarvam_chat_model,call)
        except SarvamError:return fallback
    def synthesize_speech(self,text:str,language_code:str):
        if not self.tts_enabled:raise SarvamError("not_configured","Text-to-speech is not configured.")
        def call():
            response=self.client.text_to_speech.convert(text=text[:2500],language_code=language_code,model=self.config.sarvam_tts_model,speaker="shubh",output_audio_codec="wav")
            audios=getattr(response,"audios",None) or []
            if not audios:raise SarvamError("malformed_response","Sarvam returned no audio.")
            return base64.b64decode(audios[0])
        return self._run("tts",self.config.sarvam_tts_model,call)
    def extract_document(self, content: bytes, filename: str, content_type: str, document_type: str):
        if not self.document_ai_enabled:raise SarvamError("not_configured","Sarvam Document AI is disabled.")
        from .document_ai import SarvamDocumentAIService
        doc_service=SarvamDocumentAIService(self.config,self.client)
        try:
            return doc_service.extract_document(content,filename,content_type,document_type)
        except Exception as exc:
            raise self._error(exc,"doc_ai") from exc
