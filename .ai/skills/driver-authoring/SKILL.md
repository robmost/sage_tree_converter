---
name: driver-authoring
description: Guides drafting or adapting a format-specific conversion driver for
             the SAGE merger tree converter. Use when no existing driver matches
             the input format and a new driver must be written in assets/ before
             the test conversion can run.
---

# Driver Authoring

## Stage Preamble

If the Stage 2 preamble has not already been output this session, output it now, verbatim, from AGENTS.md Section 15. Never re-output a preamble that has already been shown, and never paraphrase it.

## Instructions

This skill is invoked in Stage 2 when `kdb-lookup` found no matching driver in
`conversion-engine/drivers/`, or when the existing driver needs modification.

## Path Convention

Two path prefixes are used in this skill:
- **`.ai/skills/driver-authoring/references/<file>`** - files in this skill's own `references/` subfolder.
- **`reference/<file>` (project root)** - files in the project-root `reference/` directory (e.g. `reference/sage_lhalotree_hdf5_schema.md`).

### 1. Driver interface

Every driver must expose exactly **one** public function: `convert()` (called by
`main_driver.py`). Do not add further public functions.

The `convert()` signature is:

```python
def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
    n_output_files: int = 1,
) -> None:
    """
    Convert input merger trees to SAGE LHaloTree HDF5 or binary format.

    Parameters
    ----------
    input_path : str
        Path to the input file or directory.
    output_path : str
        Path for output file index 0 (e.g. assets/test_<base>_STC.0.hdf5).
        Additional files are derived by SplitWriter from the trailing index token.
    n_trees : int or None
        If given, convert only the first n_trees trees. Used for test runs.
    sim_params : dict or None
        Simulation parameter overrides loaded from --sim-config JSON.
        Recognised keys: particle_mass_msun_per_h, n_particles_per_side,
        box_size_mpc_per_h, omega_m, omega_l, h0. All optional; drivers
        fall back to auto-detection when absent.
    output_format : str
        'lhalo_hdf5' (default) or 'lhalo_binary'. Both are handled uniformly
        by SplitWriter - no format-conditional write blocks needed.
    n_output_files : int
        Number of output files to split trees across (default 1).
        n_trees_total MUST be known before opening SplitWriter (see section 2).
    """
```

See `.ai/skills/driver-authoring/references/driver_interface_spec.md` for the complete interface contract.

### 2. Output structure

The driver must write a valid SAGE LHaloTree output file at `output_path`.

**For `output_format="lhalo_hdf5"`** (HDF5, SAGE TreeType=1):

```text
output.hdf5
├── Header/
│   ├── [attr] ParticleMass        - float64
│   ├── [attr] NtreesPerFile       - int32
│   ├── [attr] NhalosPerFile       - int32
│   ├── [attr] NumberOfOutputFiles - int32
│   └── TreeNHalos                 - 1D int32 dataset, length = NtreesPerFile
└── Tree0/
    └── <field>   - one 1D or 2D dataset per field
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
halo_data[totnhalos]   - 104 bytes each
```

The header must precede halo data. `SplitWriter` handles this via a placeholder-then-patch
strategy - `n_trees_total` must be known upfront so the placeholder is the correct size.

**Use `SplitWriter` for both output formats.** Do not write format-conditional blocks:

```python
from utils.split_writer import SplitWriter

# n_trees_total must be known before opening SplitWriter. Cheap ways to obtain it:
#   - Count '#tree' markers in ASCII files (O(lines), no halo data loaded)
#   - Read len(work_list) after scanning file headers
#   - Read a HDF5 TreeTable row count (O(1) from header attribute)
#   Never require an O(all halos) pre-pass.

with SplitWriter(
    output_path=output_path,
    output_format=output_format,
    n_output_files=n_output_files,
    n_trees_total=n_trees_to_convert,
    particle_mass=particle_mass_1e10,
) as writer:
    for fields in tqdm(tree_stream, desc="Converting trees", unit="tree"):
        writer.write_tree(fields)

output_paths = writer.output_paths  # list of all written file paths
```

> **The "cheap pre-pass" applies to _counting_ trees, not to producing a test subset.**
> The rule above is only that `n_trees_total` must be obtainable cheaply (a line count or a
> header attribute) so `SplitWriter` can size its output. It does **not** promise that a
> test conversion with `n_trees=100` is cheap. For formats whose tree ID is global to the
> catalog (e.g. AHF), the driver must parse the whole input and identify all trees before it
> can select the first N - so an `n_trees` test still costs a near-full parse and load. Do
> not contort the driver trying to make such a subset cheap; it is inherent to the format.
> Where a format _does_ allow bounded reads (e.g. stop after N `#tree` blocks), prefer that.

SplitWriter distributes trees evenly across `n_output_files` files, derives all output
paths from `output_path` by replacing the trailing index token (`.0.hdf5` -> `.1.hdf5`,
etc.), and deletes partially-written files on exception. Do NOT call `os.remove()` in
the except handler - SplitWriter's `__exit__` already handles cleanup.

> **Required on-disk units for `SubhaloPos` and `SubhaloSpin`** (both formats): drivers always
> produce field dicts with `SubhaloPos` in **kpc/h** and `SubhaloSpin` in **(kpc/h)(km/s)**.
> `hdf5_writer` stores these values as-is. `binary_writer._pack_tree()` divides both by 1000
> internally before packing (binary reader does not apply the x0.001 factor that the HDF5
> reader does). Never scale these fields differently per format - the writer handles the
> conversion. See `reference/sage_lhalotree_hdf5_schema.md` (project root) Section 5.4 for the full table.

### 3. Performance constraint

- All tree-walking and pointer reconstruction must be **O(N) or O(N log N)**.
- **O(N^2) is not acceptable.** This includes any loop-within-loop structure over
  halos (e.g. scanning the full halo list for each halo to find its descendant).
- Use dictionary-based lookups for ID-to-index mapping (O(1) per lookup).
- See `.ai/skills/driver-authoring/references/pointer_reconstruction_patterns.md` for O(N) patterns.

If you find yourself writing a nested loop over halos, stop and redesign using
a hash map or sort-based approach before continuing.

**FOF chains.** Identify the true FOF central for this format (e.g. a parent-id of -1, a
union-find host, or a Subfind binding-rank field) and build the spatial pointers with
`utils.fof_topology.build_fof_chains` so the central heads `NextHaloInFOFGroup` - SAGE
iterates satellites from `Halo[central].NextHaloInFOFGroup`, so the most massive member is
*not* necessarily the head. Expose FOF reconstruction as a dedicated function. Flyby merging
(folding a forest's extra z=0 centrals into one) is opt-in via `sim_params["merge_flybys"]`
using `utils.fof_topology.merge_flybys` - never on by default.

**No hardcoded simulation constants.** A driver targets a *family* of simulations (shared
halo finder + merger tree + file format), so particle mass, box size, and N-particles must
not be hardcoded to one simulation. Source them: (1) `sim_params` override, (2) derive from
the data - use `utils.sim_params.estimate_particle_mass` when a mass and particle count are
available, (3) else fail or warn loudly.

### 4. Write location

Write the draft driver to `assets/drivers/<format_id>.py`.
**Do not write to `conversion-engine/drivers/` at this stage.**
The driver is moved to `conversion-engine/drivers/` only in Stage 4 via `kdb-register` (Path A).

### 5. Error handling

- The driver must `raise ConversionError(<message>)` (imported from `errors`) on any
  error. `main_driver.convert_one` propagates the message verbatim, so the batch runner
  can report the real cause - including across worker processes, where a driver's stderr
  would otherwise be lost. The standard pattern is a terminal handler in `convert()`:

  ```python
  from errors import ConversionError

  try:
      ...  # conversion work
  except ConversionError:
      raise
  except Exception as exc:
      raise ConversionError(f"conversion failed - {exc}") from exc
  ```

- Do not call `sys.exit(1)`; it is caught as a generic failure and hides the cause.
- Do not silently skip invalid data or continue past errors.
- Use informative error messages: include the tree index, halo index, and the
  field name in any error output.

### 6. Progress bars (tqdm)

Wrap all per-tree iteration loops with `tqdm`. When using `SplitWriter`, pass the
iterable directly to `tqdm`:

```python
from tqdm import tqdm
from utils.split_writer import SplitWriter

with SplitWriter(...) as writer:
    for fields in tqdm(tree_stream, desc="Converting trees", unit="tree"):
        writer.write_tree(fields)
```

- The `desc=` label must be meaningful (e.g. `"Converting trees"`).
- The progress bar must be at the **outer tree loop level**, not the halo level.
- `tqdm` is pre-installed in the container; import with `from tqdm import tqdm`.

### 6a. Auxiliary index file filtering

If the input format uses a simulation-wide index file (e.g. `forests.list`,
`locations.dat`) that maps tree IDs to file positions, **filter it to only the root
IDs present in the current input file(s)** before loading:

```python
# 1. Collect root IDs from the actual input files
root_id_filter: set[int] = set()
for fp in input_files:
    with open(fp) as fh:
        for line in fh:
            if line.startswith("#tree"):
                root_id_filter.add(int(line.split()[1]))

# 2. Pass the filter to the index parser
forest_data = _parse_forests_list(forests_list_path, root_id_filter)
```

This prevents loading O(all_simulation_trees) data in each SLURM array task, which
would scale to O(n_tasks x index_size) total memory across the job array.

### 7. Reference the template driver

Read `.ai/skills/driver-authoring/assets/driver_template.py` as a skeleton before
writing the new driver. It is a live symlink to the canonical
`conversion-engine/drivers/_template.py` (never drifts) and documents the required
function signatures, import patterns, the FOF and particle-mass patterns, and the
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
environment. **Do not modify `pyproject.toml`** - that file governs the container
image dependencies and is not part of a conversion session.

### 9. Run the Stage 2 test conversion

The driver lives in `assets/drivers/` and is not yet registered in
`conversion-engine/main_driver.py` (registration happens in Stage 4 via `kdb-register`, Path A).
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
    n_output_files=1,
)
EOF
```

Replace `<format_id>` and `<base>` with the actual values. For `lhalo_binary` output,
change the output path to `"assets/test_<base>_STC.0"` and `output_format` to
`"lhalo_binary"`. Pass a `sim_params` dict if a `--sim-config` JSON was supplied by
the user; otherwise `None` is correct.

**Stage 2 always uses `n_output_files=1`** regardless of what the user chose at G1.
The test slice is small; splitting adds no benefit. Stage 3 passes the G1-confirmed
`n_output_files` value.
