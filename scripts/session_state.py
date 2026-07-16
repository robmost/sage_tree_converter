#!/usr/bin/env python3
"""session_state.py - Durable record of the agent workflow's gate state.

The agent workflow records its progress in assets/session_state.json so that
gate state, the dataset base name, and the G1 choices survive context loss
(compaction, crashes, resumed sessions). Stage entry conditions in AGENTS.md
are checked against this file, not against conversational memory.

Usage:
    python3 scripts/session_state.py init --format-id <id>
    python3 scripts/session_state.py set <key> <value>
    python3 scripts/session_state.py gate <G1|G2|G3>
    python3 scripts/session_state.py show

Keys accepted by `set`: format_id, base, output_format, n_output_files,
mapping_source. n_output_files is stored as an integer.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

STATE_PATH = Path("assets/session_state.json")
ALLOWED_KEYS = ("format_id", "base", "output_format", "n_output_files", "mapping_source")
GATES = ("G1", "G2", "G3")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load() -> dict:
    if not STATE_PATH.is_file():
        sys.exit(f"ERROR: {STATE_PATH} not found - run 'session_state.py init' first.")
    with STATE_PATH.open() as fh:
        return json.load(fh)


def _save(state: dict) -> None:
    state["updated"] = _now()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def cmd_init(args: argparse.Namespace) -> None:
    if STATE_PATH.is_file() and not args.force:
        sys.exit(
            f"ERROR: {STATE_PATH} already exists. A session is in progress; "
            "use --force only to abandon it and start over."
        )
    _save(
        {
            "format_id": args.format_id,
            "base": None,
            "output_format": None,
            "n_output_files": None,
            "mapping_source": None,
            "gates_passed": {},
            "created": _now(),
        }
    )
    print(f"Initialised {STATE_PATH} for format_id={args.format_id}")


def cmd_set(args: argparse.Namespace) -> None:
    if args.key not in ALLOWED_KEYS:
        sys.exit(f"ERROR: unknown key '{args.key}'. Allowed: {', '.join(ALLOWED_KEYS)}")
    state = _load()
    value: object = args.value
    if args.key == "n_output_files":
        try:
            value = int(args.value)
        except ValueError:
            sys.exit(f"ERROR: n_output_files must be an integer, got '{args.value}'.")
        if value < 1:
            sys.exit(f"ERROR: n_output_files must be >= 1, got {value}.")
    state[args.key] = value
    _save(state)
    print(f"{args.key} = {value}")


def cmd_gate(args: argparse.Namespace) -> None:
    state = _load()
    passed = state.setdefault("gates_passed", {})
    expected = GATES[len(passed)] if len(passed) < len(GATES) else None
    if args.gate != expected:
        done = ", ".join(passed) or "none"
        sys.exit(
            f"ERROR: cannot record {args.gate}: gates passed so far: {done}. "
            f"Next gate must be {expected or 'nothing - all gates passed'}."
        )
    passed[args.gate] = _now()
    _save(state)
    print(f"Recorded {args.gate} at {passed[args.gate]}")


def cmd_show(_args: argparse.Namespace) -> None:
    print(json.dumps(_load(), indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create the state file at session start")
    p_init.add_argument("--format-id", required=True)
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_set = sub.add_parser("set", help="record a session value")
    p_set.add_argument("key")
    p_set.add_argument("value")
    p_set.set_defaults(func=cmd_set)

    p_gate = sub.add_parser("gate", help="record a gate as passed (in order)")
    p_gate.add_argument("gate", choices=GATES)
    p_gate.set_defaults(func=cmd_gate)

    p_show = sub.add_parser("show", help="print the current state")
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
