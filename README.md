# Reddit Video Maker Bot

Automatically generate short-form videos from Reddit posts. No Reddit API credentials required.

## Features

- **No Reddit API Keys Needed**: Uses Reddit's public `.json` endpoints (no OAuth required)
- **Multiple TTS Engines**: Qwen3 TTS (default), OpenAI TTS, ElevenLabs, TikTok, Google Translate, AWS Polly
- **Real-time Progress GUI**: Web-based dashboard showing video generation progress with live updates
- **Docker Support**: Fully containerized with docker-compose for easy deployment
- **Background Customization**: Multiple background videos and audio tracks included
- **Story Mode**: Special mode for narrative subreddits (r/nosleep, r/tifu, etc.)
- **AI Content Sorting**: Optional semantic similarity sorting for relevant posts

## Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/elebumm/RedditVideoMakerBot.git
cd RedditVideoMakerBot

# Create your config file
cp config.example.toml config.toml
# Edit config.toml with your TTS settings (no Reddit credentials needed!)

# Start with docker-compose
docker-compose up -d

# View progress at http://localhost:5000
```

## Manual Installation

### Requirements

- Python 3.10, 3.11, or 3.12
- FFmpeg
- Playwright browsers

### Setup

```bash
# Clone repository
git clone https://github.com/elebumm/RedditVideoMakerBot.git
cd RedditVideoMakerBot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install
playwright install-deps

# Download spaCy model (for story mode)
python -m spacy download en_core_web_sm

# Copy and configure
cp config.example.toml config.toml
# Edit config.toml with your settings

# Run the bot
python main.py
```

## Configuration

Create a `config.toml` file in the project root. The bot will prompt you for settings on first run.

### Reddit Settings (No API Keys Required!)

The bot scrapes Reddit's public `.json` endpoints - no API credentials needed:

```toml
[reddit.scraper]
user_agent = "python:reddit_video_bot:1.0"  # Customize to avoid rate limiting
request_delay = 2.0  # Seconds between requests

[reddit.thread]
subreddit = "AskReddit"  # Target subreddit
post_id = ""             # Optional: specific post ID
min_comments = 20        # Minimum comments required
```

**Note**: This approach is subject to Reddit's rate limiting. If you experience 429 errors, increase `request_delay`.

### Qwen TTS Setup (Default)

Qwen TTS requires a running Qwen TTS server:

```toml
[settings.tts]
voice_choice = "qwentts"
qwen_api_url = "http://localhost:8080"
qwen_email = "your_email@example.com"
qwen_password = "your_password"
qwen_speaker = "Vivian"  # Options: Chelsie, Ethan, Vivian, Asher, Aria, Oliver, Emma, Noah, Sophia
qwen_language = "English"
qwen_instruct = "Warm, friendly, conversational."
```

**Qwen TTS API Usage:**

```bash
# 1. Login to get token
TOKEN=$(curl -s http://localhost:8080/api/agent/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"YOUR_PASSWORD"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 2. Generate TTS
curl -s http://localhost:8080/api/qwen-tts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello!", "language": "English", "speaker": "Vivian", "instruct": "Warm, friendly."}' \
  --output output.wav
```

### TTS Options

| Provider | Key | Requirements |
|----------|-----|--------------|
| Qwen TTS | `qwentts` | Qwen TTS server |
| OpenAI | `openai` | API key |
| ElevenLabs | `elevenlabs` | API key |
| TikTok | `tiktok` | Session ID |
| Google Translate | `googletranslate` | None (free) |
| AWS Polly | `awspolly` | AWS credentials |
| Streamlabs Polly | `streamlabspolly` | None (rate limited) |

## Progress GUI

The bot includes a real-time progress tracking GUI.

```bash
# Enable GUI mode
export REDDIT_BOT_GUI=true
python main.py

# Or run GUI standalone
python progress_gui.py
```

Access at: http://localhost:5000

### Features

- Real-time progress updates via WebSocket
- Step-by-step visualization
- Preview images during generation
- Job history tracking

## Docker Deployment

### Using Docker Compose

```yaml
# docker-compose.yml
services:
  reddit-video-bot:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./config.toml:/app/config.toml:ro
      - ./results:/app/results
    environment:
      - REDDIT_BOT_GUI=true
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `REDDIT_SUBREDDIT` | Target subreddit |
| `TTS_VOICE_CHOICE` | TTS provider |
| `QWEN_API_URL` | Qwen TTS server URL |
| `QWEN_EMAIL` | Qwen TTS email |
| `QWEN_PASSWORD` | Qwen TTS password |

## Project Structure

```
RedditVideoMakerBot/
├── main.py                 # Entry point
├── progress_gui.py         # Progress GUI server
├── config.toml             # Configuration file
├── TTS/                    # TTS engine modules
│   ├── qwen_tts.py        # Qwen TTS provider
│   ├── openai_tts.py      # OpenAI TTS provider
│   └── ...
├── video_creation/         # Video generation
├── reddit/                 # Reddit scraper (no-auth)
│   ├── scraper.py         # Public .json endpoint scraper
│   └── subreddit.py       # Thread fetcher
├── utils/                  # Utilities
│   ├── progress.py        # Progress tracking
│   └── settings.py        # Configuration
├── GUI/                    # Web GUI templates
│   ├── progress.html
│   └── static/
├── Dockerfile
└── docker-compose.yml
```

## Output

Generated videos are saved to `results/{subreddit}/`.

## Limitations

### Reddit Scraper Limitations

- **Rate Limiting**: Reddit may throttle or block requests. Increase `request_delay` if needed.
- **~1000 Post Cap**: Reddit listings are capped at ~1000 posts. Run daily for continuous collection.
- **Incomplete Comments**: Large threads may have missing comments (\"more\" placeholders are skipped).
- **Policy Compliance**: Respect Reddit's Terms of Service when using scraped content.

## Troubleshooting

### Common Issues

**Rate Limited (429 errors)**
```toml
# Increase delay in config.toml
[reddit.scraper]
request_delay = 5.0  # Try 5+ seconds
```

**FFmpeg not found**
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

**Playwright browsers missing**
```bash
playwright install
playwright install-deps
```

**TTS authentication failed**
- Verify your Qwen TTS server is running
- Check credentials in config.toml
- Ensure the API URL is correct

## License

[Roboto Fonts](https://fonts.google.com/specimen/Roboto/about) are licensed under [Apache License V2](https://www.apache.org/licenses/LICENSE-2.0)
