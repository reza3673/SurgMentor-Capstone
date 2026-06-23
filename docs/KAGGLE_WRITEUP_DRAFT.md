# SurgMentor — Agentic Surgical OSCE Trainer

**Subtitle:** AI agents for on-demand surgical resident education  
**Track:** Agents for Good  
**Author:** Reza Tayeb  
**Competition:** Kaggle AI Agents Intensive Vibe Coding Capstone 2026

---

> **Paste instructions:** Copy everything from the horizontal rule below this
> box through the end of the document into the Kaggle Writeup editor.
> Do not paste the title/subtitle/author lines — enter those in the Kaggle form fields.
> Verify word count before submitting (target ≤ 2,500 words).

---

## The Problem

Surgical residents learn clinical reasoning through Objective Structured Clinical Examinations — OSCEs. In an OSCE, a trained examiner presents a patient case, asks a structured sequence of clinical questions, and scores the trainee's reasoning against a rubric. The OSCE format is the gold standard for surgical education because it mirrors the real challenge of clinical practice: a patient arrives with a set of symptoms, and the clinician must take a structured history, reason through differentials, and justify a management plan under time pressure. The feedback is immediate, specific, and actionable.

The problem is not with the format — it is with availability. Expert examiners are scarce, expensive, and unevenly distributed. Residents at major academic medical centres in high-income countries may have regular access to structured practice. Residents at smaller hospitals, in lower-resource healthcare settings, or between formal teaching rotations get far fewer opportunities. Clinical reasoning is a skill that degrades without deliberate practice, and the gap in access to structured OSCE practice is one of the measurable contributors to the global variation in surgical outcomes.

The specific constraint is the examiner role: a structured, multi-turn, scored interaction that requires domain knowledge, consistency, and the ability to adapt follow-up questions to the trainee's answers. SurgMentor targets that role precisely.

---

## Why Agents?

A retrieval-augmented generation pipeline alone cannot solve this problem. RAG can retrieve a relevant surgical case and produce a one-shot educational response. That is useful for free-form study. But an OSCE is not a Q&A session — it is a stateful, multi-turn, scored examination with a defined structure.

What the agent loop adds that RAG cannot:

**Session-level state.** The examiner must remember every previous answer in the session. A RAG call has no memory of the prior turn. An agent controller maintains session state across turns and uses it to advance the examination correctly.

**Intent-aware routing.** SurgMentor supports three pedagogical modes: free case retrieval, structured OSCE examination, and personalised study planning. A stateless RAG pipeline cannot distinguish between them or transition between modes gracefully. The agent controller classifies intent on every turn and routes to the correct skill.

**Consistent rubric application.** Scoring must be deterministic and structured, not improvised. A dedicated EvaluationSkill applies a fixed rubric with named clinical criteria — history taking, differential diagnosis, investigations, management — and returns a numeric score with structured feedback.

**Adaptive personalisation.** Study recommendations should be based on the individual student's historical weak areas, not generic advice. The agent reads the student's accumulated performance profile from a persistent database and uses it to bias case retrieval and generate targeted study plans.

**Evaluation signals.** Every agent turn writes a structured TurnSignal to an evaluation log — session ID, intent classified, skill selected, safety pass status, latency. This produces an auditable record of every interaction without any additional tooling.

The AI Agents Intensive course teaches exactly this distinction. SurgMentor is a deliberate demonstration that an agent is the right abstraction for problems that require multi-turn state, routing, and post-hoc evaluation.

---

## Architecture

SurgMentor is structured in five strict layers, with no coupling allowed between non-adjacent layers.

[Insert uploaded image: surgmentor_architecture_1600x900.png]

*The diagram above shows the five-layer design: the shared PERCEIVE→PLAN→ACT→OBSERVE controller loop, four composable skills (CaseRetrieval, OSCEExaminer, Evaluation, StudyPlanner), the dual-pass security layer (pre-flight sanitization and post-flight filtering), in-memory session state, Jina + ChromaDB RAG, SQLite persistence, and the structured evaluation log.*

```
Entry Interfaces → Security Layer → Agent Controller → Skills → Tool & Data Layer
```

**Entry Interfaces.** Three thin wrappers, all calling `controller.run(input_text, session_id)` — no business logic in the interface layer. `run.py` is a terminal REPL. `server.py` is a FastAPI application serving a custom HTML/CSS/JavaScript single-page application from `web/index.html` at `localhost:8000` — this is the primary browser demo interface. `app.py` is an optional three-tab Gradio fallback at `localhost:7860`.

**Security Layer** (`surgmentor/security/layer.py`). Runs at two mandatory points on every turn. Pre-flight: `sanitize_input()` checks for PII patterns (NHS numbers, SSNs), prompt injection heuristics, inputs exceeding 2000 characters, and hard-block clinical danger patterns. If any check fails, a deflection message is returned immediately and no skill is invoked. Post-flight: `filter_output()` injects the medical disclaimer ("This is an educational tool, not clinical advice"), prepends an OSCE step tag while a session is active, and strips hard-block clinical assertions from LLM output. The security layer is independently testable, named, and mandatory. It cannot be bypassed.

**Agent Controller** (`surgmentor/agent/controller.py`). The cognitive core. `AgentController.run()` executes the four-step ADK loop on every call:

- **PERCEIVE** — read or initialise `SessionState` from the in-memory session store
- **PLAN** — classify the student's intent into one of seven `IntentCategory` values; apply the OSCE override rule (if `osce_active=True` and intent is not `FINISH_OSCE`, force `OSCE_TURN` regardless of classification); build a per-skill trimmed `ContextBundle`
- **ACT** — invoke the registered skill; the controller never calls the LLM directly
- **OBSERVE** — post-flight filter, log `TurnSignal`, update session state, write to store

**Skills** (`surgmentor/skills/`). Four stateless, composable skill classes, each implementing the `Skill` abstract base class with a single `run(ContextBundle) → SkillResult` interface:

- `CaseRetrievalSkill` — embeds the student query via Jina, searches ChromaDB with weak-area bias, calls DeepSeek to present the top-3 cases with source citations
- `OSCEExaminerSkill` — three-phase state machine: `_init()` seeds a case and asks the opening question; `_turn()` responds to each answer and advances the step counter; `_finish()` delegates to EvaluationSkill
- `EvaluationSkill` — calls DeepSeek at temperature 0.1 with a structured scoring prompt; extracts score, rubric breakdown, weak areas, and study recommendations; persists the result to SQLite
- `StudyPlannerSkill` — reads the student's accumulated weak areas from SQLite; calls DeepSeek to generate a personalised remediation plan; returns an onboarding message if no history exists yet

**Tool and Data Layer.** ChromaDB (Jina-embedded surgical cases in `./db/`), SQLite (student profiles, OSCE results, session history in `data/`), DeepSeek LLM via the OpenAI-compatible API, and `eval_log.jsonl` — a machine-readable append log with one JSON object per agent cycle.

---

## Implementation Journey

The project began from an existing surgical Telegram bot — a monolithic RAG system with a working ChromaDB case database, DeepSeek integration, and Jina embeddings. The decision was to build a greenfield agent system rather than migrate the existing code. The reference bot provided the domain knowledge and data; the new system provides the architecture.

Development proceeded in seven phases. The data pipeline came first: copying the case spreadsheet, embedding 5 surgical cases via Jina, and verifying ChromaDB retrieval before writing any application code. This meant every subsequent test ran against real data, not mocks.

The security layer was built before the skills — deliberately. Building it first meant the architecture was designed around security from the start, not retrofitted. Every skill's output was always going to be filtered; the filtering rules shaped how skill prompts were written.

The four skills were built in dependency order: the `Skill` abstract base class locked the interface before any concrete skill was written, preventing each skill from defining its own convention. The EvaluationSkill came before the OSCEExaminerSkill because the OSCE `_finish()` method calls into the evaluation layer.

The controller was the last major component written, after all four skills were independently verified. A controller written to route to working skills is far simpler to test than one routing to stubs.

The most significant technical challenge was managing OSCE session state across a stateless controller. The solution was `osce_history_start_index` — a field in `SessionState` that marks where the current OSCE began in the shared conversation history. Skills receive only the OSCE-relevant slice of history, not the entire chat log. This preserves continuity without contaminating the examination with prior free-chat turns.

Testing used a two-mode strategy: sandbox-safe (`CI_NO_LLM=1 CI_NO_GRADIO=1`) for all 252 tests in the CI environment, and live mode for integration validation on a machine with API keys. All Gradio-dependent tests are guarded by `CI_NO_GRADIO=1` to avoid the SOCKS proxy incompatibility in sandboxed environments.

---

## Agents for Good

The global burden of surgical disease falls disproportionately on lower-resource healthcare systems. According to the Lancet Commission on Global Surgery, 5 billion people lack access to safe, affordable surgical care — and a significant part of that gap is a workforce quality gap, not just a workforce quantity gap. Surgeons and residents in under-resourced settings have fewer opportunities for the structured, scored practice that builds clinical reasoning.

SurgMentor removes the expert examiner as the limiting factor. A student with a laptop and a DeepSeek API key — which offers a generous free tier — can run a structured OSCE session at any time, receive rubric-based feedback on their clinical reasoning, and see their weak areas tracked over multiple sessions. The system runs locally, requires no cloud deployment, and is fully open source. Any medical school or training programme can host it, extend it to other clinical domains, or adapt it to their own case library.

The agent design is not incidental to the Agents for Good framing — it is the reason the system can do what it does. The stateful multi-turn examination, the adaptive personalisation, and the structured evaluation are all properties of the agent architecture. A simpler tool would not produce the same outcome.

---

## Results and Evaluation

A complete OSCE session runs end-to-end in the current system: case presentation → multi-turn clinical examination → rubric scoring (0–10) → weak area extraction → personalised study recommendations → persistent profile update. The student profile accumulates across sessions: weak areas compound, score history builds, and future case retrieval is biased toward the student's learning gaps.

Evaluation is first-class, not optional. After every agent cycle, a `TurnSignal` is written to `eval_log.jsonl`:

```json
{
  "session_id": "3f8a2c1d-...",
  "intent_classified": "OSCE_TURN",
  "skill_selected": "OSCEExaminerSkill",
  "output_safety_pass": true,
  "latency_ms": 812,
  "timestamp": "2026-06-20T14:22:31"
}
```

The test suite covers 252 tests across six files: security layer, OSCE skills and flow, agent controller, entry interfaces, API endpoints, and retrieval. In sandbox-safe mode, 241 tests pass, 11 are intentionally skipped behind live LLM or Gradio guards, and there are zero failures.

---

## Course Concepts Demonstrated

| Concept | Where in code | Notes |
|---------|--------------|-------|
| **Agent / ADK system** | `surgmentor/agent/controller.py` — `run()` Steps 1–11 | PERCEIVE/PLAN/ACT/OBSERVE labelled inline |
| **Context Engineering** | `surgmentor/agent/context.py` — `build_context_bundle()` | Per-skill trimmed view; OSCE history sliced from `osce_history_start_index` |
| **Agent Skills** | `surgmentor/skills/` — 4 concrete classes | Each independently testable; composable via registry |
| **Security Features** | `surgmentor/security/layer.py` | Two-point wiring; 9 named checks; 9 test coverage |
| **Evaluation** | `surgmentor/evaluation/logger.py` | `TurnSignal` per cycle; `SessionEvaluation` per OSCE |
| **Deployability** | `run.py`, `server.py`, `app.py` | Clone → 3 commands → running system (CLI or web UI) |

**Minimum 3 required course concepts demonstrated: 6 of 6 addressed.**

---

## Repository and Setup

**GitHub:** [SurgMentor-Capstone](https://github.com/reza3673/SurgMentor-Capstone)

```bash
git clone https://github.com/reza3673/SurgMentor-Capstone.git
cd SurgMentor-Capstone
pip install -r requirements.txt
cp .env.example .env   # add DEEPSEEK_API_KEY only
# Primary web interface:
python -m uvicorn server:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
# Optional Gradio fallback:
# python app.py   # http://localhost:7860
```

The pre-built vector database (5 surgical cases, chromadb==0.5.23) is included. No Jina API key is required to run the system. To rebuild from scratch, set `JINA_API_KEY` and run `python scripts/02_embed_and_store.py`.
