#!/bin/bash
# =============================================================================
# full_conversion.sh — SAGE merger tree converter: SLURM array job
#
# Divides all tree_*.dat shards across N_TASKS array tasks.  Each task owns
# ceil(N_shards / N_TASKS) files, converts them as a single unit, and writes
# one output file.  Total output files = N_TASKS (one per task).
#
# Designed for large simulations with many shards (e.g. Shin-Uchuu ~2000 files,
# 512 CPUs → ~4 shards/task, 512 output files).
#
# Usage:
#   # Print the correct sbatch command for your dataset:
#   bash slurm/full_conversion.sh --print-submit-cmd
#
#   # Or submit directly (example for 512 tasks):
#   sbatch --array=0-511 slurm/full_conversion.sh
#
# Edit the CONFIGURATION block below before submitting.
# =============================================================================

# ── SLURM directives ─────────────────────────────────────────────────────────
#SBATCH --job-name=sage-tree-conv
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=slurm/logs/conv_%A_%a.out
#SBATCH --error=slurm/logs/conv_%A_%a.err

set -euo pipefail

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Dataset name — must match the subdirectory name under INPUT_DIR.
DATASET="ShinUchuu"

# Total number of array tasks (= number of output files produced).
# Must match the --array=0-<N_TASKS-1> value in your sbatch command.
N_TASKS=512

# Output format: lhalo_hdf5 or lhalo_binary
OUTPUT_FORMAT="lhalo_binary"

# Format ID (see format-database/ for valid IDs).
FORMAT_ID="rockstar_consistent_trees_ascii"

# Path to a sim-config JSON (leave blank to use driver auto-detection).
# Shin-Uchuu: 6400^3 particles, 140 Mpc/h, m_particle = 8.97e5 Msun/h, n_snapshots=70.
SIM_CONFIG="${REPO_DIR}/assets/${DATASET}_sim_config.json"

# Number of output files produced per task (almost always 1 for array jobs).
N_OUTPUT_FILES_PER_TASK=1

# Temporary directory for per-task file lists (must be writable on compute nodes).
TMPDIR="${TMPDIR:-/tmp}"
# ─────────────────────────────────────────────────────────────────────────────

# ── Helper: print the sbatch command and exit ─────────────────────────────────
if [[ "${1:-}" == "--print-submit-cmd" ]]; then
    [[ -f "${REPO_DIR}/.env" ]] && set -a && source "${REPO_DIR}/.env" 2>/dev/null && set +a || true
    INPUT_DIR="${INPUT_DIR:-${REPO_DIR}/input}"
    INPUT_PATH="${INPUT_DIR}/${DATASET}"
    N=$(find "${INPUT_PATH}" -maxdepth 1 -name "tree_*.dat" | wc -l)
    if [[ "$N" -eq 0 ]]; then
        echo "No tree_*.dat files found in ${INPUT_PATH}" >&2; exit 1
    fi
    EFFECTIVE_TASKS=$(( N < N_TASKS ? N : N_TASKS ))
    echo "Found ${N} shards → using ${EFFECTIVE_TASKS} tasks (~$((N / EFFECTIVE_TASKS))-$((N / EFFECTIVE_TASKS + 1)) shards/task)"
    echo ""
    echo "sbatch --array=0-$((EFFECTIVE_TASKS-1)) slurm/full_conversion.sh"
    exit 0
fi

# ── SLURM execution path ──────────────────────────────────────────────────────
[[ -f "${REPO_DIR}/.env" ]] && set -a && source "${REPO_DIR}/.env" 2>/dev/null && set +a || true

PYTHON_BIN="${PYTHON_BIN:-python3}"
INPUT_DIR="${INPUT_DIR:-${REPO_DIR}/input}"
OUTPUT_DIR="${OUTPUT_DIR:-${REPO_DIR}/output}"

INPUT_PATH="${INPUT_DIR}/${DATASET}"
mkdir -p "${OUTPUT_DIR}" "${REPO_DIR}/slurm/logs"

# Build sorted shard list
mapfile -t ALL_SHARDS < <(find "${INPUT_PATH}" -maxdepth 1 -name "tree_*.dat" | sort)
N_SHARDS="${#ALL_SHARDS[@]}"

if [[ "$N_SHARDS" -eq 0 ]]; then
    echo "ERROR: no tree_*.dat files found in ${INPUT_PATH}" >&2; exit 1
fi

TASK_ID="${SLURM_ARRAY_TASK_ID:-0}"
EFFECTIVE_TASKS=$(( N_SHARDS < N_TASKS ? N_SHARDS : N_TASKS ))

if [[ "$TASK_ID" -ge "$EFFECTIVE_TASKS" ]]; then
    echo "TASK_ID=${TASK_ID} >= EFFECTIVE_TASKS=${EFFECTIVE_TASKS}, nothing to do." ; exit 0
fi

# Compute this task's shard range [START, END)
# Distribute remainder evenly: first (N_SHARDS % EFFECTIVE_TASKS) tasks get one extra shard.
REMAINDER=$(( N_SHARDS % EFFECTIVE_TASKS ))
BASE_COUNT=$(( N_SHARDS / EFFECTIVE_TASKS ))

if [[ "$TASK_ID" -lt "$REMAINDER" ]]; then
    COUNT=$(( BASE_COUNT + 1 ))
    START=$(( TASK_ID * COUNT ))
else
    COUNT=$BASE_COUNT
    START=$(( REMAINDER * (BASE_COUNT + 1) + (TASK_ID - REMAINDER) * BASE_COUNT ))
fi
END=$(( START + COUNT ))

# Write per-task file list to a temp file
FILELIST="${TMPDIR}/sage_filelist_${SLURM_JOB_ID:-0}_${TASK_ID}.txt"
printf '%s\n' "${ALL_SHARDS[@]:$START:$COUNT}" > "${FILELIST}"

PADDED_ID=$(printf "%03d" "$TASK_ID")
if [[ "$OUTPUT_FORMAT" == "lhalo_hdf5" ]]; then
    OUTPUT_PATH="${OUTPUT_DIR}/${DATASET}_shard${PADDED_ID}_STC.0.hdf5"
else
    OUTPUT_PATH="${OUTPUT_DIR}/${DATASET}_shard${PADDED_ID}_STC.0"
fi

"$PYTHON_BIN" -c "import h5py, numpy, tqdm; print('dependencies OK')"

echo "========================================"
echo "SAGE merger tree converter — array task"
echo "Task      : ${TASK_ID} / $((EFFECTIVE_TASKS-1))"
echo "Shards    : ${COUNT}  (indices ${START}–$((END-1)) of ${N_SHARDS})"
echo "Output    : ${OUTPUT_PATH}"
echo "Format    : ${FORMAT_ID} → ${OUTPUT_FORMAT}"
echo "Out files : ${N_OUTPUT_FILES_PER_TASK} per task  (${EFFECTIVE_TASKS} total)"
echo "========================================"
cat "${FILELIST}"
echo "----------------------------------------"

SIM_CONFIG_ARG=""
[[ -f "$SIM_CONFIG" ]] && SIM_CONFIG_ARG="--sim-config ${SIM_CONFIG}"

"$PYTHON_BIN" "${REPO_DIR}/conversion-engine/main_driver.py" \
    --file-list     "${FILELIST}"                  \
    --output        "${OUTPUT_PATH}"               \
    --format        "${FORMAT_ID}"                 \
    --output-format "${OUTPUT_FORMAT}"             \
    --n-output-files "${N_OUTPUT_FILES_PER_TASK}"  \
    ${SIM_CONFIG_ARG}

rm -f "${FILELIST}"
echo "Conversion complete: ${OUTPUT_PATH}"
