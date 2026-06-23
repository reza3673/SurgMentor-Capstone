# CUSTOM_FRONTEND_PLAN.md — SurgMentor FastAPI + Custom HTML Frontend

**Project:** SurgMentor — Agentic Surgical Education System  
**Phase:** 5B (entry interface replacement)  
**Date:** 2026-06-22  
**Status:** Awaiting approval  
**Prerequisite:** Phase 5 complete — `controller.run(input_text, session_id) → str` is stable and tested

---

## 1. Objective

Replace the Gradio presentation layer with a FastAPI backend and a fully custom
HTML/CSS/JavaScript frontend. The agent backend (controller, skills, security,
memory, RAG, evaluation) is **untouched**. `run.py` CLI is **untouched**.

The new stack presents the same three views — Case Retrieval, OSCE Examination,
Student Profile — in a premium health-tech visual style, with no Gradio toolbar,
copy controls, share buttons, or default Gradio component styling.

---

## 2. What Changes vs. What Stays

### Stays exactly as-is (zero edits)
| Component | File(s) |
|---|---|
| AgentController + PERCEIVE/PLAN/ACT/OBSERVE loop | `surgmentor/agent/controller.py` |
| All skills (retrieval, OSCE, evaluation, planner) | `surgmentor/skills/` |
| Security layer (sanitize + filter) | `surgmentor/security/layer.py` |
| RAG pipeline | `surgmentor/rag/` |
| Session memory | `surgmentor/memory/session.py` |
| SQLite persistence | `surgmentor/memory/db_store.py` |
| Evaluation logger | `surgmentor/evaluation/logger.py` |
| Intent classifier + context builder | `surgmentor/agent/intent.py`, `context.py` |
| UI helpers (session ID, stats renderer, finish detection) | `surgmentor/ui/helpers.py` |
| CLI entry point | `run.py` |
| Config | `config.py` |
| All existing tests | `tests/` |

### Modified (minimal)
| File | Change |
|---|---|
| `requirements.txt` | Add `fastapi>=0.111`, `uvicorn[standard]>=0.29` |
| `config.py` | Add `FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))` constant |
| `.env.example` | Add `FASTAPI_PORT=8000` line |

### New files created
| File | Purpose |
|---|---|
| `server.py` | FastAPI app + all API routes. Thin shell over `controller.run()`. |
| `web/index.html` | Single-page app (3-view SPA). All CSS and JS inline. |
| `tests/test_api.py` | API contract tests (sandbox-safe, no LLM). |

`app.py` remains as a fallback (`python app.py` still works); it is not modified.

---

## 3. FastAPI Server Design — `server.py`

### Startup sequence (mirrors `run.py`)

```python
from surgmentor.ui.helpers import validate_api_keys
from surgmentor.memory.db_store import init_database
from surgmentor.agent.controller import controller   # module-level singleton
from surgmentor.memory.session import default_store
import surgmentor.memory.db_store as db_store
from surgmentor.ui.helpers import detect_osce_finish, render_stats_markdown, create_session_id
```

On `lifespan` startup:
1. `validate_api_keys()` — exits on missing keys
2. `init_database()` — idempotent schema creation
3. Static file mount: `app.mount("/", StaticFiles(directory="web", html=True))`

### Static file serving

FastAPI serves `web/index.html` at `/`. All frontend assets are embedded in that
single file (no separate CSS or JS files needed for a competition demo).

### Endpoints

All endpoints are under the `/api` prefix to avoid collisions with the static mount.

#### `POST /api/chat`

Send one message in free-chat (Case Retrieval) mode.

**Request body:**
```json
{
  "session_id": "uuid4-string",
  "message":    "show me a case about appendicitis"
}
```

**Response:**
```json
{
  "session_id": "uuid4-string",
  "response":   "Here is case C-42 ...\n\nSources: ..."
}
```

**Server logic:** `response = controller.run(message, session_id)`  
If `controller.run` raises, return `{"session_id": ..., "response": "⚠️ Something went wrong. Please try again."}` with HTTP 200.  
Never propagate stack traces to the client.

---

#### `POST /api/osce/start`

Start a new OSCE session.

**Request body:**
```json
{ "session_id": "uuid4-string" }
```

**Response:**
```json
{
  "session_id":  "uuid4-string",
  "response":    "Welcome. Here is your case ...",
  "osce_active": true,
  "osce_step":   1
}
```

**Server logic:**
```python
response = controller.run("start osce", session_id)
state    = controller.session_store.read(session_id)
```
Returns `state.osce_active` and `state.osce_step` directly from session state.

---

#### `POST /api/osce/turn`

Send one OSCE response during an active session.

**Request body:**
```json
{
  "session_id": "uuid4-string",
  "message":    "I would take a history starting with onset and severity"
}
```

**Response:**
```json
{
  "session_id":    "uuid4-string",
  "response":      "Good. Now tell me about ...",
  "osce_active":   true,
  "osce_step":     2,
  "is_finish":     false
}
```

`is_finish` is `True` when `detect_osce_finish(response)` is True (the EvaluationSkill
scored the session and the response contains the score block). The frontend uses this
to switch from the chat view to the score panel without any additional request.

**Server logic:**
```python
response   = controller.run(message, session_id)
state      = controller.session_store.read(session_id)
is_finish  = detect_osce_finish(response)
```

---

#### `POST /api/osce/finish`

Explicitly finish the OSCE session.

**Request body:**
```json
{ "session_id": "uuid4-string" }
```

**Response:**
```json
{
  "session_id":  "uuid4-string",
  "response":    "Score: 8/10 ...",
  "osce_active": false,
  "osce_step":   0,
  "is_finish":   true
}
```

**Server logic:** `response = controller.run("finish", session_id)` — same as a turn,
but the input is always `"finish"`.

---

#### `POST /api/osce/reset`

Reset OSCE state (new session UUID, wipe controller memory for old session).

**Request body:**
```json
{ "session_id": "uuid4-string" }
```

**Response:**
```json
{
  "new_session_id": "new-uuid4-string"
}
```

**Server logic:**
```python
default_store.clear(session_id)
new_id = create_session_id()
return {"new_session_id": new_id}
```

The frontend updates its stored session_id with `new_session_id` and resets display state.

---

#### `GET /api/profile`

Fetch student stats for the Profile view.

**Query params:** `?session_id=uuid4-string`

**Response:**
```json
{
  "session_id":   "uuid4-string",
  "stats_md":     "## Your Performance Summary\n\n| Metric | Value |\n...",
  "has_data":     true
}
```

`stats_md` is the pre-rendered Markdown string from `render_stats_markdown(stats)`.
The frontend renders it with a lightweight Markdown parser (marked.js from CDN).

---

#### `POST /api/profile/plan`

Generate a personalised study plan.

**Request body:**
```json
{ "session_id": "uuid4-string" }
```

**Response:**
```json
{
  "session_id": "uuid4-string",
  "response":   "## Personalised Study Plan\n\n1. Focus on ..."
}
```

**Server logic:** `response = controller.run("what should I study", session_id)`

---

### CORS

For the competition demo (localhost), allow all origins:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```

### Error handling contract

All endpoints follow the same pattern:

```python
try:
    response = controller.run(...)
except Exception:
    response = "⚠️ Something went wrong. Please try again."
```

HTTP status is always 200 for user-facing errors (the frontend displays the message
string). 422 (validation error) is raised automatically by FastAPI for malformed request
bodies. 500 is only returned for unexpected server crashes before the try/except.

---

## 4. Frontend Design — `web/index.html`

### Architecture: Single-page app, zero build tooling

All HTML, CSS, and JavaScript live in one file. No npm, no webpack, no TypeScript.
The file is served statically by FastAPI. The frontend stores `session_id` in
`sessionStorage` so it persists across view switches but resets on tab close.

One external CDN dependency: **marked.js** (`https://cdn.jsdelivr.net/npm/marked/marked.min.js`)
for rendering Markdown responses (stats panel, study plan). Loaded from CDN at runtime.
No other external dependencies.

### Visual design system

Inspired by primeiroolhar.app.br: light, premium health-tech feel.

```css
/* Palette */
--bg-page:      #f0f5fa;     /* soft blue-grey page background */
--bg-card:      #ffffff;     /* white card surfaces */
--blue-dark:    #075985;     /* header gradient end / dark accent */
--blue-mid:     #0369a1;     /* primary interactive / header gradient start */
--blue-light:   #0284c7;     /* hover states */
--border:       #e2e8f0;     /* card borders */
--text-primary: #1e293b;     /* body text */
--text-muted:   #64748b;     /* labels, subtitles */
--text-xs:      #94a3b8;     /* metadata, timestamps */
--success:      #10b981;     /* score highlight */
--error:        #ef4444;     /* error states */
--shadow-sm:    0 1px 4px rgba(0,0,0,0.06);
--shadow-card:  0 2px 12px rgba(3,105,161,0.08);

/* Typography */
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

/* Layout */
max-width: 940px; margin: 0 auto; padding: 0 20px;
```

### Page structure

```
┌────────────────────────────────────────────────┐
│  HEADER  (gradient banner, logo, subtitle)     │
├─────┬──────────────────────────────────────────┤
│ NAV │   TAB CONTENT AREA                       │
│     │   (Case Retrieval / OSCE / Profile)      │
│     │                                          │
└─────┴──────────────────────────────────────────┘
      FOOTER (version, session ID)
```

**Header:** `linear-gradient(135deg, #0369a1 → #075985)`, white text, border-radius 14px,
box-shadow with blue tint. Title "SurgMentor", subtitle "Agentic OSCE Trainer".

**Navigation:** Three pill-style tab buttons. Active tab highlighted with `--blue-mid`
background and white text. Inactive tabs: white background, `--border` border.

**Cards:** `background: white; border-radius: 12px; box-shadow: var(--shadow-card); padding: 24px;`

**Buttons — primary:** `background: #0369a1; color: white; border-radius: 8px; font-weight: 600;
padding: 10px 20px; box-shadow: 0 1px 3px rgba(3,105,161,0.25);` Hover: `#0284c7`.

**Buttons — secondary:** `background: white; border: 1px solid #cbd5e1; color: #475569;
border-radius: 8px;` Hover: blue border + text.

**Text inputs:** `border-radius: 10px; border: 1px solid #cbd5e1; padding: 12px 16px;`
Focus: `border-color: #0369a1; box-shadow: 0 0 0 3px rgba(3,105,161,0.12);`

**Chat bubbles:**
- User: right-aligned, `background: #0369a1; color: white; border-radius: 18px 18px 4px 18px;`
- Assistant: left-aligned, `background: white; border: 1px solid #e2e8f0; border-radius: 18px 18px 18px 4px; box-shadow: var(--shadow-sm);`

**Loading state:** Animated three-dot spinner inside an assistant bubble while awaiting
API response. CSS keyframe animation — no external library needed.

**OSCE status bar:** White card with 4px left border in `--blue-mid`. Shows step counter
or "No active session".

**Score panel:** White card with 3px top border in `--blue-mid`, blue-tinted shadow.
Shown only after session ends.

### View 1 — Case Retrieval

```
┌─ Card: Free Chat ──────────────────────────────┐
│  [intro text]                                  │
│  ┌─ chat-messages div ─────────────────────┐  │
│  │  [user bubble]  [assistant bubble] ...  │  │
│  └─────────────────────────────────────────┘  │
│  ┌─ input row ─────────────────────────────┐  │
│  │  [textarea ─────────────────] [Send]    │  │
│  └─────────────────────────────────────────┘  │
│  [Clear Session] button (small, secondary)     │
└────────────────────────────────────────────────┘
```

State held in JS: `chatHistory = []`, `sessionId` (from `sessionStorage`).

On Send:
1. Append user bubble immediately.
2. Append loading bubble.
3. `POST /api/chat` with `{session_id, message}`.
4. Replace loading bubble with assistant response.
5. Auto-scroll chat to bottom.

Enter key (without Shift) submits. Shift+Enter inserts newline.

On Clear Session:
1. `POST /api/osce/reset` to clear server-side session (reuses same reset endpoint).
2. Update `sessionStorage` with new session ID.
3. Clear `chatHistory` array.
4. Clear chat DOM.

---

### View 2 — OSCE Examination

```
┌─ OSCE status bar ──────────────────────────────┐
│  "No active session" / "Step N / MAX_STEPS"    │
└────────────────────────────────────────────────┘
┌─ Card: OSCE Chat ──────────────────────────────┐
│  [chat-messages div — examiner + student msgs] │
└────────────────────────────────────────────────┘
┌─ Input row (hidden when not active) ───────────┐
│  [textarea ─────────────────────] [Send]       │
└────────────────────────────────────────────────┘
┌─ Control buttons ──────────────────────────────┐
│  [▶ Start Session]  (primary, shown when idle) │
│  [⏹ End & Score] (secondary, shown when active)│
│  [↺ New Session]  (secondary, always visible)  │
└────────────────────────────────────────────────┘
┌─ Score panel (hidden until session ends) ──────┐
│  [rendered Markdown score block]               │
└────────────────────────────────────────────────┘
```

State held in JS: `osceActive = false`, `osceStep = 0`, `osceChatHistory = []`.

**Start:** `POST /api/osce/start` → set `osceActive=true`, `osceStep=response.osce_step`,
append examiner first message, show input + End button, hide Start button.

**Turn:** `POST /api/osce/turn` → append exchange, update step counter.
If `response.is_finish` is true: transition to Finished state (same as End & Score flow).

**End & Score:** `POST /api/osce/finish` → `is_finish` always true →
show score panel with rendered Markdown, hide input + End button, show Start button,
update status bar to "Session complete".

**New Session / Reset:** `POST /api/osce/reset` → update session ID in `sessionStorage`,
clear display, reset all JS state to idle.

---

### View 3 — Student Profile

```
┌─ Card: Performance Statistics ─────────────────┐
│  [rendered Markdown stats table]               │
│  [Refresh Stats] button                        │
└────────────────────────────────────────────────┘
┌─ Card: Personalised Study Plan ────────────────┐
│  [rendered Markdown plan]                      │
│  [Generate Study Plan] button                  │
└────────────────────────────────────────────────┘
```

On load: auto-fetch `GET /api/profile?session_id=...` and render stats.

**Refresh:** re-fetch and re-render stats.

**Generate Plan:** `POST /api/profile/plan` → render plan Markdown. Show loading state
on button ("Generating…") while waiting.

Both Markdown renders go through `marked.parse(text)` into a `div` with
`class="prose"`. The prose class applies consistent typography (headings, tables,
lists) matching the design system.

---

### JavaScript state model

```javascript
// Persisted in sessionStorage (survives tab switch, lost on tab close)
let sessionId = sessionStorage.getItem('sm_session_id') || generateUUID();
sessionStorage.setItem('sm_session_id', sessionId);

// In-memory (reset on page reload)
let chatHistory   = [];
let osceActive    = false;
let osceStep      = 0;
let osceChatHistory = [];
```

All `fetch` calls use `async/await`. Errors caught with try/catch → friendly message
in the UI. No unhandled promise rejections.

```javascript
async function apiPost(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
```

### UUID generation (no crypto dependency)

```javascript
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}
```

### Responsive layout

Target: desktop-first for Kaggle video recording (1280px+ viewport). The 940px
max-width centered layout works well on any laptop screen. No mobile-specific
breakpoints needed for the demo, but the flex/grid layout degrades gracefully
at smaller widths without horizontal overflow.

---

## 5. Session ID Strategy

Identical to Phase 5, adapted for the browser:

1. On first page load, generate a UUID4 and store in `sessionStorage`.
2. All three views share the same `sessionId`. Profile stats and OSCE history
   are automatically in sync because the controller uses `session_id` as the
   student ID for SQLite lookups.
3. `POST /api/osce/reset` returns a `new_session_id`; the frontend writes this
   to `sessionStorage` to replace the old ID.
4. Refreshing the page (F5) in the same tab preserves the session (sessionStorage).
   Opening a new tab creates a new session.

---

## 6. Files to Create / Modify

### New files

```
server.py                   FastAPI app (~180 lines)
web/
  index.html                SPA — HTML + CSS + JS (~600 lines)
tests/
  test_api.py               API contract tests (~80 lines)
```

### Modified files

```
requirements.txt            + fastapi>=0.111, uvicorn[standard]>=0.29
config.py                   + FASTAPI_PORT constant
.env.example                + FASTAPI_PORT=8000
```

### Unchanged files (reference only)

`app.py`, `run.py`, all `surgmentor/` source, all existing tests.

---

## 7. `server.py` Structure

```python
# server.py
"""
SurgMentor FastAPI server — custom frontend entry point.

Wraps AgentController with a thin HTTP layer.
All business logic remains in the controller and skill layers.

Run:
  uvicorn server:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import surgmentor.memory.db_store as db_store
from surgmentor.ui.helpers import (
    validate_api_keys, detect_osce_finish, render_stats_markdown, create_session_id
)
from surgmentor.agent.controller import controller
from surgmentor.memory.session   import default_store
import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_api_keys()
    db_store.init_database()
    yield


app = FastAPI(title="SurgMentor API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message:    str

class ChatResponse(BaseModel):
    session_id: str
    response:   str

class SessionRequest(BaseModel):
    session_id: str

class OsceStateResponse(BaseModel):
    session_id:  str
    response:    str
    osce_active: bool
    osce_step:   int
    is_finish:   bool = False

class ResetResponse(BaseModel):
    new_session_id: str

class ProfileResponse(BaseModel):
    session_id: str
    stats_md:   str
    has_data:   bool

class PlanResponse(BaseModel):
    session_id: str
    response:   str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest): ...

@app.post("/api/osce/start", response_model=OsceStateResponse)
async def osce_start(req: SessionRequest): ...

@app.post("/api/osce/turn", response_model=OsceStateResponse)
async def osce_turn(req: ChatRequest): ...

@app.post("/api/osce/finish", response_model=OsceStateResponse)
async def osce_finish(req: SessionRequest): ...

@app.post("/api/osce/reset", response_model=ResetResponse)
async def osce_reset(req: SessionRequest): ...

@app.get("/api/profile", response_model=ProfileResponse)
async def profile(session_id: str): ...

@app.post("/api/profile/plan", response_model=PlanResponse)
async def profile_plan(req: SessionRequest): ...


# ── Static files (must be last — catches all remaining routes) ────────────────
app.mount("/", StaticFiles(directory="web", html=True), name="static")
```

---

## 8. Test Plan — `tests/test_api.py`

All tests sandbox-safe (`CI_NO_LLM=1`). Use `fastapi.testclient.TestClient` with
a mocked controller — no live API calls, no LLM.

### Test classes

| Class | Tests |
|---|---|
| `Test01ServerImport` | `server.py` imports cleanly; `app` object is a FastAPI instance; all 7 endpoints registered |
| `Test02ChatEndpoint` | 200 on valid request; `response` key present; controller called with correct args; exception → friendly string |
| `Test03OsceStart` | 200 on valid session_id; `osce_active=True`, `osce_step≥1` in response |
| `Test04OsceTurn` | Response mirrors controller output; `is_finish=False` for mid-session; `is_finish=True` when detect_osce_finish fires |
| `Test05OsceFinish` | `is_finish=True` always; `osce_active=False` in response |
| `Test06OsceReset` | Returns `new_session_id`; new ID is valid UUID4; different from input |
| `Test07Profile` | `stats_md` is non-empty string; `has_data` false for unknown student |
| `Test08ProfilePlan` | `response` is string; controller called with "what should I study" |
| `Test09ValidationErrors` | Missing required fields → 422; wrong types → 422 |

```python
# Pattern for all API tests:
from fastapi.testclient import TestClient
from unittest.mock import patch

def _make_client():
    # Patch controller.run and db startup before importing server
    with patch("surgmentor.agent.controller.controller") as mock_ctrl, \
         patch("surgmentor.memory.db_store.init_database"), \
         patch("surgmentor.ui.helpers.validate_api_keys"):
        from server import app
        return TestClient(app), mock_ctrl
```

### Regression: existing tests still pass

After adding `server.py` and `test_api.py`, run the full suite:
```bash
PYTHONPYCACHEPREFIX=/tmp/pycache_surgmentor CI_NO_LLM=1 \
  python -m unittest discover -s tests -v
```
Expected: all 191 prior tests + new API tests pass, 0 failures.

---

## 9. Migration Steps (implementation sequence)

1. **Update `requirements.txt`** — add `fastapi` and `uvicorn`.
2. **Update `config.py`** — add `FASTAPI_PORT` constant.
3. **Update `.env.example`** — add `FASTAPI_PORT=8000`.
4. **Implement `server.py`** — all 7 endpoints, error handling, static mount.
5. **Implement `web/index.html`** — full SPA: HTML structure, CSS design system,
   JS state model, all three views, API calls, loading states.
6. **Implement `tests/test_api.py`** — all 9 test classes.
7. **Run full test suite** — confirm 0 regressions + new tests pass.
8. **Smoke-test locally** — `uvicorn server:app --reload`, open `http://localhost:8000`,
   walk through all three views manually.

---

## 10. How to Run the Custom Frontend

```bash
# Install new dependencies (one-time)
pip install fastapi uvicorn[standard]

# Start the server
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Open in browser
http://localhost:8000
```

The Gradio fallback remains available:
```bash
python app.py   # still works, unchanged
```

---

## 11. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| StaticFiles mount shadows API routes if ordering is wrong | Mount static files **last** in `server.py`, after all `/api/` routes are registered |
| `TestClient` re-imports `server` across test classes, re-running lifespan | Patch `init_database` and `validate_api_keys` before import; use module-level `TestClient` per class |
| OSCE state read after `controller.run()` is stale if run() fails | Read state inside the `except` block too, or default to `osce_active=False` on error |
| `marked.js` CDN unreachable during offline demo | Bundle marked.min.js inline (paste into `<script>` tag in index.html as a fallback option) |
| Truncation risk when writing `web/index.html` (large file) | Write via bash Python script to `/sessions/.../outputs/` then copy, same pattern used for all large files in this project |
| Session ID lost on page refresh before `sessionStorage` write | Write to `sessionStorage` immediately on generation, before any API call |

---

## 12. Out of Scope for This Phase

- Streaming responses (server-sent events)
- Authentication / login
- Multi-student concurrent sessions
- Deployment to Hugging Face Spaces or cloud
- MCP server
- Any new skills or controller features
- Mobile-first responsive layout
