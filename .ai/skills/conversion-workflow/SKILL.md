---
name: conversion-workflow
description:
  This skill strictly enforces the state machine workflow and workspace locality constraints for the SAGE merger tree converter. It ensures a linear, gate-driven progression from discovery to final export.
---
# SAGE Conversion Workflow Skill

## Skill Context

You MUST act as a secure state machine. You are not allowed to skip states or perform actions out of order.

## 1. Workspace Locality Router

To maintain a reproducible environment, all file interactions MUST strictly adhere to this routing table:

- `.ai/skills/`: **READ.** Contains all AI execution guidelines.
- `format-database/`: **READ/WRITE.** Check for existing simulation mappings. Save successful JSON mappings here.
- `assets/cli-scripts/`: **WRITE.** Save all ad-hoc Python validation scripts or data parsers you generate here.
- `output/`: **WRITE.** Save all validation plots, `0_validation_log_*.md` logs, and target test samples (`0_test_sage_tree*.hdf5`) here.
- `output/intermediates/`: **WRITE.** Save all volatile intermediate extracted data here.
- `output/audit-logs/`: **WRITE / CONDITIONAL READ.** Save archived scripts here. NEVER proactively read from this folder to hunt for reusable code during a standard pipeline.

## 2. State Machine Execution Protocol

Advance sequentially through these states. Do NOT skip states.

- **STATE 1 (Initialization & Discovery):** Perform file inspection by first auditing file sizes (`ls -lh`), then using bounded reads (`head -n 20` or equivalent) for format identification. Check `format-database/` for priors. Never dump full file contents to the terminal. **GATE:** Proceed to STATE 2 when analysis is complete.
- **STATE 2 (Analysis Report):** Present findings and proposed mapping schema in a table. List intended validation steps. **GATE:** EXPLICIT USER APPROVAL is required over the mapping before writing conversion code.
- **STATE 3 (Test Engine):** Write conversion mappings. Process a small/fast dataset variant. Generate `0_test_sage_tree_<name>.hdf5`. **GATE:** Natively execute and pass the **Syntactic** and **Functional** validation checklist steps on this sample. **DO NOT perform Semantic Validation (plotting) in this state.**
- **STATE 4 (Full Suite, Data Checkup, & Export):** Process the entire dataset. Generate all mandatory **Semantic** plots. Perform the data checkup gate (via `sage-validation` skill). After full validation, write the final log and execute the `script-auditor` skill.

## 3. Invocation Trigger

Activate this skill unconditionally at the start of any new conversion session to frame the workflow.
