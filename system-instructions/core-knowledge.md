# Core Knowledge: Primitive Conversion Matrices

This document defines the strict "primitives" of merger tree construction. The conversion agent MUST identify the combinations of **File Format**, **Halo Finder**, and **Merger Tree Tool** to deduce mapping strategies. 

## 1. The Primitive Knowledge Matrix

You MUST use the characteristics detailed below to securely parse and map input structures to SAGE formats.

| Primitive Category | Type / Tool | General Characteristics | SAGE Technical Mapping Requirement |
| :--- | :--- | :--- | :--- |
| **File Format** | `HDF5` | Self-describing array data. You MUST recursively inspect datasets/groups/attributes to locate units and dimensions. | N/A |
| **File Format** | `ASCII` | Columnar text, typically `.dat` or `.txt`. You MUST locate the `#` header to create a column map before parsing. | N/A |
| **File Format** | `Binary` | Fixed-width C-structs. You MUST request or infer a struct schema to slice the byte arrays accurately. | N/A |
| **Halo Finder** | `SO-Based` (AHF, Rockstar) | Identifies "Host" halos and nested "Subhalos" using overdensities ($M_{vir}$, $M_{200}$). | **Synthetic FOF Requirement:** SAGE requires an overarching FOF group. You MUST map the SO "Host" dataset to act as the `FirstHaloInFOFgroup` proxy. |
| **Halo Finder** | `FOF-Based` (SUBFIND) | Identifies discrete particle groups. Inherently compatible with SAGE group tracking ($M_{fof}$, $M_{sub}$). | **Direct Map:** Direct extraction of group fields. No synthetic generation needed. |
| **Merger Tool** | `Pointer` (SubLink, LHaloTree) | Pre-linked temporal pathways (uses discrete IDs for `FirstProgenitor`, `Descendant`). | **Pointer Parity Map:** Offset incoming local struct IDs or pointers into SAGE global relative pointers. |
| **Merger Tool** | `Particle` (AHF, ConsistentTrees) | Relies on shared particle IDs or merit functions between spatial snapshot datasets. | **Tree Stitching:** You MUST stitch multi-snapshot linking files into a unified continuous tree branch architecture. |

## 2. Mandatory Synthesisation Rules

If SAGE mandates a field missing from the input data, you MUST synthesise it using the following accepted physics estimations. Do NOT prompt the user if one of the following approximations can be deployed:

1. **Mass Approximations:** If only $M_{vir}$ or $M_{200}$ is provided, map it to `M_Mean200` and `M_TopHat`.
2. **Velocity Dispersion Formulation:** If $\sigma_v$ is missing but $V_{max}$ is present, estimate using $\sigma_v \approx V_{max} / \sqrt{2}$.
3. **Null-Spin Initialisation:** If `Spin(3)` is completely absent, map it to `(0.0, 0.0, 0.0)`.
