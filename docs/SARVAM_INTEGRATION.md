# Sarvam AI integration

`SarvamService` is KATHA's single provider boundary. It owns Saaras v4 speech-to-text, Sarvam 105B structured semantic extraction and response phrasing, Bulbul v3 text-to-speech, shared credentials, normalized errors, and operation metadata logging. Document AI has a disabled feature-gated stub so no OCR capability is implied.

## Trust boundary

Sarvam returns candidate facts through a strict Pydantic JSON schema whose `concept` field is generated from KATHA's canonical concept registry. Every field is required, unknown fields and concepts are rejected, and one malformed response retry is allowed. Null, non-explicit, or invalid candidates are ignored.

The deterministic KATHA core remains authoritative. It assigns `STATED` or `UNCERTAIN`, resolves evidence, detects conflicts, chooses the minimum next question, and runs Preflight. Sarvam cannot mark facts `VERIFIED`, decide eligibility, or submit an application. Response generation receives the already-computed state and can only phrase it.

Approximate language or low confidence produces `UNCERTAIN`. Exact user claims produce `STATED`. Speech provenance is `speech_transcript`; typed provenance is `user_statement`; user edits are `user_correction`. Verified document evidence remains authoritative and disagreements become deterministic conflicts.

## Configuration

Copy `.env.example` to `.env` or configure `backend/.env`:

```dotenv
SARVAM_API_KEY=
SARVAM_ENABLED=true
SARVAM_SEMANTIC_ENABLED=true
SARVAM_TTS_ENABLED=true
SARVAM_DOC_AI_ENABLED=false
SARVAM_STT_MODEL=saaras:v4
SARVAM_CHAT_MODEL=sarvam-105b
SARVAM_TTS_MODEL=bulbul:v3
SARVAM_STT_MODE=transcribe
SARVAM_TIMEOUT_SECONDS=30
```

`GET /api/config` exposes only safe booleans: `sarvamConfigured`, `speechEnabled`, `semanticExtractionEnabled`, `ttsEnabled`, and `documentAIEnabled`. It never returns the API key.

## Failure behavior

Authentication, credits, invalid audio, rate limiting, timeout, malformed output, and provider outages are normalized to safe error codes. Semantic failures visibly use the rule-based fallback. TTS failures return the text and application state with `tts_error`; they do not discard a successful interaction. Logs include operation, model, latency, success, and fallback metadata, but not API keys or raw transcript text.

## Verification

Mocked tests never call Sarvam or spend credits:

```bash
cd backend
../.venv/bin/python -m pytest -q
```

Manual live text, audio, and optional TTS checks are separate:

```bash
.venv/bin/python scripts/test_sarvam_live.py --text "Ami VIT Vellore-e second year-e porchi"
.venv/bin/python scripts/test_sarvam_live.py --audio sample.webm --tts --language bn-en --output /tmp/katha.wav
```

The script prints the transcript (for audio), validated semantic payload, applied facts, deterministic next question, Preflight result, and TTS path. A non-zero exit means live provider verification did not succeed.
