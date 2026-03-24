"""Pre-commit hook installer for Rigorous.

Installs a git pre-commit hook that runs overclaim and consistency checks
on .tex and .md files being committed.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

HOOK_SCRIPT = '''#!/usr/bin/env bash
# Rigorously pre-commit hook — research integrity checks
# Installed by: rigorously install-hook

set -e

FAILED=0

# Find .tex and .md files being committed
TEX_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\\.(tex|md)$' || true)

if [ -n "$TEX_FILES" ]; then
    echo "Rigorously: checking manuscripts..."
    for FILE in $TEX_FILES; do
        if [ -f "$FILE" ]; then
            # Run overclaim check
            OUTPUT=$(rigorously overclaims "$FILE" 2>&1 || true)
            CRITICAL=$(echo "$OUTPUT" | grep -c "CRITICAL" || true)
            if [ "$CRITICAL" -gt 0 ]; then
                echo ""
                echo "BLOCKED: $FILE has $CRITICAL critical overclaim(s)."
                echo "$OUTPUT"
                FAILED=1
            fi
        fi
    done
fi

# Find Python ODE files being committed
PY_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\\.py$' || true)
ODE_DIRS=""

for FILE in $PY_FILES; do
    if [ -f "$FILE" ]; then
        # Check if this looks like an ODE model file (has "ode" or "dynamics" in path/name)
        if echo "$FILE" | grep -qiE '(ode|dynamics|published|coupling|solver)'; then
            DIR=$(dirname "$FILE")
            # Collect unique directories
            if ! echo "$ODE_DIRS" | grep -q "$DIR"; then
                ODE_DIRS="$ODE_DIRS $DIR"
            fi
        fi
    fi
done

for DIR in $ODE_DIRS; do
    if [ -d "$DIR" ]; then
        echo "Rigorously: checking time units in $DIR..."
        OUTPUT=$(rigorously time-units "$DIR" 2>&1 || true)
        CRITICAL=$(echo "$OUTPUT" | grep -c "CRITICAL" || true)
        if [ "$CRITICAL" -gt 0 ]; then
            echo ""
            echo "BLOCKED: $DIR has $CRITICAL critical time unit issue(s)."
            echo "$OUTPUT"
            FAILED=1
        fi
    fi
done

if [ "$FAILED" -eq 1 ]; then
    echo ""
    echo "Commit blocked by rigorously pre-commit hook."
    echo "Fix critical issues or use --no-verify to bypass (not recommended)."
    exit 1
fi

echo "Rigorously: all checks passed."
exit 0
'''


def install_precommit_hook(repo_path: str | Path = ".") -> Path:
    """Install the pre-commit hook in a git repository.

    Args:
        repo_path: Path to the git repository root.

    Returns:
        Path to the installed hook file.

    Raises:
        FileNotFoundError: If .git directory doesn't exist.
        FileExistsError: If a pre-commit hook already exists (won't overwrite).
    """
    repo_path = Path(repo_path).resolve()
    git_dir = repo_path / ".git"

    if not git_dir.is_dir():
        raise FileNotFoundError(
            f"Not a git repository: {repo_path} (no .git directory found)"
        )

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_path = hooks_dir / "pre-commit"

    if hook_path.exists():
        # Check if it's our hook
        existing = hook_path.read_text(encoding="utf-8", errors="replace")
        if "rigorously" in existing.lower():
            # Update our hook
            hook_path.write_text(HOOK_SCRIPT, encoding="utf-8")
            _make_executable(hook_path)
            return hook_path
        else:
            raise FileExistsError(
                f"A pre-commit hook already exists at {hook_path}. "
                f"Remove it first or manually integrate rigorously checks."
            )

    hook_path.write_text(HOOK_SCRIPT, encoding="utf-8")
    _make_executable(hook_path)
    return hook_path


def _make_executable(path: Path) -> None:
    """Make a file executable."""
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def uninstall_precommit_hook(repo_path: str | Path = ".") -> bool:
    """Remove the rigorously pre-commit hook.

    Args:
        repo_path: Path to the git repository root.

    Returns:
        True if hook was removed, False if not found.
    """
    repo_path = Path(repo_path).resolve()
    hook_path = repo_path / ".git" / "hooks" / "pre-commit"

    if not hook_path.exists():
        return False

    existing = hook_path.read_text(encoding="utf-8", errors="replace")
    if "rigorously" in existing.lower():
        hook_path.unlink()
        return True

    return False
