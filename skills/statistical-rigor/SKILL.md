---
name: statistical-rigor
description: >
  Audit statistical claims for methodological soundness.
  Triggers: p-values, statistical tests, "is this statistically sound",
  writing methods sections, reporting confidence intervals, effect sizes.
---

# Statistical Rigor Audit

Audit every statistical claim in a manuscript for methodological soundness,
correct test selection, and proper reporting.

## When to Use

- When reporting p-values, confidence intervals, or effect sizes
- When asked "is this statistically sound"
- When choosing or justifying a statistical test
- Before submission to audit all statistical claims

## How to Run

### Audit a manuscript

```bash
rigorous stat-check path/to/paper.tex
```

### Audit code that computes statistics

```bash
rigorous stat-check path/to/analysis.py --type code
```

### Via MCP

Use the `rigorous.stat_check` tool with parameters:
- `file`: path to manuscript or analysis code
- `type`: `paper` or `code`

## What It Checks

1. **Test appropriateness** -- is the test valid for the data type and design?
2. **Assumption verification** -- are normality, independence, homoscedasticity checked?
3. **Multiple comparisons** -- are corrections applied when testing multiple hypotheses?
4. **Effect size reporting** -- are effect sizes reported alongside p-values?
5. **Confidence intervals** -- are CIs provided, not just point estimates?
6. **Sample size justification** -- is there a power analysis or sample rationale?
7. **P-value hygiene** -- exact values reported (not "p < 0.05"), no p-hacking patterns
8. **Degrees of freedom** -- are df reported for each test?

## Example Output

```
LINE 198  FAIL  "p < 0.05" -- report exact p-value (e.g., p = 0.032)
LINE 204  WARN  t-test used but no normality check reported
LINE 215  FAIL  12 comparisons with no multiple-comparison correction
LINE 220  WARN  No effect size reported for ANOVA result
LINE 231  PASS  Cohen's d = 0.82 reported with 95% CI [0.41, 1.23]
```

## Exit Codes

- `0` -- all statistical claims sound
- `1` -- warnings (missing but non-critical information)
- `2` -- failures (incorrect tests, missing corrections)
