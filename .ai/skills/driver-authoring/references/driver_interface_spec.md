# Driver Interface Specification

## Function signature

```python
def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
) -> None:
```

Both `convert()` and `read_trees()` are public functions every driver module must expose. The main driver
(`conversion-engine/main_driver.py`) imports it by name:

```python
from drivers.<format_id> import convert
convert(input_path, output_path, n_trees=n_trees, sim_params=sim_params, output_format=output_format)
```

Do not rename it, add required positional arguments, or add return values.

## Parameters

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `input_path` | str | Yes | Absolute or relative path to the input file or input directory (format-dependent). |
| `output_path` | str | Yes | Absolute or relative path for the output file (`.hdf5` extension for `lhalo_hdf5`; no extension for `lhalo_binary`). The driver creates this file; it must not assume the parent directory exists (create it with `os.makedirs(os.path.dirname(output_path), exist_ok=True)` if needed). |
| `n_trees` | int or None | No | If not None, convert only the first `n_trees` trees. Used in Stage 2 test mode. When `n_trees` is given, the output file is still a valid SAGE LHaloTree file containing exactly `n_trees` trees with correct internal indexing. |
| `sim_params` | dict or None | No | Simulation parameter overrides loaded from `--sim-config` JSON. Recognised keys: `particle_mass_msun_per_h` (Msun/h), `n_particles_per_side`, `box_size_mpc_per_h`, `omega_m`, `omega_l`, `h0`. All optional; drivers fall back to auto-detection when absent. Extract with `(sim_params or {}).get("key")`. |

## Required output file structure

### lhalo_hdf5

The driver must produce a file that matches `reference/sage_lhalotree_hdf5_schema.md`
exactly:

```text
output.hdf5
├── Header/
│   ├── [attr] ParticleMass         — float64, 10^10 M_sun/h
│   ├── [attr] NtreesPerFile        — int32
│   ├── [attr] NhalosPerFile        — int32
│   ├── [attr] NumberOfOutputFiles  — int32
│   └── TreeNHalos                  — 1D int32 dataset, length = NtreesPerFile
└── Tree0/
    ├── Descendant             — int32 (N,)
    ├── FirstProgenitor        — int32 (N,)
    ├── NextProgenitor         — int32 (N,)
    ├── FirstHaloInFOFGroup    — int32 (N,)
    ├── NextHaloInFOFGroup     — int32 (N,)
    ├── SubhaloLen             — int32 (N,)
    ├── Group_M_Crit200        — float32 (N,)
    ├── SubhaloVMax            — float32 (N,)
    ├── SubhaloIDMostBound     — int64 (N,)
    ├── SnapNum                — int32 (N,)
    ├── SubhaloPos             — float32 (N, 3)  [kpc/h on disk]
    ├── SubhaloVel             — float32 (N, 3)
    └── SubhaloSpin            — float32 (N, 3)  [(kpc/h)(km/s) on disk]
...
└── Tree<NtreesPerFile-1>/
    └── <same fields>
```

Optional fields (`Group_M_Mean200`, `Group_M_TopHat200`, `SubhaloVelDisp`, `FileNr`)
may be included with their sentinel values if not available in the input.

### lhalo_binary

The driver must produce a file that matches `reference/sage_lhalotree_binary_schema.md`
exactly. Use `conversion-engine/utils/binary_writer` — do not write the binary struct
manually.

```text
output          (no file extension)
  Offset 0:   int32  nforests
  Offset 4:   int32  totnhalos
  Offset 8:   int32[nforests]  nhalos_per_forest
  Offset 8+4*nforests: 104-byte halo_data records (sequential, all trees)
```

## h5py writing pattern (lhalo_hdf5)

```python
import h5py
import numpy as np

with h5py.File(output_path, "w") as f:
    # Header group
    hdr = f.create_group("Header")
    hdr.attrs["ParticleMass"] = np.float64(particle_mass)
    hdr.attrs["NtreesPerFile"] = np.int32(n_trees)
    hdr.attrs["NhalosPerFile"] = np.int32(total_halos)
    hdr.attrs["NumberOfOutputFiles"] = np.int32(1)
    hdr.create_dataset("TreeNHalos", data=tree_n_halos.astype(np.int32))

    # Tree groups
    from tqdm import tqdm
    for i in tqdm(range(n_trees), desc="Writing trees"):
        grp = f.create_group(f"Tree{i}")
        grp.create_dataset("Descendant",          data=descendant[i].astype(np.int32))
        grp.create_dataset("FirstProgenitor",     data=first_progenitor[i].astype(np.int32))
        grp.create_dataset("NextProgenitor",      data=next_progenitor[i].astype(np.int32))
        grp.create_dataset("FirstHaloInFOFGroup", data=first_halo_in_fof[i].astype(np.int32))
        grp.create_dataset("NextHaloInFOFGroup",  data=next_halo_in_fof[i].astype(np.int32))
        grp.create_dataset("SubhaloLen",          data=length[i].astype(np.int32))
        grp.create_dataset("Group_M_Crit200",     data=mass[i].astype(np.float32))
        grp.create_dataset("SubhaloVMax",         data=vmax[i].astype(np.float32))
        grp.create_dataset("SubhaloIDMostBound",  data=most_bound_id[i].astype(np.int64))
        grp.create_dataset("SnapNum",             data=snap_num[i].astype(np.int32))
        grp.create_dataset("SubhaloPos",          data=pos[i].astype(np.float32))   # kpc/h
        grp.create_dataset("SubhaloVel",          data=vel[i].astype(np.float32))
        grp.create_dataset("SubhaloSpin",         data=spin[i].astype(np.float32))  # (kpc/h)(km/s)
```

## binary_writer pattern (lhalo_binary)

```python
from utils import binary_writer

bw = binary_writer.BinaryWriter(output_path)
bw.write_header(n_trees=n_trees, tree_nhalos=tree_n_halos_array)
from tqdm import tqdm
for i in tqdm(range(n_trees), desc="Writing trees"):
    bw.write_tree(fields_dict)  # keys: SubhaloPos in kpc/h, SubhaloSpin in (kpc/h)(km/s)
bw.close()
```

`fields_dict` keys must match the mandatory field list in `reference/sage_lhalotree_binary_schema.md`
Section 4. The writer divides `SubhaloPos` and `SubhaloSpin` by 1000 internally before
struct-packing — do not pre-divide in the driver.

## Error handling contract

- On any unrecoverable error: print a message to stderr and call `sys.exit(1)`.
- Include the tree index, halo index, and field name in error messages.
- Do not use bare `except:` clauses that swallow exceptions silently.
- Do not write a partial output file on error; delete the incomplete file if created.

```python
import sys, os

try:
    # ... conversion ...
except Exception as e:
    print(f"ERROR in tree {tree_idx}: {e}", file=sys.stderr)
    if os.path.exists(output_path):
        os.remove(output_path)
    sys.exit(1)
```

## Module structure

```python
# <format_id>.py
import sys
import os
import numpy as np
import h5py
from tqdm import tqdm


def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
) -> None:
    # 1. Read input
    # 2. Apply field mapping and unit conversions
    # 3. Reconstruct pointers
    # 4. Write output (HDF5 via hdf5_writer or binary via binary_writer)
    ...


def read_trees(
    input_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
) -> dict[int, dict]:
    # Same parsing logic as convert() but accumulates into a dict instead of writing.
    # Returns {tree_idx: {field_name: np.ndarray}} with SAGE LHaloTree HDF5 units.
    ...
```

No other public functions beyond these two. Private helper functions (prefixed with `_`) are allowed.
