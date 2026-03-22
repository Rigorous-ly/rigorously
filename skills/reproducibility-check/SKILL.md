---
name: reproducibility-check
description: >
  Verify that numbers reported in the paper match actual code output.
  Triggers: "can we reproduce this", "check the numbers", before submission,
  verifying figures, auditing reported results.
---

# Reproducibility Check

Verify that every numerical result reported in a manuscript can be reproduced
by running the corresponding code.

## When to Use

- When asked "can we reproduce this" or "check the numbers"
- Before submission to verify all reported results
- After modifying code to ensure paper numbers still hold
- When auditing figures, tables, or inline statistics

## How to Run

### Full reproducibility audit

```bash
rigorous repro-check path/to/paper.tex --code path/to/src/
```

### Check a specific figure or table

```bash
rigorous repro-check path/to/paper.tex --target "Table 2"
rigorous repro-check path/to/paper.tex --target "Figure 3a"
```

### Run with tolerance

```bash
rigorous repro-check path/to/paper.tex --code path/to/src/ --tolerance 0.01
```

### Via MCP

Use the `rigorous.repro_check` tool with parameters:
- `paper`: path to manuscript
- `code_dir`: path to source code directory
- `target`: optional specific table or figure
- `tolerance`: numerical tolerance for comparison (default 0.001)

## What It Checks

1. **Inline numbers** -- every number in the text traced to a code output
2. **Table values** -- each cell in each table reproduced from code
3. **Figure data** -- data underlying figures matches code output
4. **Statistical summaries** -- means, SDs, p-values match computed values
5. **Rounding consistency** -- reported precision matches actual precision

## Example Output

```
PASS  Table 1, Row 3: "mean = 4.72" -- code produces 4.7183, rounds to 4.72
FAIL  Section 3.2: "period = 28.1 days" -- code produces 26.8 days (delta = 1.3)
WARN  Figure 2a: cannot locate generating script -- add path annotation
PASS  Abstract: "r = 0.94" -- code produces r = 0.9412, rounds to 0.94
```

## Exit Codes

- `0` -- all numbers reproduced within tolerance
- `1` -- warnings (missing scripts, rounding ambiguity)
- `2` -- failures (numbers do not match code output)
