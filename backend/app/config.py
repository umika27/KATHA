import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT=Path(__file__).parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")

def env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().casefold() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    sarvam_api_key: str = os.getenv("SARVAM_API_KEY", "").strip()
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/katha.db")
    cors_origins: tuple[str, ...] = tuple(x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if x.strip())
    sarvam_stt_model: str = os.getenv("SARVAM_STT_MODEL", "saaras:v4")
    sarvam_chat_model: str = os.getenv("SARVAM_CHAT_MODEL", "sarvam-105b")
    sarvam_tts_model: str = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
    sarvam_stt_mode: str = os.getenv("SARVAM_STT_MODE", "transcribe")
    sarvam_timeout_seconds: float = float(os.getenv("SARVAM_TIMEOUT_SECONDS", "30"))
    sarvam_enabled: bool = env_bool("SARVAM_ENABLED", True)
    sarvam_semantic_enabled: bool = env_bool("SARVAM_SEMANTIC_ENABLED", True)
    sarvam_tts_enabled: bool = env_bool("SARVAM_TTS_ENABLED", True)
    sarvam_doc_ai_enabled: bool = env_bool("SARVAM_DOCUMENT_AI_ENABLED", env_bool("SARVAM_DOC_AI_ENABLED", True))
    sarvam_doc_ai_timeout_seconds: float = float(os.getenv("SARVAM_DOC_AI_TIMEOUT_SECONDS", "35"))
    sarvam_doc_ai_poll_interval: float = float(os.getenv("SARVAM_DOC_AI_POLL_INTERVAL", "1.5"))
    environment: str = os.getenv("KATHA_ENV", "development")

settings = Settings()
