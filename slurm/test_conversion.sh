#!/bin/bash
# =============================================================================
# test_conversion.sh — SAGE merger tree converter: single-node test job
#
# Mirrors Stage 2: converts the first 100 forests from the input directory
# and writes the result to assets/. Use this to verify the environment and
# sim-config before submitting the full array job.
#
# Usage:
#   sbatch slurm/test_conversion.sh
#
# Edit the CONFIGURATION block below before submitting.
# =============================================================================

# ── SLURM directives ─────────────────────────────────────────────────────────
#SBATCH --job-name=sage-tree-test
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --output=slurm/logs/test_%j.out
#SBATCH --error=slurm/logs/test_%j.err

set -euo pipefail

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
# Absolute path to the project root (directory containing this script's parent).
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Dataset name — must match the subdirectory name under input/.
DATASET="microUchuu"

# Output format: lhalo_hdf5 or lhalo_binary
OUTPUT_FORMAT="lhalo_hdf5"

# Format ID (see format-database/ for valid IDs).
FORMAT_ID="rockstar_consistent_trees_ascii"

# Path to a sim-config JSON (leave blank to use driver auto-detection).
SIM_CONFIG="${REPO_DIR}/assets/${DATASET}_sim_config.json"

# Number of forests to convert (Stage 2 default is 100).
N_TREES=5
# ─────────────────────────────────────────────────────────────────────────────

# Load .env (sets PYTHON_BIN, INPUT_DIR, OUTPUT_DIR, etc.)
if [[ -f "${REPO_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${REPO_DIR}/.env"
    set +a
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
INPUT_DIR="${INPUT_DIR:-${REPO_DIR}/input}"

INPUT_PATH="${INPUT_DIR}/${DATASET}"
ASSETS_DIR="${REPO_DIR}/assets"
mkdir -p "${ASSETS_DIR}" "${REPO_DIR}/slurm/logs"

# Determine output file extension and path
if [[ "$OUTPUT_FORMAT" == "lhalo_hdf5" ]]; then
    OUTPUT_PATH="${ASSETS_DIR}/test_${DATASET}_STC.0.hdf5"
else
    OUTPUT_PATH="${ASSETS_DIR}/test_${DATASET}_STC.0"
fi

# Verify Python dependencies
"$PYTHON_BIN" -c "import h5py, numpy, tqdm; print('dependencies OK')"

echo "========================================"
echo "SAGE merger tree converter — test run"
echo "Dataset   : ${DATASET}"
echo "Input     : ${INPUT_PATH}"
echo "Output    : ${OUTPUT_PATH}"
echo "Format    : ${FORMAT_ID} → ${OUTPUT_FORMAT}"
echo "N forests : ${N_TREES}"
echo "========================================"

SIM_CONFIG_ARG=""
[[ -f "$SIM_CONFIG" ]] && SIM_CONFIG_ARG="--sim-config ${SIM_CONFIG}"

"$PYTHON_BIN" "${REPO_DIR}/conversion-engine/main_driver.py" \
    --input      "${INPUT_PATH}"   \
    --output     "${OUTPUT_PATH}"  \
    --format     "${FORMAT_ID}"    \
    --output-format "${OUTPUT_FORMAT}" \
    --n-trees    "${N_TREES}"      \
    ${SIM_CONFIG_ARG}

echo "Test conversion complete: ${OUTPUT_PATH}"
