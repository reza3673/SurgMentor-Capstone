# surgmentor/evaluation/logger.py
"""
Evaluation logger — structured signal recording for every agent cycle.

Implements the Day 4 principle: evaluation is first-class, not optional.
Writes two types of records to eval_log.jsonl (one JSON object per line):

  TurnSignal       — emitted after every controller cycle
  SessionEvaluation — emitted at the end of each OSCE session

The eval_log.jsonl file is machine-readable and can be inspected by judges
as evidence of the evaluation architecture.

Design: intentionally minimal. This module's job is to write records.
Scoring logic lives in EvaluationSkill (Phase 3). The controller decides
when to call these functions (Phase 4).

Course concept: Evaluation (Day 4)
"""

import dataclasses
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import EVAL_LOG_PATH


# ── Signal dataclasses ────────────────────────────────────────────────────────

@dataclass
class TurnSignal:
    """
    Emitted after every agent controller cycle (one per user turn).
    Records routing decisions and output characteristics for later analysis.
    """
    session_id:         str
    intent_classified:  str           # IntentCategory name (Phase 3)
    skill_selected:     str           # Skill class name (Phase 3)
    output_safety_pass: bool          # True if output filter passed (Phase 2)
    response_length:    int           # character count of assistant response
    latency_ms:         int           # wall-clock time for the full cycle
    timestamp:          str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SessionEvaluation:
    """
    Emitted once at the end of each completed OSCE session.
    Summarises the student's performance for that case.
    """
    session_id:        str
    student_id:        str
    case_id:           str
    osce_score:        int            # 0-10
    rubric_breakdown:  dict           # {criterion: score, ...}
    weak_areas:        list[str]
    safety_events:     int            # count of output filter interventions
    completion_status: str            # "COMPLETED" | "ABANDONED" | "INCOMPLETE"
    feedback_text:     str
    timestamp:         str = field(default_factory=lambda: datetime.now().isoformat())


# ── Writer functions ──────────────────────────────────────────────────────────

def _append_record(record: dict) -> None:
    """Append one JSON line to the eval log. Creates the file if absent."""
    log_path = EVAL_LOG_PATH
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True) if os.path.dirname(log_path) else None
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_turn_signal(signal: TurnSignal) -> None:
    """Append a TurnSignal as one JSON line to eval_log.jsonl."""
    record = dataclasses.asdict(signal)
    record["_type"] = "turn_signal"
    _append_record(record)


def write_session_evaluation(evaluation: SessionEvaluation) -> None:
    """Append a SessionEvaluation as one JSON line to eval_log.jsonl."""
    record = dataclasses.asdict(evaluation)
    record["_type"] = "session_evaluation"
    _append_record(record)


# ── Standalone smoke test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile
    import config

    print("=" * 60)
    print("logger.py — smoke test")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        test_log_path = f.name

    # Patch EVAL_LOG_PATH for the duration of the test
    config.EVAL_LOG_PATH = test_log_path
    import importlib
    import surgmentor.evaluation.logger as logmod
    importlib.reload(logmod)

    # 1. TurnSignal
    ts = logmod.TurnSignal(
        session_id="sess-001",
        intent_classified="OSCE_TURN",
        skill_selected="OSCEExaminerSkill",
        output_safety_pass=True,
        response_length=420,
        latency_ms=1234,
    )
    logmod.write_turn_signal(ts)
    print("✅  write_turn_signal: OK")

    # 2. SessionEvaluation
    se = logmod.SessionEvaluation(
        session_id="sess-001",
        student_id="student-42",
        case_id="case_1",
        osce_score=8,
        rubric_breakdown={"history": 8, "examination": 7, "diagnosis": 9},
        weak_areas=["imaging interpretation"],
        safety_events=0,
        completion_status="COMPLETED",
        feedback_text="Good systematic approach. Work on imaging.",
    )
    logmod.write_session_evaluation(se)
    print("✅  write_session_evaluation: OK")

    # 3. Verify file has two valid JSON lines
    with open(test_log_path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"
    rec1 = json.loads(lines[0])
    rec2 = json.loads(lines[1])

    assert rec1["_type"] == "turn_signal"
    assert rec1["session_id"] == "sess-001"
    assert rec1["output_safety_pass"] is True
    assert rec1["latency_ms"] == 1234
    print("✅  TurnSignal JSON line: valid")

    assert rec2["_type"] == "session_evaluation"
    assert rec2["osce_score"] == 8
    assert rec2["completion_status"] == "COMPLETED"
    assert "imaging interpretation" in rec2["weak_areas"]
    print("✅  SessionEvaluation JSON line: valid")

    # 4. Timestamps are present
    assert "timestamp" in rec1
    assert "timestamp" in rec2
    print("✅  Timestamps present in both records")

    # Cleanup
    os.unlink(test_log_path)
    print(f"\n✅  All logger smoke tests PASSED")
    print(f"    Eval log path (production): {EVAL_LOG_PATH}")
