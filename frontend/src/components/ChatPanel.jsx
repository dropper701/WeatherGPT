import { useState } from "react";
import ForecastCard from "./ForecastCard";

function ChatPanel({ setWeather }) {
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [tomorrow, setTomorrow] = useState(null);
  const [weeklyForecast, setWeeklyForecast] = useState([]);
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!message.trim()) return;

    setLoading(true);
    setReply("");
    setTomorrow(null);
    setWeeklyForecast([]);

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/chat`,
        
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: message,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      const data = await response.json();

      console.log("Backend response:", data);

      if (data.type === "weather") {
        setWeather(data);
      } else if (data.type === "tomorrow") {
        setTomorrow(data);
      } else if (data.type === "seven_day") {
        setWeeklyForecast(data.forecast || []);
      } else {
        setReply(data.reply || "No response received.");
      }

      setMessage("");
    } catch (error) {
      console.error("API error:", error);
      setReply("⚠️ Unable to connect to WeatherGPT.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="chat-panel">

      {/* Chat Header */}
      <div className="chat-header">
        <h2>WeatherGPT</h2>
        <span>AI Weather Assistant</span>
      </div>

      {/* Chat Content */}
      <div className="chat-content">

        <p className="chat-intro">
          Ask me about the weather.
        </p>

        {/* AI Reply */}
        {reply && (
          <div className="chat-reply">
            {reply}
          </div>
        )}

        {/* Tomorrow Forecast */}
        {tomorrow && (
          <div className="tomorrow-card">

            <div className="tomorrow-title">
              Tomorrow in {tomorrow.city}
            </div>

            <div className="tomorrow-icon">
              {tomorrow.icon}
            </div>

            <div className="tomorrow-condition">
              {tomorrow.condition}
            </div>

            <div className="tomorrow-temperatures">
              {tomorrow.temperature_min}° —{" "}
              {tomorrow.temperature_max}°
            </div>

            <div className="tomorrow-rain">
              💧 Rain probability:{" "}
              {tomorrow.rain_probability}%
            </div>

          </div>
        )}

        {/* Seven Day Forecast */}
        {weeklyForecast.length > 0 && (
          <div className="weekly-forecast">
            {weeklyForecast.map((day) => (
              <ForecastCard
                key={day.date}
                day={day}
              />
            ))}
          </div>
        )}

      </div>

      {/* Chat Input */}
      <div className="chat-input">

        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              sendMessage();
            }
          }}
          placeholder="Ask about the weather..."
        />

        <button
          onClick={sendMessage}
          disabled={loading}
        >
          {loading ? "..." : "↗"}
        </button>

      </div>

    </section>
  );
}

export default ChatPanel;