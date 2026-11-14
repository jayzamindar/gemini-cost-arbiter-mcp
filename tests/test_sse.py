"""Tests for SSE and HTTP MCP endpoints using FastAPI."""

import pytest
import httpx
from gemini_cost_arbiter.engine import GeminiCostArbiterEngine
from gemini_cost_arbiter.mcp.server_sse import create_sse_app


@pytest.mark.asyncio
async def test_sse_app_health() -> None:
    """Verify health endpoint."""
    app = create_sse_app(GeminiCostArbiterEngine())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "gemini-cost-arbiter-mcp"


@pytest.mark.asyncio
async def test_sse_app_messages_initialize() -> None:
    """Verify POST /messages initializes MCP handshake."""
    app = create_sse_app(GeminiCostArbiterEngine())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "test-client", "version": "1.0.0"}},
        }
        response = await client.post("/messages", json=req)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert "serverInfo" in data["result"]
        assert data["result"]["serverInfo"]["name"] == "gemini-cost-arbiter-mcp"


@pytest.mark.asyncio
async def test_sse_app_messages_tools_list() -> None:
    """Verify POST /messages lists MCP tools."""
    app = create_sse_app(GeminiCostArbiterEngine())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        response = await client.post("/messages", json=req)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 2
        tool_names = [t["name"] for t in data["result"]["tools"]]
        assert "analyze_infrastructure_waste" in tool_names
        assert "generate_remediation_plan" in tool_names
        assert "get_finops_audit_summary" in tool_names
