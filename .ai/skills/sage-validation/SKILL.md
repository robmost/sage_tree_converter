---
name: sage-validation
description:
  This skill enforces the rigorous Syntactic, Semantic, and Functional validation protocols for SAGE merger tree conversions. It ensures programmatic data checkups and consistent plotting architectures.
---
# SAGE Validation Protocol Skill

## Skill Context

When you are tasked with validating a converted SAGE merger tree, you MUST adhere strictly to the protocols defined in this skill.

## 1. References & Assets

You have access to the following resources in this skill's directory to ensure reproducibility:

- **`references/validation-protocols.md`**: The master ruleset detailing the exact checks, 3-panel plotting architecture, and execution protocol. **READ THIS FILE FIRST** before attempting validation.
- **`assets/sage_validation.mplstyle`**: The mandatory Matplotlib stylesheet for all generated validation plots.
- **`assets/validation_log_style.md`**: The strict markdown template for recording the final validation log.

## 2. Reproducibility & Execution Rules

To guarantee reproducibility across all runs and environments, you MUST follow these guidelines:

1. **Asset Paths:** When writing Python validation scripts, always reference the mplstyle using its absolute path or relative path from the workspace root (e.g., `plt.style.use('.ai/skills/sage-validation/assets/sage_validation.mplstyle')`).
2. **Programmatic Checkups:** Do NOT rely on visual inspection (OCR) of plot images. You MUST write scripts that programmatically assert that data arrays are physically plausible (e.g., no `NaN`s, no exact zeros in log-scale arrays) before saving any PNG files.
3. **Log Enshrinement:** Always generate the `0_validation_log_<dataset>.md` strictly following the format in `assets/validation_log_style.md`. Do not improvise the log structure.

## 3. Invocation Trigger

Activate this skill when:

- The `conversion-workflow` enters **STATE 3 (Test Engine)** or **STATE 4 (Full Suite)**.
- The user explicitly asks to "validate" or "plot" merger tree data.
