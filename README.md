# Basic MCP server for weather querying

This document is a report from the tutorial showcased on the official MCP page about building an MCP server.

<aside>

# Initial Considerations

### Logging

It is important to denote, that on **STDIO MCP servers** (local servers) we must avoid logging to stdio, otherwise we will corrupt the output.

- No `print("hello")` in the code.

We can instead use a logging library to write to files or stderr.

### Tool Names

They must follow certain specifications.

- Tool names SHOULD be between 1 and 128 characters in length (inclusive).
- Tool names SHOULD be considered case-sensitive.
- The following SHOULD be the only allowed characters: uppercase and lowercase ASCII letters (A-Z, a-z), digits (0-9), underscore (_), dash (-), and dot (.)
- Tool names SHOULD NOT contain spaces, commas, or other special characters.
- Tool names SHOULD be unique within a server.
- Example valid tool names:
    - getUser
    - DATA_EXPORT_v2
    - admin.tools.list

### System Specifications

- Python 3.10 or higher installed.
- You must use the Python MCP SDK 1.2.0 or higher.
</aside>

# Environment Setup

To install the dependences we need to have `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Once we have it installed, we can proceed with creating and setting up our project

```bash
# Create a new directory for our project
uv init weather
cd weather

# Create virtual environment and activate it
uv venv
source .venv/bin/activate

# Install dependencies
uv add "mcp[cli]" httpx

# Create our server file
touch weather.py
```

# MCP Implementation

We are building a MCP server that exposes mainly two tools: `get_alerts` and `get_forecast`. 

## Instance

First of all we must setup the MCP instance.

```python
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"
```

The FastMCP class uses Python type hints and docstrings to automatically generate tool definitions, making it easy to create and maintain MCP tools.

## Helper functions

We then add helper functions to query and format the data from the National Weather Service API.

```python
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""
```

## Tool Execution Logic

The tool execution logic is responsible for actually executing the logic of each tool.

```python
@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period['name']}:
Temperature: {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)
```

# Running the Server

We then initialize and Run the Server

```python
def main():
    # Initialize and run the server
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
```

To actually run the server we must launch

```bash
uv run weather.py
```

# Testing with Claude Client

Using Claude for desktop, we can insert our local server in the configuration file (`claude_desktop_config.json`).

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": [
        "--directory",
        "/Path/to/Parent/Of/weather",
        "run",
        "weather.py"
      ]
    }
  }
}
```

**Be Careful**: sometimes the uv command gives errors and is thus necessary to specify the full path to the command key.

This tells Claude that there exists a server called **weather** and that to call it we simply run

```bash
uv -directory /Users/dariogosmar/Documents/EURECOM/MCP/Testing/weather run weather.py
```
