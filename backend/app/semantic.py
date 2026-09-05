from enum import Enum
from typing import Union
from pydantic import BaseModel, ConfigDict, Field
from .concepts import REGISTRY

CONCEPT_DESCRIPTIONS={
    "full_name":"Applicant's full legal or commonly used name.",
    "date_of_birth":"Applicant's date of birth; preserve the stated date without guessing missing parts.",
    "college_name":"Name of the college, university, or institution where the applicant studies.",
    "course_name":"Current course, degree, or programme of study.",
    "year_of_study":"Current academic year normalized to an integer, for example second year becomes 2.",
    "student_status":"Current student enrollment only when supported by words such as student, studying, enrolled, pursuing, or doing a course; mentioning a college alone is insufficient.",
    "household_income":"A stated household/family/parents' combined income amount whose period is monthly, weekly, or unknown. Use this observation concept instead of annual_household_income whenever the period is not explicitly annual.",
    "annual_household_income":"Combined annual household or family income. Use only when annual/yearly/per-year meaning is explicit.",
    "state_of_domicile":"Permanent, original, or home domicile state only. Never map a place where the applicant currently lives temporarily for college or work.",
    "category":"Applicant's explicitly stated social or reservation category.",
    "bank_account_holder_name":"Name of the holder of the bank account intended for the application.",
    "income_certificate":"Whether the applicant explicitly says an income certificate exists; this is never document verification.",
    "student_certificate":"Whether the applicant explicitly says a student or bonafide certificate exists; this is never document verification.",
    "domicile_certificate":"Whether the applicant explicitly says a domicile certificate exists; this is never document verification.",
}

CanonicalConcept=Enum("CanonicalConcept",{name:name for name in REGISTRY},type=str)
Scalar=Union[str,int,float,bool,None]

class ExtractedFact(BaseModel):
    model_config=ConfigDict(extra="forbid")
    concept: CanonicalConcept=Field(description="One canonical concept only. Ontology: "+" ".join(f"{key}: {value}" for key,value in CONCEPT_DESCRIPTIONS.items()))
    value: Scalar=Field(description="Value as expressed or faithfully translated from the user statement.")
    normalized_value: Scalar=Field(description="Safely normalized canonical value; never derive unsupported consequential information.")
    unit: str|None=Field(description="Real currency or measurement unit such as INR, otherwise null.")
    period: str=Field(description="Income period: annual, monthly, weekly, or unknown. Use unknown when no period is stated. Use unknown for non-income facts.",pattern="^(annual|monthly|weekly|unknown)$")
    approximate: bool=Field(description="True for around, roughly, maybe, approximately, think, or otherwise uncertain values.")
    confidence: float|None=Field(ge=0,le=1)
    source_span: str|None=Field(description="Shortest exact span of user text supporting this candidate fact.")
    explicit: bool=Field(description="True only when the fact is explicitly stated or safely normalized from the statement.")

class SemanticExtraction(BaseModel):
    model_config=ConfigDict(extra="forbid")
    facts: list[ExtractedFact]
    uncertainties: list[str]
    unmapped_information: list[str]
    clarification_needed: bool
    clarification_reason: str|None
    language_detected: str|None

class SemanticOutcome(BaseModel):
    extraction: SemanticExtraction
    provider: str
    semantic_success: bool=True
    candidate_fact_count: int=0
    fallback_used: bool=False
    fallback_reason: str|None=None
    fallback_facts: list[dict]=Field(default_factory=list)
