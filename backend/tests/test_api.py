from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
def test_correction_and_shared_state():
 sid="api-shared";c.post(f"/api/demo/reset/{sid}?scenario=initial")
 r=c.post("/api/corrections",json={"session_id":sid,"heard_value":"VIT Valor","corrected_value":"VIT Vellore","concept":"college_name","language":"hi-en","verified":True});assert r.status_code==200
 a=c.post("/api/access-point/interact",json={"session_id":sid,"language":"hi-en","text":"I study at VIT Valor"});assert a.status_code==200
 web=c.get(f"/api/session/{sid}").json();assert any(f["value"]=="VIT Vellore" for f in web["facts"]);assert set(["ui_state","resolved","missing","uncertain","conflicts","tts_audio_url"]) <= set(a.json())
def test_upload_fixture():
 r=c.post("/api/documents/upload",data={"session_id":"upload","document_type":"income_certificate","fixture_mode":"true"});assert r.json()["status"]=="VERIFIED"
