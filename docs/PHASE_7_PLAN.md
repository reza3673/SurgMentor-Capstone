# PHASE_7_PLAN.md — Submission Deliverables

**Project:** SurgMentor — Agentic Surgical Education System  
**Phase:** 7 of 7  
**Date:** 2026-06-20  
**Deadline:** July 6, 2026 at 11:59 PM PT (17 days from today)  
**Status:** Awaiting approval  
**Authoritative sources:** IMPLEMENTATION_SEQUENCE_REVIEW.md, README.md,
  docs/architecture.md, project_docs/competition_Overview.md,
  project_docs/00_competition_rules.md

---

## 1. Objectives

Produce and submit all four required submission components before the July 6, 2026
deadline. Nothing in Phase 7 changes the codebase — the system is implemented,
tested, and documented. Phase 7 is entirely about packaging and communicating what
was built.

**Specific objectives:**

1. Publish the GitHub repository with a clean, no-secrets codebase.
2. Record and upload a 5-minute YouTube demo video.
3. Write and submit the Kaggle writeup (≤ 2,500 words).
4. Attach a cover image, the video, and the GitHub link to the Kaggle submission.
5. Submit in the **Agents for Good** track before the deadline.

**Judging criteria (from competition_Overview.md):**

| Category | Criterion | Points |
|----------|-----------|--------|
| **The Pitch** | Core Concept & Value | 10 |
| **The Pitch** | YouTube Video | 10 |
| **The Pitch** | Writeup | 10 |
| **The Implementation** | Technical Implementation | 50 |
| **The Implementation** | Documentation (README) | 20 |
| **Total** | | **100** |

**Course concepts demonstrated (minimum 3 required):**

| Concept | Where demonstrated | Status |
|---------|-------------------|--------|
| Agent / ADK system | `surgmentor/agent/controller.py` — ADK loop Steps 1–11 | ✅ Done |
| Security features | `surgmentor/security/layer.py` — pre/post-flight | ✅ Done |
| Deployability | `run.py` CLI + `server.py` FastAPI + `app.py` Gradio fallback + README | ✅ Done |
| Agent skills | `surgmentor/skills/` — 4 composable skills | ✅ Done |
| MCP Server | `surgmentor/mcp/server.py` placeholder only | ⬜ Stretch |
| Antigravity | Course-specific concept — mention in video | ⬜ Optional |

Three required concepts (ADK, Security, Deployability) are fully implemented
and documented. Agent Skills is a fourth bonus concept also satisfied.

**What Phase 7 does NOT include:**

- Any code changes (the system is feature-complete at Phase 6)
- MCP implementation (stretch goal — skip if time is tight)
- A2A multi-agent topology (stretch goal)
- Hugging Face Spaces deployment (optional — GitHub link is sufficient per rules)

---

## 2. Kaggle Submission Checklist

These are the four mandatory submission components per competition_Overview.md.
All four must be attached to the Kaggle Writeup before submitting.

```
□  Kaggle Writeup (≤ 2,500 words)
     □  Title set: "SurgMentor — Agentic Surgical OSCE Trainer"
     □  Subtitle set: "AI agents for surgical resident education"
     □  Track selected: Agents for Good
     □  Writeup body complete (see §7 for outline)
     □  Word count verified: ≤ 2,500

□  Media Gallery
     □  Cover image attached (see §8)
     □  YouTube video attached (see §6)

□  Video
     □  Uploaded to YouTube (public or unlisted)
     □  ≤ 5 minutes (target: 4:30–4:50 to give buffer)
     □  URL added to Kaggle submission

□  Public Project Link
     □  GitHub repository URL attached
     □  Repository is public (not private)
     □  Repository passes no-secrets audit (see §4)

□  Submission button clicked before July 6, 2026 11:59 PM PT
```

**One-submission rule:** Each team/individual may submit exactly one entry.
Do not click submit until all four components are ready. Draft writeups that
are not submitted by the deadline are not considered.

---

## 3. GitHub Publishing Checklist

This is the sequence to follow when publishing the repository. Do not push
until every check passes.

```
Pre-publish preparation
  □  Run no-secrets audit (§4) — all 9 checks pass
  □  Verify README.md is complete — no "<!-- TODO -->" markers remain
  □  Verify .env.example contains no real values — only placeholders
  □  Verify .gitignore excludes .env, data/*.db, eval_log.jsonl
  □  Decide: include or exclude pre-built db/ (see §5)
  □  Update .gitignore accordingly for the db/ decision
  □  Confirm LICENSE file present (currently MIT — see license note below)
  □  Verify tests pass: CI_NO_LLM=1 CI_NO_GRADIO=1 python -m unittest discover -s tests -v
       Expected: 252 tests, 0 failures, 11 skipped

Repository setup (manual — no Claude tools)
  □  Create new public GitHub repository (suggested name: SurgMentor-Capstone)
  □  Set description: "Agentic surgical OSCE trainer — Kaggle AI Agents Intensive 2026"
  □  Add topics: medical-education, ai-agents, osce, surgical-education, python, gradio
  □  Do NOT initialize with a README — push the local files instead

Publishing sequence
  □  git init (local)
  □  git add . (after verifying .gitignore is correct)
  □  git status — review list of tracked files, confirm no .env, no db if excluded
  □  git commit -m "SurgMentor Phase 6 complete — competition-ready submission"
  □  git remote add origin <repo-url>
  □  git push origin main

Post-publish verification
  □  Open the GitHub repository in a browser
  □  README.md renders correctly — Mermaid diagram visible
  □  No .env file visible in the file tree
  □  No API keys visible in any file (spot-check config.py, clients.py, .env.example)
  □  Kaggle competition link added to the GitHub repo's "About" section
  □  Copy the GitHub URL for the Kaggle submission
```

**License note:** The current `LICENSE` file is MIT. The competition rules state
that winners must grant CC-BY 4.0 to the sponsor — this is an additional license
grant, not a replacement. Keeping MIT is legal. However, the old README skeleton
said "CC-BY 4.0 as required by Kaggle". Options:
- **Option A (current):** MIT — standard open source, compatible with the spirit
  of the rules. Simplest.
- **Option B:** CC-BY 4.0 — matches the explicit winner license grant. Slightly
  less conventional for software (CC-BY is more common for content than code).

Recommendation: keep MIT. If SurgMentor wins, the winner's obligations section
requires a CC-BY 4.0 grant regardless of what the LICENSE file says — both can
coexist. No action needed.

---

## 4. No-Secrets Final Audit

Run these commands from the repository root before every `git push`.
All must pass before the repository is made public.

```bash
# Check 1: No API key values starting with sk- in any .py file
grep -r "sk-" surgmentor/ run.py app.py config.py clients.py
# Expected: zero output

# Check 2: No jina_ key values in any .py file
grep -r "jina_" surgmentor/ run.py app.py
# Expected: zero output

# Check 3: .env in .gitignore
grep "^\.env$" .gitignore
# Expected: .env

# Check 4: .env.example contains only placeholders (no real key values)
grep "API_KEY=" .env.example
# Expected: lines like DEEPSEEK_API_KEY=your-deepseek-api-key-here

# Check 5: No hardcoded api_key= values (must only reference config variables)
grep -r "api_key=" surgmentor/ run.py app.py config.py | grep -v "os.getenv\|config\."
# Expected: zero output

# Check 6: Student database excluded from tracking
grep "data/\*\.db" .gitignore
# Expected: data/*.db

# Check 7: eval_log.jsonl excluded
grep "eval_log" .gitignore
# Expected: eval_log.jsonl

# Check 8: No Telegram credentials (reference repo had these — must not leak)
grep -r "TELEGRAM\|BOT_TOKEN\|telegram_id" surgmentor/ run.py app.py config.py | grep -v "# "
# Expected: zero output (or only comment references)

# Check 9: No actual key strings in any tracked file
git diff --cached --name-only | xargs grep -l "sk-\|jina_api" 2>/dev/null
# Expected: zero output (after git add, before commit)
```

**Critical rule:** If any check fails, stop immediately. Do not push.
Resolve the issue, then re-run all 9 checks from the top.

---

## 5. Decision: Include or Exclude Pre-built db/

### Context

The `./db/` directory contains the ChromaDB vector store (5MB, 5 surgical cases).
The current `.gitignore` excludes it (`db/*.sqlite3`, `db/*/`).

If judges must rebuild from scratch, they need:
- A Jina AI API key
- ~2 minutes of wall-clock time running `python scripts/02_embed_and_store.py`

If the db/ is included, judges can run the system immediately after:
```bash
pip install -r requirements.txt
cp .env.example .env  # only DEEPSEEK_API_KEY required
python run.py
```

### Analysis

| Factor | Include db/ | Exclude db/ |
|--------|------------|-------------|
| Setup for judges | Requires only DeepSeek key | Requires both DeepSeek + Jina keys + 2 min |
| Repo size | +5 MB | No change |
| Reproducibility | Judges can verify by rebuilding anyway | Forces rebuild, verifies pipeline |
| Risk of version mismatch | db/ breaks if judge's chromadb differs from 0.5.23 | No risk — fresh build always works |
| gitignore change needed | Yes — remove db/ exclusions | No change |

**5 cases is a tiny dataset.** The 5MB size is negligible. The primary purpose
of `scripts/02_embed_and_store.py` in a demo context is to show the pipeline
exists — judges who want to run it can. But reducing the setup barrier matters:
every required step is a potential judge dropout.

### Recommendation: **INCLUDE db/**

Include the pre-built ChromaDB with the following `.gitignore` change:

```
# Old (current):
db/*.sqlite3
db/*/
!db/.gitkeep

# New:
# db/ included in repo for judge convenience
# test files excluded
db/test.sqlite3
db/test.sqlite3-journal
db/write_test.txt
```

Also add a note to the README setup section:
> The pre-built vector database (5 cases) is included in the repository.
> Steps 4–5 (data pipeline) can be skipped. To verify or rebuild from scratch,
> run `python scripts/01_prepare_data.py` then `python scripts/02_embed_and_store.py`.

**If the recommendation is rejected** (exclude db/): The README must make
the Jina API key acquisition step prominent, and both keys must be mentioned
equally in the prerequisites section. No other changes needed.

---

## 6. YouTube Video Script

**Target duration:** 4:30 to 4:50 (never exceed 5:00)  
**Recording setup:** Screen capture of browser + VS Code, with voiceover.
No face camera required.  
**What to have open before recording:**
- `python -m uvicorn server:app --host 0.0.0.0 --port 8000` running; browser at `http://localhost:8000`
- VS Code open to `surgmentor/agent/controller.py`, pinned at the `run()` method
- Terminal open for the eval_log inspection in Segment 5

---

### Segment 1 — Problem (0:00–0:45, 45 seconds)

**[Show: blank slide or title card with "SurgMentor"]**

> "Surgical residents learn clinical reasoning through OSCE examinations — Objective
> Structured Clinical Examinations. In an OSCE, a trained examiner presents a patient
> case, asks a series of structured questions, and scores the trainee's clinical
> reasoning. OSCEs are the gold standard for surgical education.
>
> The problem: expert examiners are scarce and expensive. A resident in a major
> teaching hospital might get a few hours of OSCE practice per week. A resident in a
> smaller hospital or a lower-resource setting gets far less — and clinical reasoning
> is a skill that degrades without deliberate practice.
>
> SurgMentor is an agent that acts as that examiner. It's available 24/7, adapts to
> the student's learning gaps, and gives structured, scored feedback after every
> session."

---

### Segment 2 — Why Agents? (0:45–1:30, 45 seconds)

**[Show: architecture diagram from docs/architecture.md — rendered in browser or VS Code]**

> "A RAG pipeline alone can't solve this problem. RAG can fetch a relevant case —
> but it can't maintain a multi-turn examination, apply a consistent rubric, switch
> between teaching and examining modes, or adapt to a student's specific weak areas.
>
> An agent loop adds what RAG can't: intent classification — so the system knows
> whether to retrieve a case or conduct an exam. Session-level memory — so the
> examiner remembers every answer in the session. Skill composition — four independently
> testable skills that the controller routes to based on context. And evaluation —
> every turn writes a structured signal to an eval log.
>
> This is the design the AI Agents Intensive course teaches, and it's exactly the right
> design for this problem."

---

### Segment 3 — Architecture (1:30–2:30, 60 seconds)

**[Show: docs/architecture.md Mermaid diagram — stay on this view the whole segment]**

> "Here's the full architecture. Five layers.
>
> Entry interfaces — a CLI, a custom FastAPI web application, and an optional Gradio fallback. All call the same controller.
>
> Security layer — pre-flight input sanitization: PII detection, prompt injection
> heuristics, length limits. Post-flight output filtering: medical disclaimer
> injection, hard-block pattern removal. Two passes, every turn, no exceptions.
>
> The agent controller — this is the ADK loop. Perceive: read session state.
> Plan: classify intent, apply the OSCE override rule, build a trimmed context
> bundle. Act: invoke the skill. Observe: filter output, log a TurnSignal,
> update session state.
>
> Four skills: CaseRetrievalSkill searches ChromaDB with weak-area bias.
> OSCEExaminerSkill runs the three-phase examination — init, turn, finish.
> EvaluationSkill scores sessions with a structured rubric. StudyPlannerSkill
> generates personalised remediation plans from historical weak areas.
>
> At the bottom: ChromaDB for vectors, SQLite for student profiles,
> and eval_log.jsonl — one JSON object per turn, machine-readable."

---

### Segment 4 — Live Demo (2:30–4:00, 90 seconds)

**[Show: browser at localhost:8000 — SurgMentor custom web UI]**

> "Here's the system running. Three views: Chat, OSCE, and Profile — accessed via
> navigation pills at the top.
>
> [Chat view active — type: 'show me a case about right iliac fossa pain']
> The agent classifies this as RETRIEVE_CASE. CaseRetrievalSkill searches ChromaDB,
> biases the query toward this student's weak areas, and returns the top cases with
> source citations.
>
> [Click OSCE nav pill — click Start Session]
> Now it classifies as START_OSCE. The OSCEExaminer presents a patient case —
> [read first line of the case aloud] — and asks the opening question. The six-step
> progress indicator advances to Step 1.
>
> [Type a clinical response]
> The OSCE override rule means every input while a session is active goes to
> OSCEExaminerSkill, regardless of what the intent classifier says. The examiner
> follows up and the step counter advances.
>
> [Give one more response, then click End & Score]
> EvaluationSkill scores the session. [Read the score aloud]. The score panel appears
> with weak areas extracted and study recommendations listed.
>
> [Click Profile nav pill — click Refresh Stats]
> This session is now in the historical record, and StudyPlannerSkill reads
> these weak areas to generate a personalised study plan."

---

### Segment 5 — Code Highlight (4:00–4:30, 30 seconds)

**[Show: VS Code open to surgmentor/agent/controller.py, scrolled to run() method]**

> "Two things to point out in the code.
>
> The controller's run() method — you can see the ADK pattern explicitly labelled:
> PERCEIVE, PLAN, ACT, OBSERVE. Every input passes through SecurityLayer.sanitize_input
> before the controller sees it, and SecurityLayer.filter_output before the student
> sees the response.
>
> And the eval log — after this demo, eval_log.jsonl has one JSON entry per turn.
> Structured evaluation signals, machine-readable, no extra tooling required."

---

### Segment 6 — Wrap (4:30–4:50, 20 seconds)

**[Show: GitHub repository page]**

> "SurgMentor is open source. The repository is linked in the submission — 252 tests,
> full setup in four commands. Agents for Good track: making structured surgical
> education available without requiring an expert examiner to be present.
>
> Thank you."

---

**Recording notes:**

- Keep browser zoom at 100% for readability in 1080p
- Disable notifications before recording
- Use `python -m uvicorn server:app --host 0.0.0.0 --port 8000` to launch the primary web UI
- If the LLM response takes more than 10 seconds during the demo, note: "Responses
  typically take 1–2 seconds; this is a development machine without the production
  setup"
- Do not show the uvicorn terminal during the demo segment to avoid exposing paths
- The eval log inspection command can be shown in the terminal after the Gradio demo
  if time permits

---

## 7. Kaggle Writeup Outline (≤ 2,500 words)

**Title:** SurgMentor — Agentic Surgical OSCE Trainer  
**Subtitle:** AI agents for on-demand surgical resident education  
**Track:** Agents for Good  
**Target length:** 1,800–2,000 words (leaves buffer for the 2,500 word cap)

Content maps directly to the README and architecture.md — do not duplicate
work; adapt and expand.

---

### § 1 — The Problem (200 words)

Reproduce and expand on README § "The Problem". Three paragraphs:

**Paragraph 1 — The setting:** Surgical residency and the OSCE examination.
What an OSCE is, why it's the gold standard, what makes it work (an expert
examiner who can ask, probe, and score in real time).

**Paragraph 2 — The gap:** Expert examiners are scarce and expensive.
Availability is unevenly distributed — major academic centres vs. smaller
hospitals vs. lower-resource settings. The consequence is measurable: fewer
practice opportunities → weaker clinical reasoning development.

**Paragraph 3 — The specific constraint:** This is not a general AI tutor problem.
The gap is specifically in the examiner role — the structured, multi-turn,
scored interaction. SurgMentor targets that role precisely.

---

### § 2 — Why Agents? (250 words)

Reproduce and expand on README § "Why Agents?". Structured as a contrast:

**What RAG alone provides:** Case retrieval. One-shot question answering.
Useful but insufficient. A student can ask "what are the signs of appendicitis"
and get a good answer. But an OSCE is not a Q&A session.

**What an agent adds that RAG cannot:**
- Session-level state: the examiner must remember every previous answer
- Intent-aware routing: teaching mode vs. examination mode vs. remediation mode
- Consistent rubric application: evaluation must be deterministic and structured,
  not improvised
- Adaptive personalisation: study recommendations must be based on the student's
  specific weak areas from prior sessions, not general advice
- Evaluation signals: every turn must produce a structured log entry for post-hoc
  analysis

**The course connection:** The AI Agents Intensive course teaches exactly this
distinction. SurgMentor is a deliberate demonstration of why agents are the right
abstraction for this class of problem.

---

### § 3 — Architecture (400 words)

**Open with the Mermaid diagram** (embed from docs/architecture.md).

Then one paragraph per layer:

**Entry Interfaces:** Two thin wrappers — `run.py` (CLI) and `app.py` (Gradio).
Both call `controller.run(input, session_id)`. No business logic in the UI layer.

**Security Layer (`security/layer.py`):** Pre-flight sanitization (PII regex,
prompt injection heuristics, length guard, LLM scope classification) and post-flight
output filtering (medical disclaimer, OSCE step tags, hard-block clinical assertions).
Named, independently testable, wired at two points every turn. Course concept:
Security Features.

**Agent Controller (`agent/controller.py`):** The ADK loop. PERCEIVE: read
SessionState. PLAN: classify intent (7 categories), apply OSCE override rule,
build per-skill ContextBundle. ACT: invoke skill from registry. OBSERVE: filter
output, log TurnSignal, update state, write to memory. The controller never
calls the LLM directly. Course concept: Agent Architecture / ADK.

**Skills (`skills/`):** Four stateless, composable skills. CaseRetrievalSkill —
ChromaDB vector search with weak-area bias (context engineering). OSCEExaminerSkill
— 3-phase state machine (init/turn/finish). EvaluationSkill — LLM rubric scoring,
weak area extraction, SQLite persistence. StudyPlannerSkill — personalised plan from
historical profile. Course concept: Agent Skills.

**Tool & Data Layer:** ChromaDB (Jina-embedded surgical cases), SQLite (student
profiles, OSCE results, session history), DeepSeek LLM, `eval_log.jsonl` (structured
evaluation log — one JSON object per turn). Course concept: Evaluation.

---

### § 4 — Implementation Journey (300 words)

A brief honest narrative of how the system was built. This maps to the "Build"
requirement in the video rubric ("How you created it, what tools you used").

Suggested structure:
- Started from an existing Telegram surgical RAG bot (the reference repo)
- Decided to build a greenfield agent system rather than migrate the existing code
- Worked through 7 phases: data pipeline → tools → security → skills → controller
  → interfaces → documentation
- Biggest technical challenge: stateful OSCE session management across a stateless
  controller (solved by session store + `osce_history_start_index`)
- Biggest design decision: building the security layer before the skills, not after
- Testing approach: 252 tests across 6 files; sandbox-safe CI mode (no LLM) vs.
  live mode; Gradio tests guarded by `CI_NO_GRADIO=1`
- Tools: Python, DeepSeek (LLM), Jina AI (embeddings), ChromaDB (vector store),
  SQLite (profiles), Gradio (UI), standard library only for security layer

---

### § 5 — Agents for Good Justification (150 words)

Why this submission belongs in the Agents for Good track.

- Surgical mortality is disproportionately high in lower-resource healthcare settings
- The primary constraint is not technology — it is access to expert examiners who
  can provide structured, scored feedback
- SurgMentor removes the expert examiner as the limiting factor: students can
  practice OSCE sessions 24/7, receive consistent rubric-based scoring, and see
  their weak areas tracked over time
- The system is designed for minimum setup — two API keys, five commands — so it
  can run anywhere Python runs
- Open source, MIT licensed: anyone can host it, extend it, or adapt it to other
  clinical education domains

---

### § 6 — Results and Evaluation (200 words)

What the system produces and how it can be verified:

**Functional results:**
- An OSCE session runs end-to-end: case presentation → multi-turn examination
  → rubric-based scoring → weak area extraction → personalised study plan
- The student profile accumulates across sessions — weak areas compound and
  bias future case retrieval

**Evaluation evidence:**
- `eval_log.jsonl` — one TurnSignal per agent cycle, capturing session ID,
  intent classified, skill selected, output safety pass, latency, timestamp
- 184 automated tests covering security layer, skill logic, controller routing,
  OSCE state machine, and interface integration
- Security: all inputs pass through two-point sanitization; test suite verifies
  PII rejection, injection detection, disclaimer injection, and hard-block activation

**Reproducing the results:**
```bash
git clone <repo> && cd SurgMentor-Capstone
pip install -r requirements.txt
cp .env.example .env   # add DEEPSEEK_API_KEY
python -m uvicorn server:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
```

---

### § 7 — Course Concepts Table (150 words)

A table summarising how each demonstrated concept maps to code. Reproduce
the table from README § "Course Concepts Demonstrated" and add a one-sentence
explanation of each:

| Concept | Where | One-sentence explanation |
|---------|-------|--------------------------|
| Agent Architecture / ADK | `controller.py` `run()` | Steps 1–11 with PERCEIVE/PLAN/ACT/OBSERVE labels |
| Context Engineering | `context.py` `build_context_bundle()` | Per-skill trimmed view prevents token waste |
| Agent Skills | `skills/` — 4 classes | Each skill is independently testable and composable |
| Security Features | `security/layer.py` | Two-point wiring, named checks, test coverage |
| Evaluation | `evaluation/logger.py` | TurnSignal per cycle, SessionEvaluation per OSCE |
| Deployability | `run.py`, `app.py` | Five commands from clone to running system |

---

### Writeup formatting rules

- No more than one image (the architecture diagram — already in the writeup)
- No footnotes
- Short paragraphs (3–5 sentences each) — judges skim
- No bullet lists inside paragraphs — embed lists as prose or use table format
- Do not reproduce the README verbatim — adapt and expand
- Word count: verify with an external tool before submitting
  (`wc -w` on the plain text, or paste into a word processor)
- Do not start a Kaggle draft until the writeup text is finalised locally

---

## 8. Cover Image Plan

**Required by Kaggle:** A cover image must be attached to the Media Gallery
before the submission button is available. Without it, you cannot submit.

**Recommended tool:** Create in Canva, Google Slides, or PowerPoint.
Export as PNG 1600×900 (16:9 landscape).

**Content:**

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   SurgMentor                              [Top left: name]       │
│   Agentic Surgical OSCE Trainer           [Subtitle below name]  │
│                                                                  │
│   [Architecture diagram — simplified 5-layer version            │
│    using the Mermaid diagram from docs/architecture.md,         │
│    rendered or redrawn as a clean block diagram]                │
│                                                                  │
│   Kaggle AI Agents Intensive 2026   ·   Agents for Good         │
│                                              [Bottom banner]    │
└──────────────────────────────────────────────────────────────────┘
```

**Colour guidance:** Deep navy background (`#0D1B2A`), white text, steel blue
accents (`#1E6091`), green highlight for "Agents for Good" (`#2ECC8F`). This
matches the Gradio UI design system.

**Text content:**

- Title: `SurgMentor`
- Subtitle: `Agentic Surgical OSCE Trainer`
- Tagline: `24/7 structured surgical examination practice — no expert examiner required`
- Track badge: `Agents for Good`
- Bottom: `Kaggle AI Agents Intensive 2026`

**Fastest path if short on time:** Screenshot the Gradio UI in OSCE mode
(an active examination turn visible), crop to 16:9, add the project name
as an overlay text band at the top or bottom. This takes 5 minutes and
satisfies the requirement.

---

## 9. Final Demo Checklist

Run this checklist on the machine that will be used for recording, on the
same day as recording. Do not record on a different machine without re-checking.

```
Environment verification
  □  python --version → 3.10.x or 3.11.x
  □  pip show chromadb → 0.5.23 (must match the db/ build version)
  □  pip show gradio → 4.x.x
  □  .env file present with DEEPSEEK_API_KEY and JINA_API_KEY set
  □  db/ directory present with chroma.sqlite3 and at least one UUID directory

Functional checks
  □  python run.py → banner prints, no errors
  □  "show me appendicitis" → case text returned with Sources: block
  □  python -m uvicorn server:app --host 0.0.0.0 --port 8000 → starts, no errors
  □  Open http://localhost:8000 → custom web UI loads, nav pills visible
  □  Chat view: type a surgical question → response with Sources: citations
  □  OSCE view: click Start Session → patient case presented, step dot 1 active
  □  OSCE view: type one clinical response → examiner follow-up returned, step advances
  □  OSCE view: click End & Score → score panel displayed (0–10) with feedback
  □  Profile view: click Refresh Stats → historical session listed
  □  Profile view: click Generate Study Plan → personalised plan returned
  □  eval_log.jsonl grows after each turn (tail -1 eval_log.jsonl)
  □  (Optional) python app.py → Gradio fallback starts at localhost:7860, no errors

Recording setup
  □  Browser at 100% zoom
  □  Custom web UI at localhost:8000 fits in screen without scrolling (1080p or higher)
  □  System notifications disabled
  □  VS Code open to controller.py, scrolled to run() method (for Segment 5)
  □  Terminal window available (for Segment 5 eval log inspection)
  □  OBS / screen capture software tested — audio levels normal
  □  Phone on silent

Timing check (dry run before final recording)
  □  Segment 1: ≤ 0:45
  □  Segment 2: ≤ 0:45
  □  Segment 3: ≤ 1:00
  □  Segment 4: ≤ 1:30
  □  Segment 5: ≤ 0:30
  □  Segment 6: ≤ 0:20
  □  Total: ≤ 4:50
```

---

## 10. Timeline and Risk Mitigation

**Available time:** 17 days (June 20 to July 6, 2026).

### Recommended schedule

| Day | Task | Time estimate |
|-----|------|---------------|
| 1–2 | Decide db/ decision; update .gitignore; run no-secrets audit | 1 hr |
| 2–3 | Create cover image | 30 min |
| 3–5 | Write writeup body locally (§7 outline) | 3–4 hrs |
| 5–6 | Dry-run demo on recording machine; fix any issues | 1–2 hrs |
| 6–7 | Record video; export and upload to YouTube | 1–2 hrs |
| 7 | Publish GitHub repository | 30 min |
| 7–8 | Paste writeup into Kaggle draft; attach assets; verify links | 1 hr |
| 8 | Click submit | 5 min |
| 8–17 | Buffer (do not start stretch goals until all above are done) | — |

**Hard rule:** Do not click the Kaggle submit button until all four components
(writeup, video, cover image, project link) are attached and verified. There
is only one submission per team.

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Video runs over 5 minutes | High | High | Time each segment in a dry run. Segment 4 (demo) is the most variable — have a plan to cut to 2 turns instead of 3 if running long. |
| LLM responses slow during demo recording | Medium | Medium | Record during off-peak hours. If responses are slow, note it verbally ("production setup would be faster") and continue — slow responses are better than cutting the demo short. |
| GitHub publish accidentally includes .env or key values | Low | Critical | Run all 9 no-secrets checks before every push. Grep for patterns immediately after `git add`. |
| Kaggle writeup exceeds 2,500 words | Medium | Medium | Write locally first. Use `wc -w` to check before pasting into Kaggle. Per the rules, over-limit submissions "may be subject to penalty." |
| Cover image requirement overlooked | Low | High | Cover image is required to see the submit button. Create it before starting the writeup to avoid a last-minute blocker. |
| db/ version mismatch (judge has different chromadb) | Low | Medium | If db/ is included, note the exact chromadb version (0.5.23) in the README setup section with a rebuild command. |
| Deadline confusion (PT vs local time) | Low | Critical | July 6 11:59 PM Pacific Time. Convert to local timezone. Submit at least 2 hours early. |
| Writeup not submitted (saved as draft) | Low | Critical | Kaggle draft writeups not submitted by the deadline are not considered. Click the Submit button — not just Save. |

---

## 11. Exit Criteria

Phase 7 is complete when **all** of the following are true:

1. **GitHub repository is public:**
   - No secrets in any tracked file (all 9 no-secrets checks pass)
   - README.md renders correctly on GitHub (Mermaid diagram visible)
   - LICENSE file present
   - All tests documented in README

2. **YouTube video is uploaded:**
   - Public or unlisted
   - ≤ 5 minutes duration
   - Covers all 6 segments from §6
   - URL is valid and accessible

3. **Kaggle writeup is complete:**
   - All 7 sections from §7 present
   - ≤ 2,500 words (verified with word count tool)
   - Architecture diagram embedded
   - Track set to "Agents for Good"

4. **Cover image is attached** to the Kaggle Media Gallery

5. **Video is attached** to the Kaggle Media Gallery

6. **GitHub URL is attached** as the Public Project Link

7. **Submission button has been clicked** before July 6, 2026 11:59 PM PT:
   - Kaggle submission status shows "Submitted" (not "Draft")

8. **README links updated:**
   - YouTube link in `README.md §Demo` replaced with actual URL
   - No `(#)` placeholder links remaining
