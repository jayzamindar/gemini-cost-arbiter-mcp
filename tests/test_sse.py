"""Tests for SSE and HTTP MCP endpoints using FastAPI."""

import httpx
import pytest

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
        assert "approve_quarantined_action" in tool_names


@pytest.mark.asyncio
async def test_sse_rejects_oversized_payload_413_and_uses_random_session(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Verify MAX_PAYLOAD_BYTES returns HTTP 413, invalid JSON returns 400, and /sse uses random session IDs."""
    from gemini_cost_arbiter.config import ArbiterConfig

    engine = GeminiCostArbiterEngine(
        config=ArbiterConfig(
            max_payload_bytes=1024,
            db_path=str(tmp_path / "sse_413.db"),
        )
    )
    app = create_sse_app(engine=engine)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        oversized = '{"jsonrpc":"2.0","id":1,"method":"ping","pad":"' + ("x" * 2048) + '"}'
        res_413 = await client.post(
            "/messages",
            content=oversized.encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert res_413.status_code == 413
        assert "Payload Too Large" in res_413.text

        res_400 = await client.post(
            "/messages",
            content=b"{not-valid-json",
            headers={"Content-Type": "application/json"},
        )
        assert res_400.status_code == 400

    # Verify /sse route emits cryptographically random sessionId (>= 16 chars)
    import re
    import secrets

    # Exercise /sse endpoint generator directly via ASGI scope
    session_ids: list[str] = []
    for _ in range(2):
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/sse",
            "raw_path": b"/sse",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("test", 80),
        }

        async def receive() -> dict[str, str]:
            return {"type": "http.disconnect"}

        sent_chunks: list[bytes] = []

        async def send(message: dict[str, object]) -> None:
            if message.get("type") == "http.response.body":
                body = message.get("body", b"")
                if isinstance(body, bytes):
                    sent_chunks.append(body)

        await app(scope, receive, send)
        joined = b"".join(sent_chunks).decode("utf-8", errors="replace")
        match = re.search(r"sessionId=([A-Za-z0-9_-]+)", joined)
        assert match is not None, f"Missing sessionId in SSE output: {joined!r}"
        sid = match.group(1)
        assert len(sid) >= 16
        assert sid != str(id(scope))
        session_ids.append(sid)

    assert len(set(session_ids)) == 2
    assert len(secrets.token_urlsafe(16)) >= 16


@pytest.mark.asyncio
async def test_sse_rejects_placeholder_api_key_in_production(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Production mode must reject placeholder MCP_API_KEY values with HTTP 401."""
    from gemini_cost_arbiter.config import ArbiterConfig

    prod_engine = GeminiCostArbiterEngine(
        config=ArbiterConfig(
            environment="production",
            mcp_api_key="changeme",
            db_path=str(tmp_path / "sse_prod.db"),
        )
    )
    app = create_sse_app(engine=prod_engine)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/messages",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"X-API-Key": "changeme"},
        )
        assert res.status_code == 401
        assert "placeholder" in res.text
