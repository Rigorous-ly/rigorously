"""Plan Registry — SQLite SSOT for verification-gated tasks.

The agent writes claimed_complete. Only the verifier writes verified_complete.
Every state transition is logged in the evidence chain. Append-only.

State machine:
    pending → in_progress → claimed → verified
                                    → regressed
    verified → regressed (automatic, on re-verification failure)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS specs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    root_path TEXT DEFAULT '',
    created_at REAL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    spec_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    difficulty INTEGER DEFAULT 2,
    verification_type TEXT DEFAULT 'command',
    verification_run TEXT DEFAULT '',
    expected_exit INTEGER DEFAULT 0,
    expected_stdout_contains TEXT DEFAULT '[]',
    expected_stdout_excludes TEXT DEFAULT '[]',
    timeout_seconds INTEGER DEFAULT 120,
    depends_on TEXT DEFAULT '[]',
    claimed_complete INTEGER DEFAULT 0,
    claimed_by TEXT DEFAULT '',
    claimed_at REAL DEFAULT 0,
    claim_evidence TEXT DEFAULT '{}',
    verified_complete INTEGER DEFAULT 0,
    verified_at REAL DEFAULT 0,
    verification_output TEXT DEFAULT '',
    verification_hash TEXT DEFAULT '',
    state TEXT DEFAULT 'pending',
    regressed_at REAL DEFAULT 0,
    regression_reason TEXT DEFAULT '',
    created_at REAL,
    updated_at REAL,
    FOREIGN KEY (spec_id) REFERENCES specs(id)
);

CREATE TABLE IF NOT EXISTS evidence_chain (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    transition TEXT NOT NULL,
    evidence TEXT NOT NULL,
    agent_id TEXT DEFAULT '',
    model_id TEXT DEFAULT '',
    timestamp REAL NOT NULL,
    git_sha TEXT DEFAULT '',
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS expected_outputs (
    task_id TEXT NOT NULL,
    output_key TEXT NOT NULL,
    expected_pattern TEXT NOT NULL,
    tolerance REAL DEFAULT 0,
    golden_value TEXT DEFAULT '',
    golden_timestamp REAL DEFAULT 0,
    PRIMARY KEY (task_id, output_key),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS model_performance (
    model_id TEXT NOT NULL,
    task_difficulty INTEGER NOT NULL,
    attempts INTEGER DEFAULT 0,
    successes INTEGER DEFAULT 0,
    failures INTEGER DEFAULT 0,
    avg_time_seconds REAL DEFAULT 0,
    last_updated REAL DEFAULT 0,
    PRIMARY KEY (model_id, task_difficulty)
);

CREATE INDEX IF NOT EXISTS idx_tasks_spec ON tasks(spec_id);
CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_evidence_task ON evidence_chain(task_id);
"""

DEFAULT_DB = Path(".plan.db")


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()[:12]
    except Exception:
        return ""


class TaskRegistry:
    """Verification-gated task registry. SSOT for task state."""

    def __init__(self, db_path: str | Path | None = None):
        self._conn = sqlite3.connect(str(db_path or DEFAULT_DB))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    # ── YAML Loading ──────────────────────────────────────────

    def load_yaml(self, yaml_path: str | Path) -> int:
        """Load task definitions from YAML. Returns count of tasks loaded."""
        import yaml  # pyyaml

        path = Path(yaml_path)
        data = yaml.safe_load(path.read_text())

        if isinstance(data, dict):
            spec = data.get("spec", {})
            tasks = data.get("tasks", [])
        elif isinstance(data, list):
            spec = {"id": path.stem, "title": path.stem}
            tasks = data
        else:
            raise ValueError(f"Invalid YAML structure in {path}")

        # Upsert spec
        spec_id = spec.get("id", path.stem)
        self._conn.execute(
            "INSERT OR REPLACE INTO specs (id, title, root_path, created_at) "
            "VALUES (?, ?, ?, ?)",
            (spec_id, spec.get("title", spec_id),
             spec.get("root_path", ""), time.time()),
        )

        now = time.time()
        count = 0
        for t in tasks:
            v = t.get("verification", {})
            self._conn.execute(
                "INSERT OR REPLACE INTO tasks "
                "(id, spec_id, title, description, difficulty, "
                " verification_type, verification_run, expected_exit, "
                " expected_stdout_contains, expected_stdout_excludes, "
                " timeout_seconds, depends_on, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    t["id"], spec_id, t["title"],
                    t.get("description", ""),
                    t.get("difficulty", 2),
                    v.get("type", "command"),
                    v.get("run", ""),
                    v.get("expected_exit", 0),
                    json.dumps(v.get("expected_stdout_contains", [])),
                    json.dumps(v.get("expected_stdout_excludes", [])),
                    v.get("timeout_seconds", 120),
                    json.dumps(t.get("depends_on", [])),
                    now, now,
                ),
            )
            count += 1

        self._conn.commit()
        return count

    # ── Agent-writable transitions ────────────────────────────

    def claim_start(self, task_id: str, agent_id: str = "",
                    model_id: str = "") -> bool:
        """pending → in_progress. Agent starts working."""
        row = self._get_task(task_id)
        if not row or row["state"] not in ("pending", "regressed"):
            return False

        now = time.time()
        self._conn.execute(
            "UPDATE tasks SET state='in_progress', claimed_by=?, "
            "claimed_at=?, updated_at=? WHERE id=?",
            (agent_id, now, now, task_id),
        )
        self._log_evidence(task_id, f"{row['state']}->in_progress",
                           {"agent_id": agent_id, "model_id": model_id})
        self._conn.commit()
        return True

    def claim_complete(self, task_id: str, evidence: dict | None = None,
                       model_id: str = "") -> bool:
        """in_progress → claimed. Agent says it's done."""
        row = self._get_task(task_id)
        if not row or row["state"] != "in_progress":
            return False

        now = time.time()
        ev = json.dumps(evidence or {})
        self._conn.execute(
            "UPDATE tasks SET state='claimed', claimed_complete=1, "
            "claim_evidence=?, updated_at=? WHERE id=?",
            (ev, now, task_id),
        )
        self._log_evidence(task_id, "in_progress->claimed",
                           {"evidence": evidence, "model_id": model_id})
        if model_id:
            self._record_attempt(model_id, row["difficulty"])
        self._conn.commit()
        return True

    # ── Verifier-only transitions ─────────────────────────────

    def verify(self, task_id: str) -> dict:
        """Run SIV. claimed → verified or claimed → regressed.

        ONLY the verification harness calls this. Never the agent.
        Returns {passed, exit_code, stdout, hash, contention}.
        """
        from .verifier import run_siv

        row = self._get_task(task_id)
        if not row:
            return {"passed": False, "error": "task not found"}

        result = run_siv(dict(row), self._conn)
        now = time.time()
        h = hashlib.sha256(result["stdout"].encode()).hexdigest()[:16]

        if result["passed"]:
            self._conn.execute(
                "UPDATE tasks SET state='verified', verified_complete=1, "
                "verified_at=?, verification_output=?, verification_hash=?, "
                "updated_at=? WHERE id=?",
                (now, result["stdout"][:10000], h, now, task_id),
            )
            self._log_evidence(task_id, f"{row['state']}->verified",
                               {"siv": result, "hash": h})
            # Update model performance
            if row["claimed_by"]:
                self._record_success(row["claimed_by"], row["difficulty"])
        else:
            reason = result.get("reason", "SIV failed")
            self._conn.execute(
                "UPDATE tasks SET state='regressed', regressed_at=?, "
                "regression_reason=?, verified_complete=0, "
                "verification_output=?, updated_at=? WHERE id=?",
                (now, reason, result["stdout"][:10000], now, task_id),
            )
            self._log_evidence(task_id, f"{row['state']}->regressed",
                               {"siv": result, "reason": reason})
            if row["claimed_by"]:
                self._record_failure(row["claimed_by"], row["difficulty"])

        self._conn.commit()
        return result

    def regress_check(self, spec_id: str = "") -> list[dict]:
        """Re-verify all verified tasks. Auto-regress failures."""
        query = "SELECT id FROM tasks WHERE state='verified'"
        params = []
        if spec_id:
            query += " AND spec_id=?"
            params.append(spec_id)

        rows = self._conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            result = self.verify(row["id"])
            if not result.get("passed"):
                results.append({"task_id": row["id"], **result})
        return results

    # ── Queries ───────────────────────────────────────────────

    def list_tasks(self, spec_id: str = "", state: str = "") -> list[dict]:
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list = []
        if spec_id:
            query += " AND spec_id=?"
            params.append(spec_id)
        if state:
            query += " AND state=?"
            params.append(state)
        query += " ORDER BY spec_id, id"
        return [dict(r) for r in self._conn.execute(query, params).fetchall()]

    def task_status(self, task_id: str) -> dict | None:
        row = self._get_task(task_id)
        if not row:
            return None
        result = dict(row)
        result["evidence_chain"] = self._get_evidence(task_id)
        return result

    def model_stats(self, model_id: str = "") -> list[dict]:
        query = "SELECT * FROM model_performance"
        params: list = []
        if model_id:
            query += " WHERE model_id=?"
            params.append(model_id)
        return [dict(r) for r in self._conn.execute(query, params).fetchall()]

    # ── Internal helpers ──────────────────────────────────────

    def _get_task(self, task_id: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)
        ).fetchone()

    def _get_evidence(self, task_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM evidence_chain WHERE task_id=? ORDER BY timestamp",
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _log_evidence(self, task_id: str, transition: str,
                      evidence: dict) -> None:
        self._conn.execute(
            "INSERT INTO evidence_chain "
            "(task_id, transition, evidence, agent_id, model_id, "
            " timestamp, git_sha) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task_id, transition, json.dumps(evidence, default=str),
             evidence.get("agent_id", ""),
             evidence.get("model_id", ""),
             time.time(), _git_sha()),
        )

    def _record_attempt(self, model_id: str, difficulty: int) -> None:
        self._conn.execute(
            "INSERT INTO model_performance (model_id, task_difficulty, "
            "attempts, last_updated) VALUES (?, ?, 1, ?) "
            "ON CONFLICT(model_id, task_difficulty) DO UPDATE "
            "SET attempts=attempts+1, last_updated=?",
            (model_id, difficulty, time.time(), time.time()),
        )

    def _record_success(self, model_id: str, difficulty: int) -> None:
        self._conn.execute(
            "INSERT INTO model_performance (model_id, task_difficulty, "
            "successes, last_updated) VALUES (?, ?, 1, ?) "
            "ON CONFLICT(model_id, task_difficulty) DO UPDATE "
            "SET successes=successes+1, last_updated=?",
            (model_id, difficulty, time.time(), time.time()),
        )

    def _record_failure(self, model_id: str, difficulty: int) -> None:
        self._conn.execute(
            "INSERT INTO model_performance (model_id, task_difficulty, "
            "failures, last_updated) VALUES (?, ?, 1, ?) "
            "ON CONFLICT(model_id, task_difficulty) DO UPDATE "
            "SET failures=failures+1, last_updated=?",
            (model_id, difficulty, time.time(), time.time()),
        )
