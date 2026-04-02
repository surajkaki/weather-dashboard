import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Live Weather Dashboard",
    page_icon="🌤️",
    layout="wide"
)

WMO_CODES = {
    0: "Clear Sky",
    1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy Fog",
    51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
    61: "Light Rain", 63: "Moderate Rain", 65: "Heavy Rain",
    71: "Light Snow", 73: "Moderate Snow", 75: "Heavy Snow", 77: "Snow Grains",
    80: "Light Showers", 81: "Moderate Showers", 82: "Violent Showers",
    85: "Light Snow Showers", 86: "Heavy Snow Showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ Hail", 99: "Thunderstorm w/ Heavy Hail",
}

def wmo_label(code: int) -> str:
    return WMO_CODES.get(code, f"Code {code}")

try:
    from streamlit_autorefresh import st_autorefresh
    AUTO_REFRESH_AVAILABLE = True
except ImportError:
    AUTO_REFRESH_AVAILABLE = False

with st.sidebar:
    st.title("⚙️ Settings")

    city = st.text_input("City Name", value="Hyderabad")

    unit_option = st.selectbox("Temperature Unit", ["Celsius (°C)", "Fahrenheit (°F)"])
    use_fahrenheit = "Fahrenheit" in unit_option
    unit_symbol = "°F" if use_fahrenheit else "°C"

    refresh_mins = st.selectbox(
        "Auto-Refresh Interval",
        options=[30, 60],
        format_func=lambda x: f"Every {x} minutes"
    )

    if st.button("🔄 Refresh Now"):
        st.rerun()

    st.divider()
    st.caption(f"🕐 Last loaded: {datetime.now().strftime('%d %b %Y, %H:%M:%S')}")

    if not AUTO_REFRESH_AVAILABLE:
        st.warning(
            "Auto-refresh not active.\n\n"
            "Run: `pip install streamlit-autorefresh`\n"
            "then restart the app."
        )

if AUTO_REFRESH_AVAILABLE:
    st_autorefresh(interval=refresh_mins * 60 * 1000, key="weather_autorefresh")

# Converts city name → latitude, longitude, display name
def get_coordinates(city: str) -> tuple[float, float, str] | None:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city, "count": 1, "language": "en", "format": "json"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if "results" in data and data["results"]:
            r = data["results"][0]
            display = f"{r['name']}, {r.get('country', '')}"
            return r["latitude"], r["longitude"], display
        else:
            st.error(f"❌ City '{city}' not found. Try a different city name.")
    except requests.exceptions.Timeout:
        st.error("❌ Geocoding request timed out. Check your internet connection.")
    except Exception as e:
        st.error(f"❌ Geocoding error: {e}")
    return None

# Fetches current conditions and 5-day hourly forecast from Open-Meteo
def get_weather(lat: float, lon: float) -> dict | None:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,surface_pressure,visibility,weather_code",
        "hourly": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,surface_pressure,weather_code",
        "forecast_days": 5,
        "timezone": "auto",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            st.error(f"❌ Weather API error {resp.status_code}. Try again later.")
    except requests.exceptions.Timeout:
        st.error("❌ Weather request timed out. Check your internet connection.")
    except Exception as e:
        st.error(f"❌ Weather error: {e}")
    return None

def celsius_to_fahrenheit(c: float) -> float:
    return round(c * 9 / 5 + 32, 1)

def convert_temp(c: float) -> float:
    return celsius_to_fahrenheit(c) if use_fahrenheit else round(c, 1)

def detect_anomaly(current_temp: float, forecast_temps: list, threshold: float = 5.0):
    avg = sum(forecast_temps) / len(forecast_temps) if forecast_temps else current_temp
    deviation = abs(current_temp - avg)
    return deviation > threshold, round(avg, 1), round(deviation, 1)


st.title("🌤️ Live Weather Dashboard")
st.caption(
    f"📡 Source: Open-Meteo (no API key required)  |  "
    f"🔁 Auto-refresh: Every {refresh_mins} minutes  |  "
    f"📍 City: {city}"
)

with st.spinner(f"Fetching weather data for **{city}**..."):
    coords = get_coordinates(city)
    if coords is None:
        st.stop()
    lat, lon, display_name = coords
    weather = get_weather(lat, lon)
    if weather is None:
        st.stop()

cur = weather["current"]
temp_c       = cur["temperature_2m"]
feels_c      = cur["apparent_temperature"]
humidity     = cur["relative_humidity_2m"]
wind_speed   = cur["wind_speed_10m"]
pressure     = cur["surface_pressure"]
visibility_m = cur.get("visibility", 0)
weather_code = cur["weather_code"]

temp       = convert_temp(temp_c)
feels_like = convert_temp(feels_c)
visibility = round(visibility_m / 1000, 1)  # m → km
condition  = wmo_label(weather_code)

hourly = weather["hourly"]
df = pd.DataFrame({
    "datetime"  : hourly["time"],
    "temp_c"    : hourly["temperature_2m"],
    "feels_c"   : hourly["apparent_temperature"],
    "humidity"  : hourly["relative_humidity_2m"],
    "wind"      : hourly["wind_speed_10m"],
    "pressure"  : hourly["surface_pressure"],
    "condition" : [wmo_label(c) for c in hourly["weather_code"]],
})
df["datetime"]   = pd.to_datetime(df["datetime"])
df["temp"]       = df["temp_c"].apply(convert_temp)
df["feels_like"] = df["feels_c"].apply(convert_temp)
df.drop(columns=["temp_c", "feels_c"], inplace=True)

is_anomaly, avg_temp, deviation = detect_anomaly(temp, df["temp"].tolist())

st.subheader(f"📍 Current Conditions — {display_name}")
c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("🌡️ Temperature", f"{temp}{unit_symbol}",    f"Feels {feels_like}{unit_symbol}")
c2.metric("💧 Humidity",    f"{humidity}%")
c3.metric("💨 Wind Speed",  f"{wind_speed} km/h")
c4.metric("🌫️ Visibility",  f"{visibility} km")
c5.metric("📊 Pressure",    f"{pressure} hPa")
c6.metric("☁️ Condition",   condition)

if is_anomaly:
    st.warning(
        f"⚠️ **Temperature Anomaly Detected!**  "
        f"Current temp ({temp}{unit_symbol}) deviates **{deviation}{unit_symbol}** "
        f"from the 5-day average ({avg_temp}{unit_symbol})."
    )
else:
    st.success(
        f"✅ **Temperature is Normal.** "
        f"Current {temp}{unit_symbol} is close to the 5-day average of {avg_temp}{unit_symbol}."
    )

st.divider()

st.subheader("📈 5-Day Temperature Trend")
fig_temp = go.Figure()
fig_temp.add_trace(go.Scatter(
    x=df["datetime"],
    y=df["temp"],
    mode="lines+markers",
    name=f"Temperature ({unit_symbol})",
    line=dict(color="#E63946", width=2.5),
    fill="tozeroy",
    fillcolor="rgba(230, 57, 70, 0.08)",
    marker=dict(size=5)
))
fig_temp.add_trace(go.Scatter(
    x=df["datetime"],
    y=df["feels_like"],
    mode="lines",
    name=f"Feels Like ({unit_symbol})",
    line=dict(color="#F4A261", width=1.5, dash="dot"),
))
fig_temp.add_hline(
    y=avg_temp,
    line_dash="dash",
    line_color="gray",
    annotation_text=f"5-day avg: {avg_temp}{unit_symbol}",
    annotation_position="bottom right"
)
fig_temp.update_layout(
    xaxis_title="Date & Time",
    yaxis_title=f"Temperature ({unit_symbol})",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    height=350,
    margin=dict(l=0, r=0, t=30, b=0)
)
st.plotly_chart(fig_temp, use_container_width=True)

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("💧 Humidity Trend")
    fig_hum = go.Figure()
    fig_hum.add_trace(go.Bar(
        x=df["datetime"],
        y=df["humidity"],
        name="Humidity (%)",
        marker=dict(color="#457B9D", opacity=0.8)
    ))
    fig_hum.update_layout(
        xaxis_title="Date & Time",
        yaxis_title="Humidity (%)",
        yaxis=dict(range=[0, 100]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=300,
        margin=dict(l=0, r=0, t=10, b=0)
    )
    st.plotly_chart(fig_hum, use_container_width=True)

with col_right:
    st.subheader("💨 Wind Speed Trend")
    fig_wind = go.Figure()
    fig_wind.add_trace(go.Scatter(
        x=df["datetime"],
        y=df["wind"],
        mode="lines+markers",
        name="Wind Speed (km/h)",
        line=dict(color="#2A9D8F", width=2),
        fill="tozeroy",
        fillcolor="rgba(42, 157, 143, 0.1)"
    ))
    fig_wind.update_layout(
        xaxis_title="Date & Time",
        yaxis_title="Wind Speed (km/h)",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=300,
        margin=dict(l=0, r=0, t=10, b=0)
    )
    st.plotly_chart(fig_wind, use_container_width=True)

with st.expander("📋 View Raw Forecast Data Table"):
    display_df = df[["datetime", "temp", "feels_like", "humidity", "wind", "condition", "pressure"]].copy()
    display_df.columns = [
        "Date/Time", f"Temp ({unit_symbol})", f"Feels Like ({unit_symbol})",
        "Humidity (%)", "Wind (km/h)", "Condition", "Pressure (hPa)"
    ]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    f"Data fetched at **{datetime.now().strftime('%d %b %Y, %H:%M:%S')}**  |  "
    f"Source: [Open-Meteo](https://open-meteo.com) (free, no API key)  |  "
    f"Built with Streamlit + Plotly"
)
