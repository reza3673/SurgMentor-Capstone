# PHASE_4_PLAN.md — Agent Controller

**Project:** SurgMentor — Agentic Surgical Education System
**Phase:** 4 of 7
**Date:** 2026-06-20
**Status:** Awaiting approval
**Authoritative sources:** IMPLEMENTATION_SEQUENCE_REVIEW.md, TARGET_ARCHITECTURE.md,
  MIGRATION_PLAN.md, PHASE_3_PLAN.md, implemented skill interfaces and tests

---

## 1. Objectives

Phase 4 implements the **cognitive core** of SurgMentor: the agent controller that
transforms a sequence of isolated LLM calls into a coherent, stateful educational agent.

The controller is the single most important file in the competition submission. It is
where the ADK agent loop is made visible, where all prior phases connect, and where
the distinction between "a RAG pipeline" and "an agentic system" is demonstrated.

**Specific objectives:**

1. Implement `surgmentor/agent/intent.py` — classify student input into one of 8
   named `IntentCategory` values using a structured LLM call.
2. Implement `surgmentor/agent/context.py` — build a trimmed, skill-relevant
   `ContextBundle` for each skill invocation (Day 1 context engineering principle).
3. Implement `surgmentor/agent/controller.py` — the `AgentController` class with
   the full perceive → plan → act → observe loop, skill registry, security wiring,
   evaluation logging, and session state management.
4. Implement `tests/test_controller.py` — sandbox-safe tests covering routing logic,
   state transitions, security integration, OSCE lifecycle, and fallback behavior.

**Kaggle criteria directly improved by this phase:**

| Criterion | Mechanism |
|---|---|
| Technical Implementation (50 pts) | ADK loop is the primary architectural evidence |
| Agent / ADK concept (required) | `controller.py` is the primary demonstration file |
| Context Engineering (Day 1) | `context.py` per-skill trim logic |
| Security Features (Day 4) | Two-point security wiring in the loop |
| Evaluation (Day 4) | Per-turn TurnSignal written after every cycle |

---

## 2. Files to Implement

Three files replace their Phase 0 placeholders. One new test file is created.

| File | Lines (est.) | Replaces |
|---|---|---|
| `surgmentor/agent/intent.py` | ~160 | placeholder |
| `surgmentor/agent/context.py` | ~140 | placeholder |
| `surgmentor/agent/controller.py` | ~260 | placeholder |
| `tests/test_controller.py` | ~400 | new file |

**No other files are modified.** All skill files, security layer, memory layer, and
evaluation logger are complete and must not be changed during Phase 4.

**Exception rule:** If a bug in a Phase 3 skill is revealed by a Phase 4 controller
test (e.g., a SkillResult field not propagating correctly), the bug must be documented
and fixed in the skill file before the controller test is written to depend on the fix.
Explain the bug and fix before making the change.

---

## 3. IntentCategory Design

`IntentCategory` is a Python `enum.Enum` defined in `intent.py`. Each member maps
one student intent to one controller routing decision.

```python
class IntentCategory(str, Enum):
    RETRIEVE_CASE      = "RETRIEVE_CASE"
    START_OSCE         = "START_OSCE"
    OSCE_TURN          = "OSCE_TURN"
    FINISH_OSCE        = "FINISH_OSCE"
    GET_FEEDBACK       = "GET_FEEDBACK"
    STUDY_PLAN         = "STUDY_PLAN"
    UNKNOWN            = "UNKNOWN"
```

**Rationale for 7 categories (down from 8 in TARGET_ARCHITECTURE.md):**

`CLINICAL_QUESTION` is removed from the MVP set. The `ClinicalReasoningSkill` is not
implemented in Phase 3 — it is listed as a Phase 8 stretch goal in
IMPLEMENTATION_SEQUENCE_REVIEW.md. Including `CLINICAL_QUESTION` as an intent without
a backing skill would require either a stub response or routing to `CaseRetrievalSkill`
as a fallback, which is confusing. The `RETRIEVE_CASE` intent already covers general
surgical questions via `CaseRetrievalSkill`. If `ClinicalReasoningSkill` is added in
Phase 8, `CLINICAL_QUESTION` can be appended to the enum with no controller changes.

**Intent → Skill routing table (full):**

| IntentCategory | Condition | Routed to | SkillResult consumed |
|---|---|---|---|
| `RETRIEVE_CASE` | mode = chat | `CaseRetrievalSkill` | response_text, metadata |
| `START_OSCE` | mode = chat OR osce_active = False | `OSCEExaminerSkill` (_init path) | response_text, updated_case, updated_osce_step |
| `OSCE_TURN` | osce_active = True | `OSCEExaminerSkill` (_turn path) | response_text, updated_osce_step |
| `FINISH_OSCE` | osce_active = True | `OSCEExaminerSkill` (_finish path) | response_text, evaluation, session_complete |
| `GET_FEEDBACK` | always | `EvaluationSkill` | response_text, evaluation |
| `STUDY_PLAN` | always | `StudyPlannerSkill` | response_text, metadata |
| `UNKNOWN` | always | — (safe deflection, no skill) | static string |

**`OSCE_TURN` auto-detection rule:**

When `state.osce_active is True` and the student sends any input that is not an
explicit finish signal, the controller overrides the classified intent with `OSCE_TURN`.
This prevents the intent classifier from misrouting a mid-session clinical response
(e.g., "I would order a CT scan") to `RETRIEVE_CASE`. OSCE session state takes
precedence over intent classification.

**`FINISH_OSCE` signal detection:**

Both explicit ("finish", "done", "end session") and implicit (auto-finish when
`osce_step >= MAX_OSCE_STEPS`) triggers map to `FINISH_OSCE`. The controller checks
`osce_step >= MAX_OSCE_STEPS` before calling the classifier when in OSCE mode.

---

## 4. Intent Classification Strategy

### Why LLM classification, not keyword matching

Keyword matching is brittle. A student typing "can you help me practise OSCE cases?"
would miss a keyword list for `START_OSCE`. A student saying "I want feedback" might
match `GET_FEEDBACK` even when asking for feedback on a free-chat question (not a
scored session). LLM classification at `temperature=0.1` handles natural language
variation correctly and can be shown in code as a reasoning step — which judges can
read as an architectural choice.

### Classification prompt design

The prompt is structured to produce a single-word JSON response:

```
You are classifying a student's message in a surgical education system.

Current session context:
  mode: {state.mode}
  osce_active: {state.osce_active}
  osce_step: {state.osce_step}

Student message: "{student_input}"

Classify this message as EXACTLY ONE of these categories:
  RETRIEVE_CASE   — student wants to see a surgical case or learn about a condition
  START_OSCE      — student wants to begin an OSCE examination session
  OSCE_TURN       — student is mid-OSCE and this is their next response
  FINISH_OSCE     — student wants to end the current OSCE session
  GET_FEEDBACK    — student wants to see their score or past performance
  STUDY_PLAN      — student wants a personalised study plan or guidance on what to study
  UNKNOWN         — message is unclear, out of scope, or cannot be classified above

Respond with ONLY a JSON object, no other text:
{"intent": "<CATEGORY>"}
```

Session context is included in the prompt so the classifier has the information it
needs to distinguish `OSCE_TURN` from `RETRIEVE_CASE` for ambiguous inputs.

### Classification safety rules

1. **JSON parse failure → `UNKNOWN`**. If the LLM returns malformed JSON or a
   category not in the enum, the function falls back to `UNKNOWN`. This must never
   raise an exception.
2. **API call failure → `UNKNOWN`**. Any exception from the DeepSeek call returns
   `UNKNOWN`. A student always gets a response; they never see a stack trace.
3. **Lazy import**. `from clients import deepseek` is inside `classify_intent()`,
   not at module level. Preserves the established sandbox-safe import pattern.
4. **`SCOPE_CLASSIFICATION_ENABLED` flag**. If the flag is `False` (e.g., for low-
   latency testing or when classification is disabled via `.env`), the function uses
   a fast rule-based fallback instead of making an API call. This matches the
   pattern established in Phase 2 (`security/layer.py`).

### Rule-based fallback (when `SCOPE_CLASSIFICATION_ENABLED=false`)

Used in tests (CI_NO_LLM=1) and configurable in production:

```
if "osce" in lower and ("start" in lower or "begin" in lower or "examine" in lower):
    → START_OSCE
elif osce_active and ("finish" in lower or "done" in lower or "end" in lower):
    → FINISH_OSCE
elif osce_active:
    → OSCE_TURN
elif "study" in lower or "plan" in lower or "improve" in lower:
    → STUDY_PLAN
elif "feedback" in lower or "score" in lower or "how did" in lower:
    → GET_FEEDBACK
elif "case" in lower or "show" in lower or any surgical keyword:
    → RETRIEVE_CASE
else:
    → UNKNOWN
```

This fallback is not the primary path but ensures tests and low-latency scenarios
work correctly without an API call.

---

## 5. Context Bundle Construction Strategy

`context.py` implements one function:
`build_context_bundle(intent, student_input, state) → ContextBundle`.

The function applies **per-skill trim rules** — each skill receives only the fields
it needs, not the full session state. This is the Day 1 context engineering principle
made concrete. It is commented explicitly in code.

### Per-skill trim table

| Intent / Skill | student_input | session_history | current_case | weak_areas | score_history | osce_step | parameters |
|---|---|---|---|---|---|---|---|
| `RETRIEVE_CASE` / `CaseRetrievalSkill` | ✓ | windowed (last N) | — | ✓ (bias) | — | — | top_k |
| `START_OSCE` / `OSCEExaminerSkill` | — | — | None (pre-init) | — | ✓ (case selection) | 0 | case_id (optional) |
| `OSCE_TURN` / `OSCEExaminerSkill` | ✓ | full OSCE history | ✓ | — | — | ✓ | — |
| `FINISH_OSCE` / `OSCEExaminerSkill` | — | full OSCE history | ✓ | — | — | ✓ | finish=True, case_id |
| `GET_FEEDBACK` / `EvaluationSkill` | — | full OSCE history | ✓ | — | — | — | case_id, session_id |
| `STUDY_PLAN` / `StudyPlannerSkill` | ✓ | — | — | ✓ | ✓ | — | — |
| `UNKNOWN` | — | — | — | — | — | — | — |

**"windowed" for RETRIEVE_CASE:** `state.conversation_history[-HISTORY_WINDOW:]`
where `HISTORY_WINDOW = 10` (from `config.py`). This limits free-chat context to
the last 10 turns, preventing context overflow on long sessions.

**"full OSCE history" for OSCE turns:** All messages in `state.conversation_history`
from the point OSCE was initiated. The OSCE examiner needs the full transcript to
know what questions have been asked and what the student has answered. No windowing.

**`current_case` for OSCE paths:** Copied directly from `state.current_case`. For
`START_OSCE`, this is `None` — the skill's `_init()` method loads and populates it,
then the controller writes `SkillResult.updated_case` back to `state.current_case`.

**`weak_areas` sourced from session state:** `state.weak_areas` is populated when
the session is created by calling `db_store.get_student_stats(student_id)` and
extracting the `weak_areas` field. This is a one-time load at session start; it is
not refreshed per-turn (the current session's weak areas are only known after it ends).

### History slicing for OSCE context

OSCE conversation history is stored in `state.conversation_history` interleaved with
free-chat turns. When building a bundle for an OSCE skill, the controller must pass
only the turns that belong to the current OSCE session, not prior free-chat turns.

**Strategy:** When OSCE starts (`START_OSCE` intent fires), the controller records
`state.osce_history_start_index = len(state.conversation_history)`. On every
subsequent OSCE bundle build, the history slice is:
`state.conversation_history[state.osce_history_start_index:]`.

`SessionState` gains one new field: `osce_history_start_index: int = 0`.

---

## 6. AgentController.run() Loop Design

`controller.py` implements one class: `AgentController`.

The `run(student_input, session_id)` method is the single entry point used by both
the CLI (`run.py`) and the Gradio interface (`app.py`). It returns a `str` — the
filtered, safe, educator-approved response to send to the student.

### The full loop (with ADK step labels as code comments)

```python
def run(self, student_input: str, session_id: str) -> str:
    start_time = time.time()

    # ── PERCEIVE ────────────────────────────────────────────────────────────
    # Step 1: Read current session state from memory.
    state = self.session_store.read(session_id)

    # Step 2: Pre-flight security — sanitize and validate the input.
    sanitized = self.security.sanitize_input(student_input)
    if sanitized.is_blocked:
        return self.security.get_deflection_message(sanitized.rejection_reason)

    # ── PLAN ────────────────────────────────────────────────────────────────
    # Step 3: Classify student intent using session context.
    intent = classify_intent(sanitized.clean_text, state)

    # Step 4: Apply OSCE session override (state beats classifier).
    intent = self._apply_osce_override(intent, state)

    # Step 5: Select the skill for this intent.
    skill = self._route(intent)

    # Step 6: Build a trimmed context bundle for the selected skill.
    bundle = build_context_bundle(intent, sanitized.clean_text, state)

    # ── ACT ─────────────────────────────────────────────────────────────────
    # Step 7: Invoke the skill. Controller never calls LLM directly.
    if skill is None:
        raw_response = _UNKNOWN_FALLBACK
    else:
        skill_result = skill.run(bundle)
        raw_response = skill_result.response_text

    # ── OBSERVE ─────────────────────────────────────────────────────────────
    # Step 8: Post-flight security — filter the skill output.
    filtered = self.security.filter_output(
        raw_response, osce_step=state.osce_step if state.osce_active else None
    )
    safe_response = filtered.filtered_text

    # Step 9: Update session state with skill result.
    state = self._update_state(state, intent, skill_result if skill else None,
                               filtered.safety_pass)

    # Step 10: Write updated state back to memory.
    self.session_store.write(session_id, state)

    # Step 11: Write per-turn evaluation signal.
    latency_ms = int((time.time() - start_time) * 1000)
    write_turn_signal(TurnSignal(
        session_id        = session_id,
        intent_classified = intent.value,
        skill_selected    = skill.__class__.__name__ if skill else "None",
        output_safety_pass= filtered.safety_pass,
        response_length   = len(safe_response),
        latency_ms        = latency_ms,
    ))

    return safe_response
```

Every step is labeled with its ADK role as a comment in the actual code. This is
not optional — it is the mechanism by which Kaggle judges can read the file and
immediately identify the agentic pattern.

### `_apply_osce_override(intent, state)` logic

```
if state.osce_active:
    if state.osce_step >= MAX_OSCE_STEPS:
        return IntentCategory.FINISH_OSCE
    if intent in (RETRIEVE_CASE, STUDY_PLAN, GET_FEEDBACK, UNKNOWN):
        return IntentCategory.OSCE_TURN
return intent
```

This ensures mid-OSCE inputs are never misrouted, regardless of what the classifier
returns. A student asking "what is appendicitis?" mid-session gets an OSCE response,
not a case retrieval. The session context is authoritative.

### `_route(intent)` skill registry

```python
self._registry = {
    IntentCategory.RETRIEVE_CASE: CaseRetrievalSkill(),
    IntentCategory.START_OSCE:    OSCEExaminerSkill(),
    IntentCategory.OSCE_TURN:     OSCEExaminerSkill(),   # same instance, different dispatch
    IntentCategory.FINISH_OSCE:   OSCEExaminerSkill(),   # finish flag in parameters
    IntentCategory.GET_FEEDBACK:  EvaluationSkill(),
    IntentCategory.STUDY_PLAN:    StudyPlannerSkill(),
    IntentCategory.UNKNOWN:       None,
}
```

`OSCEExaminerSkill` is instantiated once and handles all three OSCE intents. It
distinguishes init / turn / finish via `bundle.osce_step` and
`bundle.parameters.get("finish")` — exactly as designed in Phase 3.

### `_update_state(state, intent, skill_result, safety_pass)` logic

```
append student_input to state.conversation_history (role="user")
if skill_result is not None:
    append skill_result.response_text to state.conversation_history (role="assistant")
    if intent == START_OSCE and skill_result.updated_case:
        state.current_case = skill_result.updated_case
        state.osce_active = True
        state.osce_step = skill_result.updated_osce_step   # = 1
        state.osce_history_start_index = len(state.conversation_history) - 2
        state.mode = "osce"
    elif intent == OSCE_TURN:
        state.osce_step = skill_result.updated_osce_step
    elif intent == FINISH_OSCE or skill_result.session_complete:
        state.osce_active = False
        state.osce_step = 0
        state.current_case = None
        state.mode = "chat"
        if skill_result.evaluation:
            state.score_history.append({
                "case_id":      skill_result.evaluation.get("case_id", "unknown"),
                "score":        skill_result.evaluation.get("score", 0),
                "completed_at": datetime.now().isoformat(),
            })
            new_weak_areas = skill_result.evaluation.get("weak_areas", [])
            state.weak_areas = _merge_weak_areas(state.weak_areas, new_weak_areas)
if not safety_pass:
    # count safety events; could be persisted to SessionEvaluation
    state.safety_event_count = getattr(state, "safety_event_count", 0) + 1
```

`_merge_weak_areas(existing, new)` appends new weak areas, deduplicates, and keeps
the list at most 10 items (oldest dropped). This ensures `weak_areas` stays bounded
and reflects the student's recent pattern, not their entire history.

---

## 7. Skill Registry Design

The skill registry is a `dict[IntentCategory, Skill | None]` instantiated in
`AgentController.__init__()`. All skills are instantiated once at controller init
and reused across calls (they are stateless per call — state lives in `SessionState`).

```python
from surgmentor.skills.case_retrieval_skill import CaseRetrievalSkill
from surgmentor.skills.osce_examiner_skill  import OSCEExaminerSkill
from surgmentor.skills.evaluation_skill     import EvaluationSkill
from surgmentor.skills.study_planner_skill  import StudyPlannerSkill

class AgentController:
    def __init__(self, session_store=None, security=None):
        self.session_store = session_store or default_store
        self.security      = security      or security_layer

        self._registry: dict[IntentCategory, Skill | None] = {
            IntentCategory.RETRIEVE_CASE: CaseRetrievalSkill(),
            IntentCategory.START_OSCE:    OSCEExaminerSkill(),
            IntentCategory.OSCE_TURN:     OSCEExaminerSkill(),
            IntentCategory.FINISH_OSCE:   OSCEExaminerSkill(),
            IntentCategory.GET_FEEDBACK:  EvaluationSkill(),
            IntentCategory.STUDY_PLAN:    StudyPlannerSkill(),
            IntentCategory.UNKNOWN:       None,
        }
```

**Dependency injection for `session_store` and `security`:** Both are injected via
`__init__` parameters with module-level singletons as defaults. Tests can pass
isolated `InMemorySessionStore()` instances and mock `SecurityLayer` objects without
patching globals. This is the testability pattern established in Phase 2.

**Single `OSCEExaminerSkill` instance for three intents:** This is intentional.
`OSCEExaminerSkill.run()` is stateless — it reads `bundle.osce_step` and
`bundle.parameters.get("finish")` to decide which internal method to call. The
same instance correctly handles init, turn, and finish.

**`None` for `UNKNOWN`:** The controller checks `if skill is None` and returns the
static fallback string. This keeps the fallback path visible and avoids routing to
a skill that has no meaningful action for unknown input.

---

## 8. SessionState Read/Write Flow

### Session creation

```
first call with session_id
  → session_store.read(session_id)   # creates default state if absent
  → db_store.get_student_stats(student_id)  # load historical weak areas
  → state.weak_areas = stats.get("weak_areas", [])
  → state.score_history = stats.get("recent_osce", [])
  → session_store.write(session_id, state)
```

The historical context load happens **once at session creation**, not on every turn.
This ensures the planner and retrieval skills see the student's gap areas without
a per-turn DB round trip.

### Per-turn read/write cycle

```
run(input, session_id):
  state = session_store.read(session_id)    # always reads current state
  ... (perceive, plan, act, observe) ...
  state = _update_state(state, ...)         # mutates in memory
  session_store.write(session_id, state)    # writes back
```

The write always succeeds (in-memory store). In a Redis-backed store, failure to
write would need retry logic — noted here for Phase 8 upgrade documentation.

### `osce_history_start_index` — new field in SessionState

This field is required by the OSCE context builder (Section 5). It is added to
`SessionState` in `session.py` with a default of `0`:

```python
osce_history_start_index: int = 0   # index into conversation_history where OSCE started
```

This is the **only change to any Phase 3 or earlier file** permitted in Phase 4.
It is additive (new field with a default) and backward-compatible with all existing
tests, which do not set this field.

---

## 9. SecurityLayer Integration

The security layer runs at two points in the controller loop, exactly as designed in
Phase 2 and documented in `layer.py`'s class docstring:

### Pre-flight (input sanitization) — Step 2 in the loop

```python
sanitized = self.security.sanitize_input(student_input)
if sanitized.is_blocked:
    return self.security.get_deflection_message(sanitized.rejection_reason)
```

The controller returns immediately on blocked input. No intent classification, no
skill call, no state update. The blocked message is still a valid string returned
to the student — they see a polite explanation, not an error.

**What is blocked at pre-flight:** long inputs (> `MAX_INPUT_LENGTH`), PII patterns,
prompt injection heuristics, and out-of-scope requests (if `SCOPE_CLASSIFICATION_ENABLED`).
Reference: `tests/test_security.py` for the full test matrix.

### Post-flight (output filtering) — Step 8 in the loop

```python
filtered = self.security.filter_output(
    raw_response,
    osce_step=state.osce_step if state.osce_active else None
)
safe_response = filtered.filtered_text
```

`filter_output` always returns a `FilteredOutput` — it never raises. `filtered_text`
is the safe version, with the educational disclaimer appended and any hard-block
patterns replaced. The controller uses `filtered_text`, never `original_text`.

**`osce_step` is passed** to allow the filter to append the step number to OSCE
responses (e.g., `"[OSCE Step 2 of 6]"`). This prevents students from losing track
of where they are in the session. The filter uses `None` for non-OSCE responses.

### Safety event counting

`filtered.safety_pass` is read in `_update_state`. If `False`, the controller
increments a `safety_event_count` in the session state. This count is included in
the `SessionEvaluation` record written at OSCE finish, providing judges with evidence
that the safety layer is active and measurable.

---

## 10. Evaluation Logging Integration

The evaluation logger writes two record types. The controller writes both.

### Per-turn: TurnSignal — Step 11 in the loop

Written after every successful `run()` call, including UNKNOWN fallbacks:

```python
write_turn_signal(TurnSignal(
    session_id         = session_id,
    intent_classified  = intent.value,
    skill_selected     = skill.__class__.__name__ if skill else "None",
    output_safety_pass = filtered.safety_pass,
    response_length    = len(safe_response),
    latency_ms         = latency_ms,
))
```

`TurnSignal` is already defined in `surgmentor/evaluation/logger.py` (Phase 1B).
The controller is its primary writer. Every call to `run()` produces exactly one
`TurnSignal` line in `eval_log.jsonl`.

### Per-session: SessionEvaluation — written by EvaluationSkill

`SessionEvaluation` is written inside `EvaluationSkill.run()` (already implemented
in Phase 3). The controller does not write it directly. The controller's role is:

1. Detect that `skill_result.session_complete is True` after a `FINISH_OSCE` call.
2. Detect that `skill_result.evaluation` is populated.
3. Write the evaluation dict back to `state.score_history` and merge `weak_areas`.
4. Return the response text to the student.

The `SessionEvaluation` record in `eval_log.jsonl` was written by `EvaluationSkill`
during the skill call (Step 7) — the controller does not need to write it again.

### Evaluation log as audit trail

After a 3-turn OSCE session, `eval_log.jsonl` should contain exactly:
- 1 `TurnSignal` for `START_OSCE`
- 1 `TurnSignal` for each `OSCE_TURN` (3 turns = 3 signals)
- 1 `TurnSignal` for `FINISH_OSCE`
- 1 `SessionEvaluation` (written by EvaluationSkill)

Total: 6 lines per 3-turn OSCE session. Judges can inspect this file as evidence
of the evaluation architecture.

---

## 11. OSCE Routing Logic

OSCE routing is the most complex control flow in the controller. This section makes
it explicit and unambiguous.

### Full OSCE session state machine

```
State: chat (osce_active=False, osce_step=0)

Student: "start osce"
  → classify_intent → START_OSCE
  → _apply_osce_override: osce_active=False, no override
  → route → OSCEExaminerSkill
  → build_context: current_case=None, osce_step=0, score_history=state.score_history
  → skill._init(): picks unseen case, calls LLM, returns updated_case + osce_step=1
  → _update_state:
      state.current_case = skill_result.updated_case
      state.osce_active = True
      state.osce_step = 1
      state.osce_history_start_index = len(history) - 2
      state.mode = "osce"

State: osce (osce_active=True, osce_step=1)

Student: "I would take a history focusing on the onset of pain..."
  → classify_intent → (may return anything, e.g., RETRIEVE_CASE)
  → _apply_osce_override: osce_active=True, intent → OSCE_TURN
  → route → OSCEExaminerSkill
  → build_context: full osce history, current_case, osce_step=1
  → skill._turn(): calls LLM, returns response, updated_osce_step=2
  → _update_state: state.osce_step = 2

... (repeat for turns 3, 4, 5, 6) ...

Auto-finish path:
  osce_step=6 → _apply_osce_override: osce_step >= MAX_OSCE_STEPS → FINISH_OSCE
  (student's input is ignored; session closes regardless)

Explicit finish path:
  Student: "I'm done"
  → classify_intent → FINISH_OSCE
  → _apply_osce_override: osce_active=True but intent already=FINISH_OSCE, no change
  → route → OSCEExaminerSkill
  → build_context: full osce history, current_case, osce_step=N, finish=True in parameters
  → skill._finish(): calls EvaluationSkill.run(), returns evaluation, session_complete=True
  → _update_state:
      state.osce_active = False
      state.osce_step = 0
      state.current_case = None
      state.mode = "chat"
      state.score_history.append(...)
      state.weak_areas = _merge_weak_areas(...)

State: chat (osce_active=False, osce_step=0)
```

### Edge cases and how the controller handles them

| Scenario | Controller behaviour |
|---|---|
| Student says "start osce" when osce_active=True | `_apply_osce_override` → `OSCE_TURN`; message treated as next OSCE response |
| Student says "show me a case" mid-OSCE | `_apply_osce_override` → `OSCE_TURN`; OSCE continues |
| Student says "finish" when osce_active=False | Routes to `OSCEExaminerSkill` with finish=True; skill participates in guard and returns "no active session" message |
| OSCE auto-finishes at step 6 | Controller sets finish=True in parameters; student's actual message is not sent to LLM |
| `EvaluationSkill` returns participation guard result | `skill_result.session_complete=True`; controller transitions to chat mode regardless |
| `OSCEExaminerSkill._init()` raises | Exception caught; fallback string returned; state unchanged |

---

## 12. Test Strategy

All Phase 4 tests live in `tests/test_controller.py`. Tests follow the same
conventions established in Phase 2 (`test_security.py`) and Phase 3
(`test_osce_flow.py`).

### Test environment setup

```python
# Module-level — before any surgmentor import
import config
config.SCOPE_CLASSIFICATION_ENABLED = False   # use rule-based fallback in all tests
config.AGENT_SESSION_DB_PATH = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
config.EVAL_LOG_PATH         = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False).name

import importlib, surgmentor.memory.db_store as db_store_module
importlib.reload(db_store_module)
db_store_module.init_database()

_LIVE_LLM = not os.getenv("CI_NO_LLM")
```

### Test classes and coverage

**`Test01IntentCategory` (4 tests) — sandbox-safe**
- Enum members exist: all 7 categories importable
- String values match member names
- Invalid string does not produce valid category (raises ValueError)
- `UNKNOWN` is a valid category (no exception on access)

**`Test02ClassifyIntent` (8 tests) — sandbox-safe (rule-based fallback)**
- "start osce" → `START_OSCE`
- "finish" with osce_active=True → `FINISH_OSCE`
- "I would order a CT" with osce_active=True → `OSCE_TURN`
- "what should I study" → `STUDY_PLAN`
- "how did I do" → `GET_FEEDBACK`
- "show me a case about appendicitis" → `RETRIEVE_CASE`
- Garbage input → `UNKNOWN`
- LLM disabled (CI_NO_LLM): classification still returns a valid IntentCategory

**`Test03ContextBundleBuilder` (8 tests) — sandbox-safe**
- `RETRIEVE_CASE` bundle: history windowed to HISTORY_WINDOW; weak_areas present
- `START_OSCE` bundle: current_case is None; osce_step = 0
- `OSCE_TURN` bundle: full osce history slice (not windowed); current_case present
- `FINISH_OSCE` bundle: `parameters["finish"]` = True; case_id present
- `STUDY_PLAN` bundle: no session_history; weak_areas and score_history present
- `GET_FEEDBACK` bundle: full history; current_case present
- History windowing: history of length HISTORY_WINDOW+6 → windowed to HISTORY_WINDOW
- OSCE history slicing: chat turns before OSCE start excluded from OSCE bundle

**`Test04ControllerRouting` (8 tests) — sandbox-safe (all skills mocked)**
- `RETRIEVE_CASE` → `CaseRetrievalSkill.run()` called once
- `START_OSCE` → `OSCEExaminerSkill.run()` called once
- `OSCE_TURN` → `OSCEExaminerSkill.run()` called once (via osce override)
- `FINISH_OSCE` → `OSCEExaminerSkill.run()` called once (finish=True in bundle)
- `STUDY_PLAN` → `StudyPlannerSkill.run()` called once
- `GET_FEEDBACK` → `EvaluationSkill.run()` called once
- `UNKNOWN` → no skill called; static fallback returned
- Blocked input → no skill called; deflection message returned

**`Test05SessionStateTransitions` (8 tests) — sandbox-safe**
- After `START_OSCE`: `state.osce_active=True`, `state.osce_step=1`, `state.mode="osce"`
- After `START_OSCE`: `state.current_case` is populated from SkillResult.updated_case
- After `OSCE_TURN`: `state.osce_step` increments by 1
- After `FINISH_OSCE`: `state.osce_active=False`, `state.osce_step=0`, `state.mode="chat"`
- After `FINISH_OSCE` with evaluation: `state.score_history` gains an entry
- After `FINISH_OSCE` with weak_areas: `state.weak_areas` is updated
- `conversation_history` gains user + assistant turns after each call
- State persists across multiple `run()` calls on same session_id

**`Test06OSCEOverride` (4 tests) — sandbox-safe**
- `RETRIEVE_CASE` intent + osce_active=True → overridden to `OSCE_TURN`
- `STUDY_PLAN` intent + osce_active=True → overridden to `OSCE_TURN`
- `FINISH_OSCE` intent + osce_active=True → not overridden (stays `FINISH_OSCE`)
- `osce_step >= MAX_OSCE_STEPS` → overridden to `FINISH_OSCE` regardless of intent

**`Test07EvaluationLogging` (4 tests) — sandbox-safe**
- After `run()`: `eval_log.jsonl` contains at least one new line
- `TurnSignal` written contains correct `session_id`, `intent_classified`, `skill_selected`
- `output_safety_pass` is True for normal output
- `latency_ms` is a non-negative integer

**`Test08SecurityIntegration` (4 tests) — sandbox-safe**
- Blocked input: controller returns deflection message (not skill output)
- Normal input: passes through; disclaimer present in response
- Modified output (filter fires): `filtered.safety_pass = False` reflected in log
- OSCE output: `osce_step` forwarded to `filter_output()`

**`Test09LiveControllerFlow` (2 tests) — native machine only, `@skipIf(not _LIVE_LLM, ...)`**
- Full OSCE session: `start osce` → 3 turns → `finish` → score returned; `eval_log.jsonl` gains SessionEvaluation line
- Free chat: "show me a case about appendicitis" → response contains "**Sources:**"

### Mocking pattern

```python
# Mock a skill's run() without calling LLM or ChromaDB:
from unittest.mock import patch, MagicMock
mock_result = SkillResult(response_text="Case presented.", metadata={})
with patch.object(controller._registry[IntentCategory.RETRIEVE_CASE],
                  "run", return_value=mock_result):
    response = controller.run("show me a case", "session-1")
```

All sandbox tests mock skill `run()` methods. The controller logic (routing, state
transitions, security wiring, logging) is tested independently of skill LLM calls.

### Running tests

```bash
# Sandbox-safe (no API keys needed):
PYTHONPYCACHEPREFIX=/tmp/pycache_surgmentor CI_NO_LLM=1 \
  python -m unittest tests/test_controller.py -v

# Full suite (requires .env with DEEPSEEK_API_KEY + populated ChromaDB):
python -m unittest tests/test_controller.py -v

# All phases together:
python -m unittest discover -s tests -v
```

---

## 13. Dependencies

### All prior phases must be complete before Phase 4 begins

| Dependency | Status | Used by |
|---|---|---|
| `surgmentor/skills/base.py` | ✅ Phase 3A | `context.py` (ContextBundle), controller type hints |
| `surgmentor/skills/evaluation_skill.py` | ✅ Phase 3A | skill registry; `GET_FEEDBACK` path |
| `surgmentor/skills/osce_examiner_skill.py` | ✅ Phase 3B | skill registry; all OSCE paths |
| `surgmentor/skills/case_retrieval_skill.py` | ✅ Phase 3C | skill registry; `RETRIEVE_CASE` path |
| `surgmentor/skills/study_planner_skill.py` | ✅ Phase 3C | skill registry; `STUDY_PLAN` path |
| `surgmentor/security/layer.py` | ✅ Phase 2 | pre-flight + post-flight in controller loop |
| `surgmentor/memory/session.py` | ✅ Phase 1B | `SessionState`, `InMemorySessionStore`, `default_store` |
| `surgmentor/evaluation/logger.py` | ✅ Phase 1B | `TurnSignal`, `write_turn_signal` |
| `surgmentor/memory/db_store.py` | ✅ Phase 1B | `get_student_stats` at session creation |
| `config.py` | ✅ Phase 0 | `HISTORY_WINDOW`, `MAX_OSCE_STEPS`, `SCOPE_CLASSIFICATION_ENABLED` |
| `clients.py` | ✅ Phase 0 | lazy import in `classify_intent()` |

### `MAX_OSCE_STEPS` import

`MAX_OSCE_STEPS = 6` is currently defined as a module-level constant in
`surgmentor/skills/osce_examiner_skill.py`. The controller needs this value
in `_apply_osce_override()`. Two options:

**Option A (recommended):** Import it from the skill module:
`from surgmentor.skills.osce_examiner_skill import MAX_OSCE_STEPS`

**Option B:** Move `MAX_OSCE_STEPS` to `config.py`.

Option A is preferred because `MAX_OSCE_STEPS` is a skill parameter, not a
system-wide config value. If the skill is modified (e.g., more steps added),
the constant travels with it. Option B will be chosen only if the import creates
a circular dependency during testing.

### `osce_history_start_index` field addition to SessionState

`session.py` gains one new field. This is the only permitted change to Phase 1B code:

```python
# in SessionState dataclass:
osce_history_start_index: int = 0
```

This field is backward-compatible. All existing Phase 3 tests construct `SessionState`
objects (via `ContextBundle`, not directly), so no test changes are needed.

---

## 14. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Intent classifier misroutes at `temperature=0.1` | Medium | Low | `OSCE_TURN` override catches most misroutes mid-session. End-to-end `Test09LiveControllerFlow` validates classifier on real inputs. |
| `osce_history_start_index` off-by-one produces wrong history slice | Medium | Medium | Dedicated test in `Test03ContextBundleBuilder`: assert chat turns before OSCE are excluded from OSCE bundle |
| `_update_state` misses a state field after `FINISH_OSCE` (e.g., forgets to clear `current_case`) | Medium | Medium | `Test05SessionStateTransitions` tests all fields explicitly after each transition |
| Skill instance in registry maintains accidental state between calls | Low | High | All Phase 3 skills are stateless by design (verified in tests). Document: "skills must not store instance state across calls" |
| `write_turn_signal` fails (file path issue, JSON serialization error) | Low | Low | `write_turn_signal` already swallows exceptions (Phase 1B design). Controller loop continues; response is unaffected |
| `_merge_weak_areas` deduplication removes meaningful duplicates | Low | Low | Test: passing ["History taking", "History taking"] produces ["History taking"] once |
| `MAX_OSCE_STEPS` import creates circular dependency | Low | Medium | Move to `config.py` as Option B; update `osce_examiner_skill.py` to import from config |
| `pycache` staleness on mounted volume (known from Phase 3) | High | Low | Run all tests with `PYTHONPYCACHEPREFIX=/tmp/pycache_surgmentor`; document in test section |

---

## 15. Exit Criteria

Phase 4 is complete when all of the following are true:

### Structural

- [ ] `surgmentor/agent/intent.py` exists, compiles, defines `IntentCategory` enum with 7 members and `classify_intent()` function
- [ ] `surgmentor/agent/context.py` exists, compiles, defines `build_context_bundle()` with per-skill trim logic
- [ ] `surgmentor/agent/controller.py` exists, compiles, defines `AgentController` class with `run()` method and all 11 steps labeled with ADK comments
- [ ] `tests/test_controller.py` exists with at least 48 sandbox-safe tests across 8 test classes
- [ ] `session.py` has `osce_history_start_index: int = 0` field added

### Functional

- [ ] `CI_NO_LLM=1 python -m unittest tests/test_controller.py` passes with 0 failures
- [ ] `CI_NO_LLM=1 python -m unittest discover -s tests -v` passes all tests (controller + security + osce_flow) with 0 failures
- [ ] `IntentCategory.UNKNOWN` input returns a non-empty, non-exception response
- [ ] Blocked input (PII pattern) returns deflection message, no skill called
- [ ] State after `START_OSCE` has `osce_active=True` and `mode="osce"`
- [ ] State after `FINISH_OSCE` has `osce_active=False` and `mode="chat"`
- [ ] `eval_log.jsonl` gains one `TurnSignal` entry per `run()` call

### ADK visibility

- [ ] `controller.py` has comments at each step: `# ── PERCEIVE`, `# ── PLAN`, `# ── ACT`, `# ── OBSERVE`
- [ ] Each comment labels which ADK principle the step implements

### Code quality

- [ ] No Phase 3 or earlier test regressions (all existing tests still pass)
- [ ] No `from clients import deepseek` at module level in any Phase 4 file
- [ ] Controller does not call the LLM directly — all LLM calls are inside skills or `classify_intent()`

---

*After creating docs/PHASE_4_PLAN.md: stop and wait for approval before implementation.*
