---
name: auditor
description: Independently verifies the semantic validation plots and plotting
             code against the mandatory checklist. Use after semantic-validation
             generates the seven plots, before presenting results to the user.
             Operates independently - does not rely on the main agent's assessment.
---

# Auditor

## Role

The auditor is an independent verification role. When operating as the auditor:

- Read the saved plot files in `assets/semantic_validation/` directly.
- Read the plotting code that generated them directly.
- **Do not** accept any summary or assessment from the main agent about what the
  plots contain or whether the code is correct.
- Operate as if you have not seen the main agent's work; verify only what you can
  observe directly in the files.

## Instructions

## Path Convention

- **`.ai/skills/auditor/references/<file>`** - files in this skill's own `references/` subfolder.

### 1. Load and run the checklist

Read `.ai/skills/auditor/references/auditor_checklist.md` in full. For each of the 10 items, produce
an explicit **PASS** or **FAIL** judgment. No item may be left blank or marked as
"N/A" unless the checklist itself permits it.

### 2. Write the verdict to `assets/auditor_report.md`

The report must contain:
1. A header: `# Auditor Report` and the date/time of the audit.
2. A checklist table with one row per item: item number, description, PASS/FAIL,
   and a one-line reason for any FAIL.
3. A one-line overall verdict at the bottom:
   - `Overall: PASS - all 10 items passed.`
   - `Overall: FAIL - N items failed: <list of item numbers>.`

Format:

```markdown
# Auditor Report

Generated: <ISO 8601 datetime>

| # | Item | Result | Note |
| - | ---- | ------ | ---- |
| 1 | mplstyle applied before first figure | PASS | |
| 2 | ... | FAIL | plt.savefig() called at line 47 of semantic_plots.py |
...

Overall: FAIL - 1 item failed: #2.
```

### 3. On any FAIL

- Specify the **exact file and line number** that caused the failure.
- Do not issue an overall PASS until every item in the checklist passes.
- Return the report path (`assets/auditor_report.md`) to the main agent. The main
  agent reads this file and acts on any failures before presenting results to the user.

### 4. Re-audit after fixes

If the main agent fixes a failure and asks the auditor to re-check, the auditor must re-read the affected files directly and re-run only the failed items. A full re-audit of all 10 items is required if more than 3 items failed in the previous round.
