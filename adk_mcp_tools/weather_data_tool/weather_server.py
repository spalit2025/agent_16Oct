"""
MCP Server for Weather Data Tools

Exposes weather data retrieval tools via Model Context Protocol (MCP) for integration
with the ADK multi-agent weather readiness framework.

This server wraps the weather data tools as MCP-compatible functions that can be
called by ADK agents or other MCP clients.
"""

import asyncio
import json
import os
from typing import Any, Dict
from dotenv import load_dotenv

# MCP Server Imports
from mcp import types as mcp_types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio

# ADK Tool Imports
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type

# Weather Data Tool Imports
from .tool_implementation import (
    find_closest_station_and_get_data,
    get_historical_weather_with_conversions,
    analyze_heat_events,
    calculate_flood_probability,
    get_census_tract_vulnerabilities,
)

# Load environment variables
load_dotenv()

# --- Initialize ADK Tools ---
print("Initializing Weather Data Tools for MCP exposure...")

# Wrap each function as an ADK FunctionTool
weather_tools = {
    "find_closest_station_and_get_data": FunctionTool(find_closest_station_and_get_data),
    "get_historical_weather_with_conversions": FunctionTool(get_historical_weather_with_conversions),
    "analyze_heat_events": FunctionTool(analyze_heat_events),
    "calculate_flood_probability": FunctionTool(calculate_flood_probability),
    "get_census_tract_vulnerabilities": FunctionTool(get_census_tract_vulnerabilities),
}

print(f"Initialized {len(weather_tools)} weather data tools:")
for tool_name in weather_tools:
    print(f"  - {tool_name}")

# --- MCP Server Setup ---
print("\nCreating MCP Server instance for Weather Data Tools...")
app = Server("weather-data-mcp-server")


@app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    """
    MCP handler to list all available weather data tools.

    Returns:
        List of MCP Tool schemas
    """
    print("MCP Server: Received list_tools request.")

    # Convert all ADK tools to MCP Tool schemas
    mcp_tool_schemas = []
    for tool_name, adk_tool in weather_tools.items():
        mcp_schema = adk_to_mcp_tool_type(adk_tool)
        mcp_tool_schemas.append(mcp_schema)
        print(f"MCP Server: Advertising tool: {mcp_schema.name}")

    return mcp_tool_schemas


@app.call_tool()
async def call_mcp_tool(
    name: str, arguments: dict
) -> list[mcp_types.Content]:
    """
    MCP handler to execute a weather data tool call.

    Args:
        name: Tool name to execute
        arguments: Dictionary of arguments for the tool

    Returns:
        List of MCP Content objects with tool results
    """
    print(f"MCP Server: Received call_tool request for '{name}'")
    print(f"MCP Server: Arguments: {json.dumps(arguments, indent=2)}")

    # Check if the requested tool exists
    if name not in weather_tools:
        error_msg = {
            "error": f"Tool '{name}' not found",
            "available_tools": list(weather_tools.keys())
        }
        print(f"MCP Server: Tool '{name}' not found")
        return [mcp_types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]

    try:
        # Get the ADK tool
        adk_tool = weather_tools[name]

        # Execute the tool
        # Note: tool_context is None because we're running outside full ADK Runner
        print(f"MCP Server: Executing tool '{name}'...")
        adk_tool_response = await adk_tool.run_async(
            args=arguments,
            tool_context=None,
        )
        print(f"MCP Server: Tool '{name}' executed successfully")
        print(f"MCP Server: Response preview: {str(adk_tool_response)[:200]}...")

        # Format response as JSON text content
        response_text = json.dumps(adk_tool_response, indent=2, default=str)
        return [mcp_types.TextContent(type="text", text=response_text)]

    except Exception as e:
        error_msg = {
            "error": f"Failed to execute tool '{name}'",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "tool_name": name,
            "arguments": arguments
        }
        print(f"MCP Server: Error executing tool '{name}': {e}")
        return [mcp_types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]


# --- MCP Server Runner ---
async def run_mcp_stdio_server():
    """
    Runs the MCP server, listening for connections over standard input/output.
    """
    print("\n" + "="*60)
    print("Weather Data MCP Server")
    print("="*60)
    print(f"Exposing {len(weather_tools)} tools via MCP protocol")
    print("="*60 + "\n")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        print("MCP Stdio Server: Starting handshake with client...")
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=app.name,
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
        print("MCP Stdio Server: Run loop finished or client disconnected.")


def main():
    """
    Main entry point for the Weather Data MCP Server.
    """
    print("Launching Weather Data MCP Server via stdio...")
    try:
        asyncio.run(run_mcp_stdio_server())
    except KeyboardInterrupt:
        print("\nWeather Data MCP Server stopped by user.")
    except Exception as e:
        print(f"Weather Data MCP Server encountered an error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Weather Data MCP Server process exiting.")


if __name__ == "__main__":
    main()
