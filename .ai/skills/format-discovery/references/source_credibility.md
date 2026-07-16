# Source Credibility Criteria

When searching for merger tree format documentation, evaluate each source against
the tiers below. Use the highest-tier source available. Always record the source URL
or citation in the `references` field of the mapping JSON.

## Tier 1 — Official Source (highest trust)

- The official code repository for the halo finder or tree tool (GitHub, GitLab,
  Bitbucket, or institutional hosting)
- Official documentation pages linked from the repository README
- README files, wiki pages, or `doc/` directories within the official repository
- In-code documentation in the official source (e.g. comments describing column order,
  struct definitions, HDF5 dataset names)

**When to use:** Always prefer this over all other sources. If the field list is in
source code (e.g. a struct or a `write_output` function), read it directly.

## Tier 2 — Peer-reviewed Publication

- The primary paper introducing the halo finder or tree tool
- Papers that describe the output format in a methods section
- Located via: NASA ADS (`ui.adsabs.harvard.edu`), arXiv (`arxiv.org`)

**When to use:** When Tier 1 is unavailable or incomplete. Record the full citation
(Author et al., Year, Journal/arXiv, DOI).

## Tier 3 — Reference Implementation

- A third-party code that reads or writes the format (e.g. a known analysis pipeline
  that parses the same files)
- Must be publicly visible and clearly associated with the format in question

**When to use:** When Tier 1 and Tier 2 are unavailable. Confirm field names against
the actual input file headers to reduce the risk of version mismatches.

## Tier 4 — Author or Project Web Page

- The personal or institutional web page of the halo finder / tree tool authors
- Tutorial pages that show example file content

**When to use:** As a supplement to Tier 1–3, or when Tier 1–3 are unavailable.

## Tier 5 — Secondary Discussion (lowest trust)

- Forum posts, Stack Overflow answers, mailing list archives
- Blog posts or tutorials written by third parties

**When to use:** Only as a last resort. Every field derived from a Tier 5 source must
be explicitly flagged to the user with a note that it is unverified.

## Recording Sources

Every candidate mapping written to `assets/proposed_mapping_<format_id>.json` must
include the URL or citation in the `references` array. If multiple sources were used,
list all of them with a note on which fields each source covers.

## Stopping Criterion

Stop searching when:

1. A complete field list for all mandatory SAGE fields has been found, OR
2. The missing fields have been confirmed as absent in the format (sentinel values), AND
3. The pointer semantics are fully documented.

Do not continue searching once these conditions are met.
