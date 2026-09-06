import logging
import re
from uuid import uuid4
from .models import Fact,Precision,Session,Status
from .semantic import SemanticExtraction,SemanticOutcome
from .sarvam_service import SarvamError,SarvamService
from .services import RuleBasedSemanticExtractionService

log=logging.getLogger("katha.semantic")

class SemanticPipeline:
    def __init__(self,provider:SarvamService,fallback=None):
        self.provider=provider;self.fallback=fallback or RuleBasedSemanticExtractionService()
    def _context(self,session:Session,requirements,resolutions,language:str,question_context=None):
        return {"application_type":"student_scholarship","language_mode":language,"allowed_concepts":[*[r.concept for r in requirements],"household_income"],"known_facts":[{"concept":f.concept,"value":f.normalized_value if f.normalized_value is not None else f.value,"status":f.status,"source":f.source_type,"period":f.period} for f in session.facts],"unresolved_requirements":[r.concept for r,x in zip(requirements,resolutions) if x.status!=Status.VERIFIED],"verified_corrections":[{"heard":c.heard_value,"corrected":c.corrected_value,"concept":c.concept} for c in session.corrections if c.verified],"current_question":question_context}
    def _normalize(self,concept:str,value):
        if concept in {"annual_household_income","household_income"} and isinstance(value,str):
            cleaned=value.casefold().replace(",","")
            match=re.search(r"(\d+(?:\.\d+)?)",cleaned)
            if match:
                number=float(match.group(1));multiplier=10_000_000 if "crore" in cleaned else 100_000 if "lakh" in cleaned or "lac" in cleaned else 1
                return int(number*multiplier)
        if concept=="year_of_study":
            if isinstance(value,(int,float)) and 1<=value<=20:return int(value)
            if isinstance(value,str):
                words={"first":1,"1st":1,"one":1,"second":2,"2nd":2,"two":2,"third":3,"3rd":3,"three":3,"fourth":4,"4th":4,"four":4,"fifth":5,"5th":5,"five":5}
                low=value.casefold()
                for word,number in words.items():
                    if re.search(rf"\b{word}\b",low):return number
                match=re.search(r"\b(\d{1,2})\b",low)
                if match and 1<=int(match.group(1))<=20:return int(match.group(1))
        if concept=="student_status" and isinstance(value,str) and any(word in value.casefold() for word in ("student","year","enrolled","active","study","studying","pursuing","doing")):return "active"
        return value
    def _fallback(self,text:str,session:Session,source_type:str,reason:str,provider_extraction=None,semantic_success=False,question_context=None):
        try:normalized,facts=self.fallback.extract(text,session.corrections,question_context=question_context)
        except Exception as exc:
            log.warning("semantic_fallback_failed session=%s error=%s",session.id,type(exc).__name__)
            normalized,facts=text.strip(),[];reason=f"{reason};deterministic_fallback_failed"
        for fact in facts:
            if fact.source_type!="derived":fact.source_type=source_type
            fact.source_span=text;fact.interpretation_provider="deterministic-fallback"
        extraction=provider_extraction or SemanticExtraction(facts=[],uncertainties=[],unmapped_information=[],clarification_needed=not facts,clarification_reason=reason if not facts else None,language_detected=None)
        fallback_facts=[{"concept":fact.concept,"value":fact.value,"normalized_value":fact.normalized_value,"approximate":fact.precision==Precision.approximate,"interpretation_provider":"deterministic-fallback"} for fact in facts]
        log.info("semantic_ingestion session=%s provider=sarvam-105b semantic_success=%s fallback=true fact_count=%d reason=%s",session.id,str(semantic_success).lower(),len(facts),reason)
        return normalized,facts,[],SemanticOutcome(extraction=extraction,provider="sarvam-105b",semantic_success=semantic_success,candidate_fact_count=len(extraction.facts),fallback_used=True,fallback_reason=reason,fallback_facts=fallback_facts)
    def _source_supports(self,item):
        span=(item.source_span or "").casefold()
        if item.concept.value=="state_of_domicile" and any(word in span for word in ("live in","living in","currently","temporary","reside in")) and not any(word in span for word in ("original","permanent","home","domicile")):return False,"temporary_residence_is_not_domicile"
        return True,None
    def extract(self,text:str,session:Session,requirements,resolutions,language:str,source_type:str,question_context=None):
        context=self._context(session,requirements,resolutions,language,question_context)
        try:outcome=self.provider.extract_semantic_facts(text,context)
        except SarvamError as exc:
            return self._fallback(text,session,source_type,exc.code,question_context=question_context)
        applied=[];ignored=[];seen=set()
        for item in outcome.extraction.facts:
            if item.value is None or not item.explicit:
                ignored.append({"fact":item.model_dump(mode="json"),"reason":"not_explicit_or_empty"});continue
            supported,reason=self._source_supports(item)
            if not supported:
                ignored.append({"fact":item.model_dump(mode="json"),"reason":reason});continue
            provider_concept=item.concept.value
            concept="annual_household_income" if provider_concept=="household_income" and item.period=="annual" else "household_income" if provider_concept=="annual_household_income" and item.period!="annual" else provider_concept
            provider_value=item.value if concept=="student_status" else item.normalized_value if item.normalized_value is not None else item.value
            normalized=self._normalize(concept,provider_value)
            if concept=="date_of_birth" and isinstance(normalized,str):
                parsed=None
                from datetime import datetime
                for pattern in ("%d %B %Y","%d %b %Y","%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%B %d, %Y","%B %d %Y","%b %d, %Y","%b %d %Y"):
                    try:parsed=datetime.strptime(normalized.strip(),pattern).date().isoformat();break
                    except ValueError:pass
                if not parsed:
                    ignored.append({"fact":item.model_dump(mode="json"),"reason":"invalid_date"});continue
                normalized=parsed
            identity=(concept,str(normalized).casefold(),item.period,(item.source_span or "").strip().casefold())
            if identity in seen:
                ignored.append({"fact":item.model_dump(mode="json"),"reason":"duplicate_candidate"});continue
            seen.add(identity)
            precision=Precision.approximate if item.approximate else Precision.exact
            status=Status.UNCERTAIN if concept=="household_income" and item.period=="unknown" or item.approximate or (item.confidence is not None and item.confidence<.7) else Status.STATED
            data_type="boolean" if isinstance(normalized,bool) else "number" if isinstance(normalized,(int,float)) else "string"
            observation=Fact(id=str(uuid4()),concept=concept,value=item.value,normalized_value=normalized,data_type=data_type,source_type=source_type,status=status,confidence=item.confidence,precision=precision,unit=item.unit if concept in {"annual_household_income","household_income"} else None,period=item.period if concept in {"annual_household_income","household_income"} else None,source_span=item.source_span,explicit=item.explicit,interpretation_provider="sarvam-105b")
            applied.append(observation)
            if concept=="household_income" and item.period in {"monthly","weekly"} and isinstance(normalized,(int,float)):
                multiplier=12 if item.period=="monthly" else 52;annual=normalized*multiplier
                applied.append(Fact(id=str(uuid4()),concept="annual_household_income",value=int(annual) if float(annual).is_integer() else annual,normalized_value=int(annual) if float(annual).is_integer() else annual,data_type="number",source_type="derived",source_id=observation.id,status=Status.DERIVED,confidence=item.confidence,precision=precision,unit=item.unit or "INR",period="annual",source_span=item.source_span,explicit=True,interpretation_provider="sarvam-105b",derived_from_fact_ids=[observation.id],derivation=f"{normalized} × {multiplier}"))
        if question_context:
            expected=question_context.get("concept")
            compatible={"household_income","annual_household_income"} if expected in {"household_income","annual_household_income"} else {expected}
            if not any(f.concept in compatible for f in applied):
                try:
                    _,fb_facts=self.fallback.extract(text,session.corrections,question_context=question_context)
                    for fact in fb_facts:
                        if fact.concept in compatible:
                            if fact.source_type!="derived":fact.source_type=source_type
                            fact.source_span=text;fact.interpretation_provider="deterministic-fallback"
                            applied.append(fact);outcome.fallback_used=True;outcome.fallback_reason="contextual_concept_fallback"
                            outcome.fallback_facts.append({"concept":fact.concept,"value":fact.value,"normalized_value":fact.normalized_value,"approximate":fact.precision==Precision.approximate,"interpretation_provider":"deterministic-fallback"})
                except Exception as exc:
                    log.warning("contextual_fallback_failed session=%s error=%s",session.id,type(exc).__name__)
        log.info("semantic_ingestion session=%s provider=sarvam-105b fallback=%s fact_count=%d ignored_count=%d",session.id,str(outcome.fallback_used).lower(),len(applied),len(ignored))
        return text.strip(),applied,ignored,outcome
