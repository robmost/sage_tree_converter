#!/usr/bin/env bash
# run_auditor.sh - Spawn the Stage 3 auditor as a fresh headless CLI process.
#
# The auditor must not share context with the conversion session, so it runs
# as a separate non-interactive CLI invocation with a self-contained prompt
# (.ai/agents/auditor.md) and receives only file paths. Its report is printed
# to stdout and captured here; the subprocess itself needs no write access.
#
# Usage:
#   scripts/run_auditor.sh [plots_dir] [report_path]
#     plots_dir    default: assets/semantic_validation
#     report_path  default: assets/auditor_report.md
#
# CLI selection: $AUDITOR_CLI (or AUDITOR_CLI in .env) forces one of
# claude|codex|agy; otherwise the first of those found on PATH is used.
# Exit codes: 0 report written, 1 precheck failed, 2 no CLI / spawn failed.

set -u

PLOTS_DIR="${1:-assets/semantic_validation}"
REPORT_PATH="${2:-assets/auditor_report.md}"
PROMPT_FILE=".ai/agents/auditor.md"
PLOTS="mah merger_rate angular_momentum hmf velocity_dist lifespan_dist spatial_dist"

# --- Mechanical prechecks: never spawn an LLM against missing plots ---------
if [ ! -f "$PROMPT_FILE" ]; then
    echo "ERROR: auditor prompt not found: $PROMPT_FILE" >&2
    exit 1
fi
missing=0
for name in $PLOTS; do
    for ext in pdf png; do
        f="$PLOTS_DIR/$name.$ext"
        if [ ! -s "$f" ]; then
            echo "ERROR: missing or empty plot file: $f" >&2
            missing=1
        fi
    done
done
if [ "$missing" -ne 0 ]; then
    echo "Prechecks failed - fix the plot generation before auditing." >&2
    exit 1
fi

# --- Pick the CLI ------------------------------------------------------------
if [ -z "${AUDITOR_CLI:-}" ] && [ -f .env ]; then
    AUDITOR_CLI="$(grep -E '^AUDITOR_CLI=' .env | cut -d= -f2- || true)"
fi
if [ -z "${AUDITOR_CLI:-}" ]; then
    for candidate in claude codex agy; do
        if command -v "$candidate" >/dev/null 2>&1; then
            AUDITOR_CLI="$candidate"
            break
        fi
    done
fi
if [ -z "${AUDITOR_CLI:-}" ] || ! command -v "$AUDITOR_CLI" >/dev/null 2>&1; then
    echo "ERROR: no auditor CLI found (set AUDITOR_CLI to claude, codex, or agy)." >&2
    exit 2
fi

# --- Build the self-contained prompt -----------------------------------------
PROMPT="$(cat "$PROMPT_FILE"; echo; for name in $PLOTS; do echo "- $PLOTS_DIR/$name.png"; done)"
export PROMPT  # the agy branch expands it inside a `script`-spawned shell

# --- Spawn headless, capture stdout as the report ----------------------------
echo "Running auditor via: $AUDITOR_CLI" >&2
case "$AUDITOR_CLI" in
    claude)
        # Read-only: the Read tool is enough to inspect PNG files.
        claude -p "$PROMPT" --allowedTools "Read" > "$REPORT_PATH"
        status=$?
        ;;
    codex)
        codex exec --sandbox read-only "$PROMPT" > "$REPORT_PATH"
        status=$?
        ;;
    agy)
        # agy -p can drop its final response from stdout under a non-TTY while
        # still exiting 0, so run it under a pseudo-TTY. macOS and Linux
        # `script` have different syntaxes.
        if [ "$(uname)" = "Darwin" ]; then
            script -q /dev/null agy -p "$PROMPT" < /dev/null > "$REPORT_PATH"
        else
            script -qec 'agy -p "$PROMPT"' /dev/null < /dev/null > "$REPORT_PATH"
        fi
        status=$?
        ;;
    *)
        echo "ERROR: unsupported AUDITOR_CLI '$AUDITOR_CLI' (use claude, codex, or agy)." >&2
        exit 2
        ;;
esac

# --- An empty report is a hard failure on every CLI --------------------------
if [ "$status" -ne 0 ] || [ ! -s "$REPORT_PATH" ]; then
    echo "ERROR: auditor produced no report (exit $status). Falling back is the" >&2
    echo "caller's decision - see .ai/skills/auditor/SKILL.md." >&2
    exit 2
fi

echo "Auditor report written to: $REPORT_PATH" >&2
exit 0
