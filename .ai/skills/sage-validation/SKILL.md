# SAGE Validation Protocol Skill

## 1. Modular Reference Architecture

To prevent instruction drift, read ONLY the relevant rule files for your current workflow state:

- **When in STATE 3:**
  - Read `references/syntactic_functional_rules.md`

- **When in STATE 4:**
  - **MANDATORY CONTEXT RESET:** Before starting STATE 4, you MUST explicitly inform the user that you are clearing your internal "working memory" to ensure instruction fidelity.
  - **First:** Read `references/global_semantic_rules.md` for the overarching constraints (3-Panel Architecture, Anti-Shortcut rules).
  - **Second:** Read `references/semantic_evolution_rules.md` for MAH, Merger Rate, and Spin constraints.
  - **Third:** Read `references/semantic_distribution_rules.md` for HMF, Velocity, Lifespan, and Spatial constraints.
  - **MANDATORY REGISTRY READ:** Read `assets/format_specs.json` for physics formulas and unit scales.
  - **THE SEVEN MANDATORY PLOTS:** You MUST generate all 7 visualisations:
    1. **mah** (Evolution: Mass growth)
    2. **merger_rate** (Evolution: Progenitor count)
    3. **spin** (Evolution: Specific angular momentum)
    4. **velocity** (Histogram: Velocity modulus)
    5. **lifespan** (Histogram: Branch depth)
    6. **hmf** (Histogram: Mass function)
    7. **spatial** (Hexbin: XY distribution)
  - **GATE:** Before writing any semantic validation code, you MUST output a "Fact Summary" table mapping every one of these 7 plot IDs to its specific formula and axes. You MUST verify this list against the inlined list above.

## 2. Automation Steps & Programmatic Checkups (CRITICAL)

DO NOT rely on visual OCR inspection of generated plot images. You MUST programmatically validate the data arrays *during* the execution of the semantic validation scripts:

- Assert `np.any(np.isnan(data))` is false.
- Ensure log-scale arrays do not contain exact zeros (which indicates unhandled invalid halos).
- Check that data bounds (min/max) are physically plausible.
- **Topology Assertions (Fail-Fast):** All validation scripts MUST implement built-in assertions to explicitly verify any constraints listed in the `topology_warnings` array of the active format mapping (found in `format-database/`). If the `topology_warnings` array is empty or missing, no assertions are required. If the script violates these bounds, it must throw an error.
- If an anomaly is detected, flag it, inform the user, and **EXPLICITLY ask** if they want you to action the anomaly.
- **Resource Warnings:** If you detect the dataset is exceptionally large, warn the user *before* processing and ask for authorization.
- **Completeness Check:** You MUST call `sage_validation_utils.verify_completeness(dataset_name)` at the absolute end of the validation script. This function will raise an AssertionError if any of the 7 mandatory plots are missing.

## 3. Post-Validation Workflow

After executing the semantic validation scripts:

1. **Report Results:** Present a summary of any warnings or errors found during the syntactic and semantic checks to the user.
2. **Anomaly Follow-Through:** If a programmatic checkup (§2) detects an anomaly and the user authorises action: investigate the root cause, create any auxiliary diagnostic files in `output/intermediates/`, fix the mapping/code, regenerate the validation, and document all debugging steps taken in the `0_validation_log_<dataset>.md`.
3. **Propose Fixes:** If validation fails, use the findings to adjust the mapping and rerun the test conversion. Do not wait for the user to diagnose the failure themselves.

## 4. Mandatory Sub-Agent Auditor Protocol (Two-Step Semantic Validation)

Before generating and executing ANY semantic validation script, you MUST complete the following sequence:

1. **Traversal Strategy Phase:** If the format uses pointers (e.g., L-HaloTree), explicitly explain your strategy for traversing the raw input pointers backward in time. You MUST NOT skip this traversal.
2. **Generate Script:** Write the semantic validation script.
3. **Sub-Agent Review:** Do NOT simulate the Auditor yourself. You MUST delegate the code review to a separate sub-agent (invoke `codebase-investigator` if using Gemini CLI, or `Explore` if using Claude Code). Provide the sub-agent with the generated script, `format_specs.json`, the `topology_warnings`, and `references/audit_checklist.md`. Explicitly document the sub-agent's findings in `0_validation_log_<dataset>.md`.
4. **Execution:** Execute only if approved.

## 5. Tool Parity

**CRITICAL RESTRICTION**: You are FORBIDDEN from modifying `sage_validation_utils.py` or writing custom matplotlib plotting routines. You MUST import `plot_3x3_evolution`, `plot_1x3_histogram`, and `plot_1x3_hexbin` from `assets/sage_validation_utils.py`. You MUST read the raw simulation input file to serve as the ground-truth "Input" arrays for these functions. You must pre-process and format your raw parsed arrays to match its expected inputs, rather than changing the utility functions. Direct `plt.savefig()` and `plt.close()` calls are strictly forbidden in generated scripts.

## 6. STATE 5: Post-Conversion Knowledge Base Update

After a conversion and validation cycle is fully complete (State 4):

1. **GATE (Wait for Yes):** Ask the user if the conversion was satisfactory `[y/N]`. **DO NOT PROCEED** until the user explicitly says "yes" or "looks good". If the user says "no", return to the debugging/execution states until the conversion is correct.
2. **Prompt for Update:** Once the user confirms success, ask if they want to add any hints to the `format-database` for future conversions `[y/N]`.
3. **AI Summarization:** If yes, take the user's raw feedback and distill it into concise, single-sentence directives for `topology_warnings` or `testing_hints`.
4. **Cap Enforcement:** The hint arrays in the JSON file MUST be capped at a maximum of **5** entries each.
   - If adding a new hint would exceed the cap of 5, you MUST offer the user two choices: (A) manually select which old hint to replace, or (B) let the AI propose an automated replacement. If the user chooses B, you must propose the change and wait for user confirmation before writing to the database.
