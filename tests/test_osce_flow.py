# tests/test_osce_flow.py
"""
OSCE flow tests — Phase 3A subset.

Phase 3A covers:
  Test 1 — ContextBundle and SkillResult dataclasses instantiate correctly
  Test 2 — Skill ABC enforcement (missing run() → TypeError)
  Test 3 — EvaluationSkill participation guard (no LLM call)
  Test 4 — EvaluationSkill invalid JSON fallback (mocked LLM)

Phase 3B tests (require live LLM + ChromaDB) will be added in a later
step and are guarded by @unittest.skipIf(os.getenv("CI_NO_LLM"), ...).

Usage:
  # Sandbox-safe (no network):
  CI_NO_LLM=1 python -m unittest tests/test_osce_flow.py

  # Full suite (native machine, requires API keys and populated ChromaDB):
  python -m unittest tests/test_osce_flow.py
"""

import importlib
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Disable LLM scope classification (security layer) during tests ─────────────
import config
config.SCOPE_CLASSIFICATION_ENABLED = False

# ── Patch SQLite and eval log to /tmp paths before any module-level DB init ───
_tmp_db  = tempfile.NamedTemporaryFile(suffix=".db",    delete=False).name
_tmp_log = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False).name
config.AGENT_SESSION_DB_PATH = _tmp_db
config.EVAL_LOG_PATH         = _tmp_log

# ── Now import modules that read config at module level ───────────────────────
import surgmentor.memory.db_store as db_store_module
import surgmentor.evaluation.logger as logger_module
importlib.reload(db_store_module)
importlib.reload(logger_module)

from surgmentor.skills.base import ContextBundle, Skill, SkillResult

# Re-import evaluation_skill after patching so it picks up reloaded db_store/logger
import surgmentor.skills.evaluation_skill as es_module
importlib.reload(es_module)
EvaluationSkill = es_module.EvaluationSkill

# Phase 3B: OSCEExaminerSkill
import surgmentor.skills.osce_examiner_skill as oe_module
importlib.reload(oe_module)
OSCEExaminerSkill = oe_module.OSCEExaminerSkill
MAX_OSCE_STEPS    = oe_module.MAX_OSCE_STEPS

# Phase 3C: CaseRetrievalSkill + StudyPlannerSkill
import surgmentor.skills.case_retrieval_skill as cr_module
import surgmentor.skills.study_planner_skill  as sp_module
importlib.reload(cr_module)
importlib.reload(sp_module)
CaseRetrievalSkill = cr_module.CaseRetrievalSkill
StudyPlannerSkill  = sp_module.StudyPlannerSkill
from surgmentor.rag.retrieval_tool import CaseResult

# Initialise the test database
db_store_module.init_database()

_LIVE_LLM = not os.getenv("CI_NO_LLM")


# ── Helper: minimal ContextBundle ─────────────────────────────────────────────

def _make_bundle(**kwargs) -> ContextBundle:
    """Return a ContextBundle with sensible defaults; override with kwargs."""
    defaults = dict(
        student_input    = "",
        session_history  = [],
        current_case     = {"case_id": "1", "diagnosis": "Acute appendicitis",
                             "disease": "Appendicitis"},
        student_id       = "test-student-001",
        weak_areas       = [],
        score_history    = [],
        osce_step        = 0,
        parameters       = {"case_id": "1", "session_id": "test-session-001"},
    )
    defaults.update(kwargs)
    return ContextBundle(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — ContextBundle and SkillResult dataclasses
# ─────────────────────────────────────────────────────────────────────────────

class Test01DataclassTypes(unittest.TestCase):
    """Verify ContextBundle and SkillResult instantiate with correct types."""

    def test_context_bundle_minimal(self):
        """ContextBundle with all fields should instantiate without error."""
        bundle = _make_bundle()
        self.assertIsInstance(bundle, ContextBundle)
        self.assertIsInstance(bundle.student_input,   str)
        self.assertIsInstance(bundle.session_history, list)
        self.assertIsNone(bundle.current_case if bundle.current_case is None else None,
                          "current_case should be dict or None")
        self.assertIsInstance(bundle.student_id,    str)
        self.assertIsInstance(bundle.weak_areas,    list)
        self.assertIsInstance(bundle.score_history, list)
        self.assertIsInstance(bundle.osce_step,     int)
        self.assertIsInstance(bundle.parameters,    dict)

    def test_context_bundle_none_case(self):
        """current_case=None should be accepted."""
        bundle = _make_bundle(current_case=None)
        self.assertIsNone(bundle.current_case)

    def test_context_bundle_defaults(self):
        """osce_step defaults to 0; parameters defaults to {}."""
        bundle = ContextBundle(
            student_input    = "test",
            session_history  = [],
            current_case     = None,
            student_id       = "s1",
            weak_areas       = [],
            score_history    = [],
        )
        self.assertEqual(bundle.osce_step, 0)
        self.assertEqual(bundle.parameters, {})

    def test_skill_result_minimal(self):
        """SkillResult with only response_text should use correct defaults."""
        result = SkillResult(response_text="hello")
        self.assertEqual(result.response_text,    "hello")
        self.assertIsNone(result.updated_case)
        self.assertEqual(result.updated_osce_step, 0)
        self.assertFalse(result.session_complete)
        self.assertIsNone(result.evaluation)
        self.assertEqual(result.metadata, {})

    def test_skill_result_all_fields(self):
        """SkillResult should accept all fields correctly."""
        result = SkillResult(
            response_text    = "Score: 8/10",
            updated_case     = {"case_id": "2"},
            updated_osce_step = 3,
            session_complete = True,
            evaluation       = {"score": 8},
            metadata         = {"latency_ms": 1200},
        )
        self.assertEqual(result.updated_osce_step, 3)
        self.assertTrue(result.session_complete)
        self.assertEqual(result.evaluation["score"], 8)
        self.assertEqual(result.metadata["latency_ms"], 1200)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — Skill ABC enforcement
# ─────────────────────────────────────────────────────────────────────────────

class Test02SkillABC(unittest.TestCase):
    """Verify the Skill ABC is enforced at instantiation time."""

    def test_concrete_skill_requires_run(self):
        """
        A subclass of Skill that does not implement run() must raise TypeError
        when instantiated. Python's ABCMeta enforces this automatically.
        """
        class IncompleteSkill(Skill):
            name        = "IncompleteSkill"
            description = "This skill is missing run()"
            # run() deliberately omitted

        with self.assertRaises(TypeError):
            _ = IncompleteSkill()

    def test_concrete_skill_with_run_is_valid(self):
        """A subclass that implements run() should instantiate without error."""
        class ValidSkill(Skill):
            name        = "ValidSkill"
            description = "A minimal valid skill"

            def run(self, bundle: ContextBundle) -> SkillResult:
                return SkillResult(response_text="ok")

        skill = ValidSkill()
        self.assertIsInstance(skill, Skill)
        result = skill.run(_make_bundle())
        self.assertEqual(result.response_text, "ok")

    def test_evaluation_skill_is_instance_of_skill(self):
        """EvaluationSkill must be an instance of the Skill ABC."""
        skill = EvaluationSkill()
        self.assertIsInstance(skill, Skill)

    def test_evaluation_skill_has_name_and_description(self):
        """EvaluationSkill must declare non-empty name and description."""
        skill = EvaluationSkill()
        self.assertIsInstance(skill.name, str)
        self.assertGreater(len(skill.name), 0)
        self.assertIsInstance(skill.description, str)
        self.assertGreater(len(skill.description), 0)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — EvaluationSkill participation guard
# ─────────────────────────────────────────────────────────────────────────────

class Test03ParticipationGuard(unittest.TestCase):
    """Verify the participation guard fires correctly and does not call the LLM."""

    def setUp(self):
        self.skill = EvaluationSkill()

    def test_participation_guard_zero_turns(self):
        """Session with no student turns should return early with score=0."""
        bundle = _make_bundle(session_history=[
            {"role": "assistant", "content": "Welcome. What is the chief complaint?"}
        ])
        with patch.object(self.skill, "_call_scoring_llm") as mock_llm:
            result = self.skill.run(bundle)
        mock_llm.assert_not_called()
        self.assertTrue(result.session_complete)
        self.assertEqual(result.evaluation["score"], 0)
        self.assertTrue(result.metadata.get("participation_guard_fired"))

    def test_participation_guard_one_turn(self):
        """Session with 1 student turn (below MIN_OSCE_TURNS) should return early."""
        bundle = _make_bundle(session_history=[
            {"role": "assistant", "content": "Describe the patient."},
            {"role": "user",      "content": "The patient has abdominal pain."},
        ])
        with patch.object(self.skill, "_call_scoring_llm") as mock_llm:
            result = self.skill.run(bundle)
        mock_llm.assert_not_called()
        self.assertTrue(result.session_complete)
        self.assertEqual(result.evaluation["score"], 0)

    def test_participation_guard_threshold(self):
        """
        Session with exactly MIN_OSCE_TURNS student turns should NOT fire the guard.
        The LLM call should be attempted (it is mocked to return fallback here).
        """
        from config import MIN_OSCE_TURNS
        history = [
            {"role": "assistant", "content": f"Question {i}"}
            for i in range(MIN_OSCE_TURNS)
        ] + [
            {"role": "user", "content": f"Answer {i}"}
            for i in range(MIN_OSCE_TURNS)
        ]
        # Return a valid minimal result from the mocked LLM
        mock_return = {
            "score": 6,
            "feedback": "Good.",
            "rubric_breakdown": {c: 6 for c in es_module._RUBRIC_CRITERIA},
            "strong_areas": ["History"],
            "weak_areas": [],
            "study_recommendations": [],
            "teaching_point": "Keep it up.",
        }
        bundle = _make_bundle(session_history=history)
        with patch.object(self.skill, "_call_scoring_llm", return_value=mock_return) as mock_llm:
            result = self.skill.run(bundle)
        mock_llm.assert_called_once()
        self.assertFalse(result.metadata.get("participation_guard_fired", False))
        self.assertEqual(result.evaluation["score"], 6)

    def test_participation_guard_ignores_system_messages(self):
        """System messages must not be counted as student turns."""
        bundle = _make_bundle(session_history=[
            {"role": "system", "content": "You are an examiner."},
            {"role": "system", "content": "Case: abdominal pain."},
            {"role": "user",   "content": ""},   # empty user turn — should not count
        ])
        with patch.object(self.skill, "_call_scoring_llm") as mock_llm:
            result = self.skill.run(bundle)
        mock_llm.assert_not_called()
        self.assertTrue(result.metadata.get("participation_guard_fired"))


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — EvaluationSkill invalid JSON fallback
# ─────────────────────────────────────────────────────────────────────────────

class Test04JsonFallback(unittest.TestCase):
    """Verify EvaluationSkill handles LLM non-JSON gracefully."""

    def setUp(self):
        self.skill = EvaluationSkill()
        from config import MIN_OSCE_TURNS
        # Build a history with enough student turns to pass the guard
        self.valid_history = (
            [{"role": "assistant", "content": f"Q{i}"} for i in range(MIN_OSCE_TURNS)] +
            [{"role": "user",      "content": f"A{i}"} for i in range(MIN_OSCE_TURNS)]
        )

    def test_non_json_response_returns_fallback(self):
        """
        When _call_scoring_llm returns the fallback dict (simulating a JSON parse
        failure inside the method), run() should still return a valid SkillResult.
        """
        from surgmentor.skills.evaluation_skill import _FALLBACK_RESULT
        bundle = _make_bundle(session_history=self.valid_history)
        with patch.object(self.skill, "_call_scoring_llm", return_value=dict(_FALLBACK_RESULT)):
            result = self.skill.run(bundle)
        self.assertIsNotNone(result)
        self.assertTrue(result.session_complete)
        self.assertIsInstance(result.evaluation["score"], int)
        self.assertGreaterEqual(result.evaluation["score"], 0)
        self.assertLessEqual(result.evaluation["score"], 10)

    def test_empty_dict_response_uses_defaults(self):
        """Empty dict from LLM should not crash; score defaults to 0."""
        bundle = _make_bundle(session_history=self.valid_history)
        with patch.object(self.skill, "_call_scoring_llm", return_value={}):
            result = self.skill.run(bundle)
        self.assertTrue(result.session_complete)
        self.assertEqual(result.evaluation["score"], 0)
        self.assertIsInstance(result.evaluation["rubric_breakdown"], dict)

    def test_invalid_score_type_is_clamped(self):
        """Non-integer score from LLM should be coerced or default to 0."""
        bundle = _make_bundle(session_history=self.valid_history)
        mock_return = {
            "score": "excellent",   # string instead of int
            "feedback": "Good.",
            "rubric_breakdown": {},
            "strong_areas": [],
            "weak_areas": [],
            "study_recommendations": [],
            "teaching_point": "",
        }
        with patch.object(self.skill, "_call_scoring_llm", return_value=mock_return):
            result = self.skill.run(bundle)
        self.assertIsInstance(result.evaluation["score"], int)
        self.assertEqual(result.evaluation["score"], 0)  # int("excellent") fails → 0

    def test_score_clamped_above_ten(self):
        """Score >10 should be clamped to 10."""
        bundle = _make_bundle(session_history=self.valid_history)
        mock_return = {
            "score": 15,
            "feedback": "Extraordinary.",
            "rubric_breakdown": {c: 10 for c in es_module._RUBRIC_CRITERIA},
            "strong_areas": [],
            "weak_areas": [],
            "study_recommendations": [],
            "teaching_point": "",
        }
        with patch.object(self.skill, "_call_scoring_llm", return_value=mock_return):
            result = self.skill.run(bundle)
        self.assertEqual(result.evaluation["score"], 10)

    def test_score_clamped_below_zero(self):
        """Score <0 should be clamped to 0."""
        bundle = _make_bundle(session_history=self.valid_history)
        mock_return = {
            "score": -3,
            "feedback": "No attempt.",
            "rubric_breakdown": {c: 0 for c in es_module._RUBRIC_CRITERIA},
            "strong_areas": [],
            "weak_areas": [],
            "study_recommendations": [],
            "teaching_point": "",
        }
        with patch.object(self.skill, "_call_scoring_llm", return_value=mock_return):
            result = self.skill.run(bundle)
        self.assertEqual(result.evaluation["score"], 0)

    def test_response_text_is_formatted_string(self):
        """response_text should always be a non-empty string."""
        bundle = _make_bundle(session_history=self.valid_history)
        mock_return = {
            "score": 7,
            "feedback": "Well done.",
            "rubric_breakdown": {c: 7 for c in es_module._RUBRIC_CRITERIA},
            "strong_areas": ["Systematic history"],
            "weak_areas": ["Management plan"],
            "study_recommendations": ["Appendicitis management"],
            "teaching_point": "Always request WBC count.",
        }
        with patch.object(self.skill, "_call_scoring_llm", return_value=mock_return):
            result = self.skill.run(bundle)
        self.assertIsInstance(result.response_text, str)
        self.assertIn("7", result.response_text)   # score should appear
        self.assertIn("Well done", result.response_text)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3B placeholders (live LLM tests — added in Phase 3B)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — OSCEExaminerSkill: dispatch and state transitions (sandbox-safe)
# ─────────────────────────────────────────────────────────────────────────────

class Test06OSCEExaminerSkill(unittest.TestCase):
    """
    Sandbox-safe tests for OSCEExaminerSkill.

    All tests mock _call_examiner_llm to avoid DeepSeek calls.
    Tests that use case selection mock retrieval_tool.get_case_by_id;
    tests that exercise _pick_unseen_case allow load_all_cases() to run
    for real (reads data/prepared_cases.json — no ChromaDB or API call).
    Tests that exercise _finish mock EvaluationSkill entirely.
    """

    _MOCK_LLM_RESPONSE = "What brings this patient in today? Please take a focused history."
    _MOCK_CASE = {
        "case_id":   "1",
        "doc_id":    "case_1",
        "text":      "A 22-year-old female presents with 24-hour right iliac fossa pain.",
        "diagnosis": "Acute appendicitis",
        "disease":   "Acute appendicitis with appendicular mass",
    }
    _MOCK_EVALUATION = {
        "score": 7,
        "feedback": "Good systematic approach.",
        "rubric_breakdown": {c: 7 for c in es_module._RUBRIC_CRITERIA},
        "strong_areas": ["History taking"],
        "weak_areas": ["Management plan"],
        "study_recommendations": ["Appendicitis management"],
        "teaching_point": "Always request WBC and CRP.",
    }

    def setUp(self):
        self.skill = OSCEExaminerSkill()

    def _bundle(self, **kwargs) -> ContextBundle:
        """Base bundle for a mid-session turn (step=2, case loaded)."""
        defaults = dict(
            student_input    = "The patient has RIF pain radiating to the umbilicus.",
            session_history  = [
                {"role": "assistant", "content": "Welcome. Please begin with history."},
                {"role": "user",      "content": "When did the pain start?"},
                {"role": "assistant", "content": "The pain started 24 hours ago."},
            ],
            current_case     = self._MOCK_CASE,
            student_id       = "test-student-003",
            weak_areas       = [],
            score_history    = [],
            osce_step        = 2,
            parameters       = {"case_id": "1", "session_id": "osce-test-003"},
        )
        defaults.update(kwargs)
        return ContextBundle(**defaults)

    # ── isinstance ────────────────────────────────────────────────────────────

    def test_is_instance_of_skill(self):
        """OSCEExaminerSkill must be an instance of the Skill ABC."""
        self.assertIsInstance(self.skill, Skill)

    def test_has_name_and_description(self):
        """OSCEExaminerSkill must declare non-empty name and description."""
        self.assertEqual(self.skill.name, "OSCEExaminerSkill")
        self.assertGreater(len(self.skill.description), 0)

    # ── Dispatch: init path ───────────────────────────────────────────────────

    def test_dispatch_to_init_when_step_zero_no_case(self):
        """
        osce_step=0 AND current_case=None → run() dispatches to _init().
        Verified by checking updated_osce_step=1 and updated_case is populated.
        """
        bundle = self._bundle(osce_step=0, current_case=None,
                              parameters={"case_id": "1"})
        # Mock get_case_by_id so no ChromaDB call is needed
        from unittest.mock import MagicMock
        mock_case_result = MagicMock()
        mock_case_result.case_id = "case_1"
        mock_case_result.text    = self._MOCK_CASE["text"]
        mock_case_result.metadata = {
            "case_id": "1", "diagnosis": "Acute appendicitis",
            "disease": "Acute appendicitis with appendicular mass",
        }
        with patch("surgmentor.skills.osce_examiner_skill.retrieval_tool.get_case_by_id",
                   return_value=mock_case_result), \
             patch.object(self.skill, "_call_examiner_llm",
                          return_value=self._MOCK_LLM_RESPONSE):
            result = self.skill.run(bundle)

        self.assertEqual(result.updated_osce_step, 1)
        self.assertIsNotNone(result.updated_case)
        self.assertEqual(result.updated_case["case_id"], "1")
        self.assertFalse(result.session_complete)
        self.assertEqual(result.metadata.get("stage"), "init")

    def test_dispatch_to_init_no_case_id_uses_load_all(self):
        """
        When no case_id in parameters, _init() calls load_all_cases()
        and picks the first unseen case. load_all_cases() runs for real here
        (reads data/prepared_cases.json — sandbox-safe).
        """
        bundle = self._bundle(osce_step=0, current_case=None, parameters={})
        with patch.object(self.skill, "_call_examiner_llm",
                          return_value=self._MOCK_LLM_RESPONSE):
            result = self.skill.run(bundle)
        # Should have loaded some real case from prepared_cases.json
        self.assertEqual(result.updated_osce_step, 1)
        self.assertIsNotNone(result.updated_case)
        self.assertIn("case_id", result.updated_case)
        self.assertIn("text",    result.updated_case)

    def test_init_response_text_from_llm(self):
        """_init() response_text should match the mocked LLM output."""
        bundle = self._bundle(osce_step=0, current_case=None,
                              parameters={"case_id": "1"})
        from unittest.mock import MagicMock
        mock_cr = MagicMock()
        mock_cr.case_id  = "case_1"
        mock_cr.text     = self._MOCK_CASE["text"]
        mock_cr.metadata = {"case_id": "1", "diagnosis": "Acute appendicitis",
                             "disease": "Acute appendicitis with appendicular mass"}
        with patch("surgmentor.skills.osce_examiner_skill.retrieval_tool.get_case_by_id",
                   return_value=mock_cr), \
             patch.object(self.skill, "_call_examiner_llm",
                          return_value=self._MOCK_LLM_RESPONSE):
            result = self.skill.run(bundle)
        self.assertEqual(result.response_text, self._MOCK_LLM_RESPONSE)

    # ── Dispatch: turn path ───────────────────────────────────────────────────

    def test_dispatch_to_turn_when_mid_session(self):
        """osce_step=2, current_case populated → dispatches to _turn()."""
        bundle = self._bundle(osce_step=2)
        with patch.object(self.skill, "_call_examiner_llm",
                          return_value=self._MOCK_LLM_RESPONSE):
            result = self.skill.run(bundle)
        self.assertEqual(result.updated_osce_step, 3)   # incremented
        self.assertFalse(result.session_complete)
        self.assertEqual(result.metadata.get("stage"), "turn")

    def test_turn_increments_osce_step(self):
        """_turn() must increment updated_osce_step by exactly 1."""
        for step in [1, 2, 3, 4, 5]:
            with self.subTest(step=step):
                bundle = self._bundle(osce_step=step)
                with patch.object(self.skill, "_call_examiner_llm",
                                  return_value="Next question."):
                    result = self.skill.run(bundle)
                self.assertEqual(result.updated_osce_step, step + 1)

    def test_turn_response_text_from_llm(self):
        """_turn() response_text should match the mocked LLM output."""
        expected = "Good. Now describe the examination findings."
        bundle = self._bundle(osce_step=2)
        with patch.object(self.skill, "_call_examiner_llm",
                          return_value=expected):
            result = self.skill.run(bundle)
        self.assertEqual(result.response_text, expected)

    def test_turn_does_not_set_session_complete(self):
        """During a turn, session_complete must remain False."""
        bundle = self._bundle(osce_step=2)
        with patch.object(self.skill, "_call_examiner_llm",
                          return_value="Keep going."):
            result = self.skill.run(bundle)
        self.assertFalse(result.session_complete)

    def test_call_examiner_llm_raises_on_import_error(self):
        """
        _call_examiner_llm no longer silently catches exceptions — it raises.
        Callers (_init, _turn) are responsible for catching and returning
        context-specific fallback text.

        This test verifies the new contract: bad lazy import → exception propagates.
        """
        import builtins
        real_import = builtins.__import__

        def _bad_import(name, *args, **kwargs):
            if name == "clients":
                raise ImportError("no clients module")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_bad_import):
            with self.assertRaises(ImportError):
                self.skill._call_examiner_llm([{"role": "user", "content": "test"}])

    def test_turn_returns_turn_fallback_on_llm_error(self):
        """
        _turn() catches any LLM exception and returns _TURN_FALLBACK.
        The returned SkillResult must still have a valid structure (step incremented,
        session_complete=False) so the session can continue or be finished by the user.
        """
        from surgmentor.skills.osce_examiner_skill import _TURN_FALLBACK
        bundle = self._bundle(osce_step=2)
        with patch.object(self.skill, "_call_examiner_llm",
                          side_effect=RuntimeError("API error")):
            result = self.skill.run(bundle)
        self.assertEqual(result.response_text, _TURN_FALLBACK)
        self.assertFalse(result.session_complete)
        self.assertEqual(result.updated_osce_step, 3)  # step still incremented

    def test_init_returns_init_fallback_on_llm_error(self):
        """
        _init() catches any LLM exception and returns _INIT_FALLBACK.
        Even on LLM failure, updated_case must be populated (case selection
        from JSON happens before the LLM call).
        """
        from surgmentor.skills.osce_examiner_skill import _INIT_FALLBACK
        from unittest.mock import MagicMock
        mock_cr = MagicMock()
        mock_cr.case_id  = "case_1"
        mock_cr.text     = self._MOCK_CASE["text"]
        mock_cr.metadata = {"case_id": "1", "diagnosis": "Acute appendicitis",
                             "disease": "Acute appendicitis"}
        bundle = self._bundle(osce_step=0, current_case=None,
                              parameters={"case_id": "1"})
        with patch("surgmentor.skills.osce_examiner_skill.retrieval_tool.get_case_by_id",
                   return_value=mock_cr), \
             patch.object(self.skill, "_call_examiner_llm",
                          side_effect=RuntimeError("API timeout")):
            result = self.skill.run(bundle)
        self.assertEqual(result.response_text, _INIT_FALLBACK)
        self.assertIsNotNone(result.updated_case)          # case loaded before LLM call
        self.assertEqual(result.updated_osce_step, 1)     # step still set to 1

    # ── Dispatch: finish path ─────────────────────────────────────────────────

    def test_dispatch_to_finish_via_parameter(self):
        """parameters['finish']=True → dispatches to _finish()."""
        bundle = self._bundle(osce_step=2,
                              parameters={"case_id": "1", "finish": True})
        mock_eval_result = SkillResult(
            response_text    = "## OSCE Score: 7/10\nGood work.",
            session_complete = True,
            evaluation       = self._MOCK_EVALUATION,
        )
        with patch("surgmentor.skills.osce_examiner_skill.EvaluationSkill") as MockEval:
            MockEval.return_value.run.return_value = mock_eval_result
            result = self.skill.run(bundle)

        MockEval.return_value.run.assert_called_once()
        self.assertTrue(result.session_complete)
        self.assertEqual(result.evaluation["score"], 7)
        self.assertEqual(result.updated_osce_step, 0)

    def test_dispatch_to_finish_via_max_steps(self):
        """osce_step >= MAX_OSCE_STEPS → dispatches to _finish() automatically."""
        bundle = self._bundle(osce_step=MAX_OSCE_STEPS)  # at limit
        mock_eval_result = SkillResult(
            response_text    = "## OSCE Score: 6/10",
            session_complete = True,
            evaluation       = {**self._MOCK_EVALUATION, "score": 6},
        )
        with patch("surgmentor.skills.osce_examiner_skill.EvaluationSkill") as MockEval:
            MockEval.return_value.run.return_value = mock_eval_result
            result = self.skill.run(bundle)

        self.assertTrue(result.session_complete)
        self.assertEqual(result.metadata.get("stage"), "finish")

    def test_finish_calls_evaluation_skill(self):
        """_finish() must call EvaluationSkill.run() exactly once."""
        bundle = self._bundle(parameters={"case_id": "1", "finish": True})
        mock_eval_result = SkillResult(
            response_text    = "Score: 8/10",
            session_complete = True,
            evaluation       = self._MOCK_EVALUATION,
        )
        with patch("surgmentor.skills.osce_examiner_skill.EvaluationSkill") as MockEval:
            MockEval.return_value.run.return_value = mock_eval_result
            self.skill.run(bundle)

        MockEval.assert_called_once()
        MockEval.return_value.run.assert_called_once()

    def test_finish_evaluation_dict_in_result(self):
        """result.evaluation must be populated after _finish()."""
        bundle = self._bundle(parameters={"case_id": "1", "finish": True})
        mock_eval_result = SkillResult(
            response_text    = "Score: 8",
            session_complete = True,
            evaluation       = self._MOCK_EVALUATION,
        )
        with patch("surgmentor.skills.osce_examiner_skill.EvaluationSkill") as MockEval:
            MockEval.return_value.run.return_value = mock_eval_result
            result = self.skill.run(bundle)

        self.assertIsNotNone(result.evaluation)
        self.assertIn("score", result.evaluation)
        self.assertIn("weak_areas", result.evaluation)
        self.assertIn("rubric_breakdown", result.evaluation)
        self.assertEqual(result.evaluation["score"], 7)

    # ── Case selection ────────────────────────────────────────────────────────

    def test_picks_unseen_case_from_score_history(self):
        """
        _pick_unseen_case skips cases already in score_history.
        Uses real load_all_cases() (reads prepared_cases.json — sandbox-safe).
        """
        from surgmentor.rag.retrieval_tool import load_all_cases
        all_cases = load_all_cases()
        if len(all_cases) < 2:
            self.skipTest("Need at least 2 cases in prepared_cases.json")

        # Mark first case as seen
        first_case_id = all_cases[0].get("metadata", {}).get("case_id", "")
        score_history = [{"case_id": first_case_id, "score": 7}]

        chosen = self.skill._pick_unseen_case(score_history)

        # Should NOT pick the first case
        self.assertNotEqual(str(chosen.get("case_id")), str(first_case_id))

    def test_fallback_to_first_case_when_all_seen(self):
        """
        When all cases are in score_history, _pick_unseen_case returns
        the first case overall (no crash, no empty result).
        """
        from surgmentor.rag.retrieval_tool import load_all_cases
        all_cases = load_all_cases()
        # Mark all cases as seen
        score_history = [
            {"case_id": c.get("metadata", {}).get("case_id", str(i))}
            for i, c in enumerate(all_cases)
        ]
        chosen = self.skill._pick_unseen_case(score_history)
        self.assertIn("case_id", chosen)
        self.assertIn("text",    chosen)
        self.assertIsNotNone(chosen["case_id"])

    def test_normalize_case_has_required_fields(self):
        """_normalize_case() must produce case_id, text, diagnosis, disease."""
        raw = {
            "id":   "case_3",
            "text": "A 45-year-old with jaundice.",
            "metadata": {"case_id": "3", "diagnosis": "Cholecystitis",
                         "disease": "Acute cholecystitis"},
        }
        normalized = self.skill._normalize_case(raw)
        self.assertEqual(normalized["case_id"], "3")
        self.assertEqual(normalized["doc_id"],  "case_3")
        self.assertEqual(normalized["text"],    raw["text"])
        self.assertEqual(normalized["diagnosis"], "Cholecystitis")
        self.assertEqual(normalized["disease"],   "Acute cholecystitis")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 — Live end-to-end OSCE flow (native machine only)
# ─────────────────────────────────────────────────────────────────────────────

@unittest.skipIf(not _LIVE_LLM, "Live LLM tests: run without CI_NO_LLM=1")
class Test07LiveOSCEFlow(unittest.TestCase):
    """
    End-to-end OSCE flow requiring live DeepSeek API + populated ChromaDB.

    These tests are NOT run in the sandbox (CI_NO_LLM=1 skips them).
    Run on the native Windows machine after populating ChromaDB:
      python -m unittest tests/test_osce_flow.py

    Expected outcome: all tests pass, eval_log.jsonl gains a session_evaluation entry.
    """

    def setUp(self):
        self.skill       = OSCEExaminerSkill()
        self.student_id  = "live-test-student"
        self.session_id  = "live-test-session"
        db_store_module.register_student(self.student_id, "Live Test Student")

    def test_live_osce_full_flow(self):
        """
        Full OSCE session: init → MIN_OSCE_TURNS turns → finish.
        Verifies:
          - Each stage returns the correct SkillResult shape
          - finish() returns session_complete=True
          - evaluation dict has score (int 0-10) and weak_areas (list)
        """
        # Step 0: init
        b0 = ContextBundle(
            student_input    = "start",
            session_history  = [],
            current_case     = None,
            student_id       = self.student_id,
            weak_areas       = [],
            score_history    = [],
            osce_step        = 0,
            parameters       = {"session_id": self.session_id},
        )
        r0 = self.skill.run(b0)
        self.assertEqual(r0.updated_osce_step, 1)
        self.assertIsNotNone(r0.updated_case)
        self.assertFalse(r0.session_complete)
        case = r0.updated_case
        history = [{"role": "assistant", "content": r0.response_text}]

        # MIN_OSCE_TURNS turns
        for i in range(MIN_OSCE_TURNS):
            bi = ContextBundle(
                student_input    = f"Student response turn {i+1}: assessing the patient carefully.",
                session_history  = list(history),
                current_case     = case,
                student_id       = self.student_id,
                weak_areas       = [],
                score_history    = [],
                osce_step        = i + 1,
                parameters       = {"case_id": case.get("case_id", ""),
                                    "session_id": self.session_id},
            )
            ri = self.skill.run(bi)
            self.assertEqual(ri.updated_osce_step, i + 2)
            self.assertFalse(ri.session_complete)
            history.append({"role": "user",      "content": bi.student_input})
            history.append({"role": "assistant",  "content": ri.response_text})

        # Finish
        bf = ContextBundle(
            student_input    = "I'm done.",
            session_history  = list(history),
            current_case     = case,
            student_id       = self.student_id,
            weak_areas       = [],
            score_history    = [],
            osce_step        = MIN_OSCE_TURNS + 1,
            parameters       = {"case_id": case.get("case_id", ""),
                                 "session_id": self.session_id,
                                 "finish":     True},
        )
        rf = self.skill.run(bf)
        self.assertTrue(rf.session_complete)
        self.assertIsNotNone(rf.evaluation)
        self.assertIsInstance(rf.evaluation["score"], int)
        self.assertGreaterEqual(rf.evaluation["score"], 0)
        self.assertLessEqual(rf.evaluation["score"], 10)
        self.assertIsInstance(rf.evaluation["weak_areas"], list)

    def test_live_eval_log_entry_written(self):
        """
        After a finished OSCE session, eval_log.jsonl must contain a
        session_evaluation entry with matching student_id.
        """
        import json
        # Run a minimal init→finish to generate the log entry
        b0 = ContextBundle(
            student_input="start", session_history=[], current_case=None,
            student_id=self.student_id, weak_areas=[], score_history=[],
            osce_step=0, parameters={"session_id": self.session_id + "-logtest"},
        )
        r0 = self.skill.run(b0)
        case    = r0.updated_case
        history = [{"role": "assistant", "content": r0.response_text}]

        for i in range(MIN_OSCE_TURNS):
            history.append({"role": "user", "content": f"Answer {i+1}"})

        bf = ContextBundle(
            student_input="done", session_history=history, current_case=case,
            student_id=self.student_id, weak_areas=[], score_history=[],
            osce_step=MIN_OSCE_TURNS + 1,
            parameters={"case_id": case.get("case_id", ""),
                        "session_id": self.session_id + "-logtest",
                        "finish": True},
        )
        self.skill.run(bf)

        import config as _cfg
        with open(_cfg.EVAL_LOG_PATH, "r", encoding="utf-8") as f:
            lines = [json.loads(l) for l in f if l.strip()]

        session_evals = [l for l in lines
                         if l.get("_type") == "session_evaluation"
                         and l.get("student_id") == self.student_id]
        self.assertGreater(len(session_evals), 0,
            "No session_evaluation entry found in eval_log.jsonl")


# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8 — CaseRetrievalSkill (sandbox-safe)
# ─────────────────────────────────────────────────────────────────────────────

class Test08CaseRetrievalSkill(unittest.TestCase):
    """
    Sandbox-safe tests for CaseRetrievalSkill.
    search_vector_store and _call_retrieval_llm are mocked throughout.
    """

    def setUp(self):
        self.skill = CaseRetrievalSkill()
        self.mock_cases = [
            CaseResult(
                case_id    = "case_1",
                text       = "A 22-year-old female with right iliac fossa pain.",
                metadata   = {"case_id": "1", "diagnosis": "Acute appendicitis",
                               "disease": "Acute appendicitis with appendicular mass"},
                similarity = 0.85,
            ),
            CaseResult(
                case_id    = "case_3",
                text       = "A 45-year-old male with RUQ pain and jaundice.",
                metadata   = {"case_id": "3", "diagnosis": "Cholecystitis",
                               "disease": "Acute cholecystitis"},
                similarity = 0.71,
            ),
        ]

    def _bundle(self, **kwargs):
        defaults = dict(
            student_input="Show me a case about abdominal pain",
            session_history=[], current_case=None,
            student_id="cr-student", weak_areas=[],
            score_history=[], osce_step=0, parameters={},
        )
        defaults.update(kwargs)
        return ContextBundle(**defaults)

    # ── type / identity ───────────────────────────────────────────────────────

    def test_is_skill_subclass(self):
        self.assertIsInstance(self.skill, Skill)

    def test_name_set(self):
        self.assertEqual(self.skill.name, "CaseRetrievalSkill")

    def test_description_nonempty(self):
        self.assertGreater(len(self.skill.description), 0)

    # ── empty retrieval guard ─────────────────────────────────────────────────

    def test_empty_retrieval_no_llm_call(self):
        """No LLM call when retrieval returns empty list."""
        with patch("surgmentor.skills.case_retrieval_skill.retrieval_tool.search_vector_store",
                   return_value=[]),              patch.object(self.skill, "_call_retrieval_llm") as mock_llm:
            result = self.skill.run(self._bundle())
        mock_llm.assert_not_called()
        self.assertIsInstance(result.response_text, str)
        self.assertGreater(len(result.response_text), 0)
        self.assertEqual(result.metadata["retrieval_hits"], 0)
        self.assertEqual(result.metadata["case_ids"], [])

    # ── normal path ───────────────────────────────────────────────────────────

    def test_sources_block_in_response(self):
        """response_text must include a Sources: block."""
        with patch("surgmentor.skills.case_retrieval_skill.retrieval_tool.search_vector_store",
                   return_value=self.mock_cases),              patch.object(self.skill, "_call_retrieval_llm", return_value="Answer text."):
            result = self.skill.run(self._bundle())
        self.assertIn("**Sources:**", result.response_text)
        self.assertIn("case_1", result.response_text)
        self.assertIn("Acute appendicitis", result.response_text)

    def test_similarity_in_citation(self):
        """Citation lines must include the similarity score."""
        with patch("surgmentor.skills.case_retrieval_skill.retrieval_tool.search_vector_store",
                   return_value=self.mock_cases),              patch.object(self.skill, "_call_retrieval_llm", return_value="Answer."):
            result = self.skill.run(self._bundle())
        self.assertIn("0.85", result.response_text)
        self.assertIn("0.71", result.response_text)

    def test_metadata_retrieval_hits(self):
        with patch("surgmentor.skills.case_retrieval_skill.retrieval_tool.search_vector_store",
                   return_value=self.mock_cases),              patch.object(self.skill, "_call_retrieval_llm", return_value="Answer."):
            result = self.skill.run(self._bundle())
        self.assertEqual(result.metadata["retrieval_hits"], 2)
        self.assertEqual(result.metadata["case_ids"], ["case_1", "case_3"])

    def test_weak_areas_forwarded_as_bias_topics(self):
        """weak_areas must be forwarded as bias_topics (Day 1 context engineering)."""
        weak = ["History taking", "Management plan"]
        with patch("surgmentor.skills.case_retrieval_skill.retrieval_tool.search_vector_store",
                   return_value=self.mock_cases) as mock_search,              patch.object(self.skill, "_call_retrieval_llm", return_value="Answer."):
            self.skill.run(self._bundle(weak_areas=weak))
        passed_bias = mock_search.call_args.kwargs.get(
            "bias_topics",
            mock_search.call_args.args[2] if len(mock_search.call_args.args) > 2 else None
        )
        self.assertEqual(passed_bias, weak)

    def test_history_windowed(self):
        """session_history beyond HISTORY_WINDOW must be trimmed before LLM call."""
        from config import HISTORY_WINDOW
        long_hist = [{"role": "user" if i % 2 == 0 else "assistant",
                      "content": f"Turn {i}"}
                     for i in range(HISTORY_WINDOW + 6)]
        captured = []
        def _capture(msgs):
            captured.extend(msgs)
            return "Resp"
        with patch("surgmentor.skills.case_retrieval_skill.retrieval_tool.search_vector_store",
                   return_value=self.mock_cases),              patch.object(self.skill, "_call_retrieval_llm", side_effect=_capture):
            self.skill.run(self._bundle(session_history=long_hist))
        hist_msgs = [m for m in captured if m["role"] in ("user", "assistant")]
        self.assertLessEqual(len(hist_msgs), HISTORY_WINDOW + 1)

    def test_llm_text_in_response(self):
        """LLM response text must appear in result.response_text."""
        llm_text = "McBurney's point tenderness is classic."
        with patch("surgmentor.skills.case_retrieval_skill.retrieval_tool.search_vector_store",
                   return_value=self.mock_cases),              patch.object(self.skill, "_call_retrieval_llm", return_value=llm_text):
            result = self.skill.run(self._bundle())
        self.assertIn(llm_text, result.response_text)

    def test_format_sources_line_count(self):
        """_format_sources produces one line per case."""
        text = self.skill._format_sources(self.mock_cases)
        lines = [l for l in text.strip().splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 9 — StudyPlannerSkill (sandbox-safe)
# ─────────────────────────────────────────────────────────────────────────────

class Test09StudyPlannerSkill(unittest.TestCase):
    """
    Sandbox-safe tests for StudyPlannerSkill.
    db_store.get_student_stats and _call_planner_llm are mocked throughout.
    """

    _STATS = {
        "user":     {"student_id": "s1", "display_name": "Alice"},
        "sessions": {"total": 6},
        "osce":     {"total_osce": 4, "avg_score": 6.25,
                     "best_score": 8, "worst_score": 4},
        "recent_osce": [
            {"diagnosis": "Acute appendicitis", "score": 8,
             "completed_at": "2026-06-18T10:00:00"},
            {"diagnosis": "Cholecystitis",       "score": 5,
             "completed_at": "2026-06-17T14:00:00"},
        ],
        "top_topics":       ["Appendicitis", "Cholecystitis"],
        "unique_diagnoses": ["Acute appendicitis", "Cholecystitis",
                              "Bowel obstruction", "Pancreatitis"],
        "weak_areas": [
            ("History taking",  4),
            ("Management plan", 3),
            ("Imaging reading", 2),
        ],
    }

    def setUp(self):
        self.skill = StudyPlannerSkill()

    def _bundle(self, **kwargs):
        defaults = dict(
            student_input="What should I study?",
            session_history=[], current_case=None,
            student_id="sp-student", weak_areas=[],
            score_history=[], osce_step=0, parameters={},
        )
        defaults.update(kwargs)
        return ContextBundle(**defaults)

    # ── type / identity ───────────────────────────────────────────────────────

    def test_is_skill_subclass(self):
        self.assertIsInstance(self.skill, Skill)

    def test_name_set(self):
        self.assertEqual(self.skill.name, "StudyPlannerSkill")

    def test_description_nonempty(self):
        self.assertGreater(len(self.skill.description), 0)

    # ── onboarding guard ─────────────────────────────────────────────────────

    def test_new_student_no_llm_call(self):
        """get_student_stats=={} → onboarding message, no LLM call."""
        with patch("surgmentor.skills.study_planner_skill.db_store.get_student_stats",
                   return_value={}) as mock_stats,              patch.object(self.skill, "_call_planner_llm") as mock_llm:
            result = self.skill.run(self._bundle())
        mock_stats.assert_called_once_with("sp-student")
        mock_llm.assert_not_called()
        self.assertTrue(result.metadata.get("new_student"))
        self.assertEqual(result.metadata["weak_areas_count"], 0)
        self.assertGreater(len(result.response_text), 0)

    def test_new_student_session_not_complete(self):
        with patch("surgmentor.skills.study_planner_skill.db_store.get_student_stats",
                   return_value={}):
            result = self.skill.run(self._bundle())
        self.assertFalse(result.session_complete)

    # ── existing student path ─────────────────────────────────────────────────

    def test_existing_student_calls_llm(self):
        with patch("surgmentor.skills.study_planner_skill.db_store.get_student_stats",
                   return_value=self._STATS),              patch.object(self.skill, "_call_planner_llm",
                          return_value="Here is your plan.") as mock_llm:
            result = self.skill.run(self._bundle())
        mock_llm.assert_called_once()
        self.assertEqual(result.response_text, "Here is your plan.")

    def test_existing_student_metadata(self):
        with patch("surgmentor.skills.study_planner_skill.db_store.get_student_stats",
                   return_value=self._STATS),              patch.object(self.skill, "_call_planner_llm", return_value="Plan."):
            result = self.skill.run(self._bundle())
        self.assertFalse(result.metadata.get("new_student"))
        self.assertAlmostEqual(result.metadata["avg_score"], 6.25)
        self.assertEqual(result.metadata["weak_areas_count"], 3)
        self.assertEqual(result.metadata["total_cases"], 4)

    def test_existing_student_not_session_complete(self):
        with patch("surgmentor.skills.study_planner_skill.db_store.get_student_stats",
                   return_value=self._STATS),              patch.object(self.skill, "_call_planner_llm", return_value="Plan."):
            result = self.skill.run(self._bundle())
        self.assertFalse(result.session_complete)

    # ── _format_student_data ──────────────────────────────────────────────────

    def test_format_includes_avg_score(self):
        text = self.skill._format_student_data(self._STATS)
        self.assertIn("6.25", text)

    def test_format_includes_weak_areas(self):
        text = self.skill._format_student_data(self._STATS)
        self.assertIn("Weak areas", text)
        self.assertIn("History taking", text)

    def test_format_includes_recent_osce(self):
        text = self.skill._format_student_data(self._STATS)
        self.assertIn("Acute appendicitis", text)

    def test_format_handles_empty_osce(self):
        minimal = {
            "user": {}, "sessions": {"total": 0},
            "osce": {"total_osce": 0, "avg_score": 0.0,
                     "best_score": 0, "worst_score": 0},
            "recent_osce": [], "top_topics": [],
            "unique_diagnoses": [], "weak_areas": [],
        }
        text = self.skill._format_student_data(minimal)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 10 — Live Phase 3C integration (native machine only)
# ─────────────────────────────────────────────────────────────────────────────

@unittest.skipIf(not _LIVE_LLM, "Live LLM tests: run without CI_NO_LLM=1")
class Test10LivePhase3C(unittest.TestCase):
    """
    Live integration tests for CaseRetrievalSkill and StudyPlannerSkill.
    Requires live DeepSeek API + populated ChromaDB (Jina embeddings).
    Run on native Windows: python -m unittest tests/test_osce_flow.py
    """

    def test_live_case_retrieval_grounded_response(self):
        skill  = CaseRetrievalSkill()
        bundle = ContextBundle(
            student_input="Show me a case about right iliac fossa pain",
            session_history=[], current_case=None, student_id="live-cr-s1",
            weak_areas=[], score_history=[], osce_step=0, parameters={},
        )
        result = skill.run(bundle)
        self.assertIsInstance(result.response_text, str)
        self.assertGreater(len(result.response_text), 50)
        self.assertIn("**Sources:**", result.response_text)
        self.assertGreater(result.metadata["retrieval_hits"], 0)

    def test_live_study_planner_new_student(self):
        skill  = StudyPlannerSkill()
        bundle = ContextBundle(
            student_input="What should I study?",
            session_history=[], current_case=None,
            student_id="brand-new-unknown-student-xyz-9999",
            weak_areas=[], score_history=[], osce_step=0, parameters={},
        )
        result = skill.run(bundle)
        self.assertTrue(result.metadata.get("new_student"))
        self.assertGreater(len(result.response_text), 20)


def tearDownModule():
    """Clean up temp files created during the test run."""
    for path in (_tmp_db, _tmp_log):
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    unittest.main()
