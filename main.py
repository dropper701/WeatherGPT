from functools import lru_cache
import os
import re
import json
import requests
import time

from dotenv import load_dotenv
from groq import Groq

from pydantic import BaseModel
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


# =========================================
# ENVIRONMENT
# =========================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing.")

client = Groq(api_key=GROQ_API_KEY)

MODEL = "groq/compound-mini"


# =========================================
# FASTAPI
# =========================================

app = FastAPI()

allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

FRONTEND_URL = os.getenv("FRONTEND_URL")

if FRONTEND_URL:
    allowed_origins.append(FRONTEND_URL.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================
# STATIC + TEMPLATES
# =========================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

templates = Jinja2Templates(directory="templates")


# =========================================
# WEATHER CONDITIONS
# =========================================

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





# -----------------------------
# WEATHER CACHE
# -----------------------------
weather_cache = {}
forecast_cache = {}

WEATHER_CACHE_SECONDS = 300
FORECAST_CACHE_SECONDS = 1800


# -----------------------------
# LOCATION
# -----------------------------
@lru_cache(maxsize=100)
def get_location(city: str):
    city = city.strip()

    url = "https://geocoding-api.open-meteo.com/v1/search"

    try:
        response = requests.get(
            url,
            params={
                "name": city,
                "count": 5,
                "language": "en",
                "format": "json"
            },
            timeout=10
        )

        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        if not results:
            print("LOCATION NOT FOUND:", city)
            return None

        # Prefer an actual city/town result
        for result in results:
            if result.get("name", "").lower() == city.lower():
                return {
                    "name": result.get("name"),
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                    "country": result.get("country", "")
                }

        # Otherwise use the first result
        result = results[0]

        return {
            "name": result.get("name"),
            "latitude": result.get("latitude"),
            "longitude": result.get("longitude"),
            "country": result.get("country", "")
        }

    except requests.RequestException as e:
        print("GEOCODING ERROR:", e)
        return None

    except Exception as e:
        print("LOCATION ERROR:", e)
        return None
# =========================================
# CURRENT WEATHER
# =========================================


def get_weather(city: str):

    city_key = city.strip().lower()

    # Check cache
    cached = weather_cache.get(city_key)

    if cached:

        cached_time, cached_result = cached

        if time.time() - cached_time < WEATHER_CACHE_SECONDS:
            print("Using cached weather for:", city_key)
            return cached_result

    location = get_location(city_key)

    if not location:
        return {
            "reply": f"❌ I couldn't find the city '{city}'."
        }

    url = "https://api.open-meteo.com/v1/forecast"

    try:

        response = requests.get(
            url,
            params={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "timezone": "auto"
            },
            timeout=15
        )

        # Handle rate limit
        if response.status_code == 429:

            print("OPEN-METEO WEATHER RATE LIMIT")

            return {
                "reply": (
                    "⚠️ The weather service is temporarily busy. "
                    "Please wait a little and try again."
                )
            }

        response.raise_for_status()

        data = response.json()

        current = data.get("current")

        if not current:

            print("OPEN-METEO WEATHER RESPONSE:", data)

            return {
                "reply": (
                    "⚠️ Current weather data is "
                    "unavailable right now."
                )
            }

        weather_code = current.get(
            "weather_code",
            -1
        )

        icon, condition = weather_condition.get(
            weather_code,
            ("🌦️", "Unknown weather")
        )

        temperature = current.get(
            "temperature_2m",
            "N/A"
        )

        humidity = current.get(
            "relative_humidity_2m",
            "N/A"
        )

        wind = current.get(
            "wind_speed_10m",
            "N/A"
        )

        result = {
            "type": "weather",
            "city": location["name"],
            "country": location.get("country", ""),
            "temperature": temperature,
            "humidity": humidity,
            "wind": wind,
            "condition": condition,
            "icon": icon
        }

        # Save result in cache
        weather_cache[city_key] = (
            time.time(),
            result
        )

        return result

    except requests.RequestException as e:

        print("WEATHER REQUEST ERROR:", e)

        return {
            "reply": (
                "⚠️ I couldn't connect to the "
                "weather service right now."
            )
        }

    except (KeyError, ValueError, TypeError) as e:

        print("WEATHER DATA ERROR:", e)

        return {
            "reply": (
                "⚠️ The weather service returned "
                "unexpected data."
            )
        }


# =========================================
# TOMORROW WEATHER
# =========================================

def get_forecast(city: str):
    city_key = city.strip().lower()

    cache_key = f"tomorrow:{city_key}"

    cached = forecast_cache.get(cache_key)

    if cached:
        cached_time, cached_result = cached

        if time.time() - cached_time < FORECAST_CACHE_SECONDS:
            print("Using cached tomorrow forecast for:", city_key)
            return cached_result

    location = get_location(city_key)

    if not location:
        return {
            "type": "error",
            "reply": f"❌ I couldn't find the city '{city}'."
        }

    url = "https://api.open-meteo.com/v1/forecast"

    try:
        response = requests.get(
            url,
            params={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "daily": (
                    "temperature_2m_max,"
                    "temperature_2m_min,"
                    "precipitation_probability_max,"
                    "weather_code"
                ),
                "forecast_days": 2,
                "timezone": "auto"
            },
            timeout=15
        )

        if response.status_code == 429:
            print("OPEN-METEO FORECAST RATE LIMIT")

            return {
                "type": "error",
                "reply": (
                    "⚠️ The weather service is temporarily busy. "
                    "Please try again later."
                )
            }

        response.raise_for_status()

        data = response.json()
        daily = data.get("daily")

        if not daily:
            return {
                "type": "error",
                "reply": "⚠️ Tomorrow's forecast is unavailable right now."
            }

        weather_code = daily["weather_code"][1]

        icon, condition = weather_condition.get(
            weather_code,
            ("🌦️", "Unknown weather")
        )

        result = {
            "type": "tomorrow",
            "city": location["name"],
            "country": location.get("country", ""),
            "temperature_max": daily["temperature_2m_max"][1],
            "temperature_min": daily["temperature_2m_min"][1],
            "rain_probability": daily["precipitation_probability_max"][1],
            "condition": condition,
            "icon": icon
        }

        forecast_cache[cache_key] = (
            time.time(),
            result
        )

        return result

    except requests.RequestException as e:
        print("FORECAST REQUEST ERROR:", e)

        return {
            "type": "error",
            "reply": "⚠️ I couldn't connect to the weather service right now."
        }

    except (
        KeyError,
        ValueError,
        TypeError,
        IndexError
    ) as e:
        print("FORECAST DATA ERROR:", e)

        return {
            "type": "error",
            "reply": "⚠️ Tomorrow's forecast is unavailable right now."
        }

# =========================================
# 7 DAY FORECAST
# =========================================

def get_7day_forecast(city: str):
    city_key = city.strip().lower()

    cache_key = f"7day:{city_key}"

    cached = forecast_cache.get(cache_key)

    if cached:
        cached_time, cached_result = cached

        if time.time() - cached_time < FORECAST_CACHE_SECONDS:
            print("Using cached 7-day forecast for:", city_key)
            return cached_result

    location = get_location(city_key)

    if not location:
        return {
            "type": "error",
            "reply": f"❌ I couldn't find the city '{city}'."
        }

    url = "https://api.open-meteo.com/v1/forecast"

    try:
        response = requests.get(
            url,
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
            timeout=15
        )

        if response.status_code == 429:
            print("OPEN-METEO 7-DAY RATE LIMIT")

            return {
                "type": "error",
                "reply": (
                    "⚠️ The weather service is temporarily busy. "
                    "Please try again later."
                )
            }

        response.raise_for_status()

        data = response.json()
        daily = data.get("daily")

        if not daily:
            return {
                "type": "error",
                "reply": "⚠️ The 7-day forecast is unavailable right now."
            }

        forecast = []

        days = len(daily["time"])

        for i in range(min(7, days)):

            weather_code = daily["weather_code"][i]

            icon, condition = weather_condition.get(
                weather_code,
                ("🌦️", "Unknown weather")
            )

            forecast.append({
                "date": daily["time"][i],
                "icon": icon,
                "condition": condition,
                "min_temp": daily["temperature_2m_min"][i],
                "max_temp": daily["temperature_2m_max"][i],
                "rain_probability": daily[
                    "precipitation_probability_max"
                ][i]
            })

        result = {
            "type": "seven_day",
            "city": location["name"],
            "country": location.get("country", ""),
            "forecast": forecast
        }

        forecast_cache[cache_key] = (
            time.time(),
            result
        )

        return result

    except requests.RequestException as e:
        print("7-DAY REQUEST ERROR:", e)

        return {
            "type": "error",
            "reply": "⚠️ I couldn't connect to the weather service right now."
        }

    except (
        KeyError,
        ValueError,
        TypeError,
        IndexError
    ) as e:
        print("7-DAY DATA ERROR:", e)

        return {
            "type": "error",
            "reply": "⚠️ The 7-day forecast is unavailable right now."
        }

# =========================================
# AI WEATHER REQUEST UNDERSTANDING
# =========================================

def understand_weather_request(message: str):

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """
You are the weather request analyzer for WeatherGPT.

Determine whether the user's message is asking about weather.

Return ONLY valid JSON in this exact format:

{
    "is_weather": true,
    "city": "Toronto",
    "type": "current"
}

Rules:

- The city can be any city, town, or location.
- Never assume a fixed city.
- "current" means current weather or today.
- "tomorrow" means tomorrow.
- "seven_day" means weekly, 7 day, seven day, or this week.

If the user asks about weather but gives no city:

{
    "is_weather": true,
    "city": null,
    "type": "current"
}

If the user is not asking about weather:

{
    "is_weather": false,
    "city": null,
    "type": "current"
}

Do not answer the user.
Return JSON only.
"""
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            temperature=0,
            max_completion_tokens=150
        )

        content = response.choices[0].message.content.strip()

        content = re.sub(r"```json\s*", "", content)
        content = re.sub(r"```\s*", "", content)

        return json.loads(content)

    except Exception as e:

        print(
            "WEATHER UNDERSTANDING ERROR:",
            type(e).__name__,
            str(e)
        )

        return {
            "is_weather": False,
            "city": None,
            "type": "current"
        }


# =========================================
# AUTO LOCATION WEATHER
# =========================================


location_weather_cache = {}

LOCATION_WEATHER_CACHE_SECONDS = 600


@app.get("/location-weather")
def location_weather(latitude: float, longitude: float):

    # Round coordinates so tiny GPS changes do not create
    # a completely different cache entry.
    lat_key = round(latitude, 2)
    lon_key = round(longitude, 2)

    cache_key = f"{lat_key},{lon_key}"

    # -----------------------------------------
    # CHECK CACHE
    # -----------------------------------------

    cached = location_weather_cache.get(cache_key)

    if cached:
        cached_time, cached_result = cached

        if time.time() - cached_time < LOCATION_WEATHER_CACHE_SECONDS:
            print(
                "Using cached location weather:",
                cache_key
            )

            return cached_result

    try:

        # -----------------------------------------
        # REVERSE GEOCODING
        # -----------------------------------------

        reverse_url = (
            "https://api.bigdatacloud.net/data/"
            "reverse-geocode-client"
        )

        reverse_response = requests.get(
            reverse_url,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "localityLanguage": "en"
            },
            timeout=10
        )

        reverse_response.raise_for_status()

        location_data = reverse_response.json()

        city = (
            location_data.get("city")
            or location_data.get("locality")
            or location_data.get("principalSubdivision")
            or "Your Location"
        )

        country = location_data.get(
            "countryName",
            ""
        )

        print("AUTO DETECTED CITY:", city)

        # -----------------------------------------
        # WEATHER USING EXACT GPS COORDINATES
        # -----------------------------------------

        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
        )

        weather_response = requests.get(
            weather_url,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "wind_speed_10m,"
                    "weather_code"
                ),
                "timezone": "auto"
            },
            timeout=15
        )

        # -----------------------------------------
        # HANDLE RATE LIMIT
        # -----------------------------------------

        if weather_response.status_code == 429:

            print("OPEN-METEO AUTO LOCATION RATE LIMIT")

            # Use previous cached data if available
            if cached:
                print(
                    "Returning stale cached location weather:",
                    cache_key
                )

                return cached[1]

            return {
                "type": "error",
                "reply": (
                    "⚠️ The weather service is temporarily busy. "
                    "Please try again in a few minutes."
                )
            }

        weather_response.raise_for_status()

        data = weather_response.json()

        current = data.get("current")

        if not current:
            return {
                "type": "error",
                "reply": (
                    "⚠️ Current weather data is "
                    "unavailable right now."
                )
            }

        # -----------------------------------------
        # WEATHER CONDITION
        # -----------------------------------------

        weather_code = current.get(
            "weather_code",
            -1
        )

        icon, condition = weather_condition.get(
            weather_code,
            ("🌦️", "Unknown weather")
        )

        result = {
            "type": "weather",
            "city": city,
            "country": country,
            "temperature": current.get(
                "temperature_2m",
                "N/A"
            ),
            "humidity": current.get(
                "relative_humidity_2m",
                "N/A"
            ),
            "wind": current.get(
                "wind_speed_10m",
                "N/A"
            ),
            "condition": condition,
            "icon": icon
        }

        # -----------------------------------------
        # SAVE RESULT TO CACHE
        # -----------------------------------------

        location_weather_cache[cache_key] = (
            time.time(),
            result
        )

        print(
            "Fresh location weather:",
            cache_key
        )

        return result

    except requests.RequestException as e:

        print(
            "AUTO LOCATION REQUEST ERROR:",
            e
        )

        # Return old cached result if available
        if cached:
            print(
                "Returning stale cached weather:",
                cache_key
            )

            return cached[1]

        return {
            "type": "error",
            "reply": (
                "⚠️ Unable to connect to "
                "the location or weather service."
            )
        }

    except (KeyError, ValueError, TypeError) as e:

        print(
            "AUTO LOCATION DATA ERROR:",
            e
        )

        # Return old cached result if available
        if cached:
            return cached[1]

        return {
            "type": "error",
            "reply": (
                "⚠️ Invalid weather data was returned."
            )
        }
# =========================================
# GROQ GENERAL CHAT
# =========================================


def ask_ai(message: str):

    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are WeatherGPT, a helpful and friendly AI assistant. "
                        "Answer general questions clearly and naturally. "
                        "Do not make up live weather information. "
                        "Keep answers reasonably concise."
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

        content = response.choices[0].message.content

        if not content:
            return "⚠️ I couldn't generate a response."

        return content

    except Exception as e:

        print("GROQ ERROR:", type(e).__name__, str(e))

        return (
            "⚠️ The AI service is temporarily unavailable. "
            "Please try again in a moment."
        )


# =========================================
# CHAT API
# =========================================

class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
def chat(request: ChatRequest):

    user_message = request.message.strip()

    if not user_message:
        return {
            "reply": "Please enter a message."
        }

    text = user_message.lower()

    # -------------------------------------
    # GREETINGS - NO AI REQUEST
    # -------------------------------------

    greetings = [
        "hi",
        "hello",
        "hey",
        "hii",
        "hiii",
        "good morning",
        "good afternoon",
        "good evening"
    ]

    if text in greetings:

        return {
            "reply": (
                "Hello! 👋 I'm WeatherGPT 🌦️\n"
                "Ask me about the weather in any city."
            )
        }

    # -------------------------------------
    # WEATHER REQUEST
    # -------------------------------------

    weather_request = understand_weather_request(user_message)

    if weather_request.get("is_weather"):

        request_type = weather_request.get("type", "current")
        city = weather_request.get("city")

        if not city:
            return {
                "reply": "🌍 Which city would you like the weather for?"
            }

        if request_type == "current":
            return get_weather(city)

        if request_type == "tomorrow":
            return get_forecast(city)

        if request_type == "seven_day":
            return get_7day_forecast(city)

    # -------------------------------------
    # GENERAL AI QUESTION
    # -------------------------------------

    return {
        "reply": ask_ai(user_message)
    }


# =========================================
# GROQ TEST
# =========================================

@app.get("/groq-test")
def groq_test():

    return {
        "reply": ask_ai(
            "Say hello to WeatherGPT in one short sentence."
        )
    }


# =========================================
# HEALTH CHECK
# =========================================

@app.get("/health")
def health():
    return {
        "status": "ok"
    }


# =========================================
# REACT FRONTEND
# =========================================

if os.path.exists("frontend/dist"):
    app.mount(
        "/",
        StaticFiles(
            directory="frontend/dist",
            html=True
        ),
        name="frontend"
    )

