# surgmentor/skills/evaluation_skill.py
"""
EvaluationSkill — score a completed OSCE session and produce structured feedback.

This skill closes the OSCE loop. After the examiner finishes, this skill:
  1. Guards against sessions with too few student turns (participation guard)
  2. Calls DeepSeek at temperature=0.1 with a structured scoring prompt
  3. Parses the JSON response into rubric sub-scores + overall score
  4. Writes a SessionEvaluation record to eval_log.jsonl
  5. Persists the OSCE result to SQLite (osce_results table)
  6. Returns a SkillResult with human-readable feedback and the evaluation dict

Permitted tools: none (operates on conversation history already in context)
LLM role: scoring agent at temperature=0.1 for determinism

Scoring rubric (5 criteria, equal weight, averaged):
  history_taking       — structured history acquisition
  examination          — appropriate examination findings
  differential_diagnosis — reasonable differential with rationale
  management_plan      — correct immediate management steps
  communication        — professional, organised presentation

Overall score scale:
  9-10  Excellent — systematic, correct, all key points covered
  7-8   Good — mostly correct, minor omissions
  5-6   Satisfactory — correct diagnosis, some steps missed
  3-4   Poor — significant clinical gaps
  0-2   Unsatisfactory — wrong diagnosis or unsafe reasoning

Design reference (read-only): surgery-rag/osce_scorer.py
Score clamping, JSON parsing pattern, and participation guard are rewritten
from scratch here. Rubric_breakdown and study_recommendations are new.

Course concepts: Agent Skills (Day 3), Evaluation (Day 4)
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import DEEPSEEK_CHAT_MODEL, MIN_OSCE_TURNS
# clients imported lazily inside _call_scoring_llm (avoids module-level SOCKS proxy error)
from surgmentor.skills.base import ContextBundle, Skill, SkillResult
from surgmentor.evaluation.logger import SessionEvaluation, write_session_evaluation
import surgmentor.memory.db_store as db_store


# ── Constants ─────────────────────────────────────────────────────────────────

_RUBRIC_CRITERIA = [
    "history_taking",
    "examination",
    "differential_diagnosis",
    "management_plan",
    "communication",
]

_RUBRIC_DESCRIPTIONS = {
    "history_taking":        "Did the student ask structured, focused history questions?",
    "examination":           "Did the student describe appropriate examination findings?",
    "differential_diagnosis":"Did the student generate a reasonable differential with rationale?",
    "management_plan":       "Did the student propose correct immediate management steps?",
    "communication":         "Was the student's communication organised and professional?",
}

_FALLBACK_RESULT = {
    "score": 0,
    "feedback": "Session completed. Automatic scoring was unavailable for this session.",
    "rubric_breakdown": {c: 0 for c in _RUBRIC_CRITERIA},
    "strong_areas": ["Completed the case"],
    "weak_areas": ["Unable to auto-score — manual review recommended"],
    "study_recommendations": [],
    "teaching_point": "Please discuss this case with your supervisor.",
}


# ── EvaluationSkill ───────────────────────────────────────────────────────────

class EvaluationSkill(Skill):
    """
    Score a completed OSCE session.

    Called by the controller on FINISH_OSCE intent, or directly from
    OSCEExaminerSkill._finish() (the documented intra-skill pipeline).

    Input (from ContextBundle):
      session_history   full OSCE transcript (system + user + assistant turns)
      current_case      case metadata including diagnosis and key points
      student_id        for db_store.save_osce_result()
      parameters        {"case_id": str, "session_id": str}

    Output (SkillResult):
      response_text     human-readable feedback (score + narrative + weak areas)
      session_complete  always True
      evaluation        {"score", "rubric_breakdown", "weak_areas",
                         "study_recommendations", "feedback", "teaching_point",
                         "strong_areas"}
    """

    name        = "EvaluationSkill"
    description = "Score a completed OSCE session and produce rubric-mapped feedback."

    # ── Public interface ──────────────────────────────────────────────────────

    def run(self, bundle: ContextBundle) -> SkillResult:
        """
        Score the OSCE session in bundle.session_history.

        Step 1: Participation guard — return early if too few student turns.
        Step 2: Build scoring prompt from history + case metadata.
        Step 3: Call DeepSeek at temperature=0.1 (deterministic scoring).
        Step 4: Parse JSON; clamp score; fall back to safe defaults on error.
        Step 5: Persist result to SQLite and append to eval_log.jsonl.
        Step 6: Return SkillResult with formatted feedback and evaluation dict.
        """
        case_id    = bundle.parameters.get("case_id", "unknown")
        session_id = bundle.parameters.get("session_id", f"{bundle.student_id}-{case_id}")

        # ── Step 1: Participation guard ───────────────────────────────────────
        student_turns = self._count_student_turns(bundle.session_history)
        if student_turns < MIN_OSCE_TURNS:
            early_feedback = (
                f"This session could not be scored: only {student_turns} student "
                f"response(s) detected. A minimum of {MIN_OSCE_TURNS} responses is "
                f"required for a fair assessment. Please start a new case and engage "
                f"fully with the examiner."
            )
            return SkillResult(
                response_text    = early_feedback,
                session_complete = True,
                evaluation       = {
                    "score": 0,
                    "feedback": early_feedback,
                    "rubric_breakdown": {c: 0 for c in _RUBRIC_CRITERIA},
                    "strong_areas": [],
                    "weak_areas": ["Insufficient participation — case not fully completed"],
                    "study_recommendations": [],
                    "teaching_point": (
                        "Engage fully with the OSCE examiner: take a structured history, "
                        "request targeted investigations, and state your differential."
                    ),
                },
                metadata = {
                    "participation_guard_fired": True,
                    "student_turns": student_turns,
                    "min_required":  MIN_OSCE_TURNS,
                },
            )

        # ── Step 2: Build scoring prompt ──────────────────────────────────────
        prompt = self._build_scoring_prompt(bundle.session_history, bundle.current_case or {})

        # ── Step 3: Call LLM ──────────────────────────────────────────────────
        raw_result = self._call_scoring_llm(prompt)  # returns dict; never raises

        # ── Step 4: Extract and clamp ─────────────────────────────────────────
        parsed = self._parse_result(raw_result)

        # ── Step 5a: Persist to SQLite ────────────────────────────────────────
        diagnosis = (bundle.current_case or {}).get("diagnosis", "Unknown")
        try:
            db_store.register_student(bundle.student_id)
            db_store.save_osce_result(
                student_id = bundle.student_id,
                case_id    = case_id,
                diagnosis  = diagnosis,
                score      = parsed["score"],
                feedback   = parsed["feedback"],
                weak_areas = parsed["weak_areas"],            # list[str] — db_store joins internally
            )
        except Exception:
            pass  # persistence failure must not break the evaluation response

        # ── Step 5b: Write to eval_log.jsonl ──────────────────────────────────
        try:
            write_session_evaluation(SessionEvaluation(
                session_id        = session_id,
                student_id        = bundle.student_id,
                case_id           = case_id,
                osce_score        = parsed["score"],
                rubric_breakdown  = parsed["rubric_breakdown"],
                weak_areas        = parsed["weak_areas"],
                safety_events     = bundle.parameters.get("safety_events", 0),
                completion_status = "COMPLETED",
                feedback_text     = parsed["feedback"],
            ))
        except Exception:
            pass  # logger failure must not break the evaluation response

        # ── Step 6: Return ────────────────────────────────────────────────────
        response_text = self._format_feedback(parsed)
        return SkillResult(
            response_text    = response_text,
            session_complete = True,
            evaluation       = parsed,
            metadata         = {
                "student_turns": student_turns,
                "case_id":       case_id,
                "llm_call":      "evaluation",
            },
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _count_student_turns(self, history: list[dict]) -> int:
        """Count turns where role='user' and content is non-empty."""
        return sum(
            1 for msg in history
            if msg.get("role") == "user" and msg.get("content", "").strip()
        )

    def _build_scoring_prompt(self, history: list[dict], case_meta: dict) -> str:
        """Construct the structured scoring prompt sent to DeepSeek."""
        # Format transcript (skip system messages — they are examiner seeding, not dialogue)
        convo_lines = []
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "").strip()
            if role == "assistant":
                convo_lines.append(f"EXAMINER: {content}")
            elif role == "user":
                convo_lines.append(f"STUDENT: {content}")
        convo_text = "\n\n".join(convo_lines)

        rubric_block = "\n".join(
            f'        "{c}": <integer 0-10>  // {_RUBRIC_DESCRIPTIONS[c]}'
            for c in _RUBRIC_CRITERIA
        )

        return f"""You are a surgical education expert scoring an OSCE performance.

CASE INFORMATION:
- Diagnosis: {case_meta.get('diagnosis', 'Unknown')}
- Disease:   {case_meta.get('disease', case_meta.get('diagnosis', 'Unknown'))}

OSCE TRANSCRIPT:
{convo_text}

Score this student's performance and respond with ONLY a valid JSON object — no other text,
no markdown fences, no explanation before or after the JSON.

{{
    "score": <integer 0-10>,
    "feedback": "<2-3 sentence overall feedback>",
    "rubric_breakdown": {{
{rubric_block}
    }},
    "strong_areas": ["<strength>", "<another strength>"],
    "weak_areas": ["<weakness>", "<another weakness>"],
    "study_recommendations": ["<topic to review>", "<another topic>"],
    "teaching_point": "<one key clinical teaching point from this case>"
}}

SCORING GUIDE:
9-10  Excellent — systematic approach, correct diagnosis, all key points covered
7-8   Good — mostly correct, minor omissions
5-6   Satisfactory — correct diagnosis but missed important steps
3-4   Poor — significant gaps in clinical reasoning
0-2   Unsatisfactory — incorrect diagnosis or dangerous reasoning
"""

    def _call_scoring_llm(self, prompt: str) -> dict:
        """
        Call DeepSeek at temperature=0.1 and parse the JSON response.
        Returns a dict. Never raises — returns _FALLBACK_RESULT on any error.

        Separating this method makes it mockable in tests without requiring
        a live API connection.
        """
        try:
            from clients import deepseek  # lazy import — not needed until first LLM call
            response = deepseek.chat.completions.create(
                model       = DEEPSEEK_CHAT_MODEL,
                messages    = [{"role": "user", "content": prompt}],
                temperature = 0.1,
                max_tokens  = 600,
            )
            raw = response.choices[0].message.content.strip()
            # Strip optional markdown code fences (```json ... ```)
            raw = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except Exception:
            return dict(_FALLBACK_RESULT)

    def _parse_result(self, raw: dict) -> dict:
        """
        Validate and clamp all fields from the LLM response.
        Returns a safe dict regardless of what the LLM returned.
        """
        # Overall score: clamp to [0, 10]
        try:
            score = max(0, min(10, int(raw.get("score", 0))))
        except (TypeError, ValueError):
            score = 0

        # Rubric breakdown: each criterion clamped to [0, 10]
        rubric_raw = raw.get("rubric_breakdown", {})
        rubric = {}
        for c in _RUBRIC_CRITERIA:
            try:
                rubric[c] = max(0, min(10, int(rubric_raw.get(c, 0))))
            except (TypeError, ValueError):
                rubric[c] = 0

        # List fields: coerce to list[str]
        # weak_areas and strong_areas are lists in the schema, but early LLM
        # responses sometimes returned a single string (e.g., "history taking")
        # instead of a list. _safe_list() normalises both cases so that
        # db_store.log_weak_areas() and StudyPlannerSkill always receive a list.
        def _safe_list(val) -> list[str]:
            if isinstance(val, list):
                return [str(x) for x in val if x]
            return []

        return {
            "score":                score,
            "feedback":             str(raw.get("feedback", _FALLBACK_RESULT["feedback"])),
            "rubric_breakdown":     rubric,
            "strong_areas":         _safe_list(raw.get("strong_areas")),
            "weak_areas":           _safe_list(raw.get("weak_areas")),
            "study_recommendations":_safe_list(raw.get("study_recommendations")),
            "teaching_point":       str(raw.get("teaching_point", "")),
        }

    def _format_feedback(self, parsed: dict) -> str:
        """Format the evaluation result as a student-facing feedback string."""
        score = parsed["score"]
        lines = [
            f"## OSCE Score: {score}/10",
            "",
            parsed["feedback"],
        ]

        if parsed["strong_areas"]:
            lines.append("\n**Strengths:**")
            for s in parsed["strong_areas"]:
                lines.append(f"  • {s}")

        if parsed["weak_areas"]:
            lines.append("\n**Areas for improvement:**")
            for w in parsed["weak_areas"]:
                lines.append(f"  • {w}")

        if parsed["study_recommendations"]:
            lines.append("\n**Recommended study topics:**")
            for r in parsed["study_recommendations"]:
                lines.append(f"  • {r}")

        if parsed["teaching_point"]:
            lines.append(f"\n**Key teaching point:** {parsed['teaching_point']}")

        # Rubric sub-scores
        if any(v > 0 for v in parsed["rubric_breakdown"].values()):
            lines.append("\n**Rubric breakdown:**")
            for criterion, sub_score in parsed["rubric_breakdown"].items():
                label = criterion.replace("_", " ").title()
                lines.append(f"  {label}: {sub_score}/10")

        return "\n".join(lines)


# ── Standalone smoke test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    import tempfile
    import config
    import importlib

    print("=" * 60)
    print("evaluation_skill.py — smoke test (participation guard only)")
    print("=" * 60)

    # Use /tmp paths to avoid SQLite write issues on mounted volume in sandbox
    tmp_db  = tempfile.NamedTemporaryFile(suffix=".db",    delete=False).name
    tmp_log = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False).name
    config.AGENT_SESSION_DB_PATH = tmp_db
    config.EVAL_LOG_PATH         = tmp_log

    import surgmentor.memory.db_store as _db
    import surgmentor.evaluation.logger as _log
    importlib.reload(_db)
    importlib.reload(_log)

    # Re-import evaluation_skill after patching so it picks up reloaded modules
    import surgmentor.skills.evaluation_skill as _es
    importlib.reload(_es)
    _db.init_database()

    bundle = ContextBundle(
        student_input    = "",
        session_history  = [{"role": "user", "content": "hi"}],  # only 1 turn
        current_case     = {"case_id": "1", "diagnosis": "Appendicitis"},
        student_id       = "smoke-student",
        weak_areas       = [],
        score_history    = [],
        osce_step        = 0,
        parameters       = {"case_id": "1"},
    )

    skill  = _es.EvaluationSkill()
    result = skill.run(bundle)

    assert result.session_complete is True, "session_complete should be True"

    assert result.evaluation["score"] == 0, "Score should be 0 for insufficient participation"
    assert result.metadata.get("participation_guard_fired") is True
    print("\u2705  Participation guard fired correctly")
    print(f"    Response: {result.response_text[:80]}...")

    os.unlink(tmp_db)
    os.unlink(tmp_log)
    print("\n\u2705  All smoke tests PASSED")
