import time
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# -----------------------------
# Minimal OpenSky API Classes
# -----------------------------
class OpenSkyApi:
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password

    def get_states(self, time_secs=0, bbox=()):
        url = "https://opensky-network.org/api/states/all"
        params = {}
        if time_secs != 0:
            params["time"] = time_secs
        if bbox and len(bbox) == 4:
            params["lamin"] = bbox[0]
            params["lamax"] = bbox[1]
            params["lomin"] = bbox[2]
            params["lomax"] = bbox[3]

        if self.username and self.password:
            resp = requests.get(url, params=params, auth=(self.username, self.password))
        else:
            resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return OpenSkyStates(data)

    def get_flights_by_aircraft(self, icao24, begin, end):
        url = "https://opensky-network.org/api/flights/aircraft"
        params = {"icao24": icao24, "begin": begin, "end": end}
        if self.username and self.password:
            resp = requests.get(url, params=params, auth=(self.username, self.password))
        else:
            resp = requests.get(url, params=params)

        resp.raise_for_status()
        data = resp.json()
        flights = [FlightData(f) for f in data] if data else []
        return flights

class OpenSkyStates:
    def __init__(self, data):
        self.time = data.get("time")
        self.states = []
        if data.get("states"):
            for s in data["states"]:
                self.states.append(StateVector(s))

class StateVector:
    def __init__(self, arr):
        self.icao24 = arr[0]
        self.callsign = arr[1].strip() if arr[1] else "N/A"
        self.origin_country = arr[2] or "N/A"
        self.time_position = arr[3]
        self.last_contact = arr[4]
        self.longitude = arr[5]
        self.latitude = arr[6]
        self.geo_altitude = arr[7]
        self.on_ground = arr[8]
        self.velocity = arr[9] if arr[9] is not None else 0.0
        self.true_track = arr[10]
        self.vertical_rate = arr[11]
        self.sensors = arr[12]
        self.baro_altitude = arr[13] if arr[13] else 0.0
        self.squawk = arr[14]
        self.spi = arr[15]
        self.position_source = arr[16]

class FlightData:
    def __init__(self, data):
        self.icao24 = data.get("icao24")
        self.firstSeen = data.get("firstSeen")
        self.estDepartureAirport = data.get("estDepartureAirport")
        self.lastSeen = data.get("lastSeen")
        self.estArrivalAirport = data.get("estArrivalAirport")
        self.callsign = data.get("callsign")
        self.estDepartureAirportHorizDistance = data.get("estDepartureAirportHorizDistance")
        self.estDepartureAirportVertDistance = data.get("estDepartureAirportVertDistance")
        self.estArrivalAirportHorizDistance = data.get("estArrivalAirportHorizDistance")
        self.estArrivalAirportVertDistance = data.get("estArrivalAirportVertDistance")
        self.departureAirportCandidatesCount = data.get("departureAirportCandidatesCount")
        self.arrivalAirportCandidatesCount = data.get("arrivalAirportCandidatesCount")

# -----------------------------
# Script-Specific Code
# -----------------------------
LAMIN = 33.421699
LAMAX = 33.458656
LOMIN = -111.988786
LOMAX = -111.917328

OPENSKY_USERNAME = None  # e.g. "your_username"
OPENSKY_PASSWORD = None  # e.g. "your_password"

api = OpenSkyApi(username=OPENSKY_USERNAME, password=OPENSKY_PASSWORD)

AIRLINE_CODES = {
    "SWA": "Southwest Airlines",
    "AAL": "American Airlines",
    "DAL": "Delta Air Lines",
    "UAL": "United Airlines",
    "ASA": "Alaska Airlines",
    "FFT": "Frontier Airlines",
    "JBU": "JetBlue Airways",
    "WN":  "Spirit Airlines",
    "HVN": "Hawaiian Airlines",
    "MCO": "Envoy Air",
    "SKW": "SkyWest Airlines",
    "EJA": "NetJets",
    "MXY": "Breeze Airways",
    "WJA": "WestJet Airline",
    # etc.
}

def get_airline_name(callsign):
    if callsign and len(callsign) >= 3:
        prefix = callsign[:3].upper()
        return AIRLINE_CODES.get(prefix, "Unknown Airline")
    return "Unknown Airline"

def strip_leading_k(airport_code):
    if airport_code != "N/A" and len(airport_code) == 4 and airport_code.startswith("K"):
        return airport_code[1:]
    return airport_code

def get_flight_details(icao24):
    now = int(time.time())
    begin = now - 10 * 3600
    end = now + 2 * 3600

    try:
        flights = api.get_flights_by_aircraft(icao24, begin, end)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (404, 429):
            return ("N/A", "N/A")
        else:
            raise e

    if flights:
        flights.sort(key=lambda f: f.firstSeen, reverse=True)
        latest = flights[0]
        origin = latest.estDepartureAirport or "N/A"
        dest = latest.estArrivalAirport or "N/A"
        return (strip_leading_k(origin), strip_leading_k(dest))
    else:
        return ("N/A", "N/A")

def fetch_flight_data():
    states = api.get_states(time_secs=0, bbox=(LAMIN, LAMAX, LOMIN, LOMAX))
    if not states or not states.states:
        return []

    flight_rows = []
    for state in states.states:
        icao24 = state.icao24
        callsign = state.callsign
        alt = state.baro_altitude
        country = state.origin_country
        vel = state.velocity
        airline = get_airline_name(callsign)
        origin, destination = get_flight_details(icao24)

        flight_rows.append({
            "Callsign": callsign,
            "Altitude(m)": f"{alt:.2f}",
            "Country": country,
            "Vel(m/s)": f"{vel:.2f}",
            "Airline": airline,
            "Origin": origin,
            "Destination": destination,
            "Model": "N/A",
        })
    return flight_rows

# -----------------------------
# Streamlit App
# -----------------------------

st.title("UnionSky ✈️")

# Auto-refresh every 15 seconds
st_autorefresh(interval=8000, limit=None, key="flight_refresh")

st.write("This dashboard fetches real-time flight data of the flights in your view.")

flights = fetch_flight_data()
if not flights:
    st.write("No flights found in the defined area.")
else:
    st.write(f"Found {len(flights)} flights in the bounding box:")
    st.table(flights)
