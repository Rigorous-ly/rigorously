---
name: citation-verify
description: >
  Verify bibliography entries against real databases.
  Triggers: creating bib files, adding citations, "check references",
  "verify citations", editing bibliography, adding new references.
---

# Citation Verification

Verify that every citation in a bibliography or manuscript references a real,
published work with correct metadata.

## When to Use

- After creating or editing `.bib` files
- When adding new citations to a manuscript
- Before submission to verify all references
- When asked to "check references" or "verify citations"

## How to Run

### Full bibliography check

```bash
rigorous cite-check path/to/references.bib
```

### Check citations in a manuscript

```bash
rigorous cite-check path/to/paper.tex --format latex
rigorous cite-check path/to/paper.md --format markdown
```

### Check a single reference

```bash
rigorous cite-check --doi "10.1234/example"
```

### Via MCP

Use the `rigorous.cite_check` tool with parameters:
- `file`: path to bib file or manuscript
- `format`: `bibtex`, `latex`, or `markdown`
- `doi`: optional single DOI to verify

## What It Checks

1. **DOI resolution** -- does the DOI resolve to a real record?
2. **Metadata accuracy** -- do authors, title, year, journal match the DOI record?
3. **Retraction status** -- has the paper been retracted?
4. **Duplicate entries** -- are there duplicate keys or DOIs?
5. **Missing fields** -- are required fields (author, year, title, journal) present?

## Example Output

```
PASS  [best2010]     Best et al. 2010 -- DOI verified, metadata matches
WARN  [smith2019]    Year mismatch: bib says 2019, CrossRef says 2020
FAIL  [jones2021]    DOI does not resolve -- possible fabricated reference
WARN  [doe2018]      Paper retracted 2022-03-15
```

## Exit Codes

- `0` -- all citations verified
- `1` -- warnings (metadata mismatches, retractions)
- `2` -- failures (unresolvable DOIs, missing references)
