from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

def now(): return datetime.now(timezone.utc)

class Status(str, Enum):
    VERIFIED="VERIFIED"; STATED="STATED"; UNCERTAIN="UNCERTAIN"; MISSING="MISSING"; CONFLICT="CONFLICT"
class Precision(str, Enum): exact="exact"; approximate="approximate"
class Fact(BaseModel):
    id: str; concept: str; value: Any; normalized_value: Any|None=None; data_type: str="string"; source_type: str="user"; source_id: str|None=None; status: Status=Status.STATED; confidence: float|None=None; precision: Precision=Precision.exact; created_at: datetime=Field(default_factory=now); updated_at: datetime=Field(default_factory=now)
class Evidence(BaseModel):
    id: str; type: str; filename: str; source: str; extracted_facts: list[str]=[]; verification_state: str="VERIFIED"; uploaded_at: datetime=Field(default_factory=now)
class Requirement(BaseModel):
    id: str; concept: str; label: str; description: str=""; required: bool=True; proof_required: bool=False; accepted_evidence_types: list[str]=[]; validation_rule: str|None=None; order: int
class RequirementResolution(BaseModel):
    requirement_id: str; status: Status; matched_fact_ids: list[str]=[]; evidence_ids: list[str]=[]; explanation: str; blockers: list[str]=[]
class Question(BaseModel):
    concept: str; question: str; priority: int; reason: str; resolves_requirement_ids: list[str]
class CorrectionMemory(BaseModel):
    heard_value: str; corrected_value: str; concept: str; language: str; verified: bool=False; usage_count: int=1
class Application(BaseModel):
    id: str; application_type: str="student_scholarship"; title: str="KATHA Educational Support Scholarship"; requirements: list[Requirement]; readiness: str="NOT_READY"; resolved_count: int=0; missing_count: int=0; uncertain_count: int=0; conflict_count: int=0
class Session(BaseModel):
    id: str; facts: list[Fact]=[]; evidence: list[Evidence]=[]; corrections: list[CorrectionMemory]=[]
