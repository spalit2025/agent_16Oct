# Weather Data Tool

Comprehensive weather data retrieval system for the ADK Multi-Agent Weather Readiness Framework.

## Overview

This package provides tools for retrieving and analyzing weather data from BigQuery public datasets, including:
- GHCN (Global Historical Climatology Network) weather stations
- US Census data for vulnerability analysis
- Historical weather event analysis

## Components

### 1. `tool_schema.py`
Original JSON schema defining the tool specifications and data models.

### 2. `tool_implementation.py`
Core Python implementations of weather data retrieval functions:

- **`find_closest_station_and_get_data`**: Find nearest GHCN weather station to a location
- **`get_historical_weather_with_conversions`**: Retrieve historical data with unit conversions
- **`analyze_heat_events`**: Identify and analyze historical heat waves
- **`calculate_flood_probability`**: Calculate flash flood probability from rainfall data
- **`get_census_tract_vulnerabilities`**: Identify vulnerable populations in census tracts

### 3. `weather_server.py`
MCP server wrapper that exposes weather tools via Model Context Protocol for ADK agent integration.

## Installation

### Prerequisites
```bash
pip install google-cloud-bigquery
pip install mcp
pip install google-adk
pip install python-dotenv
```

### Environment Setup
Create a `.env` file in the weather_data_tool directory:
```bash
GOOGLE_CLOUD_PROJECT=your-project-id
```

## Usage

### As Python Functions
```python
from adk_mcp_tools.weather_data_tool import find_closest_station_and_get_data

# Find closest weather station to coordinates
result = find_closest_station_and_get_data(
    latitude=37.39,
    longitude=-122.08,
    elements=["TMAX", "TMIN", "PRCP"],
    year=2024,
    limit=10
)

print(f"Station: {result['station_name']}")
print(f"Distance: {result['distance_miles']} miles")
```

### As MCP Server
Run the MCP server to expose tools to ADK agents:
```bash
cd /Users/sandippalit/Desktop/agent_16Oct/adk_mcp_tools/weather_data_tool
python weather_server.py
```

### With ADK Agents
Configure your Data Agent to use the weather tools:
```python
from google.adk.agents import Agent
from adk_mcp_tools.weather_data_tool import (
    find_closest_station_and_get_data,
    get_historical_weather_with_conversions
)

data_agent = Agent(
    name="Data Agent",
    tools=[find_closest_station_and_get_data, get_historical_weather_with_conversions]
)
```

## Tool Reference

### find_closest_station_and_get_data
Finds the closest GHCN weather station and retrieves recent data.

**Parameters:**
- `latitude` (float): Target latitude (-90 to 90)
- `longitude` (float): Target longitude (-180 to 180)
- `elements` (list, optional): Weather elements ["TMAX", "TMIN", "PRCP"]
- `year` (int, optional): Year to query (default: 2024)
- `limit` (int, optional): Max records (default: 10)

**Returns:**
Dictionary with station info and weather data.

### get_historical_weather_with_conversions
Retrieves historical weather data with automatic unit conversions.

**Parameters:**
- `station_id` (str): GHCN station ID (e.g., "USC00045860")
- `start_year` (int): Start year for data range
- `end_year` (int): End year for data range
- `elements` (list, optional): Weather elements to retrieve
- `start_date` (str, optional): Filter by start date (YYYY-MM-DD)
- `end_date` (str, optional): Filter by end date (YYYY-MM-DD)

**Returns:**
Dictionary with historical data and unit conversions.

### analyze_heat_events
Analyzes historical heat events to identify severe heat waves.

**Parameters:**
- `station_id` (str): GHCN station ID
- `lookback_years` (int, optional): Years to analyze (default: 5)
- `temperature_threshold_f` (float, optional): Temp threshold in F (default: 95)
- `consecutive_days` (int, optional): Min consecutive days (default: 3)

**Returns:**
Dictionary with heat event analysis and identified heat waves.

### calculate_flood_probability
Calculates flash flood probability based on rainfall intensity.

**Parameters:**
- `station_id` (str): GHCN station ID
- `rainfall_threshold_inches` (float): Rainfall threshold in inches
- `lookback_years` (int, optional): Years to analyze (default: 10)
- `time_window_hours` (int, optional): Time window (default: 1)

**Returns:**
Dictionary with flood probability analysis.

### get_census_tract_vulnerabilities
Identifies census tracts with socioeconomic vulnerabilities.

**Parameters:**
- `city_name` (str, optional): City name
- `state_code` (str, optional): Two-letter state code
- `path_coordinates` (list, optional): Storm path coordinates
- `bounding_box` (dict, optional): Geographic bounds
- `income_filter` (str, optional): Income comparison filter
- `population_density_filter` (str, optional): Density filter

**Returns:**
Dictionary with vulnerable census tract information.

## Data Sources

### BigQuery Public Datasets
- **GHCN Daily**: `bigquery-public-data.ghcn_d.ghcnd_*`
  - Weather station data with temperature, precipitation, snowfall, etc.
  - Global coverage with historical records

- **GHCN Stations**: `bigquery-public-data.ghcn_d.ghcnd_stations`
  - Station metadata with coordinates and names

- **US Census**: `bigquery-public-data.census_bureau_acs.*`
  - American Community Survey data
  - Demographics and socioeconomic indicators

## Unit Conversions

The tools automatically handle unit conversions:

| Element | Source Unit | Metric | Imperial |
|---------|------------|--------|----------|
| TMAX/TMIN | Tenths of °C | °Celsius | °Fahrenheit |
| PRCP | Tenths of mm | mm | inches |

## Error Handling

All functions return structured responses with status indicators:

```python
{
    "status": "success" | "no_data" | "error",
    "message": "Human-readable status message",
    "data": [...],
    ...
}
```

## Integration with Weather Readiness Framework

This tool is designed for the **Data Agent** in the multi-agent workflow:

1. **Root Agent** parses user query
2. **Data Agent** uses these tools to retrieve historical/census data
3. **Forecast Agent** gets real-time forecasts
4. **Insights Agent** synthesizes actionable recommendations

## Development

### Running Tests
```bash
pytest tests/test_weather_tools.py
```

### Adding New Tools
1. Add function to `tool_implementation.py`
2. Update `__init__.py` exports
3. Add tool to `weather_server.py` tools dictionary
4. Update this README

## License

Part of the Google ADK Agents for Impact Weather Readiness project.

## Support

For issues or questions, refer to the main project documentation in `/reference_docs/`.
