import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

@dataclass(frozen=True)
class Settings:
    sarvam_api_key: str = os.getenv("SARVAM_API_KEY", "").strip()
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/katha.db")
    cors_origins: tuple[str, ...] = tuple(x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if x.strip())
    sarvam_stt_model: str = os.getenv("SARVAM_STT_MODEL", "saaras:v4")
    sarvam_tts_model: str = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
    sarvam_stt_mode: str = os.getenv("SARVAM_STT_MODE", "transcribe")
    sarvam_timeout_seconds: float = float(os.getenv("SARVAM_TIMEOUT_SECONDS", "30"))

settings = Settings()
