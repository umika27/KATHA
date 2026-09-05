from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.config import Settings
from app.services import SarvamSpeechService,SpeechServiceError
from app import main

class FakeClient:
 def __init__(self,transcript="Main VIT Vellore mein second year student hoon"):
  self.speech_to_text=SimpleNamespace(transcribe=lambda **_:SimpleNamespace(transcript=transcript,language_code="hi-IN"))
  self.text_to_speech=SimpleNamespace(convert=lambda **_:SimpleNamespace(audios=["UklGRg=="]))

def test_sarvam_adapter_without_network():
 service=SarvamSpeechService(Settings(sarvam_api_key="test",sarvam_enabled=True,sarvam_tts_enabled=True),FakeClient())
 assert service.transcribe(b"audio","demo.webm").text.startswith("Main VIT")
 assert service.synthesize("hello","hi-IN").startswith(b"RIFF")

def test_speech_endpoint_uses_same_pipeline(monkeypatch):
 monkeypatch.setattr(main,"speech",SarvamSpeechService(Settings(sarvam_api_key="test",sarvam_enabled=True,sarvam_tts_enabled=True),FakeClient()))
 r=TestClient(main.app).post("/api/interactions/speech",data={"session_id":"speech-shared","language":"hi-en"},files={"file":("voice.webm",b"audio","audio/webm")})
 assert r.status_code==200
 assert {"college_name","year_of_study","student_status"}<={f["concept"] for f in r.json()["candidate_facts"]}
 assert any(f["concept"]=="college_name" for f in TestClient(main.app).get("/api/session/speech-shared").json()["facts"])

def test_tts_failure_preserves_text_and_application_state(monkeypatch):
 service=SarvamSpeechService(Settings(sarvam_api_key="test",sarvam_enabled=True,sarvam_tts_enabled=True),FakeClient())
 monkeypatch.setattr(service,"synthesize",lambda *_:(_ for _ in ()).throw(SpeechServiceError("provider_unavailable","TTS unavailable",True)))
 monkeypatch.setattr(main,"speech",service)
 r=TestClient(main.app).post("/api/interactions/speech",data={"session_id":"speech-tts-fail","language":"hi-en"},files={"file":("voice.webm",b"audio","audio/webm")})
 body=r.json()
 assert r.status_code==200 and body["response_text"] and body["tts_error"]["code"]=="provider_unavailable"
 assert body["application"]["facts"]
