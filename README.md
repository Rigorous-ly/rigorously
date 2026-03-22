# Rigorously

[![PyPI](https://img.shields.io/pypi/v/rigorously)](https://pypi.org/project/rigorously/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Automated research quality assurance.**

Rigorously catches the mistakes that slip past manual review — fabricated citations, overclaimed results, irreproducible numbers, and statistical misinterpretations. One command. Eight checks.

> **Tested on**: Python CLI, Claude Code, pre-commit hooks · **Compatible with**: 16+ AI coding platforms via the [Agent Skills](https://agentskills.io) standard and [MCP](https://modelcontextprotocol.io)

## The Problem

Citation errors appear in 25% of published papers. "Statistically significant" gets misused in half of biomedical literature. Overclaimed results are the #1 reason reviewers reject computational papers. Manual review catches some of these. Rigorously catches the rest.

```bash
pip install rigorously
rigorously check paper.tex
```

## What It Catches

| Check | What It Does |
|-------|-------------|
| **Citation Verification** | Verifies every bib entry against CrossRef — DOIs, titles, authors, journals |
| **Overclaim Detection** | Flags "proven," "validated," "novel," "impossible" — suggests precise alternatives |
| **Number Consistency** | Cross-checks every number across abstract, body, tables, and captions |
| **Parameter Auditing** | Verifies code parameters match paper claims and docstrings |
| **Statistical Auditing** | Checks p-values, sample sizes, test appropriateness, power analysis |
| **Evidence Mapping** | Traces every claim to supporting code, data, or citation |
| **Reproducibility** | Runs referenced scripts, compares output to paper numbers |
| **Adversarial Review** | Compiles findings into a simulated hostile peer review |

## Sample Output

```
$ rigorously check paper.tex

  Overclaim Detection: 4 findings
  ┌──────────┬────────┬───────────────────────┬─────────────────────────────┐
  │ CRITICAL │ L.56   │ validated             │ Use "consistent with" unless│
  │          │        │                       │ quantitatively compared     │
  │ CRITICAL │ L.216  │ proof_language         │ Models provide evidence,    │
  │          │        │                       │ not proof                   │
  │ WARNING  │ L.502  │ confirms_demonstrates │ Models predict or suggest;  │
  │          │        │                       │ they do not confirm         │
  │ INFO     │ L.89   │ significant_ambiguous  │ Specify p < X or use       │
  │          │        │                       │ "substantial"               │
  └──────────┴────────┴───────────────────────┴─────────────────────────────┘

  Citation Verification: 12 entries checked
    ✓ Best2010 — DOI resolves, metadata matches
    ✓ Karin2020 — DOI resolves, metadata matches
    ✗ LePoul2000 — Author mismatch: bib has "Bhatt" x4, PubMed has "Hanoun"

  VERDICT: 4 critical issues. Fix before submission.
```

## Platform Support

| Platform | Command |
|----------|---------|
| **CLI** | `pip install rigorously` |
| **Claude Code** | `claude plugin install rigorously` |
| **Cursor** | `cursor plugin install rigorously` |
| **Codex CLI** | `codex plugin install rigorously` |
| **Kiro** | Add power → `rigorously` |
| **Windsurf** | Add skill → `rigorously` |
| **Continue.dev** | Add MCP → `rigorously` |
| **Aider** | `aider --read rigorously` |
| **Any MCP client** | `"command": "rigorously", "args": ["serve"]` |
| **Pre-commit** | `rigorously install-hook` |
| **CI/CD** | `rigorously check paper.tex` |

## How It Works

```
paper.tex + refs.bib
       │
       ▼
  ┌─────────┐    ┌──────────┐    ┌──────────┐
  │  Parse   │───▶│ Extract  │───▶│ Verify   │
  │ LaTeX/MD │    │ claims,  │    │ against  │
  │          │    │ numbers, │    │ CrossRef,│
  │          │    │ citations│    │ code,    │
  │          │    │          │    │ PubMed   │
  └─────────┘    └──────────┘    └──────────┘
                                       │
                                       ▼
                                ┌──────────┐
                                │  Report  │
                                │ GO/NO-GO │
                                └──────────┘
```

## MCP Server

For AI agent integration:

```bash
pip install "rigorously[mcp]"
python -m rigorous.mcp_server
```

Tools: `check_paper`, `verify_citation`, `check_overclaims`, `audit_parameters`, `generate_report`

## Pre-commit Hook

```bash
rigorously install-hook
# Blocks commits with critical integrity issues in paper files
```

## vs. Alternatives

| Feature | Rigorously | RefChecker | ACL pubcheck |
|---------|-----------|------------|--------------|
| Citation verification | ✓ | ✓ | ✗ |
| Overclaim detection | ✓ | ✗ | ✗ |
| Number consistency | ✓ | ✗ | ✗ |
| Parameter auditing | ✓ | ✗ | ✗ |
| Statistical auditing | ✓ | ✗ | ✗ |
| Evidence mapping | ✓ | ✗ | ✗ |
| Reproducibility | ✓ | ✗ | ✗ |
| Adversarial review | ✓ | ✗ | ✗ |
| AI agent integration | ✓ (16+ platforms) | ✗ | ✗ |
| Pre-commit hook | ✓ | ✗ | ✗ |
| Format checking | ✗ | ✗ | ✓ |

## Origin

Built to catch real mistakes in real research. During development of a computational neuroscience paper, Rigorously caught 5 fabricated bibliography entries, 4 overclaimed results, and a parameter bug that was disguised as a scientific discovery — all before submission. It now runs on every commit.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Citation

If you use Rigorously in your research workflow:

```bibtex
@software{rigorously,
  author = {Miraj, Mansib},
  title = {Rigorously: Automated Research Quality Assurance},
  url = {https://github.com/XenResearch/rigorously},
  year = {2026}
}
```

## License

MIT
