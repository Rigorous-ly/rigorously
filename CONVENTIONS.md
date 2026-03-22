# Rigorous -- Research Quality Conventions

These conventions ensure research integrity throughout the writing and
development process. Load this file with `aider --read CONVENTIONS.md`.

## Citation Rules

- Every citation must have a valid DOI or URL that resolves to a real publication.
- Never fabricate references. If you cannot find the exact paper, say so.
- Verify author names, year, title, and journal match the DOI record.
- Check for retractions before citing any paper.
- Run `rigorous cite-check` after adding or modifying any bibliography entry.

## Claim Discipline

- Never use causal language ("causes", "drives", "determines") for correlational
  or simulation results. Use "is consistent with", "suggests", "contributes to".
- Never claim global novelty ("first ever", "unprecedented") without exhaustive
  prior-work verification. Prefer "to our knowledge".
- Every claim in results or discussion must trace to a specific figure, table,
  equation, or citation. Unsupported claims must be removed or qualified.
- Run `rigorous overclaim` before finalizing any results or discussion section.

## Parameter Integrity

- Every numerical parameter in code must have a comment citing its source
  (paper, table number, equation number).
- Parameters in the manuscript must exactly match the values in code.
- Units must be consistent and explicitly stated.
- Run `rigorous param-audit` after changing any model parameter.

## Reproducibility

- Every number in the manuscript (inline, tables, figures) must be producible
  by running the code with no manual intervention.
- Do not round intermediate results. Report final values with appropriate
  significant figures matching the precision of the measurement or computation.
- Run `rigorous repro-check` before submission.

## Statistical Reporting

- Report exact p-values, not thresholds (write "p = 0.032", not "p < 0.05").
- Always report effect sizes alongside significance tests.
- Apply multiple-comparison corrections when testing multiple hypotheses.
- State and verify assumptions for every statistical test.
- Report degrees of freedom and confidence intervals.
- Run `rigorous stat-check` on any section containing statistical claims.

## Pre-Submission Checklist

Before submitting to any venue, run the full integrity check:

```bash
rigorous check paper.tex --code src/ --bib refs.bib
```

Do not submit if there are any BLOCKING issues. Resolve all FAIL items.
WARN items should be addressed or explicitly justified in the manuscript.
