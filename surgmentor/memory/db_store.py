# surgmentor/memory/db_store.py
"""
SQLite persistence — student profiles, OSCE results, session records.

This is the single source of truth for cross-session student data.
All reads and writes go through named functions here — no raw SQL
in skills, the controller, or anywhere else.

Schema:
  users           one row per student (student_id TEXT, display_name, dates)
  osce_results    one row per completed OSCE session
  topics_studied  one row per topic/diagnosis encountered
  agent_sessions  one row per agent session (start/end/message_count)

Key design decision: student_id is TEXT (UUID), not Telegram integer.
The competition demo is anonymous. This removes the Telegram dependency
entirely while preserving the get_student_stats() shape that
StudyPlannerSkill reads.

Design reference (read-only): surgery-rag/database.py
get_student_stats() is a near-direct port; schema adapts telegram_id
(INTEGER) → student_id (TEXT) and drops Telegram/web-specific tables.

Course concepts: Agent Skills (Day 3), Evaluation (Day 4)
"""

import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import AGENT_SESSION_DB_PATH

# ── Connection helper ─────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    """Open a connection to the agent SQLite DB with named-column access."""
    os.makedirs(os.path.dirname(os.path.abspath(AGENT_SESSION_DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(AGENT_SESSION_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Schema init ───────────────────────────────────────────────────────────────

def init_database() -> None:
    """
    Create all tables if they don't exist.
    Safe to call on every startup — CREATE TABLE IF NOT EXISTS is idempotent.
    """
    conn = _connect()
    c = conn.cursor()

    # ── USERS ─────────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            student_id    TEXT PRIMARY KEY,
            display_name  TEXT,
            joined_date   TEXT,
            last_active   TEXT
        )
    """)

    # ── AGENT SESSIONS ────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_sessions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    TEXT,
            mode          TEXT,
            started_at    TEXT,
            ended_at      TEXT,
            message_count INTEGER DEFAULT 0,
            FOREIGN KEY(student_id) REFERENCES users(student_id)
        )
    """)

    # ── OSCE RESULTS ──────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS osce_results (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    TEXT,
            case_id       TEXT,
            diagnosis     TEXT,
            score         INTEGER,
            feedback      TEXT,
            weak_areas    TEXT,
            completed_at  TEXT,
            FOREIGN KEY(student_id) REFERENCES users(student_id)
        )
    """)

    # ── TOPICS STUDIED ────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS topics_studied (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    TEXT,
            topic         TEXT,
            mode          TEXT,
            studied_at    TEXT,
            FOREIGN KEY(student_id) REFERENCES users(student_id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"✅  Database initialized at: {AGENT_SESSION_DB_PATH}")


# ── User management ───────────────────────────────────────────────────────────

def register_student(student_id: str, display_name: str = "Anonymous") -> None:
    """
    Register a new student or update their display_name and last_active time.
    Upsert — safe to call on every session start.
    """
    now = datetime.now().isoformat()
    conn = _connect()
    conn.execute("""
        INSERT INTO users (student_id, display_name, joined_date, last_active)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(student_id) DO UPDATE SET
            display_name = excluded.display_name,
            last_active  = excluded.last_active
    """, (student_id, display_name, now, now))
    conn.commit()
    conn.close()


def update_last_active(student_id: str) -> None:
    """Update the last_active timestamp for a student."""
    conn = _connect()
    conn.execute(
        "UPDATE users SET last_active = ? WHERE student_id = ?",
        (datetime.now().isoformat(), student_id),
    )
    conn.commit()
    conn.close()


# ── Session management ────────────────────────────────────────────────────────

def start_agent_session(student_id: str, mode: str) -> int:
    """
    Open a new agent session row and return its row ID.
    mode: 'chat' | 'osce'
    """
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        INSERT INTO agent_sessions (student_id, mode, started_at)
        VALUES (?, ?, ?)
    """, (student_id, mode, datetime.now().isoformat()))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id


def end_agent_session(session_id: int, message_count: int) -> None:
    """Close a session with its end timestamp and final message count."""
    conn = _connect()
    conn.execute("""
        UPDATE agent_sessions
        SET ended_at = ?, message_count = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), message_count, session_id))
    conn.commit()
    conn.close()


# ── OSCE results ──────────────────────────────────────────────────────────────

def save_osce_result(
    student_id: str,
    case_id:    str,
    diagnosis:  str,
    score:      int,
    feedback:   str,
    weak_areas: list[str],
) -> None:
    """Persist a completed OSCE session result."""
    conn = _connect()
    conn.execute("""
        INSERT INTO osce_results
            (student_id, case_id, diagnosis, score, feedback, weak_areas, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        student_id,
        case_id,
        diagnosis,
        score,
        feedback,
        ", ".join(weak_areas),
        datetime.now().isoformat(),
    ))
    conn.commit()
    conn.close()


# ── Topic tracking ────────────────────────────────────────────────────────────

def log_topics(student_id: str, cases: list, mode: str) -> None:
    """
    Log which diagnoses/topics a student encountered in a retrieval result.
    cases: list of CaseResult objects (from retrieval_tool) or dicts with
           a 'metadata' key containing 'diagnosis' and 'keywords'.
    Called after every RAG retrieval.
    """
    conn = _connect()
    c = conn.cursor()
    now = datetime.now().isoformat()

    for case in cases:
        # Accept both CaseResult objects and plain dicts
        meta = getattr(case, "metadata", None) or case.get("metadata", {})
        diagnosis = meta.get("diagnosis", "")
        keywords  = meta.get("keywords",  "")

        if diagnosis and diagnosis.lower() not in ("unknown", "not documented"):
            c.execute("""
                INSERT INTO topics_studied (student_id, topic, mode, studied_at)
                VALUES (?, ?, ?, ?)
            """, (student_id, diagnosis, mode, now))

        if keywords:
            for kw in keywords.split(";"):
                kw = kw.strip()
                if kw:
                    c.execute("""
                        INSERT INTO topics_studied (student_id, topic, mode, studied_at)
                        VALUES (?, ?, ?, ?)
                    """, (student_id, kw, mode, now))

    conn.commit()
    conn.close()


# ── Stats queries ─────────────────────────────────────────────────────────────

def get_student_stats(student_id: str) -> dict:
    """
    Return a comprehensive stats dict for one student. Used by StudyPlannerSkill.

    Returns {} if the student is not registered.

    Shape:
      user              dict (student_id, display_name, joined_date, last_active)
      sessions          dict (total, osce_count, chat_count, total_messages)
      osce              dict (total_osce, avg_score, best_score, worst_score)
      recent_osce       list[dict] — last 5 completed OSCE sessions
      top_topics        list[dict] — most-studied topics (topic, count)
      unique_diagnoses  int
      weak_areas        list[(topic, count)] — sorted by frequency desc, top 5
    """
    conn = _connect()
    c = conn.cursor()

    user_row = c.execute(
        "SELECT * FROM users WHERE student_id = ?", (student_id,)
    ).fetchone()

    if not user_row:
        conn.close()
        return {}

    sessions_row = c.execute("""
        SELECT
            COUNT(*)                                            AS total,
            SUM(CASE WHEN mode = 'osce' THEN 1 ELSE 0 END)   AS osce_count,
            SUM(CASE WHEN mode = 'chat' THEN 1 ELSE 0 END)   AS chat_count,
            COALESCE(SUM(message_count), 0)                   AS total_messages
        FROM agent_sessions
        WHERE student_id = ?
    """, (student_id,)).fetchone()

    osce_row = c.execute("""
        SELECT
            COUNT(*)    AS total_osce,
            AVG(score)  AS avg_score,
            MAX(score)  AS best_score,
            MIN(score)  AS worst_score
        FROM osce_results
        WHERE student_id = ?
    """, (student_id,)).fetchone()

    recent_osce = c.execute("""
        SELECT diagnosis, score, feedback, weak_areas, completed_at
        FROM osce_results
        WHERE student_id = ?
        ORDER BY completed_at DESC
        LIMIT 5
    """, (student_id,)).fetchall()

    top_topics = c.execute("""
        SELECT topic, COUNT(*) AS count
        FROM topics_studied
        WHERE student_id = ? AND topic NOT IN ('unknown', 'not documented', '')
        GROUP BY topic
        ORDER BY count DESC
        LIMIT 8
    """, (student_id,)).fetchall()

    unique_count = c.execute("""
        SELECT COUNT(DISTINCT topic) AS count
        FROM topics_studied
        WHERE student_id = ?
    """, (student_id,)).fetchone()

    weak_rows = c.execute("""
        SELECT weak_areas
        FROM osce_results
        WHERE student_id = ? AND weak_areas != ''
    """, (student_id,)).fetchall()

    conn.close()

    # Aggregate weak area frequency
    weak_counts: dict[str, int] = {}
    for row in weak_rows:
        for area in row["weak_areas"].split(","):
            area = area.strip()
            if area:
                weak_counts[area] = weak_counts.get(area, 0) + 1
    top_weak = sorted(weak_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "user":             dict(user_row),
        "sessions":         dict(sessions_row),
        "osce":             dict(osce_row),
        "recent_osce":      [dict(r) for r in recent_osce],
        "top_topics":       [dict(t) for t in top_topics],
        "unique_diagnoses": unique_count["count"],
        "weak_areas":       top_weak,
    }


# ── Standalone smoke test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    # Use a temp DB so the smoke test does not pollute the real data
    original_path = AGENT_SESSION_DB_PATH

    # Monkey-patch the module-level path for testing
    import surgmentor.memory.db_store as _self
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = f.name

    # Patch the module's config import
    import config as _cfg
    _cfg.AGENT_SESSION_DB_PATH = test_db

    # Re-read path in this module
    import importlib
    _self = importlib.import_module("surgmentor.memory.db_store")
    # Reload so the patched path takes effect

    print("=" * 60)
    print("db_store.py — smoke test (temp DB)")
    print("=" * 60)

    # Override path directly for this test
    _orig = __import__("config").AGENT_SESSION_DB_PATH

    # We test by overriding AGENT_SESSION_DB_PATH at the module level
    import surgmentor.memory.db_store as dbm
    dbm_orig_path = dbm.AGENT_SESSION_DB_PATH if hasattr(dbm, "AGENT_SESSION_DB_PATH") else None

    # For a simpler approach: test directly using functions with a temp path
    # by temporarily monkey-patching the config constant used inside _connect()
    import config
    config.AGENT_SESSION_DB_PATH = test_db

    # Reload the module to pick up the patched path
    import importlib
    import surgmentor.memory.db_store as dbmod
    importlib.reload(dbmod)

    dbmod.init_database()
    print("✅  init_database: OK")

    dbmod.register_student("test-001", "Test Student")
    print("✅  register_student: OK")

    sid = dbmod.start_agent_session("test-001", "osce")
    assert isinstance(sid, int) and sid > 0
    print(f"✅  start_agent_session: OK (id={sid})")

    dbmod.save_osce_result(
        "test-001", "case_1", "Appendicitis", 8,
        "Good systematic approach.", ["history taking", "imaging interpretation"]
    )
    print("✅  save_osce_result: OK")

    # Minimal CaseResult-like object for log_topics
    class _FakeCase:
        metadata = {"diagnosis": "Appendicitis", "keywords": "fever;RLQ pain"}

    dbmod.log_topics("test-001", [_FakeCase()], "osce")
    print("✅  log_topics: OK")

    dbmod.end_agent_session(sid, message_count=5)
    print("✅  end_agent_session: OK")

    stats = dbmod.get_student_stats("test-001")
    assert "user" in stats
    assert "sessions" in stats
    assert "osce" in stats
    assert "recent_osce" in stats
    assert "top_topics" in stats
    assert "weak_areas" in stats
    assert stats["osce"]["total_osce"] == 1
    assert stats["osce"]["best_score"] == 8
    assert len(stats["weak_areas"]) > 0
    print(f"✅  get_student_stats: OK")
    print(f"    avg_score={stats['osce']['avg_score']:.1f}, "
          f"weak_areas={stats['weak_areas']}")

    stats_missing = dbmod.get_student_stats("nonexistent-id")
    assert stats_missing == {}
    print("✅  get_student_stats (unknown student): returns {}")

    # Cleanup
    os.unlink(test_db)
    print(f"\n✅  All db_store smoke tests PASSED")
