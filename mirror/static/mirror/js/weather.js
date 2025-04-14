const weatherMap = {
  0: { icon: "☀️", desc: "Clear" },
  1: { icon: "🌤️", desc: "Mainly clear" },
  2: { icon: "⛅", desc: "Partly cloudy" },
  3: { icon: "☁️", desc: "Overcast" },
  45: { icon: "🌫️", desc: "Fog" },
  48: { icon: "🌫️", desc: "Depositing fog" },
  51: { icon: "🌦️", desc: "Light drizzle" },
  53: { icon: "🌦️", desc: "Moderate drizzle" },
  55: { icon: "🌧️", desc: "Dense drizzle" },
  61: { icon: "🌧️", desc: "Rain" },
  63: { icon: "🌧️", desc: "Heavy rain" },
  71: { icon: "❄️", desc: "Snow" },
  95: { icon: "⛈️", desc: "Thunderstorm" },
  99: { icon: "⛈️", desc: "Thunder + hail" },
};

async function loadWeather() {
  try {
    const res = await fetch("/weather/");
    const data = await res.json();

    const code = data.weather_code;
    const icon = weatherMap[code]?.icon || "❓";
    const temp = Math.round(data.temp);
    const feels = Math.round(data.feels_like);

    const text = `${icon} ${temp}°F (feels like ${feels}°F)`;
    document.getElementById("weather").textContent = text;
  } catch (e) {
    document.getElementById("weather").textContent = "⚠️ Weather error";
  }
}

loadWeather();
setInterval(loadWeather, 10 * 60 * 1000); // refresh every 10 minutes
