"""Tests for SQLite-backed FinOps audit ledger persistence."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from gemini_cost_arbiter.ledger.store import FinOpsLedger


def test_sqlite_ledger_persistence(tmp_path: Path) -> None:
    """Verify ledger records persist to SQLite and restore across restarts."""
    db_file = tmp_path / "finops_audit.db"

    # Session 1: Create ledger and record a plan
    ledger_1 = FinOpsLedger(db_path=str(db_file))
    sample_plan = {
        "plan_id": "test-uuid-001",
        "created_at": "2026-11-13T00:00:00Z",
        "total_projected_monthly_savings_usd": 450.0,
        "actions": [{"resource_id": "i-test", "safety_risk_score": 3}],
    }
    ledger_1.record_plan(sample_plan, resource_count=2)

    summary_1 = ledger_1.get_summary()
    assert summary_1.total_batches_processed == 1
    assert summary_1.total_resources_analyzed == 2
    assert summary_1.cumulative_projected_savings_usd == 450.0

    # Session 2: Instantiate new ledger instance pointing to the same SQLite database
    ledger_2 = FinOpsLedger(db_path=str(db_file))
    summary_2 = ledger_2.get_summary()

    # Verify state was restored seamlessly
    assert summary_2.total_batches_processed == 1
    assert summary_2.total_resources_analyzed == 2
    assert summary_2.cumulative_projected_savings_usd == 450.0
    assert len(ledger_2.entries) == 1
    assert ledger_2.entries[0]["plan_id"] == "test-uuid-001"


def test_sqlite_wal_and_concurrent_writes(tmp_path: Path) -> None:
    """Verify WAL mode, busy_timeout, auto-mkdir, ensure_ascii=False, and 20-thread concurrency."""
    db_file = tmp_path / "nested" / "wal" / "finops.db"
    ledger = FinOpsLedger(db_path=str(db_file))

    assert db_file.parent.is_dir()
    with closing(sqlite3.connect(str(db_file))) as conn:
        journal_mode = str(conn.execute("PRAGMA journal_mode;").fetchone()[0]).lower()
    assert journal_mode == "wal"

    def _write_plan(idx: int) -> None:
        ledger.record_plan(
            {
                "plan_id": f"concurrent-plan-{idx:03d}",
                "created_at": f"2026-11-21T00:00:{idx:02d}Z",
                "total_projected_monthly_savings_usd": 25.0,
                "actions": [{"resource_id": f"i-conc-{idx:03d}", "note": "Savings €25 / 日本語"}],
            },
            resource_count=1,
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_write_plan, idx) for idx in range(20)]
        for fut in futures:
            fut.result()

    summary = ledger.get_summary()
    assert summary.total_batches_processed == 20
    assert summary.total_resources_analyzed == 20
    assert summary.cumulative_projected_savings_usd == 500.0

    # Verify persistence and non-ASCII preservation across reload and JSON export
    reloaded = FinOpsLedger(db_path=str(db_file))
    assert reloaded.get_summary().total_batches_processed == 20
    assert "€25 / 日本語" in reloaded.entries[0]["actions"][0]["note"]

    export_file = tmp_path / "export" / "ledger.json"
    reloaded.export_json(export_file)
    exported_text = export_file.read_text(encoding="utf-8")
    assert "€25 / 日本語" in exported_text

    # Verify reset clears both in-memory and SQLite state
    reloaded.reset()
    assert reloaded.get_summary().total_batches_processed == 0
    assert reloaded.entries == []
    reloaded_after_reset = FinOpsLedger(db_path=str(db_file))
    assert reloaded_after_reset.get_summary().total_batches_processed == 0

    # Verify in-memory ledger (db_path=None)
    mem_ledger = FinOpsLedger(db_path=None)
    mem_ledger.record_plan({"plan_id": "mem-1", "total_projected_monthly_savings_usd": 10.0, "actions": []}, 1)
    assert mem_ledger.get_summary().total_batches_processed == 1
    mem_ledger.reset()
    assert mem_ledger.get_summary().total_batches_processed == 0
