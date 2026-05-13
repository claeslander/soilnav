"""
Flask server — runs on Mac.
Typ 'vooruit', 'achteruit', 'links', 'rechts' of 'stop'.

Start: python3 server.py
"""
import threading
from flask import Flask, jsonify, request

app = Flask(__name__)
current_command = "stop"
COMMANDS = ("vooruit", "achteruit", "links", "rechts", "stop", "meet", "sequentie")

laatste_positie = {
    "lat": None,
    "lon": None,
    "hdop": 99.0,
    "fix": False
}

field_polygon = None  # [[lat, lng], ...] — ingekrimpte geofence

@app.route("/command", methods=["GET"])
def command():
    return jsonify({"command": current_command})


@app.route("/gps", methods=["PUT"])
def put_gps():
    global laatste_positie
    laatste_positie = request.get_json()
    print("GPS ontvangen:", laatste_positie)
    return jsonify({"status": "ok"}), 200


@app.route("/gps", methods=["GET"])
def get_gps():
    return jsonify(laatste_positie), 200


@app.route("/field", methods=["OPTIONS", "POST"])
def post_field():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    global field_polygon
    data = request.get_json()
    field_polygon = data.get("polygon")  # None of [[lat, lng], ...]
    print("Geofence ontvangen:", len(field_polygon) if field_polygon else 0, "punten")
    return jsonify({"status": "ok"}), 200


@app.route("/field", methods=["GET"])
def get_field():
    return jsonify({"polygon": field_polygon}), 200


@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, PUT, POST, OPTIONS'
    return response


def run_server():
    app.run(host="0.0.0.0", port=5000, use_reloader=False)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print("Server gestart op poort 5000.")
    print("Commando's: {}".format(", ".join(COMMANDS)))

    while True:
        try:
            cmd = input("[{}] > ".format(current_command)).strip().lower()
            if cmd == "q":
                break
            elif cmd in COMMANDS:
                current_command = cmd
                print("Commando ingesteld op: {}".format(cmd))
            else:
                print("Onbekend commando. Kies uit: {}".format(", ".join(COMMANDS)))
        except KeyboardInterrupt:
            break
