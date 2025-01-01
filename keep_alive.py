from flask import Flask
from threading import Thread
import logging

app = Flask('')
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        logger.error(f"Error in keep alive server: {e}")

def keep_alive():
    t = Thread(target=run)
    t.start()
