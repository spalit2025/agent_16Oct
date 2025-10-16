"""
Weather Data Tool Implementation

Implements the core functions for retrieving and analyzing weather data from BigQuery
public datasets (GHCN weather stations, US Census data) for the Data Agent in the
multi-agent weather readiness framework.

Functions:
    - find_closest_station_and_get_data: Find nearest GHCN station and get recent data
    - get_historical_weather_with_conversions: Retrieve historical data with unit conversions
    - analyze_heat_events: Identify historical heat waves
    - calculate_flood_probability: Calculate flood probability from rainfall data
    - get_census_tract_vulnerabilities: Identify vulnerable populations
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from google.cloud import bigquery
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeatherDataRetrieval:
    """
    Main class for weather data retrieval operations using BigQuery.
    """

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize the WeatherDataRetrieval client.

        Args:
            project_id: Google Cloud project ID. If None, uses default credentials.
        """
        self.client = bigquery.Client(project=project_id)
        logger.info(f"Initialized BigQuery client for project: {project_id or 'default'}")

    def _execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a BigQuery SQL query and return results as list of dictionaries.

        Args:
            query: SQL query string

        Returns:
            List of result rows as dictionaries
        """
        try:
            logger.info(f"Executing query: {query[:200]}...")
            query_job = self.client.query(query)
            results = query_job.result()

            # Convert to list of dictionaries
            rows = [dict(row) for row in results]
            logger.info(f"Query returned {len(rows)} rows")
            return rows

        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            raise


def find_closest_station_and_get_data(
    latitude: float,
    longitude: float,
    elements: Optional[List[str]] = None,
    year: int = 2024,
    limit: int = 10,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Finds the closest GHCN weather station to a target location and retrieves recent data.

    Args:
        latitude: Target location latitude in decimal degrees (-90 to 90)
        longitude: Target location longitude in decimal degrees (-180 to 180)
        elements: Weather elements to retrieve (default: ["TMAX", "TMIN", "PRCP"])
        year: Year to query (default: 2024)
        limit: Maximum number of records to return (default: 10)
        project_id: Google Cloud project ID

    Returns:
        Dictionary containing station info and weather data

    Example:
        >>> result = find_closest_station_and_get_data(37.39, -122.08)
        >>> print(result['station_name'], result['distance_miles'])
    """
    # Validate inputs
    if not -90 <= latitude <= 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
    if not -180 <= longitude <= 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")

    if elements is None:
        elements = ["TMAX", "TMIN", "PRCP"]

    # Format elements for SQL IN clause
    elements_str = ", ".join([f"'{elem}'" for elem in elements])

    # Construct SQL query
    query = f"""
        WITH
        target_location AS (
          SELECT ST_GEOGPOINT({longitude}, {latitude}) AS my_point
        ),
        closest_station AS (
          SELECT
            t1.id AS station_id,
            t1.name AS station_name,
            ST_DISTANCE(
              t2.my_point,
              ST_GEOGPOINT(t1.longitude, t1.latitude)
            ) / 1609.34 AS distance_miles
          FROM `bigquery-public-data.ghcn_d.ghcnd_stations` AS t1
          CROSS JOIN target_location AS t2
          ORDER BY distance_miles
          LIMIT 1
        )
        SELECT
          t1.station_name,
          t1.station_id,
          t2.date,
          t2.element,
          t2.value,
          t1.distance_miles
        FROM closest_station AS t1
        JOIN `bigquery-public-data.ghcn_d.ghcnd_{year}` AS t2
          ON t1.station_id = t2.id
        WHERE t2.element IN ({elements_str})
        ORDER BY t2.date DESC, t2.element
        LIMIT {limit};
    """

    # Execute query
    retrieval = WeatherDataRetrieval(project_id=project_id)
    results = retrieval._execute_query(query)

    if not results:
        return {
            "status": "no_data",
            "message": f"No weather station found near ({latitude}, {longitude})",
            "data": []
        }

    # Structure response
    return {
        "status": "success",
        "station_id": results[0]["station_id"],
        "station_name": results[0]["station_name"],
        "distance_miles": round(results[0]["distance_miles"], 2),
        "location": {"latitude": latitude, "longitude": longitude},
        "data": results
    }


def get_historical_weather_with_conversions(
    station_id: str,
    start_year: int,
    end_year: int,
    elements: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves historical weather data with automatic unit conversions.

    Args:
        station_id: GHCN station ID (e.g., 'USC00045860')
        start_year: Start year for data range
        end_year: End year for data range
        elements: Weather elements to retrieve (default: ["TMAX", "PRCP"])
        start_date: Optional start date filter in YYYY-MM-DD format
        end_date: Optional end date filter in YYYY-MM-DD format
        project_id: Google Cloud project ID

    Returns:
        Dictionary containing historical weather data with unit conversions

    Example:
        >>> data = get_historical_weather_with_conversions(
        ...     "USC00045860", 2019, 2024, ["TMAX", "TMIN"]
        ... )
    """
    if elements is None:
        elements = ["TMAX", "PRCP"]

    # Format elements for SQL
    elements_str = ", ".join([f"'{elem}'" for elem in elements])

    # Build date filter if provided
    date_filter = ""
    if start_date:
        date_filter += f" AND t2.date >= '{start_date}'"
    if end_date:
        date_filter += f" AND t2.date <= '{end_date}'"

    # Construct SQL query with unit conversions
    query = f"""
        SELECT
          t2.date,
          t2.element,
          t2.value / 10.0 AS value_metric,
          CASE
            WHEN t2.element IN ('TMAX', 'TMIN') THEN
              ((t2.value / 10.0) * 9.0 / 5.0) + 32
            WHEN t2.element = 'PRCP' THEN
              (t2.value / 10.0) / 25.4
            ELSE t2.value / 10.0
          END AS value_imperial,
          CASE
            WHEN t2.element IN ('TMAX', 'TMIN') THEN 'Fahrenheit'
            WHEN t2.element = 'PRCP' THEN 'inches'
            ELSE 'unknown'
          END AS unit
        FROM `bigquery-public-data.ghcn_d.ghcnd_*` AS t2
        WHERE t2._TABLE_SUFFIX BETWEEN '{start_year}' AND '{end_year}'
          AND t2.id = '{station_id}'
          AND t2.element IN ({elements_str})
          {date_filter}
        ORDER BY t2.date DESC;
    """

    # Execute query
    retrieval = WeatherDataRetrieval(project_id=project_id)
    results = retrieval._execute_query(query)

    return {
        "status": "success",
        "station_id": station_id,
        "date_range": {
            "start_year": start_year,
            "end_year": end_year,
            "start_date": start_date,
            "end_date": end_date
        },
        "elements": elements,
        "record_count": len(results),
        "data": results,
        "unit_conversions": {
            "TMAX": "degrees Fahrenheit",
            "TMIN": "degrees Fahrenheit",
            "PRCP": "inches"
        }
    }


def analyze_heat_events(
    station_id: str,
    lookback_years: int = 5,
    temperature_threshold_f: float = 95.0,
    consecutive_days: int = 3,
    current_year: Optional[int] = None,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyzes historical heat events to identify severe heat waves.

    Args:
        station_id: GHCN station ID
        lookback_years: Number of years to analyze (default: 5)
        temperature_threshold_f: Temperature threshold in Fahrenheit (default: 95)
        consecutive_days: Minimum consecutive days for heat wave (default: 3)
        current_year: Current year for lookback calculation (default: current year)
        project_id: Google Cloud project ID

    Returns:
        Dictionary containing heat event analysis

    Example:
        >>> events = analyze_heat_events("USC00045860", lookback_years=10)
        >>> print(f"Found {events['heat_events_count']} heat events")
    """
    if current_year is None:
        current_year = datetime.now().year

    start_year = current_year - lookback_years
    end_year = current_year

    # Convert Fahrenheit threshold to Celsius (stored as tenths in database)
    temp_threshold_c_tenths = ((temperature_threshold_f - 32) * 5 / 9) * 10

    # Query to get TMAX data
    query = f"""
        WITH daily_temps AS (
          SELECT
            date,
            value / 10.0 AS temp_celsius,
            ((value / 10.0) * 9.0 / 5.0) + 32 AS temp_fahrenheit
          FROM `bigquery-public-data.ghcn_d.ghcnd_*`
          WHERE _TABLE_SUFFIX BETWEEN '{start_year}' AND '{end_year}'
            AND id = '{station_id}'
            AND element = 'TMAX'
            AND value >= {temp_threshold_c_tenths}
          ORDER BY date
        )
        SELECT * FROM daily_temps;
    """

    retrieval = WeatherDataRetrieval(project_id=project_id)
    results = retrieval._execute_query(query)

    # Analyze for consecutive days
    heat_events = []
    if results:
        current_event = {"start_date": None, "end_date": None, "days": [], "max_temp": 0}

        for i, row in enumerate(results):
            current_date = row["date"]
            temp_f = row["temp_fahrenheit"]

            if current_event["start_date"] is None:
                # Start new event
                current_event = {
                    "start_date": current_date,
                    "end_date": current_date,
                    "days": [current_date],
                    "max_temp": temp_f,
                    "avg_temp": temp_f
                }
            else:
                # Check if consecutive
                prev_date = results[i-1]["date"]
                if (current_date - prev_date).days == 1:
                    # Continue event
                    current_event["end_date"] = current_date
                    current_event["days"].append(current_date)
                    current_event["max_temp"] = max(current_event["max_temp"], temp_f)
                else:
                    # End previous event if meets criteria
                    if len(current_event["days"]) >= consecutive_days:
                        temps = [r["temp_fahrenheit"] for r in results
                                if r["date"] in current_event["days"]]
                        current_event["avg_temp"] = sum(temps) / len(temps)
                        current_event["duration_days"] = len(current_event["days"])
                        heat_events.append(current_event)

                    # Start new event
                    current_event = {
                        "start_date": current_date,
                        "end_date": current_date,
                        "days": [current_date],
                        "max_temp": temp_f,
                        "avg_temp": temp_f
                    }

        # Check final event
        if current_event["start_date"] and len(current_event["days"]) >= consecutive_days:
            temps = [r["temp_fahrenheit"] for r in results
                    if r["date"] in current_event["days"]]
            current_event["avg_temp"] = sum(temps) / len(temps)
            current_event["duration_days"] = len(current_event["days"])
            heat_events.append(current_event)

    # Clean up events for JSON serialization
    for event in heat_events:
        event["start_date"] = str(event["start_date"])
        event["end_date"] = str(event["end_date"])
        event["days"] = [str(d) for d in event["days"]]
        event["max_temp"] = round(event["max_temp"], 1)
        event["avg_temp"] = round(event["avg_temp"], 1)

    return {
        "status": "success",
        "station_id": station_id,
        "analysis_period": {
            "start_year": start_year,
            "end_year": end_year,
            "lookback_years": lookback_years
        },
        "criteria": {
            "temperature_threshold_f": temperature_threshold_f,
            "consecutive_days": consecutive_days
        },
        "heat_events_count": len(heat_events),
        "heat_events": heat_events
    }


def calculate_flood_probability(
    station_id: str,
    rainfall_threshold_inches: float,
    lookback_years: int = 10,
    time_window_hours: int = 1,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculates historical probability of flash floods based on rainfall intensity.

    Args:
        station_id: GHCN station ID
        rainfall_threshold_inches: Rainfall threshold in inches
        lookback_years: Number of years to analyze (default: 10)
        time_window_hours: Time window for accumulation (default: 1)
        project_id: Google Cloud project ID

    Returns:
        Dictionary containing flood probability analysis

    Example:
        >>> prob = calculate_flood_probability("USC00045860", 3.0)
        >>> print(f"Flood probability: {prob['probability_percent']}%")
    """
    current_year = datetime.now().year
    start_year = current_year - lookback_years

    # Convert inches to tenths of mm (GHCN storage format)
    threshold_mm_tenths = rainfall_threshold_inches * 25.4 * 10

    query = f"""
        WITH rainfall_events AS (
          SELECT
            date,
            value / 10.0 AS precip_mm,
            (value / 10.0) / 25.4 AS precip_inches
          FROM `bigquery-public-data.ghcn_d.ghcnd_*`
          WHERE _TABLE_SUFFIX BETWEEN '{start_year}' AND '{current_year}'
            AND id = '{station_id}'
            AND element = 'PRCP'
        ),
        exceedances AS (
          SELECT
            date,
            precip_inches
          FROM rainfall_events
          WHERE precip_inches >= {rainfall_threshold_inches}
        )
        SELECT
          COUNT(*) AS exceedance_count,
          (SELECT COUNT(*) FROM rainfall_events) AS total_observations
        FROM exceedances;
    """

    retrieval = WeatherDataRetrieval(project_id=project_id)
    results = retrieval._execute_query(query)

    if not results or results[0]["total_observations"] == 0:
        return {
            "status": "insufficient_data",
            "message": "No precipitation data available for this station",
            "probability_percent": 0
        }

    exceedance_count = results[0]["exceedance_count"] or 0
    total_observations = results[0]["total_observations"]
    probability = (exceedance_count / total_observations) * 100

    return {
        "status": "success",
        "station_id": station_id,
        "analysis_period": {
            "start_year": start_year,
            "end_year": current_year,
            "lookback_years": lookback_years
        },
        "criteria": {
            "rainfall_threshold_inches": rainfall_threshold_inches,
            "time_window_hours": time_window_hours
        },
        "exceedance_count": exceedance_count,
        "total_observations": total_observations,
        "probability_percent": round(probability, 2),
        "interpretation": _interpret_flood_probability(probability)
    }


def _interpret_flood_probability(probability: float) -> str:
    """Helper function to interpret flood probability."""
    if probability < 1:
        return "Very low risk"
    elif probability < 5:
        return "Low risk"
    elif probability < 10:
        return "Moderate risk"
    elif probability < 20:
        return "High risk"
    else:
        return "Very high risk"


def get_census_tract_vulnerabilities(
    city_name: Optional[str] = None,
    state_code: Optional[str] = None,
    path_coordinates: Optional[List[List[float]]] = None,
    bounding_box: Optional[Dict[str, float]] = None,
    income_filter: str = "below_city_median",
    custom_income_threshold: Optional[float] = None,
    population_density_filter: str = "above_city_average",
    custom_density_threshold: Optional[float] = None,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Identifies census tracts with socioeconomic vulnerabilities in a geographic area.

    Args:
        city_name: City name for reference (optional)
        state_code: Two-letter state code (optional)
        path_coordinates: List of [longitude, latitude] pairs for storm path (optional)
        bounding_box: Dict with min_lat, max_lat, min_lon, max_lon (optional)
        income_filter: Income comparison filter
        custom_income_threshold: Custom median income threshold
        population_density_filter: Population density comparison filter
        custom_density_threshold: Custom density threshold
        project_id: Google Cloud project ID

    Returns:
        Dictionary containing vulnerable census tract information

    Example:
        >>> tracts = get_census_tract_vulnerabilities(
        ...     city_name="San Jose",
        ...     state_code="CA",
        ...     bounding_box={"min_lat": 37.2, "max_lat": 37.5,
        ...                   "min_lon": -122.2, "max_lon": -121.8}
        ... )
    """
    # This is a simplified implementation
    # Full implementation would require complex geospatial queries

    logger.warning(
        "get_census_tract_vulnerabilities is a placeholder implementation. "
        "Full census data integration requires additional configuration."
    )

    return {
        "status": "partial_implementation",
        "message": "Census tract vulnerability analysis requires additional setup",
        "parameters": {
            "city_name": city_name,
            "state_code": state_code,
            "income_filter": income_filter,
            "population_density_filter": population_density_filter
        },
        "next_steps": [
            "Configure access to bigquery-public-data.census_bureau_acs tables",
            "Set up geospatial indexing for storm path analysis",
            "Define vulnerability thresholds based on local baselines"
        ]
    }


# Export all functions
__all__ = [
    "find_closest_station_and_get_data",
    "get_historical_weather_with_conversions",
    "analyze_heat_events",
    "calculate_flood_probability",
    "get_census_tract_vulnerabilities",
]
