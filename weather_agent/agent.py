from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent
from google.adk.tools.google_search_tool import google_search
import json
from datetime import datetime
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest
from google.genai import types
import logging
import google.cloud.logging
cloud_logging_client = google.cloud.logging.Client()
cloud_logging_client.setup_logging()
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, \
                StdioServerParameters, StdioConnectionParams
import os
import aiohttp
google_maps_api_key = os.environ.get("GOOGLE_MAPS_API_KEY")

def log_query_to_model(callback_context: CallbackContext, llm_request: LlmRequest):
    if llm_request.contents and llm_request.contents[-1].role == 'user':
        for part in llm_request.contents[-1].parts:
            if part.text:
                logging.info("[query to %s]: %s", callback_context.agent_name, part.text)

def log_model_response(callback_context: CallbackContext, llm_response: LlmResponse):
    if llm_response.content and llm_response.content.parts:
        for part in llm_response.content.parts:
            if part.text:
                logging.info("[response from %s]: %s", callback_context.agent_name, part.text)
            elif part.function_call:
                logging.info("[function call from %s]: %s", callback_context.agent_name, part.function_call.name)


async def get_weather(latitude: float, longitude: float) -> dict:
    """Gets the weather forecast for a given latitude and longitude."""
    async with aiohttp.ClientSession() as session:
        headers = {'User-Agent': '(my-weather-app, my-email@example.com)'}
        points_url = f"https://api.weather.gov/points/{latitude},{longitude}"

        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': '(my-weather-app, my-email@example.com)'}
            points_url = f"https://api.weather.gov/points/{latitude},{longitude}"

            async with session.get(points_url, headers=headers) as points_response:
                points_response.raise_for_status()
                points_data = await points_response.json()
                forecast_url = points_data.get("properties", {}).get("forecast")

                if forecast_url:
                    async with session.get(forecast_url, headers=headers) as forecast_response:
                        forecast_response.raise_for_status()
                        return await forecast_response.json()
                return {"error": "Could not retrieve forecast URL."}

# Root Agent - Query Parser & Coordinator
query_parser_agent = Agent(
    model='gemini-2.0-flash-exp',
    name='query_parser_agent',
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    description='Parses weather readiness queries and extracts structured information including location, weather events, timeframes, and vulnerable populations.',
    instruction="""You are the Query Parser Agent. Your role is to analyze the user's query and extract structured information for downstream agents.

## CRITICAL: INTERNAL PROCESSING ONLY
- DO NOT output the JSON to the user
- Your output is ONLY for downstream agents to consume
- Simply output: "Processing your request..." and the JSON structure

## YOUR TASK
Parse the query and generate a JSON object with:
- query_id, timestamp, parsed_query (intent, confidence)
- location details (name, coordinates if known)
- weather_event (type, severity)
- temporal (timeframe_type, forecast_horizon, historical_lookback)
- vulnerable_populations (mentioned, types, require_census_data)
- infrastructure_concerns (mentioned, types)
- data_requirements (historical_data, forecast_data, census_data, geospatial_data)
- analysis_objectives (compare_historical, assess_current_risk, etc.)
- output_preferences (target_audience, urgency_level, format)

Output format:
Processing your request...
[JSON structure here - for internal use only]
=======

## OPERATIONAL PRINCIPLES

- Only use information explicitly stated in the user query
- Mark uncertain fields as null or flag for clarification
- Never invent coordinates, place_ids, or data availability
- If location is ambiguous, request clarification
- Map user descriptions to standardized NWS/NOAA event types
- Distinguish between "current conditions," "forecast," and "historical analysis"
- Automatically determine which data sources are needed based on query intent

## OUTPUT SCHEMA

Return a JSON object with this structure to the subagents:
{
  "query_id": "unique-identifier",
  "timestamp": "ISO-8601-datetime",
  "parsed_query": {
    "original_query": "user's exact question",
    "intent": "threat_assessment | preparedness_check | historical_analysis | forecast_request",
    "confidence": 0.0-1.0
  },
  "location": {
    "primary": {
      "name": "City, State, Country",
      "coordinates": {"latitude": 0.0, "longitude": 0.0},
      "administrative_levels": {
        "locality": "city-name",
        "admin_level_1": "state/province",
        "admin_level_2": "county",
        "country": "country-code"
      }
    }
  },
  "weather_event": {
    "type": "hurricane | flood | heat_wave | tornado | winter_storm | drought | wildfire | severe_thunderstorm",
    "severity_mentioned": "category/intensity if specified",
    "specific_characteristics": []
  },
  "temporal": {
    "timeframe_type": "current | forecast | historical | comparison",
    "forecast_horizon": "24h | 48h | 72h | 7days | null",
    "historical_lookback": "1year | 5years | 10years | null"
  },
  "vulnerable_populations": {
    "mentioned": boolean,
    "types": ["elderly", "children", "low-income", "disabled", "homeless", "chronic-illness"],
    "require_census_data": boolean
  },
  "infrastructure_concerns": {
    "mentioned": boolean,
    "types": ["hospitals", "schools", "shelters", "power-grid", "water-treatment", "evacuation-routes"],
    "require_mapping": boolean
  },
  "data_requirements": {
    "historical_data": {
      "needed": boolean,
      "types": []
    },
    "forecast_data": {
      "needed": boolean,
      "sources": ["NWS", "NOAA"],
      "products": []
    },
    "census_data": {
      "needed": boolean,
      "demographics": boolean
    },
    "geospatial_data": {
      "needed": boolean,
      "poi_types": []
    }
  },
  "analysis_objectives": {
    "compare_historical": boolean,
    "assess_current_risk": boolean,
    "forecast_impact": boolean,
    "identify_vulnerabilities": boolean,
    "recommend_actions": boolean
  },
  "output_preferences": {
    "target_audience": "emergency-managers | community-leaders | general-public",
    "urgency_level": "immediate | high | moderate | routine",
    "format": "executive-summary | detailed-report | alert | briefing"
  },
  "validation": {
    "location_validated": boolean,
    "weather_event_recognized": boolean,
    "sufficient_context": boolean,
    "ready_for_delegation": boolean
  }
}
Pass the relevant information to the next agent.
>>>>>>> bc05b48 (remove hardcoding)
"""
)

# Data Agent - Historical, Census, and Geospatial Data Retrieval
data_agent = Agent(
    model='gemini-2.0-flash-exp',
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    name='data_agent',
    description='Retrieves historical weather data, census demographics, and geospatial information when needed.',
    instruction="""You are the Data Agent. Your role is to provide historical weather data, census information, and geospatial data.

## CRITICAL RULES
1. Check the data_requirements from the Query Parser:
   - If historical_data.needed == false AND census_data.needed == false AND geospatial_data.needed == false, output ONLY: "No historical data required for this query."
   - Do NOT output verbose explanations or JSON structures to the user
2. If data IS needed, provide concise summaries only

## WHEN TO SKIP
- For simple forecast requests (no historical comparison needed)
- When vulnerable populations are not mentioned
- When infrastructure concerns are not mentioned

## WHEN TO PROVIDE DATA
- Historical comparisons requested
- Vulnerable population analysis needed
- Infrastructure risk assessment needed
=
Keep responses brief and data-focused.
"""
)
# Google Search Agent - for additional web-based information
google_search_agent = Agent(
    model='gemini-2.0-flash-exp',
    name='google_search_agent',
    description='A helpful assistant for user questions that require searching the web.',
    instruction="answer the user's question using the google search tool",
    tools=[google_search],
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
)

# Forecast Agent - Real-time Weather Data
forecast_agent = LlmAgent(
    model='gemini-2.0-flash-exp',
    name='forecast_agent',
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    description='Fetches real-time weather conditions, forecasts, and active warnings from NWS API.',
    instruction="""You are the Forecast Agent. Your primary role is to help with mapping, directions, and finding places. If the user asks for the weather, use the latitude and longitude from google_search_agent to get the latitude and longitude, and then delegate to the get_weather to get the forecast.

## OUTPUT FORMAT
Pass results in a structured format to the Insights Agent to synthesize.
""",
tools=[ get_weather],
    sub_agents=[google_search_agent]
)

# Insights Agent - Synthesis and Recommendations
insights_agent = Agent(
    model='gemini-2.0-flash-exp',
    name='insights_agent',
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    description='Synthesizes forecast data into a clear, actionable answer for the user.',
    instruction="""You are the Insights Agent. Your role is to provide the FINAL answer to the user's question.

## CRITICAL RULES
1. This is the FINAL response - make it clean and user-friendly
2. Answer the user's specific question directly
3. Use natural language, NOT JSON or structured formats
4. Be concise - avoid repetition from previous agents

## OUTPUT GUIDELINES

For SIMPLE QUERIES (general public, routine weather):
- Give a direct answer in 2-4 sentences
- Focus only on what the user asked
- Use plain language
- Example: "The chance of rain in San Jose next week is very low. Most days will be sunny with 0% precipitation. Only Tuesday and Wednesday have a slight 1-2% chance."

For COMPLEX QUERIES (emergency managers, threat assessment):
- Provide executive summary (2-3 sentences)
- Key threats and vulnerabilities
- Specific recommendations with timing
- Decision points

## WHAT NOT TO DO
- Do NOT repeat information from Forecast Agent verbatim
- Do NOT use "Executive Summary:" headers for simple queries
- Do NOT list all 7 days' weather unless specifically asked
- Do NOT include "Data Confidence" sections for routine queries

Read the output_preferences from Query Parser to determine response style.
"""
)

# Root Agent - Sequential Coordinator
root_agent = SequentialAgent(
    name="root_agent",
    sub_agents=[
        query_parser_agent,
        data_agent,
        forecast_agent,
        insights_agent
    ],

    
    description="You are a helpful assistant. Greet the user and then ask what they would like to know. Once you get more information related to weather, use the tools and the subagents for data retrieval, forecast analysis, and actionable insights generation for community decision-makers facing weather threats. Dont return intermediate response"
)

'''MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command='npx',
            args=[
                "-y",
                "@modelcontextprotocol/server-google-maps",
            ],
            env={
                "GOOGLE_MAPS_API_KEY": google_maps_api_key
            }
        ),
        timeout=15,
        ),
    )'''