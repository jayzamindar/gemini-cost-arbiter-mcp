"""Backward-compatibility layer for app.engine.

Re-exports GeminiCostArbiterEngine from the modular gemini_cost_arbiter package.
"""

from __future__ import annotations

import asyncio
from gemini_cost_arbiter.engine import GeminiCostArbiterEngine

__all__ = ["GeminiCostArbiterEngine"]

if __name__ == "__main__":
    engine = GeminiCostArbiterEngine()
    try:
        asyncio.run(engine.run_stdio_server())
    except KeyboardInterrupt:
        pass
