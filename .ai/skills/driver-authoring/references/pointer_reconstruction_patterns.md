# O(N) Pointer Reconstruction Patterns

This file documents O(N) and O(N log N) patterns for building LHaloTree integer
pointer arrays. All patterns avoid O(N^2) nested loops.

The detailed worked examples with code are in
`.ai/skills/format-discovery/references/pointer_reconstruction.md`. This file
focuses on design patterns and complexity guarantees.

---

## Pattern 1: Hash Map ID Lookup (O(N))

**When to use:** Input stores links as global or per-snapshot halo IDs.

**Design:**

1. Build a dictionary `{halo_id: flat_index}` in one pass over the halo array. O(N).
2. For each halo, look up its link ID in the dictionary. O(1) per halo -> O(N) total.
3. Non-existent IDs (no link) map to -1 via `dict.get(id, -1)`.

**Complexity:** O(N) time, O(N) space.
**Antipattern to avoid:** `for i in range(N): for j in range(N): if id[j] == link_id[i]` - this is O(N^2).

---

## Pattern 2: Sort-then-Scan (O(N log N))

**When to use:** Need to group halos by a key (e.g. group_id, descendant_id) and
then process each group.

**Design:**

1. Sort halos by the grouping key using `numpy.argsort` or `sorted()`. O(N log N).
2. Use `numpy.searchsorted` or `itertools.groupby` to iterate over groups. O(N).
3. Process each group independently in O(group_size) time.

**Complexity:** O(N log N) time, O(N) space.
**Antipattern to avoid:** For each unique group ID, scan the full halo list to find members - O(N x num_groups) ~ O(N^2) in the worst case.

---

## Pattern 3: defaultdict Grouping (O(N))

**When to use:** Building the progenitor chain (FirstProgenitor, NextProgenitor)
from a Descendant array.

**Design:**

```python
from collections import defaultdict

progenitors = defaultdict(list)
for i in range(N):
    desc = Descendant[i]
    if desc != -1:
        progenitors[desc].append(i)  # O(1) amortised per halo

for desc_idx, prog_list in progenitors.items():
    prog_list.sort(key=lambda i: mass[i], reverse=True)  # O(k log k) per group
    FirstProgenitor[desc_idx] = prog_list[0]
    for j in range(len(prog_list) - 1):
        NextProgenitor[prog_list[j]] = prog_list[j + 1]
```

The inner sort is O(k log k) per group; summed over all groups, this is O(N log N)
because the group sizes sum to N.

**Complexity:** O(N log N) time (dominated by sort), O(N) space.

---

## Pattern 4: Pre-sorted Input (O(N))

**When to use:** Input is already sorted in LHaloTree depth-first order (e.g. the
Gadget-2 LHaloTree binary format stores halos in walk order). Pointers are
already integer indices into the per-tree array.

**Design:**

1. Copy pointer arrays directly without transformation.
2. Verify all values are in `[-1, N-1]` using `numpy.all((arr >= -1) & (arr < N))`. O(N).
3. Verify temporal constraints using vectorised comparisons. O(N).

**Complexity:** O(N) time.

---

## Pattern 5: FOF Group Chain Building (O(N))

**When to use:** Building FirstHaloInFOFGroup and NextHaloInFOFGroup.

**Invariant (read this first):** SAGE walks a FOF group's satellites by starting at
`Halo[FirstHaloInFOFGroup].NextHaloInFOFGroup` and following the chain. The **true FOF
central must head the chain** - *not merely the most massive member*. A stripped central
can be lighter than one of its satellites; if you head the chain by mass alone, SAGE skips
every halo listed before the central and undercounts z=0 satellites. This is a universal
LHaloTree requirement, so every driver that builds FOF chains must enforce it, using
whatever signal identifies the central in that format:

| Format | Central definition |
|--------|--------------------|
| Consistent-Trees | `upid == -1` |
| AHF | union-find top central (`hostHaloID == 0` ancestor) |
| Gadget-4 (SubLink) | smallest `SubhaloNr` in the group (`SubRankInGr` is absent) |

**Design:** build a per-halo `central_idx` array (the flat index of each halo's FOF central,
self for centrals) and pass it to the shared helper `utils.fof_topology.build_fof_chains`,
which groups by `(snap, central)`, orders members by `sort_value` descending, forces the
central to the head, and returns both pointer arrays:

```python
from utils.fof_topology import build_fof_chains

# central_idx[i] = flat index of halo i's FOF central (i for a central), resolved per
# format (upid==-1, union-find host, or min SubhaloNr). sort_value is typically mass.
FirstHaloInFOFGroup, NextHaloInFOFGroup = build_fof_chains(snap, central_idx, sort_value)
```

For a vectorised driver (large flat arrays), reproduce the same result with a lexsort that
places the central first within each `(snap, group)` group, then `descending sort_value`.

**Complexity:** O(N log N) (dominated by the per-group sort), O(N) space.

### Flyby merging (Consistent-Trees / union-find forests) - OPT-IN

A forest can contain several independent z=0 FOF centrals. SAGE's native Consistent-Trees
reader applies `fix_flybys`, which demotes every non-dominant z=0 central to a satellite of
the most massive one. This is a **modelling choice, not a correctness fix** - it materially
changes the z=0 population (e.g. ~55k halos flip Type-0 -> Type-1 in micro-uchuu), and some
readers (MIMIC) deliberately keep flyby groups independent. Expose it as opt-in via
`sim_params["merge_flybys"]` (default off) and apply it with
`utils.fof_topology.merge_flybys`, which also sign-flips the demoted centrals' MostBoundID
(canonical flyby marker) where the format provides one. Do **not** enable it by default.

---

## Complexity Checklist

Before submitting a driver for Stage 2 testing, verify:

- [ ] No loop that iterates over all N halos is nested inside another loop over N halos.
- [ ] All ID-to-index mappings use a dict or numpy array lookup, not linear search.
- [ ] Any sort is applied once per group (or once total), not once per halo.
- [ ] numpy vectorised operations are used where possible instead of Python loops.
