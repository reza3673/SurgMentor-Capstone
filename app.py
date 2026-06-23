# app.py
"""
SurgMentor — Gradio Web Interface

Three-tab Gradio application for the competition demo.
All interactions route through AgentController.run() — never directly to skills.
This ensures the security layer and evaluation logging apply to every request.

Tabs:
  Tab 1 — Case Retrieval   : ask surgical questions, retrieve annotated cases
  Tab 2 — OSCE Examination : stateful examiner session with score display
  Tab 3 — Student Profile  : performance stats + personalised study plan

Usage:
  python app.py
  -> Gradio UI at http://localhost:7860

Design notes:
  - No streaming: blocking responses for simplicity and reliability (Phase 5).
  - No authentication: local-only, single-user demo mode.
  - One UUID4 session ID per browser session, shared across all three tabs.
  - All Gradio state is held in gr.State objects — the controller's InMemory-
    SessionStore holds the authoritative agent state keyed by session_id.

Course concept: Deployability (Day 5) — browser-accessible demo with no cloud
infrastructure, no login, and no configuration beyond a .env file.
"""

from __future__ import annotations

import sys
import os

# Path bootstrap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Startup validation (before any Gradio import) ─────────────────────────────
from surgmentor.ui.helpers import (
    create_session_id,
    validate_api_keys,
    render_stats_markdown,
    detect_osce_finish,
    OSCE_FINISH_MARKERS,
)

validate_api_keys()  # SystemExit(1) if DEEPSEEK_API_KEY or JINA_API_KEY missing

import surgmentor.memory.db_store as db_store
db_store.init_database()

# ── Controller singleton ───────────────────────────────────────────────────────
from surgmentor.agent.controller import controller

# ── Gradio (imported after validation so startup errors are clear) ─────────────
import inspect
import gradio as gr

# ── Gradio version-compatibility: Chatbot type parameter ─────────────────────
# Gradio 4.x (≥ ~4.13): gr.Chatbot accepts type="messages" | "tuples".
#   Default is "tuples", so we must pass type="messages" to use dict format.
# Gradio 5.x+: the `type` parameter was removed; messages format is the only
#   format and requires no flag. Passing type= raises TypeError.
# Detection at import time so the conditional runs exactly once.
_CHATBOT_TYPE_KWARG: dict = (
    {"type": "messages"}
    if "type" in inspect.signature(gr.Chatbot.__init__).parameters
    else {}
)

# ── OSCE step counter display ─────────────────────────────────────────────────
try:
    from surgmentor.skills.osce_examiner_skill import MAX_OSCE_STEPS
except Exception:
    MAX_OSCE_STEPS = 6  # fallback if import fails


# ── Design system ─────────────────────────────────────────────────────────────
_CSS = """
/* ── SurgMentor Design System — Premium Health-Tech ────────────────────────── */

/* Soft blue-grey page background — matches health-tech product aesthetic */
body { background: #f0f5fa !important; }
.gradio-container {
    max-width: 920px !important;
    margin: 0 auto !important;
    background: #f0f5fa !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ── App header ─────────────────────────────────────────────────────────────── */
#sm-header {
    background: linear-gradient(135deg, #0369a1 0%, #075985 100%);
    color: white;
    padding: 28px 32px 24px;
    border-radius: 14px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(3, 105, 161, 0.22), 0 1px 4px rgba(0, 0, 0, 0.06);
}
#sm-header h2 {
    color: white !important;
    margin: 0 0 7px 0 !important;
    font-size: 1.8rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px !important;
}
#sm-header p {
    color: rgba(255, 255, 255, 0.78) !important;
    margin: 0 !important;
    font-size: 0.875rem !important;
    line-height: 1.5 !important;
}

/* ── Tab description text ────────────────────────────────────────────────────── */
.sm-tab-intro {
    font-size: 0.875rem !important;
    color: #64748b !important;
    line-height: 1.55 !important;
    margin: 6px 0 16px 0 !important;
    padding: 0 !important;
}
.sm-tab-intro p { margin: 0 !important; }

/* ── Chatbot: white card with subtle shadow ──────────────────────────────────── */
.chatbot {
    border-radius: 12px !important;
    border: 1px solid #e2e8f0 !important;
    background: white !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06) !important;
}

/* ── Text inputs ─────────────────────────────────────────────────────────────── */
textarea, .textbox textarea {
    border-radius: 10px !important;
    border: 1px solid #cbd5e1 !important;
    background: white !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
    font-size: 0.9rem !important;
    color: #1e293b !important;
}
textarea:focus, .textbox textarea:focus {
    border-color: #0369a1 !important;
    box-shadow: 0 0 0 3px rgba(3, 105, 161, 0.12) !important;
    outline: none !important;
}

/* ── Primary buttons ─────────────────────────────────────────────────────────── */
button.lg.primary, button.sm.primary, button.primary {
    background: #0369a1 !important;
    border: none !important;
    border-radius: 8px !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    box-shadow: 0 1px 3px rgba(3, 105, 161, 0.25) !important;
    transition: background 0.15s ease !important;
}
button.lg.primary:hover, button.sm.primary:hover, button.primary:hover {
    background: #0284c7 !important;
}

/* ── Secondary buttons ───────────────────────────────────────────────────────── */
button.lg.secondary, button.sm.secondary, button.secondary {
    background: white !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
    color: #475569 !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
}
button.lg.secondary:hover, button.sm.secondary:hover, button.secondary:hover {
    border-color: #0369a1 !important;
    color: #0369a1 !important;
    background: #f0f9ff !important;
}

/* ── OSCE session status bar ─────────────────────────────────────────────────── */
#osce-status {
    background: white;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #94a3b8;
    padding: 10px 16px;
    border-radius: 0 10px 10px 0;
    margin-bottom: 12px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
#osce-status p {
    margin: 0 !important;
    font-size: 0.84rem !important;
    color: #475569 !important;
    font-weight: 500 !important;
}

/* ── OSCE score result panel ─────────────────────────────────────────────────── */
#score-panel {
    background: white;
    border: 1px solid #bae6fd;
    border-top: 3px solid #0369a1;
    border-radius: 12px;
    padding: 18px 22px;
    margin-top: 16px;
    box-shadow: 0 2px 8px rgba(3, 105, 161, 0.09);
}
#score-panel p { color: #0c4a6e !important; font-size: 0.9rem !important; }

/* ── Profile panels: white cards with subtle shadow ─────────────────────────── */
#stats-panel {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 18px 22px;
    min-height: 76px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}
#stats-panel p { font-size: 0.9rem !important; color: #334155 !important; }

#plan-panel {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 18px 22px;
    min-height: 76px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}
#plan-panel p { font-size: 0.9rem !important; color: #334155 !important; }

/* ── Section labels ──────────────────────────────────────────────────────────── */
.sm-section-label {
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: #94a3b8 !important;
    margin: 20px 0 8px 0 !important;
    padding: 0 !important;
}
.sm-section-label p { margin: 0 !important; }

/* ── Footer / disclaimer ─────────────────────────────────────────────────────── */
#sm-footer {
    border-top: 1px solid #e2e8f0;
    margin-top: 20px;
    padding-top: 10px;
    padding-bottom: 6px;
}
#sm-footer p {
    font-size: 0.78rem !important;
    color: #94a3b8 !important;
    text-align: center !important;
    margin: 0 !important;
    letter-spacing: 0.01em;
}
"""

_HEADER_HTML = """
<div id="sm-header">
  <h2>SurgMentor</h2>
  <p>Surgical Education Platform &nbsp;&middot;&nbsp; Agentic OSCE Training
     &nbsp;&middot;&nbsp; Kaggle AI Agents Intensive 2026</p>
</div>
"""

_FOOTER_HTML = """
<div id="sm-footer">
  <p>For educational use only &mdash; responses do not constitute medical advice.
     Always consult a qualified clinician for real clinical decisions.</p>
</div>
"""


# ── Shared error handler ──────────────────────────────────────────────────────

def _safe_run(user_input: str, session_id: str) -> str:
    """
    Call controller.run() and return a safe string.
    On exception, return a user-friendly error message instead of raising.

    This is the single exception boundary between the Gradio UI and the agent
    controller. All three tabs call this function — never controller.run() directly.
    This ensures a controller crash or LLM timeout surfaces as a friendly message
    rather than a stack trace in the Gradio chat window.
    """
    try:
        return controller.run(user_input, session_id)
    except Exception as exc:
        print(f"[app.py] controller error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return (
            "Something went wrong on our end. Please try again.\n\n"
            "_If this keeps happening, click **New Session** to reset._"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Case Retrieval
# ─────────────────────────────────────────────────────────────────────────────

def chat_send(user_message: str, chat_history: list, session_id: str):
    """Handle a Free Chat send event."""
    if not user_message.strip():
        return chat_history, "", session_id

    response = _safe_run(user_message, session_id)
    # Messages format: list of {"role": ..., "content": ...} dicts
    chat_history = chat_history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": response},
    ]
    return chat_history, "", session_id


def chat_reset(session_id: str):
    """Clear chat history and start a new session."""
    from surgmentor.memory.session import default_store
    default_store.clear(session_id)
    new_id = create_session_id()
    return [], new_id, f"Session: `{new_id[:8]}…`"


def _build_chat_tab():
    with gr.Tab("Case Retrieval"):
        gr.HTML(
            '<p class="sm-tab-intro">Ask about surgical conditions, request cases by '
            "diagnosis, or explore clinical topics. The agent retrieves relevant cases "
            "from its knowledge base and cites its sources.</p>"
        )

        chat_display = gr.Chatbot(
            label="Conversation",
            height=460,
            show_label=False,
            **_CHATBOT_TYPE_KWARG,   # passes type="messages" only on Gradio 4.x
        )

        with gr.Row():
            chat_input = gr.Textbox(
                placeholder='e.g. "Show me a case about acute appendicitis"',
                show_label=False,
                scale=8,
                container=False,
            )
            send_btn = gr.Button("Send", variant="primary", scale=1)

        with gr.Row():
            clear_btn    = gr.Button("New Session", variant="secondary", size="sm")
            session_label = gr.Markdown(value="", elem_id="chat_session_label")

        # State
        chat_session = gr.State(create_session_id)

        # Events
        send_btn.click(
            fn=chat_send,
            inputs=[chat_input, chat_display, chat_session],
            outputs=[chat_display, chat_input, chat_session],
        )
        chat_input.submit(
            fn=chat_send,
            inputs=[chat_input, chat_display, chat_session],
            outputs=[chat_display, chat_input, chat_session],
        )
        clear_btn.click(
            fn=chat_reset,
            inputs=[chat_session],
            outputs=[chat_display, chat_session, session_label],
        )

    return chat_session


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — OSCE Examination
# ─────────────────────────────────────────────────────────────────────────────

def osce_start(osce_history: list, session_id: str):
    """Send 'start osce' to the controller and update UI state."""
    response = _safe_run("start osce", session_id)
    osce_history = osce_history + [
        {"role": "user", "content": "[Starting OSCE session]"},
        {"role": "assistant", "content": response},
    ]
    is_finish = detect_osce_finish(response)
    osce_active = not is_finish
    score_text = response if is_finish else ""
    step_label = _step_label(1 if osce_active else 0, osce_active)
    return (
        osce_history,
        score_text,
        step_label,
        osce_active,
        1 if osce_active else 0,
        session_id,
        # button visibility
        gr.update(visible=not osce_active),   # start_btn
        gr.update(visible=osce_active),        # send_btn
        gr.update(visible=osce_active),        # finish_btn
        gr.update(visible=is_finish),          # score_display
    )


def osce_turn(user_message: str, osce_history: list, osce_step: int,
              session_id: str):
    """Handle a student response during an active OSCE session."""
    if not user_message.strip():
        return (
            osce_history, "", score_text := "",
            _step_label(osce_step, True), True, osce_step, session_id,
            gr.update(visible=False),   # start_btn
            gr.update(visible=True),    # send_btn
            gr.update(visible=True),    # finish_btn
            gr.update(visible=False),   # score_display
        )

    response = _safe_run(user_message, session_id)
    osce_history = osce_history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": response},
    ]
    is_finish = detect_osce_finish(response)
    osce_active = not is_finish
    new_step = osce_step + 1
    score_text = response if is_finish else ""
    step_label = _step_label(new_step if osce_active else 0, osce_active)

    return (
        osce_history,
        "",                             # clear input box
        score_text,
        step_label,
        osce_active,
        new_step,
        session_id,
        gr.update(visible=not osce_active),   # start_btn
        gr.update(visible=osce_active),        # send_btn
        gr.update(visible=osce_active),        # finish_btn
        gr.update(visible=is_finish),          # score_display
    )


def osce_finish(osce_history: list, session_id: str):
    """Send 'finish' to the controller to end the OSCE session."""
    response = _safe_run("finish", session_id)
    osce_history = osce_history + [
        {"role": "user", "content": "[Ending OSCE session]"},
        {"role": "assistant", "content": response},
    ]
    is_finish = detect_osce_finish(response)
    score_text = response if is_finish else (
        response + "\n\n_Session ended._"
    )
    return (
        osce_history,
        score_text,
        _step_label(0, False),
        False,          # osce_active
        0,              # osce_step
        session_id,
        gr.update(visible=True),    # start_btn
        gr.update(visible=False),   # send_btn
        gr.update(visible=False),   # finish_btn
        gr.update(visible=True),    # score_display
    )


def osce_reset(session_id: str):
    """Clear OSCE display and start a fresh session."""
    from surgmentor.memory.session import default_store
    default_store.clear(session_id)
    new_id = create_session_id()
    return (
        [],             # osce_history
        "",             # score_text
        "No active session.",
        False,          # osce_active
        0,              # osce_step
        new_id,
        gr.update(visible=True),    # start_btn
        gr.update(visible=False),   # send_btn
        gr.update(visible=False),   # finish_btn
        gr.update(visible=False),   # score_display
    )


def _step_label(step: int, active: bool) -> str:
    if not active:
        return "No active session."
    return f"Session active — Step {step} / {MAX_OSCE_STEPS}"


def _build_osce_tab(shared_session: gr.State):
    with gr.Tab("OSCE Examination"):
        gr.HTML(
            '<p class="sm-tab-intro">The AI acts as a clinical examiner, presenting a '
            "patient case step-by-step and evaluating your reasoning. Click "
            "<strong>Start Session</strong> to begin, then respond to each examiner "
            "prompt. Click <strong>End &amp; Score</strong> when ready for your "
            "assessment.</p>"
        )

        # Status bar — always visible, updates with session state
        status_label = gr.Markdown(
            value="No active session.",
            elem_id="osce-status",
        )

        # Conversation display
        osce_display = gr.Chatbot(
            label="OSCE Session",
            height=380,
            show_label=False,
            **_CHATBOT_TYPE_KWARG,   # passes type="messages" only on Gradio 4.x
        )

        # Input row — shown only when a session is active
        with gr.Row():
            osce_input = gr.Textbox(
                placeholder="Type your clinical response here and press Enter or Send…",
                show_label=False,
                scale=8,
                container=False,
                visible=False,
            )
            send_btn = gr.Button("Send", variant="primary", scale=1, visible=False)

        # Control buttons — always visible
        with gr.Row():
            start_btn  = gr.Button("Start Session",  variant="primary",    visible=True)

            finish_btn = gr.Button("End & Score",    variant="secondary",  visible=False)
            reset_btn  = gr.Button("New Session",    variant="secondary")

        # Score panel -- shown after session ends
        score_display = gr.Markdown(
            value="",
            elem_id="score-panel",
            visible=False,
        )

        # Local state (independent from shared_session so OSCE and Chat don't collide)
        osce_session  = gr.State(create_session_id)
        osce_active   = gr.State(False)
        osce_step_st  = gr.State(0)

        # Collect all outputs for event handlers
        _common_outputs = [
            osce_display,
            score_display,
            status_label,
            osce_active,
            osce_step_st,
            osce_session,
            start_btn,
            send_btn,
            finish_btn,
            score_display,  # visibility update target
        ]

        start_btn.click(
            fn=osce_start,
            inputs=[osce_display, osce_session],
            outputs=_common_outputs,
        )

        send_btn.click(
            fn=osce_turn,
            inputs=[osce_input, osce_display, osce_step_st, osce_session],
            outputs=[osce_display, osce_input, score_display, status_label,
                     osce_active, osce_step_st, osce_session,
                     start_btn, send_btn, finish_btn, score_display],
        )
        osce_input.submit(
            fn=osce_turn,
            inputs=[osce_input, osce_display, osce_step_st, osce_session],
            outputs=[osce_display, osce_input, score_display, status_label,
                     osce_active, osce_step_st, osce_session,
                     start_btn, send_btn, finish_btn, score_display],
        )

        finish_btn.click(
            fn=osce_finish,
            inputs=[osce_display, osce_session],
            outputs=_common_outputs,
        )

        reset_btn.click(
            fn=osce_reset,
            inputs=[osce_session],
            outputs=[osce_display, score_display, status_label,
                     osce_active, osce_step_st, osce_session,
                     start_btn, send_btn, finish_btn, score_display],
        )

        # Show input box when OSCE is active
        def _toggle_input(active):
            return gr.update(visible=active)

        osce_active.change(
            fn=_toggle_input,
            inputs=[osce_active],
            outputs=[osce_input],
        )

    return osce_session


# ---------------------------------------------------------------------------
# TAB 3 -- Student Profile
# ---------------------------------------------------------------------------

def profile_refresh(session_id: str):
    """Fetch latest stats from SQLite and render as Markdown."""
    try:
        stats = db_store.get_student_stats(session_id)
        return render_stats_markdown(stats), session_id
    except Exception as exc:
        return f"_Error loading stats: {exc}_", session_id


def profile_generate_plan(session_id: str):
    """Ask the controller for a personalised study plan."""
    response = _safe_run("what should I study", session_id)
    return response, session_id


def _build_profile_tab(osce_session: gr.State):
    with gr.Tab("Student Profile"):
        gr.HTML(
            '<p class="sm-tab-intro">Performance statistics and a personalised study '
            "plan based on your OSCE history. Complete at least one OSCE session to "
            "populate this page.</p>"
        )

        # Performance Statistics
        gr.HTML('<p class="sm-section-label">Performance Statistics</p>')

        stats_display = gr.Markdown(
            value="_Click Refresh to load your performance data._",
            elem_id="stats-panel",
        )

        refresh_btn = gr.Button(
            "Refresh Stats",
            variant="secondary",
            size="sm",
        )

        # Study Plan
        gr.HTML('<p class="sm-section-label" style="margin-top:18px;">Personalised Study Plan</p>')

        plan_display = gr.Markdown(
            value="_Click Generate Plan for AI-personalised study recommendations._",
            elem_id="plan-panel",
        )

        generate_btn = gr.Button(
            "Generate Study Plan",
            variant="primary",
            size="sm",
        )

        # The Profile tab shares the OSCE session so stats reflect OSCE results
        # immediately after finishing a session.
        refresh_btn.click(
            fn=profile_refresh,
            inputs=[osce_session],
            outputs=[stats_display, osce_session],
        )

        generate_btn.click(
            fn=profile_generate_plan,
            inputs=[osce_session],
            outputs=[plan_display, osce_session],
        )


# ---------------------------------------------------------------------------
# App assembly
# ---------------------------------------------------------------------------

def build_app() -> gr.Blocks:
    with gr.Blocks(
        title="SurgMentor -- Agentic OSCE Trainer",
        theme=gr.themes.Soft(),
        css=_CSS,
    ) as app:
        gr.HTML(_HEADER_HTML)

        chat_session = _build_chat_tab()
        osce_session = _build_osce_tab(chat_session)
        _build_profile_tab(osce_session)

        gr.HTML(_FOOTER_HTML)

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = build_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
