# Agent Directives: Analytical Questioning Strategy

Your primary goal during **STATE 1 (Discovery)** and **STATE 2 (Analysis Report)** is to move from initial file ambiguity to a definitive mapping structure using context-aware dialogue.

## 1. Dialogue Architecture (STATE 1 -> STATE 2 transition)

1. **Acknowledge:** Confirm file targeting and parse paths.
2. **Database Lookup:** Check `format-database/` for previously saved JSON mappings using inferred Primitive aliases (e.g., "Rockstar").
3. **Execution Phase Constraint:** During your analysis, use brief tabular summaries. Do NOT use sprawling conversational prose.
4. **The Gate Rule (CRITICAL):** You MUST NOT proceed past STATE 2 (writing conversion mapping scripts) without explicit, affirmative `user_approval` of your schema and validation checklist.

## 2. The Resolution Matrix

When inspecting source fields against SAGE destination targets, you MUST execute questioning based on the following logic matrix to resolve uncertainty. Do NOT ask generic "What does this mean?" questions.

| Ambiguity Scenario (Trigger) | Mandatory LLM Action | Questioning Archetype (Use this format) |
| :--- | :--- | :--- |
| **Unit Scaling Parity** (e.g., $10^{10} M_\odot/h$ vs $M_\odot$) | Confirm scalar multiplier before writing code. | *"I see `SubhaloMass` in $10^{10} M_\odot$. Shall I treat this directly as the virial mass for SAGE without scaling?"* |
| **Multiple Candidates** (e.g., `Vel` vs `VelDisp` lists) | Evaluate array shapes; query user for semantic definition. | *"I found `Vel` and `VelDisp`. As SAGE requires bulk velocity, I will map `Vel`. Is this correct?"* |
| **Inverse Coordinate Logic** (e.g., Snapshots 100 -> 0) | Propose reversal mathematics to match SAGE 0 -> N. | *"Snapshot vectors descend (100 -> 0). I will reverse this sequence to align with SAGE architecture. Any objections?"* |
| **Pointer Synthesisation** (e.g., missing `NextProgenitor`) | Propose tree-stitching traversal map relying on host IDs. | *"The data is forward-linked only. I will synthesize `FirstProgenitor` and `NextProgenitor` arrays by traversing the host IDs. Do you approve this schema?"* |

## 3. Communication Constraints

* **Strict Confidence Scoring:** If your Primitive Knowledge lookup gives you low confidence in a mapping, you MUST declare your confidence level (e.g., *"Confidence: 40% - This structure is non-standard."*)
* **Zero Jargon:** Use physical terminology (`virial radius`, `comoving offset`) instead of local code variables (`col_3`, `var_r`).
* **Table Dependency:** Always package your hypothetical proposed Field Schema (Source -> Target) into a simple Markdown table before requesting the required STATE 2 user approval.
