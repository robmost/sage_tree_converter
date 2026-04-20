---
name: primitive-mapping
description:
  This skill guides the agent in deducing File Format, Halo Finder, and Merger Tree Tool combinations, and synthesizing missing physics fields to be SAGE-compatible.
---
# SAGE Primitive Mapping Skill

## Skill Context

When you need to parse a new or unknown N-body simulation format and map its structural fields to SAGE requirements, rely on this skill.

## 1. References & Assets

You have access to the following resources in this skill's directory:

- **`references/core-knowledge.md`**: Defines the Primitive Knowledge Matrix and mandatory synthesisation rules (e.g., for missing Spin or Velocity Dispersion).
- **`references/questioning-strategy.md`**: The dialogue architecture and resolution matrix used to resolve ambiguities with the user.
- **`assets/format_database_template.json`**: The strict schema blueprint for saving successful format mappings.

## 2. Reproducibility & Execution Rules

To ensure reproducibility when mapping new formats:

1. **Database Consistency:** Always verify against `format-database/` in the workspace root to see if a prior mapping exists for the given primitive alias before creating a new one.
2. **Schema Uniformity:** When a new mapping schema is finalized and approved by the user, you MUST export it to `format-database/` strictly using the `assets/format_database_template.json` structure. Do not invent new JSON keys or nestings.
3. **Synthesisation Enforcement:** If a field is missing, ALWAYS apply the physics approximations listed in `core-knowledge.md` rather than asking the user for random workarounds.

## 3. Invocation Trigger

Activate this skill when:

- The `conversion-workflow` is in **STATE 1 (Discovery)** or **STATE 2 (Analysis Report)**.
- The user provides a new dataset format that lacks an existing mapping.
