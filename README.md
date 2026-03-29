# SAGE Universal Merger Tree Converter

A modular, data-agnostic toolkit for converting N-body simulation merger trees from various formats (ASCII, Binary, HDF5) and tool-chains (AHF, Rockstar, Subfind, Gadget-4) into **SAGE-compatible HDF5** files.

## 🤖 AI-Powered Workflow

This repository is specifically designed to be used with an **LLM CLI** (e.g., **Gemini CLI** or **Claude Code**). By invoking your preferred AI assistant in this directory, it will automatically follow the structured workflows defined in `GEMINI.md` or `CLAUDE.md` to guide you through the conversion process.

### How to use with an AI Assistant

1. **Clone** this repository.
2. **Add your raw tree files** to the `input/` directory.
3. **Invoke your LLM CLI** in the root folder.
4. **Ask the Assistant** to convert your data (e.g., *"Convert the AHF files I just added"*).
5. **The Assistant will:**
    * Research the file format.
    * Propose a mapping.
    * Run test conversions.
    * Generate validation plots.
    * Finalize the SAGE-compatible tree.

## 🐳 Sandboxed Execution (Docker)

To run your AI CLI and the converter in a highly secure, compartmentalised sandbox, follow this quick standard workflow:

**Scenario:** You have downloaded this codebase to `~/sage_tree_converter` and your simulation files are located in a completely different folder, such as `~/Data/sim_run_data`.

1. **Navigate to the Codebase:**

   ```bash
   cd ~/sage_tree_converter
   ```

2. **Add Your Keys:** Duplicate `.env.example` to `.env` and insert your API keys.
3. **Launch & Mount your Data:** Start the sandboxed container while dynamically linking your external data folder to the container's isolated `input/` directory using the volume (`-v`) flag:

   ```bash
   docker compose run -v ~/Data/sim_run_data:/app/input --rm converter bash
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

## 📂 Repository Structure

* **`conversion-engine/`**: Contains the core logic and specialized drivers.
  * `master_converter.py`: The main entry point for automated format detection.
  * `*_driver.py`: Tool-specific drivers (e.g., `ascii_ahf_mergertree_driver.py`).
* **`format-database/`**: JSON mapping files defining how raw simulation fields map to SAGE requirements.
* **`docs/`**: Detailed documentation on usage, supported formats, and architectural design.
* **`system-instructions/`**: Domain knowledge and validation protocols for the conversion process.
* **`input/`**: Recommended directory for placing your raw simulation data.

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

Every conversion generates a **Halo Mass Function (HMF)** plot (e.g., `output/trees_validation.png`). This allows you to immediately verify that the mass distribution and units are physically consistent.

## 📦 Requirements

* Python 3.x
* `numpy`
* `h5py`
* `pandas`
* `matplotlib`

---
*Developed for use with the Semi-Analytic Galaxy Evolution (SAGE) model.*
