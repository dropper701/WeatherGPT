import os
import re
import requests
import time

from dotenv import load_dotenv
from groq import Groq

from pydantic import BaseModel
from fastapi import FastAPI, Request
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


# =========================================
# HOME PAGE
# =========================================

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


# =========================================
# HELPER: LOCATION
# =========================================
from functools import lru_cache

@lru_cache(maxsize=100)
def get_location(city: str):

    url = "https://geocoding-api.open-meteo.com/v1/search"

    try:
        response = requests.get(
            url,
            params={
                "name": city,
                "count": 1,
                "language": "en",
                "format": "json"
            },
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        results = data.get("results")

        if not results:
            return None

        result = results[0]

        return {
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "name": result["name"],
            "country": result.get("country", "")
        }

    except requests.RequestException as e:
        print("LOCATION REQUEST ERROR:", e)
        return None

    except (KeyError, ValueError, TypeError) as e:
        print("LOCATION DATA ERROR:", e)
        return None

client = Groq(api_key=GROQ_API_KEY)
MODEL = "groq/compound-mini"


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
            "reply": (
                f"{icon} Weather in "
                f"{location['name']}:\n\n"
                f"{condition}\n"
                f"🌡️ Temperature: {temperature}°C\n"
                f"💧 Humidity: {humidity}%\n"
                f"💨 Wind Speed: {wind} km/h"
            )
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

    # Check cache
    cached = forecast_cache.get(
        f"tomorrow:{city_key}"
    )

    if cached:

        cached_time, cached_result = cached

        if (
            time.time() - cached_time
            < FORECAST_CACHE_SECONDS
        ):
            print(
                "Using cached tomorrow forecast for:",
                city_key
            )

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

        # Rate limit
        if response.status_code == 429:

            print("OPEN-METEO FORECAST RATE LIMIT")

            return {
                "reply": (
                    "⚠️ The weather service is temporarily busy. "
                    "Please wait a little and try again."
                )
            }

        response.raise_for_status()

        data = response.json()

        daily = data.get("daily")

        if not daily:
            return {
                "reply": (
                    "⚠️ Tomorrow's forecast is "
                    "unavailable right now."
                )
            }

        weather_code = daily["weather_code"][1]

        icon, condition = weather_condition.get(
            weather_code,
            ("🌦️", "Unknown weather")
        )

        max_temp = daily[
            "temperature_2m_max"
        ][1]

        min_temp = daily[
            "temperature_2m_min"
        ][1]

        rain = daily[
            "precipitation_probability_max"
        ][1]

        result = {
            "reply": (
                f"{icon} Tomorrow's weather in "
                f"{location['name']}:\n\n"
                f"{condition}\n"
                f"🌡️ Maximum: {max_temp}°C\n"
                f"🌡️ Minimum: {min_temp}°C\n"
                f"🌧️ Rain probability: {rain}%"
            )
        }

        # Save result
        forecast_cache[
            f"tomorrow:{city_key}"
        ] = (
            time.time(),
            result
        )

        return result

    except requests.RequestException as e:

        print("FORECAST REQUEST ERROR:", e)

        return {
            "reply": (
                "⚠️ I couldn't connect to the "
                "weather service right now."
            )
        }

    except (
        KeyError,
        ValueError,
        TypeError,
        IndexError
    ) as e:

        print("FORECAST DATA ERROR:", e)

        return {
            "reply": (
                "⚠️ Tomorrow's forecast is "
                "unavailable right now."
            )
        }


# =========================================
# TOMORROW WEATHER
# =========================================

def get_forecast(city: str):

    location = get_location(city)

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
                "daily":"temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "forecast_days": 2,
                "timezone": "auto"
            },
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        daily = data.get("daily")

        if not daily:
            return {
                "reply": "⚠️ Tomorrow's forecast is unavailable right now."
            }

        weather_code = daily["weather_code"][1]

        icon, condition = weather_condition.get(
            weather_code,
            ("🌦️", "Unknown weather")
        )

        max_temp = daily["temperature_2m_max"][1]
        min_temp = daily["temperature_2m_min"][1]
        rain = daily["precipitation_probability_max"][1]

        return {
            "reply": (
                f"{icon} Tomorrow's weather in {location['name']}:\n\n"
                f"{condition}\n"
                f"🌡️ Maximum: {max_temp}°C\n"
                f"🌡️ Minimum: {min_temp}°C\n"
                f"🌧️ Rain probability: {rain}%"
            )
        }

    except requests.RequestException as e:
        print("FORECAST REQUEST ERROR:", e)
        return {
            "reply": "⚠️ I couldn't connect to the weather service right now."
        }

    except (KeyError, ValueError, TypeError, IndexError) as e:
        print("FORECAST DATA ERROR:", e)
        return {
            "reply": "⚠️ Tomorrow's forecast is unavailable right now."
        }


# =========================================
# 7 DAY FORECAST
# =========================================

def get_7day_forecast(city: str):

    location = get_location(city)

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
                "daily":"weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "forecast_days": 7,
                "timezone": "auto"
            },
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        daily = data.get("daily")

        if not daily:
            return {
                "reply": "⚠️ The 7-day forecast is unavailable right now."
            }

        reply = (
            f"📅 7-Day Forecast for {location['name']}:\n\n"
        )

        days = len(daily["time"])

        for i in range(min(7, days)):

            weather_code = daily["weather_code"][i]

            icon, condition = weather_condition.get(
                weather_code,
                ("🌦️", "Unknown weather")
            )

            min_temp = daily["temperature_2m_min"][i]
            max_temp = daily["temperature_2m_max"][i]
            rain = daily["precipitation_probability_max"][i]
            date = daily["time"][i]

            reply += (
                f"📆 {date}\n"
                f"{icon} {condition}\n"
                f"🌡️ {min_temp}°C - {max_temp}°C\n"
                f"🌧️ Rain probability: {rain}%\n\n"
            )

        return {
            "reply": reply
        }

    except requests.RequestException as e:
        print("7-DAY REQUEST ERROR:", e)
        return {
            "reply": "⚠️ I couldn't connect to the weather service right now."
        }

    except (KeyError, ValueError, TypeError, IndexError) as e:
        print("7-DAY DATA ERROR:", e)
        return {
            "reply": "⚠️ The 7-day forecast is unavailable right now."
        }


# =========================================
# FIND CITY FROM WEATHER MESSAGE
# =========================================

def extract_city(message: str):

    text = message.strip()

    patterns = [
        r"(?:weather|temperature|forecast)\s+(?:in|at|for)\s+(.+?)(?:\s+tomorrow|\s+today)?$",

        r"(?:what(?:'s| is)\s+)?(?:the\s+)?weather\s+(?:in|at|for)\s+(.+)$",

        r"(?:forecast)\s+(?:in|at|for)\s+(.+)$",

        r"(?:in|at|for)\s+([A-Za-z .'-]+)$"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            city = match.group(1).strip()

            city = re.sub(
                r"\b(today|tomorrow|this week|next week)\b",
                "",
                city,
                flags=re.IGNORECASE
            ).strip()

            if city:
                return city

    return None


# =========================================
# DETECT WEATHER REQUEST TYPE
# =========================================

def detect_weather_request(message: str):

    text = message.lower().strip()

    weather_words = [
        "weather",
        "temperature",
        "forecast",
        "rain",
        "snow",
        "humid",
        "humidity"
    ]

    if not any(word in text for word in weather_words):
        return None

    city = extract_city(message)

    if not city:
        return {
            "type": "missing_city",
            "city": None
        }

    if (
        "7 day" in text
        or "7-day" in text
        or "seven day" in text
        or "weekly forecast" in text
        or "week forecast" in text
    ):
        return {
            "type": "seven_day",
            "city": city
        }

    if "tomorrow" in text:
        return {
            "type": "tomorrow",
            "city": city
        }

    return {
        "type": "current",
        "city": city
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

    weather_request = detect_weather_request(user_message)

    if weather_request:

        request_type = weather_request["type"]

        city = weather_request["city"]

        if request_type == "missing_city":

            return {
                "reply": (
                    "🌍 Please tell me the city.\n"
                    "For example: Weather in Delhi"
                )
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