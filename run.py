# run.py
"""
SurgMentor — CLI Entry Point

Interactive REPL for terminal-based testing, debugging, and development.
All student input passes through AgentController.run() — the exact same path
used by the Gradio interface, so responses are identical in both surfaces.

Usage:
  python run.py           # normal mode
  python run.py --debug   # print exception tracebacks on controller errors

Session notes:
  - A new UUID4 session ID is generated on each process startup.
  - Typing "reset" generates a new session ID and clears session memory.
  - Typing "exit" or "quit" terminates the REPL.
  - All turns are logged to eval_log.jsonl via the TurnSignal mechanism.

Course concept: Deployability (Day 5) — the CLI demonstrates that the agent
runs locally without any cloud infrastructure, login, or browser.
"""

from __future__ import annotations

import argparse
import sys
import os

# Path bootstrap — allows running from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Pure-Python helpers (no Gradio, no LLM)
from surgmentor.ui.helpers import (
    create_session_id,
    validate_api_keys,
    format_welcome_header,
    format_help,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SurgMentor CLI — agentic surgical OSCE trainer"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Print exception tracebacks on controller errors",
    )
    return parser.parse_args()


def _init() -> None:
    """
    Startup sequence:
      1. Validate API keys (SystemExit(1) on failure)
      2. Initialise SQLite schema
    """
    validate_api_keys()
    import surgmentor.memory.db_store as db_store
    db_store.init_database()


def run_repl(session_id: str, debug: bool = False) -> None:
    """
    Main REPL loop.

    PERCEIVE — read user input
    ACT      — forward to controller.run()
    RESPOND  — print result

    The controller handles all classification, skill routing, security,
    and state management internally.

    Args:
        session_id: UUID4 string used as both session key and student ID.
        debug:      If True, print exception tracebacks instead of generic error.
    """
    # Lazy import: avoids SOCKS proxy error at module level in some environments
    from surgmentor.agent.controller import controller
    from surgmentor.memory.session import default_store

    print(format_welcome_header(session_id))
    print()

    # nonlocal-style mutable container so reset can update session_id
    state = {"session_id": session_id}

    while True:
        try:
            user_input = input("You: ").strip()
        except KeyboardInterrupt:
            print("\n\nFarewell. Your session has ended.")
            break
        except EOFError:
            # Non-interactive pipe / test mode
            break

        if not user_input:
            continue

        # Meta-commands
        if user_input.lower() in ("exit", "quit"):
            print("Farewell. Your session has ended.")
            break

        if user_input.lower() == "help":
            print(format_help())
            continue

        if user_input.lower() == "reset":
            default_store.clear(state["session_id"])
            state["session_id"] = create_session_id()
            print(f"Session reset. New session ID: {state['session_id']}\n")
            continue

        # PERCEIVE / ACT / RESPOND
        try:
            response = controller.run(user_input, state["session_id"])
        except Exception as exc:
            if debug:
                import traceback
                traceback.print_exc()
            else:
                print(f"[Error] {type(exc).__name__}: {exc}", file=sys.stderr)
            response = "[Error] Something went wrong. Please try again."

        print(f"\nSurgMentor:\n{response}\n")


def main() -> None:
    args = _parse_args()

    try:
        _init()
    except SystemExit:
        raise  # preserve exit code from validate_api_keys

    session_id = create_session_id()
    run_repl(session_id, debug=args.debug)


if __name__ == "__main__":
    main()
