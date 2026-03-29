# Detailed Usage Guide

This guide provides comprehensive instructions for operating the SAGE Universal Merger Tree Converter, covering both AI-assisted and manual workflows.

## 1. Data Preparation

Regardless of your workflow, ensure your data is organized:

- **Directory Structure:** Place raw simulation files in the `input/` directory (or a subdirectory thereof).
- **File Integrity:** Ensure all required files for a tool-chain are present (e.g., for AHF, both `.AHF_halos` and `_mtree` files).
- **Permissions:** Ensure you have write access to the `output/` directory for HDF5 files and validation plots.

## 2. AI-Assisted Workflow (Recommended)

This repository is optimized for use with an LLM CLI (Gemini or Claude). The assistant is instructed to act as a research specialist.

### Standard Protocol

1. **Initiate:** Invoke your CLI in the root directory.
2. **Assign:** *"Convert the merger trees in `input/my_sim/`"*.
3. **Review:** The assistant will present a field mapping table (Source $\rightarrow$ SAGE Target). Verify these units and scales.
4. **Test:** The assistant will generate a small sample (e.g., 10 trees) first.
5. **Validate:** Check the generated `*_validation.png` plot in the `output/` folder.
6. **Full Run:** Once the sample is verified, ask for the full conversion.

## 3. Manual CLI Usage

If operating manually, use the `MasterConverter` for automated format detection.

### The Master Converter

The `master_converter.py` script serves as the primary entry point. It identifies formats by peeking at file headers and matching them against the `format-database/`.

```bash
python3 conversion-engine/master_converter.py \
    --input "input/custom_gizmo_ahf-mergertree/*" \
    --output "output/gizmo_trees.hdf5"
```

### Argument Specification

- `--input`: A glob pattern matching your data files. **Important:** Wrap in quotes to prevent shell expansion if using multiple files.
- `--output`: The path for the resulting SAGE-compatible HDF5 file.

## 4. Advanced: Independent Driver Usage

Each driver in `conversion-engine/` is standalone and can be imported into your own analysis pipeline.

### Example: Custom Binary Conversion

```python
import sys
sys.path.append('conversion-engine')
import binary_subfind_lhalotree_driver

binary_subfind_lhalotree_driver.convert(
    input_path="input/mini-millenium/trees_063.0",
    output_path="output/millennium_custom.hdf5",
    n_trees=100
)
```

## 5. Troubleshooting

- **No Format Detected:** If the Master Converter fails to identify your files, check if a matching JSON exists in `format-database/`. If it's a new format, use the AI assistant to help you "Research and Map" the new primitives.
- **Incomplete Links (AHF):** Ensure you provide the `.AHF_halos` files AND the `_mtree` files in the same glob pattern. The driver requires both to build temporal connectivity.
- **Missing Dependencies:** Run `pip install -r requirements.txt` before starting.
