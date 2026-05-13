# Apptainer runtime environment for SAGE Tree Converter.
#
# Usage (from project root):
#   source apptainer.env.sh
#   apptainer shell --pwd /app sage-tree-converter.sif

# Load project environment values (API keys, optional paths, tuning vars).
if [ -f ./.env ]; then
    set -a
    . ./.env
    set +a
fi

# Docker-compose-equivalent bind mounts.
export APPTAINER_BIND="$PWD:/app,${INPUT_DIR:-$PWD/input}:/app/input,${OUTPUT_DIR:-$PWD/output}:/app/output"

# Runtime environment inside the container.
export APPTAINERENV_HOME=/tmp
export APPTAINERENV_MPLCONFIGDIR=/tmp/matplotlib
export APPTAINERENV_COLORTERM=truecolor
export APPTAINERENV_TERM=xterm-256color

# Converter variables passed through to the container.
export APPTAINERENV_ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
export APPTAINERENV_GEMINI_API_KEY="${GEMINI_API_KEY:-}"
export APPTAINERENV_SAGE_BINARY_PATH="${SAGE_BINARY_PATH:-}"
export APPTAINERENV_SAGE_MEMORY_MULTIPLIER="${SAGE_MEMORY_MULTIPLIER:-3.0}"
export APPTAINERENV_PYTHON_BIN="${PYTHON_BIN:-python3}"
