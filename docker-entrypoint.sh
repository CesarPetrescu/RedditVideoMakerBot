#!/bin/bash
set -e

# Config directory is mounted at /app/config-dir to avoid Docker creating a directory
# when the host file doesn't exist. We use a symlink to maintain compatibility.

CONFIG_DIR="/app/config-dir"
CONFIG_FILE="/app/config.toml"
CONFIG_IN_DIR="$CONFIG_DIR/config.toml"

# Ensure the config directory exists
mkdir -p "$CONFIG_DIR"

# Remove any existing config.toml (file or directory) in /app to start fresh
rm -rf "$CONFIG_FILE" 2>/dev/null || true

# Check if config exists in the mounted directory
if [ -f "$CONFIG_IN_DIR" ]; then
    echo "Using existing config from $CONFIG_IN_DIR"
    # Create symlink so the app can use /app/config.toml
    ln -sf "$CONFIG_IN_DIR" "$CONFIG_FILE"
else
    echo "Creating config.toml from template..."
    echo "Note: No Reddit API credentials required - using public .json endpoints"

    # Create basic config from environment in the mounted directory
    cat > "$CONFIG_IN_DIR" << EOF
# Reddit Video Maker Bot Configuration
# No Reddit API credentials required - uses public .json endpoints

[reddit.scraper]
user_agent = "${REDDIT_USER_AGENT:-python:reddit_video_bot:1.0}"
request_delay = ${REDDIT_REQUEST_DELAY:-2.0}

[reddit.thread]
random = ${REDDIT_RANDOM:-true}
subreddit = "${REDDIT_SUBREDDIT:-AskReddit}"
post_id = "${REDDIT_POST_ID:-}"
max_comment_length = ${MAX_COMMENT_LENGTH:-500}
min_comment_length = ${MIN_COMMENT_LENGTH:-1}
post_lang = "${POST_LANG:-}"
min_comments = ${MIN_COMMENTS:-20}

[ai]
ai_similarity_enabled = ${AI_SIMILARITY_ENABLED:-false}
ai_similarity_keywords = "${AI_SIMILARITY_KEYWORDS:-}"

[settings]
allow_nsfw = ${ALLOW_NSFW:-false}
theme = "${THEME:-dark}"
times_to_run = ${TIMES_TO_RUN:-1}
opacity = ${OPACITY:-0.9}
storymode = ${STORYMODE:-false}
storymodemethod = ${STORYMODEMETHOD:-1}
storymode_max_length = ${STORYMODE_MAX_LENGTH:-1000}
resolution_w = ${RESOLUTION_W:-1080}
resolution_h = ${RESOLUTION_H:-1920}
zoom = ${ZOOM:-1}
channel_name = "${CHANNEL_NAME:-Reddit Tales}"

[settings.background]
background_video = "${BACKGROUND_VIDEO:-minecraft}"
background_audio = "${BACKGROUND_AUDIO:-lofi}"
background_audio_volume = ${BACKGROUND_AUDIO_VOLUME:-0.15}
enable_extra_audio = ${ENABLE_EXTRA_AUDIO:-false}
background_thumbnail = ${BACKGROUND_THUMBNAIL:-false}
background_thumbnail_font_family = "${THUMBNAIL_FONT_FAMILY:-arial}"
background_thumbnail_font_size = ${THUMBNAIL_FONT_SIZE:-96}
background_thumbnail_font_color = "${THUMBNAIL_FONT_COLOR:-255,255,255}"

[settings.tts]
voice_choice = "${TTS_VOICE_CHOICE:-qwentts}"
random_voice = ${TTS_RANDOM_VOICE:-true}
elevenlabs_voice_name = "${ELEVENLABS_VOICE_NAME:-Bella}"
elevenlabs_api_key = "${ELEVENLABS_API_KEY:-}"
aws_polly_voice = "${AWS_POLLY_VOICE:-Matthew}"
streamlabs_polly_voice = "${STREAMLABS_POLLY_VOICE:-Matthew}"
tiktok_voice = "${TIKTOK_VOICE:-en_us_001}"
tiktok_sessionid = "${TIKTOK_SESSIONID:-}"
silence_duration = ${TTS_SILENCE_DURATION:-0.3}
no_emojis = ${TTS_NO_EMOJIS:-false}
openai_api_url = "${OPENAI_API_URL:-https://api.openai.com/v1/}"
openai_api_key = "${OPENAI_API_KEY:-}"
openai_voice_name = "${OPENAI_VOICE_NAME:-alloy}"
openai_model = "${OPENAI_MODEL:-tts-1}"
qwen_api_url = "${QWEN_API_URL:-http://localhost:8080}"
qwen_email = "${QWEN_EMAIL:-}"
qwen_password = "${QWEN_PASSWORD:-}"
qwen_speaker = "${QWEN_SPEAKER:-Vivian}"
qwen_language = "${QWEN_LANGUAGE:-English}"
qwen_instruct = "${QWEN_INSTRUCT:-Warm, friendly, conversational.}"
EOF
    echo "Config file created successfully!"

    # Create symlink so the app can use /app/config.toml
    ln -sf "$CONFIG_IN_DIR" "$CONFIG_FILE"
fi

# Execute the command passed to docker run
exec "$@"
