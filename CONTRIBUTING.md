# Contributing to Rigorously

Thanks for your interest in making research more rigorous.

## Quick Start

```bash
git clone https://github.com/XenResearch/rigorously.git
cd rigorously
pip install -e ".[dev]"
python -m pytest tests/
```

## Adding a New Check

Each check lives in `rigorous/core/` as its own module. To add one:

1. Create `rigorous/core/your_check.py`
2. Implement a function that takes a file path and returns a list of findings
3. Each finding has: `severity` (critical/warning/info), `line`, `issue`, `details`
4. Add it to the check registry in `rigorous/core/__init__.py`
5. Add tests in `tests/test_your_check.py`
6. Add a CLI command in `rigorous/cli.py`

## Code Style

- Python 3.10+
- Type hints on public functions
- Tests for every check pattern

## Reporting Bugs

Open an issue with:
- The command you ran
- The input file (or a minimal reproduction)
- Expected vs actual output

## Pull Requests

- One check per PR
- Include tests
- Update README if adding a new check type
