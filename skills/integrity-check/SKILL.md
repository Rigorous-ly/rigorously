---
name: integrity-check
description: >
  Run ALL research quality checks at once as a comprehensive audit.
  Triggers: "full audit", "integrity check", /integrity-check,
  before any submission, "run everything", "final check".
---

# Full Integrity Check

Run every Rigorous check in sequence as a comprehensive pre-submission audit.
This is the single command to run before submitting to any venue.

## When to Use

- When asked for a "full audit" or "integrity check"
- Before submission to any journal or conference
- When running `/integrity-check`
- As a final gate before declaring a manuscript ready

## How to Run

### Full audit

```bash
rigorous check path/to/paper.tex --code path/to/src/
```

### Full audit with bibliography

```bash
rigorous check path/to/paper.tex --code path/to/src/ --bib path/to/refs.bib
```

### Quick mode (skip slow network checks)

```bash
rigorous check path/to/paper.tex --quick
```

### Via MCP

Use the `rigorous.check` tool with parameters:
- `paper`: path to manuscript
- `code_dir`: path to source code directory
- `bib`: optional path to bibliography file
- `quick`: boolean, skip network-dependent checks

## What It Runs

This command executes all checks in order:

1. **Citation verification** -- all references resolve and metadata matches
2. **Overclaim detection** -- no unsupported strong language
3. **Parameter audit** -- code parameters match paper and cited sources
4. **Reproducibility check** -- reported numbers match code output
5. **Statistical rigor** -- all statistical claims are methodologically sound
6. **Claim-evidence mapping** -- every claim traced to evidence
7. **Adversarial review** -- simulated hostile peer review

## Example Output

```
=== RIGOROUS INTEGRITY CHECK ===

[1/7] Citation Verification ......... 31/32 PASS, 1 WARN
[2/7] Overclaim Detection ........... 3 issues (2 MEDIUM, 1 WEAK)
[3/7] Parameter Audit ............... 47/48 PASS, 1 FAIL
[4/7] Reproducibility Check ......... 12/12 PASS
[5/7] Statistical Rigor ............. 5/6 PASS, 1 WARN
[6/7] Claim-Evidence Map ............ 14/15 mapped, 1 UNSUPPORTED
[7/7] Adversarial Review ............ 0 FATAL, 2 MAJOR, 3 MINOR

=== SUMMARY ===
BLOCKING:  1 parameter mismatch, 1 unsupported claim
ADVISORY:  2 overclaims, 1 citation warning, 1 stat warning
COSMETIC:  3 minor review notes

Verdict: NOT READY -- resolve 2 blocking issues before submission
```

## Exit Codes

- `0` -- all checks pass, ready for submission
- `1` -- advisory issues only (submit at your discretion)
- `2` -- blocking issues found (do not submit)
