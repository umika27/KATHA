#!/usr/bin/env python3
"""Manual paid Sarvam smoke test. Never imported or run by pytest."""
import argparse
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from dotenv import load_dotenv
load_dotenv(ROOT/".env")

def main():
 parser=argparse.ArgumentParser(description="Run one live Sarvam STT request and optional TTS request.")
 parser.add_argument("audio",type=Path,help="Audio file (REST recordings must be 30 seconds or shorter)")
 parser.add_argument("--tts",action="store_true",help="Also synthesize a short acknowledgement")
 parser.add_argument("--language",default="hi-IN",choices=["hi-IN","te-IN","bn-IN"])
 parser.add_argument("--output",type=Path,default=Path("sarvam-test-output.wav"))
 args=parser.parse_args()
 if not os.getenv("SARVAM_API_KEY"," ").strip(): parser.error("SARVAM_API_KEY is missing. Put it in the root .env or export it.")
 if not args.audio.is_file(): parser.error(f"Audio file not found: {args.audio}")
 from app.services import SarvamSpeechService,SpeechServiceError
 try:
  service=SarvamSpeechService();result=service.transcribe(args.audio.read_bytes(),args.audio.name)
  print(f"Transcript: {result.text}")
  print(f"Detected language: {result.detected_language or 'unknown'}")
  if args.tts:
   args.output.write_bytes(service.synthesize("KATHA speech integration is working.",args.language));print(f"TTS audio written to: {args.output}")
 except SpeechServiceError as exc:
  print(f"Sarvam test failed [{exc.code}]: {exc}",file=sys.stderr);raise SystemExit(1)
if __name__=="__main__":main()
