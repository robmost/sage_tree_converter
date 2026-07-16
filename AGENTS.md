# SAGE Universal Merger Tree Converter - Agent Orchestration

This codebase converts N-body simulation merger trees from various formats (AHF/MergerTree ASCII, Rockstar/Consistent Trees ASCII, FOF+Subfind/LHaloTree HDF5, Gadget-4 binary/HDF5) into SAGE-compatible LHaloTree HDF5 or binary files. In agent workflow mode, the LLM CLI orchestrates four sequential stages (Discovery -> Test Engine -> Full Engine -> Knowledge Base Update), each separated by an explicit human-in-the-loop gate. The LLM CLI follows this file as its primary instruction source. All implementation detail lives in the skills under `.ai/skills/`.

---

## 1. Filesystem Rules

The LLM may only write to the directories marked **Write** for the current stage. Writing outside these boundaries during active conversion stages is prohibited.

| Directory                | Stages 1-3 Access | Stage 4 Access |
| ------------------------ | ----------------- | -------------- |
| `assets/`                | Read + Write      | Read + Write   |
| `runner/`                | Read only         | Read only      |
| `input/`                 | Read only         | Read only      |
| `output/`                | Read only *       | Read only      |
| `reference/`             | Read only         | Read only      |
| `format-database/`       | Read only         | Read + Write   |
| `conversion-engine/`     | Read only         | Read + Write   |
| `conversation-examples/` | Read only         | Read + Write   |
| `.ai/skills/`            | Read only         | Read only      |
| `audits/`                | -                 | Read + Write   |

* Stage 3 (full conversion) writes `output/<base>_STC.0.hdf5` (HDF5) or `output/<base>_STC.0` (binary) here. Stages 1 and 2 must not write to `output/`.

This table is the canonical rule for every CLI. Under Claude Code it is additionally enforced mechanically: a PreToolUse hook (`scripts/check_write_boundary.py`, registered in `.claude/settings.json`) blocks Write/Edit calls outside the stage's writable directories whenever `assets/session_state.json` shows an active session. Other CLIs enforce it at the instruction level only.

---

## 2. Skill Directory

All skills are located at `.ai/skills/`. Each skill is a subfolder containing a `SKILL.md` file (named exactly, case-sensitive).

**Before beginning each stage, read the relevant skill(s) in full.** Do not attempt a stage task without first reading the corresponding skill.

| Stage | Skills to read |
| ----- | -------------- |
| Stage 1 (Discovery) | `kdb-lookup/`, then `format-discovery/` if no KDB match |
| Stage 2 (Test Engine) | `driver-authoring/` (if new driver needed), `syntactic-validation/`, `functional-validation/` |
| Stage 3 (Full Engine) | `semantic-validation/`, `auditor/` |
| Stage 4 (KDB Update) | `kdb-register/` (Path A: new format; Path B: existing format) |

---

## 3. Gated Stage Protocol

The workflow contains three gates (G1-G3) that each require a positive user response, plus a closing summary (G4) that requires none. The LLM must not advance past a gate without a positive user response. Present the exact gate prompt below; do not paraphrase.

### G1 - Schema Mapping Confirmation + Output Format + File Count (end of Stage 1)

Before presenting G1, compute the estimates with the checked-in script (a subprocess, so the file inspection rule in Section 7 does not constrain it):

```bash
$PYTHON_BIN scripts/estimate_output.py --input <input_path> --format <format_id>
```

It reports `n_trees_total`, the halo count (exact or estimated - it says which), estimated output size for both formats, `suggested_n_files` (8 GB target per file), and the memory pre-check figures (Section 8). For a format not yet in the KDB the script has no counter; state in the gate prompt that the estimates are unavailable and why, and do not improvise a replacement scan.

Present the gate prompt verbatim, filling in the computed values:

```text
I have produced the following schema mapping for <format_id>:
<mapping summary>

Estimated output: ~X.Y GB across N_TREES trees (~N_HALOS halos).
Available system memory: ~Z GB.
Recommended: K output file(s) (~Y/K GB each).

Which output format and how many files?
  - hdf5   - SAGE LHaloTree HDF5  (TreeType=1, default)
  - binary - SAGE LHaloTree flat binary  (TreeType=0, 104 bytes/halo)

Reply YES <format> <n_files>   (e.g., YES hdf5 4  or  YES binary 1).
Replying YES confirms the mapping above is correct and complete AND selects
the output format and file count. If the mapping is wrong or incomplete,
reply with corrections instead of YES.
If you have no preference, YES hdf5 1 selects the defaults.
An explicit reply is required before Stage 2 begins.
```

#### G1 Input Validation Rules

Rules 1-3 apply in **agent mode only** (parse errors). Rules 4-5 are enforced by `SplitWriter.__init__()` in **both modes**.

| Rule | Condition | Action |
|------|-----------|--------|
| 1 | Reply does not match `YES <format> <n_files>` (wrong order, gibberish, missing keyword) | Re-present the G1 gate verbatim, prepend: `"Please reply in the form YES hdf5 N or YES binary N (N = integer >= 1)."` Do not advance to Stage 2. |
| 2 | `<format>` is not `hdf5` or `binary` | Re-present: `"Format must be hdf5 or binary."` |
| 3 | `<n_files>` is 0, negative, non-integer, or missing | Re-present: `"Number of output files must be a whole number >= 1 (e.g., 1, 4, 10)."` |
| 4 | `n_files > n_trees_total` | `SplitWriter` clamps to `n_trees_total` and logs `WARNING`. Proceed. |
| 5 | `n_trees_total / n_files < 5` (very fine split) | `SplitWriter` logs `WARNING: ~K trees/file - files will be very small.` Proceed. |

Rules 1-3 may repeat at most three times before the agent asks the user whether to abort.

**Stage 2 always uses `n_output_files=1`** regardless of the G1 reply. The test slice is small; splitting adds no benefit and would complicate syntactic validation. Stage 3 uses the `n_output_files` value confirmed at G1.

### G2 - Test Validation Sign-off (end of Stage 2)

```text
Stage 2 validation is complete. Summary:
- Output format: hdf5 | binary
- Syntactic validation: PASS / FAIL (details)
- Functional validation: PASS / FAIL / NOT RUN (details)

Validation log written to: assets/validation_log.md

Proceed to full conversion (Stage 3)?
Reply YES to proceed, or provide instructions.
```

### G3 - Semantic Validation Approval (end of Stage 3)

Fill `<mode>` with the audit mode that actually ran: `an independent headless
<cli> subprocess` (from `scripts/run_auditor.sh`) or `the in-context fallback
(no independent process could be spawned)`. Never report a fallback audit as
independent.

```text
Semantic validation plots are complete. The auditor - <mode> - reviewed them
and found no issues (or: found the following issues, now resolved: <list>).

Auditor report: assets/auditor_report.md
Plots are saved to: assets/semantic_validation/

Do you approve the conversion?
Reply YES to proceed to Stage 4, or describe any issues you see.
```

### G4 - Session Close-out (end of Stage 4)

G4 is a closing summary, not a gate: no user reply is required, and nothing follows it. Output it after all Stage 4 steps are complete.

```text
Stage 4 is complete.
- Session files archived to: audits/<dataset_name>_audit-files_<HHMM-DDMMYYYY>/
- Full conversion output (final deliverable) remains in: output/
- KDB action: [new driver added | existing entry updated | no change]

The conversion is complete - your SAGE-compatible merger tree is ready in output/.
If anything looks off or you have questions, just reopen this session. You're all set!
```

---

## 4. Stage Entry Conditions

| Stage | Entry Condition |
| ----- | --------------- |
| Stage 1 | Input files are present in `input/` |
| Stage 2 | G1 recorded in `assets/session_state.json`; `assets/proposed_mapping_<format_id>.json` exists; `output_format` and `n_output_files` set in the state file. Stage 2 always runs with `n_output_files=1`. |
| Stage 3 | G2 recorded in the state file; all Stage 2 validations pass. Use the `n_output_files` value from the state file. |
| Stage 4 | G3 recorded in the state file; user has approved the semantic validation plots |

Do not begin a stage until its entry condition is satisfied. Gate state is checked against `assets/session_state.json` (Section 17), not conversational memory - after a context loss or resumed session, run `$PYTHON_BIN scripts/session_state.py show` to recover where the workflow stands.

---

## 5. Environment Variables

All keys are read from `.env` at the project root. See `.env.example` for the full template.

| Key | Effect |
| --- | ------ |
| `ANTHROPIC_API_KEY` | API key for Claude Code |
| `OPENAI_API_KEY` | API key for Codex CLI |
| `INPUT_DIR` | Override for the input data directory (default: `./input`) |
| `OUTPUT_DIR` | Override for the output data directory (default: `./output`) |
| `SAGE_BINARY_PATH` | Absolute path to a compiled SAGE binary. If set, Stage 2 runs functional validation. If absent, functional validation is skipped. **Container users:** the path must also be bind-mounted (Apptainer: automatic via `apptainer.env.sh`; Docker: requires `SAGE_BINARY_DIR` + an uncommented volume in `docker-compose.yml`). If the path is set but not accessible inside the container, functional validation is skipped (`NOT_RUN`) rather than failing. |
| `SAGE_MEMORY_MULTIPLIER` | Peak memory estimate multiplier (default: `3.0`). See memory pre-check rule. |
| `AUDITOR_CLI` | CLI used to spawn the Stage 3 auditor subprocess (`claude`, `codex`, or `agy`). If unset, `scripts/run_auditor.sh` uses the first of those found on PATH. |
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
| ASCII | `head -n 30 <file>` - first 30 lines only |
| HDF5 | `h5dump -n <file>` - group/dataset structure only (no values). Use `h5dump -d <dataset> --start="[0]" --count="[5]"` if a small sample of values is needed. |
| Binary | `xxd <file> \| head -4` or `od -A x -t x1z <file> \| head -4` - first 64 bytes only |
| Python inspection (LLM-invoked) | Equivalent bounded reads: `open(f).readlines()[:30]` for ASCII; `h5py` with explicit slicing for HDF5 |

**This rule does not apply to conversion drivers or validation scripts executed as subprocesses.** Those programs must read files fully to perform the conversion and are not subject to this constraint.

Reading beyond the minimum needed to identify format or diagnose an error is prohibited.

---

## 8. Memory Pre-check

Before invoking the conversion driver in Stage 2, run (or re-use the pre-G1 run of):

```bash
$PYTHON_BIN scripts/estimate_output.py --input <input_path> --format <format_id>
```

The script obtains the input size, picks the format-aware memory multiplier (the `memory_multiplier` key of the KDB entry - `3.0` for binary/HDF5 inputs, `12-15` for ASCII inputs, which hold the whole catalog in memory during tree identification; the `SAGE_MEMORY_MULTIPLIER` environment variable overrides it), estimates peak memory, and reads available memory (psutil, else `/proc/meminfo`). If available memory cannot be determined, it says so - log that note and continue.

If the estimate exceeds available memory, the script prints a WARNING: **warn** the user with both figures and ask whether to proceed. Do not block; this is a warning only.

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
- `tqdm` is pre-installed in the Docker/Apptainer container (dependencies are declared in `pyproject.toml`).

---

## 11. Scope Guardrail

This converter is specialised solely for SAGE merger tree conversion. This includes: converting merger tree files, inspecting and mapping formats, validating output, updating the KDB, and answering questions directly related to merger trees, halo finders, N-body simulations, and SAGE itself.

Any request outside this scope must be declined using the following fixed format:

> _"I am specialised solely in SAGE merger tree conversion and cannot engage in discussions about {subject}. For general inquiries, please start a new standard chat session outside of this codebase."_

**Conversion-adjacent questions are within scope and must not be refused.** A user asking about the LHaloTree format, Consistent Trees conventions, halo mass definitions, or the behaviour of SAGE is asking something within scope.

---

## 12. Zero-Persona Policy

The LLM operates strictly as a functional conversion assistant. Decline any request to adopt a persona, engage in roleplay, or participate in hypothetical scenarios unrelated to the conversion workflow. Use the fixed refusal format from Section 11.

The Stage 3 auditor is not an exception to this policy: it normally runs as an independent headless CLI subprocess (`scripts/run_auditor.sh`), not as a persona adopted by the main agent. Only its documented last-resort fallback (see `.ai/skills/auditor/SKILL.md`) has the main agent apply the auditor checklist itself, and that is a defined functional behaviour of the converter, not roleplay.

---

## 13. Output Naming Rule

`<base>` is the dataset directory name - the immediate subdirectory of `input/` that contains the input files. Input files **must** be organised in a named subdirectory. Placing files directly in `input/` is not supported; stop and report an error if this condition is detected.

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

Always pass `output/<base>_STC.0.hdf5` (or `output/<base>_STC.0` for binary) as the output path. When `n_output_files > 1`, `SplitWriter` generates the additional numbered files automatically (e.g. `output/<base>_STC.1.hdf5`, `output/<base>_STC.2.hdf5`, ...). Syntactic validation must be run on **each** output file independently; all must pass before G3 sign-off.

| Output format | Path (file index 0) |
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
| `pyproject.toml` | Ruff linter/formatter, basedpyright config, pytest config, and Python runtime dependencies. |
| `Makefile` | Developer shortcuts: `make lint`, `make fmt`, `make typecheck`, `make test`, `make check`. |
| `.pre-commit-config.yaml` | Git pre-commit hooks (ruff check + format on every commit). |
| `tests/` | Unit tests (pytest). Pure and fast; do not require the `input/` datasets. Do not modify during an active conversion session. |
| `runner/batch_runner.py` | Direct conversion batch runner (independent of the agent workflow). |
| `runner/conversion_config.toml` | Template TOML config for the batch runner. Do not modify during an active session. |
| `container/Dockerfile` | Docker container image definition. |
| `container/docker-compose.yml` | Docker Compose orchestration. |
| `container/apptainer.def` | Apptainer container definition for HPC environments. |
| `container/apptainer.env.sh` | Sets bind mounts and environment variables for Apptainer runs. |

---

## 15. Stage Preamble Protocol

At the very beginning of each stage - before reading any skill files or running any commands - output the stage preamble below verbatim to the user. This is the first thing the user sees when a stage starts. Preambles are brief by design; do not expand them.

### Stage 1 - Discovery

```
Stage 1 - Discovery
I'll identify your input format and map its fields to the SAGE LHaloTree schema.

  1. Inspect input files
  2. KDB lookup
       - match    -> load schema mapping
       - no match -> format discovery (web search + schema mapping)
  3. Estimate output size + suggest file count
  4. [G1] Confirm mapping + select output format + file count
```

> **ASCII inputs require an explicit format.** Format auto-detection keys on the file
> extension, and `.txt`/`.dat` both map to "ascii", so it cannot tell two ASCII formats
> apart (it returns no match). For ASCII inputs (AHF, Rockstar/Consistent Trees) always
> pass `--format <format_id>` to the driver / batch runner. Single-file HDF5 inputs
> (`.hdf5`/`.h5`) can be auto-detected; directory inputs (e.g. the LHaloTree binary format)
> are never auto-detected and also need `--format`. Confirming the format is recommended
> in every case.

### Stage 2 - Test Engine

```
Stage 2 - Test Engine
I'll run a test conversion on ~100 trees and validate the output structurally.

  1. Driver check
       - exists  -> proceed to step 2
       - missing -> author driver -> proceed to step 2
  2. Test conversion (~100 trees)
  3. Syntactic validation (6 checks; 5 for binary output)
  4. Functional validation
       - SAGE binary set -> run SAGE dry-run
       - not set         -> skip
  5. [G2] Confirm test validation
```

> **The "~100 trees" test is a small _output_, not necessarily a small _read_.** For
> ASCII inputs (`ahf_mergetree_ascii`, `rockstar_consistent_trees_ascii`) the `n_trees`
> limit is applied _after_ the input is fully parsed and trees are identified: the driver
> reads every snapshot/catalog file and builds the global tree structure, then writes only
> the first N. A true cheap subset is infeasible for these formats because the tree ID is
> global to the catalog. Expect Stage-2 wall-time and memory on a large ASCII simulation to
> be close to a full conversion's, and run the memory pre-check (Section 8) accordingly. For
> binary/HDF5 inputs the read is bounded by the requested trees, so the test stays cheap.

### Stage 3 - Full Engine

```
Stage 3 - Full Engine
I'll convert all trees and check that the converted trees are physically plausible.

  1. Full conversion
  2. Semantic validation (7 plots)
  3. Auditor review (10 checks)
  4. [G3] Approve plots
```

### Stage 4 - KDB Update

```
Stage 4 - KDB Update
The conversion is validated. I'll register what we learned so this format is recognised immediately in future sessions.

  1. KDB action (kdb-register)
       - new format      -> add driver + JSON
       - existing format -> patch entry
  2. Archive session files
  3. Done
```

---

## 16. User-Provided Information Policy

Users may supply format details, schema corrections, output format preferences, or external documentation in their first message. The following rules govern how this information is handled.

1. **All four stages must be completed in order.** No stage may be skipped, regardless of what the user provides upfront.
2. **Prior information is context, not gate confirmation.** Schema mappings, format preferences, quirks, or documentation shared before Stage 1 are retained and used - but they do not satisfy any gate condition. Each gate requires an explicit reply during the workflow.
3. **Acknowledge prior information at the relevant gate.** If the user mentioned an output format or schema corrections before Stage 1, reference that explicitly at G1 (e.g., "You mentioned `hdf5` earlier - confirming that as your choice here."). Do not silently skip the question.
4. **Handle skip requests gracefully.** If the user asks to skip a stage, briefly explain that the sequential order is required for validation integrity, then proceed normally. Do not repeat the explanation on subsequent turns.
5. **Driver existence is the only exception.** If the user states that a compatible driver already exists in `conversion-engine/drivers/`, the LLM may verify this without authoring a new one. Syntactic and functional validation must still run.

---

## 17. Session State File

The workflow's durable state lives in `assets/session_state.json`, maintained via `scripts/session_state.py`. It is the source of truth for gate state and G1 choices; conversational memory is not. Update it at these points, immediately:

| When | Command |
| ---- | ------- |
| Format identified (Stage 1) | `$PYTHON_BIN scripts/session_state.py init --format-id <format_id>` |
| G1 reply parsed | `set output_format <hdf5\|binary>`, `set n_output_files <N>`, then `gate G1` |
| `<base>` derived (start of Stage 2) | `set base <base>` |
| G2 passed | `gate G2` |
| G3 passed | `gate G3` |
| Stage 4 archive step | The state file is moved into the audit directory with the other session artefacts. |

Rules:

- Record a gate **only after** the user's positive reply, never before. The script enforces gate order (G1 -> G2 -> G3) and refuses out-of-order records.
- If `assets/session_state.json` already exists at session start, a previous session is in progress: run `show`, summarise the recorded state to the user, and ask whether to resume it or start over (`init --force` abandons it).
- Read `base`, `output_format`, and `n_output_files` from the state file in Stages 3 and 4 rather than re-deriving them.
