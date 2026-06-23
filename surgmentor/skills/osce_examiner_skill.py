# surgmentor/skills/osce_examiner_skill.py
"""
OSCEExaminerSkill — conduct a structured, multi-turn OSCE examination session.

This is the most complex skill in SurgMentor. It maintains a 3-state machine:
  init  → present the patient case and ask the first question
  turn  → respond to each student answer, advance the step counter
  finish → score the session via EvaluationSkill and return the evaluation

State is NOT held inside the skill object. All state lives in the controller's
SessionState (Phase 4). The skill reads osce_step and current_case from the
ContextBundle and writes back updated_osce_step and updated_case in SkillResult.

Dispatch logic (inside run()):
  osce_step == 0 AND current_case is None  → _init()
  parameters["finish"] == True             → _finish()
  osce_step >= MAX_OSCE_STEPS              → _finish() (auto-close long sessions)
  otherwise                                → _turn()

OSCE domains covered across turns:
  1. History taking
  2. Examination findings
  3. Investigations / differential diagnosis
  4. Management plan
  5. Communication and synthesis

Intra-skill pipeline (documented exception to the no-cross-skill-calls rule):
  _finish() calls EvaluationSkill.run() directly. This is the FINISH_OSCE pipeline.
  All other skill routing is the controller's responsibility (Phase 4).

Permitted tools: retrieval_tool.get_case_by_id, retrieval_tool.load_all_cases
LLM role: clinical surgical examiner at temperature=0.7

Design reference (read-only):
  surgery-rag/services/osce_service.py — start_case/turn/finish_case state machine
  surgery-rag/rag_engine.py — SYSTEM_PROMPT_OSCE structure
  All code written fresh; patterns informed by reference only.

Course concept: Agent Skills (Day 3) — stateful multi-turn skill with memory
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import DEEPSEEK_CHAT_MODEL, MIN_OSCE_TURNS
from surgmentor.skills.base import ContextBundle, Skill, SkillResult
from surgmentor.skills.evaluation_skill import EvaluationSkill
from surgmentor.rag import retrieval_tool   # module-level; patchable in tests


# ── Constants ─────────────────────────────────────────────────────────────────

MAX_OSCE_STEPS = 6   # auto-finish after this many student turns; configurable

SYSTEM_PROMPT_OSCE = """You are a clinical surgical examiner conducting a structured OSCE examination.
A medical student is assessing the simulated patient described in the case details below.

Your responsibilities:
1. Present the case scenario progressively — do not reveal all findings at once.
2. Cover all five OSCE domains in sequence: history, examination, investigations,
   differential diagnosis, and management plan.
3. Never confirm or deny the student's proposed diagnosis during the session.
   Maintain examiner neutrality until scoring is complete.
4. Never skip a domain — probe systematically, one question at a time.
5. If a student's answer is incomplete, acknowledge what they covered and probe for
   what is missing with a specific follow-up question.
6. Keep your responses concise (3–5 sentences). End every response with a direct
   clinical question to keep the student engaged.
7. Frame all content as educational simulation — not real patient management.

Your tone: neutral, professional, encouraging engagement without giving answers away.

IMPORTANT: You are an examiner, not a tutor. Do not teach or explain during the session.
Save teaching points for the debrief after scoring."""

_EXAMINER_FALLBACK = (
    "Thank you for your response. Could you elaborate further on the clinical findings "
    "and your reasoning? Please continue with your assessment."
)

# Distinct fallbacks so init and turn failures are distinguishable in the UI and logs.
# _EXAMINER_FALLBACK kept for backward compatibility (referenced in older tests).
_INIT_FALLBACK = (
    "⚠️ The OSCE case could not be generated — the examiner LLM did not respond. "
    "Please click Start Session again to retry."
)

_TURN_FALLBACK = (
    "⚠️ The examiner could not continue — the LLM did not respond. "
    "Please try again, or click Finish to end and score the current session."
)


def _log_llm_error(stage: str, exc: Exception) -> None:
    """
    Print a sanitized diagnostic to stderr (uvicorn terminal only).

    Reports exception type and message — no API keys, no request content,
    no stack traces are included (and none of this reaches the browser response).
    Called by _init() and _turn() to expose the root cause at the server console
    while returning a clean, user-friendly fallback to the frontend.
    """
    print(
        f"[SurgMentor OSCE] {stage} LLM failure — "
        f"{type(exc).__name__}: {exc}",
        file=sys.stderr,
        flush=True,
    )


_INIT_SEED_MESSAGE = (
    "Begin the OSCE examination. Introduce the patient scenario concisely and ask "
    "your first focused question to start the history."
)


# ── OSCEExaminerSkill ─────────────────────────────────────────────────────────

class OSCEExaminerSkill(Skill):
    """
    Conduct a multi-turn OSCE examination session.

    Course concept: Agent Skills (Day 3) — multi-step, stateful, composable.
    The skill is stateless per call; all state lives in the controller's
    SessionState and is passed in via ContextBundle each turn.

    State machine:
      run(bundle) dispatches to _init(), _turn(), or _finish()
      based on bundle.osce_step, bundle.current_case, and bundle.parameters.

    Intra-skill pipeline:
      _finish() → EvaluationSkill.run() → SkillResult with evaluation dict.
      This is the documented exception to the no-cross-skill-calls rule.
    """

    name        = "OSCEExaminerSkill"
    description = "Conduct a structured multi-turn OSCE examination session."

    # ── Public interface ──────────────────────────────────────────────────────

    def run(self, bundle: ContextBundle) -> SkillResult:
        """
        Dispatch to the correct OSCE phase based on session state.

        Dispatch rules (checked in priority order):
          1. parameters["finish"] == True  → _finish() (explicit end signal)
          2. osce_step >= MAX_OSCE_STEPS    → _finish() (auto-close)
          3. osce_step == 0 and current_case is None → _init() (fresh session)
          4. otherwise → _turn() (mid-session student response)
        """
        # Rule 1 & 2: finish triggers
        if bundle.parameters.get("finish") or bundle.osce_step >= MAX_OSCE_STEPS:
            return self._finish(bundle)

        # Rule 3: fresh session — no case loaded yet
        if bundle.osce_step == 0 and bundle.current_case is None:
            return self._init(bundle)

        # Rule 4: mid-session turn
        return self._turn(bundle)

    # ── Private: init ─────────────────────────────────────────────────────────

    def _init(self, bundle: ContextBundle) -> SkillResult:
        """
        Load a case and generate the examiner's opening statement.

        Case selection priority:
          1. bundle.parameters["case_id"] → retrieval_tool.get_case_by_id()
          2. Otherwise → retrieval_tool.load_all_cases() filtered by score_history
             (avoids repeating a case the student has already attempted)

        Returns SkillResult with updated_case populated and updated_osce_step=1.
        """
        case_id = bundle.parameters.get("case_id")
        if case_id:
            raw = retrieval_tool.get_case_by_id(str(case_id))
            if raw is not None:
                case_dict = self._case_result_to_dict(raw)
            else:
                # Requested ID not found — fall back to unseen case selection
                case_dict = self._pick_unseen_case(bundle.score_history)
        else:
            case_dict = self._pick_unseen_case(bundle.score_history)

        case_text = case_dict.get("text", "")
        try:
            intro_text = self._call_examiner_llm([
                {"role": "system",
                 "content": SYSTEM_PROMPT_OSCE + "\n\nCASE DETAILS:\n" + case_text},
                {"role": "user", "content": _INIT_SEED_MESSAGE},
            ])
        except Exception as exc:
            _log_llm_error("_init", exc)
            intro_text = _INIT_FALLBACK

        return SkillResult(
            response_text     = intro_text,
            updated_case      = case_dict,
            updated_osce_step = 1,
            metadata          = {
                "stage":   "init",
                "case_id": case_dict.get("case_id", "unknown"),
            },
        )

    # ── Private: turn ─────────────────────────────────────────────────────────

    def _turn(self, bundle: ContextBundle) -> SkillResult:
        """
        Respond to the student's answer and advance the OSCE step.

        The full session history (including the case introduction from _init)
        is passed to the LLM so the examiner maintains continuity across turns.

        RAG is intentionally skipped here. Unlike CaseRetrievalSkill (which
        searches ChromaDB on every query), the OSCE session uses only the case
        context seeded in _init(). Retrieving additional cases mid-session would
        contaminate the examination — the examiner must work from a single,
        fixed patient scenario throughout the session.

        Returns SkillResult with updated_osce_step incremented by 1.
        """
        case_text = (bundle.current_case or {}).get("text", "")
        messages  = [
            {"role": "system",
             "content": SYSTEM_PROMPT_OSCE + "\n\nCASE DETAILS:\n" + case_text},
            *bundle.session_history,
            {"role": "user", "content": bundle.student_input},
        ]
        try:
            response_text = self._call_examiner_llm(messages)
        except Exception as exc:
            _log_llm_error("_turn", exc)
            response_text = _TURN_FALLBACK

        return SkillResult(
            response_text     = response_text,
            updated_osce_step = bundle.osce_step + 1,
            metadata          = {
                "stage":     "turn",
                "osce_step": bundle.osce_step,
            },
        )

    # ── Private: finish ───────────────────────────────────────────────────────

    def _finish(self, bundle: ContextBundle) -> SkillResult:
        """
        Close the OSCE session and score it via EvaluationSkill.

        Builds an evaluation ContextBundle from the current session state and
        delegates to EvaluationSkill.run(). This is the intra-skill pipeline
        documented in the Skill ABC.

        Returns SkillResult with session_complete=True and evaluation dict
        populated from the EvaluationSkill output.
        """
        case_id = (bundle.current_case or {}).get("case_id", "unknown")
        eval_bundle = ContextBundle(
            student_input    = "",
            session_history  = bundle.session_history,
            current_case     = bundle.current_case,
            student_id       = bundle.student_id,
            weak_areas       = bundle.weak_areas,
            score_history    = bundle.score_history,
            osce_step        = 0,
            parameters       = {
                "case_id":       case_id,
                "session_id":    bundle.parameters.get("session_id",
                                    f"{bundle.student_id}-{case_id}"),
                "safety_events": bundle.parameters.get("safety_events", 0),
            },
        )
        evaluation_result = EvaluationSkill().run(eval_bundle)

        return SkillResult(
            response_text     = evaluation_result.response_text,
            session_complete  = True,
            evaluation        = evaluation_result.evaluation,
            updated_osce_step = 0,
            metadata          = {"stage": "finish", "case_id": case_id},
        )

    # ── Private: LLM call ─────────────────────────────────────────────────────

    def _call_examiner_llm(self, messages: list[dict]) -> str:
        """
        Call DeepSeek and return the examiner's response text.

        temperature=0.7 — higher than EvaluationSkill (0.1) because natural
        examiner dialogue benefits from some variation across sessions.

        Separating this method makes it mockable in tests without requiring
        a live API connection.

        Raises on any exception — callers (_init, _turn) catch the error,
        call _log_llm_error() to print a sanitized diagnostic to stderr, and
        return their own context-specific fallback string to the frontend.
        This makes _init failures and _turn failures distinguishable, and ensures
        the exception type and message are always visible in the uvicorn terminal.
        """
        from clients import deepseek  # lazy: avoids module-level SOCKS proxy error
        response = deepseek.chat.completions.create(
            model       = DEEPSEEK_CHAT_MODEL,
            messages    = messages,
            temperature = 0.7,
            max_tokens  = 400,
        )
        return response.choices[0].message.content.strip()

    # ── Private: case utilities ───────────────────────────────────────────────

    def _pick_unseen_case(self, score_history: list[dict]) -> dict:
        """
        Select the first case not already in score_history.
        Falls back to the first case overall if all cases have been seen.

        Uses load_all_cases() which reads data/prepared_cases.json
        (sandbox-safe — no ChromaDB or API call required).
        """
        all_cases = retrieval_tool.load_all_cases()
        if not all_cases:
            return {
                "case_id":   "unknown",
                "text":      "No cases available in the database.",
                "diagnosis": "Unknown",
                "disease":   "Unknown",
            }

        # Collect IDs already attempted (both numeric "1" and doc-id "case_1" forms)
        seen_ids: set[str] = set()
        for r in score_history:
            cid = str(r.get("case_id", ""))
            seen_ids.add(cid)
            seen_ids.add(f"case_{cid}")

        unseen = [c for c in all_cases
                  if str(c.get("metadata", {}).get("case_id", c.get("id", "")))
                  not in seen_ids
                  and str(c.get("id", "")) not in seen_ids]

        raw = (unseen[0] if unseen else all_cases[0])
        return self._normalize_case(raw)

    def _normalize_case(self, raw: dict) -> dict:
        """
        Normalize a dict from load_all_cases() to the standard case shape.

        load_all_cases() returns: {"id": str, "text": str, "metadata": dict}
        Standard shape:           {"case_id": str, "text": str,
                                   "diagnosis": str, "disease": str, ...metadata}
        """
        meta = raw.get("metadata", {})
        result = dict(meta)                             # copy all metadata fields
        result["case_id"]   = meta.get("case_id", raw.get("id", "unknown"))
        result["doc_id"]    = raw.get("id", "")        # preserve ChromaDB doc ID
        result["text"]      = raw.get("text", "")
        result.setdefault("diagnosis", "Unknown")
        result.setdefault("disease",   result["diagnosis"])
        return result

    def _case_result_to_dict(self, case_result) -> dict:
        """
        Convert a CaseResult dataclass (from retrieval_tool.get_case_by_id)
        to the standard case dict shape.

        CaseResult fields: case_id (doc ID), text, metadata, similarity
        """
        meta = case_result.metadata if case_result.metadata else {}
        result = dict(meta)
        result["case_id"] = meta.get("case_id", case_result.case_id)
        result["doc_id"]  = case_result.case_id
        result["text"]    = case_result.text
        result.setdefault("diagnosis", "Unknown")
        result.setdefault("disease",   result["diagnosis"])
        return result


# ── Standalone import test ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("osce_examiner_skill.py — import test")
    print("=" * 60)

    skill = OSCEExaminerSkill()
    assert isinstance(skill, Skill), "Must be a Skill instance"
    assert skill.name == "OSCEExaminerSkill"
    assert skill.description

    print(f"✅  OSCEExaminerSkill instantiated: name='{skill.name}'")
    print(f"    MAX_OSCE_STEPS = {MAX_OSCE_STEPS}")
    print(f"    MIN_OSCE_TURNS = {MIN_OSCE_TURNS}")
    print("\n✅  Import test PASSED (no LLM or ChromaDB calls made)")
