"""
Weather Data Retrieval System for ADK Multi-Agent Weather Readiness Framework

This package provides comprehensive weather data retrieval tools for the Data Agent,
including historical weather data from GHCN stations, census tract vulnerability analysis,
and specialized analysis functions for heat events and flood probability.

Modules:
    - tool_implementation: Core Python functions for weather data retrieval
    - tool_schema: JSON schema definitions for tool specifications
    - weather_server: MCP server wrapper for exposing weather tools
"""

from .tool_implementation import (
    find_closest_station_and_get_data,
    get_historical_weather_with_conversions,
    analyze_heat_events,
    calculate_flood_probability,
    get_census_tract_vulnerabilities,
)

__version__ = "0.1.0"
__all__ = [
    "find_closest_station_and_get_data",
    "get_historical_weather_with_conversions",
    "analyze_heat_events",
    "calculate_flood_probability",
    "get_census_tract_vulnerabilities",
]
