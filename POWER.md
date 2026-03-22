---
name: rigorous
displayName: Rigorous
description: >
  Research quality assurance toolkit. Verifies citations, detects overclaims,
  audits parameters, checks reproducibility, enforces statistical rigor,
  maps claims to evidence, and simulates adversarial peer review.
keywords:
  - research
  - quality-assurance
  - citations
  - reproducibility
  - statistics
  - peer-review
  - parameters
  - integrity
---

# Rigorous

Rigorous catches the mistakes that slip past manual review.

## Available Tools (via MCP)

Start the MCP server to access all tools programmatically:

```bash
python -m rigorous.mcp_server
```

### Tools

| Tool | Description |
|------|-------------|
| `rigorous.cite_check` | Verify bibliography entries against real databases |
| `rigorous.overclaim` | Scan for overclaimed language |
| `rigorous.param_audit` | Verify parameters match between code and paper |
| `rigorous.repro_check` | Verify reported numbers match code output |
| `rigorous.stat_check` | Audit statistical claims |
| `rigorous.review` | Simulate adversarial peer review |
| `rigorous.claim_map` | Map every claim to its evidence |
| `rigorous.check` | Run all checks at once |

## CLI Usage

```bash
# Full integrity check before submission
rigorous check paper.tex --code src/ --bib refs.bib

# Individual checks
rigorous cite-check refs.bib
rigorous overclaim paper.tex
rigorous param-audit model.py --paper paper.tex
rigorous repro-check paper.tex --code src/
rigorous stat-check paper.tex
rigorous review paper.tex
rigorous claim-map paper.tex --code src/
```

## Skills

See `skills/*/SKILL.md` for detailed usage of each capability. Skills follow
the agentskills.io specification and are automatically loaded by compatible
agents.
