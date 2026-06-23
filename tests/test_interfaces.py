# tests/test_interfaces.py
"""
Phase 5 — Entry Interface tests.

All sandbox-safe tests (Test01–Test07) run with CI_NO_LLM=1 and CI_NO_GRADIO=1.
They import only from surgmentor.ui.helpers and run.py helper functions —
never from app.py directly (Gradio cannot import in sandbox due to SOCKS proxy).

Patching note: run.py uses lazy imports inside run_repl() to avoid SOCKS proxy
errors at module level. Controller and session store are bound at call time via
  from surgmentor.agent.controller import controller
  from surgmentor.memory.session import default_store
Tests therefore patch the *source* module attributes rather than run.* names:
  patch("surgmentor.agent.controller.controller", mock)
  patch("surgmentor.memory.session.default_store", mock)
Python's from-import reads from the source module at the moment of the call, so
patching the source before the call intercepts correctly.

Test classes:
  Test01SessionIDGeneration   — UUID4 shape, uniqueness
  Test02OSCEFinishDetection   — marker strings, false-positive check
  Test03StatsMarkdownRenderer — onboarding message, full stats, empty sections
  Test04CLIHelpers            — welcome header, help text formatting
  Test05ValidateAPIKeys       — SystemExit on missing keys, pass-through on present
  Test06ControllerCallthrough — run_repl delegates to controller (mocked via source)
  Test07ErrorHandling         — controller exception -> friendly string (no raise)
  Test08GradioAppImport       — app.py imports and builds gr.Blocks (skipped in sandbox)
  Test09LiveCLIFlow           — live controller call via run_repl (skipped in CI)

Run (sandbox-safe):
  PYTHONPYCACHEPREFIX=/tmp/pycache_surgmentor CI_NO_LLM=1 CI_NO_GRADIO=1 \
    python -m unittest tests/test_interfaces.py -v

Run (native, all tests):
  python -m unittest tests/test_interfaces.py -v
"""

from __future__ import annotations

import importlib
import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# ── Sandbox setup ─────────────────────────────────────────────────────────────

import config
config.SCOPE_CLASSIFICATION_ENABLED = False

_tmp_db  = tempfile.NamedTemporaryFile(suffix=".db",    delete=False).name
_tmp_log = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False).name
config.AGENT_SESSION_DB_PATH = _tmp_db
config.EVAL_LOG_PATH         = _tmp_log

import surgmentor.memory.db_store   as db_store_module
import surgmentor.evaluation.logger as logger_module
importlib.reload(db_store_module)
importlib.reload(logger_module)
db_store_module.init_database()

# ── Feature flags ─────────────────────────────────────────────────────────────

_LIVE_LLM   = not os.getenv("CI_NO_LLM")
_HAS_GRADIO = not os.getenv("CI_NO_GRADIO")

# ── Import helpers under test ─────────────────────────────────────────────────

from surgmentor.ui.helpers import (
    create_session_id,
    validate_api_keys,
    detect_osce_finish,
    render_stats_markdown,
    format_welcome_header,
    format_help,
    OSCE_FINISH_MARKERS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: make a patched run_repl call
# ─────────────────────────────────────────────────────────────────────────────

def _run_repl_with_mock(
    stdin_text: str,
    mock_ctrl_run=None,
    mock_ctrl_side_effect=None,
    session_id: str = None,
) -> tuple[str, MagicMock, MagicMock]:
    """
    Run run_repl() with a mocked controller and mocked session store.

    Patches:
      surgmentor.agent.controller.controller  — intercepted by run_repl's from-import
      surgmentor.memory.session.default_store — intercepted by run_repl's from-import

    Returns (stdout_text, mock_controller, mock_store).
    """
    from run import run_repl

    if session_id is None:
        session_id = create_session_id()

    mock_ctrl = MagicMock()
    if mock_ctrl_side_effect is not None:
        mock_ctrl.run.side_effect = mock_ctrl_side_effect
    else:
        mock_ctrl.run.return_value = mock_ctrl_run or "Mock response."

    mock_store = MagicMock()
    mock_store.clear = MagicMock()

    out = io.StringIO()
    err = io.StringIO()

    import surgmentor.agent.controller as ctrl_mod
    import surgmentor.memory.session as sess_mod

    with patch.object(ctrl_mod, "controller", mock_ctrl), \
         patch.object(sess_mod, "default_store", mock_store), \
         patch("sys.stdin",  io.StringIO(stdin_text)), \
         patch("sys.stdout", out), \
         patch("sys.stderr", err):
        run_repl(session_id, debug=False)

    return out.getvalue(), mock_ctrl, mock_store


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Session ID generation
# ─────────────────────────────────────────────────────────────────────────────

class Test01SessionIDGeneration(unittest.TestCase):

    def test_is_string(self):
        self.assertIsInstance(create_session_id(), str)

    def test_uuid4_format(self):
        sid = create_session_id()
        parts = sid.split("-")
        self.assertEqual(len(parts), 5)
        self.assertEqual([len(p) for p in parts], [8, 4, 4, 4, 12])

    def test_all_hex(self):
        sid = create_session_id().replace("-", "")
        self.assertTrue(all(c in "0123456789abcdef" for c in sid), sid)

    def test_uniqueness(self):
        ids = {create_session_id() for _ in range(50)}
        self.assertEqual(len(ids), 50)

    def test_version_4(self):
        # Version 4 UUIDs have the 13th hex char (index 14 with dashes) == '4'
        sid = create_session_id()
        self.assertEqual(sid[14], "4")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — OSCE finish detection
# ─────────────────────────────────────────────────────────────────────────────

class Test02OSCEFinishDetection(unittest.TestCase):

    def test_detects_score_colon(self):
        self.assertTrue(detect_osce_finish("Score: 7/10"))

    def test_detects_final_score(self):
        self.assertTrue(detect_osce_finish("Final Score: 8 out of 10"))

    def test_detects_session_complete(self):
        self.assertTrue(detect_osce_finish("Session complete. Well done."))

    def test_detects_lowercase_score(self):
        self.assertTrue(detect_osce_finish("Your score: 6/10."))

    def test_does_not_false_positive_on_normal_turn(self):
        self.assertFalse(
            detect_osce_finish("What investigations would you order for this patient?")
        )

    def test_does_not_false_positive_on_history_question(self):
        self.assertFalse(
            detect_osce_finish("Please take a focused history from the patient.")
        )

    def test_empty_string_returns_false(self):
        self.assertFalse(detect_osce_finish(""))

    def test_all_markers_covered(self):
        for marker in OSCE_FINISH_MARKERS:
            self.assertTrue(
                detect_osce_finish(f"Prefix {marker} suffix"),
                msg=f"Marker not detected: {marker!r}",
            )

    def test_returns_bool(self):
        result = detect_osce_finish("Score: 9")
        self.assertIsInstance(result, bool)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — Stats Markdown renderer
# ─────────────────────────────────────────────────────────────────────────────

class Test03StatsMarkdownRenderer(unittest.TestCase):

    def test_none_returns_onboarding(self):
        md = render_stats_markdown(None)
        self.assertIn("No OSCE sessions", md)

    def test_empty_dict_returns_onboarding(self):
        md = render_stats_markdown({})
        self.assertIn("No OSCE sessions", md)

    def _sample_stats(self, **overrides):
        base = {
            "sessions":  {"total": 5},
            "osce":      {"total_osce": 3, "avg_score": 7.25,
                          "best_score": 9, "worst_score": 5},
            "recent_osce": [
                {"diagnosis": "Appendicitis", "score": 9,
                 "completed_at": "2026-06-20T10:00:00"},
            ],
            "weak_areas":       [("History taking", 2), ("Management", 1)],
            "top_topics":       ["Appendicitis", "Cholecystitis"],
            "unique_diagnoses": ["Appendicitis", "Cholecystitis"],
        }
        base.update(overrides)
        return base

    def test_avg_score_formatted_to_two_dp(self):
        md = render_stats_markdown(self._sample_stats())
        self.assertIn("7.25", md)

    def test_best_worst_present(self):
        md = render_stats_markdown(self._sample_stats())
        self.assertIn("9", md)
        self.assertIn("5", md)

    def test_weak_areas_listed(self):
        md = render_stats_markdown(self._sample_stats())
        self.assertIn("History taking", md)
        self.assertIn("Management", md)

    def test_recent_result_listed(self):
        md = render_stats_markdown(self._sample_stats())
        self.assertIn("Appendicitis", md)

    def test_date_truncated_to_10_chars(self):
        md = render_stats_markdown(self._sample_stats())
        self.assertIn("2026-06-20", md)

    def test_empty_weak_areas_section_omitted(self):
        stats = self._sample_stats(weak_areas=[])
        md = render_stats_markdown(stats)
        self.assertNotIn("Weak Areas", md)

    def test_empty_recent_section_omitted(self):
        stats = self._sample_stats(recent_osce=[])
        md = render_stats_markdown(stats)
        self.assertNotIn("Recent OSCE Results", md)

    def test_returns_string(self):
        self.assertIsInstance(render_stats_markdown(None), str)
        self.assertIsInstance(render_stats_markdown(self._sample_stats()), str)

    def test_none_avg_score_renders_dash(self):
        stats = self._sample_stats()
        stats["osce"]["avg_score"] = None
        md = render_stats_markdown(stats)
        self.assertIn("—", md)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — CLI helpers
# ─────────────────────────────────────────────────────────────────────────────

class Test04CLIHelpers(unittest.TestCase):

    def test_welcome_header_contains_surgmentor(self):
        sid = create_session_id()
        header = format_welcome_header(sid)
        self.assertIn("SurgMentor", header)

    def test_welcome_header_contains_session_id(self):
        sid = create_session_id()
        header = format_welcome_header(sid)
        self.assertIn(sid, header)

    def test_welcome_header_is_string(self):
        self.assertIsInstance(format_welcome_header(create_session_id()), str)

    def test_help_text_is_nonempty_string(self):
        h = format_help()
        self.assertIsInstance(h, str)
        self.assertGreater(len(h), 20)

    def test_help_text_mentions_exit(self):
        self.assertIn("exit", format_help().lower())

    def test_help_text_mentions_reset(self):
        self.assertIn("reset", format_help().lower())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — validate_api_keys
# ─────────────────────────────────────────────────────────────────────────────

class Test05ValidateAPIKeys(unittest.TestCase):

    def test_raises_system_exit_on_missing_deepseek_key(self):
        with patch.object(config, "DEEPSEEK_API_KEY", ""):
            with self.assertRaises(SystemExit) as ctx:
                validate_api_keys()
            self.assertEqual(ctx.exception.code, 1)

    def test_raises_system_exit_on_missing_jina_key(self):
        with patch.object(config, "DEEPSEEK_API_KEY", "fake-key"):
            with patch.object(config, "JINA_API_KEY", ""):
                with self.assertRaises(SystemExit) as ctx:
                    validate_api_keys()
                self.assertEqual(ctx.exception.code, 1)

    def test_passes_when_both_keys_present(self):
        with patch.object(config, "DEEPSEEK_API_KEY", "fake-deepseek"):
            with patch.object(config, "JINA_API_KEY", "fake-jina"):
                try:
                    validate_api_keys()
                except SystemExit:
                    self.fail("validate_api_keys raised SystemExit with valid keys")

    def test_exit_code_is_1_not_0(self):
        with patch.object(config, "DEEPSEEK_API_KEY", ""):
            try:
                validate_api_keys()
            except SystemExit as e:
                self.assertNotEqual(e.code, 0)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — Controller callthrough (run_repl with mocked controller)
# ─────────────────────────────────────────────────────────────────────────────

class Test06ControllerCallthrough(unittest.TestCase):
    """
    Verify that run_repl() calls controller.run() for normal input.

    Patches surgmentor.agent.controller.controller so that when run_repl
    does 'from surgmentor.agent.controller import controller', it gets the mock.
    """

    def test_response_printed_to_stdout(self):
        out, _, _ = _run_repl_with_mock(
            "show me a case\n",
            mock_ctrl_run="Case: Appendicitis",
        )
        self.assertIn("Case: Appendicitis", out)

    def test_controller_called_with_input(self):
        sid = create_session_id()
        _, mock_ctrl, _ = _run_repl_with_mock(
            "show me a case\n",
            mock_ctrl_run="Response.",
            session_id=sid,
        )
        mock_ctrl.run.assert_called_once_with("show me a case", sid)

    def test_exit_command_breaks_loop(self):
        out, mock_ctrl, _ = _run_repl_with_mock("exit\n")
        self.assertIn("Farewell", out)
        mock_ctrl.run.assert_not_called()

    def test_help_command_prints_help(self):
        out, mock_ctrl, _ = _run_repl_with_mock("help\nexit\n")
        self.assertIn("exit", out.lower())
        mock_ctrl.run.assert_not_called()

    def test_empty_input_not_forwarded(self):
        out, mock_ctrl, _ = _run_repl_with_mock("\n\nexit\n")
        mock_ctrl.run.assert_not_called()

    def test_quit_also_exits(self):
        out, mock_ctrl, _ = _run_repl_with_mock("quit\n")
        self.assertIn("Farewell", out)
        mock_ctrl.run.assert_not_called()

    def test_multiple_turns_call_controller_each_time(self):
        _, mock_ctrl, _ = _run_repl_with_mock(
            "query one\nquery two\nexit\n",
            mock_ctrl_run="Response",
        )
        self.assertEqual(mock_ctrl.run.call_count, 2)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 — Error handling
# ─────────────────────────────────────────────────────────────────────────────

class Test07ErrorHandling(unittest.TestCase):

    def test_controller_exception_repl_does_not_raise(self):
        """When controller.run() raises, run_repl prints error and continues."""
        # Should not raise — exits cleanly after 'exit'
        out, _, _ = _run_repl_with_mock(
            "show me a case\nexit\n",
            mock_ctrl_side_effect=RuntimeError("boom"),
        )
        self.assertIn("[Error]", out)

    def test_second_turn_works_after_error(self):
        """REPL continues after a controller error."""
        out, _, _ = _run_repl_with_mock(
            "query1\nquery2\nexit\n",
            mock_ctrl_side_effect=[RuntimeError("first fails"), "Second OK"],
        )
        self.assertIn("Second OK", out)

    def test_reset_clears_session_and_creates_new_id(self):
        """Typing 'reset' calls store.clear() and generates a new session ID."""
        sid = "fixed-session-abc"
        out, _, mock_store = _run_repl_with_mock(
            "reset\nexit\n",
            session_id=sid,
        )
        mock_store.clear.assert_called_once_with(sid)
        self.assertIn("Session reset", out)

    def test_keyboard_interrupt_exits_cleanly(self):
        """KeyboardInterrupt prints farewell and exits without traceback."""
        from run import run_repl
        import surgmentor.agent.controller as ctrl_mod
        import surgmentor.memory.session as sess_mod

        mock_ctrl = MagicMock()
        mock_store = MagicMock()
        out = io.StringIO()

        # Simulate Ctrl+C on the first input() call
        with patch.object(ctrl_mod, "controller", mock_ctrl), \
             patch.object(sess_mod, "default_store", mock_store), \
             patch("builtins.input", side_effect=KeyboardInterrupt), \
             patch("sys.stdout", out):
            run_repl(create_session_id())

        self.assertIn("Farewell", out.getvalue())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8 — Gradio app import (skipped in sandbox)
# ─────────────────────────────────────────────────────────────────────────────

@unittest.skipIf(not _HAS_GRADIO, "Gradio not available in sandbox (CI_NO_GRADIO=1)")
class Test08GradioAppImport(unittest.TestCase):

    def test_app_module_importable(self):
        with patch.object(config, "DEEPSEEK_API_KEY", "fake-dk"), \
             patch.object(config, "JINA_API_KEY",     "fake-jina"):
            import app as app_module
            self.assertTrue(hasattr(app_module, "build_app"))

    def test_build_app_returns_blocks(self):
        import gradio as gr
        with patch.object(config, "DEEPSEEK_API_KEY", "fake-dk"), \
             patch.object(config, "JINA_API_KEY",     "fake-jina"):
            import app as app_module
            blocks = app_module.build_app()
            self.assertIsInstance(blocks, gr.Blocks)

    def test_app_has_safe_run_helper(self):
        with patch.object(config, "DEEPSEEK_API_KEY", "fake-dk"), \
             patch.object(config, "JINA_API_KEY",     "fake-jina"):
            import app as app_module
            self.assertTrue(callable(getattr(app_module, "_safe_run", None)))


# ─────────────────────────────────────────────────────────────────────────────
# TEST 9 — Live integration (native machine only)
# ─────────────────────────────────────────────────────────────────────────────

@unittest.skipIf(not _LIVE_LLM, "Live LLM tests: run without CI_NO_LLM=1")
class Test09LiveCLIFlow(unittest.TestCase):

    def test_live_retrieve_case_via_repl(self):
        from run import run_repl
        sid = create_session_id()
        out = io.StringIO()
        with patch("sys.stdin",  io.StringIO("show me a case about appendicitis\nexit\n")), \
             patch("sys.stdout", out):
            run_repl(sid)
        self.assertIn("Sources:", out.getvalue())

    def test_live_osce_flow_via_repl(self):
        from run import run_repl
        sid = create_session_id()
        out = io.StringIO()
        inputs = "start osce\nI would take a systematic history\nfinish\nexit\n"
        with patch("sys.stdin",  io.StringIO(inputs)), \
             patch("sys.stdout", out):
            run_repl(sid)
        output = out.getvalue()
        self.assertTrue(
            any(m in output for m in ["Score:", "score:", "Session complete"]),
            f"Score not in output:\n{output[:500]}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Module teardown
# ─────────────────────────────────────────────────────────────────────────────

def tearDownModule():
    for path in (_tmp_db, _tmp_log):
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    unittest.main()
