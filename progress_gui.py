#!/usr/bin/env python
"""
Reddit Video Maker Bot - Web UI
Complete web interface for configuration, video generation, and progress tracking.
"""
import os
import json
import subprocess
import threading
import shutil
from pathlib import Path
from datetime import datetime

import toml
import requests
from flask import Flask, render_template, send_from_directory, jsonify, request, redirect, url_for
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

from utils.progress import progress_tracker

# Configuration
HOST = "0.0.0.0"
PORT = 5000
CONFIG_PATH = Path("config.toml")
BACKGROUNDS_VIDEO_PATH = Path("assets/backgrounds/video")
BACKGROUNDS_AUDIO_PATH = Path("assets/backgrounds/audio")
RESULTS_PATH = Path("results")
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi', 'mkv'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a'}

# Ensure directories exist
BACKGROUNDS_VIDEO_PATH.mkdir(parents=True, exist_ok=True)
BACKGROUNDS_AUDIO_PATH.mkdir(parents=True, exist_ok=True)
RESULTS_PATH.mkdir(parents=True, exist_ok=True)

# Configure Flask app
app = Flask(__name__, template_folder="GUI", static_folder="GUI/static")
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload

# Configure SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# Track running generation process
generation_process = None
generation_thread = None


def allowed_video_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


def allowed_audio_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS


def load_config():
    """Load current configuration."""
    if CONFIG_PATH.exists():
        try:
            return toml.load(CONFIG_PATH)
        except Exception as e:
            print(f"Error loading config: {e}")
    return {}


def save_config(config):
    """Save configuration to file."""
    try:
        with open(CONFIG_PATH, 'w') as f:
            toml.dump(config, f)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def get_background_videos():
    """Get list of available background videos."""
    videos = []
    if BACKGROUNDS_VIDEO_PATH.exists():
        for f in BACKGROUNDS_VIDEO_PATH.iterdir():
            if f.is_file() and allowed_video_file(f.name):
                videos.append({
                    'name': f.stem,
                    'filename': f.name,
                    'size': f.stat().st_size,
                    'path': str(f)
                })
    return videos


def get_background_audios():
    """Get list of available background audio tracks."""
    audios = []
    if BACKGROUNDS_AUDIO_PATH.exists():
        for f in BACKGROUNDS_AUDIO_PATH.iterdir():
            if f.is_file() and allowed_audio_file(f.name):
                audios.append({
                    'name': f.stem,
                    'filename': f.name,
                    'size': f.stat().st_size,
                    'path': str(f)
                })
    return audios


def get_generated_videos():
    """Get list of generated videos."""
    videos = []
    if RESULTS_PATH.exists():
        for subreddit_dir in RESULTS_PATH.iterdir():
            if subreddit_dir.is_dir():
                for f in subreddit_dir.iterdir():
                    if f.is_file() and f.suffix.lower() == '.mp4':
                        videos.append({
                            'name': f.stem,
                            'filename': f.name,
                            'subreddit': subreddit_dir.name,
                            'size': f.stat().st_size,
                            'created': datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                            'path': f"/results/{subreddit_dir.name}/{f.name}"
                        })
    return sorted(videos, key=lambda x: x['created'], reverse=True)


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


# ==================== Pages ====================

@app.route("/")
def index():
    """Main dashboard - redirect to settings if not configured."""
    config = load_config()
    if not config:
        return redirect(url_for('settings_page'))
    return render_template("dashboard.html")


@app.route("/settings")
def settings_page():
    """Settings/configuration page."""
    return render_template("settings.html")


@app.route("/backgrounds")
def backgrounds_page():
    """Background videos management page."""
    return render_template("backgrounds.html")


@app.route("/videos")
def videos_page():
    """Generated videos page."""
    return render_template("videos.html")


@app.route("/progress")
def progress_page():
    """Progress tracking page."""
    return render_template("progress.html")


# ==================== API Endpoints ====================

@app.route("/api/config", methods=["GET"])
def api_get_config():
    """Get current configuration."""
    config = load_config()
    # Mask sensitive fields
    if config.get('settings', {}).get('tts', {}).get('qwen_password'):
        config['settings']['tts']['qwen_password'] = '********'
    if config.get('settings', {}).get('tts', {}).get('openai_api_key'):
        config['settings']['tts']['openai_api_key'] = '********'
    return jsonify(config)


@app.route("/api/config", methods=["POST"])
def api_save_config():
    """Save configuration."""
    try:
        data = request.json

        # Load existing config to preserve masked fields
        existing_config = load_config()

        # Build new config
        config = {
            'reddit': {
                'scraper': {
                    'user_agent': data.get('user_agent', 'python:reddit_video_bot:1.0'),
                    'request_delay': float(data.get('request_delay', 2.0))
                },
                'thread': {
                    'subreddit': data.get('subreddit', 'AskReddit'),
                    'post_id': data.get('post_id', ''),
                    'random': data.get('random', True),
                    'max_comment_length': int(data.get('max_comment_length', 500)),
                    'min_comment_length': int(data.get('min_comment_length', 1)),
                    'min_comments': int(data.get('min_comments', 20)),
                    'post_lang': data.get('post_lang', '')
                }
            },
            'ai': {
                'ai_similarity_enabled': data.get('ai_similarity_enabled', False),
                'ai_similarity_keywords': data.get('ai_similarity_keywords', '')
            },
            'settings': {
                'allow_nsfw': data.get('allow_nsfw', False),
                'theme': data.get('theme', 'dark'),
                'times_to_run': int(data.get('times_to_run', 1)),
                'opacity': float(data.get('opacity', 0.9)),
                'storymode': data.get('storymode', False),
                'storymodemethod': int(data.get('storymodemethod', 1)),
                'storymode_max_length': int(data.get('storymode_max_length', 1000)),
                'resolution_w': int(data.get('resolution_w', 1080)),
                'resolution_h': int(data.get('resolution_h', 1920)),
                'zoom': float(data.get('zoom', 1)),
                'channel_name': data.get('channel_name', 'Reddit Tales'),
                'background': {
                    'background_video': data.get('background_video', 'minecraft'),
                    'background_audio': data.get('background_audio', 'lofi'),
                    'background_audio_volume': float(data.get('background_audio_volume', 0.15)),
                    'enable_extra_audio': data.get('enable_extra_audio', False),
                    'background_thumbnail': data.get('background_thumbnail', False)
                },
                'tts': {
                    'voice_choice': data.get('voice_choice', 'qwentts'),
                    'random_voice': data.get('random_voice', True),
                    'silence_duration': float(data.get('silence_duration', 0.3)),
                    'no_emojis': data.get('no_emojis', False),
                    'qwen_api_url': data.get('qwen_api_url', 'http://localhost:8080'),
                    'qwen_email': data.get('qwen_email', ''),
                    'qwen_speaker': data.get('qwen_speaker', 'Vivian'),
                    'qwen_language': data.get('qwen_language', 'English'),
                    'qwen_instruct': data.get('qwen_instruct', 'Warm, friendly, conversational.'),
                    'elevenlabs_voice_name': data.get('elevenlabs_voice_name', 'Bella'),
                    'elevenlabs_api_key': '',
                    'tiktok_voice': data.get('tiktok_voice', 'en_us_001'),
                    'tiktok_sessionid': data.get('tiktok_sessionid', ''),
                    'openai_api_url': data.get('openai_api_url', 'https://api.openai.com/v1/'),
                    'openai_voice_name': data.get('openai_voice_name', 'alloy'),
                    'openai_model': data.get('openai_model', 'tts-1'),
                    'aws_polly_voice': data.get('aws_polly_voice', 'Matthew'),
                    'streamlabs_polly_voice': data.get('streamlabs_polly_voice', 'Matthew')
                }
            }
        }

        # Preserve password if not changed
        if data.get('qwen_password') and data['qwen_password'] != '********':
            config['settings']['tts']['qwen_password'] = data['qwen_password']
        elif existing_config.get('settings', {}).get('tts', {}).get('qwen_password'):
            config['settings']['tts']['qwen_password'] = existing_config['settings']['tts']['qwen_password']
        else:
            config['settings']['tts']['qwen_password'] = ''

        # Preserve API keys if not changed
        if data.get('openai_api_key') and data['openai_api_key'] != '********':
            config['settings']['tts']['openai_api_key'] = data['openai_api_key']
        elif existing_config.get('settings', {}).get('tts', {}).get('openai_api_key'):
            config['settings']['tts']['openai_api_key'] = existing_config['settings']['tts']['openai_api_key']
        else:
            config['settings']['tts']['openai_api_key'] = ''

        if save_config(config):
            return jsonify({'success': True, 'message': 'Configuration saved successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to save configuration'}), 500

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/api/status")
def get_status():
    """Get current progress status."""
    return jsonify(progress_tracker.get_status())


@app.route("/api/backgrounds/video", methods=["GET"])
def api_get_background_videos():
    """Get list of background videos."""
    return jsonify({'videos': get_background_videos()})


@app.route("/api/backgrounds/audio", methods=["GET"])
def api_get_background_audios():
    """Get list of background audio tracks."""
    return jsonify({'audios': get_background_audios()})


@app.route("/api/backgrounds/video", methods=["POST"])
def api_upload_background_video():
    """Upload a background video."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    if file and allowed_video_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = BACKGROUNDS_VIDEO_PATH / filename
        file.save(filepath)
        return jsonify({'success': True, 'message': f'Video "{filename}" uploaded successfully'})

    return jsonify({'success': False, 'message': 'Invalid file type'}), 400


@app.route("/api/backgrounds/audio", methods=["POST"])
def api_upload_background_audio():
    """Upload a background audio track."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    if file and allowed_audio_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = BACKGROUNDS_AUDIO_PATH / filename
        file.save(filepath)
        return jsonify({'success': True, 'message': f'Audio "{filename}" uploaded successfully'})

    return jsonify({'success': False, 'message': 'Invalid file type'}), 400


@app.route("/api/backgrounds/video/<filename>", methods=["DELETE"])
def api_delete_background_video(filename):
    """Delete a background video."""
    filepath = BACKGROUNDS_VIDEO_PATH / secure_filename(filename)
    if filepath.exists():
        filepath.unlink()
        return jsonify({'success': True, 'message': 'Video deleted'})
    return jsonify({'success': False, 'message': 'File not found'}), 404


@app.route("/api/backgrounds/audio/<filename>", methods=["DELETE"])
def api_delete_background_audio(filename):
    """Delete a background audio track."""
    filepath = BACKGROUNDS_AUDIO_PATH / secure_filename(filename)
    if filepath.exists():
        filepath.unlink()
        return jsonify({'success': True, 'message': 'Audio deleted'})
    return jsonify({'success': False, 'message': 'File not found'}), 404


@app.route("/api/videos", methods=["GET"])
def api_get_videos():
    """Get list of generated videos."""
    return jsonify({'videos': get_generated_videos()})


@app.route("/api/generate", methods=["POST"])
def api_generate_video():
    """Start video generation."""
    global generation_process, generation_thread

    if generation_process and generation_process.poll() is None:
        return jsonify({'success': False, 'message': 'Generation already in progress'}), 400

    config = load_config()
    if not config:
        return jsonify({'success': False, 'message': 'Please configure settings first'}), 400

    def run_generation():
        global generation_process
        try:
            generation_process = subprocess.Popen(
                ['python', 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(Path(__file__).parent)
            )
            generation_process.wait()
        except Exception as e:
            print(f"Generation error: {e}")

    generation_thread = threading.Thread(target=run_generation)
    generation_thread.start()

    return jsonify({'success': True, 'message': 'Video generation started'})


@app.route("/api/generate/stop", methods=["POST"])
def api_stop_generation():
    """Stop video generation."""
    global generation_process

    if generation_process and generation_process.poll() is None:
        generation_process.terminate()
        return jsonify({'success': True, 'message': 'Generation stopped'})

    return jsonify({'success': False, 'message': 'No generation in progress'})


@app.route("/api/generate/status", methods=["GET"])
def api_generation_status():
    """Get generation status."""
    global generation_process

    running = generation_process and generation_process.poll() is None
    return jsonify({
        'running': running,
        'progress': progress_tracker.get_status()
    })


@app.route("/api/tts/test", methods=["POST"])
def api_test_tts():
    """Test Qwen TTS connection."""
    try:
        data = request.json
        api_url = data.get('qwen_api_url', '').rstrip('/')
        email = data.get('qwen_email', '')
        password = data.get('qwen_password', '')

        if not api_url or not email or not password:
            return jsonify({'success': False, 'message': 'Missing required fields'})

        # Test authentication
        login_url = f"{api_url}/api/agent/api/auth/login"
        auth_response = requests.post(
            login_url,
            json={'email': email, 'password': password},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        if auth_response.status_code == 200:
            result = auth_response.json()
            if 'access_token' in result:
                return jsonify({'success': True, 'message': 'Authentication successful'})
            else:
                return jsonify({'success': False, 'message': 'Invalid response from server'})
        elif auth_response.status_code == 401:
            return jsonify({'success': False, 'message': 'Invalid credentials'})
        else:
            return jsonify({'success': False, 'message': f'Server error: {auth_response.status_code}'})

    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'message': 'Cannot connect to TTS server'})
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'message': 'Connection timeout'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route("/api/backgrounds", methods=["GET"])
def api_get_all_backgrounds():
    """Get all backgrounds (videos and audio)."""
    return jsonify({
        'videos': get_background_videos(),
        'audios': get_background_audios()
    })


# ==================== Static Files ====================

@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve static files."""
    return send_from_directory("GUI/static", filename)


@app.route("/results/<path:name>")
def results(name):
    """Serve result videos."""
    return send_from_directory("results", name)


@app.route("/preview/<path:name>")
def previews(name):
    """Serve preview images."""
    return send_from_directory("assets/temp", name)


@app.route("/assets/<path:name>")
def assets(name):
    """Serve asset files."""
    return send_from_directory("assets", name)


@app.route("/backgrounds/video/<path:name>")
def serve_background_video(name):
    """Serve background videos."""
    return send_from_directory(BACKGROUNDS_VIDEO_PATH, name)


@app.route("/backgrounds/audio/<path:name>")
def serve_background_audio(name):
    """Serve background audio."""
    return send_from_directory(BACKGROUNDS_AUDIO_PATH, name)


# ==================== SocketIO Events ====================

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


# ==================== Run Server ====================

def run_gui(open_browser=True):
    """Run the GUI server."""
    import webbrowser
    if open_browser:
        webbrowser.open(f"http://localhost:{PORT}", new=2)

    print(f"Reddit Video Maker Bot UI running at http://localhost:{PORT}")
    socketio.run(app, host=HOST, port=PORT, debug=False)


def run_gui_background():
    """Run the GUI server in a background thread."""
    thread = threading.Thread(target=lambda: socketio.run(app, host=HOST, port=PORT, debug=False, use_reloader=False))
    thread.daemon = True
    thread.start()
    return thread


if __name__ == "__main__":
    run_gui()
