import os
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, \
                    StdioServerParameters, StdioConnectionParams

# IMPORTANT: Replace this with the ABSOLUTE path to your adk_server.py script
PATH_TO_YOUR_MCP_SERVER_SCRIPT = "/path/to/your/adk_server.py"

if PATH_TO_YOUR_MCP_SERVER_SCRIPT == "None":
    print("WARNING: PATH_TO_YOUR_MCP_SERVER_SCRIPT is not set. Please update it in agent.py.")
    # Optionally, raise an error if the path is critical

root_agent = LlmAgent(
    model=os.getenv("MODEL"),
    name='web_reader_mcp_client_agent',
    instruction="Use the 'load_web_page' tool to fetch content from a URL provided by the user.",
    ## Add the MCPToolset below:
    tools=[
    MCPToolset(
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
    )
],

)