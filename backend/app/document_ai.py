import io
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import Settings, settings
from .models import DocumentCandidateField, DocumentReviewCandidate

log = logging.getLogger("katha.document_ai")

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Puducherry", "Chandigarh"
]

def parse_iso_date(date_str: str) -> str | None:
    if not date_str:
        return None
    cleaned = date_str.strip().replace(",", " ").replace(".", " ")
    cleaned = " ".join(cleaned.split())
    formats = [
        "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
        "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None

def check_if_expired(date_str: str | None) -> bool:
    if not date_str:
        return False
    iso = parse_iso_date(date_str)
    if not iso:
        return False
    try:
        exp_date = datetime.strptime(iso, "%Y-%m-%d").date()
        today = datetime.now(timezone.utc).date()
        return exp_date < today
    except Exception:
        return False

def extract_candidates_from_text(pages: list[tuple[int, str]], document_type: str, filename: str, provider: str) -> DocumentReviewCandidate:
    doc_id = str(uuid4())
    full_text = "\n\n".join(f"--- Page {p} ---\n{t}" for p, t in pages)
    fields: list[DocumentCandidateField] = []
    
    # Track overall document validity
    doc_issue_date: str | None = None
    doc_expiry_date: str | None = None
    doc_financial_year: str | None = None
    doc_is_expired: bool = False
    
    # 1. Scan for issue date, expiry date, financial year across pages
    for page_num, text in pages:
        # Issue Date
        m_issue = re.search(r"(?:issue\s+date|date\s+of\s+issue|issued\s+on|dated)\s*[:\-]?\s*([0-9]{1,2}[-\s/][A-Za-z0-9]{3,9}[-\s/][0-9]{2,4}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})", text, re.I)
        if m_issue and not doc_issue_date:
            doc_issue_date = m_issue.group(1).strip()
            
        # Expiry / Validity Date
        m_exp = re.search(r"(?:valid\s+until|valid\s+upto|valid\s+up\s+to|expiry\s+date|expires\s+on|validity)\s*[:\-]?\s*([0-9]{1,2}[-\s/][A-Za-z0-9]{3,9}[-\s/][0-9]{2,4}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})", text, re.I)
        if m_exp and not doc_expiry_date:
            raw_exp = m_exp.group(1).strip()
            doc_expiry_date = raw_exp
            doc_is_expired = check_if_expired(raw_exp)

        # Financial Year
        m_fy = re.search(r"(?:financial\s+year|f\.?y\.?)\s*[:\-]?\s*(20[0-9]{2}\s*[-–/]\s*[0-9]{2,4})", text, re.I)
        if m_fy and not doc_financial_year:
            doc_financial_year = m_fy.group(1).strip()

    # 2. Extract concept-specific fields depending on document_type
    if document_type == "income_certificate":
        income_found = False
        for page_num, text in pages:
            # Pattern for annual income amount
            m_inc = re.search(r"(?:annual\s+household\s+income|annual\s+family\s+income|gross\s+annual\s+income|annual\s+income|yearly\s+income|family\s+income|household\s+income|income)[^\d\n\r]{0,35}(?:inr|rs\.?|₹)?\s*([0-9,.]+)\s*(lakh|lac|k|crore)?", text, re.I)
            if m_inc:
                raw_num = m_inc.group(1).replace(",", "").strip()
                try:
                    val = float(raw_num)
                    mult = m_inc.group(2)
                    if mult:
                        low_m = mult.lower()
                        if "lakh" in low_m or "lac" in low_m:
                            val *= 100000
                        elif "crore" in low_m:
                            val *= 10000000
                        elif "k" in low_m:
                            val *= 1000
                    num_val = int(val) if val.is_integer() else val
                    span = m_inc.group(0).strip()
                    fields.append(DocumentCandidateField(
                        concept="annual_household_income",
                        label="Annual household income",
                        value=num_val,
                        normalized_value=num_val,
                        data_type="number",
                        unit="INR",
                        period="annual",
                        confidence=0.95,
                        page_number=page_num,
                        source_span=span,
                        financial_year=doc_financial_year,
                        issue_date=doc_issue_date,
                        expiry_date=doc_expiry_date,
                        is_expired=doc_is_expired
                    ))
                    income_found = True
                    break
                except ValueError:
                    pass
        if not income_found and "income" in full_text.lower():
            # Fallback simple number pattern
            m_simple = re.search(r"(?:(?:inr|rs\.?|₹)\s*)([0-9,]{4,})", full_text, re.I)
            if m_simple:
                val = int(m_simple.group(1).replace(",", ""))
                fields.append(DocumentCandidateField(
                    concept="annual_household_income",
                    label="Annual household income",
                    value=val,
                    normalized_value=val,
                    data_type="number",
                    unit="INR",
                    period="annual",
                    confidence=0.85,
                    page_number=1,
                    source_span=m_simple.group(0).strip(),
                    financial_year=doc_financial_year,
                    issue_date=doc_issue_date,
                    expiry_date=doc_expiry_date,
                    is_expired=doc_is_expired
                ))

        # Add financial year metadata field if present
        if doc_financial_year:
            fields.append(DocumentCandidateField(
                concept="financial_year",
                label="Financial Year",
                value=doc_financial_year,
                normalized_value=doc_financial_year,
                data_type="string",
                confidence=0.95,
                page_number=1,
                source_span=f"Financial year: {doc_financial_year}",
                issue_date=doc_issue_date,
                expiry_date=doc_expiry_date,
                is_expired=doc_is_expired
            ))

    elif document_type == "student_certificate":
        # Student status
        for page_num, text in pages:
            if re.search(r"\b(?:bonafide\s+student|enrolled|active\s+student|pursuing|regular\s+student|studying)\b", text, re.I):
                m = re.search(r"(\b(?:bonafide\s+student|enrolled|active\s+student|pursuing|regular\s+student|studying)\b)", text, re.I)
                fields.append(DocumentCandidateField(
                    concept="student_status",
                    label="Student status",
                    value="active",
                    normalized_value="active",
                    data_type="string",
                    confidence=0.95,
                    page_number=page_num,
                    source_span=m.group(0) if m else "active student",
                    issue_date=doc_issue_date,
                    expiry_date=doc_expiry_date,
                    is_expired=doc_is_expired
                ))
                break

        # College Name
        college_found = False
        for page_num, text in pages:
            m_col = re.search(r"(?:college|institute|university)\s*(?:of\s+[A-Za-z\s]+|technology|engineering)?", text, re.I)
            if "vit vellore" in text.lower() or "vellore institute of technology" in text.lower():
                fields.append(DocumentCandidateField(
                    concept="college_name",
                    label="College name",
                    value="VIT Vellore",
                    normalized_value="VIT Vellore",
                    data_type="string",
                    confidence=0.98,
                    page_number=page_num,
                    source_span="Vellore Institute of Technology",
                    issue_date=doc_issue_date,
                    expiry_date=doc_expiry_date
                ))
                college_found = True
                break
            elif "delhi technological university" in text.lower() or "dtu" in text.lower():
                fields.append(DocumentCandidateField(
                    concept="college_name",
                    label="College name",
                    value="Delhi Technological University",
                    normalized_value="Delhi Technological University",
                    data_type="string",
                    confidence=0.98,
                    page_number=page_num,
                    source_span="Delhi Technological University",
                    issue_date=doc_issue_date,
                    expiry_date=doc_expiry_date
                ))
                college_found = True
                break
            elif m_col:
                # Capture line
                line = [l.strip() for l in text.split("\n") if m_col.group(0).lower() in l.lower()]
                val = line[0] if line and len(line[0]) < 60 else m_col.group(0)
                fields.append(DocumentCandidateField(
                    concept="college_name",
                    label="College name",
                    value=val,
                    normalized_value=val,
                    data_type="string",
                    confidence=0.88,
                    page_number=page_num,
                    source_span=val,
                    issue_date=doc_issue_date,
                    expiry_date=doc_expiry_date
                ))
                college_found = True
                break

        # Course name
        for page_num, text in pages:
            m_course = re.search(r"\b(B\.?Tech|B\.?Sc|M\.?Tech|M\.?B\.?A|B\.?E\.?|BCA|MCA)\b(?:\s+in\s+([A-Za-z\s]+))?", text, re.I)
            if m_course:
                course_val = m_course.group(0).strip()
                norm_course = "BTech" if "btech" in course_val.lower() or "b.tech" in course_val.lower() else course_val
                fields.append(DocumentCandidateField(
                    concept="course_name",
                    label="Course name",
                    value=norm_course,
                    normalized_value=norm_course,
                    data_type="string",
                    confidence=0.92,
                    page_number=page_num,
                    source_span=course_val,
                    issue_date=doc_issue_date,
                    expiry_date=doc_expiry_date
                ))
                break

        # Year of study
        for page_num, text in pages:
            m_yr = re.search(r"\b([1-4]|first|second|third|fourth|1st|2nd|3rd|4th)\s+year\b", text, re.I)
            if m_yr:
                yr_map = {"1": 1, "first": 1, "1st": 1, "2": 2, "second": 2, "2nd": 2, "3": 3, "third": 3, "3rd": 3, "4": 4, "fourth": 4, "4th": 4}
                token = m_yr.group(1).lower()
                int_yr = yr_map.get(token, 1)
                fields.append(DocumentCandidateField(
                    concept="year_of_study",
                    label="Year of study",
                    value=int_yr,
                    normalized_value=int_yr,
                    data_type="integer",
                    confidence=0.92,
                    page_number=page_num,
                    source_span=m_yr.group(0),
                    issue_date=doc_issue_date,
                    expiry_date=doc_expiry_date
                ))
                break

    elif document_type == "domicile_certificate":
        # State of domicile
        dom_found = False
        for page_num, text in pages:
            low_t = text.lower()
            for st in INDIAN_STATES:
                if re.search(rf"\b{re.escape(st)}\b", text, re.I):
                    m_span = re.search(rf"(?:domicile\s+of|resident\s+of\s+(?:the\s+state\s+of\s+)?|state\s+of\s+)?({re.escape(st)})", text, re.I)
                    span_text = m_span.group(0) if m_span else st
                    fields.append(DocumentCandidateField(
                        concept="state_of_domicile",
                        label="State of domicile",
                        value=st,
                        normalized_value=st,
                        data_type="string",
                        confidence=0.95,
                        page_number=page_num,
                        source_span=span_text,
                        issue_date=doc_issue_date,
                        expiry_date=doc_expiry_date,
                        is_expired=doc_is_expired
                    ))
                    dom_found = True
                    break
            if dom_found:
                break

    # Also extract applicant name if clearly stated
    for page_num, text in pages:
        m_name = re.search(r"(?:certif(?:y|ies)\s+that|student\s+name\s*[:\-]|applicant\s*[:\-]|shri/smt\.?\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", text)
        if m_name:
            name_val = m_name.group(1).strip()
            # Only add full_name if not already present
            if not any(f.concept == "full_name" for f in fields):
                fields.append(DocumentCandidateField(
                    concept="full_name",
                    label="Applicant name",
                    value=name_val,
                    normalized_value=name_val,
                    data_type="string",
                    confidence=0.85,
                    page_number=page_num,
                    source_span=m_name.group(0).strip(),
                    issue_date=doc_issue_date,
                    expiry_date=doc_expiry_date
                ))
            break

    # Proof fact flag
    fields.append(DocumentCandidateField(
        concept=document_type,
        label=f"{document_type.replace('_', ' ').title()} Verified Proof",
        value=True,
        normalized_value=True,
        data_type="boolean",
        confidence=1.0,
        page_number=1,
        source_span=f"Verified {document_type.replace('_', ' ')}: {filename}",
        issue_date=doc_issue_date,
        expiry_date=doc_expiry_date,
        is_expired=doc_is_expired
    ))

    return DocumentReviewCandidate(
        document_id=doc_id,
        document_type=document_type,
        filename=filename,
        provider=provider,
        raw_text=full_text,
        fields=fields
    )

class DocumentUnderstandingService:
    def extract_document(self, content: bytes, filename: str, content_type: str, document_type: str, fixture: bool = False) -> DocumentReviewCandidate:
        raise NotImplementedError

class BasicDocumentService(DocumentUnderstandingService):
    FIXTURES = {
        "income_certificate": {
            "annual_household_income": 382400,
            "financial_year": "2025-26",
            "issue_date": "15 Aug 2026",
            "expiry_date": "14 Aug 2027",
            "state_of_domicile": "Haryana",
            "full_name": "Aanya Sharma"
        },
        "student_certificate": {
            "student_status": "active",
            "college_name": "VIT Vellore",
            "course_name": "BTech",
            "year_of_study": 2,
            "full_name": "Aanya Sharma"
        },
        "domicile_certificate": {
            "state_of_domicile": "Haryana",
            "full_name": "Aanya Sharma"
        }
    }

    def extract_document(self, content: bytes, filename: str, content_type: str, document_type: str, fixture: bool = False) -> DocumentReviewCandidate:
        if fixture:
            pages = [(1, self._build_fixture_text(document_type))]
            return extract_candidates_from_text(pages, document_type, filename or f"fixture_{document_type}.txt", provider="demo-fixture")
        
        pages = self._extract_pages(content, filename, content_type)
        if not pages:
            return DocumentReviewCandidate(
                document_id=str(uuid4()),
                document_type=document_type,
                filename=filename,
                provider="basic-fallback",
                raw_text="",
                fields=[]
            )
        return extract_candidates_from_text(pages, document_type, filename, provider="basic-fallback")

    def extract(self, document_type: str, text: str, fixture: bool = False) -> dict[str, Any]:
        if fixture:
            return self.FIXTURES.get(document_type, {})
        cand = self.extract_document(text.encode("utf-8") if isinstance(text, str) else (text or b""), f"{document_type}.txt", "text/plain", document_type, fixture=False)
        return {f.concept: f.normalized_value for f in cand.fields if f.concept != document_type and f.normalized_value is not None}

    def _build_fixture_text(self, document_type: str) -> str:
        if document_type == "income_certificate":
            return (
                "GOVERNMENT OF HARYANA\n"
                "OFFICE OF THE TAHSILDAR\n"
                "INCOME CERTIFICATE\n\n"
                "This is to certify that Aanya Sharma, resident of Haryana,\n"
                "has an annual family income as follows:\n"
                "Annual household income: INR 382400\n"
                "Financial year: 2025–26\n"
                "Issue date: 15 Aug 2026\n"
                "Valid until: 14 Aug 2027\n"
                "Digitally signed by Tahsildar."
            )
        elif document_type == "student_certificate":
            return (
                "VELLORE INSTITUTE OF TECHNOLOGY\n"
                "BONAFIDE STUDENT CERTIFICATE\n\n"
                "This is to certify that Aanya Sharma is a bonafide student of VIT Vellore,\n"
                "currently studying in 2nd year B.Tech Computer Science Engineering.\n"
                "Enrollment Status: Active student.\n"
                "Date of issue: 01 Aug 2026."
            )
        elif document_type == "domicile_certificate":
            return (
                "GOVERNMENT OF HARYANA\n"
                "DOMICILE CERTIFICATE\n\n"
                "This is to certify that Aanya Sharma is a permanent resident of Haryana.\n"
                "State of domicile: Haryana.\n"
                "Date of issue: 10 Jan 2025."
            )
        return ""

    def _extract_pages(self, content: bytes, filename: str, content_type: str) -> list[tuple[int, str]]:
        if not content:
            return []
        # Check PDF
        if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content))
                pages = []
                for idx, p in enumerate(reader.pages):
                    t = p.extract_text() or ""
                    pages.append((idx + 1, t))
                return pages
            except Exception as e:
                log.warning("PDF extraction failed: %s", e)
                return []
        # Plain text
        try:
            txt = content.decode("utf-8", errors="ignore")
            if txt.strip():
                return [(1, txt)]
        except Exception:
            pass
        return []

class SarvamDocumentAIService(DocumentUnderstandingService):
    def __init__(self, config: Settings = settings, client: Any = None):
        self.config = config
        self.client = client
        if self.client is None and config.sarvam_api_key:
            from sarvamai import SarvamAI
            self.client = SarvamAI(api_subscription_key=config.sarvam_api_key, timeout=config.sarvam_timeout_seconds)

    @property
    def available(self) -> bool:
        return bool(self.client and self.config.sarvam_enabled and self.config.sarvam_doc_ai_enabled and self.config.sarvam_api_key)

    def extract_document(self, content: bytes, filename: str, content_type: str, document_type: str, fixture: bool = False) -> DocumentReviewCandidate:
        if not self.available:
            raise RuntimeError("Sarvam Document AI is not configured or disabled.")
        if not content:
            raise ValueError("Document file is empty.")

        # Determine MIME type for Sarvam Doc AI
        mime = content_type
        if not mime or mime == "application/octet-stream":
            low = filename.lower()
            if low.endswith(".pdf"):
                mime = "application/pdf"
            elif low.endswith((".jpg", ".jpeg")):
                mime = "image/jpeg"
            elif low.endswith(".png"):
                mime = "image/png"
            else:
                mime = "application/pdf"

        # Submit digitise job
        log.info("Submitting Sarvam Document AI job for %s (%s)", filename, mime)
        try:
            job = self.client.doc_ai.digitise(
                file=[(filename, content, mime)],
                output_format="md"
            )
            job_id = getattr(job, "job_id", None)
            if not job_id:
                raise RuntimeError("Sarvam Document AI did not return a valid job ID.")
        except Exception as exc:
            log.warning("Failed to start Sarvam Document AI job: %s", exc)
            raise RuntimeError(f"Sarvam Document AI job initiation failed: {exc}") from exc

        # Bounded polling
        max_attempts = int(self.config.sarvam_doc_ai_timeout_seconds / self.config.sarvam_doc_ai_poll_interval)
        terminal_statuses = {"completed", "partially_completed", "failed", "rejected"}
        final_status = None
        for attempt in range(max_attempts):
            time.sleep(self.config.sarvam_doc_ai_poll_interval)
            try:
                st = self.client.doc_ai.get_status(job_id)
                final_status = getattr(st, "status", None)
                if final_status in terminal_statuses:
                    break
            except Exception as poll_err:
                log.warning("Polling error on job %s: %s", job_id, poll_err)

        if final_status not in {"completed", "partially_completed"}:
            raise TimeoutError(f"Sarvam Document AI job {job_id} did not complete in time (status: {final_status}).")

        # Fetch results
        try:
            results = self.client.doc_ai.get_results(job_id)
        except Exception as res_err:
            raise RuntimeError(f"Failed to retrieve Sarvam Document AI results: {res_err}") from res_err

        # Extract markdown pages
        pages: list[tuple[int, str]] = []
        documents = getattr(results, "documents", []) or []
        for doc in documents:
            doc_pages = getattr(doc, "pages", []) or []
            for p in doc_pages:
                p_num = getattr(p, "page_num", 1) or getattr(p, "page_number", 1) or 1
                p_content = getattr(p, "content", "") or ""
                if not p_content and hasattr(p, "blocks") and p.blocks:
                    block_texts = []
                    for b in p.blocks:
                        if isinstance(b, dict):
                            t = b.get("text") or ""
                        else:
                            t = getattr(b, "text", "") or ""
                        if t.strip():
                            block_texts.append(t.strip())
                    p_content = "\n\n".join(block_texts)
                if p_content.strip():
                    pages.append((p_num, p_content))

        if not pages:
            raise RuntimeError("Sarvam Document AI returned no readable pages.")

        log.info("Sarvam Document AI successfully digitized %d pages for %s", len(pages), filename)
        return extract_candidates_from_text(pages, document_type, filename, provider="sarvam-doc-ai")

class DocumentPipeline:
    def __init__(self, sarvam_service: SarvamDocumentAIService, fallback_service: BasicDocumentService):
        self.sarvam = sarvam_service
        self.fallback = fallback_service

    def extract(self, content: bytes, filename: str, content_type: str, document_type: str, fixture_mode: bool = False) -> DocumentReviewCandidate:
        if fixture_mode:
            return self.fallback.extract_document(content, filename, content_type, document_type, fixture=True)

        # Validate file extension / MIME
        allowed_exts = (".pdf", ".png", ".jpg", ".jpeg", ".txt")
        if filename and not any(filename.lower().endswith(ext) for ext in allowed_exts):
            raise ValueError("Unsupported document format. Please upload a PDF, PNG, or JPEG file.")

        # Try Sarvam Document AI if available
        if self.sarvam.available:
            try:
                candidate = self.sarvam.extract_document(content, filename, content_type, document_type)
                if candidate.fields:
                    return candidate
                log.info("Sarvam Document AI returned 0 fields; falling back to deterministic extraction.")
            except Exception as exc:
                log.warning("Sarvam Document AI extraction failed (%s), switching to fallback: %s", type(exc).__name__, exc)

        # Fallback
        return self.fallback.extract_document(content, filename, content_type, document_type, fixture=False)
