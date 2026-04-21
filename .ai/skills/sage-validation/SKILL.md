# SAGE Validation Protocol Skill

## 1. Modular Reference Architecture

To prevent instruction drift, read ONLY the relevant rule files for your current workflow state:

- **STATE 3 (Syntactic/Functional):**
  - Read `references/syntactic_functional_rules.md`

- **STATE 4 (Full Suite - Semantic Validation):**
  - **First:** Read `references/global_semantic_rules.md` for the overarching constraints (3-Panel Architecture, Anti-Shortcut rules).
  - **Second:** Read `references/semantic_evolution_rules.md` for MAH, Merger Rate, and Spin constraints.
  - **Third:** Read `references/semantic_distribution_rules.md` for HMF, Velocity, Lifespan, and Spatial constraints.
  - **Always Refer To:** `assets/format_specs.json` for physics formulas, the visualisations registry, unit scales, and plotting defaults.

## 2. Automation Steps & Programmatic Checkups (CRITICAL)

DO NOT rely on visual OCR inspection of generated plot images. You MUST programmatically validate the data arrays *during* the execution of the semantic validation scripts:

- Assert `np.any(np.isnan(data))` is false.
- Ensure log-scale arrays do not contain exact zeros (which indicates unhandled invalid halos).
- Check that data bounds (min/max) are physically plausible.
- If an anomaly is detected, flag it, inform the user, and **EXPLICITLY ask** if they want you to action the anomaly.
- **Resource Warnings:** If you detect the dataset is exceptionally large, warn the user *before* processing and ask for authorization.

## 3. Post-Validation Workflow

After executing the semantic validation scripts:

1. **Report Results:** Present a summary of any warnings or errors found during the syntactic and semantic checks to the user.
2. **Anomaly Follow-Through:** If a programmatic checkup (§2) detects an anomaly and the user authorises action: investigate the root cause, create any auxiliary diagnostic files in `output/intermediates/`, fix the mapping/code, regenerate the validation, and document all debugging steps taken in the `0_validation_log_<dataset>.md`.
3. **Propose Fixes:** If validation fails, use the findings to adjust the mapping and rerun the test conversion. Do not wait for the user to diagnose the failure themselves.

## 4. Mandatory Auditor Persona (Two-Step Semantic Validation Protocol)

Before executing ANY semantic validation script, you MUST halt and adopt the "Auditor" persona as part of the **Two-Step Semantic Validation Protocol** (Step 1: generate script → Step 2: Auditor reviews against `references/audit_checklist.md` → Step 3: execute only if approved). Explicitly document the audit against the generated code in `0_validation_log_<dataset>.md`.

## 5. Tool Parity

All plotting MUST use `assets/sage_validation_utils.py`. Direct `plt.savefig()` and `plt.close()` calls are strictly forbidden in generated scripts.
