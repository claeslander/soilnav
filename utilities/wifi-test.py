import network
import time

from config import WIFI_SSID, WIFI_PASS  # zie config.example.py

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_SSID, WIFI_PASS)

print("Verbinden met", WIFI_SSID, "...")

timeout = 20
while not wlan.isconnected() and timeout > 0:
    time.sleep(0.5)
    timeout -= 1

if wlan.isconnected():
    print("WiFi OK:", wlan.ifconfig()[0])
else:
    print("WiFi MISLUKT - status:", wlan.status())
