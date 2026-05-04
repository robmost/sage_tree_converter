# Pointer Reconstruction

All five pointer fields (`Descendant`, `FirstProgenitor`, `NextProgenitor`,
`FirstHaloInFOFGroup`, `NextHaloInFOFGroup`) must be integer indices into the flat
per-tree halo array of the same `Tree<X>` group. They are never file-global.
The sentinel value `-1` means "no link".

---

## Case A: Global Halo ID Links

The input stores links as global halo IDs (e.g. AHF MergerTree format, where
`DescendantID` is the AHF halo ID of the descendant in the next snapshot).

### Hint Case A: Algorithm (O(N))

```python
# Build id → flat_index map for all halos in this tree
id_to_idx = {halo_id[i]: i for i in range(N)}

# Descendant
for i in range(N):
    desc_id = raw_DescendantID[i]
    Descendant[i] = id_to_idx.get(desc_id, -1)

# FirstProgenitor and NextProgenitor
# Group halos by their DescendantID; sort each group by mass descending
from collections import defaultdict
progenitors = defaultdict(list)
for i in range(N):
    if Descendant[i] != -1:
        progenitors[Descendant[i]].append(i)

FirstProgenitor[:] = -1
NextProgenitor[:] = -1
for desc_idx, prog_list in progenitors.items():
    # Sort by mass descending to identify the main progenitor
    prog_list.sort(key=lambda i: mass[i], reverse=True)
    FirstProgenitor[desc_idx] = prog_list[0]
    for j in range(len(prog_list) - 1):
        NextProgenitor[prog_list[j]] = prog_list[j + 1]
```

---

## Case B: Scale-Factor-Indexed Links (Consistent Trees)

Consistent Trees stores links as `(scale_factor, halo_id)` pairs, where the
scale factor identifies the snapshot and the halo ID identifies the halo within
that snapshot.

### Hint Case B: Algorithm (O(N log N))

```python
# Build (scale, id) → flat_index map
from collections import defaultdict
snap_id_to_idx = {}
for i in range(N):
    snap_id_to_idx[(snap[i], halo_id[i])] = i

# Descendant
for i in range(N):
    key = (desc_scale[i], desc_id[i])
    Descendant[i] = snap_id_to_idx.get(key, -1)

# FirstProgenitor / NextProgenitor: same grouping as Case A, applied after
# Descendant is reconstructed.
```

---

## Case C: Pre-built LHaloTree Pointers

Some formats (e.g. Gadget-2 LHaloTree HDF5) already store integer indices in the
LHaloTree convention. These can be copied directly **only if** they are tree-local
(i.e. indices refer to positions within the same `Tree<X>` group, not to
file-global positions).

### Hint Case C: Verification (O(N))

```python
N = len(Descendant)
assert all(-1 <= v < N for v in Descendant), "Out-of-range Descendant index"
assert all(-1 <= v < N for v in FirstProgenitor), "Out-of-range FirstProgenitor"
# ... repeat for all five pointer fields
```

If the input uses file-global indices, convert them by subtracting the offset of the
first halo in the tree from each non-sentinel value.

---

## FOF Group Pointer Reconstruction

`FirstHaloInFOFGroup` and `NextHaloInFOFGroup` link halos within the same FOF group
at the same snapshot. The central halo points to itself via `FirstHaloInFOFGroup`.

### Hint FOF: Algorithm (O(N))

```python
from collections import defaultdict

# Group halos by (snapshot, group_id); identify central as the most massive
groups = defaultdict(list)
for i in range(N):
    groups[(snap[i], group_id[i])].append(i)

FirstHaloInFOFGroup[:] = -1
NextHaloInFOFGroup[:] = -1

for (sn, gid), members in groups.items():
    # Central = most massive halo in the group
    members.sort(key=lambda i: mass[i], reverse=True)
    central = members[0]
    for m in members:
        FirstHaloInFOFGroup[m] = central
    # Build the satellite chain
    for j in range(len(members) - 1):
        NextHaloInFOFGroup[members[j]] = members[j + 1]
    # Last member's NextHaloInFOFGroup stays -1 (already initialised)
```

For formats that already identify central vs. satellite (e.g. via `HostHaloID`):

```python
for i in range(N):
    if host_halo_id[i] == halo_id[i]:
        # This halo IS the central
        FirstHaloInFOFGroup[i] = i
    else:
        # Satellite: map HostHaloID to flat index
        FirstHaloInFOFGroup[i] = id_to_idx.get(host_halo_id[i], -1)
```

---

## Snapshot Constraint Verification

After reconstruction, verify temporal pointer constraints:

```python
for i in range(N):
    if FirstProgenitor[i] != -1:
        assert snap[FirstProgenitor[i]] < snap[i], \
            f"Progenitor of halo {i} is not at an earlier snapshot"
    if Descendant[i] != -1:
        assert snap[Descendant[i]] > snap[i], \
            f"Descendant of halo {i} is not at a later snapshot"
    if FirstHaloInFOFGroup[i] != -1:
        assert snap[FirstHaloInFOFGroup[i]] == snap[i], \
            f"FOF group central of halo {i} is at a different snapshot"
```
