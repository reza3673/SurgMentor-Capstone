# surgmentor/ui/helpers.py
"""
Pure-Python UI helpers shared by run.py and app.py.

Extracted into this module so the logic can be tested in the sandbox without
importing Gradio (which fails in the sandbox due to SOCKS proxy initialisation).

All functions here are stateless and have no external dependencies beyond the
standard library and surgmentor.* modules (which use lazy LLM imports).

Public API:
  create_session_id()         -> str
  validate_api_keys()         -> None   (raises SystemExit on missing keys)
  detect_osce_finish(text)    -> bool
  render_stats_markdown(stats)-> str
  format_welcome_header(sid)  -> str

Course concept: Deployability (Day 5) — clean separation between UI shell and
core logic makes the system portable across CLI and Gradio without code duplication.
"""

from __future__ import annotations

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ── OSCE finish detection ─────────────────────────────────────────────────────

# These strings appear in EvaluationSkill output when a session is scored.
# Used by app.py to decide whether to display the Score panel.
#
# Why string-based detection? The controller returns a plain str to the UI,
# not a typed SkillResult. Passing typed results would couple app.py to skill
# internals. String markers keep the UI layer independent of skill internals:
# any future EvaluationSkill change just needs to preserve one marker string.
OSCE_FINISH_MARKERS = [
    "Score:",
    "score:",
    "Final Score",
    "final score",
    "session complete",
    "Session complete",
    "overall score",
    "Overall Score",
]


def detect_osce_finish(response: str) -> bool:
    """
    Return True if `response` looks like a FINISH_OSCE result from EvaluationSkill.

    Uses a simple multi-marker check — no regex required. The markers are
    strings that appear in every EvaluationSkill response and do not appear
    in mid-session examiner turns.

    Args:
        response: The string returned by controller.run().

    Returns:
        True if at least one OSCE_FINISH_MARKERS string is present.
    """
    return any(marker in response for marker in OSCE_FINISH_MARKERS)


# ── Session ID ────────────────────────────────────────────────────────────────

def create_session_id() -> str:
    """
    Return a new UUID4 string suitable as a session/student identifier.

    Each call produces a unique ID. Run.py calls this once per process.
    App.py calls this once per Gradio user session (on state initialisation).
    """
    return str(uuid.uuid4())


# ── API key validation ────────────────────────────────────────────────────────

_REQUIRED_KEYS = ("DEEPSEEK_API_KEY", "JINA_API_KEY")


def validate_api_keys() -> None:
    """
    Verify that all required API keys are present and non-empty in config.

    Imports config lazily to avoid a SOCKS proxy error during sandbox imports
    (config.py only reads from os.environ / .env, but some downstream
    singletons may initialise during the import chain).

    Raises:
        SystemExit(1) if any required key is missing or empty.
    """
    try:
        import config as cfg
        missing = [k for k in _REQUIRED_KEYS if not getattr(cfg, k, "")]
    except Exception as exc:
        print(f"[Error] Could not load config: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if missing:
        for key in missing:
            print(
                f"[Error] Required environment variable {key!r} is not set.\n"
                f"        Add it to your .env file and restart.",
                file=sys.stderr,
            )
        raise SystemExit(1)


# ── Welcome header ────────────────────────────────────────────────────────────

_BANNER = """\
╔══════════════════════════════════════════════════════╗
║          SurgMentor — Agentic OSCE Trainer           ║
║          Kaggle AI Agents Intensive 2026             ║
╚══════════════════════════════════════════════════════╝"""

_HELP_TEXT = """\
Commands:
  <any text>    Send a message to the agent
  reset         Start a new session (clears history)
  help          Show this help
  exit / quit   Exit SurgMentor

Suggested inputs:
  "show me a case about appendicitis"
  "start osce"
  "what should I study"
  "how did I do"
"""


def format_welcome_header(session_id: str) -> str:
    """Return the startup banner printed by run.py."""
    return (
        f"{_BANNER}\n"
        f"Session ID : {session_id}\n"
        f"Type 'help' for available commands.\n"
        f"{'─' * 54}"
    )


def format_help() -> str:
    """Return the help text for run.py."""
    return _HELP_TEXT


# ── Stats Markdown renderer ───────────────────────────────────────────────────

_ONBOARDING_STATS = (
    "No OSCE sessions completed yet. Complete a session in the **OSCE** tab "
    "to see your profile here."
)


def render_stats_markdown(stats: dict | None) -> str:
    """
    Render a db_store.get_student_stats() result as a Gradio-compatible
    Markdown string.

    Args:
        stats: The dict returned by db_store.get_student_stats(), or None
               if the student has no history.

    Returns:
        A Markdown-formatted string for display in a gr.Markdown component.
        If stats is None or empty, returns the onboarding message.
    """
    if not stats:
        return _ONBOARDING_STATS

    osce      = stats.get("osce",        {})
    sessions  = stats.get("sessions",    {})
    recent    = stats.get("recent_osce", [])
    weak      = stats.get("weak_areas",  [])     # list of (topic, count)
    topics    = stats.get("top_topics",  [])
    diagnoses = stats.get("unique_diagnoses", [])

    total_sessions = sessions.get("total", 0)
    total_osce     = osce.get("total_osce", 0)
    avg_score      = osce.get("avg_score",  None)
    best_score     = osce.get("best_score", None)
    worst_score    = osce.get("worst_score", None)

    # Header table
    avg_str   = f"{avg_score:.2f} / 10" if avg_score is not None else "—"
    best_str  = str(best_score)  if best_score  is not None else "—"
    worst_str = str(worst_score) if worst_score is not None else "—"

    lines = [
        "## Your Performance Summary\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Sessions completed | {total_sessions} |",
        f"| OSCE cases attempted | {total_osce} |",
        f"| Average score | {avg_str} |",
        f"| Best score | {best_str} |",
        f"| Worst score | {worst_str} |",
    ]

    # Weak areas
    if weak:
        lines.append("\n### Weak Areas\n")
        for i, (topic, count) in enumerate(weak[:5], 1):
            lines.append(
                f"{i}. {topic} ({count} occurrence{'s' if count != 1 else ''})"
            )

    # Recent results
    if recent:
        lines.append("\n### Recent OSCE Results\n")
        for r in recent[:5]:
            diagnosis = r.get("diagnosis", "Unknown")
            score     = r.get("score", "?")
            date      = str(r.get("completed_at", ""))[:10]
            lines.append(f"- {date}  **{diagnosis}**: {score}/10")

    # Topics studied
    if topics:
        topic_list = ", ".join(str(t) for t in topics[:10])
        lines.append(f"\n### Topics Studied\n{topic_list}")

    if diagnoses:
        lines.append(
            f"\n_Unique diagnoses encountered: {len(diagnoses)}_"
        )

    return "\n".join(lines)


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("helpers.py — smoke test")

    sid = create_session_id()
    assert len(sid) == 36 and sid.count("-") == 4, "UUID4 format"
    print(f"✅  create_session_id: {sid}")

    assert detect_osce_finish("Score: 7/10") is True
    assert detect_osce_finish("What would you do next?") is False
    print("✅  detect_osce_finish: OK")

    md = render_stats_markdown(None)
    assert "No OSCE sessions" in md
    print("✅  render_stats_markdown (None): onboarding message")

    sample = {
        "sessions": {"total": 3},
        "osce": {"total_osce": 2, "avg_score": 7.5, "best_score": 9, "worst_score": 6},
        "recent_osce": [{"diagnosis": "Appendicitis", "score": 9, "completed_at": "2026-06-20"}],
        "weak_areas":  [("History taking", 2)],
        "top_topics":  ["Appendicitis"],
        "unique_diagnoses": ["Appendicitis"],
    }

    md2 = render_stats_markdown(sample)
    assert "7.50 / 10" in md2
    assert "History taking" in md2
    print("\u2705  render_stats_markdown (with data): OK")

    header = format_welcome_header(sid)
    assert "SurgMentor" in header and sid in header
    print("\u2705  format_welcome_header: OK")

    print("\n\u2705  All helpers smoke tests PASSED")
