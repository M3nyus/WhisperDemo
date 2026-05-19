import sys
import logging
from flask import Flask, jsonify, render_template
import requests

import os
from dotenv import load_dotenv
from Logger import Logger

# Assuming your class is in a file named demo_module.py
# If it's in the same file, just make sure the class is defined above this.

app = Flask(__name__)

# --- Logging Setup ---
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

#LOAD .ENV
load_dotenv()

#IF EXIST SERVER_URL USE THAT, OR LOCALHOST
SERVER_URL = os.getenv("SERVER_URL")

if not SERVER_URL:
    SERVER_URL = "http://zv-project-server:3000"

#LOGGER
LOGFILE = os.getenv("MAIN_LOG")
log = Logger(LOGFILE)


#MAIN PAGE
@app.route("/")
def index():
    return render_template("main.html")


#START ROOM
@app.route('/start/<string:room_id>', methods=['POST', 'GET'])
def start_demo(room_id: str):
    try:
        response = requests.post(f"{SERVER_URL}/api/start/{room_id}")
        data = response.json()

        return jsonify(data), response.status_code

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


#STOP ROOM
@app.route('/command/stop/<string:room_id>', methods=['POST', 'GET'])
def stop_bot(room_id):
    try:
        response = requests.post(f"{SERVER_URL}/api/stop/{room_id}")
        data = response.json()

        return jsonify(data), response.status_code

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route('/status')
def get_status():
    return jsonify({
        "status": "main_running",
        "server": "http://localhost:3000"
    })

if __name__ == '__main__':
    # use_reloader=False is mandatory when using background threads in Flask Debug mode
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)