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

## Case B: Depth-First Index Links (Consistent Trees)

Consistent Trees pre-computes depth-first index (DFI) fields that make temporal
pointer reconstruction O(N) without building explicit link maps. Halos within each
`#tree` block are stored in depth-first order. FOF group membership is encoded via
`upid` (col 6), the global halo ID of the ultimate host central at the same snapshot.

Key columns: `id` (1), `desc_id` (3), `upid` (6), `Depth_first_ID` (28),
`Next_coprogenitor_depthfirst_ID` (32).

### Hint Case B: Algorithm (O(N))

```python
# Build lookup maps (O(N))
id_to_idx  = {int(ids[i]):  i for i in range(N)}  # global halo ID → flat index
dfi_to_idx = {int(dfis[i]): i for i in range(N)}  # DFI → flat index

# Descendant — desc_id is the global ID of the descendant halo
for i in range(N):
    desc[i] = id_to_idx.get(int(desc_ids[i]), -1)  # -1 when desc_id == -1

# FirstProgenitor — depth-first ordering: halos[i+1] is the first progenitor
# of halos[i] iff halos[i+1].desc_id == halos[i].id. No map needed.
for i in range(N - 1):
    if int(desc_ids[i + 1]) == int(ids[i]):
        FirstProgenitor[i] = i + 1

# NextProgenitor — Next_coprogenitor_depthfirst_ID (col 32) is the globally-
# sequential DFI of the next sibling progenitor. DFIs are unique across the
# whole file; all co-progenitors of a halo are within the same #tree block.
for i in range(N):
    nc_dfi = int(next_coprog_dfis[i])
    NextProgenitor[i] = dfi_to_idx.get(nc_dfi, -1)  # -1 when nc_dfi == -1

# FirstHaloInFOFGroup — upid is the global ID of the ultimate host central.
# Self-pointer when upid == -1 (halo is its own central).
# Unresolved upid (cross-forest or cross-file reference) also falls back to self.
for i in range(N):
    uid = int(upids[i])
    FirstHaloInFOFGroup[i] = i if uid == -1 else id_to_idx.get(uid, i)

# NextHaloInFOFGroup — group by (snap, central_idx); sort by mvir desc; link
from collections import defaultdict
groups = defaultdict(list)
for i in range(N):
    groups[(int(snaps[i]), int(FirstHaloInFOFGroup[i]))].append(i)
for members in groups.values():
    members.sort(key=lambda i: mvirs[i], reverse=True)
    for j in range(len(members) - 1):
        NextHaloInFOFGroup[members[j]] = members[j + 1]
```

### Forest-level processing — required for correct FOF group links

`upid` frequently references halos in **other** `#tree` blocks within the same
Consistent Trees forest. Processing each block independently causes those lookups
to fail, silently treating every affected satellite as its own central — this
produces a systematic deficit of massive galaxies after SAGE (~4× in practice).

**Fix:** when `forests.list` and `locations.dat` are present, combine all `#tree`
blocks of a complete forest into one array before calling reconstruction.
`id_to_idx` then covers the full forest, resolving all cross-tree `upid` references.

```python
# forests.list: TreeRootID → ForestID
# locations.dat: TreeRootID → (filepath, byte_offset)  ← O(1) random access

combined = np.vstack([
    read_tree_at_offset(path, offset)
    for tree_id in forest_to_trees[forest_id]
    for path, offset in [tree_to_offset[tree_id]]
])
pointers = reconstruct_pointers(combined)  # cross-tree upid now resolved
```

A forest is *complete* when every tree listed in `forests.list` for it has an entry
in `locations.dat`. Incomplete forests (e.g. a single-shard Bolshoi file where most
forests span multiple files) fall back to per-tree processing automatically.

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
