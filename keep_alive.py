# This script sets up a simple web server that UptimeRobot can ping to keep the bot alive.
from flask import Flask
from threading import Thread

# Create a Flask web server instance
app = Flask('')

# Define a route for the web server's root URL
@app.route('/')
def home():
    return "Hello! I'm alive."

# This function will run the web server in a separate thread
def run():
    app.run(host='0.0.0.0', port=8080)

# This function starts the thread for the web server
def keep_alive():
    t = Thread(target=run)
    t.start()
