function Header() {
  return (
    <header className="app-header">
      <div className="logo">
        WeatherGPT<span>°</span>
      </div>

      <nav className="weather-nav">
        <button>Clear</button>
        <button>Rain</button>
        <button>Snow</button>
        <button>Storm</button>
        <button>Night</button>
      </nav>
    </header>
  );
}

export default Header;