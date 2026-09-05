from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import Status, Precision, Session
from app.services import SarvamSpeechService, SpeechServiceError
from app.config import Settings

client = TestClient(main.app)

class FakeSpeechClient:
    def __init__(self, transcript="Haryana", audio_bytes=b"RIFF\x24\x00\x00\x00WAVEfmt "):
        self.transcript = transcript
        self.audio_bytes = audio_bytes
        self.speech_to_text = SimpleNamespace(
            transcribe=lambda **_: SimpleNamespace(transcript=self.transcript, language_code="hi")
        )
        self.text_to_speech = SimpleNamespace(
            convert=lambda **_: SimpleNamespace(audios=["UklGRiQAAABXQVZFZm10IA=="])
        )

def create_application():
    res = client.post("/api/applications")
    assert res.status_code == 201
    return res.json()["application_id"]

def test_questionnaire_typed_contextual_date_of_birth():
    app_id = create_application()
    res = client.post("/api/interactions/answer/text", json={
        "application_id": app_id,
        "question_concept": "date_of_birth",
        "question_text": "Please provide date of birth.",
        "language_mode": "hi-en",
        "text": "23 September 2006"
    })
    assert res.status_code == 200
    body = res.json()
    assert body["application_id"] == app_id
    applied = body["applied_facts"]
    assert any(f["concept"] == "date_of_birth" and f["normalized_value"] == "2006-09-23" for f in applied)
    app_state = client.get(f"/api/applications/{app_id}").json()
    dob_fact = next(f for f in app_state["facts"] if f["concept"] == "date_of_birth")
    assert dob_fact["normalized_value"] == "2006-09-23"
    assert dob_fact["source_type"] == "questionnaire_typed"

def test_questionnaire_typed_contextual_state_of_domicile():
    app_id = create_application()
    res = client.post("/api/interactions/answer/text", json={
        "application_id": app_id,
        "question_concept": "state_of_domicile",
        "question_text": "Which state is your permanent domicile?",
        "language_mode": "te-en",
        "text": "Haryana"
    })
    assert res.status_code == 200
    body = res.json()
    applied = body["applied_facts"]
    assert any(f["concept"] == "state_of_domicile" and f["normalized_value"] == "Haryana" for f in applied)

def test_questionnaire_typed_contextual_course_and_year():
    app_id = create_application()
    # Course name
    res1 = client.post("/api/interactions/answer/text", json={
        "application_id": app_id,
        "question_concept": "course_name",
        "question_text": "Please provide course name.",
        "language_mode": "hi-en",
        "text": "BTech"
    })
    assert res1.status_code == 200
    assert any(f["concept"] == "course_name" and f["normalized_value"] == "BTech" for f in res1.json()["applied_facts"])

    # Year of study
    res2 = client.post("/api/interactions/answer/text", json={
        "application_id": app_id,
        "question_concept": "year_of_study",
        "question_text": "Please provide year of study.",
        "language_mode": "hi-en",
        "text": "second year"
    })
    assert res2.status_code == 200
    assert any(f["concept"] == "year_of_study" and f["normalized_value"] == 2 for f in res2.json()["applied_facts"])

def test_questionnaire_speech_equivalent_to_typed(monkeypatch):
    app_id = create_application()
    fake = FakeSpeechClient(transcript="Haryana")
    monkeypatch.setattr(main, "speech", SarvamSpeechService(Settings(sarvam_api_key="test", sarvam_enabled=True, sarvam_tts_enabled=True), fake))

    res = client.post(
        "/api/interactions/answer/speech",
        data={
            "application_id": app_id,
            "question_concept": "state_of_domicile",
            "question_text": "Which state is your permanent domicile?",
            "language_mode": "hi-en"
        },
        files={"file": ("answer.webm", b"audio-bytes", "audio/webm")}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["transcript"] == "Haryana"
    assert any(f["concept"] == "state_of_domicile" and f["normalized_value"] == "Haryana" for f in body["applied_facts"])
    domicile_fact = next(f for f in body["application"]["facts"] if f["concept"] == "state_of_domicile")
    assert domicile_fact["source_type"] == "questionnaire_speech"

def test_answer_writes_only_to_active_application():
    app_a = create_application()
    app_b = create_application()

    client.post("/api/interactions/answer/text", json={
        "application_id": app_a,
        "question_concept": "course_name",
        "question_text": "Please provide course name.",
        "language_mode": "hi-en",
        "text": "BTech"
    })

    state_a = client.get(f"/api/applications/{app_a}").json()
    state_b = client.get(f"/api/applications/{app_b}").json()

    assert any(f["concept"] == "course_name" for f in state_a["facts"])
    assert not any(f["concept"] == "course_name" for f in state_b["facts"])

def test_income_clarification_via_questionnaire_answer():
    app_id = create_application()
    s = main.repo.get(app_id)
    obs_id = str(uuid4())
    s.facts.append(main.Fact(
        id=obs_id,
        concept="household_income",
        value=8000,
        normalized_value=8000,
        data_type="currency",
        source_type="user_statement",
        status=Status.UNCERTAIN,
        period="unknown"
    ))
    main.repo.save(s)

    current_state = client.get(f"/api/applications/{app_id}").json()
    assert current_state["questions"][0]["type"] == "clarification"

    res = client.post("/api/interactions/answer/text", json={
        "application_id": app_id,
        "question_concept": "household_income",
        "question_text": current_state["questions"][0]["question"],
        "language_mode": "hi-en",
        "text": "monthly"
    })
    assert res.status_code == 200
    after = res.json()["application"]
    annual = next(f for f in after["facts"] if f["concept"] == "annual_household_income")
    assert annual["normalized_value"] == 96000
    assert annual["status"] == "DERIVED"
    assert annual["derivation"] == "8000 × 12"
    assert not any(q["type"] == "clarification" for q in after["questions"])

def test_income_clarification_speech(monkeypatch):
    app_id = create_application()
    s = main.repo.get(app_id)
    obs_id = str(uuid4())
    s.facts.append(main.Fact(
        id=obs_id,
        concept="household_income",
        value=8000,
        normalized_value=8000,
        data_type="currency",
        source_type="user_statement",
        status=Status.UNCERTAIN,
        period="unknown"
    ))
    main.repo.save(s)

    fake = FakeSpeechClient(transcript="per month")
    monkeypatch.setattr(main, "speech", SarvamSpeechService(Settings(sarvam_api_key="test", sarvam_enabled=True, sarvam_tts_enabled=True), fake))

    res = client.post(
        "/api/interactions/answer/speech",
        data={
            "application_id": app_id,
            "question_concept": "household_income",
            "question_text": "Is ₹8,000 your household income per month or per year?",
            "language_mode": "hi-en"
        },
        files={"file": ("answer.webm", b"audio-bytes", "audio/webm")}
    )
    assert res.status_code == 200
    body = res.json()
    after = body["application"]
    annual = next(f for f in after["facts"] if f["concept"] == "annual_household_income")
    assert annual["normalized_value"] == 96000
    assert annual["status"] == "DERIVED"

def test_tts_returns_playable_wav(monkeypatch):
    fake = FakeSpeechClient()
    monkeypatch.setattr(main, "speech", SarvamSpeechService(Settings(sarvam_api_key="test", sarvam_enabled=True, sarvam_tts_enabled=True), fake))

    res = client.post("/api/tts", json={
        "text": "Aapki date of birth kya hai?",
        "language_mode": "hi-en"
    })
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("audio/wav")
    assert res.content.startswith(b"RIFF")

def test_tts_failure_leaves_state_untouched(monkeypatch):
    app_id = create_application()
    service = SarvamSpeechService(Settings(sarvam_api_key="test", sarvam_enabled=True, sarvam_tts_enabled=True), FakeSpeechClient())
    monkeypatch.setattr(service, "synthesize", lambda *_: (_ for _ in ()).throw(SpeechServiceError("provider_unavailable", "TTS unavailable", True)))
    monkeypatch.setattr(main, "speech", service)

    before_state = client.get(f"/api/applications/{app_id}").json()

    res = client.post("/api/tts", json={
        "application_id": app_id,
        "text": "Please provide date of birth.",
        "language_mode": "hi-en"
    })
    assert res.status_code == 503
    after_state = client.get(f"/api/applications/{app_id}").json()
    assert before_state == after_state

def test_localized_questions_present_in_state():
    app_id = create_application()
    state = client.get(f"/api/applications/{app_id}").json()
    qs = state["questions"]
    assert qs
    q = qs[0]
    assert "localized_questions" in q
    assert set(q["localized_questions"].keys()) == {"hi-en", "te-en", "bn-en"}

