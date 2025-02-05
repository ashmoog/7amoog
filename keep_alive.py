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
        # Use port 8000 to match .replit configuration
        app.run(host='0.0.0.0', port=8000, debug=False)
    except Exception as e:
        logger.error(f"Error in keep alive server: {e}")
        raise  # Re-raise to ensure main process knows about the failure

def keep_alive():
    """Start the keep-alive server in a separate thread"""
    server_thread = Thread(target=run, daemon=True)
    server_thread.start()
    logger.info("Keep-alive server thread started")
    return server_thread