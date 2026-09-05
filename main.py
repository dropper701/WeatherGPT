import os
import re
import json
import requests

from dotenv import load_dotenv
from groq import Groq

from typing import Literal

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel


# ==============================
# LOAD ENVIRONMENT VARIABLES
# ==============================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing from .env file")


# ==============================
# GROQ CLIENT
# ==============================

client = Groq(
    api_key=GROQ_API_KEY
)


# ==============================
# CHANGE THIS MODEL LATER
# ==============================
MODEL = "groq/compound-mini"

# ==============================
# FASTAPI APP
# ==============================

app = FastAPI()


# ==============================
# STATIC FILES
# ==============================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


# ==============================
# TEMPLATES
# ==============================

templates = Jinja2Templates(directory="templates")


# ==============================
# WEATHER INTENT MODEL
# ==============================

class WeatherIntent(BaseModel):

    intent: Literal[
        "current_weather",
        "tomorrow_weather",
        "seven_day_forecast",
        "unknown"
    ]

    city: str


# ==============================
# CHAT REQUEST MODEL
# ==============================

class ChatRequest(BaseModel):

    message: str


# ==============================
# WEATHER CONDITIONS
# ==============================

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

    75: ("❄️", "Heavy snow"),

    80: ("🌦️", "Rain showers"),

    81: ("🌧️", "Moderate rain showers"),

    82: ("⛈️", "Heavy rain showers"),

    95: ("⛈️", "Thunderstorm"),

    96: ("⛈️", "Thunderstorm with hail"),

    99: ("⛈️", "Severe thunderstorm with hail"),
}


# ==============================
# LIST AVAILABLE GROQ MODELS
# ==============================

@app.get("/models")
def list_models():

    try:

        models = client.models.list()

        return {
            "models": [
                model.id
                for model in models.data
            ]
        }

    except Exception as e:

        return {
            "error": str(e)
        }


# ==============================
# ASK AI
# ==============================

def ask_ai(message: str):

    try:

        response = client.chat.completions.create(

            model=MODEL,

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are WeatherGPT, a helpful AI assistant."
                    )
                },
                {
                    "role": "user",
                    "content": message
                }
            ],

            temperature=0.7,

            max_completion_tokens=500
        )

        return response.choices[0].message.content

    except Exception as e:

        print("\n========== GROQ ERROR ==========")
        print(type(e).__name__)
        print(str(e))
        print("================================\n")

        return f"ERROR: {str(e)}"


# ==============================
# UNDERSTAND WEATHER QUERY
# ==============================

def understand_weather_query(message: str):

    prompt = f"""
You are an intent detector for WeatherGPT.

Classify the user's message into EXACTLY one of these intents:

current_weather
tomorrow_weather
seven_day_forecast
unknown

Also identify the city mentioned by the user.

Return ONLY valid JSON.

Example:

{{
    "intent": "current_weather",
    "city": "Mumbai"
}}

If no city is mentioned, return:

{{
    "intent": "unknown",
    "city": ""
}}

User message:

{message}
"""

    try:

        response = client.chat.completions.create(

            model=MODEL,

            messages=[
                {
                    "role": "system",
                    "content": "You only return valid JSON."
                },

                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0,

            max_completion_tokens=200
        )

        result = response.choices[0].message.content

        # Remove markdown formatting if AI adds it

        result = result.replace("```json", "")
        result = result.replace("```", "")
        result = result.strip()

        return json.loads(result)

    except Exception as e:

        print("INTENT ERROR:", str(e))

        return {
            "intent": "unknown",
            "city": ""
        }


# ==============================
# HOME PAGE
# ==============================

@app.get("/")
def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


# ==============================
# CHAT API
# ==============================

@app.post("/chat")
def chat(request: ChatRequest):

    user_message = request.message.strip()

    if not user_message:

        return {
            "reply": "Please enter a message."
        }


    # Ask AI what the user wants

    data = understand_weather_query(user_message)

    intent = data.get("intent", "unknown")

    city = data.get("city", "").strip()


    print("Intent:", intent)
    print("City:", city)


    # CURRENT WEATHER

    if intent == "current_weather" and city:

        return get_weather(city)


    # TOMORROW WEATHER

    elif intent == "tomorrow_weather" and city:

        return get_forecast(city)


    # 7 DAY FORECAST

    elif intent == "seven_day_forecast" and city:

        return get_7day_forecast(city)


    # NORMAL AI CHAT

    else:

        return {
            "reply": ask_ai(user_message)
        }


# ==============================
# GET LOCATION
# ==============================

def get_location(city: str):

    geocoding_url = (
        "https://geocoding-api.open-meteo.com/v1/search"
    )

    try:

        response = requests.get(

            geocoding_url,

            params={
                "name": city,
                "count": 1
            },

            timeout=10
        )

        geo_data = response.json()


        if "results" not in geo_data:

            return None


        result = geo_data["results"][0]


        return {

            "latitude": result["latitude"],

            "longitude": result["longitude"],

            "name": result["name"]
        }

    except Exception as e:

        print("LOCATION ERROR:", str(e))

        return None


# ==============================
# CURRENT WEATHER
# ==============================

def get_weather(city: str):

    location = get_location(city)


    if not location:

        return {
            "reply": "❌ Sorry, I couldn't find that city."
        }


    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
    )


    try:

        response = requests.get(

            weather_url,

            params={

                "latitude": location["latitude"],

                "longitude": location["longitude"],

                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "wind_speed_10m,"
                    "weather_code"
                ),

                "timezone": "auto"
            },

            timeout=10
        )


        weather_data = response.json()

        current = weather_data["current"]

        weather_code = current["weather_code"]


        icon, condition = weather_condition.get(

            weather_code,

            ("🌦️", "Unknown weather")
        )


        return {

            "reply": (

                f"{icon} Weather in {location['name']}:\n\n"

                f"{condition}\n"

                f"🌡️ Temperature: "
                f"{current['temperature_2m']}°C\n"

                f"💧 Humidity: "
                f"{current['relative_humidity_2m']}%\n"

                f"💨 Wind Speed: "
                f"{current['wind_speed_10m']} km/h"
            )
        }


    except Exception as e:

        print("WEATHER ERROR:", str(e))

        return {
            "reply": "⚠️ Unable to get weather information right now."
        }


# ==============================
# TOMORROW FORECAST
# ==============================

def get_forecast(city: str):

    location = get_location(city)


    if not location:

        return {
            "reply": "❌ Sorry, I couldn't find that city."
        }


    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
    )


    try:

        response = requests.get(

            weather_url,

            params={

                "latitude": location["latitude"],

                "longitude": location["longitude"],

                "daily": (
                    "temperature_2m_max,"
                    "temperature_2m_min,"
                    "precipitation_probability_max,"
                    "weather_code"
                ),

                "timezone": "auto"
            },

            timeout=10
        )


        weather_data = response.json()

        daily = weather_data["daily"]


        weather_code = daily["weather_code"][1]


        icon, condition = weather_condition.get(

            weather_code,

            ("🌦️", "Unknown weather")
        )


        return {

            "reply": (

                f"{icon} Tomorrow's weather in "
                f"{location['name']}:\n\n"

                f"{condition}\n"

                f"🌡️ Maximum: "
                f"{daily['temperature_2m_max'][1]}°C\n"

                f"🌡️ Minimum: "
                f"{daily['temperature_2m_min'][1]}°C\n"

                f"🌧️ Rain probability: "
                f"{daily['precipitation_probability_max'][1]}%"
            )
        }


    except Exception as e:

        print("FORECAST ERROR:", str(e))

        return {
            "reply": "⚠️ Unable to get tomorrow's forecast."
        }


# ==============================
# 7 DAY FORECAST
# ==============================

def get_7day_forecast(city: str):

    location = get_location(city)


    if not location:

        return {
            "reply": "❌ Sorry, I couldn't find that city."
        }


    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
    )


    try:

        response = requests.get(

            weather_url,

            params={

                "latitude": location["latitude"],

                "longitude": location["longitude"],

                "daily": (
                    "weather_code,"
                    "temperature_2m_max,"
                    "temperature_2m_min,"
                    "precipitation_probability_max"
                ),

                "forecast_days": 7,

                "timezone": "auto"
            },

            timeout=10
        )


        weather_data = response.json()

        daily = weather_data["daily"]


        reply = (
            f"📅 7-Day Forecast for "
            f"{location['name']}:\n\n"
        )


        for i in range(7):

            weather_code = daily["weather_code"][i]


            icon, condition = weather_condition.get(

                weather_code,

                ("🌦️", "Unknown weather")
            )


            max_temp = daily["temperature_2m_max"][i]

            min_temp = daily["temperature_2m_min"][i]

            rain = (
                daily[
                    "precipitation_probability_max"
                ][i]
            )


            reply += (

                f"📆 {daily['time'][i]}\n"

                f"{icon} {condition}\n"

                f"🌡️ {min_temp}°C - "
                f"{max_temp}°C\n"

                f"🌧️ Rain probability: "
                f"{rain}%\n\n"
            )


        return {

            "reply": reply
        }


    except Exception as e:

        print("7 DAY ERROR:", str(e))

        return {
            "reply": "⚠️ Unable to get the 7-day forecast."
        }


# ==============================
# TEST GROQ
# ==============================

@app.get("/groq-test")
def groq_test():

    reply = ask_ai(
        "Say hello to WeatherGPT in one short sentence."
    )

    return {
        "reply": reply
    }