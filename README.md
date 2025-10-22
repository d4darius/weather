# MCP server for travel planning

This document is based on the tutorial showcased on the official MCP page about building an MCP server and expands it by using the weather information to plan flights
- The link to the official repo is the following: https://github.com/modelcontextprotocol/quickstart-resources/tree/main/weather-server-python

# Initial Considerations

### Logging

It is important to denote, that on **STDIO MCP servers** (local servers) we must avoid logging to stdio, otherwise we will corrupt the output.

- No `print("hello")` in the code.

We can instead use a logging library to write to files or stderr.

### Tool Names

They must follow certain specifications.

- Tool names SHOULD be between 1 and 128 characters in length (inclusive).
- Tool names SHOULD be considered case-sensitive.
- The following SHOULD be the only allowed characters: uppercase and lowercase ASCII letters (A-Z, a-z), digits (0-9), underscore (\_), dash (-), and dot (.)
- Tool names SHOULD NOT contain spaces, commas, or other special characters.
- Tool names SHOULD be unique within a server.
- Example valid tool names:
  - getUser
  - DATA_EXPORT_v2
  - admin.tools.list

### System Specifications

- Python 3.10 or higher installed.
- You must use the Python MCP SDK 1.2.0 or higher.

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
LOCAL = True

# Initialize FastMCP server
if LOCAL:
    mcp = FastMCP("weather")
else:
    port = os.environ.get("PORT", 10000)
    mcp = FastMCP("weather", host="0.0.0.0", port=port)mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
OPENMETEO_API_BASE = "https://api.open-meteo.com/v1"
IPLOC_API_BASE = "http://ip-api.com/json/"
GOOGLEFL_API_BASE = "https://serpapi.com/search?engine=google_flights"
USER_AGENT = "weather-app/1.0"
TODAY_DATE = "2025-10-21"
```

The FastMCP class uses Python type hints and docstrings to automatically generate tool definitions, making it easy to create and maintain MCP tools.

- LOCAL is a constant that controls whether the server is running locally or on a remote server

## Helper functions

We then add helper functions to query and format the data from the National Weather Service API.

### `make_geocode_request`

Performs geocoding via the Nominatim (OpenStreetMap) search API to convert a free-form place name into geographic coordinates and a display name. Used by tools that accept human location strings so they can resolve a place into lat/lon for downstream weather queries.

### `make_nws_request`

Centralized requester for National Weather Service endpoints. Handles HTTP calls to NWS (with appropriate headers and timeouts) and provides a single place to manage NWS-related network/error handling for other tools (points, forecasts, alerts).

### `format_alert`

Converts a raw NWS alert feature into a compact, human-readable text block summarizing the important fields (event, affected area, severity, description, instructions). Used to present alerts returned by the alerts tool in a readable format.

### `make_openmeteo_request`

Fallback weather fetcher that queries the Open-Meteo API for current conditions and short-range forecasts. Used when NWS data is unavailable or when a non-NWS provider is preferred; centralizes the Open-Meteo query parameters and network handling.

### `format_openmeteo_forecast`

Transforms Open-Meteo response payloads into a concise, readable forecast summary (current conditions plus the next few days). Used to present the Open-Meteo fallback data in the same human-friendly format as the primary forecast output.

### `make_iploc_request`

Fetches the current city of the user based on their IP address using the ip-api service. This function acts as a fallback mechanism to determine the user's location when no explicit input is provided. It handles network errors gracefully and ensures a default value is returned if the location cannot be resolved.

## Tool Execution Logic

The tool execution logic is responsible for actually executing the logic of each tool.

### `geocode_city`

Resolves a human-readable place name into geographic coordinates using the Nominatim helper. Serves as a small convenience tool so clients can convert a place string to lat/lon without handling geocoding details themselves. It centralizes retries/fallbacks for geocoding failures and returns a user-friendly error when the place cannot be resolved.

### `get_alerts`

Queries the National Weather Service alerts feed for a given US state, uses the centralized NWS requester, and formats each alert using the alert formatter. Presents a consolidated, human-readable block of active alerts (or a short status message when none are present). Encapsulates the logic of checking API presence/structure and transforming raw GeoJSON alert features into readable text.

### `get_forecast`

Primary forecast tool: resolves the appropriate NWS endpoints for a pair of coordinates (via the NWS "points" API), fetches the detailed forecast, and formats the next few forecast periods into readable text. If the NWS path fails, it falls back to querying Open-Meteo and formatting that response instead. This tool encapsulates provider selection (NWS first, Open-Meteo fallback), error handling, and presentation formatting so clients always receive a friendly forecast string.

### `get_current_location`

Determines the user's current city based on their IP address using the ip-api service. This tool acts as a convenience method to fetch the user's location without requiring manual input. It ensures graceful handling of errors and provides a default value if the location cannot be resolved.

### `get_flights`

Fetches a list of flights between two airports based on their IATA codes. This tool queries the Google Flights API to retrieve flight details, including departure time, duration, and price. It sorts the flights by departure time and formats the results into a human-readable list. Handles API errors gracefully and ensures a user-friendly output.

# Running the Server

We then initialize and Run the Server

```python
def main():
    # Initialize and run the server
    if LOCAL:
        mcp.run(transport='stdio')
    else:
        mcp.run(transport='streamable-http')

if __name__ == "__main__":
    main()
```

To actually run the server we must launch

```bash
uv run weather.py --local
```

# Testing with Claude Client

Using Claude for desktop, we can insert our local server in the configuration file (`claude_desktop_config.json`).

```json
{
  "mcpServers": {
    "weather": {
      "command": "/Library/Frameworks/Python.framework/Versions/3.12/bin/uv",
      "args": [
        "--directory",
        "/Path/to/Parent/Directory/weather",
        "run",
        "weather.py",
        "--local"
      ]
    }
  }
}
```

**Be Careful**: sometimes the uv command gives errors and is thus necessary to specify the full path to the command key.

This tells Claude that there exists a server called **weather** and that to call it we simply run

- the `--local` argument is passed as a boolean flag to tell the server to run locally, by omitting it we are actually running the server in remote configuration

```bash
uv -directory /Path/to/Parent/Directory/weather run weather.py
```

### Testing Prompt Example

Suppose that we want to use the host application to travel to Barcelona. We can start by inputting a system prompt like this one:

```text
Suppose that you are a travel assistant that wants to help me book a flight to my destination holiday. Your workflow is the following:
- Check that my destination weather is pleasing -> not rainy, not too cold or not too hot (temperature between 20 and 25°C)
- If the weather is not pleasing propose an alternative destination similar to the one provided, otherwise continue
- Provide the list of flight from the user's current location nearest airport and the airport closest to the destination

Please follow the workflow and help me with the task
```

The Host will ask us about where we would like to go, then check for the weather and based on that will then provide a list of potential flights:

```text
Here are the available flights from Nice Côte d'Azur Airport (NCE) to Barcelona (BCN):

Vueling VY 1520

Departure Time: 2025-10-21 23:45
Duration: 85 minutes
Price: 47 EUR

ITA AZ 355

Departure Time: 2025-10-21 19:25
Duration: 230 minutes
Price: 218 EUR

SWISS LX 569

Departure Time: 2025-10-21 15:05
Duration: 245 minutes
Price: 310 EUR
...
```

# APIs Used

This project leverages several APIs to provide weather and travel-related functionalities:

- **Nominatim (OpenStreetMap)**: Used for geocoding, converting place names into geographic coordinates.
- **National Weather Service (NWS)**: Provides detailed weather forecasts and alerts for the United States.
- **Open-Meteo**: Acts as a fallback weather provider, offering current conditions and short-range forecasts globally.
- **ip-api**: Determines the user's current location based on their IP address.
- **Google Flights API (via SERPAPI)**: Fetches flight details, including departure times, durations, and prices, between specified airports.

