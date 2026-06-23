# surgmentor/skills/study_planner_skill.py
"""
StudyPlannerSkill — generate a personalised remediation plan from past performance.

This skill reads the student's entire OSCE history from SQLite and calls DeepSeek
to synthesise an ordered study plan. The LLM cannot invent weaknesses not present
in the student's actual history — this is the grounding constraint enforced by the
system prompt and the format_student_data() helper, which presents only what is
in the database.

Onboarding guard: if the student has no history (new user, or unknown student_id),
the skill returns a welcoming onboarding message without calling the LLM.

Input (from ContextBundle):
  student_id    for db_store.get_student_stats()
  weak_areas    from session state (may differ from DB if session not yet saved)
  score_history from session state (may differ from DB — latest session not yet written)
  parameters    (unused by this skill; reserved for future options)

Output (SkillResult):
  response_text  formatted study plan or onboarding message
  metadata       {"avg_score": float, "weak_areas_count": int, "total_cases": int,
                  "new_student": bool}

Permitted tools: db_store.get_student_stats
LLM role: educational advisor at temperature=0.5
  (higher than evaluation scoring, lower than examiner — planning benefits from
  moderate creativity without hallucinating fabricated student performance data)

Course concept: Agent Skills (Day 3)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import DEEPSEEK_CHAT_MODEL
from surgmentor.skills.base import ContextBundle, Skill, SkillResult
import surgmentor.memory.db_store as db_store      # module-level; patchable in tests


# ── System prompts ────────────────────────────────────────────────────────────

SYSTEM_PROMPT_PLANNER = """You are a surgical education advisor reviewing a medical \
student's OSCE performance data.

Generate a personalised, structured study plan based ONLY on the performance data provided.

Your plan must:
1. Identify the 2–3 highest-priority weak areas (most frequent occurrences, lowest sub-scores).
2. Suggest specific surgical topics to review for each weak area.
3. Recommend a logical study sequence (foundational concepts before advanced applications).
4. Include one concrete next action the student can take immediately
   (e.g., "Start an OSCE session on Acute Appendicitis").
5. End with a brief, constructive motivational message.

CONSTRAINTS:
- Base your plan ONLY on the data provided. Do not mention topics or weaknesses
  not present in the student's performance record.
- Be concise and actionable. The student needs a clear plan, not a lecture.
- Frame recommendations constructively — avoid language that feels punitive about low scores."""

_ONBOARDING_MESSAGE = """\
**Welcome to SurgMentor!**

To receive a personalised study plan, complete at least one OSCE session first.
Your plan will be tailored to your specific performance patterns — weak areas, \
score trends, and topics you have already covered.

**Get started:** type **start OSCE** to begin your first examination session."""

_PLANNER_FALLBACK = (
    "I encountered an issue generating your study plan. "
    "Please try again in a moment."
)


# ── StudyPlannerSkill ─────────────────────────────────────────────────────────

class StudyPlannerSkill(Skill):
    """
    Generate a personalised study plan from the student's OSCE history.

    Course concept: Agent Skills (Day 3).

    The plan is grounded in actual student performance data from SQLite.
    The LLM synthesises the data into a readable plan; it cannot invent
    weaknesses not present in the student's record.

    Onboarding guard: if the student has no history, returns a welcoming
    message without calling the LLM (no cost, instant response).
    """

    name        = "StudyPlannerSkill"
    description = "Generate a personalised remediation study plan from past performance."

    # ── Public interface ──────────────────────────────────────────────────────

    def run(self, bundle: ContextBundle) -> SkillResult:
        """
        Generate a study plan for the student.

        Step 1: Fetch performance data from SQLite.
        Step 2: Onboarding guard — if no history, return welcome message.
        Step 3: Format student data as a structured text block.
        Step 4: Call DeepSeek at temperature=0.5 to generate the plan.
        Step 5: Return SkillResult with formatted plan and diagnostic metadata.
        """
        # ── Step 1: Fetch stats ───────────────────────────────────────────────
        stats = db_store.get_student_stats(bundle.student_id)

        # ── Step 2: Onboarding guard ──────────────────────────────────────────
        if not stats:
            return SkillResult(
                response_text = _ONBOARDING_MESSAGE,
                metadata      = {
                    "new_student":     True,
                    "avg_score":       None,
                    "weak_areas_count": 0,
                    "total_cases":     0,
                },
            )

        # ── Step 3: Format student data ───────────────────────────────────────
        student_data_text = self._format_student_data(stats)

        # ── Step 4: LLM call ──────────────────────────────────────────────────
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_PLANNER},
            {"role": "user",   "content": student_data_text},
        ]
        response_text = self._call_planner_llm(messages)

        # ── Step 5: Return ────────────────────────────────────────────────────
        osce_data  = stats.get("osce", {})
        weak_areas = stats.get("weak_areas", [])
        return SkillResult(
            response_text = response_text,
            metadata      = {
                "new_student":      False,
                "avg_score":        osce_data.get("avg_score"),
                "weak_areas_count": len(weak_areas),
                "total_cases":      osce_data.get("total_osce", 0),
            },
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _format_student_data(self, stats: dict) -> str:
        """
        Convert get_student_stats() output to a readable LLM-friendly block.

        Example output:
          Student Performance Summary
          ===========================
          Sessions completed: 8
          OSCE cases attempted: 4
          Average OSCE score: 6.5 / 10
          Best score:  8  (Acute appendicitis)
          Worst score: 5  (Cholecystitis)

          Weak areas (by frequency):
            1. History taking (3 occurrences)
            2. Management plan (2 occurrences)

          Topics studied: Appendicitis, Cholecystitis, Bowel obstruction
          Unique diagnoses encountered: 3
        """
        osce      = stats.get("osce", {})
        sessions  = stats.get("sessions", {})
        recent    = stats.get("recent_osce", [])
        topics    = stats.get("top_topics", [])
        diagnoses = stats.get("unique_diagnoses", [])
        weak      = stats.get("weak_areas", [])  # list of (topic, count)

        lines = [
            "Student Performance Summary",
            "===========================",
            f"Sessions completed:    {sessions.get('total', 0)}",
            f"OSCE cases attempted:  {osce.get('total_osce', 0)}",
            f"Average OSCE score:    {osce.get('avg_score', 0):.2f} / 10",
            f"Best score:            {osce.get('best_score', 0)}",
            f"Worst score:           {osce.get('worst_score', 0)}",
        ]

        if recent:
            lines.append("")
            lines.append("Recent OSCE results (latest first):")
            for r in recent[:5]:
                diagnosis = r.get("diagnosis", "Unknown")
                score     = r.get("score", "?")
                date      = str(r.get("completed_at", ""))[:10]
                lines.append(f"  {date}  {diagnosis}: {score}/10")

        if weak:
            lines.append("")
            lines.append("Weak areas (by frequency):")
            for i, (topic, count) in enumerate(weak[:5], 1):
                lines.append(f"  {i}. {topic} ({count} occurrence{'s' if count != 1 else ''})")

        if topics:
            lines.append("")
            lines.append(f"Topics studied: {', '.join(str(t) for t in topics[:10])}")

        if diagnoses:
            lines.append(f"Unique diagnoses encountered: {len(diagnoses)}")

        return "\n".join(lines)

    def _call_planner_llm(self, messages: list[dict]) -> str:
        """
        Call DeepSeek at temperature=0.5 and return the study plan text.

        temperature=0.5: moderate creativity for natural plan language,
        lower than the examiner (0.7) to avoid inventing student performance data,
        higher than scoring (0.1) because planning benefits from varied phrasing.

        Lazy import of clients avoids module-level SOCKS proxy error in sandbox.
        Returns the fallback string on any exception.
        """
        try:
            from clients import deepseek  # lazy: not needed until first LLM call
            response = deepseek.chat.completions.create(
                model       = DEEPSEEK_CHAT_MODEL,
                messages    = messages,
                temperature = 0.5,
                max_tokens  = 600,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return _PLANNER_FALLBACK


# ── Standalone import test ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("study_planner_skill.py — import test")
    print("=" * 60)
    from surgmentor.skills.base import Skill
    skill = StudyPlannerSkill()
    assert isinstance(skill, Skill)
    assert skill.name == "StudyPlannerSkill"
    print(f"✅  StudyPlannerSkill instantiated: name='{skill.name}'")

    # Smoke test: format_student_data with minimal stats
    sample_stats = {
        "user": {"student_id": "s1", "display_name": "Alice"},
        "sessions": {"total": 3},
        "osce": {"total_osce": 2, "avg_score": 6.5, "best_score": 8, "worst_score": 5},
        "recent_osce": [{"diagnosis": "Appendicitis", "score": 8, "completed_at": "2026-06-20"}],
        "top_topics": ["Appendicitis", "Cholecystitis"],
        "unique_diagnoses": ["Appendicitis", "Cholecystitis"],
        "weak_areas": [("History taking", 3), ("Management plan", 2)],
    }
    text = skill._format_student_data(sample_stats)
    assert "Weak areas" in text
    assert "History taking" in text
    print("✅  _format_student_data: OK")
    print("\n✅  Import test PASSED (no LLM or ChromaDB calls made)")
