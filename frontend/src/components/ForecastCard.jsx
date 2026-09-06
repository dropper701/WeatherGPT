function ForecastCard({ day }) {
  return (
    <div className="forecast-card">
      <div className="forecast-date">
        {day.date}
      </div>

      <div className="forecast-icon">
        {day.icon}
      </div>

      <div className="forecast-condition">
        {day.condition}
      </div>

      <div className="forecast-temperature">
        {day.min_temp}° — {day.max_temp}°
      </div>

      <div className="forecast-rain">
        💧 {day.rain_probability}%
      </div>
    </div>
  );
}

export default ForecastCard;