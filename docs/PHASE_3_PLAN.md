# PHASE_3_PLAN.md

**Project:** SurgMentor — Agentic Surgical Education System  
**Date:** 2026-06-20  
**Phase:** 3 — Skill Interface and Skill System  
**Source documents:** TARGET_ARCHITECTURE.md §3, §4 · IMPLEMENTATION_SEQUENCE_REVIEW.md §Phase 3 · MIGRATION_PLAN.md §3, §5 · PHASE_1B_COMPLETION.md · PHASE_2_PLAN.md  
**Status:** Awaiting approval before implementation begins

---

## 1. Objectives

Phase 3 builds the skill system — the operational core of SurgMentor. Each skill is an independently testable, composable unit that the Phase 4 controller will route to. By the end of this phase, a caller can invoke any skill directly without the controller and receive a real, grounded, LLM-generated response.

**Primary objectives:**

1. Lock the `ContextBundle → SkillResult` interface before any concrete skill is written, so all skills are uniformly composable from the first line of code.
2. Implement all four MVP skills: `EvaluationSkill`, `OSCEExaminerSkill`, `CaseRetrievalSkill`, `StudyPlannerSkill`.
3. Prove the skill chain works end-to-end — `OSCEExaminerSkill.init() → turn() → finish() → EvaluationSkill.run()` — in an integration test that exercises real LLM calls, real ChromaDB retrieval, real SQLite writes, and real eval log output.
4. Ensure every skill result passes through `SecurityLayer.filter_output()` before it is returned, making the security layer structurally present in every skill path.

**Kaggle criteria addressed:**

- **Agent Skills** (Day 3 course concept — required): Four named, composable skills with a shared interface is the direct embodiment of this concept. Each skill's class docstring references Day 3.
- **Technical Implementation (50 pts):** Skill composability — especially the `FINISH_OSCE` three-skill pipeline — is the most visually impressive part of the architecture for judges reading the code.

**What Phase 3 does NOT do:**

- Does not implement the controller (`agent/controller.py`). Skills are called directly in tests.
- Does not implement intent classification (`agent/intent.py`). IntentCategory is referenced but not resolved.
- Does not implement context bundle assembly (`agent/context.py`). Tests build ContextBundles manually.
- Does not implement CLI or Gradio. Entry interfaces are Phase 5.

---

## 2. Files to Be Implemented

Six files. All inside the existing package structure. No other files are created or modified.

| File | Current state | Action | Order |
|---|---|---|---|
| `surgmentor/skills/base.py` | Placeholder (imports only) | Full implementation | 1st |
| `surgmentor/skills/evaluation_skill.py` | Placeholder | Full implementation | 2nd |
| `surgmentor/skills/osce_examiner_skill.py` | Placeholder | Full implementation | 3rd |
| `surgmentor/skills/case_retrieval_skill.py` | Placeholder | Full implementation | 4th |
| `surgmentor/skills/study_planner_skill.py` | Placeholder | Full implementation | 5th |
| `tests/test_osce_flow.py` | Placeholder | Full implementation (7 tests) | 6th |

**Why this order?**

`base.py` first: locks the interface that all concrete skills implement. If any concrete skill is written first, it defines the interface by example — which creates inconsistency when the second and third skills are written and must either match or refactor. An ABC written first prevents this.

`EvaluationSkill` second: the simplest skill (direct port of `osce_scorer.py` logic). Proves the ABC works before any state machine is attempted. Also required before `OSCEExaminerSkill.finish()` can call it.

`OSCEExaminerSkill` third: most complex skill (three-state machine). Calls `EvaluationSkill` from `finish()` — so `EvaluationSkill` must exist first.

`CaseRetrievalSkill` fourth: stateless skill wrapping retrieval + LLM. Depends on `retrieval_tool.py` (Phase 1B, done) and the established interface.

`StudyPlannerSkill` fifth: fastest to implement given `get_student_stats()` is ready. One LLM call over structured data.

`test_osce_flow.py` sixth: integration test that can only be complete once all four skills exist.

---

## 3. Skill Interface Design

All skills inherit from a single abstract base class. The ABC is declared in `surgmentor/skills/base.py`. Every concrete skill that does not implement `run()` is a `TypeError` at instantiation time — the interface is enforced by Python's ABC mechanism, not by convention.

### Abstract Base Class

```python
# surgmentor/skills/base.py

class Skill(ABC):
    """
    Abstract base class for all SurgMentor skills.

    Course concept: Agent Skills (Day 3).
    Each skill is a self-contained, composable unit. It receives a ContextBundle
    and returns a SkillResult. It does not share state with other skills.
    The agent controller (Phase 4) selects skills; skills do not select each other.
    Exception: OSCEExaminerSkill.finish() calls EvaluationSkill.run() directly,
    representing an intra-skill pipeline. This is permitted and documented.

    Skills MUST NOT:
    - Import from surgmentor.agent (controller layer — Phase 4)
    - Call each other except via explicit documented pipeline patterns
    - Hold persistent state across calls (session state lives in controller)
    - Call security_layer.filter_output() — the controller does this (Phase 4)
      Exception: In Phase 3, individual skill __main__ tests may call it directly
      to verify integration, since the controller does not yet exist.
    """

    name: str = ""        # Human-readable name for controller skill registry
    description: str = "" # One-line description used in README skill catalog

    @abstractmethod
    def run(self, bundle: ContextBundle) -> SkillResult:
        """Execute the skill. Must be implemented by every concrete subclass."""
        ...
```

### Skill Registry Entry (for Phase 4 reference)

Each concrete skill class carries two class-level attributes — `name` and `description` — that the Phase 4 controller reads when building the skill registry. Skills do not register themselves; the controller imports and registers them explicitly.

---

## 4. ContextBundle and SkillResult Schema

Both dataclasses are defined in `surgmentor/skills/base.py`. They are the only data contract between the controller and skills. Skills may not assume any additional input beyond what appears in the bundle.

### ContextBundle

```python
@dataclass
class ContextBundle:
    """
    Skill input. A trimmed, skill-relevant view of session state.

    Context engineering principle (Day 1): each skill receives only the fields
    it needs. Passing the full session state to all skills would increase token
    cost and hallucination risk. The controller (Phase 4) is responsible for
    building the bundle; in Phase 3, tests build it manually.

    Field trimming per skill (defined here; enforced in Phase 4 context.py):
    - OSCEExaminerSkill:   student_input, session_history, current_case, osce_step, parameters
    - CaseRetrievalSkill:  student_input, weak_areas (biases retrieval), parameters
    - EvaluationSkill:     session_history, current_case, student_id, parameters
    - StudyPlannerSkill:   student_id, weak_areas, score_history (no session_history)
    """
    student_input:    str                    # sanitized student message (from SecurityLayer)
    session_history:  list[dict]             # list of {"role": str, "content": str}
    current_case:     dict | None            # loaded case metadata + text (CaseResult.metadata + .text)
    student_id:       str                    # stable student identifier (UUID)
    weak_areas:       list[str]              # from past OSCE results (biases retrieval)
    score_history:    list[dict]             # list of {"case_id", "score", "completed_at"}
    osce_step:        int                    # 0 if not in OSCE mode
    parameters:       dict                   # skill-specific overrides (e.g. top_k, case_id)
```

**Notes:**
- `session_history` uses the OpenAI message format (`{"role": "user"|"assistant"|"system", "content": str}`) so it can be passed directly to the DeepSeek client.
- `current_case` is `None` in `CaseRetrievalSkill` (retrieval happens inside the skill) and populated in `OSCEExaminerSkill` after `init()` runs.
- `weak_areas` is empty for new students. `CaseRetrievalSkill` uses it to bias retrieval; `StudyPlannerSkill` uses it to shape the plan.
- `parameters` allows the controller to pass skill-specific values (e.g. `{"case_id": "3"}` to force a specific OSCE case) without adding new fields to the dataclass.

### SkillResult

```python
@dataclass
class SkillResult:
    """
    Skill output. Returned by every skill's run() method.

    The controller (Phase 4) reads:
    - response_text → passes to security_layer.filter_output() → returns to student
    - updated_case → writes to session state (OSCEExaminer updates this)
    - updated_osce_step → writes to session state
    - session_complete → if True, controller triggers EvaluationSkill (unless skill already called it)
    - evaluation → if populated, controller passes to evaluation_logger
    - metadata → logged in TurnSignal
    """
    response_text:      str                    # LLM-generated response (pre-filter)
    updated_case:       dict | None = None     # OSCEExaminerSkill updates this after init()
    updated_osce_step:  int         = 0        # OSCEExaminerSkill increments this
    session_complete:   bool        = False    # True when OSCEExaminerSkill.finish() is called
    evaluation:         dict | None = None     # Populated by EvaluationSkill (score, feedback, etc.)
    metadata:           dict        = field(default_factory=dict)
```

**Notes:**
- `evaluation` is a plain dict (not a dataclass) here so that `SkillResult` does not import from `evaluation/`. The controller handles the conversion to `SessionEvaluation`.
- `session_complete = True` is the signal for the controller to release any OSCE-specific context and move the session back to chat mode.
- `metadata` carries skill-specific diagnostic data (e.g. `{"retrieval_hits": 3, "case_ids": ["1", "2", "3"]}`) that the controller logs in `TurnSignal.metadata`.

---

## 5. EvaluationSkill Plan

**File:** `surgmentor/skills/evaluation_skill.py`  
**Reference:** `surgery-rag/osce_scorer.py` (read-only) — the scoring logic is rewritten fresh, informed by the reference.  
**Course concept:** Evaluation (Day 4)

### Purpose

Score a completed OSCE session. Takes the full conversation history and the case context, calls DeepSeek at `temperature=0.1` with a structured scoring prompt, returns a `SkillResult` with the `evaluation` dict populated and `session_complete=True`.

### Design

```
EvaluationSkill.run(bundle) → SkillResult

Inputs used from bundle:
  session_history  → full OSCE transcript (system + user + assistant turns)
  current_case     → case metadata including expected diagnosis and key points
  student_id       → for db_store.save_osce_result()
  parameters       → {"case_id": str, "min_turns": int}

Steps:
  1. Participation guard: count student turns in session_history.
     If count < MIN_OSCE_TURNS (from config), return early with
     SkillResult(response_text="Too few responses to evaluate.", session_complete=True).
  2. Build scoring prompt (see Scoring Prompt section below).
  3. DeepSeek call: model=DEEPSEEK_CHAT_MODEL, temperature=0.1, max_tokens=600.
  4. Parse JSON response: extract score (int), feedback (str), rubric_breakdown (dict),
     weak_areas (list[str]), study_recommendations (list[str]).
     If parse fails: clamp to default values (score=0, feedback="Evaluation unavailable").
  5. Clamp score to [0, 10].
  6. Persist: db_store.save_osce_result(student_id, case_id, diagnosis, score, feedback, weak_areas).
  7. Log: write_session_evaluation(SessionEvaluation(...)) → appends to eval_log.jsonl.
  8. Return SkillResult:
       response_text = formatted feedback string (score + narrative + weak areas + recommendations)
       session_complete = True
       evaluation = {score, rubric_breakdown, weak_areas, study_recommendations, feedback}
```

### Scoring Prompt Structure

The prompt provides the examiner (LLM) with three inputs: the case definition (expected diagnosis, key clinical points), the full student transcript (all student turns extracted from session_history), and the rubric criteria. It asks for structured JSON output.

Rubric criteria (informed by reference `osce_scorer.py` and TARGET_ARCHITECTURE.md §6):

| Criterion | Description | Weight |
|---|---|---|
| `history_taking` | Did the student ask appropriate history questions? | 20% |
| `examination` | Did the student describe appropriate examination findings? | 20% |
| `differential_diagnosis` | Did the student generate a reasonable differential? | 20% |
| `management_plan` | Did the student propose appropriate immediate management? | 20% |
| `communication` | Was the student's communication structured and professional? | 20% |

Each criterion receives a sub-score 0–10. The overall score is the weighted mean (equal weights = simple average), rounded to nearest integer. `study_recommendations` is a new field (not in the reference) that names 1–3 specific topics the student should review.

### Score Rubric (for reference in docstring)

| Score | Meaning |
|---|---|
| 9–10 | Excellent — systematic, correct, all key points covered |
| 7–8 | Good — mostly correct, minor omissions |
| 5–6 | Satisfactory — correct diagnosis, some steps missed |
| 3–4 | Poor — significant clinical gaps |
| 0–2 | Unsatisfactory — wrong diagnosis or unsafe reasoning |

### Key Design Decisions

- `temperature=0.1`: low temperature for deterministic scoring. The reference uses the same value and explicitly documents the rationale ("grading requires consistency").
- Structured JSON output: the prompt instructs the LLM to output ONLY a JSON object. A `json.loads()` call parses it; if it fails, the skill falls back to safe defaults rather than raising.
- No partial scoring: if the LLM returns a score below 0 or above 10, clamp it. Never return an invalid score to the student or the eval log.
- `save_osce_result` writes the weak areas to SQLite. `StudyPlannerSkill` (Phase 3, Step 5) reads them in the same session if called after evaluation — or in a future session if the student returns.

---

## 6. OSCEExaminerSkill Plan

**File:** `surgmentor/skills/osce_examiner_skill.py`  
**Reference:** `surgery-rag/services/osce_service.py` + `surgery-rag/rag_engine.py` (read-only) — logic rewritten fresh.  
**Course concept:** Agent Skills (Day 3) — stateful, multi-turn skill demonstrating agent memory

### Purpose

Conduct a multi-turn OSCE examination session. The examiner presents a patient case, asks structured clinical questions, and maintains the step-by-step session until the student signals completion. At finish, it calls `EvaluationSkill.run()` directly (the intra-skill pipeline).

### States and Transitions

```
 [idle]
    │  init(case_id)
    ▼
 [STEP_0: Case Presentation]
    │  turn(student_answer)
    ▼
 [STEP_1: History Focused]
    │  turn(student_answer)
    ▼
 [STEP_2: Examination Findings]
    │  turn(student_answer)
    ▼
 [STEP_3: Differential Diagnosis]
    │  turn(student_answer)
    ▼
 [STEP_4: Management Plan]
    │  turn(student_answer) OR student sends FINISH signal
    ▼
 [FINISH]
    │  finish() → EvaluationSkill.run()
    ▼
 [SessionEvaluation returned]
```

Note: The controller manages the `osce_step` counter in `SessionState`. The skill reads `bundle.osce_step` to know which state it is in, rather than maintaining its own state. This keeps the skill stateless per call — all state lives in the session.

### Design

```
OSCEExaminerSkill.run(bundle) → SkillResult

Dispatch logic inside run():
  if bundle.osce_step == 0 and bundle.current_case is None:
    → _init(bundle)      # Present case, load case data, set updated_case
  elif bundle.parameters.get("finish") == True or bundle.osce_step >= MAX_OSCE_STEPS:
    → _finish(bundle)    # Score session via EvaluationSkill
  else:
    → _turn(bundle)      # Respond to student answer, advance step
```

**`_init(bundle)` — Case Presentation:**

```
1. Load case: retrieval_tool.get_case_by_id(bundle.parameters["case_id"])
   OR if no case_id in parameters: retrieval_tool.load_all_cases() → pick one
      that is NOT in bundle.score_history (avoid repetition).
2. Seed system prompt: SYSTEM_PROMPT_OSCE (see below) + case text.
3. Generate introductory message: "You are examining a [age] [sex] patient who
   presents with [chief complaint]. Begin by taking a focused history."
4. Return SkillResult:
     response_text = introductory examiner message
     updated_case  = {case_id, diagnosis, text, metadata}  # stored in session
     updated_osce_step = 1
```

**`_turn(bundle)` — Examiner Response:**

```
1. Append student's answer to session_history.
2. Build messages for LLM:
   [system: SYSTEM_PROMPT_OSCE + case context]
   [history: all prior turns from bundle.session_history]
   [user: bundle.student_input]
3. DeepSeek call: model=DEEPSEEK_CHAT_MODEL, temperature=0.7, max_tokens=400.
4. Response is the examiner's feedback + next question.
5. Return SkillResult:
     response_text = examiner response
     updated_osce_step = bundle.osce_step + 1
```

**`_finish(bundle)` — Session Completion:**

```
1. Build evaluation context bundle from current bundle:
   eval_bundle = ContextBundle(
     student_input   = "",
     session_history = bundle.session_history,
     current_case    = bundle.current_case,
     student_id      = bundle.student_id,
     parameters      = {"case_id": bundle.current_case["case_id"]}
     ... (other fields zeroed/empty)
   )
2. evaluation_result = EvaluationSkill().run(eval_bundle)
3. Log: write_session_evaluation(SessionEvaluation from evaluation_result.evaluation).
4. Return SkillResult:
     response_text     = evaluation_result.response_text (score + feedback)
     session_complete  = True
     evaluation        = evaluation_result.evaluation
     updated_osce_step = 0
```

### OSCE System Prompt Design

The system prompt is embedded in the skill as a module-level constant: `SYSTEM_PROMPT_OSCE`. It is written fresh; the reference's `SYSTEM_PROMPT_OSCE` is informative but not copied.

The prompt must convey:

1. Role: "You are a clinical surgical examiner conducting an OSCE examination."
2. Behaviour: neutral, stepwise, non-revealing. Never confirm or deny the student's diagnosis mid-session. Ask one question at a time.
3. OSCE steps: the examiner must cover all five domains (history, examination, differential, management, communication) before the session ends.
4. Safety: frame all clinical content as educational. Do not provide definitive real-world clinical guidance.
5. Format: short responses (3–5 sentences). End every examiner response with a direct question to keep the student engaged.

### MAX_OSCE_STEPS

`MAX_OSCE_STEPS = 6` (configurable via `config.py` if needed). After step 6, the controller should auto-trigger `finish` even if the student has not explicitly ended the session. This prevents infinite sessions.

---

## 7. CaseRetrievalSkill Plan

**File:** `surgmentor/skills/case_retrieval_skill.py`  
**Reference:** `surgery-rag/rag_engine.py` (chat branch, read-only) — rewritten fresh.  
**Course concept:** Agent Skills (Day 3) + Context Engineering (Day 1, via bias_topics)

### Purpose

Find and present a relevant surgical case in response to a free-form student query. Retrieval is grounded: the LLM rewrites the presentation but cannot fabricate case details. Source citations are appended to every response.

### Design

```
CaseRetrievalSkill.run(bundle) → SkillResult

Steps:
1. Query assembly:
   query = bundle.student_input
   bias_topics = bundle.weak_areas  # context engineering: steer toward student gaps
   
2. Retrieval:
   cases = search_vector_store(query, top_k=TOP_K_RESULTS, bias_topics=bias_topics)
   If cases is empty: return SkillResult with "No relevant cases found" message.

3. Context building:
   case_context = format_case_context(cases)  # "[Case 1] ID: X | Diagnosis: Y ...\n{text}"

4. Log topics:
   db_store.log_topics(bundle.student_id, cases, mode="chat")

5. LLM call:
   messages = [
     {"role": "system",    "content": SYSTEM_PROMPT_CHAT + "\n\n" + case_context},
     {"role": "system",    "content": "IMPORTANT: present only information from the
                            above cases. Do not introduce clinical facts not present
                            in the provided cases."},
     *bundle.session_history[-HISTORY_WINDOW:],  # windowed context
     {"role": "user",      "content": bundle.student_input}
   ]
   response = DeepSeek call, temperature=0.7, max_tokens=600

6. Citation append:
   sources_block = "\n\n**Sources:**\n" + format_sources(cases)
   full_response = response + sources_block

7. Return SkillResult:
     response_text = full_response
     metadata = {"retrieval_hits": len(cases), "case_ids": [c.case_id for c in cases]}
```

### `format_sources(cases)` Output Format

```
- Case 1: [case_id] — [diagnosis] (similarity: 0.72)
- Case 2: [case_id] — [diagnosis] (similarity: 0.68)
```

### CHAT System Prompt Design

Module-level constant: `SYSTEM_PROMPT_CHAT`. Written fresh; informed by the reference.

The prompt must convey:
1. Role: "You are a surgical education tutor helping a medical student learn from clinical cases."
2. Grounding constraint: "Respond only using information from the provided cases. Do not add clinical details not present in the case descriptions."
3. Pedagogical tone: Socratic where appropriate. Explain, do not just state.
4. Safety: do not provide real-world clinical management advice. Frame all content as educational.

### Streaming Variant

A `run_streaming(bundle)` generator method is added alongside `run()` for use by the Gradio interface in Phase 5. It yields chunks from the DeepSeek streaming API. The citation block is yielded as the final chunk. The Phase 4 controller always calls `run()` (non-streaming); the Gradio app calls `run_streaming()` directly.

---

## 8. StudyPlannerSkill Plan

**File:** `surgmentor/skills/study_planner_skill.py`  
**Reference:** None — new skill. Data source: `db_store.get_student_stats()` (Phase 1B).  
**Course concept:** Agent Skills (Day 3)

### Purpose

Generate a personalized remediation plan based on the student's complete history. Reads structured data (weak areas, score trajectory, top topics) from SQLite and calls the LLM to synthesize an ordered study plan. The LLM cannot invent weaknesses not present in the student's actual history.

### Design

```
StudyPlannerSkill.run(bundle) → SkillResult

Steps:
1. Fetch student history:
   stats = db_store.get_student_stats(bundle.student_id)
   If stats is empty (new student with no history):
     return SkillResult with onboarding message:
     "Complete at least one OSCE session to receive a personalized study plan."

2. Prepare structured context:
   weak_areas_text  = formatted list of (topic, count) pairs
   score_history    = list of (case_id, score, date) — last 10 results
   avg_score        = stats["osce"]["avg_score"]

3. LLM call:
   messages = [
     {"role": "system", "content": SYSTEM_PROMPT_PLANNER},
     {"role": "user",   "content": format_student_data(stats)}
   ]
   response = DeepSeek call, temperature=0.5, max_tokens=600
   (higher temperature than evaluation: planning benefits from some creativity)

4. Parse LLM response into StudyPlan dataclass:
   @dataclass
   class StudyPlan:
     priority_areas:     list[str]   # top 3 weak areas to address first
     recommended_topics: list[str]   # surgical topics to review
     recommended_cases:  list[str]   # case_ids the student has not yet seen (from db)
     action_items:       list[str]   # concrete next steps ("Start OSCE on topic X")
     encouragement:      str         # one motivational sentence

5. Return SkillResult:
     response_text = formatted plan (priority areas → topics → cases → actions)
     metadata = {"avg_score": avg_score, "weak_areas_count": len(bundle.weak_areas)}
```

### Grounding Rule

The system prompt for this skill must include: "Base your plan ONLY on the data provided. Do not mention clinical topics or cases that are not present in the student's history or the surgical education domain."

### PLANNER System Prompt Design

Module-level constant: `SYSTEM_PROMPT_PLANNER`. Key elements:
1. Role: "You are a surgical education advisor reviewing a student's performance data."
2. Grounding: plan based only on the provided history — do not invent weaknesses.
3. Output format: ordered list — priority areas first, then topics, then recommended next OSCE cases.
4. Tone: constructive, encouraging. Avoid language that feels punitive about low scores.

### `format_student_data(stats)` Helper

Converts the `get_student_stats()` dict into a readable LLM-friendly block:

```
Student Performance Summary
===========================
Sessions completed: 12
OSCE cases attempted: 5
Average OSCE score:  6.4 / 10
Best score:  8  (Case: 3, Periappendiceal abscess)
Worst score: 4  (Case: 1, Acute appendicitis)

Weak areas (by frequency):
  1. Imaging interpretation (4 occurrences)
  2. Management plan (3 occurrences)
  3. History taking (1 occurrence)

Topics studied: Appendicitis, Cholecystitis, Bowel obstruction
```

---

## 9. Test Strategy

### `tests/test_osce_flow.py` — 7 Required Tests

All 7 tests test the skill system end-to-end. Tests that require LLM or ChromaDB calls are **live tests** — they must pass on the native Windows machine. Sandbox-runnable tests (no LLM, no Jina, no ChromaDB) are explicitly identified.

| # | Test | LLM call? | ChromaDB? | Notes |
|---|---|---|---|---|
| 1 | `test_context_bundle_dataclass` | No | No | ContextBundle and SkillResult instantiate with all defaults. Types match spec. **Sandbox-safe.** |
| 2 | `test_skill_abc_enforcement` | No | No | A class that inherits `Skill` but omits `run()` raises `TypeError` on instantiation. **Sandbox-safe.** |
| 3 | `test_evaluation_skill_participation_guard` | No | No | `EvaluationSkill.run()` with 1 student turn (below `MIN_OSCE_TURNS`) returns `SkillResult(session_complete=True)` without calling LLM. Patch `_call_llm` to assert it is NOT called. **Sandbox-safe.** |
| 4 | `test_evaluation_skill_json_parse_failure` | Yes (mocked) | No | If DeepSeek returns non-JSON, `EvaluationSkill.run()` returns safe defaults (score=0, `session_complete=True`). Mock the DeepSeek call. **Sandbox-safe with mock.** |
| 5 | `test_case_retrieval_skill_empty_result` | No | No | If `search_vector_store` returns `[]` (mocked), `CaseRetrievalSkill.run()` returns a "No cases found" message without calling LLM. **Sandbox-safe with mock.** |
| 6 | `test_osce_full_flow` | **Yes** | **Yes** | End-to-end: `OSCEExaminerSkill.run(step=0)` → `run(step=1)` → `run(step=2)` → `run(step=3, finish=True)`. Verify: `session_complete=True`, `evaluation["score"]` is int 0–10, `evaluation["weak_areas"]` is list. **Native machine only.** |
| 7 | `test_eval_log_written` | **Yes** | **Yes** | After test 6, read `eval_log.jsonl` and verify a new `_type: "session_evaluation"` entry exists with matching `session_id`. Use a temp JSONL path. **Native machine only.** |

### Sandbox vs. Native Split

Tests 1–5 are designed to run in the sandbox without network access. Tests 6–7 require both the DeepSeek API and ChromaDB — they are marked `@unittest.skipIf(os.getenv("CI_NO_LLM"), "Skipping live LLM tests in sandbox")` so they are automatically skipped when the `CI_NO_LLM=1` environment variable is set.

**Sandbox verification command:**
```bash
CI_NO_LLM=1 python -m unittest tests/test_osce_flow.py
```
Expected: 5 tests pass, 2 skipped, 0 failures.

**Native machine verification command:**
```bash
python -m unittest tests/test_osce_flow.py
```
Expected: 7 tests pass.

### No Mocking of Core Tools in Live Tests

Tests 6 and 7 use real ChromaDB, real Jina embeddings (via `search_vector_store`), and real DeepSeek API calls. This is consistent with the Phase 1B decision: the system must be tested against real integrations, not against mocks that test the mock's behavior. Test 6 will be slow (~5–10 seconds) — this is acceptable for an integration test.

---

## 10. Dependencies

Phase 3 has zero new external dependencies. All required packages are already in `requirements.txt` (verified during Phase 1A/1B setup).

### Phase 3 Internal Dependencies

| Phase 3 file | Depends on |
|---|---|
| `skills/base.py` | `dataclasses`, `abc` (stdlib) |
| `skills/evaluation_skill.py` | `skills/base.py`, `surgmentor/memory/db_store.py`, `surgmentor/evaluation/logger.py`, `clients.py`, `config.py` |
| `skills/osce_examiner_skill.py` | `skills/base.py`, `skills/evaluation_skill.py`, `surgmentor/rag/retrieval_tool.py`, `clients.py`, `config.py` |
| `skills/case_retrieval_skill.py` | `skills/base.py`, `surgmentor/rag/retrieval_tool.py`, `surgmentor/memory/db_store.py`, `clients.py`, `config.py` |
| `skills/study_planner_skill.py` | `skills/base.py`, `surgmentor/memory/db_store.py`, `clients.py`, `config.py` |
| `tests/test_osce_flow.py` | All four concrete skills, `surgmentor/evaluation/logger.py` |

### Phase 2 Dependency (SecurityLayer)

Phase 3 skills do not import `SecurityLayer` directly. `filter_output()` is the controller's responsibility (Phase 4). The one exception: in Phase 3 integration tests, each skill's standalone `__main__` test may call `SecurityLayer.filter_output()` manually to verify the integration works before the controller exists. This is a test pattern, not a production dependency.

### Phase 4 Readiness Requirements (produced by Phase 3)

After Phase 3, Phase 4 (controller) depends on:

| Symbol | Produced by | Used by |
|---|---|---|
| `ContextBundle` dataclass | `skills/base.py` | `agent/context.py` to build bundles |
| `SkillResult` dataclass | `skills/base.py` | `agent/controller.py` to read skill output |
| `Skill` ABC | `skills/base.py` | `agent/controller.py` skill registry type |
| `CaseRetrievalSkill` | `skills/case_retrieval_skill.py` | registered as `RETRIEVE_CASE` handler |
| `OSCEExaminerSkill` | `skills/osce_examiner_skill.py` | registered as `START_OSCE / OSCE_TURN / FINISH_OSCE` handler |
| `EvaluationSkill` | `skills/evaluation_skill.py` | registered as `GET_FEEDBACK` handler |
| `StudyPlannerSkill` | `skills/study_planner_skill.py` | registered as `STUDY_PLAN` handler |

---

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| DeepSeek API latency makes test_osce_full_flow slow or flaky | Medium | Low | Test is already marked as native-only. Add `timeout=30` to API calls. Accept ~10s test time as acceptable. |
| LLM returns invalid JSON in EvaluationSkill | Medium | Medium | Score parsing has explicit fallback to safe defaults (score=0, feedback="Evaluation unavailable"). Test 4 verifies this path. |
| OSCEExaminerSkill state machine and SessionState osce_step diverge | Medium | High | The skill reads `bundle.osce_step` (controller-provided) and returns `updated_osce_step`. The controller writes back. No state is held in the skill object. Test 6 verifies the step increments correctly across 3 turns. |
| `EvaluationSkill` called from inside `OSCEExaminerSkill._finish()` creates a circular dependency if not managed | Low | High | `EvaluationSkill` does not import from `osce_examiner_skill.py`. The call direction is one-way: OSCEExaminer → Evaluation. No circular import. |
| `StudyPlannerSkill` called on a new student with empty history | Low | Medium | Handled by early-return check: if `get_student_stats()` returns `{}`, return onboarding message without calling LLM. Test scaffold includes this case. |
| `CaseRetrievalSkill` streaming variant breaks if used outside Gradio | Low | Low | `run_streaming()` is a generator method. If called outside an async/streaming context, the caller can collect all chunks with `"".join(run_streaming(bundle))`. Phase 5 handles the Gradio integration. |
| MAX_OSCE_STEPS constant needs to be adjustable for demo pacing | Medium | Low | Add `MAX_OSCE_STEPS` to `config.py` as an env-var-backed constant before Phase 3 implementation. Default: 6. |
| History window trimming in CaseRetrievalSkill may cut relevant context | Low | Low | `HISTORY_WINDOW = 10` passes the last 10 turns. For chat mode this is sufficient. OSCE mode is not windowed (full history required for grading). |

---

## 12. Exit Criteria

Phase 3 is complete when ALL of the following are satisfied:

### Structural (sandbox-verifiable)

1. All five Phase 3 files import without error:
   ```python
   from surgmentor.skills.base import Skill, ContextBundle, SkillResult
   from surgmentor.skills.evaluation_skill import EvaluationSkill
   from surgmentor.skills.osce_examiner_skill import OSCEExaminerSkill
   from surgmentor.skills.case_retrieval_skill import CaseRetrievalSkill
   from surgmentor.skills.study_planner_skill import StudyPlannerSkill
   ```

2. All four concrete skills are instances of `Skill`:
   ```python
   assert isinstance(EvaluationSkill(), Skill)
   assert isinstance(OSCEExaminerSkill(), Skill)
   assert isinstance(CaseRetrievalSkill(), Skill)
   assert isinstance(StudyPlannerSkill(), Skill)
   ```

3. A class inheriting `Skill` without implementing `run()` raises `TypeError`.

4. Tests 1–5 in `test_osce_flow.py` pass with `CI_NO_LLM=1` (no network calls):
   ```bash
   CI_NO_LLM=1 python -m unittest tests/test_osce_flow.py
   # Expected: 5 passed, 2 skipped
   ```

5. Phase 1B and Phase 2 modules still import cleanly (no regressions):
   ```python
   from surgmentor.rag.retrieval_tool import search_vector_store
   from surgmentor.memory.db_store import get_student_stats
   from surgmentor.security.layer import SecurityLayer
   from surgmentor.evaluation.logger import write_turn_signal
   ```

### Functional (native Windows machine — Reza runs)

6. All 7 tests in `test_osce_flow.py` pass with live API keys:
   ```bash
   python -m unittest tests/test_osce_flow.py
   # Expected: 7 passed, 0 failed
   ```

7. End-to-end OSCE flow verification (can be the same run as test 6, or manual):
   ```python
   from surgmentor.skills.osce_examiner_skill import OSCEExaminerSkill
   from surgmentor.skills.base import ContextBundle
   import uuid

   session_id = str(uuid.uuid4())
   student_id = "test-student"
   skill = OSCEExaminerSkill()

   # Step 0: init
   b0 = ContextBundle(student_input="start", session_history=[],
                      current_case=None, student_id=student_id,
                      weak_areas=[], score_history=[], osce_step=0, parameters={})
   r0 = skill.run(b0)
   print("Case loaded:", r0.updated_case["case_id"])
   print("Step now:", r0.updated_osce_step)  # expected: 1

   # Step 1: turn
   b1 = ContextBundle(student_input="The patient is a 28-year-old male with RIF pain",
                      session_history=[{"role": "assistant", "content": r0.response_text}],
                      current_case=r0.updated_case, student_id=student_id,
                      weak_areas=[], score_history=[], osce_step=1, parameters={})
   r1 = skill.run(b1)
   print("Turn 1 response:", r1.response_text[:80])

   # Finish
   bf = ContextBundle(student_input="I'm done", session_history=[...],
                      current_case=r0.updated_case, student_id=student_id,
                      weak_areas=[], score_history=[], osce_step=3,
                      parameters={"finish": True})
   rf = skill.run(bf)
   print("Score:", rf.evaluation["score"])       # expected: int 0–10
   print("Session complete:", rf.session_complete)  # expected: True
   ```

8. `eval_log.jsonl` gains a `_type: "session_evaluation"` entry after the flow above.

---

## 13. Phase 4 Readiness

After Phase 3, the following controller building blocks are ready:

| Controller concern | Phase 3 provides |
|---|---|
| Skill registry type | `Skill` ABC — all four concrete skills are instances |
| Input to skills | `ContextBundle` — controller builds it in `agent/context.py` |
| Output from skills | `SkillResult` — controller reads `response_text`, `session_complete`, `evaluation`, `updated_osce_step` |
| OSCE pipeline | `OSCEExaminerSkill._finish()` → `EvaluationSkill.run()` already tested |
| Multi-skill composition | Three-skill chain (`FINISH_OSCE` → OSCE finish → Evaluation → StudyPlan) is demonstrable |
| Evaluation integration | `EvaluationSkill` writes to SQLite and eval_log; controller only needs to read `SkillResult.evaluation` |

Phase 4 (Agent Controller) may begin after all 12 exit criteria above are confirmed.
