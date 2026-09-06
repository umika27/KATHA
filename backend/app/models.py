from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, Field

def now(): return datetime.now(timezone.utc)

class Status(str, Enum):
    VERIFIED="VERIFIED"; STATED="STATED"; UNCERTAIN="UNCERTAIN"; DERIVED="DERIVED"; MISSING="MISSING"; CONFLICT="CONFLICT"
class Precision(str, Enum): exact="exact"; approximate="approximate"
class Fact(BaseModel):
    id: str; concept: str; value: Any; normalized_value: Any|None=None; data_type: str="string"; source_type: str="user"; source_id: str|None=None; status: Status=Status.STATED; confidence: float|None=None; precision: Precision=Precision.exact; unit: str|None=None; period: str|None=None; source_span: str|None=None; explicit: bool=True; interpretation_provider: str|None=None; derived_from_fact_ids: list[str]=Field(default_factory=list); derivation: str|None=None; created_at: datetime=Field(default_factory=now); updated_at: datetime=Field(default_factory=now)
class Evidence(BaseModel):
    id: str; type: str; filename: str; source: str="upload"; extracted_facts: list[str]=Field(default_factory=list); verification_state: str="VERIFIED"; uploaded_at: datetime=Field(default_factory=now); issue_date: str|None=None; expiry_date: str|None=None; financial_year: str|None=None; is_expired: bool=False; source_page: int|None=None; source_text: str|None=None; provider: str|None=None; confidence: float|None=None; document_id: str|None=None; raw_text: str|None=None
class DocumentCandidateField(BaseModel):
    id: str=Field(default_factory=lambda: str(uuid4())); concept: str; label: str; value: Any; normalized_value: Any=None; data_type: str="string"; confidence: float|None=None; page_number: int|None=None; source_span: str|None=None; period: str|None=None; unit: str|None=None; financial_year: str|None=None; issue_date: str|None=None; expiry_date: str|None=None; is_expired: bool=False; status: str="PENDING"
class DocumentReviewCandidate(BaseModel):
    document_id: str; document_type: str; filename: str; provider: str; raw_text: str|None=None; fields: list[DocumentCandidateField]=Field(default_factory=list); created_at: datetime=Field(default_factory=now)
class Requirement(BaseModel):
    id: str; concept: str; label: str; description: str=""; required: bool=True; proof_required: bool=False; accepted_evidence_types: list[str]=[]; validation_rule: str|None=None; order: int
class RequirementResolution(BaseModel):
    requirement_id: str; status: Status; matched_fact_ids: list[str]=[]; evidence_ids: list[str]=[]; explanation: str; blockers: list[str]=[]
class Question(BaseModel):
    concept: str; question: str; priority: int; reason: str; resolves_requirement_ids: list[str]; type: str="requirement"; known_value: Any|None=None; missing_qualifier: str|None=None; fact_id: str|None=None; options: list[str]=Field(default_factory=list); localized_questions: dict[str, str]=Field(default_factory=dict); evidence_request: dict[str, Any]|None=None
class CorrectionMemory(BaseModel):
    heard_value: str; corrected_value: str; concept: str; language: str; verified: bool=False; usage_count: int=1; created_at: datetime=Field(default_factory=now)
class Application(BaseModel):
    id: str; application_type: str="student_scholarship"; title: str="KATHA Educational Support Scholarship"; requirements: list[Requirement]; readiness: str="NOT_READY"; resolved_count: int=0; missing_count: int=0; uncertain_count: int=0; conflict_count: int=0
class Session(BaseModel):
    id: str; facts: list[Fact]=Field(default_factory=list); evidence: list[Evidence]=Field(default_factory=list); corrections: list[CorrectionMemory]=Field(default_factory=list); pending_documents: list[DocumentReviewCandidate]=Field(default_factory=list)
class AcceptCandidateIn(BaseModel):
    application_id: str; document_id: str; field_ids: list[str]|None=None; overrides: dict[str, Any]=Field(default_factory=dict)
class IgnoreCandidateIn(BaseModel):
    application_id: str; document_id: str; field_ids: list[str]|None=None
class ConflictResolveIn(BaseModel):
    application_id: str; concept: str; resolution_choice: str; custom_value: Any|None=None; evidence_id: str|None=None
