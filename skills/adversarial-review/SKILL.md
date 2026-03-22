---
name: adversarial-review
description: >
  Simulate hostile peer review to find weaknesses before submission.
  Triggers: "review this", "is this ready", before submission,
  "would a reviewer catch this", "what are the weaknesses".
---

# Adversarial Review

Simulate a rigorous, skeptical peer review to identify weaknesses, gaps,
and vulnerabilities in a manuscript before submission.

## When to Use

- When asked "review this" or "is this ready for submission"
- When asked "would a reviewer catch this"
- Before submission to any venue
- When asked "what are the weaknesses"

## How to Run

### Full adversarial review

```bash
rigorous review path/to/paper.tex
```

### Review specific aspects

```bash
rigorous review path/to/paper.tex --focus methodology
rigorous review path/to/paper.tex --focus novelty
rigorous review path/to/paper.tex --focus reproducibility
```

### Set reviewer persona

```bash
rigorous review path/to/paper.tex --persona "computational neuroscience"
rigorous review path/to/paper.tex --persona "statistics"
```

### Via MCP

Use the `rigorous.review` tool with parameters:
- `file`: path to manuscript
- `focus`: optional aspect to focus on
- `persona`: optional reviewer domain expertise

## What It Evaluates

1. **Novelty** -- is the contribution genuinely new? What prior work is closest?
2. **Methodology** -- are the methods sound and appropriate for the claims?
3. **Reproducibility** -- could someone replicate this from the paper alone?
4. **Logical gaps** -- are there unstated assumptions or missing steps?
5. **Missing controls** -- what ablations, baselines, or comparisons are absent?
6. **Scope vs. claims** -- do the conclusions stay within what the evidence supports?
7. **Presentation** -- is the writing clear, precise, and well-structured?
8. **Fatal flaws** -- issues that would guarantee rejection

## Example Output

```
FATAL   No ablation study separating coupling contribution from subsystem behavior.
        A reviewer will ask: "How do you know this isn't just the HPA model alone?"

MAJOR   Section 3: Claims emergent behavior but does not define emergence formally.
        Suggest: Add definition and cite Thompson & Varela 2001.

MAJOR   Figure 4: No error bars or confidence bands on simulation trajectories.
        Suggest: Run ensemble with parameter perturbation, show spread.

MINOR   Abstract line 3: "novel framework" -- reviewers are skeptical of self-assessed
        novelty. Suggest: let the contribution speak for itself.

MINOR   References: 8 of 32 citations are self-citations (25%). May raise concerns.
```

## Exit Codes

- `0` -- no fatal or major issues found
- `1` -- major issues found
- `2` -- fatal issues found
