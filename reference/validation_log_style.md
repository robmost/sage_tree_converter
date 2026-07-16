# Validation Log Style Guide

This document defines the required structure and content of the validation log
(`assets/validation_log.md`) produced during a conversion session. The log is written
at the end of Stage 2 and extended at the end of Stage 3. Dynamic fields are shown as
`<placeholder>`.

---

## Log File Template

```markdown
# Validation Log

## Header

| Field           | Value                          |
| --------------- | ------------------------------ |
| Dataset name    | <dataset_name>                 |
| Input format    | <format_id>                    |
| Date / Time     | <ISO 8601 datetime, e.g. 2025-07-14T09:32:00Z> |
| Session ID      | <timestamp-based or UUID, e.g. 20250714-093200> |

---

## Stage 2: Test Conversion Validation

**Trees tested:** <N> (first <N> trees, `--n-trees <N>`)

### Syntactic Checks

| # | Check                        | Result | Details                          |
| - | ---------------------------- | ------ | -------------------------------- |
| 1 | File integrity               | PASS / FAIL | <reason if FAIL>            |
| 2 | Schema compliance            | PASS / FAIL | <reason if FAIL>            |
| 3 | Pointer integrity - temporal | PASS / FAIL | <reason if FAIL>            |
| 4 | Pointer integrity - spatial  | PASS / FAIL | <reason if FAIL>            |
| 5 | Snapshot consistency         | PASS / FAIL | <reason if FAIL>            |
| 6 | Property consistency         | PASS / FAIL | <reason if FAIL>            |

**Overall syntactic result:** PASS / FAIL

### Functional Validation

**Result:** PASS / FAIL / NOT RUN

**Reason (if NOT RUN):** `SAGE_BINARY_PATH` not set in `.env`.

**Details (if FAIL):**

- SAGE exit code: <exit_code>
- Error message from SAGE log: <error_excerpt>

### Errors Encountered and Resolutions

- <Error 1 description> -> <Resolution applied>
- <Error 2 description> -> <Resolution applied>
- _(none)_ if no errors occurred

---

## Stage 3: Full Conversion and Semantic Validation

### Semantic Validation Plots

| Plot file                              | Status      |
| -------------------------------------- | ----------- |
| `assets/semantic_validation/mah.pdf`              | PASS / FAIL |
| `assets/semantic_validation/merger_rate.pdf`      | PASS / FAIL |
| `assets/semantic_validation/angular_momentum.pdf` | PASS / FAIL |
| `assets/semantic_validation/hmf.pdf`              | PASS / FAIL |
| `assets/semantic_validation/velocity_dist.pdf`    | PASS / FAIL |
| `assets/semantic_validation/lifespan_dist.pdf`    | PASS / FAIL |
| `assets/semantic_validation/spatial_dist.pdf`     | PASS / FAIL |

### Auditor Sub-agent Verdict

**Overall verdict:** PASS / FAIL

**Checklist summary:** See `assets/auditor_report.md` for the full per-item breakdown.

### Issues Found in Stage 3

For each issue, classify as **plotting error** or **conversion error**:

| # | Description | Classification | Resolution |
| - | ----------- | -------------- | ---------- |
| 1 | <description> | plotting / conversion | <action taken> |

_(none)_ if no issues were found.

---

## Signature

| Field              | Value                  |
| ------------------ | ---------------------- |
| User approval time | <ISO 8601 datetime>    |
| User comments      | <free text or "None">  |
```

---

## Notes on Usage

- The log is created (with Stage 2 content only) when Gate G2 is presented to the user.
- The Stage 3 section is appended after Gate G3.
- Every PASS/FAIL field must be filled; no blank cells are permitted.
- The "Errors Encountered and Resolutions" list must record every fix cycle, even
  if the final result is PASS. An empty list is acceptable only if no errors occurred.
- The signature block is filled in only after the user confirms at Gate G3.
