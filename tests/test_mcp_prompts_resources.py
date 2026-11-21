"""Tests validating Model Context Protocol (MCP) Prompts and Resources lifecycle."""

import json

import pytest

from gemini_cost_arbiter.engine import GeminiCostArbiterEngine


@pytest.mark.asyncio
async def test_mcp_prompts_list_and_get() -> None:
    """Verify prompts/list and prompts/get operations."""
    engine = GeminiCostArbiterEngine()

    # 1. prompts/list
    list_msg = {"jsonrpc": "2.0", "id": 10, "method": "prompts/list", "params": {}}
    resp = await engine.handle_mcp_message(list_msg)
    assert resp is not None
    assert resp["id"] == 10
    prompts = resp["result"]["prompts"]
    prompt_names = [p["name"] for p in prompts]
    assert "finops_waste_audit_runbook" in prompt_names
    assert "remediation_rollback_procedure" in prompt_names

    # 2. prompts/get for finops_waste_audit_runbook
    get_msg = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "prompts/get",
        "params": {"name": "finops_waste_audit_runbook", "arguments": {"environment": "production"}},
    }
    get_resp = await engine.handle_mcp_message(get_msg)
    assert get_resp is not None
    assert get_resp["id"] == 11
    content_text = get_resp["result"]["messages"][0]["content"]["text"]
    assert "production" in content_text
    assert "generate_remediation_plan" in content_text


@pytest.mark.asyncio
async def test_mcp_resources_list_and_read() -> None:
    """Verify resources/list and resources/read operations."""
    engine = GeminiCostArbiterEngine()

    # 1. resources/list
    list_msg = {"jsonrpc": "2.0", "id": 20, "method": "resources/list", "params": {}}
    resp = await engine.handle_mcp_message(list_msg)
    assert resp is not None
    resources = resp["result"]["resources"]
    uris = [r["uri"] for r in resources]
    assert "finops://audit/ledger" in uris
    assert "finops://policies/risk-matrix" in uris
    assert "finops://config/instance-mappings" in uris

    # 2. resources/read for finops://policies/risk-matrix
    read_matrix = {
        "jsonrpc": "2.0",
        "id": 21,
        "method": "resources/read",
        "params": {"uri": "finops://policies/risk-matrix"},
    }
    matrix_resp = await engine.handle_mcp_message(read_matrix)
    assert matrix_resp is not None
    content_json = matrix_resp["result"]["contents"][0]["text"]
    matrix_data = json.loads(content_json)
    assert "1" in matrix_data
    assert "5" in matrix_data

    # 3. resources/read for finops://config/instance-mappings
    read_mappings = {
        "jsonrpc": "2.0",
        "id": 22,
        "method": "resources/read",
        "params": {"uri": "finops://config/instance-mappings"},
    }
    mappings_resp = await engine.handle_mcp_message(read_mappings)
    assert mappings_resp is not None
    mappings_json = mappings_resp["result"]["contents"][0]["text"]
    mappings_data = json.loads(mappings_json)
    assert "instance_downsize_map" in mappings_data
