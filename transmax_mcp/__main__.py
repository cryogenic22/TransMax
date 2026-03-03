"""Entry point for running MCP server: python -m transmax_mcp"""
from transmax_mcp.server import main
import asyncio

asyncio.run(main())
