# h5py Code Patterns for Syntactic Validation

Common h5py patterns used in `run_syntactic_checks.py` and manual validation.

## Opening a file safely

```python
import h5py

try:
    f = h5py.File(path, "r")
except Exception as e:
    print(f"FAIL Check 1 — File integrity: {e}")
    raise SystemExit(1)
```

## Listing all Tree groups

```python
tree_names = sorted([k for k in f.keys() if k.startswith("Tree")])
n_trees = len(tree_names)
```

## Reading header attributes and TreeNHalos

```python
hdr = f["Header"]
n_trees_attr = int(hdr.attrs["NtreesPerFile"])
n_halos_attr = int(hdr.attrs["NhalosPerFile"])
tree_n_halos = hdr["TreeNHalos"][:]   # dataset, not attribute
```

## Checking mandatory fields in a tree group

```python
MANDATORY_FIELDS = {
    "Descendant", "FirstProgenitor", "NextProgenitor",
    "FirstHaloInFOFGroup", "NextHaloInFOFGroup",
    "Len", "Group_M_Crit200", "SubhaloVMax", "MostBoundID",
    "SnapNum", "Pos", "SubhaloVel", "SubhaloSpin",
}

for tree_name in tree_names:
    grp = f[tree_name]
    present = set(grp.keys())
    missing = MANDATORY_FIELDS - present
    if missing:
        print(f"FAIL Check 2 — Missing fields in {tree_name}: {missing}")
```

## Vectorised pointer range check (O(N))

```python
import numpy as np

def check_pointer_range(arr, N, field_name, tree_name):
    bad = np.where((arr < -1) | (arr >= N))[0]
    if len(bad):
        print(f"FAIL Check 3/4 — {field_name} in {tree_name}: "
              f"{len(bad)} out-of-range values, first at index {bad[0]}")
        return False
    return True
```

## Vectorised snapshot ordering check (O(N))

```python
def check_temporal_ordering(snap, Descendant, FirstProgenitor, NextProgenitor,
                             tree_name):
    ok = True
    # Descendant must be at a strictly later snapshot
    mask = Descendant != -1
    if np.any(snap[Descendant[mask]] <= snap[np.where(mask)[0]]):
        print(f"FAIL Check 3 — Descendant snapshot ordering violated in {tree_name}")
        ok = False
    # Progenitors must be at a strictly earlier snapshot
    mask = FirstProgenitor != -1
    if np.any(snap[FirstProgenitor[mask]] >= snap[np.where(mask)[0]]):
        print(f"FAIL Check 3 — FirstProgenitor snapshot ordering violated in {tree_name}")
        ok = False
    mask = NextProgenitor != -1
    if np.any(snap[NextProgenitor[mask]] >= snap[np.where(mask)[0]]):
        print(f"FAIL Check 3 — NextProgenitor snapshot ordering violated in {tree_name}")
        ok = False
    return ok
```

## Spatial pointer same-snapshot check (O(N))

```python
def check_spatial_ordering(snap, FoF, Next, tree_name):
    ok = True
    mask = FoF != -1
    if np.any(snap[FoF[mask]] != snap[np.where(mask)[0]]):
        print(f"FAIL Check 4 — FirstHaloInFOFGroup crosses snapshot in {tree_name}")
        ok = False
    mask = Next != -1
    if np.any(snap[Next[mask]] != snap[np.where(mask)[0]]):
        print(f"FAIL Check 4 — NextHaloInFOFGroup crosses snapshot in {tree_name}")
        ok = False
    return ok
```

## Property range check (O(N))

```python
def check_property_ranges(grp, tree_name):
    ok = True
    mass = grp["Group_M_Crit200"][:]
    if not np.all(np.isfinite(mass)):
        print(f"FAIL Check 6 — Group_M_Crit200 has NaN/Inf in {tree_name}")
        ok = False
    if np.any(mass < 0) or np.any(mass > 1e6):
        print(f"FAIL Check 6 — Group_M_Crit200 out of [0, 1e6] in {tree_name}")
        ok = False
    vel_mag = np.linalg.norm(grp["SubhaloVel"][:], axis=1)
    if np.any(vel_mag > 10000):
        print(f"FAIL Check 6 — SubhaloVel magnitude > 10000 km/s in {tree_name}")
        ok = False
    pos = grp["Pos"][:]
    if not np.all(np.isfinite(pos)):
        print(f"FAIL Check 6 — Pos has NaN/Inf in {tree_name}")
        ok = False
    return ok
```
