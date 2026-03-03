"""MCP server for TransMax - exposes translation tools to AI agents.

Usage:
    python -m transmax_mcp.server

Config for claude_desktop_config.json:
    {
        "mcpServers": {
            "transmax": {
                "command": "python",
                "args": ["-m", "transmax_mcp.server"],
                "env": {"OPENAI_API_KEY": "..."}
            }
        }
    }
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any


def create_server():
    """Create and configure the MCP server with TransMax tools."""
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent
    except ImportError:
        print("Error: 'mcp' package not installed. Install with: pip install mcp", file=sys.stderr)
        sys.exit(1)

    from transmax_sdk import TransMaxSDK, SDKConfig
    from transmax_mcp.tools import TransMaxTools

    # Build SDK config from environment
    config = SDKConfig(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )
    sdk = TransMaxSDK(config=config)
    tools = TransMaxTools(sdk=sdk)

    server = Server("transmax")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="translate",
                description="Translate text to a target language with pharma quality checks. Auto-detects source language.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to translate"},
                        "target_lang": {"type": "string", "description": "Target language code (e.g., 'ja', 'fr', 'de')"},
                        "source_lang": {"type": "string", "description": "Source language code, or 'auto' for detection", "default": "auto"},
                    },
                    "required": ["text", "target_lang"],
                },
            ),
            Tool(
                name="detect_language",
                description="Detect the language of input text.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to analyze"},
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="quality_check",
                description="Run pharmaceutical quality gates on a source/translation pair. Returns verdict (PASS/REVIEW_REQUIRED/BLOCKED) and defects.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_text": {"type": "string"},
                        "translated_text": {"type": "string"},
                        "source_lang": {"type": "string"},
                        "target_lang": {"type": "string"},
                    },
                    "required": ["source_text", "translated_text", "source_lang", "target_lang"],
                },
            ),
            Tool(
                name="back_translate",
                description="Verify a translation via back-translation to the original language.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "translated_text": {"type": "string"},
                        "source_lang": {"type": "string", "description": "Original language"},
                        "target_lang": {"type": "string", "description": "Language of the translated text"},
                    },
                    "required": ["translated_text", "source_lang", "target_lang"],
                },
            ),
            Tool(
                name="glossary_lookup",
                description="Look up a term in the active glossary for approved translations.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {"type": "string"},
                        "target_lang": {"type": "string", "default": ""},
                    },
                    "required": ["term"],
                },
            ),
            Tool(
                name="estimate_cost",
                description="Estimate the LLM cost for translating text.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "model": {"type": "string", "description": "Model name (optional)"},
                    },
                    "required": ["text"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            if name == "translate":
                result = await tools.translate(
                    text=arguments["text"],
                    target_lang=arguments["target_lang"],
                    source_lang=arguments.get("source_lang", "auto"),
                )
            elif name == "detect_language":
                result = tools.detect_language(arguments["text"])
            elif name == "quality_check":
                result = await tools.quality_check(
                    source_text=arguments["source_text"],
                    translated_text=arguments["translated_text"],
                    source_lang=arguments["source_lang"],
                    target_lang=arguments["target_lang"],
                )
            elif name == "back_translate":
                result = await tools.back_translate(
                    translated_text=arguments["translated_text"],
                    source_lang=arguments["source_lang"],
                    target_lang=arguments["target_lang"],
                )
            elif name == "glossary_lookup":
                result = tools.glossary_lookup(
                    term=arguments["term"],
                    target_lang=arguments.get("target_lang", ""),
                )
            elif name == "estimate_cost":
                result = tools.estimate_cost(
                    text=arguments["text"],
                    model=arguments.get("model"),
                )
            else:
                result = {"error": f"Unknown tool: {name}"}

            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    return server


async def main():
    from mcp.server.stdio import stdio_server
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
