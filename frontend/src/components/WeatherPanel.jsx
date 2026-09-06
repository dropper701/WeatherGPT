function WeatherPanel({ weather, currentTime }) {
  if (!weather) {
    return (
      <section className="weather-panel">
        <div className="weather-top">
          <div>
            <div className="weather-location">Detecting location...</div>
            <div className="weather-time">{currentTime}</div>
          </div>
        </div>

        <div className="weather-loading">
          <div className="weather-temperature">—</div>

          <div className="weather-condition">
            Waiting for weather
          </div>

          <div className="weather-description">
            Getting your local weather...
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="weather-panel">

      <div className="weather-top">
        <div>
          <div className="weather-location">
            {weather.city}
          </div>

          <div className="weather-country">
            {weather.country}
          </div>
        </div>

        <div className="weather-time">
          {currentTime}
        </div>
      </div>

      <div className="weather-main">
        <div className="weather-temperature">
          {weather.temperature}°
        </div>

        <div className="weather-condition">
          <span className="weather-icon">
            {weather.icon}
          </span>

          {weather.condition}
        </div>

        <div className="weather-description">
          Current weather conditions
        </div>
      </div>

      <div className="weather-stats">

        <div>
          <span>💨 Wind</span>
          <strong>{weather.wind} km/h</strong>
        </div>

        <div>
          <span>💧 Humidity</span>
          <strong>{weather.humidity}%</strong>
        </div>

      </div>

    </section>
  );
}

export default WeatherPanel;