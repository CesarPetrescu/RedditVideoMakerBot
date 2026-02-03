# Reddit Video Maker Bot

Automatically generate short-form videos from Reddit posts. Supports multiple TTS engines including Qwen3 TTS.

## Features

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
# Edit config.toml with your credentials

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

# Run the bot
python main.py
```

## Configuration

Create a `config.toml` file in the project root. The bot will prompt you for settings on first run.

### Reddit API Setup

1. Go to [Reddit Apps](https://www.reddit.com/prefs/apps)
2. Create a new app with type "script"
3. Note your `client_id` and `client_secret`

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

All config options can be set via environment variables:

| Variable | Description |
|----------|-------------|
| `REDDIT_CLIENT_ID` | Reddit API client ID |
| `REDDIT_CLIENT_SECRET` | Reddit API client secret |
| `REDDIT_USERNAME` | Reddit username |
| `REDDIT_PASSWORD` | Reddit password |
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
├── reddit/                 # Reddit API
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

## Troubleshooting

### Common Issues

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
