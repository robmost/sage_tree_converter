#!/usr/bin/env bash
# archive_session.sh - Stage 4 archiving of the session's conversion products.
#
# Sweeps the session artefacts out of assets/ into a timestamped audit
# directory, keeping only the scaffolding the next session needs. The Stage 3
# full conversion output in output/ is the final deliverable and is never
# touched.
#
# Usage:
#   scripts/archive_session.sh <dataset_name>
#     dataset_name  human-readable label (often equals <base>)
#
# Prints the audit directory path on success. Exit 1 on bad usage or if the
# audit directory ends up empty.

set -u

if [ $# -ne 1 ]; then
    echo "usage: $0 <dataset_name>" >&2
    exit 1
fi
DATASET_NAME="$1"

TIMESTAMP="$(date +"%H%M-%d%m%Y")"
AUDIT_DIR="audits/${DATASET_NAME}_audit-files_${TIMESTAMP}"
mkdir -p "$AUDIT_DIR"

# Bytecode caches are build artefacts, not session records.
rm -rf assets/__pycache__ assets/drivers/__pycache__

# --- Driver drafts -----------------------------------------------------------
# Archived file by file so the package scaffolding (assets/drivers/__init__.py)
# survives - driver-authoring imports drafts as drivers.<format_id>.
for f in assets/drivers/*.py; do
    [ -e "$f" ] || continue
    case "${f##*/}" in
        __init__.py) continue ;;
    esac
    mv "$f" "$AUDIT_DIR/" || true
done

# --- Everything else ---------------------------------------------------------
# Sweeping, rather than listing the filenames a session is expected to produce,
# means a file a session named for itself cannot be silently left behind. The
# glob skips dotfiles, which is what keeps .gitkeep in place.
for entry in assets/*; do
    [ -e "$entry" ] || continue
    case "${entry##*/}" in
        drivers) continue ;;
    esac
    mv "$entry" "$AUDIT_DIR/" || true
done

if [ -z "$(ls -A "$AUDIT_DIR")" ]; then
    echo "ERROR: audit directory $AUDIT_DIR is empty - nothing was archived." >&2
    rmdir "$AUDIT_DIR"
    exit 1
fi

echo "Archived session files:"
ls "$AUDIT_DIR"
echo "$AUDIT_DIR"
