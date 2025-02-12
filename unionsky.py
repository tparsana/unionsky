import time
import sys
import requests

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
        """
        Retrieve flight history for a specific aircraft between [begin, end] (Unix time).
        Returns a list of FlightData objects (or an empty list if no data).
        """
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
# Purposely left blank.
LAMIN = 0
LAMAX = 0
LOMIN = 0
LOMAX = 0

OPENSKY_USERNAME = None
OPENSKY_PASSWORD = None 

# Instantiate the API client
api = OpenSkyApi(username=OPENSKY_USERNAME, password=OPENSKY_PASSWORD)

# A dictionary to derive airline name from callsign prefix
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

    # Add more mappings as needed.
}

def get_airline_name(callsign):
    """Derive the airline name from the first 3 letters of callsign."""
    if callsign and len(callsign) >= 3:
        prefix = callsign[:3].upper()
        return AIRLINE_CODES.get(prefix, "Unknown Airline")
    return "Unknown Airline"

def get_flight_details(icao24):
    """
    Retrieve flight data from the last 6 hours for this aircraft.
    Sort by 'firstSeen' descending so we pick the most recent flight.
    Return (origin, destination) or ("N/A","N/A") if none found.
    """
    now = int(time.time())
    begin = now - 10 * 3600  # 10 hours ago (adjust as needed)
    end = now + 2 * 3600
    flights = api.get_flights_by_aircraft(icao24, begin, end)

    if flights:
        # Sort flights by the time they began so we pick the most recent
        flights.sort(key=lambda f: f.firstSeen, reverse=True)
        latest_flight = flights[0]
        origin = latest_flight.estDepartureAirport if latest_flight.estDepartureAirport else "N/A"
        destination = latest_flight.estArrivalAirport if latest_flight.estArrivalAirport else "N/A"
        return origin, destination
    else:
        return "N/A", "N/A"

def strip_leading_k(airport_code):
    """
    If the airport code is exactly 4 characters long and starts with 'K',
    remove the first character (e.g., 'KSAT' -> 'SAT').
    Otherwise, return it as is.
    """
    if airport_code != "N/A" and len(airport_code) == 4 and airport_code.startswith("K"):
        return airport_code[1:]
    return airport_code

def display_flights():
    # Get the latest states for your bounding box
    states = api.get_states(time_secs=0, bbox=(LAMIN, LAMAX, LOMIN, LOMAX))

    # Clear screen for a fresh table
    if sys.platform.startswith("win"):
        pass 
    else:
        print("\033c", end="")

    if not states or not states.states:
        print("No flight states found in the defined area.")
        return

    # Print table header
    header = (
        f"{'Callsign':<10} {'Altitude(m)':<12} {'Country':<15} {'Vel(m/s)':<10} "
        f"{'Airline':<20} {'Origin':<10} {'Destination':<12} {'Model':<10}"
    )
    print(header)
    print("-" * len(header))

    # For each aircraft in the bounding box
    for state in states.states:
        icao24 = state.icao24
        callsign = state.callsign
        alt = state.baro_altitude
        country = state.origin_country
        vel = state.velocity
        airline = get_airline_name(callsign)
        origin, destination = get_flight_details(icao24)

        # Strip leading 'K' if we have 4-letter codes
        origin = strip_leading_k(origin)
        destination = strip_leading_k(destination)

        model = "N/A"  # Not provided by OpenSky

        print(
            f"{callsign:<10} {alt:<12.2f} {country:<15} {vel:<10.2f} "
            f"{airline:<20} {origin:<10} {destination:<12} {model:<10}"
        )

def main():
    print("=== Enhanced OpenSky Flight Tracker ===")
    print("Press Ctrl+C to stop.\n")

    while True:
        display_flights()
        time.sleep(10)

if __name__ == "__main__":
    main()
