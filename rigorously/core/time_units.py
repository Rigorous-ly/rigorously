"""Time unit consistency checking for coupled ODE systems.

Scans Python ODE model files for time unit declarations (docstrings,
comments, rate constant annotations) and verifies that coupling/solver
code properly converts between models with different time bases.

This check would have caught the serotonin (hours) vs HPA (minutes)
coupling bug that required t/60 conversion in the unified solver.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class TimeUnitFinding:
    """A time unit consistency issue."""

    file: str
    line: int
    severity: Literal["critical", "warning", "info"]
    issue: str
    details: str

    def __str__(self) -> str:
        sev_tag = self.severity.upper()
        fname = Path(self.file).name
        return f"[{sev_tag}] {fname}:{self.line} ({self.issue}) {self.details}"


# Docstring / comment patterns for explicit time unit declarations
_TIME_UNIT_DOCSTRING_PATTERNS = [
    # "time in hours", "time in minutes", "Units: time in MINUTES"
    (re.compile(
        r"(?:time\s+(?:in|is|=)\s+|time\s*:\s*|time\s+unit\s*:\s*)"
        r"(hours?|hrs?|minutes?|mins?|days?|seconds?|secs?|weeks?)",
        re.IGNORECASE,
    ), "docstring_declaration"),
    # "Units: ... time in HOURS"
    (re.compile(
        r"units?\s*:.*?time\s+(?:in\s+)?(hours?|hrs?|minutes?|mins?|days?|seconds?|secs?|weeks?)",
        re.IGNORECASE,
    ), "units_declaration"),
]

# Rate constant unit annotations in comments: # 1/hr, # /min, # per hour
_RATE_UNIT_PATTERNS = [
    (re.compile(
        r"#\s*.*?"
        r"(?:1/|per\s+|/)"
        r"(hours?|hrs?|hr|minutes?|mins?|min|days?|seconds?|secs?|sec|weeks?|wk)",
        re.IGNORECASE,
    ), "rate_comment"),
    # "uM/hr", "μM/min", "mg/day" in comments
    (re.compile(
        r"#\s*.*?\w+/"
        r"(hours?|hrs?|hr|minutes?|mins?|min|days?|seconds?|secs?|sec|weeks?|wk)",
        re.IGNORECASE,
    ), "concentration_rate_comment"),
]

# Time conversion patterns in coupling/solver code
_CONVERSION_FACTORS = ["60", "24", "1440", "3600"]
_CONVERSION_PATTERNS = [
    re.compile(rf"t\s*[*/]\s*{f}(?:\.0)?") for f in _CONVERSION_FACTORS
] + [
    re.compile(rf"[*/]\s*{f}(?:\.0)?\s*$") for f in ["60"]
]

# Map raw matched strings to canonical unit names
_UNIT_CANONICAL: dict[str, str] = {
    a: c for aliases, c in [
        (["hour", "hours", "hr", "hrs"], "hours"),
        (["minute", "minutes", "min", "mins"], "minutes"),
        (["day", "days"], "days"),
        (["second", "seconds", "sec", "secs"], "seconds"),
        (["week", "weeks", "wk"], "weeks"),
    ] for a in aliases
}


def _canonicalize(unit: str) -> str:
    return _UNIT_CANONICAL.get(unit.lower().strip(), unit.lower().strip())


@dataclass
class ModelTimeInfo:
    """Detected time unit information for a single file."""

    file: str
    declared_unit: str | None  # From docstring/header
    declared_line: int
    rate_units: list[tuple[int, str, str]]  # (line, unit, raw_text)
    has_conversion: bool  # Whether file contains t/60 etc.
    conversion_lines: list[int]


def _detect_file_time_units(filepath: Path) -> ModelTimeInfo:
    """Scan a single Python file for time unit information."""
    source = filepath.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    declared_unit: str | None = None
    declared_line: int = 0
    rate_units: list[tuple[int, str, str]] = []
    conversion_lines: list[int] = []

    for i, line in enumerate(lines, start=1):
        for pattern, _kind in _TIME_UNIT_DOCSTRING_PATTERNS:
            m = pattern.search(line)
            if m and declared_unit is None:
                declared_unit = _canonicalize(m.group(1))
                declared_line = i
        for pattern, _kind in _RATE_UNIT_PATTERNS:
            m = pattern.search(line)
            if m:
                rate_units.append((i, _canonicalize(m.group(1)), line.strip()))
        for pattern in _CONVERSION_PATTERNS:
            if pattern.search(line):
                conversion_lines.append(i)

    return ModelTimeInfo(
        file=str(filepath), declared_unit=declared_unit,
        declared_line=declared_line, rate_units=rate_units,
        has_conversion=len(conversion_lines) > 0,
        conversion_lines=conversion_lines,
    )


_CONVERSION_DOC_RE = re.compile(
    r"converted\s+to|→|=>|->|convert(?:ed|s|ing)",
    re.IGNORECASE,
)


def _check_internal_consistency(info: ModelTimeInfo) -> list[TimeUnitFinding]:
    """Check that rate constant units in a file agree with its declared time unit."""
    findings: list[TimeUnitFinding] = []

    if not info.declared_unit or not info.rate_units:
        return findings

    for line, unit, raw in info.rate_units:
        if unit != info.declared_unit:
            # Check if the comment documents a unit conversion
            # e.g. "1/day -> converted to 1/min" is intentional
            if _CONVERSION_DOC_RE.search(raw):
                findings.append(TimeUnitFinding(
                    file=info.file,
                    line=line,
                    severity="info",
                    issue="documented_unit_conversion",
                    details=(
                        f"Rate constant documents conversion from "
                        f"'{unit}' to '{info.declared_unit}': {raw[:120]}"
                    ),
                ))
            else:
                findings.append(TimeUnitFinding(
                    file=info.file,
                    line=line,
                    severity="critical",
                    issue="internal_unit_mismatch",
                    details=(
                        f"File declares time in '{info.declared_unit}' "
                        f"(line {info.declared_line}) but rate constant on "
                        f"this line uses '{unit}': {raw[:120]}"
                    ),
                ))

    return findings


def _check_coupling_conversions(
    model_infos: list[ModelTimeInfo],
    solver_infos: list[ModelTimeInfo],
) -> list[TimeUnitFinding]:
    """Verify solver files have conversion code when models differ in time units."""
    findings: list[TimeUnitFinding] = []

    unit_to_files: dict[str, list[str]] = {}
    for info in model_infos:
        if info.declared_unit:
            unit_to_files.setdefault(info.declared_unit, []).append(
                Path(info.file).name
            )
    if len(unit_to_files) <= 1:
        return findings

    units_summary = ", ".join(
        f"{u} ({', '.join(fs)})" for u, fs in sorted(unit_to_files.items())
    )

    for solver in solver_infos:
        if not solver.has_conversion:
            findings.append(TimeUnitFinding(
                file=solver.file,
                line=0,
                severity="critical",
                issue="missing_time_conversion",
                details=(
                    f"Solver/coupling file couples models with different time units "
                    f"[{units_summary}] but contains NO time conversion code "
                    f"(expected t/60, t*60, etc.)."
                ),
            ))
        else:
            findings.append(TimeUnitFinding(
                file=solver.file,
                line=solver.conversion_lines[0] if solver.conversion_lines else 0,
                severity="info",
                issue="time_conversion_present",
                details=(
                    f"Solver/coupling file contains time conversion(s) at "
                    f"line(s) {solver.conversion_lines}. "
                    f"Models use: {units_summary}."
                ),
            ))

    return findings


def _scan_coupling_for_direct_calls(
    solver_info: ModelTimeInfo,
    model_infos: list[ModelTimeInfo],
) -> list[TimeUnitFinding]:
    """Flag ODE function calls that pass raw 't' without unit conversion."""
    findings: list[TimeUnitFinding] = []

    source = Path(solver_info.file).read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()

    func_unit_hints: dict[str, str] = {}
    for info in model_infos:
        if info.declared_unit:
            stem = Path(info.file).stem
            func_unit_hints[stem] = info.declared_unit
            parts = stem.split("_")
            if parts:
                func_unit_hints[parts[0]] = info.declared_unit

    ode_call_re = re.compile(r"(\w+_ode)\s*\(([^)]*)\)")
    for i, line in enumerate(lines, start=1):
        for m in ode_call_re.finditer(line):
            func_name, call_args = m.group(1), m.group(2)
            matched_unit = None
            for hint, unit in func_unit_hints.items():
                if hint in func_name:
                    matched_unit = unit
                    break
            if matched_unit is None:
                continue
            t_arg = call_args.split(",")[0].strip() if "," in call_args else call_args.strip()
            if t_arg != "t" or re.search(r"t\s*[*/]\s*\d+", t_arg):
                continue
            nearby = lines[max(0, i - 3):i + 2]
            if not any(p.search(nl) for nl in nearby for p in _CONVERSION_PATTERNS):
                findings.append(TimeUnitFinding(
                    file=solver_info.file, line=i, severity="warning",
                    issue="direct_t_pass",
                    details=(
                        f"Function '{func_name}' (model uses {matched_unit}) "
                        f"is called with raw 't' and no visible conversion. "
                        f"Verify the caller handles unit conversion."
                    ),
                ))

    return findings


def audit_time_units(
    code_directory: str | Path,
    solver_directories: list[str | Path] | None = None,
) -> list[TimeUnitFinding]:
    """Audit time unit consistency across ODE model files.

    Args:
        code_directory: Directory containing ODE model Python files.
        solver_directories: Additional solver/coupling directories. If None,
            auto-discovers unified_solver.py and coupling/ in parent dir.
    """
    code_dir = Path(code_directory)
    if not code_dir.exists():
        raise FileNotFoundError(f"Directory not found: {code_dir}")

    findings: list[TimeUnitFinding] = []

    # 1. Scan all Python files in the model directory
    model_infos: list[ModelTimeInfo] = []
    for py_file in sorted(code_dir.rglob("*.py")):
        if py_file.name.startswith("__"):
            continue
        info = _detect_file_time_units(py_file)
        model_infos.append(info)

        # Report each file's detected time unit
        if info.declared_unit:
            findings.append(TimeUnitFinding(
                file=str(py_file),
                line=info.declared_line,
                severity="info",
                issue="time_unit_detected",
                details=(
                    f"Model declares time unit: '{info.declared_unit}'. "
                    f"Found {len(info.rate_units)} rate constant annotations."
                ),
            ))

            # Check internal consistency
            findings.extend(_check_internal_consistency(info))
        elif info.rate_units:
            # Has rate annotations but no explicit declaration
            units_found = set(u for _, u, _ in info.rate_units)
            findings.append(TimeUnitFinding(
                file=str(py_file),
                line=info.rate_units[0][0],
                severity="warning",
                issue="no_time_unit_declaration",
                details=(
                    f"File has rate constant annotations suggesting unit(s) "
                    f"{sorted(units_found)} but no explicit time unit declaration "
                    f"in docstring. Add 'Units: time in X' to the module docstring."
                ),
            ))

    # 2. Collect solver/coupling files
    solver_infos: list[ModelTimeInfo] = []
    solver_dirs: list[Path] = []

    if solver_directories:
        for sd in solver_directories:
            solver_dirs.append(Path(sd))
    else:
        # Auto-discover: check parent directory for common patterns
        parent = code_dir.parent
        for candidate in [
            parent / "unified_solver.py",
            parent / "solver.py",
            parent / "coupling",
        ]:
            if candidate.exists():
                solver_dirs.append(candidate)

    for sd in solver_dirs:
        if sd.is_file():
            solver_infos.append(_detect_file_time_units(sd))
        elif sd.is_dir():
            for py_file in sorted(sd.rglob("*.py")):
                if py_file.name.startswith("__"):
                    continue
                solver_infos.append(_detect_file_time_units(py_file))

    # 3. Cross-file consistency: check conversions
    if solver_infos:
        findings.extend(_check_coupling_conversions(model_infos, solver_infos))

        # 4. Check for direct ODE calls without conversion
        for solver in solver_infos:
            findings.extend(_scan_coupling_for_direct_calls(solver, model_infos))

    # 5. Summary: report distinct time units found
    all_units = set()
    for info in model_infos:
        if info.declared_unit:
            all_units.add(info.declared_unit)

    if len(all_units) > 1:
        findings.append(TimeUnitFinding(
            file=str(code_dir),
            line=0,
            severity="warning",
            issue="multiple_time_units",
            details=(
                f"Models in this directory use {len(all_units)} different time units: "
                f"{sorted(all_units)}. Coupling code MUST convert between them."
            ),
        ))
    elif len(all_units) == 1:
        findings.append(TimeUnitFinding(
            file=str(code_dir),
            line=0,
            severity="info",
            issue="uniform_time_units",
            details=f"All models use the same time unit: '{next(iter(all_units))}'.",
        ))

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (severity_order.get(f.severity, 9), f.line))

    return findings
