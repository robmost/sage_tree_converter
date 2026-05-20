---
name: driver-authoring
description: Guides drafting or adapting a format-specific conversion driver for
             the SAGE merger tree converter. Use when no existing driver matches
             the input format and a new driver must be written in assets/ before
             the test conversion can run.
---

# Driver Authoring

## Stage Preamble

The Stage 2 preamble is output from AGENTS.md §15 at stage entry. Do not re-output it here — proceed directly to driver authoring.

## Instructions

This skill is invoked in Stage 2 when `kdb-lookup` found no matching driver in
`conversion-engine/drivers/`, or when the existing driver needs modification.

## Path Convention

Two path prefixes are used in this skill:
- **`.ai/skills/driver-authoring/references/<file>`** — files in this skill's own `references/` subfolder.
- **`reference/<file>` (project root)** — files in the project-root `reference/` directory (e.g. `reference/sage_lhalotree_hdf5_schema.md`).

### 1. Driver interface

Every driver must expose exactly **two** public functions: `convert()` (called by
`main_driver.py` for conversion) and `read_trees()` (called by semantic validation to
load the original input data independently). Do not add further public functions beyond
these two.

The `convert()` signature is:

```python
def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
) -> None:
    """
    Convert input merger trees to SAGE LHaloTree HDF5 or binary format.

    Parameters
    ----------
    input_path : str
        Path to the input file or directory.
    output_path : str
        Path for the output file.
    n_trees : int or None
        If given, convert only the first n_trees trees. Used for test runs.
    sim_params : dict or None
        Simulation parameter overrides loaded from --sim-config JSON.
        Recognised keys: particle_mass_msun_per_h, n_particles_per_side,
        box_size_mpc_per_h, omega_m, omega_l, h0. All optional; drivers
        fall back to auto-detection when absent.
    output_format : str
        'lhalo_hdf5' (default) or 'lhalo_binary'. Selects the output writer.
    """
```

The `read_trees()` signature is:

```python
def read_trees(
    input_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
) -> dict[int, dict]:
    """Read input trees into the SAGE LHaloTree schema without writing output.

    Reuses the driver's existing private parsing helpers and applies all unit
    conversions and pointer reconstruction, but accumulates results in memory
    instead of writing to disk. Called by semantic validation so the original
    source data can be used as the reference (input) column.

    Parameters
    ----------
    sim_params : dict or None
        Same simulation parameter overrides as convert(). Pass through to any
        private helper that reads particle_mass or box_size from sim_params.

    Returns
    -------
    dict[int, dict[str, np.ndarray]]
        tree_idx (0-based, matching convert() write order) → field dict.
        SubhaloPos in kpc/h, SubhaloSpin in (kpc/h)(km/s), masses in 1e10 Msun/h.
    """
```

Implement `read_trees()` by reusing the same private helpers as `convert()`.
Do **not** call `read_trees()` from within `convert()` — keep the streaming
optimisations in `convert()` unchanged.

See `.ai/skills/driver-authoring/references/driver_interface_spec.md` for the complete interface contract.

### 2. Output structure

The driver must write a valid SAGE LHaloTree output file at `output_path`.

**For `output_format="lhalo_hdf5"`** (HDF5, SAGE TreeType=1):

```text
output.hdf5
├── Header/
│   ├── [attr] ParticleMass        — float64
│   ├── [attr] NtreesPerFile       — int32
│   ├── [attr] NhalosPerFile       — int32
│   ├── [attr] NumberOfOutputFiles — int32
│   └── TreeNHalos                 — 1D int32 dataset, length = NtreesPerFile
└── Tree0/
    └── <field>   — one 1D or 2D dataset per field
...
└── Tree<N-1>/
    └── <field>
```

All mandatory fields from `reference/sage_lhalotree_hdf5_schema.md` (project root) must be written
to every `Tree<X>/` group. Dtypes must match the schema exactly (int32, float32,
int64 as specified).

**For `output_format="lhalo_binary"`** (binary, SAGE TreeType=0):

```text
int32  nforests
int32  totnhalos
int32  nhalos_per_forest[nforests]
halo_data[totnhalos]   — 104 bytes each, packed via utils.binary_writer
```

The header must be written BEFORE halo data. If tree counts are not known upfront
(streaming input), accumulate all field dicts in memory then write header + trees.
Use `utils.binary_writer.write_header()` + `write_tree()` — same API as `hdf5_writer`.

> **Required on-disk units for `SubhaloPos` and `SubhaloSpin`** (both formats): drivers always
> produce field dicts with `SubhaloPos` in **kpc/h** and `SubhaloSpin` in **(kpc/h)(km/s)**.
> `hdf5_writer` stores these values as-is. `binary_writer._pack_tree()` divides both by 1000
> internally before packing (binary reader does not apply the ×0.001 factor that the HDF5
> reader does). Never scale these fields differently per format — the writer handles the
> conversion. See `reference/sage_lhalotree_hdf5_schema.md` (project root) Section 5.4 for the full table.

### 3. Performance constraint

- All tree-walking and pointer reconstruction must be **O(N) or O(N log N)**.
- **O(N²) is not acceptable.** This includes any loop-within-loop structure over
  halos (e.g. scanning the full halo list for each halo to find its descendant).
- Use dictionary-based lookups for ID-to-index mapping (O(1) per lookup).
- See `.ai/skills/driver-authoring/references/pointer_reconstruction_patterns.md` for O(N) patterns.

If you find yourself writing a nested loop over halos, stop and redesign using
a hash map or sort-based approach before continuing.

### 4. Write location

Write the draft driver to `assets/drivers/<format_id>.py`.
**Do not write to `conversion-engine/drivers/` at this stage.**
The driver is moved to `conversion-engine/drivers/` only in Stage 4 via `kdb-extend`.

### 5. Error handling

- The driver must call `sys.exit(1)` (or raise an uncaught exception) on any error.
- Do not silently skip invalid data or continue past errors.
- Use informative error messages: include the tree index, halo index, and the
  field name in any error output.

### 6. Progress bars (tqdm)

Wrap all per-tree iteration loops with `tqdm`:

```python
from tqdm import tqdm

with h5py.File(output_path, "w") as out_f:
    for tree_idx in tqdm(range(n_trees_to_convert), desc="Converting trees"):
        # convert tree tree_idx
        ...
```

- The `desc=` label must be meaningful (e.g. `"Converting trees"`).
- The progress bar must be at the **outer tree loop level**, not the halo level.
- `tqdm` is pre-installed in the container; import with `from tqdm import tqdm`.

### 7. Reference the template driver

Read `conversion-engine/drivers/_template.py` as a skeleton before writing the
new driver. It documents the required function signatures, import patterns, and
HDF5/binary writing utilities in a self-contained example.

### 8. Verify Python dependencies before first run

Before running the draft driver for the first time, confirm that all required
packages are importable inside the active environment:

```bash
$PYTHON_BIN -c "import h5py, numpy, tqdm; print('dependencies OK')"
```

If any package is missing inside the container, install it:

```bash
pip install h5py numpy tqdm
```

Outside the container (development only), use `pip install --user` or a virtual
environment. **Do not modify `requirements.txt`** — that file governs the container
image and is not part of a conversion session.

### 9. Run the Stage 2 test conversion

The driver lives in `assets/drivers/` and is not yet registered in
`conversion-engine/main_driver.py` (registration happens in Stage 4 via `kdb-extend`).
Do **not** attempt to invoke it through `main_driver.py`. Instead, invoke it directly
by prepending `conversion-engine/` to `sys.path` (so `from utils import ...` resolves)
and calling `convert()` as a library function:

```bash
$PYTHON_BIN - <<'EOF'
import sys
sys.path.insert(0, "conversion-engine")
sys.path.insert(0, "assets")
from drivers.<format_id> import convert
convert(
    "input/<base>/",
    "assets/test_<base>_STC.0.hdf5",
    n_trees=100,
    sim_params=None,
    output_format="lhalo_hdf5",
)
EOF
```

Replace `<format_id>` and `<base>` with the actual values. For `lhalo_binary` output,
change the output path to `"assets/test_<base>_STC.0"` and `output_format` to
`"lhalo_binary"`. Pass a `sim_params` dict if a `--sim-config` JSON was supplied by
the user; otherwise `None` is correct.
