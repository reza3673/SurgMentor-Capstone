# ARCHITECTURE_IMAGE_SPEC.md — SurgMentor Architecture Diagram

**Purpose:** Specification for the architecture PNG to be embedded in the Kaggle writeup and README.  
**Export filename:** `surgmentor_architecture_1600x900.png`  
**Canvas size:** 1600 × 900 px (16:9 landscape)  
**Recommended tool:** Figma, Canva, or any vector tool that can export 1600 × 900 PNG at 1× scale.

---

## 1. Source Verification

All labels and arrows in this spec are derived directly from source code. Do not alter
them to sound better — accuracy is what judges will verify against the repo.

| Spec element | Source of truth |
|---|---|
| Controller loop steps | `surgmentor/agent/controller.py` — `run()` Steps 1–11 comments |
| Security layer checks | `surgmentor/security/layer.py` — `sanitize_input()` / `filter_output()` |
| Skill names | `surgmentor/agent/controller.py` — `_registry` dict |
| Session memory | `surgmentor/memory/session.py` — `InMemorySessionStore` / `SessionState` |
| Evaluation logger | `surgmentor/evaluation/logger.py` — `TurnSignal` / `SessionEvaluation` |
| Retrieval tool | `surgmentor/rag/retrieval_tool.py` — `search_vector_store()` |
| Student stats | `surgmentor/memory/db_store.py` — SQLite tables |
| FastAPI server | `server.py` — endpoint list in module docstring |
| Entry interfaces | `run.py` (CLI), `server.py` + `web/index.html` (web), `app.py` (Gradio) |

---

## 2. Colour Palette

Use these exact hex values. They match the SurgMentor web UI and the COVER_IMAGE_SPEC.

| Role | Hex | Use |
|---|---|---|
| Canvas background | `#FFFFFF` (white) or `#F4F7FA` (near-white) | Full canvas fill |
| Section header band | `#0D1B2A` (deep navy) | Top banner text background |
| Primary blocks | `#1A2B3C` | Non-entry layer cards |
| Entry interface blocks | `#1E6091` (steel blue) | CLI, Web UI, Gradio cards |
| Accent / highlight | `#2ECC8F` (green) | Primary entry marker, skill arrows |
| Text on dark blocks | `#FFFFFF` | All labels inside dark cards |
| Text on light canvas | `#1A2B3C` | Section labels, leader text |
| Arrow colour | `#1E6091` or `#0D1B2A` | Directional flow arrows |
| Gradio block text | `#A0B4C8` (muted) | Explicitly marks optional status |
| Warning / optional | `#A0B4C8` | "optional fallback" label |

---

## 3. Typography

| Element | Size | Weight | Colour |
|---|---|---|---|
| Diagram title | 22–26pt | Bold | `#0D1B2A` on light canvas |
| Layer section labels (① ② ③ ④ ⑤) | 10–11pt | Regular | `#A0B4C8` |
| Block primary label | 11–13pt | Bold | `#FFFFFF` |
| Block secondary label / sub-text | 9–10pt | Regular | `#A0B4C8` or white-70% |
| Arrow labels | 8–9pt | Regular | `#1E6091` |

Font: Inter, Roboto, or system sans-serif. No serif fonts.

---

## 4. Canvas Layout — Six Rows

The diagram flows top-to-bottom. Allocate canvas rows as follows:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ROW 0  Title bar (small)                                               │
│         "SurgMentor — Agentic Surgical OSCE Trainer"                    │
│                                                                         │
│  ROW 1  ① Entry Interfaces  [4 blocks, horizontal]                     │
│         CLI · Custom Web UI (PRIMARY) · Gradio (OPTIONAL) · ─ ─ ─      │
│                                                                         │
│  ROW 2  ② Security Layer  [single wide block, horizontal pair]         │
│         sanitize_input() PRE-FLIGHT ←→ filter_output() POST-FLIGHT     │
│                                                                         │
│  ROW 3  ③ Agent Controller  [ADK loop, horizontal 4-step band]        │
│         PERCEIVE → PLAN → ACT → OBSERVE                                 │
│                                                                         │
│  ROW 4  ④ Skills  [4 blocks, horizontal]                               │
│         CaseRetrieval · OSCEExaminer · Evaluation · StudyPlanner        │
│                                                                         │
│  ROW 5  ⑤ Tool & Data Layer  [5 blocks, horizontal]                   │
│         DeepSeek · Jina + ChromaDB · SQLite · Session Memory · Eval Log │
└─────────────────────────────────────────────────────────────────────────┘
```

Approximate row heights (px of 900 total, after 30 px top/bottom margin):

| Row | Px |
|-----|----|
| Title | 40 |
| ① Entry Interfaces | 110 |
| Gap + arrows | 30 |
| ② Security Layer | 90 |
| Gap + arrows | 30 |
| ③ Agent Controller | 100 |
| Gap + arrows | 30 |
| ④ Skills | 130 |
| Gap + arrows | 30 |
| ⑤ Tool & Data Layer | 100 |
| Remaining margin | ~70 |

---

## 5. Exact Block Specifications

### Row 0 — Title

**Text:** `SurgMentor — Agentic Surgical OSCE Trainer`  
**Position:** Top-left, 30 px from left edge, 14 px from top  
**Style:** 22pt bold, `#0D1B2A`  
**Optional sub-label (right side):** `Kaggle AI Agents Intensive 2026 · Agents for Good` — 10pt, `#A0B4C8`

---

### Row 1 — ① Entry Interfaces

Section label: `① ENTRY INTERFACES` — 9pt, `#A0B4C8`, left-aligned above the row.

Four blocks, left to right:

**Block 1: CLI**
- Label line 1: `CLI`
- Label line 2: `run.py`
- Background: `#1E6091`
- Text: white
- Width: ~180 px

**Block 2: Custom Web UI** ← **MAKE THIS BLOCK VISUALLY PROMINENT**
- Label line 1: `Custom Web UI` (bold, larger)
- Label line 2: `server.py  +  web/index.html`
- Label line 3: `FastAPI · localhost:8000`
- Badge on block: green pill or border: `PRIMARY` in `#2ECC8F`
- Background: `#0D1B2A` (darkest, to stand out as primary)
- Green left-border accent: 4px `#2ECC8F`
- Text: white
- Width: ~280 px (wider than other entry blocks)

**Block 3: Gradio** ← **MARK EXPLICITLY AS OPTIONAL**
- Label line 1: `Gradio`
- Label line 2: `app.py · localhost:7860`
- Label line 3: `optional fallback` — in `#A0B4C8` muted colour, italic
- Background: `#1A2B3C` (muted, lighter than other blocks)
- Dashed or lighter border to visually de-emphasise
- Text: `#A0B4C8` (muted, not bright white) for sub-labels
- Width: ~180 px

All three blocks share a common bottom. Arrows from all three point downward to the Security Layer.

**Arrow below each block:**
- Solid downward arrow, colour `#1E6091`
- Label on the CLI and Web UI arrows: `controller.run(input_text, session_id)` (9pt, only once — place on the arrow from the Web UI block or as a shared annotation between arrows)

---

### Row 2 — ② Security Layer

Section label: `② SECURITY LAYER` — 9pt, `#A0B4C8`.

One wide block spanning the full usable width (~1540 px), split into two halves internally with a thin divider line.

**Left half — PRE-FLIGHT:**
- Header: `sanitize_input()` — 11pt bold white
- Sub-label: `PRE-FLIGHT` — 10pt `#2ECC8F`
- Checks list (9pt, white): `① empty guard` · `② length > 2000 chars` · `③ PII patterns` · `④ injection heuristics` · `⑤ LLM scope (optional)`
- Below checks: `→ SanitizedInput` — 9pt `#A0B4C8`
- Blocked path: small dashed arrow or label `blocked → deflection (no skill called)` pointing right/out

**Right half — POST-FLIGHT:**
- Header: `filter_output()` — 11pt bold white
- Sub-label: `POST-FLIGHT` — 10pt `#2ECC8F`
- Steps list (9pt, white): `① hard-block clinical assertions` · `② OSCE step tag` · `③ medical disclaimer`
- Below steps: `→ FilteredOutput` — 9pt `#A0B4C8`

**Block background:** `#1A2B3C`  
**Divider between halves:** thin `#1E6091` line

**Arrows:**
- Incoming: from entry interface row → left side of block (pre-flight)
- Outgoing (blocked path): small curved arrow back to entry interfaces labelled `deflection`
- Outgoing (pass path): downward arrow from centre of block → Agent Controller

---

### Row 3 — ③ Agent Controller

Section label: `③ AGENT CONTROLLER — surgmentor/agent/controller.py` — 9pt, `#A0B4C8`.

One wide block, internally subdivided into four sequential steps with right-pointing arrows between them. This is the ADK loop — make it visually read left-to-right.

**Step 1 — PERCEIVE:**
- Bold label: `PERCEIVE`
- Sub-text: `read SessionState` / `from InMemorySessionStore`
- Background of step cell: `#0D1B2A`

**Step 2 — PLAN:**
- Bold label: `PLAN`
- Sub-text: `classify_intent()` / `OSCE override` / `build ContextBundle`
- Background of step cell: `#0D1B2A`

**Step 3 — ACT:**
- Bold label: `ACT`
- Sub-text: `invoke skill` / `(controller never calls LLM directly)`
- Background of step cell: `#0D1B2A`

**Step 4 — OBSERVE:**
- Bold label: `OBSERVE`
- Sub-text: `post-flight filter` / `log TurnSignal` / `update + write state`
- Background of step cell: `#0D1B2A`

**Connector arrows between steps:** `→` in `#2ECC8F` (green), thick enough to read at thumbnail size.

**Overall block background:** `#1A2B3C` with `#0D1B2A` step cells.  
**Downward arrow** from ACT step → Skills row.  
**Upward arrow** from OBSERVE step → Security Layer (post-flight), labelled `post-flight`.  
**Upward arrow** from PERCEIVE step → Session Memory block (row 5), labelled `read / write`.

---

### Row 4 — ④ Skills

Section label: `④ SKILLS — surgmentor/skills/` — 9pt, `#A0B4C8`.

Four blocks, left to right. Equal width (~350 px each, with small gaps). All have `#1A2B3C` background, `#1E6091` 1px border.

**Block 1: CaseRetrievalSkill**
- Label: `CaseRetrievalSkill`
- Sub-text: `embed query via Jina` / `ChromaDB cosine search` / `weak-area bias` / `top-3 with citations`
- Bottom arrow: → ChromaDB (row 5), → DeepSeek (row 5)

**Block 2: OSCEExaminerSkill**
- Label: `OSCEExaminerSkill`
- Sub-text: `_init()  seed case + Q1` / `_turn()  examiner follow-up` / `_finish()  → EvaluationSkill`
- Bottom arrow: → DeepSeek (row 5)

**Block 3: EvaluationSkill**
- Label: `EvaluationSkill`
- Sub-text: `rubric score 0–10` / `extract weak_areas` / `persist to SQLite`
- Bottom arrow: → DeepSeek (row 5), → SQLite (row 5)

**Block 4: StudyPlannerSkill**
- Label: `StudyPlannerSkill`
- Sub-text: `read weak_areas from SQLite` / `generate personalised plan`
- Bottom arrow: → DeepSeek (row 5), → SQLite (row 5) (read arrow)

---

### Row 5 — ⑤ Tool & Data Layer

Section label: `⑤ TOOL & DATA LAYER` — 9pt, `#A0B4C8`.

Five blocks, left to right. Smaller height than skill blocks (~80 px). `#1A2B3C` background, `#1E6091` border.

**Block 1: DeepSeek LLM**
- Label: `DeepSeek LLM`
- Sub-text: `deepseek-chat` / `OpenAI-compatible API`

**Block 2: Jina + ChromaDB**
- Label: `Jina  +  ChromaDB`
- Sub-text: `jina-embeddings-v3` / `1024 dims · ./db/`

**Block 3: SQLite**
- Label: `SQLite`
- Sub-text: `data/students.db` / `profiles · OSCE results`

**Block 4: Session Memory**
- Label: `Session Memory`
- Sub-text: `InMemorySessionStore` / `SessionState per session`
- Bidirectional arrow to/from PERCEIVE (Agent Controller row)

**Block 5: Eval Log**
- Label: `eval_log.jsonl`
- Sub-text: `TurnSignal per cycle` / `SessionEvaluation per OSCE`
- Incoming arrow from OBSERVE step, labelled `write`

---

## 6. Arrow Map

All arrows are directional. Arrowhead on the destination end only (single-headed).

| From | To | Label | Style |
|------|----|-------|-------|
| CLI block | Security Layer (pre-flight) | *(unlabelled or shared label below)* | solid |
| Custom Web UI block | Security Layer (pre-flight) | `controller.run(input_text, session_id)` | solid |
| Gradio block | Security Layer (pre-flight) | *(unlabelled)* | dashed (optional) |
| Security Layer (blocked path) | *(exit, right edge)* | `deflection` | dashed, outward |
| Security Layer (pre-flight pass) | Agent Controller PERCEIVE | *(unlabelled)* | solid |
| Agent Controller OBSERVE | Security Layer (post-flight) | `post-flight filter` | solid, upward |
| Security Layer (post-flight) | Entry interfaces | `safe response` | solid, upward |
| Agent Controller ACT | Skills (all 4) | *(fan-out arrows)* | solid |
| Agent Controller PERCEIVE | Session Memory | `read / write` | solid bidirectional |
| Agent Controller OBSERVE | Eval Log | `write TurnSignal` | solid |
| CaseRetrievalSkill | Jina + ChromaDB | *(unlabelled)* | solid |
| CaseRetrievalSkill | DeepSeek LLM | *(unlabelled)* | solid |
| OSCEExaminerSkill | DeepSeek LLM | *(unlabelled)* | solid |
| EvaluationSkill | DeepSeek LLM | *(unlabelled)* | solid |
| EvaluationSkill | SQLite | `persist result` | solid |
| StudyPlannerSkill | SQLite | `read weak_areas` | solid |
| StudyPlannerSkill | DeepSeek LLM | *(unlabelled)* | solid |

**Arrow colours:**  
- Solid data-flow arrows: `#1E6091`  
- Optional/fallback arrows (Gradio): dashed `#A0B4C8`  
- OSCE step tag / response return arrows: `#2ECC8F`

---

## 7. What Must NOT Appear in the Image

| Forbidden element | Reason |
|---|---|
| "OSCE Certified" | Not a real certification — misleading |
| "MCP" or "Model Context Protocol" | Not implemented in this project |
| "A2A" or "Agent-to-Agent" | Not implemented |
| Telegram logo or Telegram references | Telegram bot is a separate reference project, not part of this system |
| Any external service not actually used (e.g., AWS, GCP, Firebase) | Accuracy requirement |
| "Gradio" shown as primary or equal-weight to Custom Web UI | Gradio is explicitly optional fallback — must be visually subordinate |
| Any claim of clinical validation, hospital approval, or regulatory compliance | Prohibited — educational tool only |

---

## 8. Thumbnail-Readiness Guidelines

The image appears at three sizes: full 1600×900 (Kaggle writeup), ~400×225 (Kaggle card thumbnail), and possibly 1280×720 or smaller in YouTube video.

Rules to ensure it reads at all three sizes:

1. **Minimum font size for block labels: 11pt at 1×.** Text smaller than this will be illegible at thumbnail.
2. **Sub-text inside blocks (9–10pt):** acceptable to be unreadable at thumbnail — the block structure and label are what matter.
3. **Arrow stroke width: 2px minimum.** 1px arrows disappear at thumbnail. Use 2–3px.
4. **Block borders: 1–2px.** Thinner than 1px will not render at small scale.
5. **Five-row structure must read as five distinct bands** at thumbnail. Achieved by alternating background tones or clear horizontal spacing (20–30 px gap between rows).
6. **PERCEIVE → PLAN → ACT → OBSERVE** must be legible at 400 px wide. Use 12pt+ for these four step labels.
7. **"PRIMARY" badge on Custom Web UI block** must contrast clearly against the block background.
8. **"optional fallback" text on Gradio block** does not need to be readable at thumbnail — the muted block colour communicates subordinate status visually.

---

## 9. Optional: Simplified Thumbnail Variant

If the detailed version is too dense at 400×225, prepare a second pass at reduced complexity:

- Merge the two Security Layer halves into one block labelled `Security Layer (pre + post)`
- Merge the five data-layer blocks into two: `LLM + Embeddings + Vector Store` and `SQLite + Eval Log + Session`
- Keep all five rows; keep all four skill blocks; keep the ADK loop labels
- Export as `surgmentor_architecture_1600x900_simplified.png`

Use the simplified variant only if the detailed variant is illegible at thumbnail.

---

## 10. Export Instructions

1. Set canvas to exactly **1600 × 900 px** before drawing anything.
2. Export at **1× scale** (not 2×) — the target is exactly 1600×900 px in the file.
3. Format: **PNG** (not JPG — compression artefacts degrade text readability).
4. File name: `surgmentor_architecture_1600x900.png`
5. Place a copy in the project root. Do NOT commit to git (it is a generated asset).
6. Open the exported PNG in an image viewer and verify pixel dimensions read 1600 × 900.

---

## 11. Validation Checklist

Before using the image in the submission, verify every item below.

### Content accuracy

- [ ] All five rows present: Entry Interfaces, Security Layer, Agent Controller, Skills, Tool & Data Layer
- [ ] Entry interfaces show exactly three sources: CLI (`run.py`), Custom Web UI (`server.py + web/index.html`), Gradio (`app.py`) — no more, no fewer
- [ ] Custom Web UI is visually primary (prominent block, green accent, `PRIMARY` badge or equivalent)
- [ ] Gradio is visually subordinate (muted colour, `optional fallback` label, dashed arrow or lighter border)
- [ ] Security Layer shows both `sanitize_input()` and `filter_output()` — both labelled as PRE-FLIGHT and POST-FLIGHT respectively
- [ ] Agent loop shows exactly four steps in order: `PERCEIVE → PLAN → ACT → OBSERVE`
- [ ] PERCEIVE sub-text references `SessionState` or `InMemorySessionStore` (matches `session.py`)
- [ ] PLAN sub-text references `classify_intent()` and OSCE override (matches `controller.py` Steps 3–4)
- [ ] ACT sub-text states controller does NOT call LLM directly (matches `controller.py` Step 7 comment)
- [ ] OBSERVE sub-text references `TurnSignal` or eval log (matches `controller.py` Step 11)
- [ ] Exactly four skills shown: `CaseRetrievalSkill`, `OSCEExaminerSkill`, `EvaluationSkill`, `StudyPlannerSkill`
- [ ] `OSCEExaminerSkill` sub-text shows the three phases: `_init()`, `_turn()`, `_finish()`
- [ ] `EvaluationSkill` sub-text mentions SQLite persistence (matches `evaluation_skill.py`)
- [ ] `StudyPlannerSkill` sub-text mentions reading weak_areas from SQLite (matches `study_planner_skill.py`)
- [ ] Data layer includes: DeepSeek LLM, Jina + ChromaDB, SQLite, Session Memory (InMemorySessionStore), eval_log.jsonl
- [ ] `eval_log.jsonl` block shows `TurnSignal` (matches `logger.py`)
- [ ] No "OSCE Certified", "MCP", "A2A", or Telegram references anywhere in the image
- [ ] No fabricated services (AWS, Firebase, Redis, etc.) shown

### Visual quality

- [ ] Canvas is exactly 1600 × 900 px (verify in image properties)
- [ ] All block primary labels readable at 1600×900 (≥ 11pt)
- [ ] ADK step labels (PERCEIVE/PLAN/ACT/OBSERVE) readable at 400 px width
- [ ] Arrows have arrowheads and are at least 2px stroke width
- [ ] Gradio block is visually distinguishable from CLI and Web UI blocks (muted, dashed, or smaller)
- [ ] Five rows clearly separated — not a single visual blob
- [ ] Background is white or near-white (not navy — navy is for the cover image, not the architecture diagram)

### File

- [ ] Exported as PNG (not JPG)
- [ ] Filename: `surgmentor_architecture_1600x900.png`
- [ ] File size reasonable (50–500 KB for a vector-exported PNG at this resolution)
- [ ] File opens correctly in a browser (drag to Chrome to verify)
