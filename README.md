# KATHA
# KATHA

**A Human-to-Institution Accessibility Fabric**

> Speak. Show. Understand. Prove. Access.

KATHA turns human reality into machine-verifiable access. A person should not need the right language, accent, typing ability, digital literacy, or understanding of bureaucracy to access a digital service — the system adapts to the person instead.

---

## Table of Contents

- [The Problem](#the-problem)
- [What KATHA Is](#what-katha-is)
- [Core Concept](#core-concept)
- [System Architecture](#system-architecture)
- [Hardware — KATHA Access Node](#hardware--katha-access-node)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Demo Scenario](#demo-scenario)
- [What Makes KATHA Different](#what-makes-katha-different)
- [Scope of the MVP](#scope-of-the-mvp)
- [Roadmap](#roadmap)
- [Design Principles](#design-principles)
- [License](#license)

---

## The Problem

Digital access today is structured around **forms**. But a form isn't really asking for "fields" — it's asking a person to perform a chain of difficult tasks:

- Understand formal or bureaucratic terminology
- Convert their situation into structured fields
- Know which evidence is required, and whether it's valid
- Repeat the same information across multiple portals
- Resolve contradictions and navigate conditional questions
- Communicate in the "right" language and pronunciation
- Avoid a mistake that could cause rejection

This means **even eligible people can fail to access services** they qualify for.

The real problem isn't "people have difficulty filling forms." It's that **institutions encode access as rigid digital structures, while people communicate through stories, incomplete information, documents, and speech — and there is no persistent semantic layer between the two.**

That is the gap KATHA fills.

---

## What KATHA Is

KATHA is a **Human-to-Institution Accessibility Fabric** delivered through three coordinated surfaces, all powered by the same semantic engine:

| Surface | Description |
|---|---|
| **KATHA Platform** | Web app for uploading forms, discovering opportunities, managing evidence, and completing applications |
| **KATHA Live** | A browser extension that overlays intelligence directly onto existing institutional websites |
| **KATHA Access Node** | A physical edge device for help desks, libraries, NGOs, and public service centres |

The user never has to learn three different systems — KATHA carries the same verified meaning across all of them.

---

## Core Concept

KATHA does not treat a **form** as the fundamental unit of work — it treats the **underlying requirement** as the unit of work.

A PDF might ask *"Aggregate annual household earnings,"* a website might ask *"Gross parental income per annum,"* and another portal might ask *"Annual family income."* To KATHA, all three represent the same concept: `annual_household_income`. This makes KATHA **interface-independent** — different forms can look completely different while representing the same human facts.

### KIR — KATHA Intermediate Representation

KIR sits between the person and the institution:

```
HUMAN SIDE                    INSTITUTION SIDE
speech / documents /    ↔ KIR ↔    PDF / website /
corrections / touch                rules / schemas
```

This separates **what the person means**, **what the institution requires**, and **how the current interface happens to display it**.

### Requirement Graph & Evidence Graph

- **Requirement Graph** — compiled from any form/PDF/website: required facts, eligibility constraints, dependencies, accepted evidence, and conditional rules.
- **Evidence Graph** — built from the human side: facts with full **provenance** (source, confidence, verification status, timestamp, expiry).

### Proof-Carrying Applications

Every consequential answer traces a full chain:

```
Claim → Evidence → Requirement → Decision
```

So for any filled value, KATHA can answer: *"Why is this here?"*

### Requirement ↔ Evidence Matching

Every requirement resolves into one of four states:

| State | Meaning |
|---|---|
| ✓ **PROVEN** | Sufficient, valid evidence exists |
| ? **UNCERTAIN** | Something is known, but needs clarification |
| ○ **MISSING** | Required fact or evidence is absent |
| ⚠ **CONFLICT** | Two sources disagree |

### Bureaucracy Compression

KATHA only asks what's genuinely unresolved:

```
31 fields → 17 resolved from evidence → 6 reused → 3 derived → 2 removed by rules
                                                        ↓
                                          Only 3 actually require the user
```

Quantified as the **Human Burden Ratio (HBR)**:

```
HBR = new facts requiring human input / total requirements
```

Lower is better — this makes accessibility a measurable engineering outcome, not just a claim.

---

## System Architecture

```
                        USER
                          │
        ┌─────────┬───────┼───────┬─────────┐
        Voice     Touch   Document   Text
                          │
                          ▼
              KATHA EDGE RUNTIME
        (audio preprocessing, personal lexicon,
         local session, evidence cache,
         deterministic rules, sync manager)
                          │
                          ↕
                  KATHA CLOUD
     (Sarvam STT/TTS, multilingual interpretation,
      document intelligence, semantic extraction)
                          │
                          ▼
                    KATHA IR
          (Evidence Graph + Requirement Graph)
                          │
                          ▼
              Reasoning + Preflight
                          │
        ┌─────────────────┼─────────────────┐
     Platform          Extension        Access Node
```

**Guiding principle:** *AI interprets. Deterministic systems decide.*

- **AI** handles: speech interpretation, semantic mapping proposals, document understanding, jargon explanation.
- **Deterministic logic** handles: validation, requirement states, evidence sufficiency, rule evaluation, contradictions, readiness, and submission gating.

This is what keeps KATHA trustworthy rather than a black box that quietly guesses.

---

## Hardware — KATHA Access Node

A physical, two-tier system designed to be buildable without custom PCBs or embedded UI work.

```
┌─────────────────────┐   Serial/WiFi   ┌──────────────────────────┐
│   ESP32 DEV KIT       │◄──────────────►│         LAPTOP             │
│  (Physical Layer)     │                 │   (Compute + UI Layer)     │
│  • Push-to-talk button │                │  • Camera (doc capture)    │
│  • Status LED           │                │  • Microphone / Speaker     │
└─────────────────────┘                 │  • Browser (KATHA UI)       │
                                          │  • Backend (FastAPI)        │
                                          └──────────────────────────┘
```

- **ESP32** acts purely as a tactile front panel: reads the push-to-talk button, drives the status LED (ready / listening / processing / confirm), and sends/receives simple event codes to the laptop over USB serial or WiFi.
- **Laptop** does all the real work: camera capture for documents, microphone/speaker for voice interaction, and renders the actual KATHA Platform UI in a browser.
- **Resilient Edge Mode:** if connectivity drops, already-verified facts, cached session state, and deterministic rules keep working locally; cloud-only tasks queue and sync once connectivity returns.

Full component list, wiring notes, and communication protocol are in [`/hardware/README.md`](./hardware/README.md).

---

## Key Features

- **KATHA Adapt** — learns the user's pronunciation, code-switching habits, and vocabulary over time (e.g., a misheard "VIT Valor" is corrected once to "VIT Vellore" and never mismatched again).
- **Multimodal personalization** — verified document text (e.g., an ID) can correct uncertain speech recognition.
- **No silent guessing** — approximate or uncertain claims are stored as such (`income ≈ ₹4L, status: approximate`) and never silently promoted to official values for high-stakes fields.
- **Minimum Question Planner** — asks the single question or requests the single document that resolves the most outstanding requirements at once.
- **Access Path Planning** — surfaces the smallest legitimate next step that unlocks the most access across multiple opportunities.
- **KATHA Preflight** — a pre-submission check for missing evidence, expired documents, contradictions, and unresolved requirements before anything is submitted.
- **KATHA Lens** — overlays plain-language explanations directly on confusing form fields (meaning, why it's needed, what proves it, current status).
- **Ask the Form** — lets users interrogate the process itself ("Why are they asking this?", "What's blocking me?"), answered by tracing the Requirement Graph.
- **KATHA Focus Mode** — hides everything already resolved, showing only what still needs the user's attention.
- **Cross-device continuity** — a fact verified at a physical Access Node is instantly recognized later on a laptop via the browser extension.
- **Semantic Process Diff** *(secondary)* — compares two versions of a process (e.g., a scheme's 2025 vs 2026 rules) semantically, not as a text diff.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Browser Extension | Chrome Extension (Manifest V3) |
| Backend | FastAPI (Python) |
| Data Contracts | Pydantic (`Claim`, `Evidence`, `Requirement`, `KIRNode`, `ApplicationState`) |
| Speech | Sarvam AI (multilingual Indian-language STT/TTS) |
| Documents | PDF / OCR / document extraction pipeline |
| Storage | PostgreSQL / Supabase |
| Edge Compute | Python edge service (on laptop or Raspberry Pi, as applicable) |
| Edge Local Storage | SQLite |
| Hardware | ESP32 Dev Kit (button, LED), laptop (camera, mic, speaker, display) |

---

## Repository Structure

```
katha/
├── platform/           # Next.js web application
├── extension/          # KATHA Live browser extension (Manifest V3)
├── backend/            # FastAPI services — reasoning, graphs, rules
│   ├── models/         # Pydantic contracts (Claim, Evidence, Requirement, KIR)
│   ├── graphs/          # Requirement Graph + Evidence Graph logic
│   ├── compiler/        # PDF / website → Requirement Graph compiler
│   └── preflight/       # Preflight validation engine
├── hardware/            # ESP32 firmware + Access Node build guide
│   ├── firmware/        # Arduino/ESP-IDF button + LED + serial/WiFi code
│   └── laptop-listener/ # Python listener script (serial/HTTP)
├── data/                # Synthetic/demo schemas and fixtures
└── docs/                # Architecture notes, schemas, demo script
```

---

## Getting Started

> This is a hackathon MVP — setup steps below are illustrative and should be adjusted to match the actual repo once code is in place.

```bash
# Clone the repository
git clone https://github.com/<your-org>/katha.git
cd katha

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Platform (frontend)
cd ../platform
npm install
npm run dev

# Browser Extension
cd ../extension
npm install
npm run build
# then load /extension/dist as an unpacked extension in Chrome

# Hardware (optional)
# Flash /hardware/firmware to the ESP32 Dev Kit via Arduino IDE
# Run the laptop-side listener:
cd ../hardware/laptop-listener
python listener.py
```

Environment variables (Sarvam API keys, database URL, etc.) go in a `.env` file — see `.env.example`.

---

## Demo Scenario

A short walkthrough of the intended live demo:

1. **Paper** — a fictional scholarship form is shown to the Access Node's camera; KATHA compiles it into a Requirement Graph.
2. **Speak** — the push-to-talk button is pressed; a user speaks naturally in a code-mixed Indian language.
3. **Personalize** — KATHA mishears a local proper noun, the user corrects it once, and KATHA remembers it going forward.
4. **Show** — a fictional income certificate is captured; the value is extracted and marked as document-verified.
5. **Handle conflict safely** — spoken "around four lakh" vs. a certificate's exact value is reconciled without hallucinating a false match.
6. **Compress** — the interface animates from "27 visible fields" down to "only 2 questions for you."
7. **Preflight** — a missing certificate blocks submission until resolved; once uploaded, the application becomes ready.
8. **Cross-device** — the same verified facts are recognized moments later on a completely different web application via the browser extension.
9. **Adaptation payoff** — the earlier-corrected term is now recognized correctly the first time.
10. **Technical reveal** — clicking "Why is this application ready?" expands the full Requirement → Claim → Evidence → Rule chain.

> All demo documents, names, and figures are **fictional and synthetic**, created solely for demonstration purposes.

---

## What Makes KATHA Different

Existing tools already offer translation, OCR, speech-to-text, PDF autofill, browser autofill, and chatbots. KATHA's contribution is the **semantic layer above all of these**:

1. Interface-independent semantic representation (KIR)
2. Requirement Graph compiled from any form/PDF/website
3. Evidence Graph with full provenance
4. Requirement ↔ Evidence matching with explicit uncertainty states
5. Proof-Carrying Applications
6. Bureaucracy Compression (measurable via HBR)
7. Personalized semantic adaptation (not just accent correction)
8. Minimum-action planning across requirements and opportunities
9. Preflight rejection prevention
10. Continuity across physical device, browser extension, and platform
11. Hybrid edge-cloud architecture with resilient offline behavior
12. Semantic portability across unrelated institutions

---

## Scope of the MVP

**In scope for the hackathon build:**
- One deep, end-to-end scholarship workflow
- PDF/image form input → Requirement Graph
- Multilingual narrative extraction → Evidence Graph
- Document evidence with provenance and conflict handling
- Bureaucracy Compression + minimum-question logic
- Preflight validation
- Platform + browser extension
- ESP32 + laptop Access Node
- Correction memory and cross-device state reuse

**Explicitly out of scope (to protect focus):**
- Custom acoustic models or fully offline STT
- Custom PCBs or bespoke hardware
- Biometric voice identity
- Auto-submission to real institutional portals
- A generic autonomous browser agent or open-ended RAG chatbot

---

## Roadmap

Starting in **education** (scholarships, admissions, fee waivers, financial aid) because it's relatable and testable, then extending the same engine — only the requirement schemas change — to:

- Public services and government benefits
- Employment and onboarding
- Insurance and banking
- NGO intake and welfare programs

---

## Design Principles

- **Uncertain information never silently becomes official information.**
- **AI interprets. Deterministic systems decide.**
- **Move meaning, not unnecessary raw data** — minimize persistent storage of raw audio/documents.
- **The system adapts to the person — not the other way around.**

---

> *You shouldn't have to learn how the system speaks. The system should learn how you do.*

## License

_Add your chosen license here (e.g., MIT, Apache 2.0)._
