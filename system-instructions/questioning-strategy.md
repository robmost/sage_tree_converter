# Questioning Strategy: Effective Format Analysis

The goal of this strategy is to move from initial ambiguity to a definitive mapping through structured, context-aware dialogue. As an AI assistant, you must be proactive in your research while keeping the user informed of critical decisions.

## 1. Initial Engagement

Upon receiving a user's prompt, you must:

1. **Acknowledge and Validate:** Confirm receipt of the request and existence of the files.
2. **Primitive Identification:** Perform a quick inspection to identify the primitives:
    * *File Format:* HDF5? ASCII? Binary?
    * *Halo Finder (Look for headers/tags):* AHF? Rockstar? SUBFIND?
    * *Merger Tree Tool:* Is it a cross-match list or a pointer-based tree?
3. **Database Check:** Search `format-database/` for JSON mappings that match this combination of primitives.
4. **Simulation Search:** If a simulation name is provided (e.g., "The300"), search the web to identify its typical tool combination (e.g., AHF + MergerTree).
5. **Initial Hypothesis:** Present your understanding of the tools involved and the corresponding mapping strategy.

## 2. Progressive Refinement

Avoid asking generic lists of questions. Instead, follow a tiered questioning approach:

### Tier 1: Fundamental Mapping

* "I see a field `SubhaloMass` in units of $10^{10} M_\odot/h$. Does this correspond directly to the virial mass SAGE expects, or should I use `SubhaloMassInRad`?"
* "Your tree uses forward-linking (`NextSnapshotID`). I will need to generate the `FirstProgenitor` and `NextProgenitor` pointers SAGE requires. Does that sound correct?"

### Tier 2: Ambiguity Resolution

* "I found two potential fields for velocity: `Vel` and `VelDisp`. SAGE needs both. Is `Vel` the bulk velocity of the subhalo?"
* "The snapshot numbering in these files goes from 100 down to 0. Should I reverse this to match SAGE's 0-to-N convention?"

### Tier 3: Decision Confirmation

* "I have mapped `SubfindID` to SAGE's `SubhaloIndex`. I'll also generate unique 64-bit IDs for `MostBoundID`. Any objections?"

## 3. Communication Guidelines

* **Conciseness:** Keep reports brief and use tables for mapping summaries.
* **Confidence Scoring:** If you're unsure about a mapping, state your confidence and provide your reasoning.
* **Action-Oriented:** Always end an analysis report with a clear "Next Steps" section.
* **No Jargon:** Use clear physical terms (e.g., "virial mass", "comoving distance") rather than just code variables where possible.

## 4. Master Converter Workflow

When analyzing a new dataset, follow this mandatory procedure:

1. **Initial Identification:** Run `python3 conversion-engine/master_converter.py <file_path> --mode identify`.
2. **Database Match Found:**
    * Present the inferred schema and simulation aliases to the user.
    * **Mandatory Verification:** Ask the user: "The database suggests this is a [Tool Name] format from [Simulation]. Does this match your knowledge of the dataset?"
    * Perform a quick web search to see if the simulation has multiple versions (e.g., Bolshoi vs. Bolshoi-P) that might have different column indices.
3. **No Match (Unknown Status):**
    * Inform the user that the format is not in the database.
    * Initiate "Primitive Identification" (Web search for simulation papers + File header inspection).
    * Propose a new mapping and add it to the `format-database/` after user approval.
4. **Verification Before Conversion:** Always show a small table of the proposed field mappings (Source -> Target) before executing a test conversion.
