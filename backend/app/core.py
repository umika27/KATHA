from .models import *
from .concepts import QUESTION_TEXTS
from .document_ai import check_if_expired

def _compatible(a,b):
    try: return float(a) == float(b)
    except (TypeError,ValueError): return str(a).casefold()==str(b).casefold()

def resolve(req: Requirement, session: Session):
    facts=[f for f in session.facts if f.concept==req.concept]
    ev=[e for e in session.evidence if e.type in req.accepted_evidence_types]

    for e in ev:
        if e.expiry_date and check_if_expired(e.expiry_date):
            e.is_expired = True
            e.verification_state = "EXPIRED"
        elif not e.expiry_date:
            e.is_expired = False

    valid_ev=[e for e in ev if not e.is_expired]
    has_expired_ev=bool(ev and not valid_ev)

    if not facts:
        return RequirementResolution(requirement_id=req.id,status=Status.MISSING,explanation=f"{req.label} is missing.",blockers=["Required information is missing."] if req.required else [])

    verified=[f for f in facts if (f.status==Status.VERIFIED or f.source_type=="document") and (not f.source_id or any(e.id==f.source_id for e in valid_ev))]
    exact_user=[f for f in facts if f.source_type in {"user","user_statement","speech_transcript","questionnaire_typed","questionnaire_speech","user_correction"} and f.precision==Precision.exact and not (f.derivation and "superseded" in f.derivation)]

    if verified and exact_user and any(not _compatible(u.normalized_value or u.value,v.normalized_value or v.value) for u in exact_user for v in verified):
        return RequirementResolution(requirement_id=req.id,status=Status.CONFLICT,matched_fact_ids=[f.id for f in facts],evidence_ids=[e.id for e in ev],explanation="An exact stated value conflicts with verified evidence.",blockers=["Resolve the conflicting values."])

    if has_expired_ev and req.proof_required and not valid_ev:
        return RequirementResolution(requirement_id=req.id,status=Status.UNCERTAIN,matched_fact_ids=[f.id for f in facts],evidence_ids=[e.id for e in ev],explanation=f"Provided {ev[0].type.replace('_',' ')} has expired.",blockers=["Provide unexpired proof."])

    if verified and (not req.proof_required or valid_ev):
        return RequirementResolution(requirement_id=req.id,status=Status.VERIFIED,matched_fact_ids=[f.id for f in facts],evidence_ids=[e.id for e in valid_ev],explanation="Verified by supporting evidence.")

    if any(f.precision==Precision.approximate for f in facts):
        return RequirementResolution(requirement_id=req.id,status=Status.UNCERTAIN,matched_fact_ids=[f.id for f in facts],explanation="The known value is approximate.",blockers=["An exact value is required."])

    return RequirementResolution(requirement_id=req.id,status=Status.STATED,matched_fact_ids=[f.id for f in facts],evidence_ids=[e.id for e in ev],explanation="Stated by the user; proof is still needed." if req.proof_required else "Stated by the user.",blockers=["Required proof is missing."] if req.proof_required else [])

def resolve_all(reqs,session): return [resolve(r,session) for r in reqs]
def questions(reqs,resolutions,session=None):
    by={r.id:r for r in reqs}; qs=[]
    income_resolution=next((x for x in resolutions if x.requirement_id=="req-7"),None)
    observations=[f for f in session.facts if f.concept=="household_income" and f.period=="unknown"] if session and income_resolution and income_resolution.status!=Status.VERIFIED else []
    if observations:
     fact=observations[-1];amount=f"{float(fact.normalized_value):,.0f}" if isinstance(fact.normalized_value,(int,float)) else str(fact.normalized_value)
     loc_income={"hi-en":f"Yeh ₹{amount} aapke ghar ki income per month hai ya per year?","te-en":f"Ee ₹{amount} mee household income per month aa leka per year aa?","bn-en":f"Ei ₹{amount} ki apanar monthly income naki yearly income?"}
     qs.append(Question(concept="household_income",question=f"Is ₹{amount} your household income per month or per year?",priority=0,reason="The household income amount is known, but its period is not specified.",resolves_requirement_ids=["req-7"],type="clarification",known_value=fact.normalized_value,missing_qualifier="period",fact_id=fact.id,options=["monthly","annual","edit"],localized_questions=loc_income))
    prompts={"state_of_domicile":"Which state is your permanent domicile?","annual_household_income":"What is your exact annual household income?"}
    for x in resolutions:
      r=by[x.requirement_id]
      if r.concept=="annual_household_income" and observations:continue
      if not r.required or x.status==Status.VERIFIED or (x.status==Status.STATED and not r.proof_required): continue
      priority={Status.MISSING:1,Status.CONFLICT:2,Status.UNCERTAIN:3,Status.STATED:4}.get(x.status,5)
      q=prompts.get(r.concept, f"Please provide {r.label.lower()}." if x.status==Status.MISSING else f"Please provide proof for {r.label.lower()}.")
      loc={lang:texts[r.concept] for lang,texts in QUESTION_TEXTS.items() if r.concept in texts}
      evidence_req=None
      if r.proof_required and r.accepted_evidence_types and x.status in (Status.STATED,Status.UNCERTAIN,Status.MISSING):
       doc_t=r.accepted_evidence_types[0]
       evidence_req={"document_type":doc_t,"label":r.label,"message":f"To prove {r.label.lower()}, KATHA needs your {doc_t.replace('_',' ')}."}
      qs.append(Question(concept=r.concept,question=q,priority=priority,reason=f"This scholarship requires {r.label.lower()} and it is {x.status.value.lower()}.",resolves_requirement_ids=[r.id],localized_questions=loc,evidence_request=evidence_req))
    return sorted(qs,key=lambda q:(q.priority,by[q.resolves_requirement_ids[0]].order))
def preflight(reqs,resolutions):
    counts={s:sum(x.status==s for x in resolutions) for s in Status}; blockers=[]
    for r,x in zip(reqs,resolutions):
      blocks=r.required and (x.status in (Status.MISSING,Status.UNCERTAIN,Status.CONFLICT) or (x.status==Status.STATED and r.proof_required))
      if blocks: blockers.append({"concept":r.concept,"message":x.blockers[0] if x.blockers else x.explanation})
    resolved=sum(not (r.required and (x.status in (Status.MISSING,Status.UNCERTAIN,Status.CONFLICT) or (x.status==Status.STATED and r.proof_required))) for r,x in zip(reqs,resolutions))
    return {"status":"READY" if not blockers else "NOT_READY","resolved":resolved,"missing":counts[Status.MISSING],"uncertain":counts[Status.UNCERTAIN],"conflicts":counts[Status.CONFLICT],"blockers":blockers,"warnings":[]}
