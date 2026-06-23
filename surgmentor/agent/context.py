# surgmentor/agent/context.py
"""
Context bundle builder for the AgentController.

This module implements the Day 1 context engineering principle:
each skill receives a trimmed, skill-relevant view of session state —
NOT the full SessionState. The controller calls build_context_bundle()
before every skill invocation.

Why trimming matters:
  - Reduces token cost (shorter prompts = lower API spend)
  - Reduces hallucination risk (irrelevant context confuses the LLM)
  - Makes each skill's purpose visible from the bundle it receives

Per-skill trim rules (from PHASE_4_PLAN.md §5):

  RETRIEVE_CASE / CaseRetrievalSkill:
    student_input + windowed history (last HISTORY_WINDOW turns) + weak_areas
    History is windowed because free-chat doesn't need full session context.

  START_OSCE / OSCEExaminerSkill._init():
    No history, no case (pre-init). score_history for unseen-case selection.
    current_case=None signals the skill to load a fresh case.

  OSCE_TURN / OSCEExaminerSkill._turn():
    student_input + FULL OSCE history slice + current_case + osce_step.
    The examiner needs the complete transcript to ask coherent follow-ups.
    History is sliced from osce_history_start_index, not windowed.

  FINISH_OSCE / OSCEExaminerSkill._finish():
    Full OSCE history + current_case + finish=True in parameters.
    student_input is not forwarded — the finish action is controller-initiated.

  GET_FEEDBACK / EvaluationSkill:
    Full OSCE history + current_case + identifiers in parameters.
    Used when a student asks "how did I do?" after a session ends.

  STUDY_PLAN / StudyPlannerSkill:
    weak_areas + score_history only. No session_history.
    The planner works from performance data, not the current conversation.

  UNKNOWN:
    Minimal bundle — not routed to a skill. Included for completeness.

Course concept: Context Engineering (Day 1)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import HISTORY_WINDOW
from surgmentor.agent.intent import IntentCategory
from surgmentor.memory.session import SessionState
from surgmentor.skills.base import ContextBundle


# ── Public interface ──────────────────────────────────────────────────────────

def build_context_bundle(
    intent:        IntentCategory,
    student_input: str,
    state:         SessionState,
) -> ContextBundle:
    """
    Build a trimmed, skill-relevant ContextBundle for the given intent.

    The bundle is the only communication channel between the controller and a skill.
    Skills must not read SessionState directly — they receive only the fields
    the controller has chosen to forward. This enforces the least-privilege
    principle for context (a form of Day 4 security thinking applied to LLM context).

    Args:
        intent:        The classified (and OSCE-overridden) intent.
        student_input: The sanitized student message (from SecurityLayer).
        state:         The current SessionState (read from InMemorySessionStore).

    Returns:
        A ContextBundle with only the fields relevant to the selected skill.
    """
    builders = {
        IntentCategory.RETRIEVE_CASE: _bundle_retrieve_case,
        IntentCategory.START_OSCE:    _bundle_start_osce,
        IntentCategory.OSCE_TURN:     _bundle_osce_turn,
        IntentCategory.FINISH_OSCE:   _bundle_finish_osce,
        IntentCategory.GET_FEEDBACK:  _bundle_get_feedback,
        IntentCategory.STUDY_PLAN:    _bundle_study_plan,
        IntentCategory.UNKNOWN:       _bundle_minimal,
    }
    builder = builders.get(intent, _bundle_minimal)
    return builder(student_input, state)


# ── Per-intent bundle builders ────────────────────────────────────────────────

def _bundle_retrieve_case(student_input: str, state: SessionState) -> ContextBundle:
    """
    CaseRetrievalSkill: query + windowed history + weak_areas for retrieval bias.

    Context engineering choice: history is windowed (last HISTORY_WINDOW turns).
    Free-chat sessions can grow long, but the retrieval skill only needs recent
    context to understand the student's current topic of interest.
    weak_areas biases ChromaDB retrieval toward the student's learning gaps
    (Day 1 principle: steer retrieval toward what the student most needs to see).
    """
    return ContextBundle(
        student_input   = student_input,
        session_history = state.conversation_history[-HISTORY_WINDOW:],
        current_case    = None,
        student_id      = state.student_id,
        weak_areas      = list(state.weak_areas),
        score_history   = [],
        osce_step       = 0,
        parameters      = {},
    )


def _bundle_start_osce(student_input: str, state: SessionState) -> ContextBundle:
    """
    OSCEExaminerSkill (init path): no history, no case, score_history for case selection.

    current_case=None is the signal to OSCEExaminerSkill._init() that this is a
    fresh session requiring a new case to be loaded. score_history is forwarded
    so _pick_unseen_case() can avoid cases the student has already seen.
    student_input is not forwarded — the init action ignores the triggering message.
    """
    return ContextBundle(
        student_input   = "",
        session_history = [],
        current_case    = None,
        student_id      = state.student_id,
        weak_areas      = list(state.weak_areas),
        score_history   = list(state.score_history),
        osce_step       = 0,
        parameters      = {},
    )


def _bundle_osce_turn(student_input: str, state: SessionState) -> ContextBundle:
    """
    OSCEExaminerSkill (turn path): student response + FULL OSCE history + case.

    Context engineering choice: history is NOT windowed here. The OSCE examiner
    needs the complete transcript of the current session to:
      - Know which questions have already been asked
      - Know what the student has already answered
      - Maintain continuity across turns
    The OSCE history slice (from osce_history_start_index) excludes free-chat
    turns that occurred before the OSCE session started.
    """
    return ContextBundle(
        student_input   = student_input,
        session_history = _get_osce_history(state),
        current_case    = state.current_case,
        student_id      = state.student_id,
        weak_areas      = [],
        score_history   = [],
        osce_step       = state.osce_step,
        parameters      = {},
    )


def _bundle_finish_osce(student_input: str, state: SessionState) -> ContextBundle:
    """
    OSCEExaminerSkill (finish path): OSCE history + case + finish=True in parameters.

    finish=True in parameters tells OSCEExaminerSkill.run() to route to _finish()
    immediately, regardless of osce_step. student_input is not forwarded — the
    finish action is initiated by the controller, not the student's text.
    """
    case_id = (state.current_case or {}).get("case_id", "unknown")
    return ContextBundle(
        student_input   = "",
        session_history = _get_osce_history(state),
        current_case    = state.current_case,
        student_id      = state.student_id,
        weak_areas      = [],
        score_history   = [],
        osce_step       = state.osce_step,
        parameters      = {"finish": True, "case_id": case_id},
    )


def _bundle_get_feedback(student_input: str, state: SessionState) -> ContextBundle:
    """
    EvaluationSkill: OSCE history + current_case + identifiers in parameters.

    Used when a student explicitly asks for feedback after a session. If no OSCE
    session has been completed (current_case=None, empty history), EvaluationSkill's
    participation guard will fire and return a helpful "no session to score" message.
    """
    case_id    = (state.current_case or {}).get("case_id", "unknown")
    session_id = state.session_id
    return ContextBundle(
        student_input   = "",
        session_history = _get_osce_history(state),
        current_case    = state.current_case,
        student_id      = state.student_id,
        weak_areas      = [],
        score_history   = [],
        osce_step       = 0,
        parameters      = {"case_id": case_id, "session_id": session_id},
    )


def _bundle_study_plan(student_input: str, state: SessionState) -> ContextBundle:
    """
    StudyPlannerSkill: weak_areas + score_history only — no session_history.

    Context engineering choice: the planner operates on the student's performance
    data (SQLite), not the current conversation. Forwarding session_history would
    add noise without improving the study plan. The planner calls db_store itself
    using student_id, so weak_areas and score_history here are the session-level
    cache (populated at session creation from the student's persistent record).
    """
    return ContextBundle(
        student_input   = student_input,
        session_history = [],
        current_case    = None,
        student_id      = state.student_id,
        weak_areas      = list(state.weak_areas),
        score_history   = list(state.score_history),
        osce_step       = 0,
        parameters      = {},
    )


def _bundle_minimal(student_input: str, state: SessionState) -> ContextBundle:
    """UNKNOWN intent: minimal bundle. Not routed to a skill."""
    return ContextBundle(
        student_input   = student_input,
        session_history = [],
        current_case    = None,
        student_id      = state.student_id,
        weak_areas      = [],
        score_history   = [],
        osce_step       = 0,
        parameters      = {},
    )


# ── History slicer ────────────────────────────────────────────────────────────

def _get_osce_history(state: SessionState) -> list[dict]:
    """
    Return only the conversation turns belonging to the current OSCE session.

    Slices state.conversation_history from osce_history_start_index onward.
    This excludes free-chat turns that occurred before the OSCE was initiated —
    the examiner should not see unrelated chat context.

    Before any OSCE has started (osce_history_start_index=0, conversation_history=[]),
    this returns [] — safe fallback that EvaluationSkill's participation guard handles.
    """
    start = getattr(state, "osce_history_start_index", 0)
    return state.conversation_history[start:]


# ── Standalone import test ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("context.py — import test")
    print("=" * 60)
    from surgmentor.memory.session import make_default_state

    state = make_default_state("s1", "student-1", mode="chat")
    state.weak_areas      = ["History taking", "Management plan"]
    state.score_history   = [{"case_id": "1", "score": 7}]
    state.conversation_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi, how can I help?"},
    ]

    b = build_context_bundle(IntentCategory.RETRIEVE_CASE, "show me a case", state)
    assert b.weak_areas == ["History taking", "Management plan"]
    assert b.current_case is None
    print("✅  RETRIEVE_CASE bundle: weak_areas forwarded, current_case=None")

    b2 = build_context_bundle(IntentCategory.START_OSCE, "start osce", state)
    assert b2.current_case is None
    assert b2.osce_step == 0
    assert b2.score_history == [{"case_id": "1", "score": 7}]
    print("✅  START_OSCE bundle: current_case=None, score_history forwarded")

    b3 = build_context_bundle(IntentCategory.STUDY_PLAN, "what should I study", state)
    assert b3.session_history == []
    assert b3.weak_areas == ["History taking", "Management plan"]
    print("✅  STUDY_PLAN bundle: no session_history, weak_areas forwarded")

    print("\n✅  Import test PASSED")
