from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def create_application():
 response=client.post("/api/applications")
 assert response.status_code==201
 return response.json()

def upload_fixture(application_id,document_type):
 return client.post("/api/documents/upload",data={"session_id":application_id,"document_type":document_type,"fixture_mode":"true"})

def test_application_lifecycle_isolates_evidence_facts_preflight_and_reset():
 application_a=create_application();a_id=application_a["application_id"]
 assert application_a["application"]["id"]==a_id
 assert application_a["application"]["requirements"]
 assert application_a["facts"]==[] and application_a["evidence"]==[]
 assert application_a["preflight"]["status"]=="NOT_READY"

 assert upload_fixture(a_id,"income_certificate").status_code==200
 client.post("/api/interactions/text",json={"session_id":a_id,"language":"hi-en","text":"I study at VIT Vellore"})
 client.post("/api/answers",json={"session_id":a_id,"concept":"full_name","value":"Application A Student"})
 client.post("/api/corrections",json={"session_id":a_id,"heard_value":"VIT Valor","corrected_value":"VIT Vellore","concept":"college_name","language":"hi-en","verified":True})
 reloaded_a=client.get(f"/api/applications/{a_id}").json()
 assert {e["type"] for e in reloaded_a["evidence"]}=={"income_certificate"}
 assert any(f["source_type"]=="document" and f["status"]=="VERIFIED" for f in reloaded_a["facts"])
 assert any(f["source_type"]=="user_statement" for f in reloaded_a["facts"])
 assert reloaded_a["corrections"]

 application_b=create_application();b_id=application_b["application_id"]
 assert b_id!=a_id and application_b["facts"]==[] and application_b["evidence"]==[]
 assert upload_fixture(b_id,"student_certificate").status_code==200
 reloaded_b=client.get(f"/api/applications/{b_id}").json()
 assert {e["type"] for e in reloaded_b["evidence"]}=={"student_certificate"}
 assert reloaded_a["preflight"]!=reloaded_b["preflight"]

 a_after_b=client.get(f"/api/applications/{a_id}").json()
 assert {e["type"] for e in a_after_b["evidence"]}=={"income_certificate"}
 assert all(e["type"]!="student_certificate" for e in a_after_b["evidence"])

 reset_a=client.post(f"/api/applications/{a_id}/reset").json()
 assert reset_a["facts"]==[] and reset_a["evidence"]==[] and reset_a["corrections"]==[]
 assert reset_a["application"]["requirements"] and reset_a["preflight"]["status"]=="NOT_READY"
 b_after_reset=client.get(f"/api/applications/{b_id}").json()
 assert b_after_reset["facts"]==reloaded_b["facts"] and b_after_reset["evidence"]==reloaded_b["evidence"]

def test_unknown_application_lifecycle_routes_do_not_create_records():
 missing=str(uuid4())
 assert client.get(f"/api/applications/{missing}").status_code==404
 assert client.post(f"/api/applications/{missing}/reset").status_code==404
