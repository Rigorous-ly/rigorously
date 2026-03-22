---
name: parameter-audit
description: >
  Verify ODE and model parameters match between code, documentation, and
  cited papers. Triggers: modifying model parameters, "check parameters",
  "are these consistent", editing constants, changing coefficients.
---

# Parameter Audit

Verify that every numerical parameter in code matches the value stated in the
manuscript, supplementary materials, and the original cited source.

## When to Use

- After modifying any model parameter in code
- When asked "check parameters" or "are these consistent"
- Before submission to ensure code-paper agreement
- When porting parameters from a published paper into code

## How to Run

### Audit parameters in a source file

```bash
rigorous param-audit path/to/model.py
```

### Cross-reference code against manuscript

```bash
rigorous param-audit path/to/model.py --paper path/to/paper.tex
```

### Check a specific parameter

```bash
rigorous param-audit --name "k_serotonin" --expected 0.035 --source "Best2010 Table 1"
```

### Via MCP

Use the `rigorous.param_audit` tool with parameters:
- `code_file`: path to source code
- `paper_file`: optional path to manuscript
- `name`: optional specific parameter name
- `expected`: optional expected value
- `source`: optional citation for the parameter

## What It Checks

1. **Code-paper consistency** -- parameter in code matches the manuscript table
2. **Unit consistency** -- units stated in comments match the equation context
3. **Source traceability** -- each parameter has a citation (paper, table, equation)
4. **Range plausibility** -- values fall within biologically reasonable ranges
5. **Drift detection** -- parameters changed since last audit are flagged

## Example Output

```
PASS  k_serotonin = 0.035   [model.py:42]  matches [paper.tex Table 1]  (Best2010 Eq.3)
FAIL  tau_cortisol = 15.0    [hpa.py:87]    paper says 12.0  [paper.tex Table 2]
WARN  v_max = 120.0          [dopamine.py:31]  no citation found -- add source
WARN  K_m = 0.5              [dopamine.py:32]  unit mismatch: code says mM, paper says uM
```

## Exit Codes

- `0` -- all parameters consistent
- `1` -- warnings (missing citations, unit questions)
- `2` -- failures (value mismatches between code and paper)
