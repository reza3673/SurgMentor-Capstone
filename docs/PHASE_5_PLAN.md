# PHASE_5_PLAN.md — Entry Interfaces

**Project:** SurgMentor — Agentic Surgical Education System  
**Phase:** 5 of 7  
**Date:** 2026-06-20  
**Status:** Awaiting approval  
**Authoritative sources:** IMPLEMENTATION_SEQUENCE_REVIEW.md, TARGET_ARCHITECTURE.md,
  PHASE_4_PLAN.md, implemented AgentController API (`controller.run(input_text, session_id) → str`)

---

## 1. Objectives

Phase 5 wraps the completed AgentController in two entry interfaces: a CLI REPL
(`run.py`) and a Gradio web application (`app.py`). Both interfaces are thin shells.
All intelligence, routing, state management, security, and evaluation remain inside
the controller and skill layers already built in Phases 1–4. Neither interface calls
a skill directly.

**Specific objectives:**

1. Implement `run.py` — an interactive REPL for terminal-based testing and debugging.
   Validates the controller end-to-end before Gradio complexity is added.
2. Implement `app.py` — a three-tab Gradio application that surfaces all major agent
   capabilities to a non-technical evaluator (competition judges, demo audience).
3. Verify the complete local setup flow in one linear sequence — the exact sequence
   that will appear in the competition video.
4. Confirm all 133 existing tests still pass after the two new files are added.

**Kaggle criteria directly improved by this phase:**

| Criterion | Mechanism |
|---|---|
| Deployability (required concept) | Working Gradio app; local setup is a single script sequence |
| Technical Implementation (50 pts) | Running system visible to judges |
| Video demo content | All three Gradio tabs are demo-able |

**What Phase 5 does NOT include:**

- README, architecture diagram, video, Kaggle writeup (Phase 6–7)
- MCP server, A2A topology (Phase 8 stretch)
- Deployment to Hugging Face Spaces or any cloud host (Phase 8 stretch)
- Any new skills or controller logic — controller is imported as-is from Phase 4

---

## 2. Files to Implement

Two files replace their Phase 0 placeholders:

| File | Lines (est.) | Description |
|---|---|---|
| `run.py` | ~80 | CLI REPL: read → `controller.run()` → print, loop |
| `app.py` | ~280 | Gradio 3-tab app: Chat / OSCE / Student Profile |

No other files are created or modified in Phase 5.

---

## 3. CLI Design — `run.py`

### Purpose

`run.py` is a minimal command-line REPL that proves `controller.run()` works end-to-end
in a local environment with live API keys, populated ChromaDB, and a real SQLite database.
It is a debugging tool and a fallback demo surface, not the primary user interface.

### Session ID strategy

The CLI uses a single persistent session ID per process invocation. On startup,
`run.py` generates a UUID4 and uses it for every turn in that REPL session:

```python
session_id = str(uuid.uuid4())
```

This means session state (conversation history, OSCE progress, weak areas) accumulates
correctly across turns. Restarting the CLI creates a new session — by design. The student
is always identified as `session_id` for this interface (SQLite records will use the
session UUID as the student identifier).

There is no `--student-id` argument in Phase 5. If multi-student CLI use becomes
necessary, it is a Phase 8 enhancement.

### Commands

The CLI responds to three meta-commands in addition to any student input the controller
accepts:

| Command | Behavior |
|---|---|
| `exit` or `quit` | Print goodbye message, exit cleanly |
| `reset` | Generate a new UUID session_id, clear the old session from memory, print confirmation |
| `help` | Print a brief usage reminder (available intents and meta-commands) |

Any other input is forwarded verbatim to `controller.run(input_text, session_id)` and
the result is printed. No post-processing is done by `run.py` — formatting is the
controller's responsibility.

### Startup sequence

On startup, `run.py` must:

1. Import `config` and verify that `DEEPSEEK_API_KEY` and `JINA_API_KEY` are set
   (non-empty strings). If either is missing, print a clear error and exit with code 1.
   Do not raise an uncaught exception.
2. Call `db_store.init_database()` to ensure the SQLite schema exists.
3. Print a brief welcome header (name, version note, session ID, `help` reminder).
4. Enter the REPL loop.

### Error handling

All exceptions raised by `controller.run()` are caught in `run.py`. On exception:
- Print a user-friendly error line: `[Error] Something went wrong. Please try again.`
- Print the exception type and message at DEBUG level if `--debug` flag is set.
- Do not exit — continue the REPL loop.

A `KeyboardInterrupt` (Ctrl+C) exits cleanly with a farewell message.

### Invocation

```bash
python run.py            # normal mode
python run.py --debug    # show exception tracebacks
```

---

## 4. Gradio App Design — `app.py`

### Framework version and constraints

Gradio 4.x (`gradio>=4.0`). Use blocking (non-streaming) responses for all LLM
interactions in Phase 5. Streaming is an optional Phase 8 enhancement — blocking is
fully acceptable for judging and avoids generator-pattern complexity in the controller.

The app must launch cleanly with `python app.py` and be accessible at `http://localhost:7860`.
It must not require any environment setup beyond `.env` keys and a populated ChromaDB.

### Overall structure

`app.py` defines a single `gr.Blocks()` application with three tabs. The module-level
`controller` singleton (imported from `surgmentor.agent.controller`) is shared across
all tabs. Each tab manages its own Gradio state object for session ID and display state.

```python
from surgmentor.agent.controller import controller
import gradio as gr
```

No other imports from the `surgmentor` package are needed in `app.py`, except
`db_store.get_student_stats()` for the Student Profile tab data fetch.

### Tab 1 — Free Chat

**Purpose:** Demonstrate `CaseRetrievalSkill` (and UNKNOWN fallback). The student asks
surgical questions or requests cases. The agent retrieves relevant cases from ChromaDB
and responds with structured case context + citations.

**UI components:**

| Component | Type | Description |
|---|---|---|
| Chat history | `gr.Chatbot` | Displays the conversation. Persists for the session. |
| Input box | `gr.Textbox` | Student message. Submit on Enter or button click. |
| Send button | `gr.Button` | Triggers the controller call. |
| Clear button | `gr.Button` | Clears the Chatbot display and resets the session. |
| Session ID display | `gr.Markdown` (small) | Shows the current session UUID (for debugging). |

**Behavior:**

1. On send: append the user message to the `gr.Chatbot` history immediately, then call
   `controller.run(user_message, session_id)` and append the response.
2. On clear: generate a new session UUID, clear the chatbot history, reset state.
3. The session ID shown is the same ID passed to `controller.run()`. This allows a
   judge to grep `eval_log.jsonl` for that session's audit trail.

**Gradio state:** `gr.State` holds `session_id` (str) and `chat_history` (list[list]).

### Tab 2 — OSCE Examination

**Purpose:** Demonstrate the full OSCE lifecycle: start → turns → finish → score display.
This is the highest-value tab for the competition demo.

**UI components:**

| Component | Type | Description |
|---|---|---|
| Chat display | `gr.Chatbot` | OSCE turn history (examiner + student messages). |
| Input box | `gr.Textbox` | Student response to the examiner. |
| Send button | `gr.Button` | Submit the student's response. Visible during an active session. |
| Start OSCE button | `gr.Button` | Sends `"start osce"` to the controller. Visible when no session is active. |
| Finish OSCE button | `gr.Button` | Sends `"finish"` to the controller. Visible during an active session. |
| Score display | `gr.Markdown` | Renders the final score block after `FINISH_OSCE`. Hidden during active session. |
| Session status | `gr.Markdown` | Shows "Session active — Step N / MAX" or "No active session". |
| Reset button | `gr.Button` | Clears the OSCE display and resets state, regardless of session state. |

**Behavior:**

OSCE tab state tracks `osce_active` (bool) and `osce_step` (int) locally in Gradio
state, mirroring the SessionState held by the controller. This allows buttons to
show/hide correctly without querying the controller's internal state.

1. **Start:** user clicks "Start OSCE" → `controller.run("start osce", session_id)` →
   response is the examiner's first question → appended to chatbot. Set `osce_active=True`.
   Show Send and Finish buttons. Hide Start button.

2. **Turn:** user types response → `controller.run(response, session_id)` → examiner's
   next question → appended to chatbot. Increment `osce_step` in local state.

3. **Finish:** user clicks "Finish OSCE" or inputs a finish phrase →
   `controller.run("finish", session_id)` → response contains the score block →
   Score display becomes visible with the full response text. Set `osce_active=False`.
   Restore Start button visibility. Hide Send/Finish.

4. **Auto-finish signal:** the controller applies the `MAX_OSCE_STEPS` override internally.
   The OSCE tab does not need to track this limit — when the controller routes to FINISH_OSCE
   automatically, the response will contain the score text, and `app.py` detects this by
   checking whether the response contains a score marker string (defined as a constant).

5. **Reset:** clears all display, resets local state to `osce_active=False`, generates
   a new session UUID. This is a UI reset only — the controller's session store already
   cleared its OSCE state when the session finished.

**Score display detection:**

The controller's response after FINISH_OSCE will contain a score block formatted by
`EvaluationSkill`. `app.py` uses a simple string check to detect the finish response:

```python
OSCE_FINISH_MARKERS = ["Score:", "score:", "Final Score", "session complete"]
is_finish_response = any(m in response for m in OSCE_FINISH_MARKERS)
```

When `is_finish_response` is True, move the response text to the Score display
component rather than (or in addition to) the chatbot history.

**Gradio state:** `gr.State` holds `session_id`, `chat_history`, `osce_active` (bool),
`osce_step` (int).

### Tab 3 — Student Profile

**Purpose:** Demonstrate persistent student data and the `StudyPlannerSkill`. Shows
the student's OSCE history, weak areas, and generates a personalised study plan
via the controller.

**UI components:**

| Component | Type | Description |
|---|---|---|
| Stats display | `gr.Markdown` | Session count, OSCE count, avg score, best/worst, weak areas, recent results. |
| Refresh button | `gr.Button` | Re-fetches stats from SQLite and re-renders the Markdown. |
| Study Plan header | `gr.Markdown` | Section header. |
| Generate Plan button | `gr.Button` | Sends `"what should I study"` to the controller → displays the plan. |
| Plan display | `gr.Markdown` | Shows the plan returned by the controller (StudyPlannerSkill output). |

**Stats fetch:**

The Student Profile tab calls `db_store.get_student_stats(session_id)` directly —
not through the controller — because stats display is a pure read operation that
does not need security filtering, intent classification, or state mutation.

If `get_student_stats()` returns `None` (new student, no history), display the
onboarding message: "No OSCE sessions completed yet. Complete a session in the
OSCE tab to see your profile here."

If stats exist, render them as a structured Markdown block using the same formatting
as `StudyPlannerSkill._format_student_data()` — reuse that method by importing the
skill, or duplicate the format logic inline. Duplication is acceptable here because
the display format and the LLM prompt format may diverge in Phase 8.

**Study plan generation:**

Clicking "Generate Plan" calls `controller.run("what should I study", session_id)`.
The controller classifies this as `STUDY_PLAN`, invokes `StudyPlannerSkill`, and
returns a formatted plan string. The plan is displayed in the Plan display component.

**Session ID sharing:**

The Student Profile tab shares the same session ID as the OSCE tab. This ensures
that if the student completes an OSCE session in Tab 2 and then clicks "Refresh"
in Tab 3, the stats reflect that session's results (subject to SQLite write timing
— the controller writes results at FINISH_OSCE time, before the response is returned).

---

## 5. Session ID Strategy

### Principles

1. **One session ID per Gradio user session.** Generated as `str(uuid.uuid4())` when
   `app.py` initializes the Gradio state. Persists for the lifetime of the browser tab.
   Closing the tab and reopening creates a new session.

2. **Session ID doubles as student ID.** `AgentController._get_or_init_state()` uses
   `session_id` as both the memory key and the `student_id` passed to `db_store`.
   This means all three tabs sharing the same session ID read and write the same
   student record in SQLite.

3. **Tabs share the session ID via a top-level `gr.State`.** A single `gr.State`
   object at the `gr.Blocks` level holds the session UUID and is passed to all
   three tab event handlers. This ensures Tab 2 (OSCE) and Tab 3 (Profile) refer to
   the same student.

4. **CLI uses a UUID4 per process.** No persistence across CLI restarts. This is
   acceptable for Phase 5. Cross-session CLI persistence is a Phase 8 enhancement.

5. **No authentication in Phase 5.** The Gradio app is local-only (`server_name="0.0.0.0"`,
   `share=False`). The competition demo does not require user accounts or login.
   Any browser reaching `localhost:7860` gets a fresh session UUID automatically.

### Session ID in eval_log.jsonl

Every `TurnSignal` written by the controller includes the `session_id`. This means
a judge can filter `eval_log.jsonl` by session ID to see the exact audit trail of a
specific Gradio session. This traceability should be called out in the competition video.

---

## 6. OSCE Flow in the UI

The full end-to-end OSCE lifecycle from the student's perspective in `app.py`:

```
1. Student opens Tab 2 — OSCE Examination
   └─ Status shows: "No active session"
   └─ Start OSCE button is visible

2. Student clicks "Start OSCE"
   └─ app.py calls: controller.run("start osce", session_id)
   └─ Controller: classify → START_OSCE → OSCEExaminerSkill._init()
   └─ Examiner first message appears in chatbot
   └─ Status shows: "Session active — Step 1 / {MAX_OSCE_STEPS}"
   └─ Start button hidden; Send + Finish buttons visible

3. Student types a clinical response and clicks Send (repeats N times)
   └─ app.py calls: controller.run(response, session_id)
   └─ Controller: override → OSCE_TURN → OSCEExaminerSkill._turn()
   └─ Examiner follow-up appears in chatbot
   └─ Status updates step counter

4. Student clicks "Finish OSCE"  (or types "finish" / "I'm done")
   └─ app.py calls: controller.run("finish", session_id)
   └─ Controller: classify → FINISH_OSCE → OSCEExaminerSkill._finish()
     → EvaluationSkill scores the session
     → db_store.save_osce_result() writes to SQLite
     → TurnSignal logged to eval_log.jsonl
     → SecurityLayer post-flight filters response
   └─ Score block displayed in Score display component
   └─ Status shows: "Session complete"
   └─ Finish / Send hidden; Start button restored

5. Student switches to Tab 3 — Student Profile
   └─ Clicks Refresh
   └─ app.py calls: db_store.get_student_stats(session_id)
   └─ New OSCE result is visible in stats
   └─ Student clicks "Generate Plan"
   └─ controller.run("what should I study", session_id) → plan displayed
```

This is the exact sequence to demonstrate in the competition video.

---

## 7. Student Profile Tab — Data Rendering

The stats Markdown block rendered by Tab 3 follows this template:

```markdown
## Your Performance Summary

| Metric | Value |
|--------|-------|
| Sessions completed | N |
| OSCE cases attempted | N |
| Average score | X.XX / 10 |
| Best score | N |
| Worst score | N |

### Weak Areas
1. Topic name (N occurrences)
2. ...

### Recent OSCE Results
- YYYY-MM-DD  Diagnosis: N/10
- ...

### Topics Studied
Appendicitis, Cholecystitis, Bowel Obstruction, ...
```

If any section has no data (no weak areas, no recent results), that section is
omitted entirely rather than showing an empty table or list.

The study plan returned by `controller.run("what should I study", session_id)` is
displayed verbatim as Markdown below the stats block. Gradio renders Markdown
natively, so headers, bold text, and numbered lists in the plan will render correctly.

---

## 8. Error Handling

### Controller exceptions in `app.py`

All calls to `controller.run()` are wrapped in a try/except in `app.py`. On exception:

```python
try:
    response = controller.run(user_input, session_id)
except Exception as e:
    response = (
        "⚠️ Something went wrong on our end. Please try again.\n\n"
        "_If this keeps happening, try clicking Reset to start a new session._"
    )
```

The exception is logged to stderr (not displayed to the user). The chatbot continues
to function — the error message appears as the assistant response.

### Database initialization failure

`app.py` calls `db_store.init_database()` at the top of the module (outside any event
handler) during startup. If this raises, the exception propagates and Gradio will not
launch. The error message will be visible in the terminal. This is acceptable — a
missing database is a configuration error that the developer must fix before launching.

### Missing API keys

`app.py` validates `DEEPSEEK_API_KEY` and `JINA_API_KEY` from `config.py` at startup.
If either is absent or empty, print a clear error to stderr and raise `SystemExit(1)`.
This prevents the app from launching in a broken state that would silently fail on
every LLM call.

### ChromaDB not populated

`retrieval_tool.py` already handles this case — it returns an empty list when ChromaDB
is empty or the collection does not exist. `CaseRetrievalSkill` returns a "no results
found" message in that case. No additional error handling is needed in `app.py`.

### Gradio server port conflict

If port 7860 is in use, Gradio will fail to bind. This is a standard Gradio error
and the developer resolves it manually (`kill` the conflicting process, or change the
port via `server_port` arg). No special handling in `app.py`.

---

## 9. Local Setup Verification

Phase 5 must verify that the following sequence works cleanly from a fresh checkout
(keys in `.env`, Python environment activated):

```bash
# Step 1 — Install dependencies
pip install -r requirements.txt

# Step 2 — Prepare case data (only if db/ is empty)
python scripts/01_prepare_data.py
python scripts/02_embed_and_store.py

# Step 3 — Verify retrieval (optional sanity check)
python scripts/03_test_retrieval.py

# Step 4 — Run CLI (validates controller before Gradio)
python run.py

# Step 5 — Run Gradio app
python app.py
```

Steps 1–3 were verified in Phase 1A. The Phase 5 verification adds Steps 4–5.
The verification is done on the native Windows machine (not the sandbox) because
the sandbox cannot call the DeepSeek or Jina APIs.

**Verification checklist (native machine):**

| Step | Expected result |
|------|-----------------|
| `python run.py` starts | Welcome header prints; session ID shown |
| Type "show me a case about appendicitis" | Formatted case + Sources: section returned |
| Type "start osce" | Examiner's first question returned |
| Type a clinical response | Examiner's follow-up returned |
| Type "finish" | Score block returned |
| Type "what should I study" | Study plan or onboarding message returned |
| Type "exit" | Clean exit, no traceback |
| `python app.py` starts | Gradio URL printed; browser opens at localhost:7860 |
| Tab 1: send a message | Response appears in chatbot |
| Tab 2: click Start OSCE | Examiner question appears; step counter shows Step 1 |
| Tab 2: complete 3 turns + Finish | Score block appears |
| Tab 3: click Refresh | Stats rendered (or onboarding message if new student) |
| Tab 3: click Generate Plan | Study plan rendered |
| `eval_log.jsonl` | One line per turn; parseable as JSON |

---

## 10. Test Strategy

### What is tested

Phase 5 tests are integration-level. Unit testing of `run.py` and `app.py` is not
the goal — both files contain only UI wiring, not logic. The tests verify that
the entry-point files integrate cleanly with the controller and produce expected outputs.

### New test file

**`tests/test_interfaces.py`** — ~40 sandbox-safe tests.

| Test class | What it tests |
|---|---|
| `Test01CLIStartup` | `run.py` imports cleanly; key validation raises SystemExit on missing keys; REPL can be instantiated |
| `Test02AppImport` | `app.py` imports cleanly; `gr.Blocks` object is created without launching |
| `Test03SessionIDGeneration` | Session IDs are valid UUID4 strings; two independent sessions get distinct IDs |
| `Test04ControllerCallthrough` | `controller.run()` is called from simulated CLI input with mocked controller; response returned |
| `Test05OSCEFinishDetection` | `OSCE_FINISH_MARKERS` correctly identifies finish responses; does not false-positive on mid-session responses |
| `Test06StatsRendering` | Stats Markdown template renders correctly from sample `get_student_stats()` output; empty sections omitted |
| `Test07ErrorHandling` | Controller exception → error message string returned (not raised); app does not crash |

All tests use `CI_NO_LLM=1` and mock the controller. No Gradio server is launched
in tests — the `gr.Blocks` object is created but `.launch()` is not called.

### Regression test

After `test_interfaces.py` passes, run the full discovery suite:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache_surgmentor CI_NO_LLM=1 \
  python -m unittest discover -s tests -v
```

Expected: 133 existing tests still pass + new tests pass. Zero failures.

### Live integration test

On the native Windows machine (not sandbox) after `python app.py` is verified:

```bash
python -m unittest tests/test_interfaces.py
```

The live test class (`Test08LiveIntegration`, skipped with `CI_NO_LLM=1`) runs
`controller.run("show me a case", session_id)` against the live API and asserts the
response contains "Sources:". This is identical in structure to the live test in
`test_controller.py`.

---

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Gradio version incompatible with `chromadb==0.4.24` | Medium | High | Resolve during `pip install -r requirements.txt` step. If conflict: upgrade chromadb and rebuild vector store. Pin resolved versions. |
| Gradio state sharing across tabs breaks session continuity | Medium | Medium | Use a single `gr.State` at the `gr.Blocks` level for session_id. Verify tab-to-tab session persistence in integration test before recording video. |
| OSCE finish detection regex false-positives | Low | Low | Use multiple marker strings; require at least one to match. Test with real EvaluationSkill output format (known from Phase 3). |
| `app.py` launch hangs on ChromaDB initialization | Low | Medium | ChromaDB uses lazy connection in `retrieval_tool.py` — connection happens at first query, not import. App startup should be fast. |
| Windows-specific path issues in `run.py` or `app.py` | Low | Medium | All file paths use `pathlib.Path` or `os.path.join` — not hardcoded separators. Verify on native Windows machine. |
| Video demo uses wrong session — score history absent | Medium | Low | Before recording, complete at least one OSCE session and refresh the Profile tab to confirm history is visible. |
| `gr.Blocks` concurrency: two simultaneous OSCE sessions from same browser | Low | Low | Each Gradio tab has its own session UUID. Concurrent requests from two tabs would be two separate sessions. Acceptable for Phase 5. |

---

## 12. Exit Criteria

Phase 5 is complete when **all** of the following are true:

1. **`run.py` works end-to-end on the native Windows machine:**
   - Free chat response with Sources: section
   - OSCE start, at least 2 turns, finish with score
   - Clean exit via `exit` command

2. **`python app.py` launches without error on the native Windows machine:**
   - All three Gradio tabs load and respond
   - Tab 2 OSCE session completes: start → 3 turns → finish → score displayed
   - Tab 3 shows stats after the OSCE session is completed in Tab 2

3. **`tests/test_interfaces.py` passes (sandbox):**
   - All sandbox-safe tests pass with `CI_NO_LLM=1`
   - Zero failures

4. **Full test suite passes with no regressions (sandbox):**
   - 133 prior tests + new Phase 5 tests all pass
   - Zero failures

5. **`eval_log.jsonl` contains parseable TurnSignal entries for every turn:**
   - Verified by `cat eval_log.jsonl | python -c "import sys,json; [json.loads(l) for l in sys.stdin]"`

6. **The local setup sequence is verified:**
   - `pip install -r requirements.txt` → `python scripts/02_embed_and_store.py` →
     `python run.py` → `python app.py` runs cleanly in order
