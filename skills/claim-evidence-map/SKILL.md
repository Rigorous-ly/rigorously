---
name: claim-evidence-map
description: >
  Map every claim in a manuscript to its supporting evidence.
  Triggers: writing results, "what's the evidence", "trace the claims",
  "map claims to evidence", auditing the argument structure.
---

# Claim-Evidence Mapping

Trace every claim in a manuscript to the specific evidence (data, figure,
equation, citation) that supports it. Identify unsupported claims.

## When to Use

- When writing or revising results and discussion
- When asked "what's the evidence for this" or "trace the claims"
- Before submission to verify every claim has backing
- When restructuring an argument

## How to Run

### Map all claims in a manuscript

```bash
rigorous claim-map path/to/paper.tex
```

### Map claims with code cross-reference

```bash
rigorous claim-map path/to/paper.tex --code path/to/src/
```

### Export as structured data

```bash
rigorous claim-map path/to/paper.tex --output claims.json
```

### Via MCP

Use the `rigorous.claim_map` tool with parameters:
- `file`: path to manuscript
- `code_dir`: optional path to source code
- `output`: optional output file for structured report

## What It Produces

1. **Claim inventory** -- every assertion extracted from the text
2. **Evidence link** -- each claim mapped to figure, table, equation, or citation
3. **Support strength** -- direct evidence, indirect evidence, or unsupported
4. **Chain of reasoning** -- logical dependencies between claims
5. **Gap report** -- claims with no identified evidence

## Example Output

```
CLAIM 1  "The coupled system exhibits a 28-day oscillation"
         Evidence: Figure 2a (direct), Equation 12 (analytical), Table 1 row 5
         Strength: STRONG

CLAIM 2  "Serotonin-cortisol coupling produces emergent mood cycling"
         Evidence: Figure 4 (direct), ablation in Section 4.2
         Strength: STRONG

CLAIM 3  "This framework generalizes to other affective disorders"
         Evidence: None found in manuscript
         Strength: UNSUPPORTED
         -> Action required: add evidence, weaken claim, or remove

CLAIM 4  "Parameters are biologically realistic"
         Evidence: Table 1 citations (indirect -- cites source papers)
         Strength: MODERATE
         -> Suggestion: add direct comparison to clinical measurement ranges
```

## Exit Codes

- `0` -- all claims have supporting evidence
- `1` -- some claims have weak or indirect evidence only
- `2` -- unsupported claims found
