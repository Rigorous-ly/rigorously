"""SIV — Structured Integrity Verification.

Deterministic. No LLM judgment. Runs the verification command,
captures stdout, checks against declared expectations.

The verifier is the judge. The agent is the defendant. The test is the evidence.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from typing import Any


def run_siv(task: dict, conn: Any = None) -> dict:
    """Run Structured Integrity Verification for a task.

    Args:
        task: dict with verification_run, expected_exit,
              expected_stdout_contains, expected_stdout_excludes,
              timeout_seconds
        conn: optional SQLite connection for golden output checks

    Returns:
        {passed, exit_code, stdout, stderr, reason, hash, contention, duration}
    """
    cmd = task.get("verification_run", "")
    if not cmd:
        return _fail("no verification_run defined")

    expected_exit = task.get("expected_exit", 0)
    timeout = task.get("timeout_seconds", 120)

    try:
        contains = json.loads(task.get("expected_stdout_contains", "[]"))
    except (json.JSONDecodeError, TypeError):
        contains = []
    try:
        excludes = json.loads(task.get("expected_stdout_excludes", "[]"))
    except (json.JSONDecodeError, TypeError):
        excludes = []

    # 1. Run the command
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        return _fail(f"timeout after {timeout}s")
    except Exception as e:
        return _fail(f"execution error: {e}")

    duration = time.time() - t0

    # 2. Check exit code
    if exit_code != expected_exit:
        return _fail(
            f"exit code {exit_code} (expected {expected_exit})",
            stdout=stdout, stderr=stderr, exit_code=exit_code,
            duration=duration,
        )

    # 3. Check stdout contains all expected patterns
    for pattern in contains:
        if pattern not in stdout:
            return _fail(
                f"stdout missing: '{pattern}'",
                stdout=stdout, stderr=stderr, exit_code=exit_code,
                duration=duration,
            )

    # 4. Check stdout excludes all forbidden patterns
    for pattern in excludes:
        if pattern in stdout:
            return _fail(
                f"stdout contains forbidden: '{pattern}'",
                stdout=stdout, stderr=stderr, exit_code=exit_code,
                duration=duration,
            )

    # 5. Check golden outputs for contention
    contention = []
    if conn:
        contention = _check_golden(task.get("id", ""), stdout, conn)

    return {
        "passed": True,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "reason": "all checks passed",
        "contention": contention,
        "duration": round(duration, 2),
    }


def _check_golden(task_id: str, stdout: str, conn) -> list[str]:
    """Check stdout against stored golden outputs. Returns contention list."""
    contentions = []
    try:
        rows = conn.execute(
            "SELECT * FROM expected_outputs WHERE task_id=?",
            (task_id,),
        ).fetchall()
    except Exception:
        return []

    for row in rows:
        pattern = row["expected_pattern"]
        golden = row["golden_value"]

        # Check if pattern matches somewhere in stdout
        match = re.search(pattern, stdout)
        if not match:
            contentions.append(
                f"{row['output_key']}: pattern '{pattern}' not found in stdout"
            )
            continue

        # If golden value exists, check for drift
        if golden and match.group(0) != golden:
            tolerance = row["tolerance"]
            try:
                actual_num = float(re.search(r"[\d.]+", match.group(0)).group())
                golden_num = float(re.search(r"[\d.]+", golden).group())
                if abs(actual_num - golden_num) > tolerance:
                    contentions.append(
                        f"{row['output_key']}: value changed "
                        f"({golden} → {match.group(0)}, tolerance={tolerance})"
                    )
            except (ValueError, AttributeError):
                if match.group(0) != golden:
                    contentions.append(
                        f"{row['output_key']}: output changed "
                        f"({golden} → {match.group(0)})"
                    )

    return contentions


def _fail(reason: str, stdout: str = "", stderr: str = "",
          exit_code: int = -1, duration: float = 0) -> dict:
    return {
        "passed": False,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "reason": reason,
        "contention": [],
        "duration": round(duration, 2),
    }
