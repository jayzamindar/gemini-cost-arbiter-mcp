"""Server-Sent Events (SSE) and HTTP MCP transport server using FastAPI."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
import uvicorn

from gemini_cost_arbiter.engine import GeminiCostArbiterEngine

logger = logging.getLogger("gemini_cost_arbiter.sse")


class SensitiveQueryParamFilter(logging.Filter):
    """Redact sensitive query parameters such as apiKey from access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(re.sub(r"apiKey=[^&\s\"]+", "apiKey=***", arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
        if isinstance(record.msg, str):
            record.msg = re.sub(r"apiKey=[^&\s\"]+", "apiKey=***", record.msg)
        return True


# Install access log filter on uvicorn.access logger
logging.getLogger("uvicorn.access").addFilter(SensitiveQueryParamFilter())


def create_sse_app(
    engine: Optional[GeminiCostArbiterEngine] = None,
    api_key: Optional[str] = None,
) -> FastAPI:
    """Create FastAPI application exposing MCP endpoints over SSE and HTTP POST with optional auth."""
    app = FastAPI(
        title="Gemini Cost Arbiter MCP Server",
        version="1.0.0",
        description="Model Context Protocol Server with SSE and HTTP JSON-RPC 2.0 transports.",
    )
    arbiter_engine = engine or GeminiCostArbiterEngine()
    effective_api_key = api_key or arbiter_engine.config.mcp_api_key
    message_queues: Dict[str, asyncio.Queue] = {}

    def _verify_auth(request: Request) -> None:
        """Enforce timing-safe authentication and fail-closed security in production."""
        is_production = arbiter_engine.config.environment.lower() == "production"
        if (is_production or arbiter_engine.config.require_auth) and not effective_api_key:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: Server configuration mandates authentication, but MCP_API_KEY is unconfigured in production.",
            )

        if not effective_api_key:
            return

        # 1. Check Authorization: Bearer <token> (timing-safe constant-time comparison)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if hmac.compare_digest(token, effective_api_key):
                return
        # 2. Check X-API-Key header (timing-safe constant-time comparison)
        x_api_key = request.headers.get("X-API-Key", "").strip()
        if x_api_key and hmac.compare_digest(x_api_key, effective_api_key):
            return
        # 3. Check query param (?apiKey= or ?api_key=) for SSE browser connections (timing-safe comparison)
        query_key = request.query_params.get("apiKey") or request.query_params.get("api_key")
        if query_key and hmac.compare_digest(query_key, effective_api_key):
            return

        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Valid authentication credential required (Bearer token, X-API-Key, or ?apiKey=).",
        )

    @app.get("/health")
    async def health() -> Dict[str, str]:
        """Unauthenticated healthcheck probe for container orchestration."""
        return {"status": "healthy", "service": "gemini-cost-arbiter-mcp"}

    @app.get("/sse")
    async def sse_endpoint(request: Request) -> EventSourceResponse:
        """SSE stream for receiving JSON-RPC notifications and tool call results."""
        _verify_auth(request)
        client_id = str(id(request))
        queue: asyncio.Queue = asyncio.Queue()
        message_queues[client_id] = queue

        async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
            try:
                # Send endpoint discovery event according to MCP SSE specification
                yield {
                    "event": "endpoint",
                    "data": f"/messages?sessionId={client_id}",
                }
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield {"event": "message", "data": json.dumps(msg)}
                    except asyncio.TimeoutError:
                        yield {"event": "ping", "data": "{}"}
            finally:
                message_queues.pop(client_id, None)

        return EventSourceResponse(event_generator())

    @app.post("/messages")
    async def handle_message_post(request: Request) -> JSONResponse:
        """Process inbound JSON-RPC 2.0 messages posted to the session endpoint."""
        _verify_auth(request)
        try:
            body = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

        response = await arbiter_engine.handle_mcp_message(body)
        session_id = request.query_params.get("sessionId")

        if session_id and session_id in message_queues and response:
            await message_queues[session_id].put(response)

        return JSONResponse(content=response or {"jsonrpc": "2.0", "result": None})

    return app


def run_sse(
    host: str = "127.0.0.1",
    port: int = 8000,
    engine: Optional[GeminiCostArbiterEngine] = None,
    api_key: Optional[str] = None,
) -> None:
    """Launch Uvicorn webserver hosting the MCP SSE endpoints."""
    app = create_sse_app(engine=engine, api_key=api_key)
    uvicorn.run(app, host=host, port=port, log_level="info")
