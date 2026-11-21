"""Standard I/O MCP transport server."""

from __future__ import annotations

import asyncio

from gemini_cost_arbiter.engine import GeminiCostArbiterEngine


async def run_stdio(engine: GeminiCostArbiterEngine) -> None:
    """Run standard I/O loop."""
    await engine.run_stdio_server()


def main() -> None:
    """Stdio server process runner."""
    engine = GeminiCostArbiterEngine()
    try:
        asyncio.run(run_stdio(engine))
    except KeyboardInterrupt:
        pass
