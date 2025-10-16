from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent
from google.adk.tools.google_search_tool import google_search

weather_agent_sequential = Agent(
    model='gemini-2.5-flash',
    name='weather_agent_sequential',
    description='A helpful assistant for user questions.',
    instruction="answer the user's question",
)

google_search_agent = Agent(
    model='gemini-2.5-flash',
    name='google_search_agent',
    description='A helpful assistant for user questions that require searching the web.',
    instruction="answer the user's question using the google search tool",
    tools=[google_search],
)

root_agent = SequentialAgent(
    name="root_agent",
    sub_agents=[weather_agent_sequential, google_search_agent],
    description="Just pass the workflow to sequential",
)
