# O(N) Tree-Walking Patterns

All traversal of merger tree structure must use the patterns in this file.
Every pattern here is O(N) or O(depth) per tree. O(N^2) patterns are forbidden.

---

## Pattern 1: Walk the main progenitor branch (depth-first, O(depth))

The main progenitor branch follows `FirstProgenitor` from the root halo back to the
earliest ancestor. At each step you visit one halo. Total work is O(branch_depth).

```python
def main_progenitor_branch(root_idx, FirstProgenitor, SnapNum, data_array):
    """Collect (snapshot, value) pairs along the main progenitor branch."""
    snaps, values = [], []
    h = root_idx
    while h != -1:
        snaps.append(SnapNum[h])
        values.append(data_array[h])
        h = FirstProgenitor[h]
    return snaps, values
```

Use this for MAH, merger rate (step 1: identify main branch), and angular momentum.

---

## Pattern 2: Count progenitors at each snapshot (O(N))

Build a count array by scanning all halos once: for each halo, if its `Descendant`
points to a main-branch halo at snapshot s, increment the count at snapshot s.

```python
def count_progenitors_per_snapshot(tree_halos, Descendant, SnapNum,
                                   main_branch_indices):
    """Count progenitors per snapshot for a single tree.

    main_branch_indices: set of flat indices that are on the main branch.
    """
    main_branch_set = set(main_branch_indices)
    counts = {}
    for i, desc in enumerate(Descendant):
        if desc != -1 and desc in main_branch_set and i not in main_branch_set:
            snap_of_desc = SnapNum[desc]
            counts[snap_of_desc] = counts.get(snap_of_desc, 0) + 1
    return counts  # {snapshot: n_progenitors}
```

Total cost: O(N) per tree - one pass over all halos.

---

## Pattern 3: Walk all progenitors of a single halo (O(k), k = number of progenitors)

To visit all progenitors (major + minor mergers) of halo `i`:

```python
def all_progenitors(i, FirstProgenitor, NextProgenitor):
    """Yield all direct progenitors of halo i."""
    p = FirstProgenitor[i]
    while p != -1:
        yield p
        p = NextProgenitor[p]
```

The chain follows `FirstProgenitor` then `NextProgenitor` until sentinel `-1`.
This is O(k) where k is the number of progenitors - never O(N).

---

## Pattern 4: Walk all halos in a FOF group (O(g), g = group size)

```python
def fof_group_members(i, FirstHaloInFOFGroup, NextHaloInFOFGroup):
    """Yield all halos in the FOF group of halo i."""
    central = FirstHaloInFOFGroup[i]
    member = central
    while member != -1:
        yield member
        member = NextHaloInFOFGroup[member]
```

---

## Pattern 5: Compute lifespan for all root halos (O(N) total)

Lifespan = number of distinct snapshots on the main progenitor branch.

```python
def compute_lifespans(root_indices, FirstProgenitor, SnapNum):
    """Compute lifespan (branch depth) for a list of root halos. O(N) total."""
    lifespans = []
    for root in root_indices:
        depth = 0
        h = root
        while h != -1:
            depth += 1
            h = FirstProgenitor[h]
        lifespans.append(depth)
    return lifespans
```

The sum of all branch depths is at most N (each halo appears on at most one
main branch), so the total cost across all trees is O(N).

---

## Antipatterns - do not use

```python
# BAD: O(N^2) - for each halo, search all halos for progenitors
for i in range(N):
    progenitors_of_i = [j for j in range(N) if Descendant[j] == i]
```

```python
# BAD: O(N^2) - nested loop over snapshots x halos
for snap in snapshots:
    halos_at_snap = [h for h in range(N) if SnapNum[h] == snap]
```

Use `defaultdict` or `numpy` grouping instead:

```python
# GOOD: O(N) - group by snapshot in one pass
from collections import defaultdict
halos_by_snap = defaultdict(list)
for h in range(N):
    halos_by_snap[SnapNum[h]].append(h)
```
