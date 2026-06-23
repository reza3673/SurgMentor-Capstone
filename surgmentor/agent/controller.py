# surgmentor/agent/controller.py
"""
AgentController — the cognitive core of SurgMentor.

This is the primary demonstration file for the Kaggle AI Agents Intensive
competition. It implements the full ADK agent loop:

  ── PERCEIVE ──  Read session state + sanitize input (SecurityLayer pre-flight)
  ── PLAN ──      Classify intent + apply OSCE override + select skill + build bundle
  ── ACT ──       Invoke the selected skill (controller never calls LLM directly)
  ── OBSERVE ──   Filter output (SecurityLayer post-flight) + log TurnSignal
                  + update session state + write state back to memory

The controller is stateless per call. All state lives in InMemorySessionStore.
Skills are stateless across calls — they receive a ContextBundle and return a
SkillResult. The controller owns all state transitions.

Course concepts demonstrated:
  Agent Architecture (Day 2)   — explicit perceive → plan → act → observe loop
  Context Engineering (Day 1)  — per-skill trimmed ContextBundle (in context.py)
  Security Features (Day 4)    — two-point SecurityLayer wiring (pre + post)
  Evaluation (Day 4)           — TurnSignal written after every cycle
  Agent Skills (Day 3)         — skill registry, composable, independently testable

Design references (read-only):
  surgery-rag/telegram_bot.py — session state management pattern
  docs/PHASE_4_PLAN.md §6     — authoritative loop design

Dependency injection: session_store and security are injected via __init__.
Tests pass isolated InMemorySessionStore instances and mock SecurityLayer objects.
The module-level `controller` singleton is used by run.py and app.py (Phase 5).
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime

from surgmentor.agent.intent    import IntentCategory, classify_intent, get_unknown_response
from surgmentor.agent.context   import build_context_bundle
from surgmentor.memory.session  import (
    InMemorySessionStore, SessionState, default_store, make_default_state
)
from surgmentor.evaluation.logger import TurnSignal, write_turn_signal
from surgmentor.security.layer  import security_layer, SecurityLayer
from surgmentor.skills.base     import Skill, SkillResult
from surgmentor.skills.case_retrieval_skill import CaseRetrievalSkill
from surgmentor.skills.osce_examiner_skill  import OSCEExaminerSkill, MAX_OSCE_STEPS
from surgmentor.skills.evaluation_skill     import EvaluationSkill
from surgmentor.skills.study_planner_skill  import StudyPlannerSkill
import surgmentor.memory.db_store as db_store


# ── AgentController ───────────────────────────────────────────────────────────

class AgentController:
    """
    The SurgMentor agent controller.

    Implements the ADK perceive → plan → act → observe loop.
    Routes student input to the correct skill, wires security, and logs evaluation
    signals. The controller never calls the LLM directly — all LLM interactions
    are encapsulated inside skills and the intent classifier.

    Usage (Phase 5):
        ctrl = AgentController()          # or use module-level `controller` singleton
        response = ctrl.run(input_text, session_id)
    """

    def __init__(
        self,
        session_store: InMemorySessionStore | None = None,
        security:      SecurityLayer        | None = None,
    ) -> None:
        """
        Initialise the controller with injectable dependencies.

        Args:
            session_store: In-memory session store. Defaults to module-level singleton.
                           Tests pass a fresh InMemorySessionStore() for isolation.
            security:      SecurityLayer instance. Defaults to module-level singleton.
                           Tests may pass a mock or real instance.
        """
        self.session_store = session_store or default_store
        self.security      = security      or security_layer

        # ── Skill registry ────────────────────────────────────────────────────
        # Maps each IntentCategory to a Skill instance (or None for UNKNOWN).
        # All skills are instantiated once; they are stateless across calls —
        # state lives in SessionState, not inside the skill.
        #
        # OSCEExaminerSkill is listed three times (START_OSCE / OSCE_TURN /
        # FINISH_OSCE) using the same instance. The skill's dispatch logic reads
        # bundle.osce_step and bundle.parameters.get("finish") to select
        # _init() / _turn() / _finish() — no additional routing needed here.
        self._registry: dict[IntentCategory, Skill | None] = {
            IntentCategory.RETRIEVE_CASE: CaseRetrievalSkill(),
            IntentCategory.START_OSCE:    OSCEExaminerSkill(),
            IntentCategory.OSCE_TURN:     OSCEExaminerSkill(),
            IntentCategory.FINISH_OSCE:   OSCEExaminerSkill(),
            IntentCategory.GET_FEEDBACK:  EvaluationSkill(),
            IntentCategory.STUDY_PLAN:    StudyPlannerSkill(),
            IntentCategory.UNKNOWN:       None,
        }

    # ── Public interface ──────────────────────────────────────────────────────

    def run(self, student_input: str, session_id: str) -> str:
        """
        Process one student turn and return a safe, filtered response string.

        The full ADK loop runs inside this method. Every call to run() produces:
          - One TurnSignal line in eval_log.jsonl  (per-turn audit)
          - One updated SessionState in session_store (persistent context)
          - One safe response string returned to the student

        Args:
            student_input: Raw student message (may be unsanitized).
            session_id:    Stable session identifier (str); controls which
                           SessionState is read and written.

        Returns:
            A safe, filtered response string ready to display to the student.
        """
        start_time    = time.time()
        skill_result: SkillResult | None = None

        # ── PERCEIVE ─────────────────────────────────────────────────────────
        # Step 1: Read current session state from memory.
        #         Creates a default state (and loads historical student data) on
        #         the first call for this session_id.
        state = self._get_or_init_state(session_id)

        # Step 2: Pre-flight security — sanitize and validate the raw student input.
        #         If blocked (PII, too long, injection, out-of-scope), return the
        #         deflection message immediately. No skill is called.
        #         osce_active is forwarded so the security layer can skip LLM scope
        #         classification during an active OSCE session — clinical interview
        #         questions like "where is the exact pain?" must not be blocked by
        #         a context-free scope classifier; the OSCE override (Step 4) handles
        #         routing. Stage 1 rule-based checks still apply unconditionally.
        sanitized = self.security.sanitize_input(student_input, osce_active=state.osce_active)
        if sanitized.is_blocked:
            deflection = self.security.get_deflection_message(sanitized.rejection_reason)
            self._log_turn(session_id, "BLOCKED", "None", True,
                           deflection, int((time.time() - start_time) * 1000))
            return deflection

        # ── PLAN ─────────────────────────────────────────────────────────────
        # Step 3: Classify the student's intent.
        #         Session context (mode, osce_active, osce_step) is forwarded so
        #         the classifier can distinguish OSCE_TURN from RETRIEVE_CASE.
        intent = classify_intent(sanitized.clean_text, state)

        # Step 4: Apply OSCE session override.
        #         When osce_active is True, session state takes precedence over
        #         the classifier. Mid-session inputs are never misrouted to
        #         RETRIEVE_CASE or STUDY_PLAN regardless of their content.
        intent = self._apply_osce_override(intent, state)

        # Step 5: Select the skill for this intent from the registry.
        skill = self._registry.get(intent)

        # Step 6: Build a trimmed, skill-relevant context bundle.
        #         Each skill receives only the fields it needs — not the full
        #         session state. This is context engineering in practice (Day 1).
        bundle = build_context_bundle(intent, sanitized.clean_text, state)

        # ── ACT ──────────────────────────────────────────────────────────────
        # Step 7: Invoke the selected skill.
        #         The controller never calls the LLM directly — all LLM
        #         interactions are encapsulated inside skills. UNKNOWN → no skill.
        if skill is None:
            raw_response = get_unknown_response()
        else:
            try:
                skill_result = skill.run(bundle)
                raw_response = skill_result.response_text
            except Exception:
                raw_response = get_unknown_response()
                skill_result = None

        # ── OBSERVE ──────────────────────────────────────────────────────────
        # Step 8: Post-flight security — filter the skill output.
        #         Every response passes through this filter before reaching the
        #         student. The educational disclaimer is injected here.
        #         osce_step is forwarded so the filter can annotate OSCE responses.
        filtered = self.security.filter_output(
            raw_response,
            osce_step=state.osce_step if state.osce_active else None,
        )
        safe_response = filtered.filtered_text

        # Step 9: Update session state with the results of this turn.
        #         Appends history, transitions OSCE fields, merges weak_areas.
        state = self._update_state(
            state, intent, student_input, safe_response, skill_result,
            filtered.safety_pass,
        )

        # Step 10: Write updated state back to session memory.
        self.session_store.write(session_id, state)

        # Step 11: Write per-turn evaluation signal to eval_log.jsonl.
        #          One TurnSignal per run() call. Provides an audit trail of
        #          intent routing, skill selection, and safety pass status.
        latency_ms = int((time.time() - start_time) * 1000)
        self._log_turn(
            session_id, intent.value,
            skill.__class__.__name__ if skill else "None",
            filtered.safety_pass, safe_response, latency_ms,
        )

        return safe_response

    # ── Private: session initialisation ──────────────────────────────────────

    def _get_or_init_state(self, session_id: str) -> SessionState:
        """
        Read session state. On first call, pre-populate with historical student
        data (weak areas, score history) from the student's persistent SQLite record.

        This one-time load at session creation ensures the planner and retrieval
        skills see the student's learning gaps without a per-turn DB round trip.
        """
        is_new = session_id not in self.session_store.list_active()
        state  = self.session_store.read(session_id, student_id=session_id)

        if is_new:
            try:
                stats = db_store.get_student_stats(session_id)
                if stats:
                    state.weak_areas    = [a for a, _ in stats.get("weak_areas", [])]
                    state.score_history = stats.get("recent_osce", [])
                    self.session_store.write(session_id, state)
            except Exception:
                pass  # historical load failure must not block the session
        return state

    # ── Private: OSCE override ────────────────────────────────────────────────

    def _apply_osce_override(
        self, intent: IntentCategory, state: SessionState
    ) -> IntentCategory:
        """
        OSCE session state takes precedence over intent classification.

        When osce_active is True:
          - Auto-finish: if osce_step >= MAX_OSCE_STEPS, force FINISH_OSCE
            regardless of what the student typed (time limit reached).
          - Otherwise: any intent except FINISH_OSCE is overridden to OSCE_TURN.
            This prevents a mid-session clinical response (e.g., "I would order a
            CT scan") from being misrouted to RETRIEVE_CASE.

        When osce_active is False: intent is returned unchanged.
        """
        if not state.osce_active:
            return intent
        if state.osce_step >= MAX_OSCE_STEPS:
            return IntentCategory.FINISH_OSCE
        if intent != IntentCategory.FINISH_OSCE:
            return IntentCategory.OSCE_TURN
        return intent

    # ── Private: state update ─────────────────────────────────────────────────

    def _update_state(
        self,
        state:         SessionState,
        intent:        IntentCategory,
        student_input: str,
        response_text: str,
        skill_result:  SkillResult | None,
        safety_pass:   bool,
    ) -> SessionState:
        """
        Apply all state mutations resulting from one controller cycle.

        Operations (in order):
          1. Append user turn to conversation_history (if non-empty input)
          2. Append assistant turn to conversation_history
          3. Apply OSCE field transitions based on intent
          4. Merge evaluation results (score_history, weak_areas) on session end
          5. Increment safety_event_count if output filter fired
        """
        # 1 + 2: Append conversation turns
        if student_input.strip():
            state.conversation_history.append(
                {"role": "user", "content": student_input}
            )
        state.conversation_history.append(
            {"role": "assistant", "content": response_text}
        )

        if skill_result is None:
            if not safety_pass:
                state.safety_event_count = getattr(state, "safety_event_count", 0) + 1
            return state

        # 3: OSCE field transitions
        if intent == IntentCategory.START_OSCE and skill_result.updated_case:
            # OSCE initiated: record the case, mark active, note where OSCE history begins
            state.current_case = skill_result.updated_case
            state.osce_active  = True
            state.osce_step    = skill_result.updated_osce_step  # = 1 after init
            state.mode         = "osce"
            # osce_history_start_index: index of the "start osce" user turn.
            # After appending user + assistant turns above, len = N+2 (or N+1 if
            # no user input). Point to the user turn we just appended.
            user_appended = bool(student_input.strip())
            state.osce_history_start_index = (
                len(state.conversation_history) - 2
                if user_appended else
                len(state.conversation_history) - 1
            )

        elif intent == IntentCategory.OSCE_TURN:
            state.osce_step = skill_result.updated_osce_step

        elif intent == IntentCategory.FINISH_OSCE or skill_result.session_complete:
            # 4: Capture evaluation before clearing current_case
            case_id = (state.current_case or {}).get("case_id", "unknown")
            if skill_result.evaluation:
                ev = skill_result.evaluation
                state.score_history.append({
                    "case_id":      case_id,
                    "score":        ev.get("score", 0),
                    "completed_at": datetime.now().isoformat(),
                })
                state.weak_areas = _merge_weak_areas(
                    state.weak_areas, ev.get("weak_areas", [])
                )
            # Clear all OSCE fields
            state.osce_active              = False
            state.osce_step                = 0
            state.current_case             = None
            state.mode                     = "chat"
            state.osce_history_start_index = 0

        # 5: Safety event counter
        if not safety_pass:
            state.safety_event_count = getattr(state, "safety_event_count", 0) + 1

        return state

    # ── Private: logging ──────────────────────────────────────────────────────

    def _log_turn(
        self,
        session_id:    str,
        intent_str:    str,
        skill_name:    str,
        safety_pass:   bool,
        response_text: str,
        latency_ms:    int,
    ) -> None:
        """
        Write a TurnSignal to eval_log.jsonl. Swallows all exceptions.
        Logging failure must never break the student's response.
        """
        try:
            write_turn_signal(TurnSignal(
                session_id         = session_id,
                intent_classified  = intent_str,
                skill_selected     = skill_name,
                output_safety_pass = safety_pass,
                response_length    = len(response_text),
                latency_ms         = latency_ms,
            ))
        except Exception:
            pass


# ── Module-level helper ───────────────────────────────────────────────────────

def _merge_weak_areas(existing: list[str], new: list[str]) -> list[str]:
    """
    Merge new weak areas into the existing list, deduplicate, cap at 10.

    New items are appended after existing items so the most recent pattern
    has the highest index. When over-cap, the oldest items are dropped.
    This keeps weak_areas bounded and reflecting recent performance.
    """
    combined = list(existing)
    for w in new:
        if w not in combined:
            combined.append(w)
    return combined[-10:]  # keep most recent 10


# ── Module-level singleton ────────────────────────────────────────────────────
# Used by run.py (CLI) and app.py (Gradio) in Phase 5.
# Tests instantiate their own AgentController() with isolated session stores.

controller = AgentController()


# ── Standalone import test ────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile
    import config
    import importlib

    print("=" * 60)
    print("controller.py — smoke test (no LLM, all mocked)")
    print("=" * 60)

    # Patch paths to avoid SQLite/log write issues on mounted volume in sandbox
    tmp_db  = tempfile.NamedTemporaryFile(suffix=".db",    delete=False).name
    tmp_log = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False).name
    config.AGENT_SESSION_DB_PATH        = tmp_db
    config.EVAL_LOG_PATH                = tmp_log
    config.SCOPE_CLASSIFICATION_ENABLED = False   # rule-based only

    import surgmentor.memory.db_store   as _db
    import surgmentor.evaluation.logger as _log
    importlib.reload(_db)
    importlib.reload(_log)

    _db.init_database()

    from unittest.mock import patch, MagicMock
    from surgmentor.skills.base import SkillResult

    ctrl  = AgentController(session_store=InMemorySessionStore())
    mock_result = SkillResult(response_text="Case presented.", metadata={"retrieval_hits": 1, "case_ids": ["case_1"]})

    with patch.object(ctrl._registry[IntentCategory.RETRIEVE_CASE],
                      "run", return_value=mock_result):
        response = ctrl.run("show me a case about appendicitis", "session-smoke")

    assert "Case presented." in response, f"Unexpected response: {response}"
    state = ctrl.session_store.read("session-smoke")
    assert len(state.conversation_history) == 2
    print("✅  RETRIEVE_CASE: routed, response returned, history updated")

    import os as _os
    _os.unlink(tmp_db)
    _os.unlink(tmp_log)
    print("\n✅  Smoke test PASSED")
