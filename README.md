# KATHA

KATHA is a Human-to-Institution Accessibility Fabric. People describe their reality through speech, text, and documents; institutions demand structured fields and proof. This scholarship MVP keeps those layers separate and makes every unresolved or verified value visible.

```text
Next.js browser ─────┐
                     ├── FastAPI / KATHA Core ── SQLite
Kivy Access Point ───┘          │
                                └── Sarvam STT/TTS (optional)
```

FastAPI is the only source of truth. Both clients use the same `session_id`; refreshing the browser or opening the lightweight Raspberry Pi client reads the same persisted state. The SPI TFT does not run Chromium or the web platform.

## What works

- Typed Hindi/Hinglish, Telugu + English, and Bengali + English demo narratives mapped to one canonical concept registry
- Browser MediaRecorder → FastAPI → Sarvam Saaras v4 → the same deterministic semantic extractor used by typed input
- Sarvam Bulbul v3 response playback, with text-only fallback on failure
- Explicit `VERIFIED`, `STATED`, `UNCERTAIN`, `MISSING`, and `CONFLICT` states
- Text-PDF/basic deterministic extraction and fictional fixture documents with provenance
- Minimum-question answers, correction memory, Preflight, and shared SQLite sessions
- Five demo states: INITIAL, PARTIAL, CONFLICT, MISSING_PROOF, READY
- Native Kivy Access Point simulator, independent of display/touch drivers

No application is submitted automatically.

## Repository

- `backend/app` — API, models, deterministic engines, services, configuration, persistence
- `backend/tests` — domain, API, mocked Sarvam, and end-to-end demo tests
- `frontend` — Next.js application journey and typed API client
- `access_point` — Kivy simulator and hardware-neutral input adapter
- `scripts/test_sarvam.py` — manual-only live Sarvam check
- `docs/ACCESS_POINT_API.md` — stable Raspberry Pi API contract

## Environment

Copy `.env.example` to `.env`. Never commit `.env` or expose `SARVAM_API_KEY` through a `NEXT_PUBLIC_` variable.

```dotenv
SARVAM_API_KEY=
DATABASE_URL=sqlite:///./data/katha.db
CORS_ORIGINS=http://localhost:3000
SARVAM_STT_MODEL=saaras:v4
SARVAM_TTS_MODEL=bulbul:v3
SARVAM_STT_MODE=transcribe
SARVAM_TIMEOUT_SECONDS=30
```

Copy `frontend/.env.example` to `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Without a Sarvam key, the application starts normally and identifies itself as typed mode. Typed interaction, fixture evidence, shared state, and Preflight remain functional. Speech buttons do not fake success.

## Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000
```

Swagger is available at `http://localhost:8000/docs`.

```bash
cd backend
../.venv/bin/python -m pytest -q
```

SQLite schema initialization and the current additive migration run automatically. Demo sessions are not deleted on startup.

## Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Verification:

```bash
npm run lint
npm run typecheck
npm run build
```

Browser recordings are capped below Sarvam REST’s 30-second limit. Current Saaras documentation lists WebM, WAV, MP3, AAC, AIFF, OGG/Opus, FLAC and several other supported formats.

## Manual Sarvam test

This command makes one paid/live STT request. It is never invoked by pytest:

```bash
.venv/bin/python scripts/test_sarvam.py path/to/recording.webm
```

Add `--tts` to also write a short synthesized response:

```bash
.venv/bin/python scripts/test_sarvam.py path/to/recording.wav --tts --language hi-IN --output /tmp/katha-tts.wav
```

The script exits non-zero for missing credentials, missing files, authentication failure, unavailable credits, invalid audio, rate limiting, timeout, or provider errors.

## Kivy Access Point

```bash
cd access_point
cp config.example.json config.json
pip install -r requirements.txt
python main.py
```

Set `BACKEND_URL`, `DEFAULT_LANGUAGE`, `SCREEN_WIDTH`, and `SCREEN_HEIGHT` in `config.json`. Use `KATHA_SESSION_ID=demo-01` to share the browser session. Actual framebuffer, touch controller, microphone, packaging, and autostart remain hardware-team work.

## Demo walkthrough

1. Start FastAPI and Next.js, then open `http://localhost:3000`.
2. Open Developer Demo Controls and select INITIAL or PARTIAL.
3. Choose a language and speak for less than 28 seconds, or use the clearly marked typed example.
4. Inspect the original transcript and canonical facts. Approximate ₹4 lakh remains uncertain.
5. Add the fictional income certificate. The exact ₹3,82,400 document value becomes verified while the approximate prior claim remains visible.
6. Add student and domicile evidence, then answer the minimum remaining questions.
7. Watch the question count decrease and Preflight become READY FOR REVIEW.
8. Refresh the browser or open Kivy with `demo-01`; both retrieve the same SQLite session.

## API overview

- `GET /api/health`, `GET /api/config`
- `GET /api/session/{session_id}`
- `POST /api/interactions/text`, `POST /api/interactions/speech`
- `POST /api/tts`, `POST /api/answers`
- `POST /api/documents/upload`, `POST /api/corrections`
- `POST /api/access-point/interact`
- `POST /api/demo/reset/{session_id}` (development/demo only)

## Honest limitations

Semantic extraction remains deliberately rule-based and demo-scoped. Uploaded images are accepted by the UI but return an unknown extraction result because OCR/Document AI is not implemented. Only deterministic fixtures and safely parsed text produce document facts. AI-extracted values must not become verified without KATHA provenance rules. Authentication, encryption/retention controls, production PostgreSQL, offline sync, general form parsing, and browser extensions are out of scope.
