"use client";
import type {ReactNode} from "react";

export const languages={"hi-en":"Hindi / Hinglish","te-en":"Telugu + English","bn-en":"Bengali + English"} as const;

export function Header({language,onLanguage,demoOpen,onDemo,onNewApplication}:{language:keyof typeof languages;onLanguage:(value:keyof typeof languages)=>void;demoOpen:boolean;onDemo:()=>void;onNewApplication:()=>void}){
 return <header className="nav"><a className="brand" href="#top" aria-label="KATHA home">KATHA <small>Human-to-Institution Accessibility Fabric</small></a><div className="nav-actions"><label className="sr-only" htmlFor="language">Language mode</label><select id="language" value={language} onChange={e=>onLanguage(e.target.value as keyof typeof languages)}>{Object.entries(languages).map(([key,label])=><option value={key} key={key}>{label}</option>)}</select><button className="new-application" onClick={onNewApplication}>New Application</button><button className={`demo-nav ${demoOpen?"active":""}`} onClick={onDemo} aria-expanded={demoOpen}>Demo</button></div></header>
}

export function HeroInteraction({speechAvailable,recording,seconds,busy,onSpeak,onType,onEvidence}:{speechAvailable:boolean;recording:boolean;seconds:number;busy:boolean;onSpeak:()=>void;onType:()=>void;onEvidence:()=>void}){
 return <section className="hero" id="top"><p className="kicker">Human-to-Institution Accessibility Fabric</p><h1>Tell KATHA your story.<br/><em>KATHA handles the structure.</em></h1><p className="lede">Speak naturally, share evidence, and KATHA works out what the application already knows, what can be proven, and what still needs you.</p><div className="hero-actions"><button className={`speak ${recording?"recording":""}`} onClick={onSpeak} disabled={!speechAvailable||busy} aria-label={recording?"Stop recording":"Speak to KATHA"}><span className="mic" aria-hidden="true">{recording?"■":"●"}</span>{recording?`Stop · 0:${String(seconds).padStart(2,"0")}`:"Speak to KATHA"}</button><button className="link-button" onClick={onType}>Type instead</button><button className="link-button" onClick={onEvidence}>Upload evidence</button></div><p className={`voice-note ${speechAvailable?"available":""}`}>{speechAvailable?"Live multilingual voice powered by Sarvam":"Live voice unavailable. You can continue by typing."}</p></section>
}

export function DemoGuide({step,onClose}:{step:number;onClose:()=>void}){
 const copy=["Tell KATHA your situation.","Add proof for your income.","Answer what is still missing.","Run Preflight and review readiness."];
 return <aside className="guide" aria-live="polite"><div><span>GUIDED DEMO</span><b>Step {step} of 4</b></div><p>{copy[step-1]}</p><button onClick={onClose} aria-label="Close guided demo">×</button></aside>
}

export function Surface({children,className=""}:{children:ReactNode;className?:string}){return <section className={`surface ${className}`}>{children}</section>}
