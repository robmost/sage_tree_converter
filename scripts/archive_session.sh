#!/usr/bin/env bash
# archive_session.sh - Stage 4 archiving of the session's conversion products.
#
# Moves the Stage 2 test outputs and all session artefacts from assets/ into a
# timestamped audit directory. The Stage 3 full conversion output in output/
# is the final deliverable and is never touched.
#
# Usage:
#   scripts/archive_session.sh <dataset_name> <base> <format_id>
#     dataset_name  human-readable label (often equals <base>)
#     base          dataset directory name (AGENTS.md Section 13)
#     format_id     format identifier of this session
#
# Prints the audit directory path on success. Exit 1 on bad usage or if the
# audit directory ends up empty.

set -u

if [ $# -ne 3 ]; then
    echo "usage: $0 <dataset_name> <base> <format_id>" >&2
    exit 1
fi
DATASET_NAME="$1"
BASE="$2"
FORMAT_ID="$3"

TIMESTAMP="$(date +"%H%M-%d%m%Y")"
AUDIT_DIR="audits/${DATASET_NAME}_audit-files_${TIMESTAMP}"
mkdir -p "$AUDIT_DIR"

# Stage 2 test conversion products (HDF5 and binary cases).
mv "assets/test_${BASE}_STC.0.hdf5" "$AUDIT_DIR/" 2>/dev/null || true
mv "assets/test_${BASE}_STC.0"      "$AUDIT_DIR/" 2>/dev/null || true

# Session artefacts. The || true guards cover files a session never produced
# (e.g. sage_stdout.log when functional validation was skipped).
mv assets/validation_log.md         "$AUDIT_DIR/" 2>/dev/null || true
mv assets/auditor_report.md         "$AUDIT_DIR/" 2>/dev/null || true
mv assets/test_sage_params.par      "$AUDIT_DIR/" 2>/dev/null || true
mv assets/sage_stdout.log           "$AUDIT_DIR/" 2>/dev/null || true
mv assets/sage_test_output          "$AUDIT_DIR/" 2>/dev/null || true
mv assets/semantic_validation       "$AUDIT_DIR/" 2>/dev/null || true
mv assets/session_state.json        "$AUDIT_DIR/" 2>/dev/null || true

# Dataset-specific support files written to assets/ during Stage 2.
mv assets/*_snaplist.txt            "$AUDIT_DIR/" 2>/dev/null || true
mv assets/*_snaplist.dat            "$AUDIT_DIR/" 2>/dev/null || true
mv assets/*sim_config*.json         "$AUDIT_DIR/" 2>/dev/null || true

# Source driver draft (the production copy, if any, lives in
# conversion-engine/drivers/ after registration). Absent for KDB-match
# sessions that used an existing driver.
mv "assets/drivers/${FORMAT_ID}.py" "$AUDIT_DIR/" 2>/dev/null || true

# Stale draft files that are no longer needed.
rm -f "assets/proposed_mapping_${FORMAT_ID}.json"
rm -rf assets/drivers/__pycache__

if [ -z "$(ls -A "$AUDIT_DIR")" ]; then
    echo "ERROR: audit directory $AUDIT_DIR is empty - nothing was archived." >&2
    rmdir "$AUDIT_DIR"
    exit 1
fi

echo "Archived session files:"
ls "$AUDIT_DIR"
echo "$AUDIT_DIR"
