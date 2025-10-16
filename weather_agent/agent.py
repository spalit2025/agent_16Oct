from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent

weather_agent_sequential = Agent(
    model='gemini-2.5-flash',
    name='weather_agent_sequential',
    description='A helpful assistant for user questions.',
    instruction="answer the user's question",
)

root_agent = SequentialAgent(
    name="root_agent",
    sub_agents=[weather_agent_sequential],
    description="Just pass the workflow to sequential",
)



