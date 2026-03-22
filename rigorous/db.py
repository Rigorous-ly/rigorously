"""SQLite storage for check results.

Stores findings from all checks in a local SQLite database for
tracking research integrity over time.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(".rigorous.db")


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Get or create a SQLite connection with the schema initialized."""
    db_path = Path(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS check_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            file_path TEXT NOT NULL,
            check_type TEXT NOT NULL,
            total_critical INTEGER DEFAULT 0,
            total_warning INTEGER DEFAULT 0,
            total_info INTEGER DEFAULT 0,
            metadata TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            file_path TEXT,
            line INTEGER,
            severity TEXT NOT NULL,
            issue TEXT NOT NULL,
            details TEXT,
            check_type TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES check_runs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(run_id);
        CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
        CREATE INDEX IF NOT EXISTS idx_runs_file ON check_runs(file_path);
        """
    )
    conn.commit()


def store_run(
    conn: sqlite3.Connection,
    file_path: str,
    check_type: str,
    findings: list[Any],
    metadata: dict | None = None,
) -> int:
    """Store a check run and its findings.

    Args:
        conn: SQLite connection.
        file_path: Path to the checked file.
        check_type: Type of check (overclaim, citations, etc.).
        findings: List of finding objects.
        metadata: Optional metadata dict.

    Returns:
        The run ID.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Count severities
    counts = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        sev = getattr(f, "severity", "info")
        counts[sev] = counts.get(sev, 0) + 1

    cursor = conn.execute(
        """
        INSERT INTO check_runs (timestamp, file_path, check_type,
                                total_critical, total_warning, total_info, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            file_path,
            check_type,
            counts["critical"],
            counts["warning"],
            counts["info"],
            json.dumps(metadata or {}),
        ),
    )
    run_id = cursor.lastrowid

    # Store individual findings
    for f in findings:
        conn.execute(
            """
            INSERT INTO findings (run_id, file_path, line, severity, issue, details, check_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                getattr(f, "file", file_path),
                getattr(f, "line", 0),
                getattr(f, "severity", "info"),
                getattr(f, "issue", "unknown"),
                getattr(f, "details", str(f)),
                check_type,
            ),
        )

    conn.commit()
    return run_id


def get_history(
    conn: sqlite3.Connection,
    file_path: str | None = None,
    check_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Retrieve past check runs.

    Args:
        conn: SQLite connection.
        file_path: Filter by file path.
        check_type: Filter by check type.
        limit: Max results.

    Returns:
        List of run dicts.
    """
    query = "SELECT * FROM check_runs WHERE 1=1"
    params: list = []

    if file_path:
        query += " AND file_path = ?"
        params.append(file_path)
    if check_type:
        query += " AND check_type = ?"
        params.append(check_type)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_findings_for_run(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    """Retrieve all findings for a specific run.

    Args:
        conn: SQLite connection.
        run_id: The check run ID.

    Returns:
        List of finding dicts.
    """
    rows = conn.execute(
        "SELECT * FROM findings WHERE run_id = ? ORDER BY severity, line",
        (run_id,),
    ).fetchall()
    return [dict(row) for row in rows]
