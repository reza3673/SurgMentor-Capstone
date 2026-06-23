# server.py
"""
SurgMentor FastAPI server — custom frontend entry point.

Wraps AgentController with a minimal HTTP layer.
All business logic stays inside the controller and skill layers.
This file is a thin shell: receive request → call controller.run() → return response.

Run:
  uvicorn server:app --host 0.0.0.0 --port 8000 --reload

Or using config.py:
  python -c "import uvicorn, config; uvicorn.run('server:app', host='0.0.0.0', port=config.FASTAPI_PORT, reload=True)"

Endpoints:
  POST /api/chat               Free-chat (Case Retrieval)
  POST /api/osce/start         Start a new OSCE session
  POST /api/osce/turn          Send one OSCE response
  POST /api/osce/finish        Explicitly end and score the OSCE session
  POST /api/osce/reset         Clear session state, return a new session ID
  GET  /api/profile            Fetch student stats as pre-rendered Markdown
  POST /api/profile/plan       Generate a personalised study plan

Static files:
  GET  /                       Serves web/index.html (the custom SPA)
  GET  /*                      All other paths served from web/

Course concept: Deployability (Day 5) — the FastAPI server is the production-grade
alternative to Gradio; it exposes the same controller.run() interface via HTTP.
"""

from __future__ import annotations

import os
import sys

# Path bootstrap — allows running from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import surgmentor.memory.db_store as db_store
from surgmentor.ui.helpers import (
    validate_api_keys,
    detect_osce_finish,
    render_stats_markdown,
    create_session_id,
)
from surgmentor.agent.controller import controller
from surgmentor.memory.session import default_store
from surgmentor.skills.osce_examiner_skill import MAX_OSCE_STEPS


# ── Lifespan: startup / shutdown ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
      1. Validate that DEEPSEEK_API_KEY and JINA_API_KEY are present.
      2. Initialise the SQLite schema (idempotent — safe to call on every start).
    Shutdown: nothing to clean up (SQLite connections are per-function).
    """
    validate_api_keys()
    db_store.init_database()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SurgMentor API",
    description="Agentic surgical OSCE training — HTTP interface to AgentController",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ───────────────────────────────────────────────────────────

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
    max_steps:   int  = MAX_OSCE_STEPS   # authoritative from osce_examiner_skill

class ResetResponse(BaseModel):
    new_session_id: str

class ProfileResponse(BaseModel):
    session_id: str
    stats_md:   str
    has_data:   bool

class PlanResponse(BaseModel):
    session_id: str
    response:   str


# ── Shared helper ─────────────────────────────────────────────────────────────

def _safe_run(message: str, session_id: str) -> str:
    """
    Call controller.run() and catch all exceptions.
    Returns a user-friendly error string on failure (never raises).
    """
    try:
        return controller.run(message, session_id)
    except Exception:
        return (
            "⚠️ Something went wrong on our end. Please try again.\n\n"
            "_If this keeps happening, click Reset to start a new session._"
        )


def _read_osce_state(session_id: str) -> tuple[bool, int]:
    """
    Read osce_active and osce_step from the session store.
    Returns (False, 0) if the session does not exist.
    """
    try:
        state = default_store.read(session_id)
        return state.osce_active, state.osce_step
    except Exception:
        return False, 0


def _reset_osce_state(session_id: str) -> None:
    """
    Reset only the OSCE-specific in-memory fields before starting a new session.

    Called exclusively by osce_start() to ensure the controller sees
    osce_active=False when it processes "start osce".  Without this reset,
    AgentController._apply_osce_override() forces any intent to OSCE_TURN
    while osce_active is True — meaning a page-reload or second Start click
    would launch a mid-session turn instead of a fresh examination.

    Uses controller.session_store as the authoritative store — the exact same
    object that controller.run() reads from on every cycle.  In the current
    single-process deployment, controller.session_store and the module-level
    default_store are the same InMemorySessionStore instance (confirmed by
    id() comparison).  Writing through controller.session_store makes this
    guarantee explicit and is robust against future refactoring where the two
    could diverge (e.g., if controller is given an injected store in tests).

    Fields reset:
      osce_active=False, osce_step=0, current_case=None,
      mode='chat', osce_history_start_index=0

    Fields preserved (intentionally):
      conversation_history — osce_history_start_index correctly excludes
                             pre-OSCE turns from _turn() bundles; no need to
                             clear history to get a clean OSCE context.
      weak_areas           — loaded from SQLite on session init; kept for planner
      score_history        — student progress; kept for stats display

    Does NOT touch SQLite — persistent scores, topics, and OSCE results are
    stored in db_store and are completely unaffected.
    """
    try:
        state = controller.session_store.read(session_id)
        state.osce_active              = False
        state.osce_step                = 0
        state.current_case             = None
        state.mode                     = "chat"
        state.osce_history_start_index = 0
        controller.session_store.write(session_id, state)
    except Exception:
        pass  # no-op if session absent — controller creates a fresh state anyway


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """
    Free-chat (Case Retrieval) endpoint.
    Forwards the student message to controller.run() and returns the response.
    """
    response = _safe_run(req.message, req.session_id)
    return ChatResponse(session_id=req.session_id, response=response)


@app.post("/api/osce/start", response_model=OsceStateResponse)
async def osce_start(req: SessionRequest) -> OsceStateResponse:
    """
    Start a new OSCE session.

    Always initialises a fresh examination, even if the session already has
    osce_active=True (e.g. page reload, second Start click, tab reuse).

    The reset step clears osce_active/osce_step before calling controller.run
    so AgentController._apply_osce_override() sees a clean state and routes
    correctly to START_OSCE instead of forcing OSCE_TURN.
    """
    _reset_osce_state(req.session_id)          # must precede controller.run
    response = _safe_run("start osce", req.session_id)
    osce_active, osce_step = _read_osce_state(req.session_id)
    return OsceStateResponse(
        session_id=req.session_id,
        response=response,
        osce_active=osce_active,
        osce_step=osce_step,
        is_finish=False,
    )


@app.post("/api/osce/turn", response_model=OsceStateResponse)
async def osce_turn(req: ChatRequest) -> OsceStateResponse:
    """
    Send one student response during an active OSCE session.

    is_finish is True when the controller's response contains a score block
    (EvaluationSkill fired — session was scored automatically or manually).
    The frontend uses is_finish to transition to the score panel without a
    second request.
    """
    response    = _safe_run(req.message, req.session_id)
    is_finish   = detect_osce_finish(response)
    osce_active, osce_step = _read_osce_state(req.session_id)
    return OsceStateResponse(
        session_id=req.session_id,
        response=response,
        osce_active=osce_active,
        osce_step=osce_step,
        is_finish=is_finish,
    )


@app.post("/api/osce/finish", response_model=OsceStateResponse)
async def osce_finish(req: SessionRequest) -> OsceStateResponse:
    """
    Explicitly finish and score the OSCE session.
    Sends 'finish' to the controller. is_finish is always True on this endpoint.
    """
    response    = _safe_run("finish", req.session_id)
    is_finish   = detect_osce_finish(response)
    osce_active, osce_step = _read_osce_state(req.session_id)
    return OsceStateResponse(
        session_id=req.session_id,
        response=response,
        osce_active=osce_active,
        osce_step=osce_step,
        is_finish=is_finish,
    )


@app.post("/api/osce/reset", response_model=ResetResponse)
async def osce_reset(req: SessionRequest) -> ResetResponse:
    """
    Clear session state for the given session_id and issue a fresh session ID.
    The frontend updates its stored session_id with new_session_id and resets
    all display state.
    """
    default_store.clear(req.session_id)
    new_id = create_session_id()
    return ResetResponse(new_session_id=new_id)


@app.get("/api/profile", response_model=ProfileResponse)
async def profile(session_id: str) -> ProfileResponse:
    """
    Fetch student stats as pre-rendered Markdown.
    Calls db_store.get_student_stats() directly — this is a pure read that does
    not need security filtering, intent classification, or state mutation.
    """
    try:
        stats = db_store.get_student_stats(session_id)
    except Exception:
        stats = {}

    stats_md = render_stats_markdown(stats)
    has_data = bool(stats)
    return ProfileResponse(session_id=session_id, stats_md=stats_md, has_data=has_data)


@app.post("/api/profile/plan", response_model=PlanResponse)
async def profile_plan(req: SessionRequest) -> PlanResponse:
    """
    Generate a personalised study plan via StudyPlannerSkill.
    Forwards 'what should I study' to the controller.
    """
    response = _safe_run("what should I study", req.session_id)
    return PlanResponse(session_id=req.session_id, response=response)


# ── Static files — MUST be mounted after all /api/ routes ────────────────────
# StaticFiles with html=True serves web/index.html for '/' and any path that
# does not match a file on disk. This means the SPA handles its own routing.
_WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
if os.path.isdir(_WEB_DIR):
    app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="static")


# ── Direct launch ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    import config
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=config.FASTAPI_PORT,
        reload=False,
    )
