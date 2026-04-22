---
name: script-auditor
description:
  This skill manages the lifecycle of ad-hoc validation scripts generated during the SAGE conversion workflow. It prevents workspace bloat and enforces clean execution environments while retaining reproducibility.
---
# CLI Script Auditor Skill

## Skill Context

During the conversion process, you will write multiple Python scripts (e.g., test parsers, visualization scripts) into `assets/cli-scripts/`. This skill dictates how to manage them post-execution.

## 1. Reproducibility & Retention Rules

To ensure the CLI environment remains reproducible without accumulating technical debt:

1. **No Proactive Reuse:** Scripts written for previous datasets MUST NOT be proactively read or scavenged for code. Each new dataset requires a fresh derivation to prevent cross-contamination of logic.
2. **Post-Validation Auditing:** Scripts must only be retained as an audit trail for forensic debugging.
3. **Execution Gate:** This skill MUST ONLY be executed at the very end of **STATE 4 (Full Suite)**, *after* the programmatic data validation checkup is fully complete and approved.

## 2. Execution Actions

When this skill is triggered at the end of STATE 4, you MUST perform the following actions:

1. Create a dataset-specific, timestamped audit directory to ensure unique runs on the same dataset remain distinct: `output/audit-logs/<dataset_name>_<YYYYMMDD_HHMMSS>_scripts/`.
2. Move all `.py` or auxiliary scripts generated during the current session from `assets/cli-scripts/` into the newly created audit directory.
3. Leave `assets/cli-scripts/` completely empty, ready for the next conversion session.

## 3. Invocation Trigger

Activate this skill when:

- **STATE 4 (Full Suite)** has successfully concluded, the validation log is written, and you are preparing to present the final completion report to the user.
- The user explicitly requests a workspace cleanup or audit flush.
