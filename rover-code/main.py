import network
import urequests
import ujson
import time
from machine import I2C, Pin
from quad_motor_driver import QuadMotorDriver
from omlaag import rotate_down, pins as stepper_pins
from omhoog import rotate_up

# ── Configuratie ──────────────────────────────────────────────────────────────
# SERVER_IP = IP van de Mac waarop control-server/server.py draait.
# Check met `ifconfig` (Mac/Linux) of `ipconfig` (Windows).
# Dit IP moet overeenkomen met GPS_SERVER in website/app.js.
from config import WIFI_SSID, WIFI_PASS  # zie config.example.py
SERVER_IP   = "172.20.10.7"   # zelfde als GPS_SERVER in website/app.js
SERVER_PORT = 5000

GPS_UPLOAD_INTERVAL  = 1   # seconden tussen GPS-uploads naar server
FIELD_FETCH_INTERVAL = 30  # seconden tussen ophalen geofence van server
# ─────────────────────────────────────────────────────────────────────────────

motor = QuadMotorDriver(scl=1, sda=0)

# GPS via I2C bus 1 (aparte bus van de motordriver op bus 0)
gps_i2c  = I2C(1, scl=Pin(7), sda=Pin(6), freq=100000)
GPS_ADDR = 0x20
REG_YEAR_H = 0

print("I2C scan (motors)...")
gevonden = motor.i2c.scan()
if gevonden:
    for adres in gevonden:
        print("  0x{:02X}".format(adres))
else:
    print("  geen apparaten gevonden")

# ── WiFi verbinding ───────────────────────────────────────────────────────────
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_SSID, WIFI_PASS)
print("Verbinden met WiFi...")
timeout = 20
while not wlan.isconnected() and timeout > 0:
    time.sleep(0.5)
    timeout -= 1

if wlan.isconnected():
    ip, subnet, gateway, dns = wlan.ifconfig()
    print("WiFi OK")
    print("  SSID    :", wlan.config("ssid"))
    print("  IP      :", ip)
    print("  Subnet  :", subnet)
    print("  Gateway :", gateway)
    print("  DNS     :", dns)
    print("  RSSI    :", wlan.status("rssi"), "dBm")
else:
    print("WiFi MISLUKT - status:", wlan.status())
    print("  0=IDLE 1=CONNECTING 2=WRONG_PASSWORD 3=NO_AP 4=CONNECT_FAIL -1=ERROR")
    raise RuntimeError("Geen WiFi verbinding")

# ── URL's ─────────────────────────────────────────────────────────────────────
cmd_url   = "http://{}:{}/command".format(SERVER_IP, SERVER_PORT)
gps_url   = "http://{}:{}/gps".format(SERVER_IP, SERVER_PORT)
field_url = "http://{}:{}/field".format(SERVER_IP, SERVER_PORT)

current    = None
_last_done = None

gps_data = {"lat": None, "lon": None, "hdop": 0.0, "fix": False}
geofence  = None  # [[lat, lon], ...] of None

_last_gps_upload  = 0
_last_field_fetch = 0


# ── GPS hulpfuncties ──────────────────────────────────────────────────────────

def lees_gps():
    """Lees GPS-positie via I2C en werk gps_data bij."""
    print("GPS: locatie lezen...")
    try:
        data = gps_i2c.readfrom_mem(GPS_ADDR, REG_YEAR_H, 20)

        lat_deg  = data[7]
        lat_min  = data[8]
        lat_frac = (data[9] << 16 | data[10] << 8 | data[11]) / 100000.0
        lat_dir  = chr(data[12])

        lon_deg  = data[13]
        lon_min  = data[14]
        lon_frac = (data[15] << 16 | data[16] << 8 | data[17]) / 100000.0
        lon_dir  = chr(data[18])

        sats = data[19]

        if sats == 0 or lat_deg == 0:
            print("GPS: geen fix")
            gps_data.update({"lat": None, "lon": None, "hdop": 99.0, "fix": False})
            return

        lat = lat_deg + (lat_min + lat_frac) / 60.0
        if lat_dir == 'S':
            lat = -lat

        lon = lon_deg + (lon_min + lon_frac) / 60.0
        if lon_dir == 'W':
            lon = -lon

        print("GPS OK: {:.6f}, {:.6f}".format(lat, lon))
        gps_data.update({"lat": lat, "lon": lon, "hdop": 0.0, "fix": True})

    except Exception as e:
        print("GPS fout:", type(e).__name__, e)
        gps_data.update({"lat": None, "lon": None, "hdop": 99.0, "fix": False})


def upload_gps():
    """Stuur huidige GPS-positie naar de server via PUT /gps."""
    try:
        r = urequests.put(
            gps_url,
            data=ujson.dumps(gps_data),
            headers={"Content-Type": "application/json"}
        )
        r.close()
    except Exception as e:
        print("GPS upload fout:", e)


# ── Geofence hulpfuncties ─────────────────────────────────────────────────────

def fetch_geofence():
    """Haal de actieve geofence op van de server via GET /field."""
    global geofence
    try:
        r = urequests.get(field_url)
        data = r.json()
        r.close()
        geofence = data.get("polygon")
        if geofence:
            print("Geofence geladen:", len(geofence), "punten")
        else:
            print("Geen actieve geofence")
    except Exception as e:
        print("Geofence ophalen mislukt:", e)


def point_in_polygon(lat, lon, polygon):
    """Ray-casting algoritme: geeft True als (lat, lon) binnen het polygoon valt."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]
        if ((lon_i > lon) != (lon_j > lon)) and \
           (lat < (lat_j - lat_i) * (lon - lon_i) / (lon_j - lon_i) + lat_i):
            inside = not inside
        j = i
    return inside


def within_geofence():
    """True als rover binnen de geofence valt. Zonder GPS-fix of geofence altijd True."""
    if not geofence or not gps_data["fix"]:
        return True
    return point_in_polygon(gps_data["lat"], gps_data["lon"], geofence)


# ── Commando's ────────────────────────────────────────────────────────────────

def do_meet():
    motor.stop()
    for _ in range(4):
        rotate_down()
    time.sleep(10)
    for _ in range(4):
        rotate_up()
    for p in stepper_pins:
        p.value(0)


def do_sequentie():
    for _ in range(4):
        if not within_geofence():
            print("Buiten geofence — sequentie gestopt")
            motor.stop()
            return
        motor.go_forward()
        time.sleep(7)
        do_meet()
        if not within_geofence():
            print("Buiten geofence — sequentie gestopt")
            motor.stop()
            return
        motor.go_forward()
        time.sleep(7)
    motor.stop()


# ── Hoofdlus ──────────────────────────────────────────────────────────────────

while True:
    try:
        now = time.time()

        # GPS uitlezen en periodiek uploaden naar server
        lees_gps()
        if now - _last_gps_upload >= GPS_UPLOAD_INTERVAL:
            upload_gps()
            _last_gps_upload = now

        # Geofence periodiek ophalen van server
        if now - _last_field_fetch >= FIELD_FETCH_INTERVAL:
            fetch_geofence()
            _last_field_fetch = now

        # Commando ophalen van server
        r = urequests.get(cmd_url)
        cmd = r.json()["command"]
        r.close()
        current = cmd

        # Continu commando's — elke iteratie opnieuw uitvoeren
        if cmd == "vooruit":
            _last_done = None
            if within_geofence():
                motor.go_forward()
            else:
                print("Buiten geofence — vooruit geblokkeerd")
                motor.stop()
            time.sleep(0.5)
        elif cmd == "achteruit":
            _last_done = None
            motor.go_backward()
            time.sleep(0.5)
        elif cmd == "links":
            _last_done = None
            motor.turn_left()
        elif cmd == "rechts":
            _last_done = None
            motor.turn_right()
        elif cmd == "stop":
            _last_done = None
            motor.stop()
            time.sleep(0.5)
        elif cmd == "meet" and _last_done != "meet":
            _last_done = "meet"
            do_meet()
        elif cmd == "sequentie" and _last_done != "sequentie":
            _last_done = "sequentie"
            do_sequentie()

    except Exception as e:
        print("Fout:", e)
        motor.stop()
        _last_done = None
        current = None
        time.sleep(0.5)
