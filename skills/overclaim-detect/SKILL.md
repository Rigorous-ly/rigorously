---
name: overclaim-detect
description: >
  Scan papers for overclaimed language and unsupported assertions.
  Triggers: writing results sections, "check for overclaims",
  "is this too strong", reviewing manuscript language, drafting conclusions.
---

# Overclaim Detection

Scan manuscript text for language that overstates findings beyond what the
evidence supports.

## When to Use

- When writing or editing results and discussion sections
- When asked "check for overclaims" or "is this too strong"
- Before submission to audit all claims
- When reviewing conclusions against methodology

## How to Run

### Scan a manuscript

```bash
rigorous overclaim path/to/paper.tex
rigorous overclaim path/to/paper.md
```

### Scan specific sections

```bash
rigorous overclaim path/to/paper.tex --sections results,discussion,abstract
```

### Via MCP

Use the `rigorous.overclaim` tool with parameters:
- `file`: path to manuscript
- `sections`: optional comma-separated section filter

## What It Detects

1. **Causal language without causal design** -- "X causes Y" from correlational data
2. **Universals without universal evidence** -- "always", "never", "all cases"
3. **Novelty inflation** -- "first ever", "unprecedented", "never before"
4. **Hedge removal** -- conclusions stronger than the stated limitations allow
5. **Scope creep** -- claims that extend beyond the study population or conditions
6. **Missing qualifiers** -- assertions that lack "in this model", "under these conditions"

## Example Output

```
LINE 142  STRONG  "This proves that serotonin drives mood"
          -> Suggest: "These results are consistent with serotonin contributing to mood"
          -> Reason: ODE model results do not constitute causal proof

LINE 287  MEDIUM  "For the first time, we show..."
          -> Suggest: "To our knowledge, this is the first demonstration of..."
          -> Reason: Cannot verify global novelty without exhaustive review

LINE 301  WEAK    "always produces oscillatory behavior"
          -> Suggest: "produces oscillatory behavior across all tested parameter ranges"
          -> Reason: Universal claim limited to explored parameter space
```

## Exit Codes

- `0` -- no overclaims detected
- `1` -- overclaims found (see report)
