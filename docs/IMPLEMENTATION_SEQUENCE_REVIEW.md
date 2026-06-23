# IMPLEMENTATION_SEQUENCE_REVIEW.md

**Project:** SurgMentor — Agentic Surgical Education System  
**Date:** 2026-06-20  
**Author:** Implementation sequence re-analysis  
**Sources reviewed:** TARGET_ARCHITECTURE.md, MIGRATION_PLAN.md, GAP_ANALYSIS.md  
**Purpose:** Authoritative implementation roadmap for the remainder of the project.

> This document supersedes the informal phase descriptions in MIGRATION_PLAN.md sections 7–9.
> When there is a conflict between this document and any other, this document takes precedence.

---

## 1. Review Finding: Is the Previous Phase Sequence Correct?

**Short answer: The sequence is structurally sound but Phase 1 contains a critical ordering defect.**

The previous plan groups five distinct deliverables into "Phase 1 — Tool and Data Layer":

1. `surgmentor/rag/retrieval_tool.py`
2. `surgmentor/memory/db_store.py`
3. `surgmentor/memory/session.py`
4. `surgmentor/evaluation/logger.py`
5. `scripts/01_prepare_data.py` and `scripts/02_embed_and_store.py`

Items 1–4 can be written in that order. But item 5 — the data pipeline scripts — must be **written and executed** before item 1 can be meaningfully tested. `retrieval_tool.py` queries a ChromaDB vector store. If the vector store does not exist, retrieval returns nothing, and the tool cannot be verified. The phase as written creates a situation where a file can be written but not tested until the scripts at the end of the same phase are run.

**The fix:** Split Phase 1 into two sub-phases:
- **Phase 1A (Data Pipeline):** Write and execute scripts 01 and 02. Verify with script 03. This produces a working ChromaDB in `db/` and `data/prepared_cases.json`.
- **Phase 1B (Tool Layer):** With the vector store live, implement and test `retrieval_tool.py` against real data, then `db_store.py`, `session.py`, and `logger.py`.

A second structural issue exists: `data/cases.xlsx` must be **copied from the `surgery-rag/` reference repo** into `SurgMentor Capstone/data/` before any script can run. This copy step is not called out explicitly anywhere. It is the absolute prerequisite of Phase 1A and must be logged as step zero.

No other structural revision is required. The broad sequence — data → tools → security → skills → controller → interfaces → documentation → submission — is correct and is the one recommended by all three source documents.

---

## 2. The Optimal First Implementation Phase

**Phase 1A — Data Pipeline (scripts + asset copy) must come before all else.**

### Why this phase, not any other?

The entire knowledge layer of SurgMentor rests on the ChromaDB vector store. Every skill that retrieves or presents a surgical case calls `search_vector_store()` or `get_case_by_id()` — both of which query ChromaDB. The EvaluationSkill verifies student answers against the loaded case context. The OSCEExaminerSkill seeds its session from a case loaded from ChromaDB. The StudyPlannerSkill retrieves cases to recommend based on weak areas.

If Phase 1A is deferred — even by one phase — the consequence is that every tool and skill must be tested against mocked data. Mocks accumulate technical debt. They test the mock, not the real integration. When the vector store is eventually built and plugged in, any mismatch between mock behavior and real ChromaDB behavior introduces bugs at the worst possible time (during integration, close to deadline).

By executing Phase 1A first, every subsequent phase can be tested against real case data, real embeddings, and real retrieval results. The system grows on a verified foundation.

### Critical prerequisite before Phase 1A begins

Before scripts/01 or 02 can run:
- `data/cases.xlsx` must be copied from `<SOURCE_PROJECT>/data/cases.xlsx` into `<PROJECT_ROOT>/data/cases.xlsx`
- This is a data asset copy, not a code migration — it is explicitly permitted under the greenfield constraints

---

## 3. Revised Implementation Phases

### Phase 1A — Data Pipeline & Asset Copy
**Goal:** A working ChromaDB vector store and verified retrieval before any application code is written.  
**Kaggle criteria improved:** Technical Implementation (50 pts) — enables all RAG-dependent skills; Deployability (via reproducible setup commands).  
**Files created or executed:**

| Action | Target |
|---|---|
| Copy | `data/cases.xlsx` ← from reference repo |
| Write + execute | `scripts/01_prepare_data.py` → produces `data/prepared_cases.json` |
| Write + execute | `scripts/02_embed_and_store.py` → builds `db/` vector store |
| Write + execute | `scripts/03_test_retrieval.py` → confirms retrieval works |

**Exit criterion:** `scripts/03_test_retrieval.py` returns at least 1 case for each of 3 test queries with similarity scores printed. If this test fails, Phase 1B does not begin.

**Dependencies:** Python environment with packages from `requirements.txt` installed. DeepSeek and Jina API keys in `.env`.

**Risks:**
- `chromadb==0.4.24` may conflict with `gradio>=4.0`. Resolve dependency conflicts before Phase 1B starts — do not defer.
- Jina embedding API has a rate limit. The batch size (32) in the original script handles this; preserve it.

---

### Phase 1B — Tool and Storage Layer
**Goal:** All low-level tools that skills will call — retrieval, database, session memory, eval logger — implemented and individually testable.  
**Kaggle criteria improved:** Technical Implementation (50 pts) — provides the data access layer that all 4 skills depend on.  
**Files:**

| File | Description |
|---|---|
| `surgmentor/rag/retrieval_tool.py` | `search_vector_store()`, `get_case_by_id()`, `_embed_query()` with cache, `format_case_context()`, `load_all_cases()`. Lazy ChromaDB connection (not at import time). |
| `surgmentor/memory/db_store.py` | Schema: users, osce_results, topics_studied, agent_sessions. `init_database()`, `register_student()`, `save_osce_result()`, `get_student_stats()`, `log_topics()`. |
| `surgmentor/memory/session.py` | `SessionState` dataclass. `InMemorySessionStore` with read/write/clear. |
| `surgmentor/evaluation/logger.py` | `TurnSignal` dataclass. `SessionEvaluation` dataclass. `write_turn_signal()`, `write_session_evaluation()` → appends JSON line to `eval_log.jsonl`. |

**Exit criterion:** A standalone Python script can call `search_vector_store("abdominal pain")` and receive a list of `CaseResult` objects with real diagnosis and presentation text. `db_store.init_database()` creates the schema without error.

**Dependencies:** Phase 1A complete (ChromaDB populated). `config.py`, `clients.py` (already implemented).

---

### Phase 2 — Security Layer
**Goal:** A named, importable, independently testable `SecurityLayer` module before any skill code is written.  
**Kaggle criteria improved:** Security Features (one of the 3 required course concepts — this single module checks that box); Technical Implementation (50 pts) — a visible security layer is a concrete differentiator.  
**Files:**

| File | Description |
|---|---|
| `surgmentor/security/layer.py` | Input sanitizer (rule-based: length, PII regex, injection heuristics) + scope enforcement (LLM call, temp=0.1) + output filter (hard-block patterns, disclaimer injection, least-privilege tool check). `SanitizedInput` and `FilteredOutput` dataclasses. |
| `tests/test_security.py` | 8 tests: PII rejection, injection detection, over-length rejection, out-of-scope deflection, disclaimer presence in output, hard-block activation, clean input passthrough, tool privilege check. |

**Why before skills, not after?**

MIGRATION_PLAN Section 9 states this explicitly: "Build it before the controller, not after. It must be a named, importable module — not a post-hoc add-on." If the security layer is built after skills, there is an incentive to bolt it on rather than design it as a first-class layer. Building it first enforces the discipline that all skill outputs will be filtered before they are returned — the controller can then wire it in naturally rather than inserting safety checks as afterthoughts.

The security layer has no dependencies on the skill system. It depends only on `config.py` (for `MAX_INPUT_LENGTH`) and `clients.py` (for the scope classification LLM call). Both are already implemented. There is zero implementation cost to building it now.

**Exit criterion:** All 8 tests in `tests/test_security.py` pass. A known PII pattern ("SSN: 123-45-6789") is rejected. A clean surgical education question is passed through. Every output contains the educational disclaimer.

**Risks:** The scope classification LLM call adds ~300–500ms latency per request. If this proves too slow in demo, make it optional via `config.py` flag (`SCOPE_CLASSIFICATION_ENABLED=false`). The rule-based checks are sufficient for MVP.

---

### Phase 3 — Skill Interface and Skill System
**Goal:** All four MVP skills fully implemented, independently runnable, and tested end-to-end before the controller is built.  
**Kaggle criteria improved:** Technical Implementation (50 pts) — skill composability is directly observable; Agent Skills (one of the 6 course concepts, maps to Day 3).  
**Files:**

| File | Order | Rationale |
|---|---|---|
| `surgmentor/skills/base.py` | First | Locks the `ContextBundle → SkillResult` interface. All concrete skills must implement it. Prevents each skill from defining its own interface convention. |
| `surgmentor/skills/evaluation_skill.py` | Second | Simplest refactor (direct port of `osce_scorer.py` pattern). Proves the `Skill` ABC works before tackling complex state machines. |
| `surgmentor/skills/osce_examiner_skill.py` | Third | Most complex and highest-value for demo (init / turn / finish state machine). Test it independently before wiring into controller. |
| `surgmentor/skills/case_retrieval_skill.py` | Fourth | Powers the free chat tab. Depends on `retrieval_tool.py` (Phase 1B) and the established skill interface. |
| `surgmentor/skills/study_planner_skill.py` | Fifth | Fastest to implement (one LLM call over `get_student_stats()` output). Confirmed MVP (see MIGRATION_PLAN Section 10). |
| `tests/test_osce_flow.py` | Sixth | End-to-end: init → 3 turns → finish → evaluation. Verifies `SessionEvaluation` populated, `eval_log.jsonl` written. |

**Why base.py before any concrete skill?**

If `case_retrieval_skill.py` is written first, it defines the interface by example. `evaluation_skill.py` then either adopts a slightly different pattern (inconsistency) or is forced to match the first skill retroactively (rework). Locking the ABC first means every skill is consistent from the start — which matters when the controller's skill registry must treat them uniformly.

**Why evaluation_skill before osce_examiner_skill?**

`osce_examiner_skill.py`'s `finish()` method must call into the evaluation layer (`evaluation_skill.run()` or at minimum `evaluation_logger.write_session_evaluation()`). If the evaluation skill is not yet implemented when `finish()` is written, `finish()` either calls a stub or is written incompletely. Writing evaluation first means `finish()` can be written to completion.

**Exit criterion:** A standalone test (not using the controller) can call `OSCEExaminerSkill.init(case_id)` → `turn(answer_1)` → `turn(answer_2)` → `turn(answer_3)` → `finish()` and receive a `SessionEvaluation` object with a numeric score and feedback text. `eval_log.jsonl` gains a new entry. All 7 tests in `test_osce_flow.py` pass.

**Dependencies:** Phase 1B (retrieval_tool, db_store, logger). Phase 2 (security layer, for output filtering in skill results). Phase 0 (`clients.py`, already implemented).

---

### Phase 4 — Agent Controller
**Goal:** The ADK-pattern controller that wires all skills, session memory, security, and evaluation into a single `controller.run(input, session_id) → str` call.  
**Kaggle criteria improved:** Technical Implementation (50 pts) — this is the single highest-impact file in the project; ADK pattern (one of the 3 required course concepts — must be visible in this file's code).  
**Files:**

| File | Description |
|---|---|
| `surgmentor/agent/intent.py` | `IntentCategory` enum (8 categories). `classify_intent(input, state) → IntentCategory` via LLM call at temp=0.1. `UNKNOWN` fallback with safe deflection text. |
| `surgmentor/agent/context.py` | `build_context_bundle(intent, input, state) → ContextBundle`. Per-skill trim logic (OSCE gets full history; planner gets profile only; retrieval gets query + weak_areas). |
| `surgmentor/agent/controller.py` | `AgentController`. Skill registry `{IntentCategory → Skill}`. `run(input, session_id) → str` with the full perceive → plan → act → observe loop. ADK-pattern comment at each step. Pre-flight: `security_layer.sanitize()`. Post-flight: `security_layer.filter_output()`. Per-turn: `eval_logger.write_turn_signal()`. |

**Why the controller comes after all skills?**

The controller is a router. Its only job is to select a skill, build a context bundle, call the skill, filter the output, and log a signal. If the controller is built before skills exist, it must either call stubs or be written speculatively without knowing the actual `SkillResult` shape. Both options introduce rework. A controller written after all four skills exist can be tested against real skill outputs immediately.

**Exit criterion:** `python run.py` (CLI) accepts "show me a case about appendicitis" and returns a formatted case response. Accepts "start OSCE" and enters examiner mode. Accepts "how did I do" after a completed session and returns a score. All responses contain the educational disclaimer. `eval_log.jsonl` gains an entry per turn.

**Dependencies:** All Phase 3 skills complete. Phase 1B tools complete. Phase 2 security layer complete.

---

### Phase 5 — Entry Interfaces
**Goal:** A working CLI (`run.py`) and Gradio UI (`app.py`) that both use `controller.run()` for all interactions.  
**Kaggle criteria improved:** Deployability (one of the 3 required course concepts); Video demo content; Technical Implementation (50 pts — judges want to see the agent running).  
**Files:**

| File | Description |
|---|---|
| `run.py` | Simple REPL: `input → controller.run(input, session_id) → print`. CLI is built first because it is simpler to debug than Gradio. |
| `app.py` | Gradio 3-tab UI: Free Chat (`CaseRetrievalSkill` path), OSCE Session (`OSCEExaminerSkill` path + score display on finish), Student Profile (`StudyPlannerSkill` + `db_store.get_student_stats()` display). |

**Why CLI before Gradio?**

Gradio adds UI state management, event wiring, and streaming complexity on top of the controller. If the controller has a bug, it is much harder to isolate in Gradio than in a simple REPL. Building the CLI first validates the controller end-to-end. Any bugs found are fixed at the controller level, and then Gradio inherits a correct controller.

**Exit criterion:** `python app.py` launches Gradio at `http://localhost:7860`. All three tabs function. An OSCE session can be started, conducted for 3 turns, finished, and the resulting score is displayed. The Student Profile tab shows historical weak areas (even if empty for a new student).

**Phase 5 also verifies the complete local setup flow end-to-end:**
```
pip install -r requirements.txt
cp .env.example .env   # user fills in keys
python scripts/01_prepare_data.py
python scripts/02_embed_and_store.py
python app.py
```
This exact sequence will be recorded in the competition video.

---

### Phase 6 — Documentation
**Goal:** README, architecture diagram, and inline code comments that make the system comprehensible to a judge who has never seen the code before.  
**Kaggle criteria improved:** Documentation (20 pts — second-largest criterion); closes GAP-D1, GAP-D2, GAP-D3.  
**Files:**

| File / Action | Description |
|---|---|
| Code comment pass | Agent controller: ADK-pattern label at each step. Security layer: named principle per check. Each skill: course concept reference in class docstring. Evaluation logger: Day 4 reference. |
| `README.md` | Problem (2 paragraphs), why agents (1 paragraph), architecture diagram, skill descriptions, exact setup commands, demo video link placeholder. |
| `docs/architecture.png` | Mermaid diagram from TARGET_ARCHITECTURE.md rendered to PNG for writeup and video. |
| `.env.example` | Finalize — verify all required variables are listed with placeholder values and inline comments. |

**Why documentation is Phase 6, not Phase 7 or concurrent?**

Documentation must be written after the system is implemented because the README setup commands must reflect the actual working install sequence — not the planned sequence. If the implementation changes any command (e.g., a different entry point name), the README written after Phase 5 reflects that change automatically. The comment pass similarly benefits from the implementation being final — comments that describe a final design are more accurate than comments written during development that may be superseded.

Documentation is placed before submission deliverables because the video demo requires a finished README to show during the architecture walkthrough, and the Kaggle writeup is substantially easier to write when the documentation is already drafted.

---

### Phase 7 — Submission Deliverables
**Goal:** All mandatory submission components complete before the July 6, 2026 deadline.  
**Kaggle criteria improved:** Video (10 pts), Writeup (10 pts), closes GAP-S1, S2, S3, S4.  
**Steps (all human steps; Reza executes these):**

| Step | Action | Closes |
|---|---|---|
| 7-1 | Cover image: SurgMentor name, tagline, architecture diagram | GAP-S4 |
| 7-2 | YouTube video (5 min): problem → why agents → architecture → live OSCE → code highlight → wrap | GAP-S1 |
| 7-3 | Kaggle writeup (target 1,800–2,000 words): narrative from PROJECT_UNDERSTANDING.md Section 8 | GAP-S2 |
| 7-4 | Publish GitHub repository (manual): verify no `.env` or key values in any file first | GAP-S3 |
| 7-5 | Kaggle hackathon submission: video + GitHub link + cover image + Agents for Good track | All |

**Video content plan (for reference):**

| Segment | Content | Target duration |
|---|---|---|
| Problem | Surgical resident training gap; OSCE as gold standard; cost of expert examiners | 45s |
| Why agents | Why RAG pipeline is insufficient; what the agent loop adds (intent routing, memory, evaluation) | 45s |
| Architecture | Walk the architecture diagram; name each layer; call out ADK pattern | 60s |
| Live demo | Start OSCE → 2–3 turns → finish → score + feedback displayed | 90s |
| Code highlight | Show `controller.run()` loop in code; point to ADK comment; show security module | 30s |
| Wrap | GitHub link, track, closing | 30s |

---

### Phase 8 — Stretch Goals (attempt only if all Phase 1–7 steps are complete)

Ordered by score impact:

| Priority | Goal | Impact | Effort | When to start |
|---|---|---|---|---|
| 1 | `ClinicalReasoningSkill` (5th skill) | Adds a 5th composable skill; improves architecture depth score | M (2–3 days) | After video recorded |
| 2 | MCP Server (2 tools: `search_surgical_cases`, `evaluate_osce_session`) | Checks MCP course concept box; Day 2 concept demonstrated | M (2–3 days) | After ClinicalReasoningSkill |
| 3 | A2A multi-agent topology (OrchestratorAgent → TutorAgent / OSCEAgent) | Raises architecture quality ceiling | M (2–3 days) | After MCP |
| 4 | Hugging Face Spaces deployment | Public demo URL; removes local setup barrier for judges | M (2 days) | After A2A or independently |

---

## 4. Dependency Graph

```
data/cases.xlsx (copy)
        │
        ▼
scripts/01_prepare_data.py (execute)
        │
        ▼
scripts/02_embed_and_store.py (execute)
        │
        ▼
scripts/03_test_retrieval.py (verify)         config.py ─────┐
        │                                     clients.py ────┤
        ▼                                                     │
surgmentor/rag/retrieval_tool.py ◄────────────────────────── ┘
        │
        ├──► surgmentor/memory/db_store.py
        │           │
        │           ▼
        │    surgmentor/memory/session.py
        │
        ├──► surgmentor/evaluation/logger.py
        │
        └──► surgmentor/security/layer.py ◄── (no skill dependencies)
                    │
                    ▼
             surgmentor/skills/base.py
                    │
                    ├──► surgmentor/skills/evaluation_skill.py (uses logger, db_store)
                    │
                    ├──► surgmentor/skills/osce_examiner_skill.py (uses retrieval_tool, evaluation_skill)
                    │
                    ├──► surgmentor/skills/case_retrieval_skill.py (uses retrieval_tool)
                    │
                    └──► surgmentor/skills/study_planner_skill.py (uses db_store)
                                │
                                ▼
                         surgmentor/agent/intent.py
                                │
                         surgmentor/agent/context.py
                                │
                         surgmentor/agent/controller.py
                                │
                       ┌────────┴────────┐
                       ▼                 ▼
                    run.py           app.py
                       │                 │
                       └────────┬────────┘
                                ▼
                          documentation
                                │
                                ▼
                        submission deliverables
```

**Hard rules from this graph:**
1. No skill can be written before `skills/base.py` is final.
2. `osce_examiner_skill.py` must not call `evaluation_skill.py` until evaluation_skill exists.
3. `controller.py` must not be written before all four skills are independently verified.
4. `app.py` must not be written before `run.py` is proven (CLI validates the controller loop first).

---

## 5. File Modification Inventory

### Phase 1A
- `data/cases.xlsx` — copy in (new)
- `scripts/01_prepare_data.py` — write and execute
- `scripts/02_embed_and_store.py` — write and execute
- `scripts/03_test_retrieval.py` — write and execute

### Phase 1B
- `surgmentor/rag/retrieval_tool.py` — implement (replace placeholder)
- `surgmentor/memory/db_store.py` — implement (replace placeholder)
- `surgmentor/memory/session.py` — implement (replace placeholder)
- `surgmentor/evaluation/logger.py` — implement (replace placeholder)

### Phase 2
- `surgmentor/security/layer.py` — implement (replace placeholder)
- `tests/test_security.py` — implement (replace placeholder)

### Phase 3
- `surgmentor/skills/base.py` — implement (replace placeholder)
- `surgmentor/skills/evaluation_skill.py` — implement (replace placeholder)
- `surgmentor/skills/osce_examiner_skill.py` — implement (replace placeholder)
- `surgmentor/skills/case_retrieval_skill.py` — implement (replace placeholder)
- `surgmentor/skills/study_planner_skill.py` — implement (replace placeholder)
- `tests/test_osce_flow.py` — implement (replace placeholder)

### Phase 4
- `surgmentor/agent/intent.py` — implement (replace placeholder)
- `surgmentor/agent/context.py` — implement (replace placeholder)
- `surgmentor/agent/controller.py` — implement (replace placeholder)

### Phase 5
- `run.py` — implement (replace placeholder)
- `app.py` — implement (replace placeholder)

### Phase 6
- All `surgmentor/**/*.py` files — comment pass (modify in place)
- `README.md` — full content (replace skeleton)
- `docs/architecture.png` — new file
- `.env.example` — verify completeness (minor edits if needed)

### Phase 8 (stretch only)
- `surgmentor/mcp/server.py` — implement (replace placeholder)
- `surgmentor/skills/case_retrieval_skill.py` — extend with ClinicalReasoningSkill pattern (or new file)
- `requirements.txt` — uncomment `mcp` if Phase 8 is reached

---

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `chromadb==0.4.24` conflicts with `gradio>=4.0` at install time | Medium | High | Resolve dependency resolution in Phase 1A before writing any application code. If conflict: upgrade chromadb and rebuild the vector store. |
| `scripts/02_embed_and_store.py` Jina API rate limiting | Low | Medium | Keep original batch size (32). Add retry/backoff if rate errors occur. |
| `osce_examiner_skill.py` state machine complexity causes Phase 3 overrun | Medium | Medium | Build and test `init()` and `turn()` before `finish()`. `finish()` can emit a stub result that is fleshed out in Phase 3-4 (evaluation_skill) if needed. |
| Intent classifier misroutes edge-case inputs | High | Medium | Add `UNKNOWN` fallback before launch. Test the full list of 8 intent categories with 3 example inputs each (24 test cases total) before Phase 4 ends. |
| Gradio streaming incompatibility with controller loop | Medium | Medium | Test streaming output in Phase 5 early. Non-streaming is fully acceptable for judging — disable streaming if it blocks progress. |
| Video logistics (audio, screen capture, 5-min limit) | High | High | Prepare the demo script before recording. Record with the system in its Phase 5 state (stable, not undergoing changes). |
| API keys accidentally written into source files | Low | Critical | All keys loaded from `.env` only. Human step: grep source files for key patterns before running `git push` during Phase 7-4. |
| Time overrun leaves submission incomplete | Medium | Critical | The mandatory submission items (video, writeup, GitHub, cover image) must be scheduled explicitly. Do not start stretch goals until video is recorded. |

---

## 7. Kaggle Judging Criteria — Phase Impact Map

| Phase | Primary criterion improved | Points at stake |
|---|---|---|
| 1A (Data Pipeline) | Technical Implementation — enables all skill functionality | 50 (foundational) |
| 1B (Tool Layer) | Technical Implementation — retrieval and storage layer visible in code | 50 (foundational) |
| 2 (Security) | Security Features (required concept) + Technical Implementation | 50 + concept check |
| 3 (Skills) | Technical Implementation (skill composability) + Agent Skills (required concept) | 50 + concept check |
| 4 (Controller) | Technical Implementation (ADK pattern — highest single impact) + ADK concept | 50 + concept check |
| 5 (Interfaces) | Deployability (required concept) + Video demo content | concept check + 10 |
| 6 (Documentation) | Documentation criterion | 20 |
| 7 (Submission) | Video + Writeup + validity of submission | 10 + 10 + validity |

**The 3 required course concepts are satisfied by phases 2, 3/4, and 5:**
- Security features → Phase 2
- Agent / ADK system → Phase 4
- Deployability → Phase 5

**If time pressure forces a cut, this is the minimum viable path:**
Phase 1A → 1B → 2 → 3 (OSCE + Evaluation only) → 4 → 5 → 6 → 7. All four skills are strongly recommended (the StudyPlannerSkill is fast), but a three-skill submission still satisfies GAP-A2 and GAP-C1.

---

## 8. Alternative Sequences Rejected

### Alternative: Build agent controller first
**Rejected.** The controller is a router — it routes to skills. Without skills, it routes to stubs. Stubs create technical debt: when real skills replace them, the controller must be retested. The controller written after skills exist can be tested against real outputs immediately.

### Alternative: Build Gradio interface first
**Rejected.** A UI-first approach leads to stubbed LLM calls and fake responses to make the interface look complete. Any fake data in the demo is detectable by judges inspecting the code. The interface should be the last thing added — it reflects a system that already works.

### Alternative: Build security layer last (post-hoc)
**Rejected.** GAP-C3 describes this as a critical failure mode: "The absence of visible guardrails will stand out to any judge familiar with the course." Building security after skills incentivizes bolting it on as an afterthought. Building it before skills means every skill's output is designed with the assumption it will be filtered — this produces a cleaner architecture that judges can read as intentional, not retrofitted.

### Alternative: Build skills in order of complexity (easiest last)
**Rejected.** Building the simplest skill (StudyPlannerSkill) first would prove the `Skill` interface works but leave the most complex skill (OSCEExaminerSkill) for the end of Phase 3 — creating a time crunch risk if it takes longer than expected. Building the second-easiest skill (EvaluationSkill) first proves the interface, then the most complex skill is tackled while schedule slack still exists.

### Alternative: Combine Phases 1A and 1B into one phase
**Rejected.** The distinction between "pipeline that produces the data" and "tool that queries the data" is important for testing. If they are one phase, it is tempting to write `retrieval_tool.py` before running the scripts — leaving the tool untestable until the end of the combined phase. The exit criterion for Phase 1A (a working retrieval test) is the entry gate for Phase 1B.

---

## 9. Summary

**Recommended phase sequence (authoritative):**

```
Phase 0  (DONE)    — Project scaffold, placeholders, config, clients
Phase 1A           — Copy cases.xlsx; write + execute scripts 01/02/03
Phase 1B           — retrieval_tool, db_store, session, logger
Phase 2            — Security layer + tests/test_security.py
Phase 3            — skills/base.py + 4 skills + tests/test_osce_flow.py
Phase 4            — intent, context, controller; wire security + evaluation
Phase 5            — run.py (CLI), app.py (Gradio); verify local setup flow
Phase 6            — Comment pass, README.md, architecture.png
Phase 7            — Cover image, video, writeup, GitHub publish, Kaggle submit
Phase 8 (stretch)  — ClinicalReasoningSkill, MCP, A2A, HF Spaces
```

**Phase 1A is the correct next step.** It has no code dependencies, unblocks everything downstream, and can be verified with a single test command.
