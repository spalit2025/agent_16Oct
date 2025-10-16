{
  "tool_name": "weather_data_retrieval_system",
  "description": "Comprehensive weather data retrieval system for the Data Agent. Finds closest GHCN weather stations and retrieves historical weather data with automatic unit conversions.",
  
  "functions": [
    {
      "name": "find_closest_station_and_get_data",
      "description": "Finds the closest GHCN weather station to a target location and retrieves recent weather data. Combines station lookup with immediate data retrieval.",
      "parameters": {
        "latitude": {
          "type": "number",
          "required": true,
          "description": "Target location latitude in decimal degrees (e.g., 37.39)",
          "range": [-90, 90]
        },
        "longitude": {
          "type": "number",
          "required": true,
          "description": "Target location longitude in decimal degrees (e.g., -122.08)",
          "range": [-180, 180]
        },
        "elements": {
          "type": "array",
          "required": false,
          "default": ["TMAX", "TMIN", "PRCP"],
          "description": "Weather elements to retrieve. Common values: TMAX (max temp), TMIN (min temp), PRCP (precipitation), SNOW (snowfall), SNWD (snow depth)",
          "items": {"type": "string"}
        },
        "year": {
          "type": "integer",
          "required": false,
          "default": 2024,
          "description": "Specific year table to query (e.g., 2024). Use most recent available year."
        },
        "limit": {
          "type": "integer",
          "required": false,
          "default": 10,
          "description": "Maximum number of records to return"
        }
      },
      "sql_template": """
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
        WHERE t2.element IN ({elements})
        ORDER BY t2.date DESC, t2.element
        LIMIT {limit};
      """
    },
    
    {
      "name": "get_historical_weather_with_conversions",
      "description": "Retrieves historical weather data for a specific station across multiple years with automatic unit conversions. Use after finding station ID or when station ID is known.",
      "parameters": {
        "station_id": {
          "type": "string",
          "required": true,
          "description": "GHCN station ID (e.g., 'USC00045860'). Obtain from find_closest_station_and_get_data first."
        },
        "start_year": {
          "type": "integer",
          "required": true,
          "description": "Start year for historical data range (e.g., 2019)"
        },
        "end_year": {
          "type": "integer",
          "required": true,
          "description": "End year for historical data range (e.g., 2025)"
        },
        "elements": {
          "type": "array",
          "required": false,
          "default": ["TMAX", "PRCP"],
          "description": "Weather elements to retrieve",
          "items": {"type": "string"}
        },
        "start_date": {
          "type": "string",
          "required": false,
          "description": "Optional: Filter by start date in YYYY-MM-DD format"
        },
        "end_date": {
          "type": "string",
          "required": false,
          "description": "Optional: Filter by end date in YYYY-MM-DD format"
        }
      },
      "sql_template": """
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
          END AS value_imperial
        FROM `bigquery-public-data.ghcn_d.ghcnd_*` AS t2
        WHERE t2._TABLE_SUFFIX BETWEEN '{start_year}' AND '{end_year}'
          AND t2.id = '{station_id}'
          AND t2.element IN ({elements})
          {date_filter}
        ORDER BY t2.date DESC;
      """,
      "unit_conversions": {
        "TMAX": {
          "source": "tenths of degrees Celsius",
          "metric": "degrees Celsius",
          "imperial": "degrees Fahrenheit",
          "formula_metric": "value / 10.0",
          "formula_imperial": "((value / 10.0) * 9.0 / 5.0) + 32"
        },
        "TMIN": {
          "source": "tenths of degrees Celsius",
          "metric": "degrees Celsius",
          "imperial": "degrees Fahrenheit",
          "formula_metric": "value / 10.0",
          "formula_imperial": "((value / 10.0) * 9.0 / 5.0) + 32"
        },
        "PRCP": {
          "source": "tenths of millimeters",
          "metric": "millimeters",
          "imperial": "inches",
          "formula_metric": "value / 10.0",
          "formula_imperial": "(value / 10.0) / 25.4"
        }
      }
    },
    
    {
      "name": "analyze_heat_events",
      "description": "Analyzes historical heat events to identify severe heat waves based on temperature thresholds and duration.",
      "parameters": {
        "station_id": {
          "type": "string",
          "required": true,
          "description": "GHCN station ID"
        },
        "lookback_years": {
          "type": "integer",
          "required": false,
          "default": 5,
          "description": "Number of years to analyze (e.g., 5 for last 5 years)"
        },
        "temperature_threshold_f": {
          "type": "number",
          "required": false,
          "default": 95,
          "description": "Temperature threshold in Fahrenheit to define heat event (e.g., 95)"
        },
        "consecutive_days": {
          "type": "integer",
          "required": false,
          "default": 3,
          "description": "Number of consecutive days above threshold to qualify as heat wave (e.g., 3)"
        },
        "current_year": {
          "type": "integer",
          "required": false,
          "description": "Current year for calculating lookback period. Defaults to current year."
        }
      },
      "analysis_steps": [
        "Retrieve TMAX data for specified lookback period",
        "Convert to Fahrenheit",
        "Identify periods where TMAX >= threshold for consecutive_days or more",
        "Calculate duration and intensity (max temp, avg temp) for each event",
        "Return ranked list of historical severe heat events"
      ]
    },
    
    {
      "name": "calculate_flood_probability",
      "description": "Calculates historical probability of flash floods based on rainfall intensity thresholds.",
      "parameters": {
        "station_id": {
          "type": "string",
          "required": true,
          "description": "GHCN station ID or basin identifier"
        },
        "rainfall_threshold_inches": {
          "type": "number",
          "required": true,
          "description": "Rainfall intensity threshold in inches (e.g., 3 inches/hour)"
        },
        "lookback_years": {
          "type": "integer",
          "required": false,
          "default": 10,
          "description": "Number of years of historical data to analyze"
        },
        "time_window_hours": {
          "type": "integer",
          "required": false,
          "default": 1,
          "description": "Time window for rainfall accumulation (e.g., 1 for per-hour rate)"
        }
      },
      "analysis_steps": [
        "Retrieve PRCP data for specified period",
        "Convert to inches",
        "Count exceedances: times rainfall >= threshold within time_window",
        "Calculate probability: exceedances / total_observation_periods",
        "Return probability as percentage with confidence interval"
      ]
    },
    
    {
      "name": "get_census_tract_vulnerabilities",
      "description": "Identifies census tracts with socioeconomic vulnerabilities in a specified geographic area.",
      "parameters": {
        "city_name": {
          "type": "string",
          "required": false,
          "description": "City name for reference median income and population density"
        },
        "state_code": {
          "type": "string",
          "required": false,
          "description": "Two-letter state code (e.g., 'CA')"
        },
        "path_coordinates": {
          "type": "array",
          "required": false,
          "description": "Array of [longitude, latitude] pairs defining storm path or area of interest",
          "items": {
            "type": "array",
            "items": {"type": "number"}
          }
        },
        "bounding_box": {
          "type": "object",
          "required": false,
          "description": "Alternative to path_coordinates: rectangular area",
          "properties": {
            "min_lat": {"type": "number"},
            "max_lat": {"type": "number"},
            "min_lon": {"type": "number"},
            "max_lon": {"type": "number"}
          }
        },
        "income_filter": {
          "type": "string",
          "required": false,
          "default": "below_city_median",
          "enum": ["below_city_median", "below_state_median", "below_national_median", "custom"],
          "description": "Income comparison filter"
        },
        "custom_income_threshold": {
          "type": "number",
          "required": false,
          "description": "Custom median income threshold if income_filter is 'custom'"
        },
        "population_density_filter": {
          "type": "string",
          "required": false,
          "default": "above_city_average",
          "enum": ["above_city_average", "above_state_average", "custom"],
          "description": "Population density comparison filter"
        },
        "custom_density_threshold": {
          "type": "number",
          "required": false,
          "description": "Custom population density threshold (people per sq mile) if filter is 'custom'"
        }
      },
      "data_sources": [
        "bigquery-public-data.geo_us_boundaries.census_tracts",
        "bigquery-public-data.census_bureau_acs.* (American Community Survey)",
        "Custom storm path coordinates from Forecast Agent"
      ],
      "sql_template": """
        WITH 
        city_baseline AS (
          -- Calculate city median income and average population density
          SELECT 
            AVG(median_income) AS city_median_income,
            AVG(population_density) AS city_avg_density
          FROM `bigquery-public-data.census_bureau_acs.*`
          WHERE geo_id LIKE '{state_code}%'
            AND place_name = '{city_name}'
        ),
        storm_path AS (
          -- Create linestring or polygon from path coordinates
          SELECT ST_GEOGFROMTEXT('{path_geom}') AS path_geom
        ),
        vulnerable_tracts AS (
          SELECT 
            ct.geo_id,
            ct.tract_geom,
            acs.median_income,
            acs.population_density,
            baseline.city_median_income,
            baseline.city_avg_density
          FROM `bigquery-public-data.geo_us_boundaries.census_tracts` AS ct
          JOIN `bigquery-public-data.census_bureau_acs.*` AS acs
            ON ct.geo_id = acs.geo_id
          CROSS JOIN city_baseline AS baseline
          CROSS JOIN storm_path AS sp
          WHERE ST_INTERSECTS(ct.tract_geom, sp.path_geom)
            AND acs.median_income < baseline.city_median_income
            AND acs.population_density > baseline.city_avg_density
        )
        SELECT * FROM vulnerable_tracts;
      """
    }
  ],
  
  "usage_workflow": {
    "step_1": {
      "action": "find_closest_station_and_get_data",
      "purpose": "Initial station discovery and data preview",
      "input": "User location (lat/lon)",
      "output": "Station ID, name, distance, sample recent data"
    },
    "step_2": {
      "action": "get_historical_weather_with_conversions",
      "purpose": "Comprehensive historical data retrieval",
      "input": "Station ID from step 1, date range, elements needed",
      "output": "Full historical dataset with unit conversions"
    },
    "step_3": {
      "action": "analyze_heat_events OR calculate_flood_probability OR get_census_tract_vulnerabilities",
      "purpose": "Specialized analysis based on query type",
      "input": "Historical data and analysis parameters",
      "output": "Risk assessment, probabilities, vulnerable populations"
    }
  },
  
  "common_elements": {
    "TMAX": "Maximum temperature",
    "TMIN": "Minimum temperature",
    "PRCP": "Precipitation",
    "SNOW": "Snowfall",
    "SNWD": "Snow depth",
    "AWND": "Average wind speed",
    "WSF2": "Fastest 2-minute wind speed",
    "WT01": "Fog",
    "WT03": "Thunder",
    "WT05": "Hail"
  },
  
  "error_handling": {
    "no_station_found": "If no station found within reasonable distance (>50 miles), expand search radius or notify user",
    "missing_data": "GHCN stations may have gaps. Check data quality flags and consider multiple stations",
    "year_unavailable": "If requested year table doesn't exist, use latest available year",
    "invalid_coordinates": "Validate lat/lon are within valid ranges before querying"
  }
}