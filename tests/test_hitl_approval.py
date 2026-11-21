"""Tests for Critical Risk (5/5) Quarantine & Anti-Replay HITL Approval Gate (REM-013)."""

from __future__ import annotations

import json
import time

import pytest

from gemini_cost_arbiter.config import ArbiterConfig
from gemini_cost_arbiter.engine import GeminiCostArbiterEngine
from gemini_cost_arbiter.guardrails.risk_scorer import GuardrailEngine
from gemini_cost_arbiter.models.remediation import RemediationActionItem


def test_risk_5_quarantined_and_anti_replay_approval() -> None:
    """Risk 5/5 actions are always quarantined; HITL approval enforces HMAC, <=300s TTL, expiry, and nonce uniqueness."""
    raw_action = {
        "resource_id": "i-critical-prod-db",
        "resource_type": "EC2",
        "action_type": "TERMINATE",
        "target_configuration": "terminated",
        "current_monthly_spend_usd": 1200.0,
        "projected_monthly_spend_usd": 0.0,
        "projected_monthly_savings_usd": 1200.0,
        "safety_risk_score": 5,
        "system_mitigations": ["Pre-termination EBS snapshot", "DNS failover verified"],
    }
    enriched = GuardrailEngine.audit_and_enrich_action(raw_action)
    assert enriched["quarantined"] is True
    assert enriched["quarantine_reason"] == "Critical risk (5/5) requires signed HITL SRE approval"

    item = RemediationActionItem(**enriched)
    assert item.quarantined is True

    secret = "prod-hitl-signing-secret-at-least-32-chars!"
    now = 1_700_000_000.0
    issued_at = now - 10.0
    expires_at = issued_at + 300.0
    nonce = "nonce-unique-001"
    used_nonces: set[str] = set()

    sig = GuardrailEngine.sign_hitl_approval(
        plan_id="plan-123",
        resource_id="i-critical-prod-db",
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
        secret=secret,
    )

    # Valid approval succeeds once
    assert (
        GuardrailEngine.verify_hitl_approval(
            plan_id="plan-123",
            resource_id="i-critical-prod-db",
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce,
            signature=sig,
            secret=secret,
            now=now,
            used_nonces=used_nonces,
        )
        is True
    )

    # Replayed nonce fails closed
    assert (
        GuardrailEngine.verify_hitl_approval(
            plan_id="plan-123",
            resource_id="i-critical-prod-db",
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce,
            signature=sig,
            secret=secret,
            now=now,
            used_nonces=used_nonces,
        )
        is False
    )

    # TTL > 300s fails closed
    bad_ttl_sig = GuardrailEngine.sign_hitl_approval(
        plan_id="plan-123",
        resource_id="i-critical-prod-db",
        issued_at=issued_at,
        expires_at=issued_at + 301.0,
        nonce="nonce-ttl-too-long",
        secret=secret,
    )
    assert (
        GuardrailEngine.verify_hitl_approval(
            plan_id="plan-123",
            resource_id="i-critical-prod-db",
            issued_at=issued_at,
            expires_at=issued_at + 301.0,
            nonce="nonce-ttl-too-long",
            signature=bad_ttl_sig,
            secret=secret,
            now=now,
            used_nonces=used_nonces,
        )
        is False
    )

    # Expired token (now >= expires_at) fails closed
    expired_sig = GuardrailEngine.sign_hitl_approval(
        plan_id="plan-123",
        resource_id="i-critical-prod-db",
        issued_at=now - 200.0,
        expires_at=now,
        nonce="nonce-expired",
        secret=secret,
    )
    assert (
        GuardrailEngine.verify_hitl_approval(
            plan_id="plan-123",
            resource_id="i-critical-prod-db",
            issued_at=now - 200.0,
            expires_at=now,
            nonce="nonce-expired",
            signature=expired_sig,
            secret=secret,
            now=now,
            used_nonces=used_nonces,
        )
        is False
    )

    # Tampered resource_id fails closed
    assert (
        GuardrailEngine.verify_hitl_approval(
            plan_id="plan-123",
            resource_id="i-other-instance",
            issued_at=issued_at,
            expires_at=expires_at,
            nonce="nonce-tampered",
            signature=sig,
            secret=secret,
            now=now,
            used_nonces=used_nonces,
        )
        is False
    )


@pytest.mark.asyncio
async def test_mcp_approve_quarantined_action_tool(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Verify approve_quarantined_action is registered in tools/list and enforces anti-replay in tools/call."""
    secret = "mcp-hitl-signing-secret-at-least-32-chars!"
    engine = GeminiCostArbiterEngine(
        config=ArbiterConfig(
            plan_signing_secret=secret,
            db_path=str(tmp_path / "hitl.db"),
        )
    )

    list_resp = await engine.handle_mcp_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert list_resp is not None
    tool_names = [t["name"] for t in list_resp["result"]["tools"]]
    assert "approve_quarantined_action" in tool_names

    now = time.time()
    issued_at = now - 5.0
    expires_at = issued_at + 120.0
    nonce = "mcp-nonce-001"
    sig = GuardrailEngine.sign_hitl_approval(
        plan_id="plan-mcp-1",
        resource_id="i-risk5-01",
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
        secret=secret,
    )

    call_resp = await engine.handle_mcp_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "approve_quarantined_action",
                "arguments": {
                    "plan_id": "plan-mcp-1",
                    "resource_id": "i-risk5-01",
                    "issued_at": issued_at,
                    "expires_at": expires_at,
                    "nonce": nonce,
                    "signature": sig,
                },
            },
        }
    )
    assert call_resp is not None
    assert "result" in call_resp
    payload = json.loads(call_resp["result"]["content"][0]["text"])
    assert payload["approved"] is True
    assert payload["quarantined"] is False
    assert payload["nonce"] == nonce

    # Replay same nonce -> JSON-RPC -32602 error
    replay_resp = await engine.handle_mcp_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "approve_quarantined_action",
                "arguments": {
                    "plan_id": "plan-mcp-1",
                    "resource_id": "i-risk5-01",
                    "issued_at": issued_at,
                    "expires_at": expires_at,
                    "nonce": nonce,
                    "signature": sig,
                },
            },
        }
    )
    assert replay_resp is not None
    assert replay_resp["error"]["code"] == -32602
