#!/usr/bin/env python3
"""check_write_boundary.py - PreToolUse hook enforcing AGENTS.md Section 1.

Registered in .claude/settings.json for Write/Edit tool calls (Claude Code
only; other CLIs fall back to the instruction-level rule). The canonical
write-access table lives in AGENTS.md Section 1 - this hook mirrors it, it
does not define it.

Behaviour:
- No assets/session_state.json  -> allow everything (development session,
  no conversion workflow in progress).
- Active session                -> allow writes only inside the directories
  the current stage may write to; block everything else inside the project.
- Paths outside the project directory are not governed by the table -> allow.

Hook contract: JSON on stdin with tool_input.file_path; exit 0 allows,
exit 2 blocks and feeds stderr back to the model.
"""

import json
import os
import sys
from pathlib import Path

# Stage -> writable directory prefixes (relative to the project root).
# Mirrors the table in AGENTS.md Section 1.
STAGE_WRITABLE = {
    1: ("assets/",),
    2: ("assets/",),
    3: ("assets/", "output/"),
    4: (
        "assets/",
        "format-database/",
        "conversion-engine/",
        "conversation-examples/",
        "audits/",
    ),
}


def current_stage(state_path: Path) -> int:
    with state_path.open() as fh:
        gates = json.load(fh).get("gates_passed", {})
    return 1 + sum(1 for g in ("G1", "G2", "G3") if g in gates)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return  # not a payload we understand; do not block

    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
    state_path = project_dir / "assets" / "session_state.json"
    if not state_path.is_file():
        return  # no active conversion session: development work is unrestricted

    target = Path(file_path)
    if not target.is_absolute():
        target = project_dir / target
    try:
        rel = target.resolve().relative_to(project_dir)
    except ValueError:
        return  # outside the project: not governed by the table

    rel_str = rel.as_posix() + ("/" if target.is_dir() else "")
    stage = current_stage(state_path)
    allowed = STAGE_WRITABLE[stage]
    if any(rel_str == p.rstrip("/") or rel_str.startswith(p) for p in allowed):
        return

    print(
        f"BLOCKED: a conversion session is active (stage {stage}) and "
        f"'{rel}' is outside the writable directories for this stage: "
        f"{', '.join(allowed)}. See AGENTS.md Section 1. If this is "
        "development work, archive or remove assets/session_state.json first.",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
