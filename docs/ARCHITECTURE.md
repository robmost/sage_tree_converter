# Architectural Design

The SAGE Universal Merger Tree Converter is built on a **modular driver-based architecture** designed for extensibility and AI-assisted operation.

## 1. Component Overview

### The Master Converter (`master_converter.py`)

The orchestrator of the conversion process. It performs:

- **Heuristic Identification:** Peeks at file headers to detect the format.
- **Driver Dispatch:** Loads the correct specialized driver based on detected tools.
- **Glob Resolution:** Handles complex input patterns to group snapshots and link files.

### Specialized Drivers (`*_driver.py`)

Each driver is a standalone module responsible for a specific tool-chain.

- **Isolation:** Logic for AHF snapshot skipping is contained entirely within its driver, keeping the other drivers simple.
- **Agnosticism:** Drivers do not contain simulation names; they focus on data structures (e.g., `Binary_Subfind_LHaloTree`).
- **Standardized Output:** All drivers produce a unified SAGE-compatible HDF5 format.

### Format Database (`format-database/`)

A collection of JSON files that decouple field names from the engine logic.

- **Schema Mapping:** Defines which raw column (e.g., `Mhalo`) maps to which SAGE field (e.g., `Mvir`).
- **Unit Metadata:** Stores scaling factors and default units.

## 2. Data Flow

1. **Input:** User provides a glob pattern of raw files.
2. **Identification:** `MasterConverter` detects the tool-chain.
3. **Loading:** The corresponding driver reads all files into memory (or chunks).
4. **Linking:** Temporal pointers (`Descendant`, `FirstProgenitor`) are resolved.
5. **Validation:** Driver generates an HMF plot.
6. **Output:** A single, unified HDF5 file is written.

## 3. Extensibility

To add support for a new simulation tool-chain:

1. Create a new JSON mapping in `format-database/`.
2. Implement a new driver in `conversion-engine/` following the `convert(input, output)` interface.
3. Update the heuristic identification logic in `MasterConverter.identify_format_and_tools()`.
