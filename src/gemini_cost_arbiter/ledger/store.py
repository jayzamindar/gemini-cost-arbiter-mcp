"""FinOps cumulative audit ledger with optional SQLite WAL persistence."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

from gemini_cost_arbiter.models.audit import FinOpsAuditSummary


class FinOpsLedger:
    """Thread- and process-safe audit ledger with optional SQLite WAL persistence and JSON export."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path
        self._thread_lock = threading.RLock()
        self._file_lock: FileLock | None = None
        self.entries: list[dict[str, Any]] = []
        self._total_batches_processed: int = 0
        self._total_resources_analyzed: int = 0
        self._cumulative_waste_identified_usd: float = 0.0
        self._cumulative_projected_savings_usd: float = 0.0
        self._remediations_generated_count: int = 0
        self._last_updated: str = datetime.now(UTC).isoformat()

        if self.db_path:
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
                self._file_lock = FileLock(f"{self.db_path}.lock", timeout=10.0)
            self._init_sqlite()

    @contextmanager
    def _acquire_locks(self) -> Iterator[None]:
        """Acquire thread-level RLock and process-level FileLock in a consistent order."""
        with self._thread_lock:
            if self._file_lock is not None:
                with self._file_lock:
                    yield
            else:
                yield

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection configured with WAL mode and busy timeout."""
        if self.db_path is None:
            raise RuntimeError("Cannot connect to SQLite when db_path is None.")
        conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_sqlite(self) -> None:
        """Initialize SQLite database tables and restore cumulative metrics."""
        if self.db_path is None:
            return
        with self._acquire_locks():
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS finops_plans (
                            plan_id TEXT PRIMARY KEY,
                            created_at TEXT NOT NULL,
                            resource_count INTEGER NOT NULL,
                            projected_savings REAL NOT NULL,
                            plan_json TEXT NOT NULL
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS finops_metadata (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL
                        )
                        """
                    )
                self._load_from_sqlite_unlocked(conn)
            finally:
                conn.close()

    def _load_from_sqlite_unlocked(self, conn: sqlite3.Connection) -> None:
        """Load historical entries and counters from an active SQLite connection."""
        cursor = conn.cursor()
        cursor.execute("SELECT plan_json, resource_count FROM finops_plans ORDER BY created_at ASC")
        rows = cursor.fetchall()
        self.entries.clear()
        self._total_batches_processed = 0
        self._total_resources_analyzed = 0
        self._cumulative_waste_identified_usd = 0.0
        self._cumulative_projected_savings_usd = 0.0
        self._remediations_generated_count = 0

        for plan_json, r_count in rows:
            plan = json.loads(plan_json)
            self.entries.append(plan)
            savings = float(plan.get("total_projected_monthly_savings_usd", 0.0))
            self._total_batches_processed += 1
            self._total_resources_analyzed += int(r_count)
            self._cumulative_waste_identified_usd += savings
            self._cumulative_projected_savings_usd += savings
            self._remediations_generated_count += len(plan.get("actions", []))

        if self.entries:
            self._last_updated = self.entries[-1].get("created_at", datetime.now(UTC).isoformat())

    def _load_from_sqlite(self) -> None:
        """Load historical entries and counters from SQLite."""
        if self.db_path is None:
            return
        with self._acquire_locks():
            conn = self._connect()
            try:
                self._load_from_sqlite_unlocked(conn)
            finally:
                conn.close()

    def record_plan(self, plan_dict: dict[str, Any], resource_count: int) -> None:
        """Record an evaluated remediation plan in the ledger and persist to SQLite if enabled."""
        savings = float(plan_dict.get("total_projected_monthly_savings_usd", 0.0))
        actions_count = len(plan_dict.get("actions", []))
        plan_id = str(plan_dict.get("plan_id", ""))
        created_at = str(plan_dict.get("created_at", datetime.now(UTC).isoformat()))

        with self._acquire_locks():
            if self.db_path:
                conn = self._connect()
                try:
                    with conn:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO finops_plans (plan_id, created_at, resource_count, projected_savings, plan_json)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                plan_id,
                                created_at,
                                resource_count,
                                savings,
                                json.dumps(plan_dict, ensure_ascii=False),
                            ),
                        )
                finally:
                    conn.close()

            self.entries.append(plan_dict)
            self._total_batches_processed += 1
            self._total_resources_analyzed += resource_count
            self._cumulative_waste_identified_usd += savings
            self._cumulative_projected_savings_usd += savings
            self._remediations_generated_count += actions_count
            self._last_updated = datetime.now(UTC).isoformat()

    def get_summary(self) -> FinOpsAuditSummary:
        """Produce an aggregated executive summary."""
        with self._thread_lock:
            return FinOpsAuditSummary(
                total_batches_processed=self._total_batches_processed,
                total_resources_analyzed=self._total_resources_analyzed,
                cumulative_waste_identified_usd=round(self._cumulative_waste_identified_usd, 2),
                cumulative_projected_savings_usd=round(self._cumulative_projected_savings_usd, 2),
                remediations_generated_count=self._remediations_generated_count,
                last_updated=self._last_updated,
            )

    def reset(self) -> None:
        """Clear all audit entries and reset metrics."""
        with self._acquire_locks():
            if self.db_path:
                conn = self._connect()
                try:
                    with conn:
                        conn.execute("DELETE FROM finops_plans")
                        conn.execute("DELETE FROM finops_metadata")
                finally:
                    conn.close()

            self.entries.clear()
            self._total_batches_processed = 0
            self._total_resources_analyzed = 0
            self._cumulative_waste_identified_usd = 0.0
            self._cumulative_projected_savings_usd = 0.0
            self._remediations_generated_count = 0
            self._last_updated = datetime.now(UTC).isoformat()

    def export_json(self, destination_path: Path) -> None:
        """Export ledger contents to disk."""
        with self._thread_lock:
            data = {
                "summary": self.get_summary().model_dump(),
                "entries": list(self.entries),
            }
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
