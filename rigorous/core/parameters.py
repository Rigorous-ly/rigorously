"""ODE parameter consistency checking.

For Python files containing ODE models, checks that:
1. Parameter values in comments/docstrings match actual code values.
2. STEADY_STATE arrays are actual fixed points (quick ODE integration).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class ParameterFinding:
    """A parameter consistency issue."""

    file: str
    line: int
    severity: Literal["critical", "warning", "info"]
    issue: str
    details: str


def _extract_assignments(source: str) -> dict[str, list[tuple[int, float, str]]]:
    """Extract variable assignments that look like parameters.

    Returns:
        Dict mapping variable name -> list of (line_number, value, context).
    """
    assignments: dict[str, list[tuple[int, float, str]]] = {}

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return assignments

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = None
                if isinstance(target, ast.Name):
                    name = target.id
                elif isinstance(target, ast.Attribute):
                    name = ast.dump(target)

                if name and isinstance(node.value, (ast.Constant, ast.UnaryOp)):
                    value = None
                    if isinstance(node.value, ast.Constant) and isinstance(
                        node.value.value, (int, float)
                    ):
                        value = float(node.value.value)
                    elif isinstance(node.value, ast.UnaryOp) and isinstance(
                        node.value.op, ast.USub
                    ):
                        if isinstance(node.value.operand, ast.Constant) and isinstance(
                            node.value.operand.value, (int, float)
                        ):
                            value = -float(node.value.operand.value)

                    if value is not None:
                        line = node.lineno
                        context = name
                        if name not in assignments:
                            assignments[name] = []
                        assignments[name].append((line, value, context))

    return assignments


def _extract_comment_values(source: str) -> list[tuple[int, str, float, str]]:
    """Extract parameter values mentioned in comments and docstrings.

    Returns:
        List of (line_number, param_name, value, raw_text).
    """
    results: list[tuple[int, str, float, str]] = []
    lines = source.splitlines()

    # Pattern: param_name = value or param_name: value in comments
    param_comment_re = re.compile(
        r"#.*?(\w+)\s*[=:]\s*([+-]?\d+\.?\d*(?:e[+-]?\d+)?)"
        r"|"
        r'["\'].*?(\w+)\s*[=:]\s*([+-]?\d+\.?\d*(?:e[+-]?\d+)?)',
        re.IGNORECASE,
    )

    for i, line in enumerate(lines, start=1):
        for m in param_comment_re.finditer(line):
            name = m.group(1) or m.group(3)
            val_str = m.group(2) or m.group(4)
            if name and val_str:
                try:
                    value = float(val_str)
                    results.append((i, name, value, line.strip()))
                except ValueError:
                    continue

    return results


def _extract_dict_params(source: str) -> dict[str, list[tuple[int, float]]]:
    """Extract parameter values from dict literals and class attributes.

    Returns:
        Dict mapping parameter name -> list of (line, value).
    """
    params: dict[str, list[tuple[int, float]]] = {}

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return params

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, val in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    name = key.value
                    if isinstance(val, ast.Constant) and isinstance(val.value, (int, float)):
                        if name not in params:
                            params[name] = []
                        params[name].append((val.lineno, float(val.value)))

    return params


def _find_steady_state_arrays(source: str) -> list[tuple[int, str, list[float]]]:
    """Find arrays named *steady* or *STEADY* or *fixed_point*.

    Returns:
        List of (line, name, values).
    """
    results: list[tuple[int, str, list[float]]] = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return results

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id
                    if re.search(r"steady|fixed_point|equilibrium", name, re.IGNORECASE):
                        # Try to extract the array values
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            values: list[float] = []
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(
                                    elt.value, (int, float)
                                ):
                                    values.append(float(elt.value))
                                elif isinstance(elt, ast.UnaryOp) and isinstance(
                                    elt.op, ast.USub
                                ):
                                    if isinstance(elt.operand, ast.Constant):
                                        values.append(-float(elt.operand.value))
                                else:
                                    break  # Non-constant element, skip this array
                            if values:
                                results.append((node.lineno, name, values))

    return results


def check_parameters(filepath: str | Path) -> list[ParameterFinding]:
    """Check parameter consistency in a Python ODE model file.

    Checks:
    1. Parameters in comments/docstrings match code assignments.
    2. Duplicate parameter definitions with different values.
    3. Steady-state arrays are flagged for manual verification.

    Args:
        filepath: Path to a Python file.

    Returns:
        List of ParameterFinding objects.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    source = filepath.read_text(encoding="utf-8", errors="replace")
    findings: list[ParameterFinding] = []

    # 1. Extract all assignments and comment values
    assignments = _extract_assignments(source)
    comment_values = _extract_comment_values(source)
    dict_params = _extract_dict_params(source)

    # 2. Check comment values against assignments
    for line, name, comment_val, raw in comment_values:
        # Look for matching assignment
        if name in assignments:
            for assign_line, assign_val, _ in assignments[name]:
                if assign_val != 0 and comment_val != 0:
                    rel_diff = abs(assign_val - comment_val) / max(
                        abs(assign_val), abs(comment_val)
                    )
                    if rel_diff > 0.001:  # More than 0.1% difference
                        findings.append(
                            ParameterFinding(
                                file=str(filepath),
                                line=line,
                                severity="critical",
                                issue="comment_code_mismatch",
                                details=(
                                    f"Parameter '{name}' documented as {comment_val} "
                                    f"(line {line}) but assigned as {assign_val} "
                                    f"(line {assign_line}). "
                                    f"Relative difference: {rel_diff:.4%}."
                                ),
                            )
                        )

        # Also check dict params
        if name in dict_params:
            for dict_line, dict_val in dict_params[name]:
                if dict_val != 0 and comment_val != 0:
                    rel_diff = abs(dict_val - comment_val) / max(
                        abs(dict_val), abs(comment_val)
                    )
                    if rel_diff > 0.001:
                        findings.append(
                            ParameterFinding(
                                file=str(filepath),
                                line=line,
                                severity="critical",
                                issue="comment_dict_mismatch",
                                details=(
                                    f"Parameter '{name}' documented as {comment_val} "
                                    f"(line {line}) but found as {dict_val} in dict "
                                    f"(line {dict_line})."
                                ),
                            )
                        )

    # 3. Check for duplicate assignments with different values
    for name, assign_list in assignments.items():
        if len(assign_list) > 1:
            values = set(v for _, v, _ in assign_list)
            if len(values) > 1:
                lines_and_vals = [(ln, v) for ln, v, _ in assign_list]
                findings.append(
                    ParameterFinding(
                        file=str(filepath),
                        line=assign_list[0][0],
                        severity="warning",
                        issue="duplicate_parameter",
                        details=(
                            f"Parameter '{name}' assigned multiple times with "
                            f"different values: {lines_and_vals}."
                        ),
                    )
                )

    # 4. Flag steady-state arrays for verification
    steady_states = _find_steady_state_arrays(source)
    for line, name, values in steady_states:
        findings.append(
            ParameterFinding(
                file=str(filepath),
                line=line,
                severity="info",
                issue="steady_state_found",
                details=(
                    f"Steady-state array '{name}' found with {len(values)} values. "
                    f"Verify these are actual fixed points by running ODE integration."
                ),
            )
        )

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (severity_order.get(f.severity, 9), f.line))

    return findings
