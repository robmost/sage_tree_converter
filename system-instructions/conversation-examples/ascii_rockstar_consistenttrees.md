# Rockstar ConsistentTrees ASCII Conversion Example

**User:** "I have a Bolshoi dataset processed with Rockstar and ConsistentTrees. Please convert it to SAGE format."

**Assistant:**
I see the dataset.

## STATE 1: Initialization & Discovery

- **Files Found:** `out_*.list` scattered ASCII outputs.
- **Database Match:** Matched `format-database/ascii_rockstar_consistenttrees.json`.

**Completeness Check:**
The required positional and physics columns are present across the `.list` headers.

## STATE 2: Analysis Report

Rockstar stores Host and Subhalo properties via FOFS group linkages based on the `upid` field.

| Rockstar Field (Source) | SAGE Field (Target) | Units/Action |
| :--- | :--- | :--- |
| `mvir` (Col 10) | **Mvir** | Msun/h |
| `x(17), y(18), z(19)` | **Pos** | Mpc/h |
| `vx(20), vy(21), vz(22)` | **Vel** | km/s |
| `upid` (Col 6) | **FOF_Group** | Map hierarchy. `upid == -1` defines host block. |

**Intended Validation Checklist:**
I will generate the following 7 mandatory plots for standard physics verification:

1. `mah` (Evolution)
2. `merger_rate` (Evolution)
3. `spin` (Evolution)
4. `velocity` (Histogram)
5. `lifespan` (Histogram)
6. `hmf` (Histogram)
7. `spatial` (Hexbin)

**Proposed Next Step:**
I require your **EXPLICIT APPROVAL** of this mapping and validation layout. Upon approval, I will execute a test parsing constraint.

**User:** "Approved. Go ahead."

**Assistant:**
Understood. Moving to State 3.

## STATE 3: Test Engine

Extracting the first 100 halos iteratively so memory limits are respected.

**Test Results:**

- **Output:** `output/0_test_sage_tree_bolshoi.hdf5`
- **Validation:** Syntactic loop structures resolve flawlessly. Semantic boundaries properly mapped the hierarchy for the sampled halos.
*(No visualisations generated during this test cycle).*

Moving to State 4.

## STATE 4: Full Suite & Export

Processing the full Rockstar list.

**Final Conversion Results:**

- **Primary Data Output:** `output/0_full_sage_tree_bolshoi.hdf5`
- **Validation Log:** Recorded fully to `output/0_validation_log_bolshoi.md`.
- **Validation Plots:**
  - `output/1_validation_mah_bolshoi.png`
  - `output/1_validation_merger_rate_bolshoi.png`
  - `output/1_validation_spin_bolshoi.png`
  - `output/1_validation_velocity_bolshoi.png`
  - `output/1_validation_lifespan_bolshoi.png`
  - `output/1_validation_hmf_bolshoi.png`
  - `output/1_validation_spatial_bolshoi.png`
- **Cleanup:** `assets/cli-scripts/` emptied, ad-hoc files moved to `output/audit-logs/bolshoi_scripts/`.

Conversion complete.
