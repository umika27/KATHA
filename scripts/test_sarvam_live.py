#!/usr/bin/env python3
"""Manual paid Sarvam end-to-end smoke test. Never run by pytest."""
import argparse,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from dotenv import load_dotenv
load_dotenv(ROOT/".env");load_dotenv(ROOT/"backend"/".env")

def heading(value):print(f"\n=== {value} ===")
def main():
 parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
 group.add_argument("--text");group.add_argument("--audio",type=Path)
 parser.add_argument("--tts",action="store_true");parser.add_argument("--language",default="hi-en",choices=["hi-en","te-en","bn-en"]);parser.add_argument("--output",type=Path,default=Path("sarvam-live-output.wav"))
 parser.add_argument("--debug-semantic",action="store_true",help="Print safe SDK response/request diagnostics (never the API key)")
 args=parser.parse_args()
 if not os.getenv("SARVAM_API_KEY","").strip():parser.error("SARVAM_API_KEY is missing from .env or backend/.env")
 if args.audio and not args.audio.is_file():parser.error(f"Audio file not found: {args.audio}")
 from app.sarvam_service import SarvamService,SarvamError
 from app.semantic_pipeline import SemanticPipeline
 from app.services import RuleBasedSemanticExtractionService
 from app.models import Session
 from app.workflow import scholarship_requirements
 from app.core import resolve_all,questions,preflight
 provider=SarvamService();pipeline=SemanticPipeline(provider,RuleBasedSemanticExtractionService());session=Session(id="manual-live-test");reqs=scholarship_requirements()
 try:
  text=args.text
  if args.audio:
   text,detected=provider.transcribe_audio(args.audio.read_bytes(),args.audio.name)
   heading("STT TRANSCRIPT");print(text);print("Detected:",detected or "unknown")
  normalized,facts,ignored,outcome=pipeline.extract(text,session,reqs,resolve_all(reqs,session),args.language,"speech_transcript" if args.audio else "user_statement");session.facts.extend(facts)
  resolutions=resolve_all(reqs,session);next_questions=questions(reqs,resolutions,session);pf=preflight(reqs,resolutions)
  heading("SEMANTIC STATUS");print(outcome.model_dump_json(indent=2,exclude={"extraction","fallback_facts"}))
  heading("SEMANTIC ENVELOPE");print(outcome.extraction.model_dump_json(indent=2,exclude={"facts"}))
  heading("SARVAM FACTS");print(*[fact.model_dump_json() for fact in outcome.extraction.facts],sep="\n") if outcome.extraction.facts else print("None")
  heading("FALLBACK FACTS");print(*[__import__("json").dumps(fact,ensure_ascii=False) for fact in outcome.fallback_facts],sep="\n") if outcome.fallback_facts else print("None")
  heading("FINAL ACCEPTED FACTS");print(*[f.model_dump_json() for f in facts],sep="\n") if facts else print("None");print("Ignored:",ignored)
  if args.debug_semantic:
   heading("SARVAM SDK DIAGNOSTICS");print(__import__("json").dumps(provider.last_semantic_diagnostics,ensure_ascii=False,indent=2,default=str))
  heading("NEXT QUESTION");print(next_questions[0].model_dump_json(indent=2) if next_questions else "None")
  heading("PREFLIGHT");print(pf)
  if args.tts:
   response=provider.generate_response({"facts":[f.model_dump(mode="json") for f in facts],"next_question":next_questions[0].model_dump(mode="json") if next_questions else None,"preflight":pf},"KATHA processed your information.",args.language)
   args.output.write_bytes(provider.synthesize_speech(response,{"hi-en":"hi-IN","te-en":"te-IN","bn-en":"bn-IN"}[args.language]));heading("TTS OUTPUT PATH");print(args.output.resolve())
 except SarvamError as exc:print(f"Sarvam failed [{exc.code}]: {exc}",file=sys.stderr);raise SystemExit(1)
if __name__=="__main__":main()
