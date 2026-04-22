# The Semantic Validation Audit Checklist

> [!CAUTION]
> **ANTI-SYCOPHANCY ADVERSARIAL DIRECTIVE:**
> When acting as the Auditor, you MUST assume the generated code is flawed. You are forbidden from simply answering "Yes" to these checklist items. For every item, you MUST perform a **Two-Phase Review**:
>
> 1. **Phase 1 (Shortcut Search):** Explicitly search for and cite any code that *looks* like a shortcut (e.g., setting `in_data = out_data`, reverse-mathing from output, placeholders, skipping required logic). If you find a shortcut, the script **FAILS** immediately.
> 2. **Phase 2 (Compliance Proof):** Only if Phase 1 is clean, cite the **exact line number(s)** and the **exact code snippet** that explicitly performs the required independent action.
>
> If you cannot point to the exact line of code for both phases, the script **FAILS** the audit.

Before executing any semantic validation script, apply the Two-Phase Review to the following:

## 0. Completeness Audit (MANDATORY FIRST STEP)

- [ ] **Check:** Does the script contain logic to generate ALL 7 mandatory plots (refer to `SKILL.md` for the list)?

## 1. Independent Input Extraction (ANTI-SHORTCUT ENFORCEMENT)

- [ ] **Check:** Does the script read the raw source files directly instead of reading the converted SAGE HDF5 output?
- [ ] **Check:** Does the script explicitly traverse raw input pointers (e.g., `FirstProgenitor`) independently?

## 2. Zero-Mass Filtering

- [ ] **Check:** Are halos with mass $\le 0$ filtered out before selection for Evolution plots?

## 3. Lowest Available Redshift Filtering

- [ ] **Check:** Is data for distribution plots restricted to the lowest available redshift?

## 4. Proper Utility Function Usage

- [ ] **Check:** Does the script use the hardened plotting functions from `sage_validation_utils.py`?

## 5. Topological Match Enforcement & Performance

- [ ] **Check:** Does the script use `OriginalID` to filter the HDF5 output to match the input subset exactly?
- [ ] **Check:** Does the script use O(1) dictionary lookups for performance?

## 6. Data Parity & Precision

- [ ] **Check:** Is **Unit Scaling Parity** enforced?
- [ ] **Check:** Is **Physical Definition Parity (Spin)** enforced?

## 7. Redundant File Operations

- [ ] **Check:** Does the script explicitly AVOID calling `plt.savefig()` or `plt.close()` after invoking functions from `sage_validation_utils.py`?

***

**Audit Failure Protocol:**
If *any* of the above checks fail or lack explicit Phase 1/2 citations, you MUST halt, explain the failure, and regenerate a new script.
