# surgmentor/memory/session.py
"""
Session memory — per-conversation state management.

SessionState holds everything the AgentController needs to route correctly
and every skill needs to produce coherent responses across turns.

InMemorySessionStore is the default backend (acceptable for competition demo).
State is lost on process restart — cross-session student data is persisted
separately in db_store.py so personalization survives restarts.

Design notes:
  - History windowing is NOT done here. The session store owns the full
    record. Trimming is done in agent/context.py (Phase 4) when building
    the per-skill context bundle. This is the Day 1 context engineering
    principle: each skill sees only the context it needs.
  - HISTORY_WINDOW is imported from config so Phase 4 context builders
    can reference it without re-importing config themselves.

Course concepts: Agent Architecture (Day 2), Context Engineering (Day 1)
"""

import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import HISTORY_WINDOW  # re-exported for context builders in Phase 4


# ── State dataclass ───────────────────────────────────────────────────────────

@dataclass
class SessionState:
    """
    Complete per-session agent state. All fields needed by the controller
    and skills across a single conversation are stored here.

    Ephemeral by design — lost on process restart. Student profile data
    (scores, weak areas, topics studied) is persisted in db_store.py.
    """
    session_id:           str
    student_id:           str
    mode:                 str              # "chat" | "osce"
    osce_active:          bool = False
    osce_step:            int  = 0        # 0 = not started
    current_case:         dict | None = None
    conversation_history: list[dict] = field(default_factory=list)
    # [{role: "user"|"assistant", content: str}, ...]
    weak_areas:           list[str]  = field(default_factory=list)
    score_history:        list[dict] = field(default_factory=list)
    last_active:          str        = field(default_factory=lambda: datetime.now().isoformat())
    osce_history_start_index: int    = 0  # index into conversation_history where current OSCE started


def make_default_state(session_id: str, student_id: str, mode: str = "chat") -> SessionState:
    """Create a fresh SessionState with safe defaults."""
    return SessionState(
        session_id=session_id,
        student_id=student_id,
        mode=mode,
    )


# ── In-memory store ───────────────────────────────────────────────────────────

class InMemorySessionStore:
    """
    Thread-unsafe in-memory session store. Suitable for the single-process
    Gradio demo. If multi-process deployment is needed, replace this with a
    Redis-backed store without changing the interface.

    Interface:
      read(session_id)            -> SessionState  (creates default if absent)
      write(session_id, state)    -> None
      clear(session_id)           -> None
      list_active()               -> list[str]     (all known session IDs)
    """

    def __init__(self) -> None:
        self._store: dict[str, SessionState] = {}

    def read(self, session_id: str, student_id: str = "", mode: str = "chat") -> SessionState:
        """
        Return the SessionState for session_id.
        Creates and stores a default state if none exists.

        student_id and mode are only used when creating a new state —
        they are ignored if the session already exists.
        """
        if session_id not in self._store:
            self._store[session_id] = make_default_state(
                session_id=session_id,
                student_id=student_id or session_id,
                mode=mode,
            )
        return self._store[session_id]

    def write(self, session_id: str, state: SessionState) -> None:
        """Persist updated state back to the store."""
        state.last_active = datetime.now().isoformat()
        self._store[session_id] = state

    def clear(self, session_id: str) -> None:
        """Remove a session from the store (e.g. after logout or reset)."""
        self._store.pop(session_id, None)

    def list_active(self) -> list[str]:
        """Return all session IDs currently held in the store."""
        return list(self._store.keys())


# ── Module-level default store ────────────────────────────────────────────────
# The controller imports and uses this singleton.
# Tests that need isolation should instantiate their own InMemorySessionStore.

default_store = InMemorySessionStore()


# ── Standalone smoke test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("session.py — smoke test")
    print("=" * 60)

    store = InMemorySessionStore()

    # 1. Read non-existent session creates default
    state = store.read("s1", student_id="student-42", mode="chat")
    assert state.session_id == "s1"
    assert state.student_id == "student-42"
    assert state.mode == "chat"
    assert state.osce_active is False
    assert state.osce_step == 0
    assert state.current_case is None
    assert state.conversation_history == []
    assert state.weak_areas == []
    assert state.score_history == []
    print("✅  read (new session): default state created correctly")

    # 2. Write and read back
    state.osce_active = True
    state.osce_step = 2
    state.current_case = {"id": "case_1", "diagnosis": "Appendicitis"}
    state.conversation_history.append({"role": "user", "content": "The patient has RLQ pain."})
    state.weak_areas = ["history taking"]
    store.write("s1", state)

    retrieved = store.read("s1")
    assert retrieved.osce_active is True
    assert retrieved.osce_step == 2
    assert retrieved.current_case["diagnosis"] == "Appendicitis"
    assert len(retrieved.conversation_history) == 1
    assert retrieved.weak_areas == ["history taking"]
    print("✅  write + read: round-trip OK")

    # 3. Second session is independent
    state2 = store.read("s2", student_id="student-99", mode="osce")
    assert state2.session_id == "s2"
    assert state2.osce_active is False  # independent of s1
    print("✅  independent sessions: OK")

    # 4. list_active
    active = store.list_active()
    assert "s1" in active
    assert "s2" in active
    print(f"✅  list_active: {active}")

    # 5. clear
    store.clear("s1")
    active = store.list_active()
    assert "s1" not in active
    assert "s2" in active
    print("✅  clear: OK")

    # 6. Read after clear creates fresh state
    fresh = store.read("s1", student_id="student-42")
    assert fresh.osce_active is False
    assert fresh.conversation_history == []
    print("✅  read after clear: fresh state created")

    # 7. HISTORY_WINDOW is importable
    assert isinstance(HISTORY_WINDOW, int) and HISTORY_WINDOW > 0
    print(f"✅  HISTORY_WINDOW = {HISTORY_WINDOW} (imported from config)")

    # 8. default_store singleton exists
    assert isinstance(default_store, InMemorySessionStore)
    print("✅  default_store singleton: OK")

    print(f"\n✅  All session smoke tests PASSED")
