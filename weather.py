from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
import os
import argparse

args = argparse.ArgumentParser()
args.add_argument("--local", action="store_true", help="Run the server in local mode (stdio transport)")
opt = args.parse_args()

LOCAL = opt.local

# Initialize FastMCP server
if LOCAL:
    mcp = FastMCP("weather")
else:
    # The server will run on the port number specified by the environment
    # host: specifies that the server is accessible to anywhere -> listen on all network interfaces
    # port: tells which port number to bind to
    port = os.environ.get("PORT", 10000)
    mcp = FastMCP("weather", host="0.0.0.0", port=port)

# Constants
NWS_API_BASE = "https://api.weather.gov"
OPENMETEO_API_BASE = "https://api.open-meteo.com/v1"
USER_AGENT = "weather-app/1.0"

# Geocoding (Nominatim)
# API_BASE: base URL to perform geocoding information on a city (like Turin)
# USER_AGENT: necessary for the header requested by the API of the form:
#             weather-app/1.0 (contact@example.com)
#             Nominatim requests that you must identify your application with a User-Agent.
GEOCODE_API_BASE = "https://nominatim.openstreetmap.org/search"
GEOCODE_USER_AGENT = f"weather-app/1.0 ({os.environ.get('CONTACT_EMAIL', 'contact@example.com')})"

# ------------------
# HELPER FUNCTIONS
# ------------------

async def make_geocode_request(city: str) -> dict[str, Any] | None:
    """Call Nominatim to geocode a free-form location string. Returns first match or None."""
    params = {"q":city,"format":"json","limit":1}
    headers = {
        "User-Agent": USER_AGENT,
        "Accept":"application/json"
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(GEOCODE_API_BASE, params=params, headers=headers, timeout=30.0)
            # We check the status and raises an exception in case of error
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return None
            # Nominatim returns a list of matches (for a given city) -> we select the first and access the necessary fields
            item = data[0]
            return {
                "latitude": float(item["lat"]),
                "longitude": float(item["lon"]),
                "display_name": item.get("diplay_name")
            }
        except Exception:
            return None



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

async def make_openmeteo_request(lat: float, lon: float) -> dict[str, Any] | str:
    """Fetch current weather and short forecast from Open-Meteo as a fallback."""
    url = OPENMETEO_API_BASE+f"/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m&daily=temperature_2m_max,temperature_2m_min,weathercode&timezone=auto&forecast_days=3"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
        
def format_openmeteo_forecast(data: dict) -> str:
    """Format Open-Meteo data into a readable forecast string."""
    current = data.get("current_weather", {})
    daily = data.get("daily", {})

    forecast = f"""
Current Weather:
Temperature: {current.get('temperature', 'N/A')}°C
Wind: {current.get('windspeed', 'N/A')} km/h from {current.get('winddirection', 'N/A')}°
Weather Code: {current.get('weathercode', 'N/A')} (see https://open-meteo.com/en/docs for codes)

Next 3 Days Forecast:
"""
    for i in range(min(3, len(daily.get("time", [])))):
        date = daily["time"][i]
        max_temp = daily["temperature_2m_max"][i]
        min_temp = daily["temperature_2m_min"][i]
        code = daily["weathercode"][i]
        forecast += f"{date}: High {max_temp}°C, Low {min_temp}°C, Code {code}\n"
    
    return forecast

# ------------------
# TOOLS
# ------------------

# async: the task is performed in an asynchronous way: the server can start other calls in parallel
#        in this case it is used so that we can await the response of the client

# decorator: it's a function that takes as input another function or class and modifies it accordingly
@mcp.tool()
async def geocode_city(city: str) -> dict[str, Any] | str:
    """Geocode a city/place name to latitude/longitude using Nominatim.
    Returns {"latitude": float, "longitude": float, "display_name": str} or an error string.
    """
    result = await make_geocode_request(city)

    if not result:
        return "Unable to geocode the provided location."
    return result

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
    # First try using NWS_API and then use OPENWEATHER as fallback
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if points_data:
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
    # NWS failed -> fallback on openweather
    openmeteo_data = await make_openmeteo_request(latitude, longitude)

    if openmeteo_data:
        return format_openmeteo_forecast(openmeteo_data)
    return "Unable to fetch forecast data from any provider."



def main():
    # Initialize and run the server
    if LOCAL:
        mcp.run(transport='stdio')
    else:
        mcp.run(transport='streamable-http')

if __name__ == "__main__":
    main()