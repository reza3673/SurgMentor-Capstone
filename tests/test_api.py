# tests/test_api.py
"""
Phase 5B — FastAPI server contract tests.

All tests are sandbox-safe (CI_NO_LLM=1). The AgentController, db_store init,
and validate_api_keys are patched before the FastAPI app is imported so no LLM
calls, no Jina calls, and no SQLite writes occur.

Test classes:
  Test01ServerImport        — server.py imports; app is FastAPI; all 7 routes present
  Test02ChatEndpoint        — POST /api/chat happy path; exception → friendly string
  Test03OsceStart           — POST /api/osce/start; osce_active=True in response
  Test04OsceTurn            — POST /api/osce/turn; is_finish flag logic
  Test05OsceFinish          — POST /api/osce/finish; is_finish always present
  Test06OsceReset           — POST /api/osce/reset; new_session_id is fresh UUID
  Test07Profile             — GET  /api/profile; stats_md non-empty; has_data flag
  Test08ProfilePlan         — POST /api/profile/plan; response is string
  Test09ValidationErrors    — missing fields / wrong types → 422

Run (sandbox-safe):
  PYTHONPYCACHEPREFIX=/tmp/pycache_surgmentor CI_NO_LLM=1 \
    python -m unittest tests/test_api.py -v
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# ── Path bootstrap ─────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Sandbox config patches (must happen before any surgmentor import) ──────────

import config
config.SCOPE_CLASSIFICATION_ENABLED = False

_tmp_db  = tempfile.NamedTemporaryFile(suffix=".db",    delete=False).name
_tmp_log = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False).name
config.AGENT_SESSION_DB_PATH = _tmp_db
config.EVAL_LOG_PATH         = _tmp_log

import surgmentor.memory.db_store   as _db_mod
import surgmentor.evaluation.logger as _log_mod
importlib.reload(_db_mod)
importlib.reload(_log_mod)
_db_mod.init_database()

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_client():
    """
    Return a (TestClient, mock_controller) pair.

    Patches applied before server.py is imported:
      - controller.run()          — avoids LLM
      - db_store.init_database()  — already initialised above
      - validate_api_keys()       — no real keys needed
      - db_store.get_student_stats() — controlled stats output
    """
    from fastapi.testclient import TestClient

    # Patch session store so _read_osce_state and _reset_osce_state both work.
    # _reset_osce_state now accesses state via controller.session_store; wiring
    # mock_ctrl.session_store = mock_store ensures both functions hit the same store.
    from surgmentor.memory.session import InMemorySessionStore, make_default_state
    mock_store = InMemorySessionStore()

    mock_ctrl = MagicMock()
    mock_ctrl.run.return_value = "Test response from mock controller."
    mock_ctrl.session_store = mock_store   # must match default_store patch below

    with patch("surgmentor.agent.controller.controller", mock_ctrl), \
         patch("surgmentor.memory.session.default_store", mock_store), \
         patch("surgmentor.memory.db_store.init_database", return_value=None), \
         patch("surgmentor.ui.helpers.validate_api_keys", return_value=None):
        # Import fresh each time inside the patch context
        import server as srv
        importlib.reload(srv)
        # raise_server_exceptions=True (default): server exceptions surface as Python
        # exceptions in the test instead of returning an empty-body response.
        # All error-path tests (test_controller_exception_returns_friendly_string etc.)
        # still pass because the server catches those exceptions internally in _safe_run.
        client = TestClient(srv.app)

    return client, mock_ctrl, mock_store


# ── Test 01: Import and structure ─────────────────────────────────────────────

class Test01ServerImport(unittest.TestCase):
    """server.py imports cleanly; app is FastAPI; all 7 routes registered."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        mock_ctrl = MagicMock()
        mock_ctrl.run.return_value = "ok"

        with patch("surgmentor.agent.controller.controller", mock_ctrl), \
             patch("surgmentor.memory.db_store.init_database", return_value=None), \
             patch("surgmentor.ui.helpers.validate_api_keys", return_value=None):
            import server as srv
            importlib.reload(srv)
            cls.app = srv.app
            cls.client = TestClient(srv.app)

    def test_app_is_fastapi(self):
        from fastapi import FastAPI
        self.assertIsInstance(self.app, FastAPI)

    def test_all_routes_registered(self):
        paths = {r.path for r in self.app.routes}
        expected = {
            "/api/chat",
            "/api/osce/start",
            "/api/osce/turn",
            "/api/osce/finish",
            "/api/osce/reset",
            "/api/profile",
            "/api/profile/plan",
        }
        for path in expected:
            self.assertIn(path, paths, f"Route {path!r} not registered")

    def test_openapi_schema_available(self):
        r = self.client.get("/openapi.json")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("paths", data)


# ── Test 02: /api/chat ─────────────────────────────────────────────────────────

class Test02ChatEndpoint(unittest.TestCase):
    """POST /api/chat — happy path, controller called with correct args, exception → friendly string."""

    @classmethod
    def setUpClass(cls):
        cls.client, cls.mock_ctrl, cls.store = _make_client()

    def test_happy_path_returns_200(self):
        self.mock_ctrl.run.return_value = "Here is a case about appendicitis."
        r = self.client.post("/api/chat",
            json={"session_id": "s-chat-01", "message": "appendicitis case"})
        self.assertEqual(r.status_code, 200)

    def test_response_contains_correct_keys(self):
        self.mock_ctrl.run.return_value = "Response text."
        r = self.client.post("/api/chat",
            json={"session_id": "s-chat-02", "message": "hello"})
        data = r.json()
        self.assertIn("session_id", data)
        self.assertIn("response",   data)

    def test_session_id_echoed(self):
        self.mock_ctrl.run.return_value = "ok"
        r = self.client.post("/api/chat",
            json={"session_id": "echo-this", "message": "hi"})
        self.assertEqual(r.json()["session_id"], "echo-this")

    def test_controller_called_with_message_and_session_id(self):
        self.mock_ctrl.run.return_value = "ok"
        self.mock_ctrl.run.reset_mock()
        self.client.post("/api/chat",
            json={"session_id": "s-ctrl-check", "message": "appendicitis"})
        self.mock_ctrl.run.assert_called_once_with("appendicitis", "s-ctrl-check")

    def test_controller_exception_returns_friendly_string(self):
        self.mock_ctrl.run.side_effect = RuntimeError("LLM timeout")
        r = self.client.post("/api/chat",
            json={"session_id": "s-exc", "message": "boom"})
        self.assertEqual(r.status_code, 200)
        body = r.json()["response"]
        self.assertIn("Something went wrong", body)
        self.mock_ctrl.run.side_effect = None  # reset

    def test_response_is_string(self):
        self.mock_ctrl.run.return_value = "Case details here."
        r = self.client.post("/api/chat",
            json={"session_id": "s-type", "message": "test"})
        self.assertIsInstance(r.json()["response"], str)


# ── Test 03: /api/osce/start ───────────────────────────────────────────────────

class Test03OsceStart(unittest.TestCase):
    """POST /api/osce/start — 200, osce fields present, examiner message returned."""

    @classmethod
    def setUpClass(cls):
        cls.client, cls.mock_ctrl, cls.store = _make_client()

    def test_returns_200(self):
        self.mock_ctrl.run.return_value = "Welcome. Here is your patient."
        r = self.client.post("/api/osce/start", json={"session_id": "s-osce-start"})
        self.assertEqual(r.status_code, 200)

    def test_response_keys_present(self):
        self.mock_ctrl.run.return_value = "Examiner first question."
        r = self.client.post("/api/osce/start", json={"session_id": "s-osce-keys"})
        data = r.json()
        for key in ("session_id", "response", "osce_active", "osce_step", "is_finish"):
            self.assertIn(key, data, f"Key {key!r} missing from /api/osce/start response")

    def test_controller_called_with_start_osce(self):
        self.mock_ctrl.run.reset_mock()
        self.mock_ctrl.run.return_value = "First question."
        self.client.post("/api/osce/start", json={"session_id": "s-start-check"})
        self.mock_ctrl.run.assert_called_once_with("start osce", "s-start-check")

    def test_is_finish_false_on_start(self):
        self.mock_ctrl.run.return_value = "Patient presents with pain."
        r = self.client.post("/api/osce/start", json={"session_id": "s-not-finish"})
        self.assertFalse(r.json()["is_finish"])


# ── Test 04: /api/osce/turn ────────────────────────────────────────────────────

class Test04OsceTurn(unittest.TestCase):
    """POST /api/osce/turn — is_finish logic, response echoed correctly."""

    @classmethod
    def setUpClass(cls):
        cls.client, cls.mock_ctrl, cls.store = _make_client()

    def test_returns_200(self):
        self.mock_ctrl.run.return_value = "Good. What is your diagnosis?"
        r = self.client.post("/api/osce/turn",
            json={"session_id": "s-turn-01", "message": "I would take a history"})
        self.assertEqual(r.status_code, 200)

    def test_is_finish_false_for_mid_session_response(self):
        self.mock_ctrl.run.return_value = "Good. Describe the examination."
        r = self.client.post("/api/osce/turn",
            json={"session_id": "s-turn-mid", "message": "history taken"})
        self.assertFalse(r.json()["is_finish"])

    def test_is_finish_true_when_score_marker_present(self):
        self.mock_ctrl.run.return_value = "Score: 8/10\n\nExcellent performance."
        r = self.client.post("/api/osce/turn",
            json={"session_id": "s-turn-end", "message": "finish"})
        self.assertTrue(r.json()["is_finish"])

    def test_is_finish_true_for_final_score_marker(self):
        self.mock_ctrl.run.return_value = "Final Score: 7 out of 10."
        r = self.client.post("/api/osce/turn",
            json={"session_id": "s-turn-final", "message": "done"})
        self.assertTrue(r.json()["is_finish"])

    def test_controller_called_with_student_message(self):
        self.mock_ctrl.run.reset_mock()
        self.mock_ctrl.run.return_value = "Next question."
        self.client.post("/api/osce/turn",
            json={"session_id": "s-turn-ctrl", "message": "my answer"})
        self.mock_ctrl.run.assert_called_once_with("my answer", "s-turn-ctrl")

    def test_response_field_is_string(self):
        self.mock_ctrl.run.return_value = "Next question."
        r = self.client.post("/api/osce/turn",
            json={"session_id": "s-turn-type", "message": "answer"})
        self.assertIsInstance(r.json()["response"], str)


# ── Test 05: /api/osce/finish ──────────────────────────────────────────────────

class Test05OsceFinish(unittest.TestCase):
    """POST /api/osce/finish — is_finish key present; controller called with 'finish'."""

    @classmethod
    def setUpClass(cls):
        cls.client, cls.mock_ctrl, cls.store = _make_client()

    def test_returns_200(self):
        self.mock_ctrl.run.return_value = "Score: 9/10\n\nExcellent."
        r = self.client.post("/api/osce/finish", json={"session_id": "s-finish-01"})
        self.assertEqual(r.status_code, 200)

    def test_is_finish_key_present(self):
        self.mock_ctrl.run.return_value = "Score: 8/10"
        r = self.client.post("/api/osce/finish", json={"session_id": "s-finish-key"})
        self.assertIn("is_finish", r.json())

    def test_controller_called_with_finish(self):
        self.mock_ctrl.run.reset_mock()
        self.mock_ctrl.run.return_value = "Score: 7/10"
        self.client.post("/api/osce/finish", json={"session_id": "s-finish-ctrl"})
        self.mock_ctrl.run.assert_called_once_with("finish", "s-finish-ctrl")

    def test_response_contains_score_text(self):
        self.mock_ctrl.run.return_value = "Score: 6/10\n\nSatisfactory."
        r = self.client.post("/api/osce/finish", json={"session_id": "s-finish-text"})
        self.assertIn("Score", r.json()["response"])


# ── Test 06: /api/osce/reset ───────────────────────────────────────────────────

class Test06OsceReset(unittest.TestCase):
    """POST /api/osce/reset — new_session_id returned; it is a valid UUID4; different from input."""

    @classmethod
    def setUpClass(cls):
        cls.client, cls.mock_ctrl, cls.store = _make_client()

    def test_returns_200(self):
        r = self.client.post("/api/osce/reset", json={"session_id": "s-reset-01"})
        self.assertEqual(r.status_code, 200)

    def test_new_session_id_present(self):
        r = self.client.post("/api/osce/reset", json={"session_id": "s-reset-key"})
        self.assertIn("new_session_id", r.json())

    def test_new_session_id_is_string(self):
        r = self.client.post("/api/osce/reset", json={"session_id": "s-reset-type"})
        self.assertIsInstance(r.json()["new_session_id"], str)

    def test_new_session_id_is_uuid4_shape(self):
        import re
        r = self.client.post("/api/osce/reset", json={"session_id": "s-reset-uuid"})
        new_id = r.json()["new_session_id"]
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        self.assertRegex(new_id, pattern, f"{new_id!r} is not a valid UUID4")

    def test_new_session_id_differs_from_input(self):
        old = "s-reset-diff-input"
        r = self.client.post("/api/osce/reset", json={"session_id": old})
        self.assertNotEqual(r.json()["new_session_id"], old)


# ── Test 07: /api/profile ─────────────────────────────────────────────────────

class Test07Profile(unittest.TestCase):
    """GET /api/profile — stats_md non-empty; has_data reflects whether stats exist."""

    @classmethod
    def setUpClass(cls):
        cls.client, cls.mock_ctrl, cls.store = _make_client()

    def test_returns_200_for_unknown_student(self):
        with patch("surgmentor.memory.db_store.get_student_stats", return_value={}):
            r = self.client.get("/api/profile?session_id=unknown-student")
        self.assertEqual(r.status_code, 200)

    def test_has_data_false_for_unknown_student(self):
        with patch("surgmentor.memory.db_store.get_student_stats", return_value={}):
            r = self.client.get("/api/profile?session_id=new-student-no-data")
        self.assertFalse(r.json()["has_data"])

    def test_stats_md_non_empty_for_unknown_student(self):
        with patch("surgmentor.memory.db_store.get_student_stats", return_value={}):
            r = self.client.get("/api/profile?session_id=new-no-data")
        # Even for no-data student, the onboarding message should be returned
        self.assertGreater(len(r.json()["stats_md"]), 0)

    def test_has_data_true_when_stats_present(self):
        sample_stats = {
            "user": {"student_id": "s1", "display_name": "Test",
                     "joined_date": "2026-01-01", "last_active": "2026-06-22"},
            "sessions": {"total": 2, "osce_count": 1, "chat_count": 1, "total_messages": 10},
            "osce": {"total_osce": 1, "avg_score": 8.0, "best_score": 8, "worst_score": 8},
            "recent_osce": [{"diagnosis": "Appendicitis", "score": 8,
                              "feedback": "Good", "weak_areas": "", "completed_at": "2026-06-22"}],
            "top_topics": ["Appendicitis"],
            "unique_diagnoses": ["Appendicitis"],  # render_stats_markdown expects a list (calls len())
            "weak_areas": [("history taking", 1)],
        }
        with patch("surgmentor.memory.db_store.get_student_stats", return_value=sample_stats):
            r = self.client.get("/api/profile?session_id=has-data-student")
        data = r.json()
        self.assertTrue(data["has_data"])
        self.assertIn("Performance Summary", data["stats_md"])

    def test_session_id_echoed(self):
        with patch("surgmentor.memory.db_store.get_student_stats", return_value={}):
            r = self.client.get("/api/profile?session_id=echo-me")
        self.assertEqual(r.json()["session_id"], "echo-me")

    def test_db_exception_returns_200_with_onboarding(self):
        with patch("surgmentor.memory.db_store.get_student_stats",
                   side_effect=Exception("DB error")):
            r = self.client.get("/api/profile?session_id=db-err")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["has_data"])


# ── Test 08: /api/profile/plan ────────────────────────────────────────────────

class Test08ProfilePlan(unittest.TestCase):
    """POST /api/profile/plan — response is string; controller called with study query."""

    @classmethod
    def setUpClass(cls):
        cls.client, cls.mock_ctrl, cls.store = _make_client()

    def test_returns_200(self):
        self.mock_ctrl.run.return_value = "## Study Plan\n1. Review appendicitis."
        r = self.client.post("/api/profile/plan", json={"session_id": "s-plan-01"})
        self.assertEqual(r.status_code, 200)

    def test_response_is_string(self):
        self.mock_ctrl.run.return_value = "Study plan text."
        r = self.client.post("/api/profile/plan", json={"session_id": "s-plan-type"})
        self.assertIsInstance(r.json()["response"], str)

    def test_controller_called_with_study_query(self):
        self.mock_ctrl.run.reset_mock()
        self.mock_ctrl.run.return_value = "Plan text."
        self.client.post("/api/profile/plan", json={"session_id": "s-plan-ctrl"})
        self.mock_ctrl.run.assert_called_once_with("what should I study", "s-plan-ctrl")

    def test_session_id_echoed(self):
        self.mock_ctrl.run.return_value = "Plan."
        r = self.client.post("/api/profile/plan", json={"session_id": "plan-echo"})
        self.assertEqual(r.json()["session_id"], "plan-echo")

    def test_controller_exception_returns_friendly_string(self):
        self.mock_ctrl.run.side_effect = RuntimeError("timeout")
        r = self.client.post("/api/profile/plan", json={"session_id": "s-plan-exc"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Something went wrong", r.json()["response"])
        self.mock_ctrl.run.side_effect = None


# ── Test 09: Validation errors ─────────────────────────────────────────────────

class Test09ValidationErrors(unittest.TestCase):
    """Missing required fields or wrong types → 422 Unprocessable Entity."""

    @classmethod
    def setUpClass(cls):
        cls.client, cls.mock_ctrl, cls.store = _make_client()

    def test_chat_missing_message(self):
        r = self.client.post("/api/chat", json={"session_id": "s"})
        self.assertEqual(r.status_code, 422)

    def test_chat_missing_session_id(self):
        r = self.client.post("/api/chat", json={"message": "hello"})
        self.assertEqual(r.status_code, 422)

    def test_osce_start_missing_session_id(self):
        r = self.client.post("/api/osce/start", json={})
        self.assertEqual(r.status_code, 422)

    def test_osce_turn_missing_message(self):
        r = self.client.post("/api/osce/turn", json={"session_id": "s"})
        self.assertEqual(r.status_code, 422)

    def test_osce_finish_missing_session_id(self):
        r = self.client.post("/api/osce/finish", json={})
        self.assertEqual(r.status_code, 422)

    def test_osce_reset_missing_session_id(self):
        r = self.client.post("/api/osce/reset", json={})
        self.assertEqual(r.status_code, 422)

    def test_profile_missing_session_id_param(self):
        r = self.client.get("/api/profile")  # no ?session_id=
        self.assertEqual(r.status_code, 422)

    def test_profile_plan_missing_session_id(self):
        r = self.client.post("/api/profile/plan", json={})
        self.assertEqual(r.status_code, 422)


# ── Test 10: osce/start reset regression ─────────────────────────────────────

class Test10OsceStartReset(unittest.TestCase):
    """
    Regression: POST /api/osce/start must clear osce_active BEFORE calling
    controller.run so AgentController._apply_osce_override does not convert
    START_OSCE to OSCE_TURN.

    Root cause: when the browser reuses a sessionStorage session_id that already
    has osce_active=True, _apply_osce_override forces any intent to OSCE_TURN.
    Fix: _reset_osce_state() clears osce_active/osce_step before controller.run.
    """

    @classmethod
    def setUpClass(cls):
        cls.client, cls.mock_ctrl, cls.mock_store = _make_client()
        cls.mock_ctrl.run.return_value = "Patient case: 45-year-old with RUQ pain."

    def test_start_on_active_session_returns_200(self):
        """Starting OSCE when osce_active=True must succeed, not 500."""
        from surgmentor.memory.session import make_default_state
        state = make_default_state("active-osce-sid", "student-active")
        state.osce_active = True
        state.osce_step   = 3
        self.mock_store.write("active-osce-sid", state)
        r = self.client.post("/api/osce/start", json={"session_id": "active-osce-sid"})
        self.assertEqual(r.status_code, 200)

    def test_start_on_active_session_resets_osce_step_to_zero(self):
        """
        osce_step in the response must be 0 after start-with-existing-session.

        Mechanism: _reset_osce_state sets osce_step=0 before controller.run;
        the mock controller does not update state, so _read_osce_state returns 0.
        Without the reset, this would return the original seeded value (3) and
        the frontend would show "Step 3 / 6" on a brand-new case.
        """
        from surgmentor.memory.session import make_default_state
        state = make_default_state("active-osce-step", "student-step")
        state.osce_active = True
        state.osce_step   = 3
        self.mock_store.write("active-osce-step", state)
        r = self.client.post("/api/osce/start", json={"session_id": "active-osce-step"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json()["osce_step"], 0,
            "osce_step must be 0 after reset; session was not cleared before controller.run"
        )

    def test_start_controller_called_with_start_osce_message(self):
        """controller.run must always receive 'start osce'."""
        self.mock_ctrl.run.reset_mock()
        r = self.client.post("/api/osce/start", json={"session_id": "start-msg-sid"})
        self.assertEqual(r.status_code, 200)
        called_msg = self.mock_ctrl.run.call_args[0][0]
        self.assertEqual(called_msg, "start osce")

    def test_start_is_finish_always_false(self):
        """osce/start never sets is_finish=True."""
        r = self.client.post("/api/osce/start", json={"session_id": "is-finish-start"})
        self.assertFalse(r.json()["is_finish"])

    def test_max_steps_present_in_osce_start_response(self):
        """OsceStateResponse includes max_steps so frontend needs no hardcoded value."""
        r = self.client.post("/api/osce/start", json={"session_id": "max-steps-sid"})
        data = r.json()
        self.assertIn("max_steps", data)
        self.assertIsInstance(data["max_steps"], int)
        self.assertGreater(data["max_steps"], 0)

    def test_max_steps_equals_backend_constant(self):
        """max_steps value must match MAX_OSCE_STEPS from osce_examiner_skill."""
        from surgmentor.skills.osce_examiner_skill import MAX_OSCE_STEPS
        r = self.client.post("/api/osce/start", json={"session_id": "max-steps-val"})
        self.assertEqual(r.json()["max_steps"], MAX_OSCE_STEPS)

    def test_max_steps_also_present_in_osce_turn_response(self):
        """All OsceStateResponse endpoints carry max_steps, not just start."""
        r = self.client.post("/api/osce/turn",
                             json={"session_id": "max-steps-turn",
                                   "message": "I would take a history"})
        self.assertIn("max_steps", r.json())



# ── Test 11: Real controller store — object identity + routing ────────────────

class Test11OsceStartRealStore(unittest.TestCase):
    """
    Integration regression: uses the REAL AgentController singleton and the
    real session store — not a mock controller or a mock store.

    Test10 (mock store) verifies the API response shape and the store-level
    reset behaviour, but the mock_store used there is a DIFFERENT object from
    the store controller.run() reads in production.  These tests prove two
    stronger properties:

      1. controller.session_store IS the same object that _reset_osce_state
         reads and writes — no store-identity divergence in production.

      2. After _reset_osce_state runs, the state that controller._get_or_init_state
         returns has osce_active=False, osce_step=0, current_case=None — so
         _apply_osce_override sees a clean state and routes to START_OSCE,
         not OSCE_TURN, even when the session previously had osce_active=True.

      3. OSCEExaminerSkill.run() dispatches to _init() (not _turn()) — confirmed
         by injecting a distinguishable marker into the mock LLM response.

      4. The HTTP response body contains the _init() marker, not the _turn()
         fallback ("Thank you for your response…").

    Setup: server is reloaded WITHOUT the controller mock so srv.controller is
    the real AgentController singleton.  Only _call_examiner_llm and
    db_store.init_database are patched to avoid real API calls and double-init.
    """

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import server as srv

        # Reload server WITHOUT controller mock — real AgentController in use.
        # validate_api_keys and db_store.init_database are still patched to
        # avoid real key checks and double-init on the temp DB.
        with patch("surgmentor.memory.db_store.init_database", return_value=None), \
             patch("surgmentor.ui.helpers.validate_api_keys", return_value=None):
            importlib.reload(srv)

        cls.srv    = srv
        cls.client = TestClient(srv.app)
        # Real controller + real store (confirmed same object below)
        cls.ctrl   = srv.controller
        cls.store  = srv.controller.session_store

    def _seed_active_osce(self, session_id: str) -> None:
        """Write an active OSCE state into the real store."""
        from surgmentor.memory.session import make_default_state
        state = make_default_state(session_id, session_id)
        state.osce_active  = True
        state.osce_step    = 3
        state.current_case = {"case_id": "old_case", "text": "Old patient scenario."}
        state.mode         = "osce"
        self.store.write(session_id, state)

    # ── Test 1: Object identity ───────────────────────────────────────────────

    def test_default_store_and_controller_store_are_same_object(self):
        """
        server.default_store must be the exact same InMemorySessionStore
        instance as controller.session_store.

        If they differ, _reset_osce_state (which now writes through
        controller.session_store) and controller.run() would operate on
        different stores — the reset would be invisible to the controller.
        """
        self.assertIs(
            self.srv.default_store,
            self.ctrl.session_store,
            "server.default_store and controller.session_store must be the same object; "
            "if they diverge, _reset_osce_state writes to a store the controller never reads.",
        )

    # ── Test 2: Reset writes to the store the controller reads ────────────────

    def test_reset_clears_active_osce_in_real_store(self):
        """
        _reset_osce_state must clear osce_active/osce_step/current_case
        in the real controller.session_store so controller.run() sees a
        clean state.
        """
        SID = "real-store-reset-verify"
        self._seed_active_osce(SID)

        before = self.store.read(SID)
        self.assertTrue(before.osce_active)
        self.assertEqual(before.osce_step, 3)
        self.assertIsNotNone(before.current_case)

        self.srv._reset_osce_state(SID)

        after = self.store.read(SID)
        self.assertFalse(
            after.osce_active,
            "_reset_osce_state must clear osce_active in controller.session_store",
        )
        self.assertEqual(after.osce_step, 0)
        self.assertIsNone(after.current_case)

    # ── Test 3: State seen by controller has osce_active=False ───────────────

    def test_state_at_controller_entry_has_osce_active_false(self):
        """
        The state returned by controller._get_or_init_state (= the state that
        _apply_osce_override reads) must have osce_active=False after the
        reset — even when the session had osce_active=True before Start click.
        """
        from surgmentor.agent import controller as ctrl_mod
        from surgmentor.skills.osce_examiner_skill import OSCEExaminerSkill

        SID = "real-store-precheck"
        self._seed_active_osce(SID)

        captured = []
        orig_init = ctrl_mod.AgentController._get_or_init_state

        def capturing_get_or_init(self_ctrl, sid):
            state = orig_init(self_ctrl, sid)
            if sid == SID:
                captured.append({
                    "osce_active":  state.osce_active,
                    "osce_step":    state.osce_step,
                    "current_case": state.current_case,
                })
            return state

        with patch.object(ctrl_mod.AgentController,
                          "_get_or_init_state", capturing_get_or_init), \
             patch.object(OSCEExaminerSkill,
                          "_call_examiner_llm", return_value="INIT:Case text."):
            r = self.client.post("/api/osce/start", json={"session_id": SID})

        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(captured), 1,
                         "controller._get_or_init_state should be called exactly once")
        snap = captured[0]
        self.assertFalse(
            snap["osce_active"],
            "osce_active must be False at controller entry — "
            "_reset_osce_state must run before controller.run()",
        )
        self.assertEqual(snap["osce_step"], 0)
        self.assertIsNone(snap["current_case"])

    # ── Test 4: START_OSCE path, not OSCE_TURN ────────────────────────────────

    def test_intent_override_returns_start_osce_not_osce_turn(self):
        """
        _apply_osce_override must return START_OSCE (not OSCE_TURN) because
        the state has osce_active=False after _reset_osce_state.
        """
        from surgmentor.agent import controller as ctrl_mod
        from surgmentor.agent.intent import IntentCategory
        from surgmentor.skills.osce_examiner_skill import OSCEExaminerSkill

        SID = "real-store-intent-check"
        self._seed_active_osce(SID)

        overrides_seen = []
        orig_override = ctrl_mod.AgentController._apply_osce_override

        def capturing_override(self_ctrl, intent, state):
            result = orig_override(self_ctrl, intent, state)
            overrides_seen.append(result)
            return result

        with patch.object(ctrl_mod.AgentController,
                          "_apply_osce_override", capturing_override), \
             patch.object(OSCEExaminerSkill,
                          "_call_examiner_llm", return_value="INIT:Case."):
            self.client.post("/api/osce/start", json={"session_id": SID})

        self.assertEqual(len(overrides_seen), 1)
        self.assertEqual(
            overrides_seen[0],
            IntentCategory.START_OSCE,
            "_apply_osce_override must return START_OSCE; "
            "OSCE_TURN means osce_active was still True when controller.run() started.",
        )

    # ── Test 5: _init() ran — confirmed via current_case in the store ───────────

    def test_init_path_confirmed_by_current_case_in_store(self):
        """
        OSCEExaminerSkill._init() ALWAYS populates skill_result.updated_case
        (case selection from prepared_cases.json happens before the LLM call).
        _update_state(START_OSCE) then writes that dict to state.current_case.

        _turn() never touches current_case — _update_state(OSCE_TURN) only
        increments osce_step.  After _reset_osce_state(), current_case is None;
        if _turn() ran instead of _init(), current_case would remain None.

        Checking current_case in the store therefore proves _init() was reached
        without patching _call_examiner_llm — avoiding the LLM mock that is
        sensitive to import order and proxy-error behaviour in multi-file runs.
        """
        SID = "real-store-init-path"
        self._seed_active_osce(SID)

        r = self.client.post("/api/osce/start", json={"session_id": SID})

        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["osce_active"])
        self.assertEqual(body["osce_step"], 1,
                         "osce_step=1 after _init(); 0 means state was not updated at all")

        # current_case in the store is the definitive proof of _init() vs _turn()
        final_state = self.store.read(SID)
        self.assertIsNotNone(
            final_state.current_case,
            "_init() must be called — current_case=None means _turn() ran instead "
            "(OSCE_TURN only updates osce_step, never populates current_case).",
        )
        # The case must be freshly loaded (not the stale seeded one that was reset)
        self.assertNotEqual(
            final_state.current_case.get("case_id"), "old_case",
            "current_case must be a freshly loaded case, not the stale seeded state",
        )


# ── Module teardown ────────────────────────────────────────────────────────────

def tearDownModule():
    for path in (_tmp_db, _tmp_log):
        try:
            os.unlink(path)
        except OSError:
            pass
