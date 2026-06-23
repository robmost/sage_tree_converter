# Driver Interface Specification

## Function signature

```python
def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
    n_output_files: int = 1,
) -> None:
```

`convert()` is the single public function every driver module must expose. The main driver
(`conversion-engine/main_driver.py`) imports it by name:

```python
from drivers.<format_id> import convert
convert(input_path, output_path, n_trees=n_trees, sim_params=sim_params,
        output_format=output_format, n_output_files=n_output_files)
```

Do not rename it, add required positional arguments, or add return values.

## Parameters

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `input_path` | str | Yes | Absolute or relative path to the input file or input directory (format-dependent). |
| `output_path` | str | Yes | Absolute or relative path for the output file (`.hdf5` extension for `lhalo_hdf5`; no extension for `lhalo_binary`). The driver creates this file; it must not assume the parent directory exists (create it with `os.makedirs(os.path.dirname(output_path), exist_ok=True)` if needed). |
| `n_trees` | int or None | No | If not None, convert only the first `n_trees` trees. Used in Stage 2 test mode. When `n_trees` is given, the output file is still a valid SAGE LHaloTree file containing exactly `n_trees` trees with correct internal indexing. |
| `sim_params` | dict or None | No | Simulation parameter overrides loaded from `--sim-config` JSON. Recognised keys: `particle_mass_msun_per_h` (Msun/h), `n_particles_per_side`, `box_size_mpc_per_h`, `omega_m`, `omega_l`, `h0`. All optional; drivers fall back to auto-detection when absent. Extract with `(sim_params or {}).get("key")`. |
| `output_format` | str | No | `"lhalo_hdf5"` (default, SAGE TreeType=1) or `"lhalo_binary"` (SAGE TreeType=0). Both are handled uniformly by `SplitWriter` - no format-conditional write blocks needed in the driver. |
| `n_output_files` | int | No | Number of output files to split trees across (default 1). `SplitWriter` derives file N paths from `output_path` by replacing the trailing index token (e.g. `.0.hdf5` -> `.1.hdf5`). `n_trees_total` MUST be known before opening `SplitWriter`. |

## Required output file structure

### lhalo_hdf5

The driver must produce a file that matches `reference/sage_lhalotree_hdf5_schema.md`
exactly:

```text
output.hdf5
├── Header/
│   ├── [attr] ParticleMass         - float64, 10^10 M_sun/h
│   ├── [attr] NtreesPerFile        - int32
│   ├── [attr] NhalosPerFile        - int32
│   ├── [attr] NumberOfOutputFiles  - int32
│   └── TreeNHalos                  - 1D int32 dataset, length = NtreesPerFile
└── Tree0/
    ├── Descendant             - int32 (N,)
    ├── FirstProgenitor        - int32 (N,)
    ├── NextProgenitor         - int32 (N,)
    ├── FirstHaloInFOFGroup    - int32 (N,)
    ├── NextHaloInFOFGroup     - int32 (N,)
    ├── SubhaloLen             - int32 (N,)
    ├── Group_M_Crit200        - float32 (N,)
    ├── SubhaloVMax            - float32 (N,)
    ├── SubhaloIDMostBound     - int64 (N,)
    ├── SnapNum                - int32 (N,)
    ├── SubhaloPos             - float32 (N, 3)  [kpc/h on disk]
    ├── SubhaloVel             - float32 (N, 3)
    └── SubhaloSpin            - float32 (N, 3)  [(kpc/h)(km/s) on disk]
...
└── Tree<NtreesPerFile-1>/
    └── <same fields>
```

Optional fields (`Group_M_Mean200`, `Group_M_TopHat200`, `SubhaloVelDisp`, `FileNr`)
may be included with their sentinel values if not available in the input.

### lhalo_binary

The driver must produce a file that matches `reference/sage_lhalotree_binary_schema.md`
exactly. Use `conversion-engine/utils/binary_writer` - do not write the binary struct
manually.

```text
output          (no file extension)
  Offset 0:   int32  nforests
  Offset 4:   int32  totnhalos
  Offset 8:   int32[nforests]  nhalos_per_forest
  Offset 8+4*nforests: 104-byte halo_data records (sequential, all trees)
```

## On-disk HDF5 layout (lhalo_hdf5, for reference)

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

## Writing output - use `SplitWriter` (both formats)

The blocks above show the raw on-disk layout for reference only. Drivers do **not** call
`hdf5_writer` or `binary_writer` directly - write through `SplitWriter`, which selects the
writer from `output_format`, streams trees, distributes them across `n_output_files`, and
deletes partial files on error (see `SKILL.md` section 2 and
`conversion-engine/drivers/_template.py`):

```python
from utils.split_writer import SplitWriter

with SplitWriter(
    output_path=output_path,
    output_format=output_format,
    n_output_files=n_output_files,
    n_trees_total=n_trees_total,   # must be known before opening
    particle_mass=particle_mass_1e10,
) as writer:
    for fields in tree_stream:     # one field dict per tree, in write order
        writer.write_tree(fields)
```

Each `fields` dict must contain the mandatory keys - single source
`conversion-engine/utils/schema.py::MANDATORY_FIELDS` - with `SubhaloPos` in kpc/h,
`SubhaloSpin` in (kpc/h)(km/s), masses in 10^10 Msun/h. For `lhalo_binary`, `SplitWriter`
divides `SubhaloPos` and `SubhaloSpin` by 1000 internally before struct-packing - do not
pre-divide in the driver.

## Error handling contract

- On any unrecoverable error: raise `ConversionError` (imported from `errors`) with a
  message describing the cause. `main_driver.convert_one` propagates that message so the
  batch runner can report it (including across worker processes). Do not call `sys.exit(1)`;
  it is caught as a generic failure and hides the cause.
- Include the tree index, halo index, and field name in error messages.
- Do not use bare `except:` clauses that swallow exceptions silently.
- Do not write a partial output file on error. When writing through `SplitWriter`, its
  `__exit__` already deletes partially-written files - do not call `os.remove()` yourself.

```python
from errors import ConversionError

try:
    # ... conversion ...
except ConversionError:
    raise
except Exception as exc:
    raise ConversionError(f"ERROR in tree {tree_idx}: {exc}") from exc
```

## Module structure

```python
# <format_id>.py
import sys
import os
import numpy as np
import h5py
from tqdm import tqdm

from errors import ConversionError


def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
    n_output_files: int = 1,
) -> None:
    # 1. Read input
    # 2. Apply field mapping and unit conversions
    # 3. Reconstruct pointers
    # 4. Write output via SplitWriter (HDF5 or binary, selected by output_format)
    ...
```

No other public functions. Private helper functions (prefixed with `_`) are allowed.
