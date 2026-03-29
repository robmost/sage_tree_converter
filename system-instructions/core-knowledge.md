# Core Knowledge: Modular Merger Tree Conversion

This document defines the "primitives" of merger tree construction. The converter should identify the **File Format**, **Halo Finder**, and **Merger Tree Tool** to determine the mapping strategy.

## 1. File Formats (Containers)

* **HDF5:** Self-describing, hierarchical. Requires inspection of groups and attributes to find metadata (units, box size).
* **ASCII:** Columnar text. Requires a header or user-provided column mapping. Common in older AHF and Rockstar outputs.
* **Binary:** Fixed-width C-structs. Requires a schema (header) to interpret. The SAGE output format is itself a specific binary schema.

## 2. Halo Finders (Spatial Analysis)

Determines how halos are identified and what physical properties are available.

### SO-based (Spherical Overdensity) - e.g., AHF, Rockstar

* **Structure:** Hierarchical (Host -> Subhalo -> Sub-subhalo).
* **Properties:** Usually provides $M_{vir}$, $M_{200c}$, $R_{vir}$, $V_{max}$, etc.
* **SAGE Mapping:** Requires synthetic FOF group pointers. The "Host" is mapped as the `FirstHaloInFOFgroup`.

### FOF-based (Friends-of-Friends) - e.g., SUBFIND, VELOCIraptor

* **Structure:** Groups of particles.
* **Properties:** Provides $M_{fof}$ and often subhalo-specific properties like $M_{sub}$.
* **SAGE Mapping:** Direct mapping to FOF group fields.

## 3. Merger Tree Tools (Temporal Analysis)

Determines how halos are linked across snapshots.

### Pointer-based (Pre-linked) - e.g., SubLink, LHaloTree

* **Logic:** Files contain direct IDs or indices for `FirstProgenitor`, `Descendant`, etc.
* **SAGE Mapping:** Often a direct translation of IDs to SAGE's relative indexing.

### Particle-based (Cross-match) - e.g., MergerTree (AHF), ConsistentTrees

* **Logic:** Files list shared particles or "merit" scores between snapshot pairs.
* **SAGE Mapping:** Requires "stitching" pairwise links into a continuous tree and identifying the "Main Progenitor" (usually via merit function sorting).

## 4. Mandatory Field Mapping Strategies

(Same as before: Synthetic FOF groups, Mass/Radius approximations, $\sigma_v$ and Spin estimations).
