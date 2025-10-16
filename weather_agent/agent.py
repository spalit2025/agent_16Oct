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


import aiohttp
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


async def get_latitude_longitude(location: str):
    """Gets the latitude and longitude for a given location"""
    return 37.2882,-121.8492


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

Keep responses brief and data-focused.
"""
)

# Forecast Agent - Real-time Weather Data
forecast_agent = Agent(
    model='gemini-2.0-flash-exp',
    name='forecast_agent',
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    description='Fetches real-time weather conditions and forecasts from NWS API.',
    instruction="""You are the Forecast Agent. Use the weather tools to get current forecasts.

## YOUR TASKS
1. Use get_latitude_longitude() to get coordinates for the location
2. Use get_weather() with those coordinates to fetch the forecast
3. Extract and summarize the relevant forecast information
4. Focus on what the user asked about (rain, temperature, severe weather, etc.)

## OUTPUT FORMAT
Provide a clear, concise forecast summary focusing on the user's specific question.
Do NOT output raw JSON or overly technical data to the user.

Example: "The 7-day forecast for San Jose shows mostly sunny conditions with highs in the mid-70s. There is minimal chance of rain throughout the week (0-2% chance)."
""",
    tools=[get_weather, get_latitude_longitude],
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

# Google Search Agent - for additional web-based information
google_search_agent = Agent(
    model='gemini-2.0-flash-exp',
    name='google_search_agent',
    description='Searches the web for additional information when needed.',
    instruction="""You are the Google Search Agent. Only provide additional information if:
- The previous agents couldn't answer the question
- Additional context is specifically requested
- Current information needs web verification

Otherwise, respond with: "No additional information needed."

Use the google_search tool only when necessary.
""",
    tools=[google_search],
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
)

# Root Agent - Sequential Coordinator
root_agent = SequentialAgent(
    name="root_agent",
    sub_agents=[
        query_parser_agent,
        data_agent,
        forecast_agent,
        insights_agent,
        google_search_agent
    ],
    description="You are a helpful assistant. Weather Readiness Multi-Agent System: Coordinates query parsing, data retrieval, forecast analysis, and actionable insights generation for community decision-makers facing weather threats. Don't return intermediate response."
)
