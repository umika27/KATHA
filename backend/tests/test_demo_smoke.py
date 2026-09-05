from app.main import app
from fastapi.testclient import TestClient

client=TestClient(app)

def upload(sid,kind):
 return client.post("/api/documents/upload",data={"session_id":sid,"document_type":kind,"fixture_mode":"true"})

def test_complete_demo_journey_and_shared_state():
 sid="smoke-demo-second-pass"
 assert client.get("/api/health").json()["status"]=="ok"
 start=client.post(f"/api/demo/reset/{sid}?scenario=initial").json()
 assert start["preflight"]["status"]=="NOT_READY"
 typed=client.post("/api/interactions/text",json={"session_id":sid,"language":"hi-en","text":"Main VIT Vellore mein second year student hoon. Family income around 4 lakh hai."}).json()
 concepts={f["concept"] for f in typed["extracted_candidate_facts"]}
 assert {"college_name","year_of_study","student_status","annual_household_income"} <= concepts
 before=client.get(f"/api/session/{sid}").json()
 income=next(r for r in before["resolutions"] if r["requirement_id"]=="req-7")
 assert income["status"]=="UNCERTAIN"
 question_count=len(before["questions"])
 assert upload(sid,"income_certificate").json()["status"]=="VERIFIED"
 after_income=client.get(f"/api/session/{sid}").json()
 assert next(r for r in after_income["resolutions"] if r["requirement_id"]=="req-7")["status"]=="VERIFIED"
 assert len(after_income["questions"])<question_count
 assert after_income["preflight"]["status"]=="NOT_READY"
 upload(sid,"student_certificate");upload(sid,"domicile_certificate")
 required={r["concept"] for r in after_income["application"]["requirements"] if r["required"]}
 current=client.get(f"/api/session/{sid}").json()
 known={f["concept"] for f in current["facts"]}
 for concept in required-known:
  client.post("/api/answers",json={"session_id":sid,"concept":concept,"value":"Demo value"})
 final=client.get(f"/api/session/{sid}").json()
 assert final["preflight"]["status"]=="READY"
 access=client.post("/api/access-point/interact",json={"session_id":sid,"language":"hi-en","text":"Scholarship status"}).json()
 assert access["application_status"]=="READY"
