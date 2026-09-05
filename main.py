import os
import re
import json
import requests
from dotenv import load_dotenv
from google import genai
from typing import Literal
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel


load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)


class WeatherIntent(BaseModel):
    intent: Literal[
        "current_weather",
        "tomorrow_weather",
        "seven_day_forecast",
        "unknown"
    ]
    city: str

    
def understand_weather_query(message: str):
        prompt = f"""
You are the intent detector for WeatherGPT.

Classify this user message into one of these:
current_weather
tomorrow_weather
seven_day_forecast
unknown

Also identify the city.

User message:
{message}

Return ONLY JSON like this:
{{
    "intent": "current_weather",
    "city": "Mumbai"
}}
"""

        response = client.interactions.create(
            model="gemini-3.8-flash",
            input=prompt
        )

        return response.output_text

def ask_gemini(message:str):
    prompt=f"""
You are WeatherGpt, an intelligent and helpfull AI assistant.
Rules:
- Answer general questions normally.
- Be conversational and natural.
- Explain concepts clearly.
- Do not invent factual weather information.
- Keep answers useful rather than unnecessarily long.
User:
{message}
"""
    interaction = client.interactions.create(
        model="gemini-3.8-flash",
        input=prompt
    )
    return interaction.output_text
    
app = FastAPI()
# connect the static folder()
app.mount(
    path="/static",
    app=StaticFiles(directory="static"),
    name="static",
)
# connect the template folder()
templates = Jinja2Templates(directory="templates")


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )
# Structure of the message coming from JavaScript


class ChatRequest(BaseModel):
    message: str


weather_condition = {
    0: ("☀️", "Clear sky"),
    1: ("🌤️", "Mainly clear"),
    2: ("⛅", "Partly cloudy"),
    3: ("☁️", "Overcast"),

    45: ("🌫️", "Fog"),
    48: ("🌫️", "Rime fog"),

    51: ("🌦️", "Light drizzle"),
    53: ("🌦️", "Moderate drizzle"),
    55: ("🌧️", "Heavy drizzle"),

    61: ("🌧️", "Slight rain"),
    63: ("🌧️", "Moderate rain"),
    65: ("🌧️", "Heavy rain"),

    71: ("❄️", "Slight snow"),
    73: ("❄️", "Moderate snow"),
    75: ("❄️", "Heavy snow "),

    80: ("🌦️", "Rain showers"),
    81: ("🌧️", "Moderate rain showers"),
    82: ("⛈️", "Heavy rain showers"),

    95: ("⛈️", "Thunderstorm"),
    96: ("⛈️", "Thunderstorm with hail"),
    99: ("⛈️", "Severe thunderstorm with hail"),
}


# Chat API
@app.post("/chat")
def chat(request: ChatRequest):

    user_message = request.message.lower().strip()
    gemini_result = understand_weather_query(user_message)

    data = json.loads(gemini_result)

    intent = data["intent"]
    city = data["city"]

    print("Gemini intent:", intent)
    print("Gemini city:", city)

    if intent == "current_weather":
        return get_weather(city)

    elif intent == "tomorrow_weather":
        return get_forecast(city)

    elif intent == "seven_day_forecast":
        return get_7day_forecast(city)

    else:
        return {
            "reply": ask_gemini(user_message)
        }


   

# weather api


@app.get("/weather/{city}")
def get_weather(city: str):

    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"

    geo_response = requests.get(
        geocoding_url,
        params={
            "name": city,
            "count": 1
        }
    )
    geo_data = geo_response.json()

    if "results" not in geo_data:
        return {"error": "City not found"}
    latitude = geo_data["results"][0]["latitude"]
    longitude = geo_data["results"][0]["longitude"]

    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_response = requests.get(
        weather_url,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": ("temperature_2m,"
                        "relative_humidity_2m,"
                        "wind_speed_10m",
                        "weather_code"
                        ),
            "timezone": "auto"
        }
    )

    weather_data = weather_response.json()

    current = weather_data["current"]
    weather_code = current["weather_code"]
    # get icon and description from dictionary
    icon, condition = weather_condition.get(
        weather_code,
        ("🌦️", "unknown weather")
    )

    return {

        "reply": (
        f"{icon} Weather in {city.title()}:\n"
        f"{condition}\n"
        f"🌡️ Temperature: {current['temperature_2m']}°C\n"
        f"💧 Humidity: {current['relative_humidity_2m']}%\n"
        f"💨 Wind Speed: {current['wind_speed_10m']} km/h"
    )

    }


@app.get("/forecast/{city}")
def get_forecast(city: str):

    # Find latitude and longitude
    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"

    geo_response = requests.get(
        geocoding_url,
        params={
            "name": city,
            "count": 1
        }
    )

    geo_data = geo_response.json()

    if "results" not in geo_data:
        return {
            "reply": "Sorry, I couldn't find that city."
        }

    latitude = geo_data["results"][0]["latitude"]
    longitude = geo_data["results"][0]["longitude"]

    # Get forecast data
    weather_url = "https://api.open-meteo.com/v1/forecast"

    weather_response = requests.get(
        weather_url,
        params={
            "latitude": latitude,
            "longitude": longitude,

            "daily": (
                "temperature_2m_max,"
                "temperature_2m_min,"
                "precipitation_probability_max,"
                "weather_code"
            ),

            "timezone": "auto"
        }
    )

    weather_data = weather_response.json()

    daily = weather_data["daily"]

    # [1] means tomorrow
    weather_code = daily["weather_code"][1]

    icon, condition = weather_condition.get(
        weather_code,
        ("🌦️", "Unknown weather")
    )

    return {
        "reply": (
            f"{icon} Tomorrow's weather in {city.title()}:\n"
            f"{condition}\n"
            f"🌡️ Maximum: {daily['temperature_2m_max'][1]}°C\n"
            f"🌡️ Minimum: {daily['temperature_2m_min'][1]}°C\n"
            f"🌧️ Rain probability: "
            f"{daily['precipitation_probability_max'][1]}%"
        )
    }


@app.get("/forecast7/{city}")
def get_7day_forecast(city: str):
    # Find latitude and Longitude
    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
    geo_response = requests.get(
        geocoding_url,
        params={
            "name": city,
            "count": 1
        }
    )
    geo_data = geo_response.json()
    if "results"not in geo_data:
        return {
            "reply": "Sorry, I couldn't find that city."
        }

    latitude = geo_data["results"][0]["latitude"]
    longitude = geo_data["results"][0]["longitude"]

    # Get 7-day forecast
    weather_url = "https://api.open-meteo.com/v1/forecast"

    weather_response = requests.get(
        weather_url,
        params={
            "latitude": latitude,
            "longitude": longitude,

            "daily": (
                "weather_code,"
                "temperature_2m_max,"
                "temperature_2m_min,"
                "precipitation_probability_max"
            ),

            "forecast_days": 7,
            "timezone": "auto"
        }
    )

    weather_data = weather_response.json()

    daily = weather_data["daily"]

    reply = f"📅 7-Day Forecast for {city.title()}:\n\n"

    # Loop through all 7 days
    for i in range(7):

        weather_code = daily["weather_code"][i]

        icon, condition = weather_condition.get(
            weather_code,
            ("🌦️", "Unknown weather")
        )

        max_temp = daily["temperature_2m_max"][i]
        min_temp = daily["temperature_2m_min"][i]
        rain = daily["precipitation_probability_max"][i]

        reply += (
            f"📆 {daily['time'][i]}\n"
            f"{icon} {condition}\n"
            f"🌡️ {min_temp}°C - {max_temp}°C\n"
            f"🌧️ Rain probability: {rain}%\n\n"
        )

    return {
        "reply": reply
    }


@app.get("/gemini-test")
def gemini_test():
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents="Say hello to WeatherGPT in one short sentence."
    )

    return {
        "reply": response.text
    }


@app.get("/intent-test")
def intent_test(message: str):
    result = understand_weather_query(message)

    return {
        "gemini_result":result
        
    }
