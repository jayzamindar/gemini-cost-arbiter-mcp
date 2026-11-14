"""FinOps cumulative audit ledger with optional SQLite persistence."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from gemini_cost_arbiter.models.audit import FinOpsAuditSummary


class FinOpsLedger:
    """Thread-safe audit ledger with optional SQLite persistence and JSON export."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        self.entries: List[Dict[str, Any]] = []
        self._total_batches_processed: int = 0
        self._total_resources_analyzed: int = 0
        self._cumulative_waste_identified_usd: float = 0.0
        self._cumulative_projected_savings_usd: float = 0.0
        self._remediations_generated_count: int = 0
        self._last_updated: str = datetime.now(timezone.utc).isoformat()

        if self.db_path:
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize SQLite database tables and restore cumulative metrics."""
        conn = sqlite3.connect(self.db_path)
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
            self._load_from_sqlite()
        finally:
            conn.close()

    def _load_from_sqlite(self) -> None:
        """Load historical entries and counters from SQLite."""
        conn = sqlite3.connect(self.db_path)
        try:
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
                self._last_updated = self.entries[-1].get("created_at", datetime.now(timezone.utc).isoformat())
        finally:
            conn.close()

    def record_plan(self, plan_dict: Dict[str, Any], resource_count: int) -> None:
        """Record an evaluated remediation plan in the ledger and persist to SQLite if enabled."""
        self.entries.append(plan_dict)
        savings = float(plan_dict.get("total_projected_monthly_savings_usd", 0.0))
        actions_count = len(plan_dict.get("actions", []))
        plan_id = str(plan_dict.get("plan_id", ""))
        created_at = str(plan_dict.get("created_at", datetime.now(timezone.utc).isoformat()))

        self._total_batches_processed += 1
        self._total_resources_analyzed += resource_count
        self._cumulative_waste_identified_usd += savings
        self._cumulative_projected_savings_usd += savings
        self._remediations_generated_count += actions_count
        self._last_updated = datetime.now(timezone.utc).isoformat()

        if self.db_path:
            conn = sqlite3.connect(self.db_path)
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO finops_plans (plan_id, created_at, resource_count, projected_savings, plan_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (plan_id, created_at, resource_count, savings, json.dumps(plan_dict)),
                    )
            finally:
                conn.close()

    def get_summary(self) -> FinOpsAuditSummary:
        """Produce an aggregated executive summary."""
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
        self.entries.clear()
        self._total_batches_processed = 0
        self._total_resources_analyzed = 0
        self._cumulative_waste_identified_usd = 0.0
        self._cumulative_projected_savings_usd = 0.0
        self._remediations_generated_count = 0
        self._last_updated = datetime.now(timezone.utc).isoformat()

        if self.db_path:
            conn = sqlite3.connect(self.db_path)
            try:
                with conn:
                    conn.execute("DELETE FROM finops_plans")
                    conn.execute("DELETE FROM finops_metadata")
            finally:
                conn.close()

    def export_json(self, destination_path: Path) -> None:
        """Export ledger contents to disk."""
        data = {
            "summary": self.get_summary().model_dump(),
            "entries": self.entries,
        }
        destination_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
