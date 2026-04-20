# SAGE Universal Merger Tree Converter

A modular, data-agnostic toolkit for converting N-body simulation merger trees from various formats (ASCII, Binary, HDF5) and tool-chains (AHF, Rockstar, Subfind, Gadget-4) into **SAGE-compatible HDF5** files.

## 🤖 AI-Powered Workflow

This repository is specifically designed to be used with an **LLM CLI** (e.g., **Gemini CLI** or **Claude Code**). By invoking your preferred AI assistant in this directory, it will automatically follow the structured workflows defined in `AGENTS.md` and the `.ai/skills/` directory to guide you through the conversion process.

### How to use with an AI Assistant

1. **Clone** this repository.
2. **Add your raw tree files** to the `input/` directory.
3. **Invoke your LLM CLI** in the root folder.
4. **Ask the Assistant** to convert your data (e.g., *"Convert the AHF files I just added"*).
5. **The Assistant will autonomously advance through 4 States:**
    * **STATE 1 (Discovery):** Research the file format and identify the required tool-chains.
    * **STATE 2 (Analysis Report):** Propose a mapping schema and explicitly list the 7 validation steps. **(Requires your explicit approval to proceed).**
    * **STATE 3 (Test Engine):** Extract a small sample subset to run rapid functional integrity checks.
    * **STATE 4 (Full Suite):** Process the entire dataset, generate 7 mandatory 3-panel semantic validation plots, and produce the final SAGE-compatible tree.

## 🐳 Sandboxed Execution (Docker)

To run your AI CLI and the converter in a highly secure, compartmentalised sandbox, follow this quick standard workflow:

**Scenario:** You have downloaded this codebase to `~/sage_tree_converter` and your simulation files are located in a completely different folder, such as `~/Data/sim_run_data`.

1. **Navigate to the Codebase:**

   ```bash
   cd ~/sage_tree_converter
   ```

2. **Setup Environment:** Duplicate `.env.example` to `.env` and insert your API keys. You can also define optional `INPUT_DIR` and `OUTPUT_DIR` paths in `.env` to permanently mount your external data and output folders.
3. **Launch & Mount your Data:** Start the sandboxed container. Docker Compose will automatically link your external folders if defined in `.env`, or default to the local `input/` and `output/` directories:

   ```bash
   docker compose run --rm converter bash
   ```

4. **Invoke the AI:** You are now inside the sandbox! Launch your AI CLI safely:

   ```bash
   claude
   # OR
   gemini
   ```

5. **Prompt:** Simply tell the AI, *"I've placed my raw simulation files in the `input/` directory. Please analyse and convert them to the SAGE format."* The AI will parse the files, write the Python logic, and safely dump the final results into your host's `output/` directory!

## 🚀 Manual Quick Start (CLI)

If you prefer to run the tools manually without an AI or Docker, use the **Master Converter**:

```bash
python3 conversion-engine/master_converter.py \
    --input "input/custom_gizmo_ahf-mergertree/*" \
    --output "output/gizmo_trees.hdf5"
```

## 📂 Repository Structure

* **`conversion-engine/`**: Contains the core logic and specialized drivers.
  * `master_converter.py`: The main entry point for automated format detection.
  * `*_driver.py`: Tool-specific drivers (e.g., `ascii_ahf_mergertree_driver.py`).
* **`format-database/`**: JSON mapping files defining how raw simulation fields map to SAGE requirements.
* **`output/`**: Destination for final validation plots, markdown logs, and converted SAGE tree HDF5s.
  * **`intermediates/`**: Transient directory used by AI agents for extracting subsets and streaming volatile data without cluttering outputs.
* **`assets/`**: Read-only styles and ad-hoc scripting environments.
  * **`cli-scripts/`**: Sandboxed workspace where the LLMs write and execute testing logic without polluting the codebase.
* **`.ai/skills/`**: Centralised repository of AI skills (e.g., validation protocols, mapping strategies, and workflow state machines) that strictly govern the AI's autonomous actions.
* **`input/`**: Recommended directory for placing your raw sandbox simulation data.

## 🛠 Supported Tool-Chains

This converter is built around **tools**, not just simulation names. It supports any simulation that uses:

| Halo Finder | Merger Tree Tool | File Format | Driver |
| :--- | :--- | :--- | :--- |
| **SUBFIND** | LHaloTree | Binary | `binary_subfind_lhalotree_driver.py` |
| **SUBFIND** | Gadget-4 Tree | HDF5 | `hdf5_gadget4_driver.py` |
| **Rockstar** | ConsistentTrees | ASCII | `ascii_rockstar_consistenttrees_driver.py` |
| **AHF** | MergerTree | ASCII | `ascii_ahf_mergertree_driver.py` |

## ✨ Key Features

### 1. Snapshot Skipping (AHF)

The AHF driver utilises a **Global ID Mapping** strategy. It can resolve progenitor-descendant links across non-sequential snapshots, ensuring a continuous tree even if halos are "lost" for one or more snapshots.

### 2. Data-Agnostic Design

All scripts are designed to be agnostic of specific simulation filenames. Use glob patterns (e.g., `*.AHF_halos`) to provide your data, and the engine handles the rest.

### 3. Automated Validation

Every full conversion is strictly gated behind a mandatory suite of Syntactic, Semantic, and Functional tests. The CLI will systematically map raw data and generate **seven 3-panel comparative plots** (e.g., Mass Assembly History, Spin Evolution, Mass Functions) to mathematically verify unit scalings, coordinate origins, and pointer continuity. The results are logged rigorously in the `output/` directory.

## 📦 Requirements

* Python 3.x
* `numpy`
* `h5py`
* `pandas`
* `matplotlib`

---
*Developed for use with the Semi-Analytic Galaxy Evolution (SAGE) model.*
