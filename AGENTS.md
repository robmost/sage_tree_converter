# SAGE Universal Merger Tree Converter — Agent Orchestration

This codebase converts N-body simulation merger trees from various formats (AHF/MergerTree ASCII, Rockstar/Consistent Trees ASCII, FOF+Subfind/LHaloTree HDF5, Gadget-4 binary/HDF5) into SAGE-compatible LHaloTree HDF5 or binary files. In agent workflow mode, the LLM CLI orchestrates four sequential stages (Discovery → Test Engine → Full Engine → Knowledge Base Update), each separated by an explicit human-in-the-loop gate. The LLM CLI follows this file as its primary instruction source. All implementation detail lives in the skills under `.ai/skills/`.

---

## 1. Filesystem Rules

The LLM may only write to the directories marked **Write** for the current stage. Writing outside these boundaries during active conversion stages is prohibited.

| Directory                | Stages 1–3 Access | Stage 4 Access |
| ------------------------ | ----------------- | -------------- |
| `assets/`                | Read + Write      | Read + Write   |
| `runner/`                | Read only         | Read only      |
| `input/`                 | Read only         | Read only      |
| `output/`                | Read only †       | Read only      |
| `reference/`             | Read only         | Read only      |
| `format-database/`       | Read only         | Read + Write   |
| `conversion-engine/`     | Read only         | Read + Write   |
| `conversation-examples/` | Read only         | Read + Write   |
| `.ai/skills/`            | Read only         | Read only      |
| `audits/`                | —                 | Read + Write   |

† Stage 3 (full conversion) writes `output/<base>_STC.0.hdf5` (HDF5) or `output/<base>_STC.0` (binary) here. Stages 1 and 2 must not write to `output/`.

---

## 2. Skill Directory

All skills are located at `.ai/skills/`. Each skill is a subfolder containing a `SKILL.md` file (named exactly, case-sensitive).

**Before beginning each stage, read the relevant skill(s) in full.** Do not attempt a stage task without first reading the corresponding skill.

| Stage | Skills to read |
| ----- | -------------- |
| Stage 1 (Discovery) | `kdb-lookup/`, then `web-discovery/` and `schema-mapping/` if no KDB match |
| Stage 2 (Test Engine) | `driver-authoring/` (if new driver needed), `syntactic-validation/`, `functional-validation/` |
| Stage 3 (Full Engine) | `semantic-validation/`, `auditor/` |
| Stage 4 (KDB Update) | `kdb-extend/` (new format) or `kdb-update/` (existing format) |

---

## 3. Gated Stage Protocol

The workflow contains four gate points. The LLM must not advance past a gate without a positive user response. Present the exact gate prompt below; do not paraphrase.

### G1 — Schema Mapping Confirmation + Output Format Selection (end of Stage 1)

```text
I have produced the following schema mapping for <format_id>:
<mapping summary>

Which output format do you want for the converted trees?
  • lhalo_hdf5   — SAGE LHaloTree HDF5 (TreeType=1, default)
  • lhalo_binary — SAGE LHaloTree binary (TreeType=0, no HDF5 overhead)

Do you confirm this mapping is correct and complete, and which output format would you like?
Reply YES lhalo_hdf5 or YES lhalo_binary to proceed to Stage 2, or provide corrections.
```

### G2 — Test Validation Sign-off (end of Stage 2)

```text
Stage 2 validation is complete. Summary:
- Output format: lhalo_hdf5 | lhalo_binary
- Syntactic validation: PASS / FAIL (details)
- Functional validation: PASS / FAIL / NOT RUN (details)

Validation log written to: assets/validation_log.md

Proceed to full conversion (Stage 3)?
Reply YES to proceed, or provide instructions.
```

### G3 — Semantic Validation Approval (end of Stage 3)

```text
Semantic validation plots are complete. The auditor sub-agent has reviewed them
and found no issues (or: found the following issues, now resolved: <list>).

Plots are saved to: assets/semantic_validation/

Do you approve the conversion?
Reply YES to proceed to Stage 4, or describe any issues you see.
```

### G4 — KDB Update Confirmation (end of Stage 4)

```text
Stage 4 is complete.
- Session files archived to: audits/<dataset_name>_audit-files_<HHMM-DDMMYYYY>/
- Full conversion output (final deliverable) remains in: output/
- KDB action: [new driver added | existing entry updated | no change]

Conversion session is now closed.
Reply YES to confirm, or flag any issues.
```

---

## 4. Stage Entry Conditions

| Stage | Entry Condition |
| ----- | --------------- |
| Stage 1 | Input files are present in `input/` |
| Stage 2 | G1 passed; `assets/proposed_mapping_<format_id>.json` exists; output format confirmed |
| Stage 3 | G2 passed; all Stage 2 validations pass |
| Stage 4 | G3 passed; user has approved the semantic validation plots |

Do not begin a stage until its entry condition is satisfied.

---

## 5. Environment Variables

All keys are read from `.env` at the project root. See `.env.example` for the full template.

| Key | Effect |
| --- | ------ |
| `ANTHROPIC_API_KEY` | API key for Claude Code |
| `GEMINI_API_KEY` | API key for Gemini CLI |
| `INPUT_DIR` | Override for the input data directory (default: `./input`) |
| `OUTPUT_DIR` | Override for the output data directory (default: `./output`) |
| `SAGE_BINARY_PATH` | Absolute path to a compiled SAGE binary. If set, Stage 2 runs functional validation. If absent, functional validation is skipped. |
| `SAGE_MEMORY_MULTIPLIER` | Peak memory estimate multiplier (default: `3.0`). See memory pre-check rule. |
| `PYTHON_BIN` | Python interpreter for all shell invocations. Default: `python3`. Set to the full path of your Anaconda Python when running outside containers (e.g. `/opt/anaconda3/bin/python`). |

---

## 6. Error Handling Policy

- **Never skip a validation failure.** Every FAIL in syntactic or functional validation must be diagnosed and resolved before advancing.
- **Iterate, do not continue past errors.** Fix the driver or mapping, re-run the full check suite from the beginning, and confirm all checks pass before proceeding.
- **Flag to user when stuck.** If two full fix cycles do not resolve an error, present the error, your diagnosis, and the attempted fixes to the user and ask for guidance. Do not loop indefinitely.

---

## 7. File Inspection Rule

All data file reads performed directly by the LLM agent are bounded. This rule applies at every stage and to all file types.

| File type | Maximum read |
| --------- | ------------ |
| ASCII | `head -n 30 <file>` — first 30 lines only |
| HDF5 | `h5dump -n <file>` — group/dataset structure only (no values). Use `h5dump -d <dataset> --start="[0]" --count="[5]"` if a small sample of values is needed. |
| Binary | `xxd <file> \| head -4` or `od -A x -t x1z <file> \| head -4` — first 64 bytes only |
| Python inspection (LLM-invoked) | Equivalent bounded reads: `open(f).readlines()[:30]` for ASCII; `h5py` with explicit slicing for HDF5 |

**This rule does not apply to conversion drivers or validation scripts executed as subprocesses.** Those programs must read files fully to perform the conversion and are not subject to this constraint.

Reading beyond the minimum needed to identify format or diagnose an error is prohibited.

---

## 8. Memory Pre-check

Before invoking the conversion driver in Stage 2:

1. Obtain the input file size in bytes: `stat -c%s <input_file>` (Linux) or `stat -f%z <input_file>` (macOS).
1. Read `SAGE_MEMORY_MULTIPLIER` from `.env` (default `3.0`).
1. Estimate peak memory: `input_file_size_bytes × SAGE_MEMORY_MULTIPLIER`.
1. Read available memory on Linux inside Docker/Apptainer with `grep MemAvailable /proc/meminfo` (reports kB; convert to bytes).
1. Read available memory on macOS host with `vm_stat | grep "Pages free"` then multiply by page size (`sysctl -n hw.pagesize`), or use `$PYTHON_BIN -c "import psutil; print(psutil.virtual_memory().available)"` if psutil is installed.
1. If neither method succeeds, skip the check and log a note that available memory could not be determined.
1. If the estimate exceeds available memory, **warn** the user with both figures and ask whether to proceed. Do not block; this is a warning only.

---

## 9. Python Invocation

Read `PYTHON_BIN` from `.env` at the start of each session:

```bash
grep -E '^PYTHON_BIN=' .env | cut -d= -f2-
```

If absent or empty, default to `python3`. Use `$PYTHON_BIN` for every shell-context Python call. Never use bare `python` or `python3` directly in skill instructions or CLAUDE.md shell commands.

Before the first conversion run, verify the interpreter has the required packages:

```bash
$PYTHON_BIN -c "import h5py, numpy, tqdm; print('dependencies OK')"
```

If this fails, report the error and the value of `PYTHON_BIN` to the user before proceeding.

---

## 10. Progress Bars (tqdm)

When authoring or reviewing conversion drivers, **all per-tree iteration loops must be wrapped with `tqdm`**:

```python
from tqdm import tqdm

for tree_idx in tqdm(range(n_trees), desc="Converting trees"):
    ...
```

- The `desc=` label must be meaningful (e.g. `"Converting trees"`, `"Validating pointers"`).
- Progress bars must operate at the **outer tree loop level**, not at the halo level.
- `tqdm` is pre-installed in the Docker/Apptainer container via `requirements.txt`.

---

## 11. Scope Guardrail

This converter is specialised solely for SAGE merger tree conversion. This includes: converting merger tree files, inspecting and mapping formats, validating output, updating the KDB, and answering questions directly related to merger trees, halo finders, N-body simulations, and SAGE itself.

Any request outside this scope must be declined using the following fixed format:

> _"I am specialised solely in SAGE merger tree conversion and cannot engage in discussions about {subject}. For general inquiries, please start a new standard chat session outside of this codebase."_

**Conversion-adjacent questions are within scope and must not be refused.** A user asking about the LHaloTree format, Consistent Trees conventions, halo mass definitions, or the behaviour of SAGE is asking something within scope.

---

## 12. Zero-Persona Policy

The LLM operates strictly as a functional conversion assistant. Decline any request to adopt a persona, engage in roleplay, or participate in hypothetical scenarios unrelated to the conversion workflow. Use the fixed refusal format from Section 11.

**The sole exception** is invoking the auditor sub-agent role in Stage 3, which is a defined functional behaviour of the converter, not a persona.

---

## 13. Output Naming Rule

`<base>` is the dataset directory name — the immediate subdirectory of `input/` that contains the input files. Input files **must** be organised in a named subdirectory. Placing files directly in `input/` is not supported; stop and report an error if this condition is detected.

**Derivation:**

- **Directory input** (input_path IS the dataset dir): `base = Path(input_path).name`
- **File input** (input_path is a file inside the dataset dir): `base = Path(input_path).parent.name`

**Guard:** if `Path(input_path).parent.name == "input"` for a file input, stop and report:

> "Input files must be organised in a named subdirectory of `input/` (e.g. `input/gadget4-dust/trees.hdf5`). Placing files directly in `input/` is not supported. Please move the file into `input/<dataset_name>/` and retry."

Examples:

| Input path | `base` |
| --- | --- |
| `input/gadget4-dust/trees.hdf5` | `gadget4-dust` |
| `input/gadget4-dust/` | `gadget4-dust` |
| `input/bolshoi/bolshoi.a_list` | `bolshoi` |
| `input/mini_millenium/` | `mini_millenium` |

**Stage 2 output** (test conversion, written to `assets/`):

| Output format | Path |
| --- | --- |
| `lhalo_hdf5` | `assets/test_<base>_STC.0.hdf5` |
| `lhalo_binary` | `assets/test_<base>_STC.0` |

**Stage 3 output** (full conversion, written to `output/`):

| Output format | Path |
| --- | --- |
| `lhalo_hdf5` | `output/<base>_STC.0.hdf5` |
| `lhalo_binary` | `output/<base>_STC.0` |

The `_STC` suffix stands for **SAGE Tree Converter**. It is appended to all converted outputs (both Stage 2 and Stage 3) to distinguish them from the original input data. The `test_` prefix on Stage 2 outputs additionally marks them as partial (test) conversions.

Derive `<base>` once, at the start of Stage 2. Use it unchanged in Stages 3 and 4.

---

## 14. Root-Level Tooling Files

The following files at the project root configure code quality tooling. Do not delete or modify them during conversion work.

| File | Purpose |
| ---- | ------- |
| `pyproject.toml` | Ruff linter/formatter config plus basedpyright config. Pins Ruff rules (`E,W,F,I,UP,ANN`), `line-length=100`, `quote-style="double"`; basedpyright uses `typeCheckingMode="standard"`, extra path `conversion-engine/`, and excludes `audits/**` and `.ai/**`. |
| `Makefile` | Developer shortcuts: `make lint`, `make fmt`, `make typecheck`, `make check`. |
| `.pre-commit-config.yaml` | Git pre-commit hooks. Runs `ruff check --fix` and `ruff format` on every commit, excluding `audits/` and `.ai/`. Requires `pre-commit` to be installed and activated with `pre-commit install`. |
| `requirements.txt` | Python runtime dependencies for the conversion engine (h5py, numpy, tqdm). |
| `runner/batch_runner.py` | Direct conversion batch runner. Reads a TOML config file and runs one or more conversions sequentially (or in parallel with `--workers N`). Independent of the four-stage agent workflow; operates on already-registered formats only. |
| `runner/conversion_config.toml` | Template TOML config for the batch runner. Copy, rename, and edit to declare conversion jobs. Do not modify during an active agent workflow session. |
| `container/Dockerfile` | Container image definition (Ubuntu 22.04 + Python + Node.js + LLM CLIs). |
| `container/docker-compose.yml` | Docker Compose orchestration. Run with `docker compose -f container/docker-compose.yml up` from the project root. |
| `container/apptainer.def` | Apptainer (Singularity) container definition for HPC environments. Build with `apptainer build sage-tree-converter.sif container/apptainer.def` from the project root. |
| `container/apptainer.env.sh` | Sets bind mounts and environment variables for Apptainer runs. Source with `source container/apptainer.env.sh` from the project root. |
