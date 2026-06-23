# PHASE_1B_PLAN.md

**Project:** SurgMentor — Agentic Surgical Education System  
**Date:** 2026-06-20  
**Phase:** 1B — Tool and Storage Layer  
**Source of truth:** docs/IMPLEMENTATION_SEQUENCE_REVIEW.md  
**Status:** Awaiting approval before implementation begins

---

## 1. Phase 1B Objectives

Phase 1B implements the four foundational modules that every skill in Phase 3
will call. These modules form the data-access and memory layer that sits between
the raw infrastructure (ChromaDB, SQLite, Jina API) and the skill system.

The objective is to have every tool and storage function independently
importable, callable, and verified before a single skill file is touched.
Phase 3 skills are not allowed to begin until each module below has been
implemented and smoke-tested in isolation.

The four objectives, in implementation order:

1. **`surgmentor/rag/retrieval_tool.py`** — Wrap ChromaDB and the Jina
   embedding API into named, testable tool functions that skills call.
   Introduce per-process embedding cache and lazy ChromaDB connection.

2. **`surgmentor/memory/db_store.py`** — Implement the SQLite schema and
   all CRUD functions for student profiles, OSCE results, and session records.
   This is the persistence layer for cross-session student state.

3. **`surgmentor/memory/session.py`** — Implement in-memory session state
   management. Every controller cycle reads state before routing and writes
   state after the skill returns. This module makes that possible.

4. **`surgmentor/evaluation/logger.py`** — Implement the eval_log.jsonl
   writer. The EvaluationSkill (Phase 3) and the controller (Phase 4) both
   write to this log. It must exist before either is built.

---

## 2. Files to be Modified

Phase 1B touches exactly four files. No other files change.

| File | Current state | Action |
|---|---|---|
| `surgmentor/rag/retrieval_tool.py` | Placeholder (TODO comments only) | Full implementation |
| `surgmentor/memory/db_store.py` | Placeholder (TODO comments only) | Full implementation |
| `surgmentor/memory/session.py` | Placeholder (TODO comments only) | Full implementation |
| `surgmentor/evaluation/logger.py` | Placeholder (TODO comments only) | Full implementation |

No other files are modified in Phase 1B. The scripts written in Phase 1A
are complete. The security layer, skills, and agent controller are Phase 2–4
targets and must not be started until Phase 1B is approved complete.

---

## 3. Why These Files Before Everything Else

### Why retrieval_tool.py before skills?

`CaseRetrievalSkill` calls `search_vector_store()`.
`OSCEExaminerSkill` calls `get_case_by_id()`.
`StudyPlannerSkill` calls (indirectly) `load_all_cases()` for case recommendations.

If these functions do not exist when skills are written, skills must mock
them. Mocks create two problems: they test the mock instead of the real
integration, and they get replaced later at exactly the wrong time
(during skill composition, when integration bugs are most expensive to fix).

Building retrieval_tool.py first means every skill can be tested against
the real ChromaDB from its first line of code. Phase 1A proved the database
is populated and working — Phase 1B closes the gap between the database
and the application layer.

### Why db_store.py before skills?

`EvaluationSkill` calls `save_osce_result()`.
`StudyPlannerSkill` calls `get_student_stats()`.
Both write diagnostic data to `log_topics()`.

The `get_student_stats()` function from the reference repo (`database.py`)
was identified in MIGRATION_PLAN.md as the primary reason StudyPlannerSkill
was promoted to MVP. Its output (weak_areas, recent_osce, top_topics) is
exactly what the planner LLM call consumes. This function must be present
and returning real data before StudyPlannerSkill can be written or verified.

Additionally, `init_database()` must be called before any skill stores data.
If it is not called at startup, the first `save_osce_result()` raises a
"no such table" error at the worst possible time: during a demo run.

### Why session.py before the controller?

The agent controller's first action in every cycle is:
`state = session_memory.read(session_id)`.
Its last action is:
`session_memory.write(session_id, updated_state)`.

The controller cannot be written — even as a skeleton — without knowing
the exact fields of `SessionState`. If session.py is not implemented first,
the controller either guesses the schema or imports a stub that may not
match the final design. Either path creates rework.

`SessionState` is also the type that all context bundle construction
(`agent/context.py`, Phase 4) reads from. The shape of the state object
propagates through the entire controller and skill system. Locking it in
Phase 1B prevents cascading schema changes later.

### Why logger.py before skills?

`EvaluationSkill.run()` ends by calling `write_session_evaluation()`.
The agent controller ends every cycle by calling `write_turn_signal()`.

If logger.py is not present when EvaluationSkill is written, the skill
either imports a stub or skips the evaluation call and it gets bolted on
later. The IMPLEMENTATION_SEQUENCE_REVIEW explicitly identified this as
the antipattern to avoid for the security and evaluation layers: build them
before the components that depend on them, so the dependency is natural
rather than retrofitted.

Logger.py has zero dependencies on anything in Phase 1B — it writes to a
file. It can be written in an hour. There is no reason to defer it.

---

## 4. Scope of Each Implementation

### 4.1 `surgmentor/rag/retrieval_tool.py`

**Public interface (what skills will call):**

```
CaseResult                        # dataclass
  case_id: str
  text: str
  metadata: dict
  similarity: float

search_vector_store(
    query: str,
    top_k: int = TOP_K_RESULTS,
    bias_topics: list[str] = []
) -> list[CaseResult]

get_case_by_id(case_id: str) -> CaseResult | None

load_all_cases() -> list[dict]       # from prepared_cases.json, cached

format_case_context(cases: list[CaseResult]) -> str
```

**Internal implementation details:**

- `_embed_query(text: str) -> list[float]` — Jina API, `retrieval.query`
  task, `normalized=True`. Per-process dict cache keyed by query text.
  Same pattern as `_embed_cache` in `surgery-rag/rag_engine.py`.

- ChromaDB connection is lazy: `_get_collection()` returns a cached
  client/collection pair initialized on first call, not at import time.
  This is a deliberate improvement over the reference (`rag_engine.py`
  connects at import — a module-level side effect that breaks unit tests
  and makes the sandbox build environment require a live ChromaDB).

- `search_vector_store` accepts `bias_topics: list[str]` — a list of
  weak areas from the student profile. If non-empty, the query string is
  augmented with the bias topics before embedding (e.g. append
  "focus on: haemostasis, wound closure"). This implements the context
  engineering principle from TARGET_ARCHITECTURE.md Section 4 —
  `CaseRetrievalSkill` uses the student's weak areas to bias retrieval
  toward their knowledge gaps.

- `format_case_context` produces the numbered context block used in
  LLM system prompts: `[Case 1] ID: X | Diagnosis: Y | Similarity: Z\n{text}\n`.

**Reference:** `surgery-rag/rag_engine.py` lines 29–97
(`_embed_cache`, `_embed_query()`, `retrieve_cases()`). Logic rewritten
fresh; lazy connection and `bias_topics` parameter are new.

---

### 4.2 `surgmentor/memory/db_store.py`

**Schema (4 tables):**

```sql
users
  student_id    TEXT PRIMARY KEY      -- anonymous ID (UUID or Gradio session)
  display_name  TEXT
  joined_date   TEXT                  -- ISO 8601
  last_active   TEXT

osce_results
  id            INTEGER PRIMARY KEY AUTOINCREMENT
  student_id    TEXT
  case_id       TEXT
  diagnosis     TEXT
  score         INTEGER               -- 0-10
  feedback      TEXT
  weak_areas    TEXT                  -- comma-separated
  completed_at  TEXT

topics_studied
  id            INTEGER PRIMARY KEY AUTOINCREMENT
  student_id    TEXT
  topic         TEXT
  mode          TEXT                  -- 'chat' | 'osce'
  studied_at    TEXT

agent_sessions
  id            INTEGER PRIMARY KEY AUTOINCREMENT
  student_id    TEXT
  mode          TEXT                  -- 'chat' | 'osce'
  started_at    TEXT
  ended_at      TEXT
  message_count INTEGER DEFAULT 0
```

**Key design decisions vs. reference (`database.py`):**

- `student_id` is `TEXT`, not `INTEGER`. The competition demo is anonymous
  (no Telegram). Student IDs are UUIDs generated per Gradio session, or
  set via `run.py` CLI argument. This eliminates the Telegram dependency.

- No `web_login_tokens` or `active_osce_sessions` tables. These are
  Telegram/web-layer features not present in the competition architecture.

- `agent_sessions` replaces both `sessions` and `web_sessions` from the
  reference. It is platform-agnostic.

**Public functions:**

```
init_database() -> None
register_student(student_id, display_name) -> None
update_last_active(student_id) -> None
start_agent_session(student_id, mode) -> int   # returns session row id
end_agent_session(session_id, message_count) -> None
save_osce_result(student_id, case_id, diagnosis, score, feedback, weak_areas) -> None
log_topics(student_id, cases: list[CaseResult], mode) -> None
get_student_stats(student_id) -> dict
```

`get_student_stats()` returns the same structure as the reference (user,
sessions, osce averages, recent_osce, top_topics, weak_areas). This is
the data source for `StudyPlannerSkill` — the function must return
`weak_areas` as a list of `(topic, count)` tuples.

**Reference:** `surgery-rag/database.py` — table schemas and query
logic. `get_student_stats()` is a near-direct port; schema changes only
replace `telegram_id` with `student_id` (TEXT) and remove
Telegram/web-specific tables.

---

### 4.3 `surgmentor/memory/session.py`

**SessionState (dataclass):**

```python
@dataclass
class SessionState:
    session_id:           str
    student_id:           str
    mode:                 str        # "chat" | "osce"
    osce_active:          bool
    osce_step:            int        # current step in OSCE sequence (0 = not started)
    current_case:         dict | None
    conversation_history: list[dict] # [{role: str, content: str}, ...]
    weak_areas:           list[str]
    score_history:        list[dict]
    last_active:          str        # ISO 8601
```

**InMemorySessionStore:**

```
read(session_id: str) -> SessionState    # creates default state if absent
write(session_id: str, state: SessionState) -> None
clear(session_id: str) -> None
list_active() -> list[str]              # session IDs with active state
```

**History windowing:**

The `read()` method does not trim history — it returns the full state.
Trimming is done in `agent/context.py` (Phase 4) when building the
context bundle for each skill. This separation of concerns is deliberate:
the session store owns the full record; the context builder decides what
each skill sees. This is the Day 1 context engineering principle from
TARGET_ARCHITECTURE.md Section 4.

`HISTORY_WINDOW` from `config.py` is imported here but only used by the
context builder in Phase 4.

**No database backend for session.py.** In-memory only. Cross-session
persistence is handled by `db_store.py` (OSCE results, topics, stats).
The SessionState is ephemeral by design — losing it on restart is
acceptable for the competition demo.

---

### 4.4 `surgmentor/evaluation/logger.py`

**Dataclasses:**

```python
@dataclass
class TurnSignal:
    session_id:          str
    timestamp:           str        # ISO 8601
    intent_classified:   str        # IntentCategory name
    skill_selected:      str        # Skill class name
    output_safety_pass:  bool
    response_length:     int        # character count
    latency_ms:          int

@dataclass
class SessionEvaluation:
    session_id:          str
    student_id:          str
    case_id:             str
    osce_score:          int        # 0-10
    rubric_breakdown:    dict
    weak_areas:          list[str]
    safety_events:       int        # count of output filter interventions
    completion_status:   str        # "COMPLETED" | "ABANDONED" | "INCOMPLETE"
    feedback_text:       str
    timestamp:           str        # ISO 8601
```

**Public functions:**

```
write_turn_signal(signal: TurnSignal) -> None
write_session_evaluation(evaluation: SessionEvaluation) -> None
```

Both functions append one JSON line to `eval_log.jsonl`
(`EVAL_LOG_PATH` from `config.py`). The file is created if absent.
Append-only: no rotation, no deletion in MVP.

`dataclasses.asdict()` is used for serialization — no custom JSON encoder.
`datetime.now().isoformat()` is used for timestamps when the caller does
not supply one.

This is the entire module. It is intentionally small — its job is to write
records, nothing else. The scoring logic lives in `EvaluationSkill` (Phase 3).

---

## 5. Dependency Map for Phase 1B

```
config.py (already done)
clients.py (already done)
    │
    ├── surgmentor/rag/retrieval_tool.py
    │     imports: config (JINA_API_KEY, JINA_EMBEDDING_MODEL, CHROMA_DB_PATH,
    │                      COLLECTION_NAME, TOP_K_RESULTS)
    │     imports: requests, chromadb
    │     no imports from surgmentor/
    │
    ├── surgmentor/memory/db_store.py
    │     imports: config (AGENT_SESSION_DB_PATH)
    │     imports: sqlite3, datetime
    │     no imports from surgmentor/
    │
    ├── surgmentor/memory/session.py
    │     imports: config (HISTORY_WINDOW)
    │     imports: dataclasses, datetime
    │     no imports from surgmentor/
    │
    └── surgmentor/evaluation/logger.py
          imports: config (EVAL_LOG_PATH)
          imports: dataclasses, json, datetime
          no imports from surgmentor/
```

All four modules are independent of each other. They share no imports
from within the `surgmentor/` package. This means they can be implemented
and verified in any order, and a bug in one does not block another.

The implementation order (retrieval_tool → db_store → session → logger)
is chosen by complexity descending: the hardest module first, while full
focus is available.

---

## 6. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Jina API blocked in sandbox (known from Phase 1A) | Certain | Medium | `retrieval_tool.py` can be written and structurally tested without calling the API. Embed-cache path and ChromaDB query path can be tested with a pre-stored vector (same technique used in Phase 1A verification). API call itself verified when Reza runs on native machine. |
| SQLite writes blocked on mounted volume | Certain | Low | `db_store.py` will be written and syntax-checked in the sandbox. A local `/tmp/` SQLite path (`AGENT_SESSION_DB_PATH=/tmp/test.db`) will be used for smoke-testing. The resulting schema is identical regardless of path. |
| `get_student_stats()` returns unexpected shape | Low | Medium | Write a standalone test at the end of `db_store.py`'s `if __name__ == "__main__":` block: insert a fake student, fake OSCE result, run `get_student_stats()`, assert all required keys present. |
| `SessionState` fields need revision after Phase 3 | Medium | Low | The dataclass uses mutable defaults correctly (`field(default_factory=list)`). Adding fields later is non-breaking. The controller (Phase 4) only reads fields it needs — extra fields are ignored. |
| `eval_log.jsonl` path not writable in sandbox | Low | Low | Config path is `"./eval_log.jsonl"`. Sandbox can write to `/tmp/` alternative. The logger has no dependencies; verifying it means writing one JSON line and reading it back. |

---

## 7. Verification Plan (exit criteria for Phase 1B)

Phase 1B is complete when all four of the following hold:

**1. retrieval_tool.py** — `python -c "from surgmentor.rag.retrieval_tool import search_vector_store, get_case_by_id, load_all_cases, format_case_context, CaseResult; print('import OK')"` executes without error. Standalone smoke-test (using stored vector from ChromaDB, no Jina API call) returns at least 1 `CaseResult` with correct fields.

**2. db_store.py** — `init_database()` runs without error, creating `./data/surgmentor_agent.db`. `register_student("test-001", "Test Student")` → `get_student_stats("test-001")` returns a dict with keys `user`, `sessions`, `osce`, `recent_osce`, `top_topics`, `weak_areas`. Verified by the module's own `__main__` block.

**3. session.py** — `InMemorySessionStore` round-trip: `write("s1", state)` → `read("s1")` returns identical `SessionState`. Default state created when `read("new-id")` is called for a non-existent session. Verified by the module's own `__main__` block.

**4. logger.py** — `write_turn_signal(TurnSignal(...))` appends a valid JSON line to the log file. `write_session_evaluation(SessionEvaluation(...))` appends a second valid JSON line. Both lines are parseable as JSON. Verified by the module's own `__main__` block.

---

## 8. Revision Assessment vs. IMPLEMENTATION_SEQUENCE_REVIEW.md

**No revision required.** The Phase 1B scope defined in
IMPLEMENTATION_SEQUENCE_REVIEW.md is correct and remains unchanged.

One observation from Phase 1A that affects Phase 1B execution (not scope):

The sandbox blocks Jina API calls and SQLite writes to the mounted volume.
Both constraints are known and the mitigation strategy (local `/tmp/`
paths for SQLite smoke-tests; stored-vector technique for retrieval
verification) is established from Phase 1A. These are execution
constraints, not design constraints. The implementations will be
identical to what would run on Reza's native machine.

The `CHROMA_DB_PATH` change in `config.py` (made env-configurable during
Phase 1A) benefits Phase 1B: `retrieval_tool.py`'s lazy connection reads
`CHROMA_DB_PATH` from config, which now reads from the environment. Setting
`CHROMA_DB_PATH=/tmp/ref_db` in the sandbox allows retrieval_tool.py
to be smoke-tested against the full reference ChromaDB without any code changes.

---

## 9. What Phase 1B Does NOT Include

The following are explicitly out of scope for Phase 1B and must not be
started until Phase 2 approval is received:

- `surgmentor/security/layer.py` — Phase 2
- `surgmentor/skills/base.py` and all skill files — Phase 3
- `surgmentor/agent/` files — Phase 4
- `app.py` and `run.py` — Phase 5
- Any modification to the data pipeline scripts — Phase 1A is frozen

