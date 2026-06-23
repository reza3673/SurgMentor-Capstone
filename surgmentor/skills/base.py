# surgmentor/skills/base.py
"""
Base classes and shared dataclasses for the SurgMentor skill system.

Skills are reusable, composable, stateless behavioral units (Day 3 principle).
Every skill receives a ContextBundle and returns a SkillResult. State is never
stored inside a skill — it lives in the controller's session memory.

Course concept: Agent Skills (Day 3)
Each skill:
  - Has a single responsibility (one domain, one purpose)
  - Is independently testable without the controller
  - Declares which tools it is permitted to use
  - Does not call other skills directly, except for the documented
    OSCEExaminerSkill → EvaluationSkill pipeline (Phase 3, Step 3-3)

Context engineering (Day 1): ContextBundle is NOT the full SessionState.
It is a trimmed, skill-relevant view. The controller (Phase 4, agent/context.py)
builds the bundle; it trims history, profile, and parameters to the minimum
each skill needs. This reduces token cost and hallucination risk.
"""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ── ContextBundle ─────────────────────────────────────────────────────────────

@dataclass
class ContextBundle:
    """
    Skill input. A trimmed, skill-relevant view of session state.

    Context engineering principle (Day 1): each skill receives only the fields
    it needs. The controller (Phase 4, agent/context.py) builds this bundle
    from the full SessionState, keeping only what is relevant per skill.

    Per-skill trimming (enforced in Phase 4, documented here for reference):
      OSCEExaminerSkill  → student_input, session_history, current_case, osce_step, parameters
      CaseRetrievalSkill → student_input, weak_areas, parameters
      EvaluationSkill    → session_history, current_case, student_id, parameters
      StudyPlannerSkill  → student_id, weak_areas, score_history (no session_history)

    In Phase 3 tests, ContextBundles are built manually. In Phase 4, the
    controller's context.py builds them automatically before each skill call.
    """
    student_input:    str                           # sanitized student message
    session_history:  list[dict]                    # [{"role": str, "content": str}, ...]
    current_case:     dict | None                   # loaded case metadata + text; None before init
    student_id:       str                           # stable student identifier (UUID)
    weak_areas:       list[str]                     # from past OSCE results; empty for new students
    score_history:    list[dict]                    # [{"case_id", "score", "completed_at"}, ...]
    osce_step:        int           = 0             # 0 if not in OSCE mode
    parameters:       dict          = field(default_factory=dict)  # skill-specific overrides


# ── SkillResult ───────────────────────────────────────────────────────────────

@dataclass
class SkillResult:
    """
    Skill output. Returned by every skill's run() method.

    The controller (Phase 4) reads:
      response_text     → passes to security_layer.filter_output() before returning to student
      updated_case      → writes to SessionState.current_case (OSCEExaminerSkill)
      updated_osce_step → writes to SessionState.osce_step
      session_complete  → if True, controller transitions session back to chat mode
      evaluation        → if populated, controller writes TurnSignal / SessionEvaluation to log
      metadata          → logged in TurnSignal.metadata (for observability)
    """
    response_text:      str                         # LLM-generated response (pre-security-filter)
    updated_case:       dict | None = None          # set by OSCEExaminerSkill after _init()
    updated_osce_step:  int         = 0             # incremented by OSCEExaminerSkill._turn()
    session_complete:   bool        = False         # True when OSCE session ends
    evaluation:         dict | None = None          # populated by EvaluationSkill
    metadata:           dict        = field(default_factory=dict)  # diagnostic info for logging


# ── Skill ABC ─────────────────────────────────────────────────────────────────

class Skill(ABC):
    """
    Abstract base class for all SurgMentor skills.

    Course concept: Agent Skills (Day 3).

    All concrete skills must:
      1. Inherit from Skill
      2. Implement run(bundle: ContextBundle) -> SkillResult
      3. Set class-level `name` and `description` for the controller's skill registry

    Skills MUST NOT:
      - Import from surgmentor.agent (controller layer — Phase 4)
      - Hold persistent state across calls (state lives in session memory)
      - Call security_layer.filter_output() — the controller does this (Phase 4)
        Exception: Phase 3 standalone __main__ tests may call it manually.

    Exception to the no-cross-skill-calls rule:
      OSCEExaminerSkill._finish() calls EvaluationSkill.run() directly.
      This is the documented intra-skill pipeline for the FINISH_OSCE flow.
      All other cross-skill calls are the controller's responsibility.
    """

    name: str        = ""   # human-readable; used in controller skill registry
    description: str = ""   # one-line description for README skill catalog

    @abstractmethod
    def run(self, bundle: ContextBundle) -> SkillResult:
        """
        Execute the skill.

        Receives a ContextBundle trimmed to this skill's relevant fields.
        Returns a SkillResult for the controller to process.

        Must be implemented by every concrete subclass.
        A class inheriting Skill that omits this method raises TypeError
        at instantiation time (Python ABC enforcement).
        """
        ...
