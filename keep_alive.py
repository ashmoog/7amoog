from flask import Flask
from threading import Thread
import logging
import os

app = Flask('')
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    try:
        port = int(os.environ.get('PORT', 8000))
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"Error in keep alive server: {e}")
        raise  # Re-raise to ensure main process knows about the failure

def keep_alive():
    """Start the keep-alive server in a separate thread"""
    server_thread = Thread(target=run, daemon=True)
    server_thread.start()
    logger.info("Keep-alive server thread started")
    return server_thread