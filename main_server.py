import sys
import logging
import threading
import asyncio
from flask import Flask, jsonify
from aiortc.contrib.media import MediaBlackhole
from Bot import Demo
import os
from dotenv import load_dotenv
from Logger import Logger


# Assuming your class is in a file named demo_module.py
# If it's in the same file, just make sure the class is defined above this.

app = Flask(__name__)

#LOAD .ENV
load_dotenv()

#LOGGER
LOGFILE = os.getenv("LOG")
log = Logger(LOGFILE)

# --- Logging Setup ---
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)


@app.route('/status')
def get_status():
    if demo_instance:
        return jsonify({
            "room_id": demo_instance.roomId,
            "closed": getattr(demo_instance, '_closed', False)
        })
    return jsonify({"status": "idle"})
