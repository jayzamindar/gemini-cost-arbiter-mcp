"""Tests for SQLite-backed FinOps audit ledger persistence."""

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
