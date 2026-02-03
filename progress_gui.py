#!/usr/bin/env python
"""
Progress GUI for Reddit Video Maker Bot.
Real-time progress tracking with steps and previews.
"""
import os
import json
import threading
import webbrowser
from pathlib import Path

from flask import Flask, render_template, send_from_directory, jsonify, request
from flask_socketio import SocketIO, emit

from utils.progress import progress_tracker

# Configuration
HOST = "0.0.0.0"
PORT = 5000

# Configure Flask app
app = Flask(__name__, template_folder="GUI", static_folder="GUI/static")
app.secret_key = os.urandom(24)

# Configure SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")


# Progress update callback
def broadcast_progress(data):
    """Broadcast progress updates to all connected clients."""
    socketio.emit("progress_update", data, namespace="/progress")


# Register the callback
progress_tracker.add_update_callback(broadcast_progress)


@app.after_request
def after_request(response):
    """Ensure responses aren't cached."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def index():
    """Main progress dashboard."""
    return render_template("progress.html")


@app.route("/api/status")
def get_status():
    """Get current progress status."""
    return jsonify(progress_tracker.get_status())


@app.route("/api/history")
def get_history():
    """Get job history."""
    return jsonify({
        "jobs": [job.to_dict() for job in progress_tracker.job_history]
    })


# Serve static files
@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve static files."""
    return send_from_directory("GUI/static", filename)


# Serve result videos
@app.route("/results/<path:name>")
def results(name):
    """Serve result videos."""
    return send_from_directory("results", name)


# Serve preview images
@app.route("/preview/<path:name>")
def previews(name):
    """Serve preview images."""
    return send_from_directory("assets/temp", name)


# Serve temp assets (screenshots, audio visualizations)
@app.route("/assets/<path:name>")
def assets(name):
    """Serve asset files."""
    return send_from_directory("assets", name)


# SocketIO Events
@socketio.on("connect", namespace="/progress")
def handle_connect():
    """Handle client connection."""
    emit("progress_update", progress_tracker.get_status())


@socketio.on("disconnect", namespace="/progress")
def handle_disconnect():
    """Handle client disconnection."""
    pass


@socketio.on("request_status", namespace="/progress")
def handle_request_status():
    """Handle status request from client."""
    emit("progress_update", progress_tracker.get_status())


def run_gui(open_browser=True):
    """Run the progress GUI server."""
    if open_browser:
        webbrowser.open(f"http://localhost:{PORT}", new=2)

    print(f"Progress GUI running at http://localhost:{PORT}")
    socketio.run(app, host=HOST, port=PORT, debug=False)


def run_gui_background():
    """Run the GUI server in a background thread."""
    thread = threading.Thread(target=lambda: socketio.run(app, host=HOST, port=PORT, debug=False, use_reloader=False))
    thread.daemon = True
    thread.start()
    return thread


if __name__ == "__main__":
    run_gui()
