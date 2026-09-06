import { useEffect, useState } from "react";
import "./App.css";

import Header from "./components/Header";
import WeatherPanel from "./components/WeatherPanel";
import ChatPanel from "./components/ChatPanel";

function App() {
  const [weather, setWeather] = useState(null);
  const [location, setLocation] = useState(null);
  const [locationError, setLocationError] = useState("");

  const [timeMode, setTimeMode] = useState("");
  const [currentTime, setCurrentTime] = useState("");

  const [weatherMode, setWeatherMode] = useState("clear");

  // =========================================
  // DETECT REAL LOCAL TIME
  // =========================================

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const hour = now.getHours();

      // Display actual local time
      setCurrentTime(
        now.toLocaleTimeString([], {
          hour: "numeric",
          minute: "2-digit",
        })
      );

      // Determine time of day
      if (hour >= 5 && hour < 12) {
        setTimeMode("morning");
      } else if (hour >= 12 && hour < 17) {
        setTimeMode("afternoon");
      } else if (hour >= 17 && hour < 21) {
        setTimeMode("evening");
      } else {
        setTimeMode("night");
      }
    };

    // Run immediately
    updateTime();

    // Update every minute
    const timer = setInterval(updateTime, 60000);

    return () => clearInterval(timer);
  }, []);

  // =========================================
  // DETECT WEATHER MODE
  // =========================================

  useEffect(() => {
    if (!weather) return;

    const condition = weather.condition?.toLowerCase() || "";

    if (
      condition.includes("thunder") ||
      condition.includes("storm")
    ) {
      setWeatherMode("storm");
    } else if (
      condition.includes("rain") ||
      condition.includes("drizzle") ||
      condition.includes("shower")
    ) {
      setWeatherMode("rain");
    } else if (
      condition.includes("snow") ||
      condition.includes("sleet")
    ) {
      setWeatherMode("snow");
    } else if (
      condition.includes("cloud") ||
      condition.includes("overcast")
    ) {
      setWeatherMode("cloudy");
    } else {
      setWeatherMode("clear");
    }
  }, [weather]);

  // =========================================
  // DETECT USER LOCATION + WEATHER
  // =========================================

  useEffect(() => {
    if (!navigator.geolocation) {
      setLocationError(
        "Geolocation is not supported by this browser."
      );
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const latitude = position.coords.latitude;
        const longitude = position.coords.longitude;

        console.log("Latitude:", latitude);
        console.log("Longitude:", longitude);

        setLocation({
          latitude,
          longitude,
        });

        try {
          const response = await fetch(
             `${import.meta.env.VITE_API_URL}/location-weather?latitude=${latitude}&longitude=${longitude}`
            
          );

          if (!response.ok) {
            throw new Error(
              `HTTP error: ${response.status}`
            );
          }

          const data = await response.json();

          console.log("Location weather:", data);

          if (data.type === "weather") {
            setWeather(data);
            setLocationError("");
          } else {
            setLocationError(
              data.reply || "Unable to load local weather."
            );
          }
        } catch (error) {
          console.error("Weather error:", error);

          setLocationError(
            "Unable to load your local weather."
          );
        }
      },

      (error) => {
        console.error("Location error:", error);

        if (error.code === error.PERMISSION_DENIED) {
          setLocationError(
            "Location permission was denied."
          );
        } else if (
          error.code === error.POSITION_UNAVAILABLE
        ) {
          setLocationError(
            "Your location is currently unavailable."
          );
        } else if (error.code === error.TIMEOUT) {
          setLocationError(
            "Location request timed out."
          );
        } else {
          setLocationError(
            "Unable to detect your location."
          );
        }
      },

      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000,
      }
    );
  }, []);

  // =========================================
  // UI
  // =========================================

  return (
    <div className={`app ${timeMode} ${weatherMode}`}>

      <Header />

      <main className="main-layout">
        <WeatherPanel 
        weather={weather}
        currentTime={currentTime} 
        />

        <ChatPanel setWeather={setWeather} />
      </main>

      

      {/* Location status */}
      {location && (
        <div className="location-status">
          📍 Location detected
        </div>
      )}

      {/* Location / weather error */}
      {locationError && (
        <div className="location-status error">
          {locationError}
        </div>
      )}

    </div>
  );
}

export default App;