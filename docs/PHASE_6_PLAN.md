# PHASE_6_PLAN.md — Documentation and Comment Pass

**Project:** SurgMentor — Agentic Surgical Education System  
**Phase:** 6 of 7  
**Date:** 2026-06-20  
**Status:** Awaiting approval  
**Authoritative sources:** IMPLEMENTATION_SEQUENCE_REVIEW.md, TARGET_ARCHITECTURE.md,
  PHASE_5_PLAN.md, current implemented codebase (Phases 1–5 complete)

---

## 1. Objectives

Phase 6 makes the implemented system comprehensible to a competition judge who has
never seen the code before. It does not change any logic. It produces three
deliverables: a `README.md`, a Mermaid architecture diagram (rendered as text
in `docs/architecture.md`), and a targeted inline comment pass over the files
that are weakest or most important for the judging rubric.

**Specific objectives:**

1. Write `README.md` — the front page of the GitHub repository. Judges read this
   first. It must explain the problem, the solution, why agents are the right
   abstraction, how to set up and run the system, and which course concepts are
   demonstrated where in the code.

2. Create `docs/architecture.md` — a Mermaid diagram of the full system embedded
   in a short narrative. Serves as both a reference document and the source for
   the architecture diagram displayed in the competition video.

3. Execute a targeted inline comment pass — add or improve comments in files where
   judges are most likely to look, ensuring every major design decision is explained
   at the point in the code where it occurs.

4. Verify `.env.example` is complete and accurate against the current `config.py`.

5. Verify no secrets, API keys, or `.env` files have leaked into any committed file.

**Kaggle criteria directly improved by this phase:**

| Criterion | Mechanism |
|---|---|
| Documentation (20 pts) | README, architecture diagram, inline comments |
| Technical Implementation (50 pts) | Comment pass surfaces architecture quality for judges |
| Deployability (required concept) | README setup section is a judge-executable reproduction guide |

**What Phase 6 does NOT include:**

- Video recording (Phase 7 — human step)
- Kaggle writeup (Phase 7 — human step)
- MCP server, A2A, Hugging Face deployment (Phase 8 stretch)
- Any logic changes — if a logic bug is found during the comment pass, it is
  noted and reported but not fixed inline. A separate targeted fix request
  is made before the Phase 6 deliverable is finalized.

---

## 2. Files to Modify

### New files created

| File | Description |
|------|-------------|
| `README.md` | Full competition-ready README (replaces skeleton) |
| `docs/architecture.md` | Mermaid diagram + system narrative |

### Files receiving comment pass (targeted additions only — no logic changes)

| File | Current quality | Pass needed |
|------|----------------|-------------|
| `surgmentor/agent/controller.py` | Strong — ADK loop comments already present | Add per-step line labels in `run()` matching the PERCEIVE/PLAN/ACT/OBSERVE structure documented in the module docstring |
| `surgmentor/agent/intent.py` | Strong — strategy and fallback documented | Add one-line comment above each rule cluster in `_classify_via_rules()` explaining the trigger pattern |
| `surgmentor/agent/context.py` | Strong — trim rules documented | No changes needed |
| `surgmentor/security/layer.py` | Strong — threat model referenced | Add one-line label above each `sanitize_input()` check identifying the threat it addresses |
| `surgmentor/skills/base.py` | Strong — ABC and dataclass purpose clear | No changes needed |
| `surgmentor/skills/osce_examiner_skill.py` | Strong — state machine documented | Add brief comment above `_turn()` prompt construction explaining why RAG is skipped in OSCE mode |
| `surgmentor/skills/case_retrieval_skill.py` | Adequate — logic clear | Add comment explaining the `bias_topics` weak-area bias mechanism |
| `surgmentor/skills/evaluation_skill.py` | Adequate | Add comment above the `weak_areas` list extraction explaining the prior bug that was fixed (list not string) |
| `surgmentor/skills/study_planner_skill.py` | Strong — onboarding guard documented | No changes needed |
| `surgmentor/rag/retrieval_tool.py` | Strong — least-privilege principle noted | Add one-line comment on the embedding cache explaining its purpose |
| `surgmentor/memory/db_store.py` | Strong — schema and design documented | No changes needed |
| `surgmentor/memory/session.py` | Strong — design notes present | No changes needed |
| `surgmentor/evaluation/logger.py` | Strong — Day 4 principle noted | No changes needed |
| `surgmentor/ui/helpers.py` | Adequate — purpose clear | Add one-line comment on `OSCE_FINISH_MARKERS` explaining the string-based detection rationale |
| `config.py` | Adequate | Add inline comment on `SCOPE_CLASSIFICATION_ENABLED` explaining the performance tradeoff |
| `run.py` | Strong — ADK labels present | No changes needed |
| `app.py` | Adequate — tab structure clear | Add one-line comment above `_safe_run()` explaining the exception boundary design |
| `.env.example` | Good — complete | Verify against current `config.py`; add any missing variables |

### Files explicitly not touched

| File | Reason |
|------|--------|
| `clients.py` | Already clear; any change risks SOCKS proxy regression |
| `scripts/01_prepare_data.py` | Data pipeline; not in judge's primary review path |
| `scripts/02_embed_and_store.py` | Data pipeline; scripts are self-documenting |
| `scripts/03_test_retrieval.py` | Utility script |
| `surgmentor/mcp/server.py` | Phase 8 stretch — placeholder only |
| All `__init__.py` files | Empty by design |
| All `tests/*.py` files | Test docstrings already explain purpose; adding more risks cluttering the reading experience |

---

## 3. README.md Structure

The README is the primary artifact judges read. It must answer six questions in
order: (1) What is the problem? (2) What did you build? (3) Why agents? (4) How do
I run it? (5) Where are the course concepts? (6) What does it look like?

Target length: 600–900 words of prose. Diagrams and tables supplement but do not
replace prose. Judges skim — every section must have a one-sentence payoff visible
without scrolling.

### Section outline

```
# SurgMentor — Agentic Surgical OSCE Trainer

## The Problem                          (~80 words)
## Why Agents?                          (~80 words)
## Architecture                         (diagram + 60-word caption)
## Skills                               (table: 4 skills, one-line each)
## Course Concepts Demonstrated         (table: concept → where in code)
## Setup                                (numbered commands — exact, copy-pasteable)
## Running SurgMentor                   (CLI and Gradio commands + what to expect)
## Demo                                 (link placeholder + 5-step demo script)
## Evaluation Evidence                  (eval_log.jsonl description)
## Project Structure                    (file tree — top-level only)
## Agents for Good                      (2-sentence track justification)
## License                              (MIT, 1 line)
```

### Section specifications

#### § The Problem

Two paragraphs. Paragraph 1: surgical resident training gap — OSCE examinations
are the gold standard but require expert examiners who are scarce and expensive.
Paragraph 2: the consequence — trainees get fewer practice opportunities than the
evidence base recommends, with measurable effects on clinical reasoning development.

No citations required. The problem must be legible to a judge who is not a medical
professional.

#### § Why Agents?

One paragraph. Explain that a RAG pipeline is insufficient: it can retrieve relevant
cases but cannot maintain conversational state, apply a consistent scoring rubric,
switch between pedagogical modes (teaching vs. examining), or adapt to the student's
specific weak areas. An agent loop is the right abstraction because it adds intent
classification, session-level memory, skill composition, and post-hoc evaluation —
all of which are required for a coherent OSCE simulation.

The agent vs. pipeline distinction is the conceptual heart of the submission. This
paragraph must be specific and comparative, not generic.

#### § Architecture

Embed the Mermaid diagram from `docs/architecture.md` (a code block). Follow with
a one-sentence caption naming each of the five layers: Entry Interface → Security
Layer → Agent Controller → Skills → Tool/Data Layer.

#### § Skills

A four-row table:

| Skill | Purpose | Course concept |
|-------|---------|----------------|
| CaseRetrievalSkill | Retrieve cases from ChromaDB based on query + weak-area bias | Agent Skills (Day 3) |
| OSCEExaminerSkill | Conduct stateful 3-phase OSCE session (init/turn/finish) | Agent Skills (Day 3) |
| EvaluationSkill | Score a completed session via LLM rubric; extract weak areas | Evaluation (Day 4) |
| StudyPlannerSkill | Generate personalised study plan from historical performance | Agent Skills (Day 3) |

#### § Course Concepts Demonstrated

A table mapping each required concept to the exact file and function where it is
demonstrated. This is the most important table in the README for judging:

| Concept | Where | File |
|---------|-------|------|
| Agent Architecture / ADK loop | `AgentController.run()` steps 1–11 | `surgmentor/agent/controller.py` |
| Context Engineering | `build_context_bundle()` per-skill trim | `surgmentor/agent/context.py` |
| Agent Skills | `Skill` ABC + 4 concrete implementations | `surgmentor/skills/` |
| Security Features | `SecurityLayer.sanitize_input()` + `filter_output()` | `surgmentor/security/layer.py` |
| Evaluation | `TurnSignal` logged per turn; `SessionEvaluation` per OSCE | `surgmentor/evaluation/logger.py` |
| Deployability | `run.py` CLI + `app.py` Gradio + local setup commands | `run.py`, `app.py` |

#### § Setup

Numbered commands — exact and copy-pasteable. No "you may need to" hedging.
Every command must be verified against the actual working system:

```
1. git clone <repo-url> && cd SurgMentor-Capstone
2. pip install -r requirements.txt
3. cp .env.example .env          # fill in DEEPSEEK_API_KEY and JINA_API_KEY
4. python scripts/01_prepare_data.py
5. python scripts/02_embed_and_store.py
6. python run.py                 # CLI demo
   # or
6. python app.py                 # Gradio UI at http://localhost:7860
```

Steps 4–5 are skipped if the repository ships with a pre-built `db/` directory
(to be decided in Phase 7 before GitHub publish). If not shipping the db, the
note "This step takes ~2 minutes and requires a Jina API key" must appear.

#### § Running SurgMentor

Three subsections (brief): CLI usage, Gradio usage, expected output examples.
One short paragraph each. No screenshots (those go in the video). Plain text
showing the expected prompt and a one-line example response is sufficient.

#### § Demo

A link placeholder: `[Watch the demo on YouTube](<link>)`. Below it, a 5-step
numbered demo script matching the OSCE flow from PHASE_5_PLAN.md §6, so a judge
who cannot watch the video can replicate the demo manually.

#### § Evaluation Evidence

Two sentences: `eval_log.jsonl` is created at runtime and contains one JSON object
per agent cycle. Describe the fields (session_id, intent_classified, skill_selected,
output_safety_pass, latency_ms) and state that it can be inspected with:

```bash
python -c "import json; [print(json.dumps(json.loads(l), indent=2)) for l in open('eval_log.jsonl')]"
```

#### § Project Structure

A top-level file tree (not exhaustive — key files only):

```
SurgMentor-Capstone/
├── run.py                          # CLI entry point
├── app.py                          # Gradio web UI
├── config.py                       # Environment-based configuration
├── surgmentor/
│   ├── agent/                      # Controller, intent classifier, context builder
│   ├── security/                   # Input sanitizer and output filter
│   ├── skills/                     # 4 composable skill implementations
│   ├── rag/                        # ChromaDB retrieval tools
│   ├── memory/                     # SQLite persistence + session state
│   ├── evaluation/                 # TurnSignal and SessionEvaluation logger
│   └── ui/                         # Shared UI helpers (session ID, stats rendering)
├── scripts/                        # Data pipeline (run once to populate ChromaDB)
├── tests/                          # Sandbox-safe test suite (184 tests)
├── data/                           # cases.xlsx source data
└── docs/                           # Architecture and planning documents
```

#### § Agents for Good

Two sentences: Explain that SurgMentor targets the global surgical training gap —
specifically the shortage of expert OSCE examiners in low- and middle-income
countries where surgical mortality is highest. The agent system makes structured
OSCE practice available on-demand without requiring an expert examiner to be present.

#### § License

`MIT License. See LICENSE file.`

Note: a `LICENSE` file containing the MIT license text must be created in Phase 6
as part of this deliverable.

---

## 4. Architecture Diagram Plan

### File: `docs/architecture.md`

A Markdown document containing:
1. A one-paragraph system overview (3–4 sentences)
2. The full Mermaid diagram (as a fenced code block — renders in GitHub)
3. A layer-by-layer description (one paragraph per layer, ~40 words each)

### Diagram content

The diagram reproduces the five-layer architecture from TARGET_ARCHITECTURE.md §1,
updated to reflect the actual implemented system (Phase 5 state). Key additions
over the draft in TARGET_ARCHITECTURE.md:

- Show actual file names next to each component (e.g., `controller.py`)
- Show the two SecurityLayer call points (pre-flight and post-flight arrows)
- Show `eval_log.jsonl` as a write-only output from the evaluation layer
- Show all four skills in the skill layer (named, not generic "SKILL" boxes)
- Show ChromaDB and SQLite as distinct storage components in the data layer

### Diagram format

Mermaid `flowchart TD` (top-down). GitHub renders Mermaid natively in Markdown
code blocks with the `mermaid` language tag — no image generation needed. The video
will show this diagram rendered in a browser tab or VS Code preview.

If a rendered PNG is also needed for the Kaggle writeup cover image, it will be
generated in Phase 7 using a Mermaid CLI tool or browser screenshot — not in Phase 6.

---

## 5. Code Comment Pass Strategy

### Principles

1. **Explain design decisions, not mechanics.** "We trim history to HISTORY_WINDOW
   turns here" is redundant — the code shows it. "We trim here because each skill
   should see only the context it needs (Day 1 context engineering)" adds meaning.

2. **Name the course concept at the point of use.** Every place where an ADK pattern,
   Day 1–4 principle, or security mechanism is implemented should have a one-line
   `# Course concept: X (Day N)` or `# ADK: PERCEIVE` marker. These are already
   present in most files — the pass reinforces and fills gaps.

3. **Flag non-obvious decisions.** Lazy imports, the `osce_history_start_index`
   mechanism, the `weak_areas` list-not-string fix, the OSCE override rule — each
   of these has a reason. If the reason isn't already in a comment, add one sentence.

4. **Do not explain Python.** No comments on `for`, `if`, or list comprehensions
   unless the specific expression is genuinely confusing.

5. **Keep comments short.** One or two lines per decision. Longer explanations belong
   in the module docstring, not inline.

### Comment style convention

All inline comments added in Phase 6 use the same prefix style already established
in the codebase:

```python
# ── PERCEIVE ──────────────────────────────────────────────────────────
# Step 1: Read current session state ...
```

For single-line additions:
```python
validate_api_keys()  # SystemExit(1) if keys are missing — hard failure at startup
```

No new section-separator bars (`# ───...`) are introduced unless they match the
existing style in that file exactly.

### Files where comment pass adds the most judging value

In priority order:

1. **`surgmentor/agent/controller.py`** — the single most important file. The ADK
   loop steps already have `# ── PERCEIVE ──` etc. markers in the module docstring.
   These must appear as inline markers on the actual code lines inside `run()`,
   not just in the docstring. This is the primary evidence of ADK pattern.

2. **`surgmentor/security/layer.py`** — the security concept demonstration. Each
   check in `sanitize_input()` should have a one-line label identifying the threat
   category it addresses (e.g., `# PII guard`, `# Prompt injection guard`,
   `# Length limit`).

3. **`surgmentor/skills/osce_examiner_skill.py`** — the most complex skill.
   The `_turn()` method's decision to skip RAG and use only the seeded case context
   needs a brief explanation, since it may look like an oversight to a judge unfamiliar
   with OSCE pedagogy.

4. **`app.py`** — judges may read the Gradio app to understand the UI architecture.
   The `_safe_run()` exception boundary and the session ID sharing pattern between
   tabs each deserve one comment.

---

## 6. Setup Instructions

The setup instructions in the README must match the actual working sequence verified
in Phase 5. They are written here as the authoritative source; the README copies them.

### Prerequisites

- Python 3.10 or 3.11 (3.12+ may have ChromaDB compatibility issues)
- A DeepSeek API account and API key (free tier is sufficient for demo)
- A Jina AI account and API key (free tier is sufficient — 1M tokens/month)

### One-time data pipeline

```bash
# After cloning and installing dependencies:
python scripts/01_prepare_data.py      # ~5 seconds
python scripts/02_embed_and_store.py   # ~2 minutes (Jina API calls)
python scripts/03_test_retrieval.py    # optional sanity check
```

Step 2 builds the ChromaDB vector store in `./db/`. It must be run once per machine.
If the repository ships with a pre-populated `db/` directory (to be decided in
Phase 7), this step can be skipped. The `.gitignore` currently excludes `db/*` —
this decision must be made before Phase 7 publish.

### Running CLI

```bash
python run.py
```

On startup: validates API keys, initialises SQLite schema, prints session ID.
On each turn: input → `controller.run()` → response → `eval_log.jsonl` entry.
Type `help` for commands. Type `exit` to quit.

### Running Gradio

```bash
python app.py
```

Opens at `http://localhost:7860`. Three tabs: Free Chat, OSCE Examination,
Student Profile. No browser extension required. No login required.

---

## 7. Demo Workflow Documentation

The demo workflow is documented in two places: the README `§ Demo` section (for
judges who read the code), and as the foundation of the video script (Phase 7).

### Canonical demo sequence (5 steps)

This sequence demonstrates all 6 course concepts in under 5 minutes:

```
Step 1 — Launch app.py
  → Shows: Deployability concept
  → Browser opens at localhost:7860

Step 2 — Free Chat tab: "show me a case about right iliac fossa pain"
  → Agent classifies as RETRIEVE_CASE → CaseRetrievalSkill
  → Response includes case context + Sources: section with case IDs
  → Shows: Agent Skills, Context Engineering

Step 3 — OSCE tab: click "Start OSCE"
  → Agent classifies as START_OSCE → OSCEExaminerSkill._init()
  → Examiner presents a patient case and asks the first question
  → Status shows "Session active — Step 1 / 6"
  → Shows: Agent Architecture (stateful session initiated)

Step 4 — OSCE tab: 3 student responses (clinical reasoning)
  → Each input: OSCE override rule routes to OSCEExaminerSkill._turn()
  → Examiner follows up with the next question
  → Shows: Agent Architecture (session state maintained across turns)

Step 5 — OSCE tab: click "Finish OSCE"
  → EvaluationSkill scores the session
  → Score block displayed: score, feedback, weak areas, study recommendations
  → eval_log.jsonl receives TurnSignal entries for every turn
  → Shows: Evaluation, Security Features (disclaimer injected in output)
```

After Step 5, switching to the Student Profile tab and clicking "Refresh" shows
the session's score in the historical record, demonstrating persistent evaluation.

This sequence is what the video records and what the README demo section describes.

---

## 8. Kaggle Judging Alignment

The judging criteria and point values are:

| Criterion | Points | How Phase 6 addresses it |
|-----------|--------|--------------------------|
| Technical Implementation | 50 | Comment pass makes ADK loop, skill composition, and security wiring visible to judges reading the code |
| Documentation | 20 | README + architecture diagram + inline comments |
| Video | 10 | README demo section is the video script; Phase 7 records it |
| Writeup | 10 | README narrative is the draft for the Kaggle writeup |
| Deployability (required concept) | — | README setup section is the reproduction guide |
| Agent Architecture (required concept) | — | `controller.py` comment pass makes ADK loop unmistakable |
| Security Features (required concept) | — | `layer.py` comment pass labels each security check |

### Comment style for judging

The Kaggle AI Agents Intensive course covers 6 concepts across 5 days. The judging
rubric rewards evidence that the submission author understands these concepts and
applied them deliberately. The most effective evidence is code that is self-annotating:
a judge reading `controller.py` should not need to cross-reference the README to
understand which course concept is being demonstrated.

The existing docstrings in most files already name the course concept. The comment
pass adds the same annotation at the *function* and *step* level, not just the
module level. This distinction matters because judges read code top-down and often
stop at the first method.

---

## 9. Security / No-Secrets Checklist

Before the Phase 6 deliverable is marked complete, verify:

| Check | Method | Expected result |
|-------|--------|----------------|
| No `DEEPSEEK_API_KEY` value in any `.py` file | `grep -r "sk-" surgmentor/ run.py app.py config.py` | Zero matches |
| No `JINA_API_KEY` value in any `.py` file | `grep -r "jina_" surgmentor/ run.py app.py` | Zero matches |
| `.env` is not tracked | `cat .gitignore \| grep ".env"` | `.env` appears |
| `.env.example` contains no real values | Visual inspection | All values are placeholders |
| No hardcoded API base URLs that include keys | `grep -r "api_key=" surgmentor/` | Only `config.py` reference via variable |
| `data/students.db` excluded from git | `cat .gitignore \| grep "students.db"` | Excluded |
| `db/` vector store excluded | `cat .gitignore \| grep "db/"` | `db/*` pattern present, `.gitkeep` retained |
| `eval_log.jsonl` excluded | `cat .gitignore \| grep "eval_log"` | Excluded |
| No Telegram tokens or user IDs | `grep -r "TELEGRAM" surgmentor/ run.py app.py` | Zero matches (those are in the reference repo only) |

These checks are run as a final step before Phase 6 is marked complete. Any failure
is a blocker — the commit cannot be pushed to GitHub until all checks pass.

The grep commands above are the exact commands to run. They should be run on the
native Windows machine (using Git Bash or PowerShell `Select-String`) before
Phase 7 publish.

---

## 10. Test Commands to Document

The README and architecture doc reference the test suite. Phase 6 documents the
exact commands a judge can use to verify the system locally:

### Sandbox-safe (no API keys required)

```bash
# Run all tests in CI mode (no LLM, no Gradio)
PYTHONPYCACHEPREFIX=/tmp/pycache_surgmentor CI_NO_LLM=1 CI_NO_GRADIO=1 \
  python -m unittest discover -s tests -v

# Expected: 184 tests, 0 failures, 11 skipped
```

### Full suite (API keys required, native machine)

```bash
# Run all tests including live LLM integration tests
python -m unittest discover -s tests -v

# Expected: 184 tests, 0 failures, 0 skipped
# Note: live tests call DeepSeek and Jina APIs; ensure keys are in .env
```

### Individual test files

```bash
python -m unittest tests/test_security.py -v       # Security layer (22 tests)
python -m unittest tests/test_osce_flow.py -v      # Skills and OSCE flow (63 tests)
python -m unittest tests/test_controller.py -v     # Agent controller (61 tests)
python -m unittest tests/test_interfaces.py -v     # CLI and app interfaces (51 tests)
```

These commands appear verbatim in the README `§ Setup` section under a collapsible
"Running the test suite" subsection so they don't clutter the primary setup path.

---

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| README prose too long — judges skim | Medium | Medium | Keep section headers scannable; first sentence of each section carries the full message. Target: readable in under 3 minutes. |
| Mermaid diagram does not render in GitHub | Low | Medium | Test rendering in a GitHub gist before Phase 7 publish. If Mermaid fails, use ASCII diagram as fallback — TARGET_ARCHITECTURE.md already has one. |
| Comment pass accidentally changes logic (whitespace, indentation) | Low | High | Run the full test suite after every file in the comment pass. Zero logic-changing edits permitted. |
| `.env.example` out of sync with `config.py` | Low | Low | Read `config.py` line-by-line against `.env.example` during Phase 6 — patch any gaps. Current `.env.example` appears complete based on inspection. |
| Security checklist reveals a secret in the wrong file | Very low | Critical | Run all grep checks before marking Phase 6 complete. The greenfield project was built from scratch without copying API keys from the reference repo. |
| README setup commands do not match Windows paths | Medium | Medium | Verify all path separators and command syntax against the Windows-native `python` invocation. Use forward slashes in README (work on all platforms). |

---

## 12. Exit Criteria

Phase 6 is complete when **all** of the following are true:

1. **`README.md` is complete:**
   - All 12 sections present and populated (no `<!-- TODO -->` markers)
   - Setup commands are verified against the actual working system
   - Course concepts table lists all 6 concepts with file and function references
   - Demo section contains the 5-step sequence

2. **`docs/architecture.md` exists and contains:**
   - Full Mermaid diagram with actual file names
   - One-paragraph system overview
   - Layer-by-layer description

3. **`LICENSE` file exists** (MIT license text)

4. **Targeted comment pass complete in priority files:**
   - `surgmentor/agent/controller.py` — ADK step labels on actual code lines in `run()`
   - `surgmentor/security/layer.py` — threat category label on each `sanitize_input()` check
   - `surgmentor/skills/osce_examiner_skill.py` — RAG-skip explanation in `_turn()`
   - All other targeted files from §2 above

5. **`.env.example` verified against `config.py`** — no missing variables

6. **Security checklist fully passed:**
   - All 9 grep checks from §9 return zero matches or expected results

7. **Full test suite still passes** after comment pass:
   - `184 tests, 0 failures, 11 skipped` with `CI_NO_LLM=1 CI_NO_GRADIO=1`
   - Zero test regressions introduced by comment-only edits

8. **README is self-contained for reproduction:**
   - A judge following the README alone can set up and run the system
   - No external reference needed except `.env` key acquisition
