# SAGE Conversion Validation Log

**Date:** {YYYY-MM-DD}
**Simulation Name:** {Simulation Name}
**Original Format/Halo Finder:** {e.g., L-HaloTree / Bpstat}

## 1. Syntactic Validation

| Check | Status (Pass/Fail) | Script Used (in `assets/cli-scripts/`) | Output/Notes |
| --- | --- | --- | --- |
| File Integrity | {Pass/Fail} | {Script File Name} | {Details/Error} |
| Pointer Integrity | {Pass/Fail} | {Script File Name} | {Details/Error} |
| Snapshot Consistency | {Pass/Fail} | {Script File Name} | {Details/Error} |

---

## 2. Auditor Review

> **AUDITOR SECTION — DO NOT EDIT MANUALLY.**
> This section is populated exclusively by the Auditor persona during the Two-Step Semantic Validation Protocol. The Auditor's approval is a prerequisite for Section 3 (Semantic Validation) to be executed.

**Script Under Review:** `{Script File Name}`
**Auditor Verdict:** `{APPROVED / REJECTED}`

### Checklist Findings

#### 2.1 Independent Input Extraction

- **Status:** `{Pass/Fail}`
- **Citation:** Line(s) `{N}–{M}` — `{exact code snippet}`
- **Notes:** {Auditor observation or reason for failure.}

#### 2.2 Zero-Mass Filtering

- **Status:** `{Pass/Fail}`
- **Citation:** Line(s) `{N}–{M}` — `{exact code snippet}`
- **Notes:** {Auditor observation or reason for failure.}

#### 2.3 Lowest Available Redshift Filtering

- **Status:** `{Pass/Fail}`
- **Citation:** Line(s) `{N}–{M}` — `{exact code snippet}`
- **Notes:** {Auditor observation or reason for failure.}

#### 2.4 Proper Utility Function Usage

- **Status:** `{Pass/Fail}`
- **Citation:** Line(s) `{N}–{M}` — `{exact code snippet}`
- **Notes:** {Auditor observation or reason for failure.}

#### 2.5 Topological Match Enforcement & Performance

- **Status:** `{Pass/Fail}`
- **Citation:** Line(s) `{N}–{M}` — `{exact code snippet}`
- **Notes:** {Auditor observation or reason for failure.}

#### 2.6 Data Parity & Precision — Unit Scaling

- **Status:** `{Pass/Fail}`
- **Citation:** Line(s) `{N}–{M}` — `{exact code snippet}`
- **Notes:** {Auditor observation or reason for failure.}

#### 2.7 Data Parity & Precision — Physical Definition (Spin)

- **Status:** `{Pass/Fail}`
- **Citation:** Line(s) `{N}–{M}` — `{exact code snippet}`
- **Notes:** {Auditor observation or reason for failure.}

#### 2.8 Data Parity & Precision — Temporal NaN Padding

- **Status:** `{Pass/Fail}`
- **Citation:** Line(s) `{N}–{M}` — `{exact code snippet}`
- **Notes:** {Auditor observation or reason for failure.}

#### 2.9 Data Parity & Precision — Topological Branch Confinement

- **Status:** `{Pass/Fail}`
- **Citation:** Line(s) `{N}–{M}` — `{exact code snippet}`
- **Notes:** {Auditor observation or reason for failure.}

### Auditor Summary

> {Concise statement of overall script compliance. If REJECTED, state which item(s) failed and confirm the script has been discarded for rewriting. If APPROVED, confirm all eight items passed and grant execution clearance.}

---

## 3. Semantic Validation

| Check | Status (Pass/Fail) | Script Used (in `assets/cli-scripts/`) | Output Image Saved in `output/` | Notes |
| --- | --- | --- | --- | --- |
| Mass Growth (MAH) | {Pass/Fail} | {Script File Name} | {Image Filename} | {Observation} |
| Velocity Distributions | {Pass/Fail} | {Script File Name} | {Image Filename} | {Observation} |
| Spatial Integrity | {Pass/Fail} | {Script File Name} | {Image Filename} | {Observation} |
| Unit Conversion Check | {Pass/Fail} | {Script File Name} | {N/A or Image} | {Observation} |
| Merger Rate & Topology | {Pass/Fail} | {Script File Name} | {Image Filename} | {Observation} |
| Lifespan Distribution | {Pass/Fail} | {Script File Name} | {Image Filename} | {Observation} |
| Spin Continuity | {Pass/Fail} | {Script File Name} | {Image Filename} | {Observation} |
| Mass Function | {Pass/Fail} | {Script File Name} | {Image Filename} | {Observation} |

## 4. Functional Validation

| Check | Status (Pass/Fail) | Notes |
| --- | --- | --- |
| Small Sample Test | {Pass/Fail} | {Success criteria met?} |
| SAGE Dry Run | {Pass/Fail/Skipped} | {Log/Error} |

## Final Conclusion

{Summary of validation run and confirmation of data readiness for SAGE. Must reference the Auditor's verdict from Section 2.}
