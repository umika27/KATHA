from .models import *

def _compatible(a,b):
    try: return abs(float(a)-float(b))/max(abs(float(b)),1) <= .10
    except (TypeError,ValueError): return str(a).casefold()==str(b).casefold()

def resolve(req: Requirement, session: Session):
    facts=[f for f in session.facts if f.concept==req.concept]
    ev=[e for e in session.evidence if e.type in req.accepted_evidence_types]
    if not facts: return RequirementResolution(requirement_id=req.id,status=Status.MISSING,explanation=f"{req.label} is missing.",blockers=["Required information is missing."] if req.required else [])
    verified=[f for f in facts if f.status==Status.VERIFIED or f.source_type=="document"]
    exact_user=[f for f in facts if f.source_type=="user" and f.precision==Precision.exact]
    if verified and exact_user and any(not _compatible(u.normalized_value or u.value,v.normalized_value or v.value) for u in exact_user for v in verified):
        return RequirementResolution(requirement_id=req.id,status=Status.CONFLICT,matched_fact_ids=[f.id for f in facts],evidence_ids=[e.id for e in ev],explanation="An exact stated value conflicts with verified evidence.",blockers=["Resolve the conflicting values."])
    if verified and (not req.proof_required or ev):
        return RequirementResolution(requirement_id=req.id,status=Status.VERIFIED,matched_fact_ids=[f.id for f in facts],evidence_ids=[e.id for e in ev],explanation="Verified by supporting evidence.")
    if any(f.precision==Precision.approximate for f in facts):
        return RequirementResolution(requirement_id=req.id,status=Status.UNCERTAIN,matched_fact_ids=[f.id for f in facts],explanation="The known value is approximate.",blockers=["An exact value is required."])
    return RequirementResolution(requirement_id=req.id,status=Status.STATED,matched_fact_ids=[f.id for f in facts],evidence_ids=[e.id for e in ev],explanation="Stated by the user; proof is still needed." if req.proof_required else "Stated by the user.",blockers=["Required proof is missing."] if req.proof_required else [])

def resolve_all(reqs,session): return [resolve(r,session) for r in reqs]
def questions(reqs,resolutions):
    by={r.id:r for r in reqs}; qs=[]
    prompts={"state_of_domicile":"Which state is your permanent domicile?","annual_household_income":"What is your exact annual household income?"}
    for x in resolutions:
      r=by[x.requirement_id]
      if not r.required or x.status==Status.VERIFIED or (x.status==Status.STATED and not r.proof_required): continue
      priority={Status.MISSING:1,Status.CONFLICT:2,Status.UNCERTAIN:3,Status.STATED:4}.get(x.status,5)
      q=prompts.get(r.concept, f"Please provide {r.label.lower()}." if x.status==Status.MISSING else f"Please provide proof for {r.label.lower()}.")
      qs.append(Question(concept=r.concept,question=q,priority=priority,reason=f"This scholarship requires {r.label.lower()} and it is {x.status.value.lower()}.",resolves_requirement_ids=[r.id]))
    return sorted(qs,key=lambda q:(q.priority,by[q.resolves_requirement_ids[0]].order))
def preflight(reqs,resolutions):
    counts={s:sum(x.status==s for x in resolutions) for s in Status}; blockers=[]
    for r,x in zip(reqs,resolutions):
      blocks=r.required and (x.status in (Status.MISSING,Status.UNCERTAIN,Status.CONFLICT) or (x.status==Status.STATED and r.proof_required))
      if blocks: blockers.append({"concept":r.concept,"message":x.blockers[0] if x.blockers else x.explanation})
    resolved=sum(not (r.required and (x.status in (Status.MISSING,Status.UNCERTAIN,Status.CONFLICT) or (x.status==Status.STATED and r.proof_required))) for r,x in zip(reqs,resolutions))
    return {"status":"READY" if not blockers else "NOT_READY","resolved":resolved,"missing":counts[Status.MISSING],"uncertain":counts[Status.UNCERTAIN],"conflicts":counts[Status.CONFLICT],"blockers":blockers,"warnings":[]}
