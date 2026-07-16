---
name: auditor
description: Runs the independent audit of the semantic validation plots by
             spawning a fresh headless CLI subprocess. Use after
             semantic-validation generates the seven plots, before presenting
             results to the user at G3.
---

# Auditor

## Role

The auditor is an **independent process**, not a role the main agent plays.
Independence comes from process isolation: a fresh headless CLI invocation
that has never seen this session's context, receives only file paths, and
inspects the rendered PNG plots directly. Its mandate, checklist (10 items),
and report format live in one canonical file:

- **`.ai/agents/auditor.md`** - the complete auditor prompt (CLI-agnostic).

The code-structure checks that older versions of this checklist performed
(style application, save_figure usage, field selection, O(N) walking) are now
deterministic unit tests in `tests/test_semantic_plots.py`. They run in CI and
via `make test`; do not re-perform them by hand during a session.

## Instructions

### 1. Spawn the auditor subprocess

```bash
bash scripts/run_auditor.sh assets/semantic_validation assets/auditor_report.md
```

The wrapper:
1. Verifies all seven plots exist as non-empty PDF **and** PNG files
   (exit 1 and no LLM spawned otherwise - fix plot generation first).
2. Picks the CLI from `AUDITOR_CLI` in `.env`, else the first of
   `claude` / `codex` / `agy` on PATH.
3. Runs it headless and read-only with the canonical prompt plus the PNG
   paths, capturing stdout to `assets/auditor_report.md`.
4. Treats an empty report as a hard failure (exit 2).

Do not pass the subprocess any summary of the session, the conversion, or the
plots. The prompt file and the PNG paths are its complete input.

### 2. Read the report and act on failures

Read `assets/auditor_report.md`. For every FAIL item:

1. Diagnose the cause in the conversion (driver bug, unit error, pointer
   reconstruction error) - diagnosis and fixes are the main agent's job; the
   auditor never proposes them.
2. Fix, re-run the full conversion if needed, regenerate all seven plots.
3. Re-run the audit from step 1. **Every re-audit runs all 10 items** - there
   is no partial re-audit.

Do not present results to the user until the report's overall verdict is PASS,
or two full fix cycles have failed (then follow the error handling policy in
AGENTS.md Section 6 and ask the user for guidance).

### 3. Fallback: in-context audit (last resort only)

If `run_auditor.sh` exits 2 because no CLI can be spawned (no binary on PATH,
no credentials inside the container, no network):

1. Read `.ai/agents/auditor.md` and apply its checklist yourself by reading
   the PNG files directly, judging each item from the images alone.
2. Write the same report format to `assets/auditor_report.md`, with the mode
   line set to `Audit mode: in-context fallback`.
3. The G3 prompt must state that the fallback mode ran (see AGENTS.md
   Section 3). Never describe a fallback audit as independent.
