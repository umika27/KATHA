# KATHA Access Point API

The Raspberry Pi client is a thin UI. FastAPI remains the only source of truth; use the same `session_id` in the web and Access Point clients.

`POST /api/access-point/interact` accepts:

```json
{"session_id":"demo-01","language":"hi-en","text":"Scholarship ke liye apply karna hai"}
```

The stable response contains `session_id`, `ui_state`, `response_text`, `application_status`, `resolved`, `missing`, `uncertain`, `conflicts`, `next_question`, and nullable `tts_audio_url`. `ui_state` is one of `IDLE`, `LISTENING`, `PROCESSING`, `RESULT`, `READY`, `ERROR`. The server returns terminal `RESULT` or `READY`; transitional and error states are rendered locally.

`GET /api/session/{session_id}` returns facts, evidence, requirement resolutions, questions and Preflight. Clients must not create authoritative state.

HTTP 422 means invalid input. On network failure show `ERROR` and allow retry. Never present `STATED`, `UNCERTAIN`, or `CONFLICT` as verified. Supported languages are `hi-en`, `te-en`, and `bn-en`. Authentication and transport security are intentionally absent from the local MVP.
