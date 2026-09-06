import io
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import Status, Precision

@pytest.fixture
def client():
    return TestClient(app)

def make_app(client):
    r = client.post("/api/applications")
    assert r.status_code == 201
    return r.json()["application_id"]

def test_a_document_upload_belongs_only_to_active_application(client):
    app1 = make_app(client)
    app2 = make_app(client)
    
    # Upload to app1
    content = b"Annual household income: INR 382400\nFinancial year: 2025-26"
    r = client.post("/api/documents/upload", data={"session_id": app1, "document_type": "income_certificate"}, files={"file": ("income.txt", content, "text/plain")})
    assert r.status_code == 200
    assert r.json()["status"] == "REVIEW_REQUIRED"
    
    # Verify app1 has pending document, app2 has none
    st1 = client.get(f"/api/applications/{app1}").json()
    st2 = client.get(f"/api/applications/{app2}").json()
    assert len(st1.get("pending_documents", [])) == 1
    assert len(st2.get("pending_documents", [])) == 0

def test_b_extraction_candidates_do_not_silently_become_verified_facts(client):
    app_id = make_app(client)
    content = b"Annual household income: INR 382400\nFinancial year: 2025-26"
    r = client.post("/api/documents/upload", data={"session_id": app_id, "document_type": "income_certificate"}, files={"file": ("income.txt", content, "text/plain")})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "REVIEW_REQUIRED"
    
    # Check application facts - NO verified income fact should be in facts yet
    st = client.get(f"/api/applications/{app_id}").json()
    income_facts = [f for f in st["facts"] if f["concept"] == "annual_household_income"]
    assert len(income_facts) == 0
    assert len(st["evidence"]) == 0

def test_c_accepting_candidate_creates_evidence_with_provenance(client):
    app_id = make_app(client)
    content = b"Annual household income: INR 382400\nFinancial year: 2025-26\nIssue date: 15 Aug 2026\nValid until: 14 Aug 2027"
    r = client.post("/api/documents/upload", data={"session_id": app_id, "document_type": "income_certificate"}, files={"file": ("income.txt", content, "text/plain")})
    cand = r.json()["candidate"]
    
    # Accept candidate
    r_accept = client.post("/api/documents/candidates/accept", json={"application_id": app_id, "document_id": cand["document_id"]})
    assert r_accept.status_code == 200
    res = r_accept.json()
    assert res["status"] == "ACCEPTED"
    assert len(res["evidence"]) > 0
    
    st = res["application"]
    income_fact = next((f for f in st["facts"] if f["concept"] == "annual_household_income"), None)
    assert income_fact is not None
    assert income_fact["value"] == 382400
    assert income_fact["status"] == "VERIFIED"
    assert income_fact["source_type"] == "document"
    assert income_fact["source_span"] is not None
    assert income_fact["source_id"] == res["evidence"]["id"]

def test_d_ignored_candidate_does_not_alter_application_truth(client):
    app_id = make_app(client)
    content = b"Annual household income: INR 382400"
    r = client.post("/api/documents/upload", data={"session_id": app_id, "document_type": "income_certificate"}, files={"file": ("income.txt", content, "text/plain")})
    cand = r.json()["candidate"]
    
    # Ignore candidate
    r_ign = client.post("/api/documents/candidates/ignore", json={"application_id": app_id, "document_id": cand["document_id"]})
    assert r_ign.status_code == 200
    
    st = client.get(f"/api/applications/{app_id}").json()
    assert len(st["facts"]) == 0
    assert len(st["evidence"]) == 0
    assert len(st.get("pending_documents", [])) == 0

def test_e_edited_extraction_has_correct_provenance_and_status(client):
    app_id = make_app(client)
    content = b"Annual household income: INR 382400"
    r = client.post("/api/documents/upload", data={"session_id": app_id, "document_type": "income_certificate"}, files={"file": ("income.txt", content, "text/plain")})
    cand = r.json()["candidate"]
    
    # User edits income to 350000 before accepting
    r_accept = client.post("/api/documents/candidates/accept", json={
        "application_id": app_id,
        "document_id": cand["document_id"],
        "overrides": {"annual_household_income": 350000}
    })
    assert r_accept.status_code == 200
    st = r_accept.json()["application"]
    fact = next(f for f in st["facts"] if f["concept"] == "annual_household_income")
    assert fact["value"] == 350000
    assert fact["source_type"] == "user_edited_document"
    assert fact["status"] == "STATED"
    assert "Edited from document" in fact["derivation"]

def test_f_evidence_resolves_correct_requirement(client):
    app_id = make_app(client)
    # Stated income
    client.post("/api/interactions/answer/text", json={
        "application_id": app_id,
        "question_concept": "annual_household_income",
        "question_text": "Income",
        "language_mode": "hi-en",
        "text": "382400 per year"
    })
    
    # Upload and accept income certificate
    content = b"Annual household income: INR 382400\nValid until: 14 Aug 2027"
    r = client.post("/api/documents/upload", data={"session_id": app_id, "document_type": "income_certificate"}, files={"file": ("income.txt", content, "text/plain")})
    cand = r.json()["candidate"]
    r_acc = client.post("/api/documents/candidates/accept", json={"application_id": app_id, "document_id": cand["document_id"]})
    st = r_acc.json()["application"]
    
    inc_res = next(r for r in st["resolutions"] if r["requirement_id"] == "req-7")
    assert inc_res["status"] == "VERIFIED"

def upload_and_accept(client, app_id, doc_type, filename, content, mime="text/plain"):
    r = client.post("/api/documents/upload", data={"session_id": app_id, "document_type": doc_type}, files={"file": (filename, content, mime)})
    assert r.status_code == 200
    res = r.json()
    assert res["status"] == "REVIEW_REQUIRED"
    cand = res["candidate"]
    r_acc = client.post("/api/documents/candidates/accept", json={"application_id": app_id, "document_id": cand["document_id"]})
    assert r_acc.status_code == 200
    return r_acc

def test_g_evidence_does_not_resolve_unrelated_requirement(client):
    app_id = make_app(client)
    content = b"Annual household income: INR 382400"
    r = upload_and_accept(client, app_id, "income_certificate", "income.txt", content)
    st = r.json()["application"]
    
    # Domicile requirement (req-8) and student status (req-3) must remain unresolved
    dom_res = next(r for r in st["resolutions"] if r["requirement_id"] == "req-8")
    assert dom_res["status"] == "MISSING"

def test_h_stated_value_equals_evidence_value_no_conflict(client):
    app_id = make_app(client)
    # User stated 382400
    client.post("/api/interactions/answer/text", json={
        "application_id": app_id,
        "question_concept": "annual_household_income",
        "question_text": "Income",
        "language_mode": "hi-en",
        "text": "382400 annual"
    })
    # Document has 382400
    content = b"Annual household income: INR 382400"
    upload_and_accept(client, app_id, "income_certificate", "income.txt", content)
    st = client.get(f"/api/applications/{app_id}").json()
    inc_res = next(r for r in st["resolutions"] if r["requirement_id"] == "req-7")
    assert inc_res["status"] == "VERIFIED"
    assert st["preflight"]["conflicts"] == 0

def test_i_stated_value_different_from_evidence_triggers_conflict(client):
    app_id = make_app(client)
    # User stated 400000
    client.post("/api/interactions/answer/text", json={
        "application_id": app_id,
        "question_concept": "annual_household_income",
        "question_text": "Income",
        "language_mode": "hi-en",
        "text": "400000 annual"
    })
    # Document has 382400
    content = b"Annual household income: INR 382400"
    upload_and_accept(client, app_id, "income_certificate", "income.txt", content)
    st = client.get(f"/api/applications/{app_id}").json()
    inc_res = next(r for r in st["resolutions"] if r["requirement_id"] == "req-7")
    assert inc_res["status"] == "CONFLICT"

def test_j_unresolved_conflict_blocks_ready_in_preflight(client):
    app_id = make_app(client)
    client.post("/api/interactions/answer/text", json={"application_id": app_id, "question_concept": "annual_household_income", "question_text": "Income", "language_mode": "hi-en", "text": "400000 annual"})
    content = b"Annual household income: INR 382400"
    upload_and_accept(client, app_id, "income_certificate", "income.txt", content)
    st = client.get(f"/api/applications/{app_id}").json()
    assert st["preflight"]["status"] == "NOT_READY"
    assert st["preflight"]["conflicts"] > 0
    assert any("conflict" in b["message"].lower() for b in st["preflight"]["blockers"])

def test_k_conflict_resolution_recomputes_preflight(client):
    app_id = make_app(client)
    client.post("/api/interactions/answer/text", json={"application_id": app_id, "question_concept": "annual_household_income", "question_text": "Income", "language_mode": "hi-en", "text": "400000 annual"})
    content = b"Annual household income: INR 382400"
    upload_and_accept(client, app_id, "income_certificate", "income.txt", content)
    
    # Resolve via use_document
    r_res = client.post("/api/conflicts/resolve", json={
        "application_id": app_id,
        "concept": "annual_household_income",
        "resolution_choice": "use_document"
    })
    assert r_res.status_code == 200
    st = r_res.json()["application"]
    assert st["preflight"]["conflicts"] == 0
    inc_res = next(r for r in st["resolutions"] if r["requirement_id"] == "req-7")
    assert inc_res["status"] == "VERIFIED"

def test_l_expired_evidence_does_not_count_as_valid_proof(client):
    app_id = make_app(client)
    # Upload expired certificate (valid until Aug 2020)
    content = b"Annual household income: INR 382400\nValid until: 14 Aug 2020"
    r = upload_and_accept(client, app_id, "income_certificate", "income.txt", content)
    st = r.json()["application"]
    inc_res = next(r for r in st["resolutions"] if r["requirement_id"] == "req-7")
    assert inc_res["status"] != "VERIFIED"
    assert inc_res["status"] in ("UNCERTAIN", "STATED")

def test_m_evidence_without_expiry_is_not_falsely_marked_expired(client):
    app_id = make_app(client)
    content = b"Annual household income: INR 382400"
    r = upload_and_accept(client, app_id, "income_certificate", "income.txt", content)
    st = r.json()["application"]
    ev = st["evidence"][0]
    assert ev["is_expired"] is False
    assert ev["verification_state"] == "VERIFIED"

def test_n_replacing_or_removing_document_recomputes_state(client):
    app_id = make_app(client)
    content = b"Annual household income: INR 382400"
    r = upload_and_accept(client, app_id, "income_certificate", "income.txt", content)
    ev_id = r.json()["evidence"]["id"]
    
    # Remove document
    r_del = client.delete(f"/api/documents/{app_id}/{ev_id}")
    assert r_del.status_code == 200
    st = r_del.json()["application"]
    assert len(st["evidence"]) == 0
    assert not any(f["concept"] == "income_certificate" for f in st["facts"])
    inc_res = next(r for r in st["resolutions"] if r["requirement_id"] == "req-7")
    assert inc_res["status"] == "MISSING"

def test_o_application_isolation(client):
    app1 = make_app(client)
    app2 = make_app(client)
    content = b"State of domicile: Haryana"
    upload_and_accept(client, app1, "domicile_certificate", "domicile.txt", content)
    
    st1 = client.get(f"/api/applications/{app1}").json()
    st2 = client.get(f"/api/applications/{app2}").json()
    assert len(st1["evidence"]) == 1
    assert len(st2["evidence"]) == 0

def test_p_document_ai_failure_fallback(client):
    app_id = make_app(client)
    # Plain text document falls back cleanly to deterministic parser
    content = b"VELLORE INSTITUTE OF TECHNOLOGY\nBONAFIDE STUDENT CERTIFICATE\nAanya Sharma is a bonafide student of VIT Vellore\n2nd year B.Tech Computer Science\nStatus: Active student"
    r = client.post("/api/documents/upload", data={"session_id": app_id, "document_type": "student_certificate"}, files={"file": ("student.txt", content, "text/plain")})
    assert r.status_code == 200
    cand = r.json()["candidate"]
    assert any(f["concept"] == "student_status" and f["value"] == "active" for f in cand["fields"])
    assert any(f["concept"] == "college_name" and "VIT" in f["value"] for f in cand["fields"])

def test_q_unsupported_document_type_produces_controlled_error(client):
    app_id = make_app(client)
    r = client.post("/api/documents/upload", data={"session_id": app_id, "document_type": "passport_scan"}, files={"file": ("scan.txt", b"test", "text/plain")})
    assert r.status_code == 422

def test_r_applicant_upload_cannot_bypass_candidate_review_with_client_parameters(client):
    """
    Security invariant regression test:
    A normal applicant-facing request to POST /api/documents/upload must NEVER
    be able to bypass candidate review and directly create VERIFIED evidence merely by
    supplying auto_accept=true, fixture_mode=true, or any equivalent client-controlled parameter.
    """
    from app.main import app, get_upload_security_context, UploadSecurityContext
    # Ensure default applicant context (no trusted test fixture bypass)
    app.dependency_overrides[get_upload_security_context] = lambda: UploadSecurityContext(allow_trusted_auto_accept=False)

    app_id = make_app(client)
    content = b"Annual household income: INR 382400\nFinancial year: 2023-2024\nValid until: 2027-08-15"

    # 1. Real file upload with auto_accept=true
    r1 = client.post("/api/documents/upload", data={"session_id": app_id, "document_type": "income_certificate", "auto_accept": "true"}, files={"file": ("income.txt", content, "text/plain")})
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["status"] == "REVIEW_REQUIRED", "Real file upload with auto_accept=true must require review"
    assert "candidate" in data1
    # Evidence and verified facts must remain UNCHANGED in application
    st1 = client.get(f"/api/applications/{app_id}").json()
    assert len(st1["evidence"]) == 0, "No evidence should be created before explicit candidate accept"
    assert not any(f["concept"] == "annual_household_income" and f["status"] == Status.VERIFIED for f in st1["facts"])

    # 2. Real file upload with fixture_mode=true
    r2 = client.post("/api/documents/upload", data={"session_id": app_id, "document_type": "income_certificate", "fixture_mode": "true"}, files={"file": ("income.txt", content, "text/plain")})
    assert r2.status_code == 200
    assert r2.json()["status"] == "REVIEW_REQUIRED", "Real file upload with fixture_mode=true must require review"
    st2 = client.get(f"/api/applications/{app_id}").json()
    assert len(st2["evidence"]) == 0

    # 3. Client request without file sending auto_accept=true or fixture_mode=true
    r3 = client.post("/api/documents/upload", data={"session_id": app_id, "document_type": "income_certificate", "auto_accept": "true", "fixture_mode": "true"})
    assert r3.status_code == 200
    assert r3.json()["status"] == "REVIEW_REQUIRED", "Normal applicant fixture request must require review"
    st3 = client.get(f"/api/applications/{app_id}").json()
    assert len(st3["evidence"]) == 0

    # 4. Verification of the full Review-Before-Trust cycle:
    # upload real document -> facts/evidence unchanged -> REVIEW_REQUIRED -> explicit Accept -> only then evidence/facts created
    cand_id = r3.json()["candidate"]["document_id"]
    acc_resp = client.post("/api/documents/candidates/accept", json={
        "application_id": app_id,
        "document_id": cand_id
    })
    assert acc_resp.status_code == 200
    assert acc_resp.json()["status"] == "ACCEPTED"
    st_final = client.get(f"/api/applications/{app_id}").json()
    assert len(st_final["evidence"]) == 1, "Evidence created only after explicit candidate accept"
    assert any(f["concept"] == "annual_household_income" and f["status"] == Status.VERIFIED for f in st_final["facts"])


