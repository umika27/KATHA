"use client";
import {useCallback,useEffect,useMemo,useRef,useState} from "react";
import {api,API_BASE,ApiError,Fact,SemanticMeta,SessionState,Status} from "../lib/api";
import {DemoGuide,Header,HeroInteraction,languages} from "../components/KathaUI";
const APPLICATION_KEY="katha_active_application_id",LEGACY_SESSION_KEY="katha_session_id",examples={"hi-en":"Main VIT Vellore mein second year student hoon. Family income around 4 lakh hai.","te-en":"Nenu VIT Vellore lo second year student. Family income around 4 lakh.","bn-en":"Ami VIT Vellore-e second year student. Family income around 4 lakh."};
declare global{interface Window{__kathaInitializationPromise?:Promise<{sessionId:string;state:SessionState}>}}
function initializeSession(){
 if(window.__kathaInitializationPromise)return window.__kathaInitializationPromise;
 const initialization=(async()=>{
  const storedId=localStorage.getItem(APPLICATION_KEY)||localStorage.getItem(LEGACY_SESSION_KEY);
  if(storedId){try{const state=await api.application(storedId);localStorage.setItem(APPLICATION_KEY,storedId);localStorage.removeItem(LEGACY_SESSION_KEY);return {sessionId:storedId,state}}catch(error){if(!(error instanceof ApiError)||error.status!==404)throw error}}
  const state=await api.createApplication();localStorage.setItem(APPLICATION_KEY,state.application_id);localStorage.removeItem(LEGACY_SESSION_KEY);return {sessionId:state.application_id,state}
 })();
 window.__kathaInitializationPromise=initialization;
 void initialization.then(()=>{if(window.__kathaInitializationPromise===initialization)delete window.__kathaInitializationPromise},()=>{if(window.__kathaInitializationPromise===initialization)delete window.__kathaInitializationPromise});
 return initialization;
}
const title=(v:string)=>v.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase()),money=(v:unknown)=>typeof v==="number"?new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}).format(v):String(v??"");
export default function Home(){
 const [sessionId,setSessionId]=useState<string|null>(null),[data,setData]=useState<SessionState|null>(null),[language,setLanguage]=useState<keyof typeof languages>("hi-en"),[text,setText]=useState(examples["hi-en"]),[error,setError]=useState(""),[busy,setBusy]=useState(""),[speechAvailable,setSpeechAvailable]=useState(false),[recording,setRecording]=useState(false),[seconds,setSeconds]=useState(0),[transcript,setTranscript]=useState(""),[candidates,setCandidates]=useState<Fact[]>([]),[answer,setAnswer]=useState(""),[uploadResult,setUploadResult]=useState(""),[adaptDone,setAdaptDone]=useState(false),[demoOpen,setDemoOpen]=useState(false),[showType,setShowType]=useState(false),[guided,setGuided]=useState(false),[documentType,setDocumentType]=useState("income_certificate"),[editingTranscript,setEditingTranscript]=useState(false),[transcriptDraft,setTranscriptDraft]=useState(""),[editingFact,setEditingFact]=useState<Fact|null>(null),[factDraft,setFactDraft]=useState(""),[semantic,setSemantic]=useState<SemanticMeta|null>(null);
 const [questionRecording,setQuestionRecording]=useState(false),[questionSeconds,setQuestionSeconds]=useState(0),[questionState,setQuestionState]=useState<"IDLE"|"LISTENING"|"PROCESSING"|"UNDERSTOOD"|"ERROR">("IDLE"),[questionError,setQuestionError]=useState(""),[playingQuestion,setPlayingQuestion]=useState(false),[voiceGuidance,setVoiceGuidance]=useState(false),[questionAnswerOutcome,setQuestionAnswerOutcome]=useState<{text:string;source:"voice"|"typed";facts:Fact[];concept:string}|null>(null),[editingQuestionFact,setEditingQuestionFact]=useState<Fact|null>(null),[editingQuestionDraft,setEditingQuestionDraft]=useState("");
 const recorder=useRef<MediaRecorder|null>(null),chunks=useRef<Blob[]>([]),timer=useRef<ReturnType<typeof setInterval>|null>(null);
 const questionRecorder=useRef<MediaRecorder|null>(null),questionChunks=useRef<Blob[]>([]),questionTimer=useRef<ReturnType<typeof setInterval>|null>(null),audioElementRef=useRef<HTMLAudioElement|null>(null),audioUrlRef=useRef<string|null>(null),lastAutoSpokenRef=useRef<string|null>(null);

 function stopAudio(){
  if(audioElementRef.current){audioElementRef.current.pause();audioElementRef.current.src="";audioElementRef.current=null}
  if(audioUrlRef.current){URL.revokeObjectURL(audioUrlRef.current);audioUrlRef.current=null}
  setPlayingQuestion(false);
 }

 const playQuestion=useCallback(async(textToSpeak:string)=>{
  if(playingQuestion){stopAudio();return}
  stopAudio();setPlayingQuestion(true);setQuestionError("");
  try{
   const blob=await api.tts(textToSpeak,language,sessionId||undefined);
   const url=URL.createObjectURL(blob);
   audioUrlRef.current=url;
   const a=new Audio(url);
   audioElementRef.current=a;
   a.onended=()=>{stopAudio()};
   a.onerror=()=>{stopAudio();setQuestionError("Audio playback unavailable. You can continue by reading or typing your answer.")};
   await a.play();
  }catch{
   stopAudio();setQuestionError("Audio playback unavailable. You can continue by reading or typing your answer.");
  }
 },[playingQuestion,language,sessionId]);

 const load=useCallback(async()=>{if(!sessionId)return;try{setData(await api.session(sessionId));setError("")}catch(e){setError((e as Error).message)}},[sessionId]);
 useEffect(()=>{initializeSession().then(({sessionId,state})=>{setSessionId(sessionId);setData(state);setError("")}).catch(e=>setError((e as Error).message));api.config().then(c=>setSpeechAvailable(c.speech_available)).catch(()=>setSpeechAvailable(false));return()=>{if(timer.current)clearInterval(timer.current);if(questionTimer.current)clearInterval(questionTimer.current);stopAudio()}},[]);

 const currentQ=data?.questions[0];
 const activeQText=currentQ?(currentQ.localized_questions?.[language]||currentQ.question):"No more questions.";

 useEffect(()=>{
  if(!voiceGuidance||!speechAvailable||!currentQ)return;
  if(lastAutoSpokenRef.current===activeQText)return;
  lastAutoSpokenRef.current=activeQText;
  playQuestion(activeQText).catch(()=>{});
 },[voiceGuidance,currentQ,activeQText,speechAvailable,playQuestion]);

 async function typed(){const story=text.trim();if(!sessionId){setError("No active application is available.");return}if(!story){setError("Tell KATHA something about your scholarship application first.");return}setBusy("Understanding your story…");setError("");try{const r=await api.text(sessionId,language,story);setTranscript(r.normalized_text);setTranscriptDraft(r.normalized_text);setCandidates(r.extracted_candidate_facts);setSemantic(r.semantic);setData(r.application);setText("")}catch(e){setError((e as Error).message)}finally{setBusy("")}}
 async function startRecording(){if(!sessionId||recording||!speechAvailable)return;try{const stream=await navigator.mediaDevices.getUserMedia({audio:true}),mime=MediaRecorder.isTypeSupported("audio/webm;codecs=opus")?"audio/webm;codecs=opus":"audio/webm",r=new MediaRecorder(stream,{mimeType:mime});chunks.current=[];r.ondataavailable=e=>{if(e.data.size)chunks.current.push(e.data)};r.onstop=async()=>{stream.getTracks().forEach(t=>t.stop());if(timer.current)clearInterval(timer.current);setRecording(false);setBusy("KATHA is understanding…");const form=new FormData();form.append("file",new Blob(chunks.current,{type:mime}),"recording.webm");form.append("session_id",sessionId);form.append("language",language);try{const x=await api.speech(form);setTranscript(x.transcript);setTranscriptDraft(x.transcript);setCandidates(x.candidate_facts);setSemantic(x.semantic);await load();if(x.audio_url)new Audio(API_BASE+x.audio_url).play().catch(()=>{})}catch(e){setError((e as Error).message)}finally{setBusy("")}};recorder.current=r;r.start();setSeconds(0);setRecording(true);timer.current=setInterval(()=>setSeconds(s=>{if(s>=27)r.stop();return s+1}),1000)}catch{setError("Microphone permission was denied or no microphone is available.")}}
 function stopRecording(){if(recorder.current?.state==="recording")recorder.current.stop()}
 async function upload(type:string,file?:File){if(!sessionId)return;setBusy("Reading evidence…");setUploadResult("");const form=new FormData();form.append("session_id",sessionId);form.append("document_type",type);if(file)form.append("file",file);else form.append("fixture_mode","true");try{const r=await api.upload(form);setUploadResult(r.status==="VERIFIED"?`${title(type)} added with document provenance.`:r.message);await load()}catch(e){setError((e as Error).message)}finally{setBusy("")}}

 async function submitQuestionAnswer(){
  if(!sessionId||!currentQ||!answer.trim())return;
  setQuestionState("PROCESSING");setQuestionError("");setBusy("Understanding your answer…");
  try{
   const r=await api.answerText(sessionId,currentQ.concept,activeQText,language,answer.trim());
   setData(r.application);setAnswer("");
   setQuestionAnswerOutcome({text:r.normalized_text,source:"typed",facts:r.applied_facts,concept:currentQ.concept});
   setQuestionState("UNDERSTOOD");
  }catch(e){
   setQuestionError((e as Error).message||"KATHA could not understand that answer. Try again.");
   setQuestionState("ERROR");
  }finally{setBusy("")}
 }

 async function startQuestionRecording(){
  if(!sessionId||!currentQ||questionRecording||!speechAvailable)return;
  stopAudio();setQuestionError("");setQuestionAnswerOutcome(null);
  try{
   const stream=await navigator.mediaDevices.getUserMedia({audio:true}),mime=MediaRecorder.isTypeSupported("audio/webm;codecs=opus")?"audio/webm;codecs=opus":"audio/webm",r=new MediaRecorder(stream,{mimeType:mime});
   questionChunks.current=[];
   r.ondataavailable=e=>{if(e.data.size)questionChunks.current.push(e.data)};
   r.onstop=async()=>{
    stream.getTracks().forEach(t=>t.stop());
    if(questionTimer.current)clearInterval(questionTimer.current);
    setQuestionRecording(false);setQuestionState("PROCESSING");setBusy("Understanding your answer…");
    const form=new FormData();
    form.append("file",new Blob(questionChunks.current,{type:mime}),"answer.webm");
    form.append("application_id",sessionId);
    form.append("question_concept",currentQ.concept);
    form.append("question_text",activeQText);
    form.append("language_mode",language);
    try{
     const x=await api.answerSpeech(form);
     setData(x.application);
     setQuestionAnswerOutcome({text:x.transcript,source:"voice",facts:x.applied_facts,concept:currentQ.concept});
     setQuestionState("UNDERSTOOD");
     if(voiceGuidance&&x.audio_url){
      const a=new Audio(API_BASE+x.audio_url);
      audioElementRef.current=a;
      a.play().catch(()=>{});
     }
    }catch{
     setQuestionError("I couldn't hear that. Try again or type your answer.");
     setQuestionState("ERROR");
    }finally{setBusy("")}
   };
   questionRecorder.current=r;r.start();setQuestionSeconds(0);setQuestionRecording(true);setQuestionState("LISTENING");
   questionTimer.current=setInterval(()=>setQuestionSeconds(s=>{if(s>=18)r.stop();return s+1}),1000);
  }catch{
   setQuestionError("Microphone permission was denied or no microphone is available.");
   setQuestionState("ERROR");
  }
 }
 function stopQuestionRecording(){if(questionRecorder.current?.state==="recording")questionRecorder.current.stop()}

 async function saveQuestionCorrection(){
  if(!sessionId||!editingQuestionFact||!editingQuestionDraft.trim())return;
  setBusy("Applying correction…");
  try{
   const res=await api.correction(sessionId,language,String(editingQuestionFact.value??""),editingQuestionDraft.trim(),editingQuestionFact.concept);
   setData(res.application);
   setQuestionAnswerOutcome(prev=>prev?{...prev,facts:prev.facts.map(f=>f.concept===editingQuestionFact.concept?{...f,value:editingQuestionDraft.trim(),normalized_value:editingQuestionDraft.trim(),source_type:"user_correction",status:"STATED"}:f)}:null);
   setEditingQuestionFact(null);setEditingQuestionDraft("");setAdaptDone(true);
  }catch(e){setError((e as Error).message)}finally{setBusy("")}
 }

 async function clarifyIncome(period:"monthly"|"annual"){
  const q=data?.questions.find(q=>q.type==="clarification"&&q.concept==="household_income");
  if(!sessionId||!q?.fact_id)return;setBusy("Updating your income…");
  try{
   const state=await api.clarifyIncomePeriod(sessionId,q.fact_id,period);
   setData(state);
   const incomeFacts=state.facts.filter(f=>f.id===q.fact_id||f.derived_from_fact_ids?.includes(q.fact_id!));
   setCandidates(incomeFacts);
   setQuestionAnswerOutcome({text:period==="monthly"?"Per month":"Per year",source:"typed",facts:incomeFacts,concept:"household_income"});
   setQuestionState("UNDERSTOOD");
  }catch(e){setError((e as Error).message)}finally{setBusy("")}
 }

 async function play(){
  const targetText=activeQText!=="No more questions."?activeQText:"Your application is ready for review.";
  await playQuestion(targetText);
 }

 async function correctTranscript(){if(!sessionId||!transcriptDraft.trim())return;setBusy("Applying your correction…");try{const r=await api.text(sessionId,language,transcriptDraft);setTranscript(r.normalized_text);setCandidates(r.extracted_candidate_facts);setSemantic(r.semantic);setData(r.application);setEditingTranscript(false)}catch(e){setError((e as Error).message)}finally{setBusy("")}}
 async function correctFact(){if(!sessionId||!editingFact||!factDraft.trim())return;setBusy("Saving your correction…");try{const r=await api.correction(sessionId,language,String(editingFact.value??""),factDraft,editingFact.concept);setData(r.application);setCandidates(current=>current.map(f=>f.id===editingFact.id?{...f,value:factDraft,normalized_value:factDraft,source_type:"user_correction",status:"STATED"}:f));setEditingFact(null);setAdaptDone(true)}catch(e){setError((e as Error).message)}finally{setBusy("")}}
 function clearEphemeral(){setTranscript("");setTranscriptDraft("");setCandidates([]);setSemantic(null);setAnswer("");setUploadResult("");setEditingTranscript(false);setEditingFact(null);setFactDraft("");setAdaptDone(false);setQuestionAnswerOutcome(null);setEditingQuestionFact(null);setQuestionError("");stopAudio()}
 async function newApplication(){setBusy("Creating a new application…");try{const state=await api.createApplication();localStorage.setItem(APPLICATION_KEY,state.application_id);setSessionId(state.application_id);setData(state);clearEphemeral();setDemoOpen(false)}catch(e){setError((e as Error).message)}finally{setBusy("")}}
 async function resetCurrent(){if(!sessionId)return;setBusy("Resetting current application…");try{setData(await api.resetApplication(sessionId));clearEphemeral()}catch(e){setError((e as Error).message)}finally{setBusy("")}}
 async function reset(s:string){if(!sessionId)return;setBusy("Loading demo state…");try{setData(await api.reset(sessionId,s));clearEphemeral()}catch(e){setError((e as Error).message)}finally{setBusy("")}}

 const resolutions=useMemo(()=>Object.fromEntries((data?.resolutions||[]).map(r=>[r.requirement_id,r])),[data]),groups=useMemo(()=>{const g:Record<string,any[]>={VERIFIED:[],KNOWN:[],NEEDS_YOU:[],CONFLICTS:[]};for(const r of data?.application.requirements||[]){const s=resolutions[r.id]?.status as Status;(s==="VERIFIED"?g.VERIFIED:s==="CONFLICT"?g.CONFLICTS:s==="STATED"?g.KNOWN:g.NEEDS_YOU).push(r)}return g},[data,resolutions]),needs=data?.questions.length||0,total=data?.application.requirements.length||0;
 const guideStep=!transcript?1:!data?.evidence.some(e=>e.type==="income_certificate")?2:needs>0?3:4;

 return <main><Header language={language} onLanguage={l=>{setLanguage(l);setText(examples[l]);stopAudio()}} demoOpen={demoOpen} onDemo={()=>setDemoOpen(!demoOpen)} onNewApplication={newApplication}/>
 <HeroInteraction speechAvailable={speechAvailable} recording={recording} seconds={seconds} busy={!!busy||!sessionId} onSpeak={recording?stopRecording:startRecording} onType={()=>{setShowType(true);requestAnimationFrame(()=>document.querySelector("#type")?.scrollIntoView({behavior:"smooth"}))}} onEvidence={()=>document.querySelector("#evidence")?.scrollIntoView({behavior:"smooth"})}/>
 {guided&&<DemoGuide step={guideStep} onClose={()=>setGuided(false)}/>} 
 {error&&<div className="error-banner" role="alert"><span>{error}</span><button onClick={()=>setError("")}>Dismiss</button></div>}{busy&&<div className="busy" role="status">{busy}</div>}
 {showType&&<section className="type-panel reveal" id="type"><div><p className="kicker">Your words, your language</p><h2>Type your story</h2><p>Clearly marked example for {languages[language]}—edit it freely.</p></div><div className="type-control"><label className="sr-only" htmlFor="story">Tell KATHA your story</label><textarea id="story" value={text} onChange={e=>setText(e.target.value)} autoFocus/><button className="primary" onClick={typed} disabled={!!busy}>Tell KATHA</button></div></section>}
 {transcript&&<section className="understood"><div><p className="kicker">You said</p>{editingTranscript?<div className="correction-editor"><textarea value={transcriptDraft} onChange={e=>setTranscriptDraft(e.target.value)}/><button onClick={correctTranscript}>Apply correction</button><button onClick={()=>setEditingTranscript(false)}>Cancel</button></div>:<><p className="quote">“{transcript}”</p><button className="correct-button" onClick={()=>{setTranscriptDraft(transcript);setEditingTranscript(true)}}>Correct transcript</button></>}</div><div><p className="kicker">What KATHA understood</p>{semantic&&process.env.NODE_ENV==="development"&&<p className="semantic-diagnostics">Provider: {semantic.provider} · Fallback: {String(semantic.fallback_used)}{semantic.fallback_reason?` (${semantic.fallback_reason})`:""} · Candidates: {semantic.candidate_fact_count}</p>}<div className="chips">{candidates.length?candidates.map(f=><span key={f.id}>{title(f.concept)} · {f.concept.includes("income")?money(f.normalized_value):String(f.normalized_value??f.value)} · {f.status}{f.period==="unknown"?" · Needs clarification: income period":""}{f.derivation?` · ${f.derivation}`:""}{f.precision==="approximate"?" · ≈":""}{f.concept!=="household_income"&&<button aria-label={`Correct ${title(f.concept)}`} onClick={()=>{setEditingFact(f);setFactDraft(String(f.value??""))}}>Correct</button>}</span>):<span>I understood your message, but I couldn&apos;t map any of it to the information this scholarship needs yet.</span>}</div>{editingFact&&<div className="correction-editor fact-editor"><label>Correct {title(editingFact.concept)}<input value={factDraft} onChange={e=>setFactDraft(e.target.value)}/></label><button onClick={correctFact}>Save fact</button><button onClick={()=>setEditingFact(null)}>Cancel</button></div>}<button className="hear" onClick={play} disabled={!speechAvailable}>{playingQuestion?"⏹ Stop":"▶ Hear response"}</button></div></section>}
 {adaptDone&&<p className="correction-success" role="status">✓ Correction remembered. KATHA will use it as context next time.</p>}
 {data&&<><section className="compression"><p>KATHA reduced this application to what still needs your attention.</p><div className="compression-flow"><div><b>{total}</b><span>requirements</span></div><i>→</i><div><b>{data.preflight.resolved}</b><span>resolved</span></div><i>→</i><div className="accent"><b>{needs}</b><span>need you</span></div></div></section>
 <section className="journey"><div className="main-column"><p className="kicker">Application workspace</p><h2>{data.application.title}</h2>{Object.entries(groups).map(([name,items])=>items.length>0&&<details className={`group group-${name}`} open={name==="NEEDS_YOU"||name==="VERIFIED"} key={name}><summary><span>{name.replace("_"," ")}</span><b>{items.length}</b></summary><div>{items.map(r=>{const facts=data.facts.filter(f=>f.concept===r.concept),verified=facts.find(f=>f.status==="VERIFIED"||f.source_type==="document"),fact=verified||facts.at(-1),prior=verified&&facts.find(f=>f.source_type==="user"),ev=data.evidence.find(e=>e.id===fact?.source_id);return <article className="requirement" key={r.id}><div><h3>{r.label}</h3><p className="value">{fact?(r.concept.includes("income")?money(fact.normalized_value):String(fact.normalized_value??fact.value)):"Not provided"}</p>{fact?.derivation&&<p className="source">Derived from household income · {fact.derivation}</p>}{ev&&<p className="source">Source: {title(ev.type)} · {new Date(ev.uploaded_at).toLocaleDateString()}</p>}{prior&&<p className="prior">Previously stated: {prior.precision==="approximate"?"approximately ":""}{r.concept.includes("income")?money(prior.value):String(prior.value)}</p>}</div><span className={`status ${fact?.status==="DERIVED"?"DERIVED":resolutions[r.id]?.status}`}>{fact?.status==="DERIVED"?"DERIVED":resolutions[r.id]?.status}</span></article>})}</div></details>)}</div>
 <aside><section className="question-card">
  <div className="card-top-row">
   <p className="kicker">{currentQ?.type==="clarification"?"KATHA needs one detail":"Minimum next step"}</p>
   {speechAvailable&&<button className={`voice-guidance-toggle ${voiceGuidance?"active":""}`} onClick={()=>setVoiceGuidance(!voiceGuidance)} aria-pressed={voiceGuidance} title="Automatically speak new questions">Voice guidance: {voiceGuidance?"ON":"OFF"}</button>}
  </div>
  <h2>KATHA knows {data.preflight.resolved} of {total} requirements.</h2>
  <p>Only {needs} thing{needs===1?"":"s"} still need you.</p>
  <hr/>
  <div className="question-title-row">
   <h3>{activeQText}</h3>
   {currentQ&&speechAvailable&&<button className={`listen-btn ${playingQuestion?"playing":""}`} onClick={()=>playQuestion(activeQText)} disabled={!!busy} aria-label={playingQuestion?"Stop audio":"Listen to question"}>{playingQuestion?"⏹ Stop":"🔊 Listen"}</button>}
  </div>
  {currentQ&&<div className="question-interaction-area">
   {speechAvailable&&<div className="question-voice-row">
    <button className={`question-speak ${questionRecording?"recording":""}`} onClick={questionRecording?stopQuestionRecording:startQuestionRecording} disabled={!!busy} aria-label={questionRecording?"Stop recording answer":"Speak answer"}>
     <span className="mic-dot" aria-hidden="true">{questionRecording?"■":"●"}</span>
     {questionRecording?`Stop · 0:${String(questionSeconds).padStart(2,"0")}`:"Speak answer"}
    </button>
    {questionState==="LISTENING"&&<span className="listening-tag">Listening…</span>}
    {questionState==="PROCESSING"&&<span className="processing-tag">Understanding your answer…</span>}
   </div>}
   {currentQ.type==="clarification"?<div className="clarification-options"><button onClick={()=>clarifyIncome("monthly")}>Per month</button><button onClick={()=>clarifyIncome("annual")}>Per year</button><button onClick={()=>{setText(String(currentQ.known_value??""));setShowType(true);document.querySelector("#type")?.scrollIntoView({behavior:"smooth"})}}>Edit amount</button></div>:
   <div className="answer-row"><input value={answer} onChange={e=>setAnswer(e.target.value)} placeholder={`Type your answer for ${title(currentQ.concept)}…`} onKeyDown={e=>e.key==="Enter"&&submitQuestionAnswer()} disabled={!!busy||questionRecording}/><button onClick={submitQuestionAnswer} disabled={!answer.trim()||!!busy||questionRecording}>Save</button></div>}
   {questionError&&<p className="question-error" role="alert">{questionError}</p>}
  </div>}
  {questionAnswerOutcome&&<div className="question-outcome reveal">
   <div className="outcome-heard">
    <p className="outcome-kicker">{questionAnswerOutcome.source==="voice"?"What KATHA heard":"You said"}</p>
    <p className="outcome-text">“{questionAnswerOutcome.text}”</p>
   </div>
   <div className="outcome-understood">
    <p className="outcome-kicker">What KATHA understood</p>
    <div className="outcome-chips">
     {questionAnswerOutcome.facts.length?questionAnswerOutcome.facts.map(f=><span key={f.id} className="understood-chip">
      <b>{title(f.concept)}</b> · {f.concept.includes("income")?money(f.normalized_value):String(f.normalized_value??f.value)} · {f.status}
      {f.derivation?` (${f.derivation})`:""}
      {f.source_type!=="document"&&<button aria-label={`Edit ${title(f.concept)}`} onClick={()=>{setEditingQuestionFact(f);setEditingQuestionDraft(String(f.value??""))}}>Edit</button>}
     </span>):<span>I heard your answer, but couldn&apos;t map it yet. You can try typing it above.</span>}
    </div>
    {editingQuestionFact&&<div className="inline-editor">
     <label>Correct {title(editingQuestionFact.concept)}:
      <input value={editingQuestionDraft} onChange={e=>setEditingQuestionDraft(e.target.value)}/>
     </label>
     <button className="primary-sm" onClick={saveQuestionCorrection}>Save edit</button>
     <button className="ghost-sm" onClick={()=>setEditingQuestionFact(null)}>Cancel</button>
    </div>}
    <button className="outcome-dismiss" onClick={()=>setQuestionAnswerOutcome(null)}>Proceed</button>
   </div>
  </div>}
  <p className="reason">{currentQ?.reason}</p>
 </section>
 <section className={`preflight-card ${data.preflight.status==="READY"?"ready":""}`}><p className="kicker">Application readiness</p><h2>{data.preflight.status==="READY"?"✓ Ready for review":"● Not ready"}</h2><p>{data.preflight.status==="READY"?"Every required fact is resolved or supported. Review before submission.":`${data.preflight.blockers.length} blockers remaining`}</p>{data.preflight.blockers.length>0&&<details><summary>View blocker details</summary>{data.preflight.blockers.map(b=><div className="blocker" key={b.concept}><b>{title(b.concept)}</b><span>{b.message}</span></div>)}</details>}<button className="preflight-refresh" onClick={load}>Run Preflight</button></section>
 {transcript.toLowerCase().includes("vit valor")&&!adaptDone&&<section className="adapt"><p className="kicker">KATHA Adapt</p><p>I heard: <s>VIT Valor</s></p><h3>Did you mean VIT Vellore?</h3><button onClick={async()=>{if(sessionId){await api.correction(sessionId,language,"VIT Valor","VIT Vellore","college_name");setAdaptDone(true)}}}>Yes, remember this</button></section>}</aside></section>
 <section className="evidence-section" id="evidence"><p className="kicker">Evidence & provenance</p><h2>Human claim → Evidence → Requirement → Ready</h2><label className="document-label" htmlFor="document-type">Document type</label><select id="document-type" value={documentType} onChange={e=>setDocumentType(e.target.value)}><option value="income_certificate">Income certificate</option><option value="student_certificate">Student certificate</option><option value="domicile_certificate">Domicile certificate</option></select><label className="dropzone"><span>Drop a file here, or <b>choose document</b></span><small>Text PDF or text file. Image OCR is not available yet.</small><input type="file" accept=".pdf,.txt" onChange={e=>e.target.files?.[0]&&upload(documentType,e.target.files[0])}/></label><div className="evidence-list">{data.evidence.length?data.evidence.map(e=><article key={e.id}><span>Document</span><h3>{title(e.type)}</h3><p>{e.filename}</p><b>✓ {e.verification_state}</b></article>):<p>No evidence uploaded yet.</p>}</div><div className="upload-grid"><span>Demo fixtures:</span>{["income_certificate","student_certificate","domicile_certificate"].map(t=><button key={t} onClick={()=>upload(t)} disabled={!!busy}>+ {title(t)}</button>)}</div>{uploadResult&&<p className="success">✓ {uploadResult}</p>}</section>
 {demoOpen&&<section className="demo reveal"><button className="guided-button" onClick={async()=>{await reset("initial");setGuided(true);setDemoOpen(false)}}>Start guided demo</button><button className="reset-current" onClick={resetCurrent}>Reset Current Application</button><div className="demo-controls">{["initial","partial","conflict","ready"].map(s=><button onClick={()=>reset(s)} key={s}>{title(s)}</button>)}</div></section>}</>}
 <footer><b>KATHA</b><p>AI interprets. Deterministic systems decide. Nothing is submitted automatically.</p></footer></main>}
