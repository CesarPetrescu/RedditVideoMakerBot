#!/usr/bin/env python
"""
Reddit Video Maker Bot
Generates short-form videos from Reddit posts with Qwen TTS.
"""
import math
import os
import sys
from os import name
from pathlib import Path
from subprocess import Popen
from typing import Dict, NoReturn, Optional

from prawcore import ResponseException

from reddit.subreddit import get_subreddit_threads
from utils import settings
from utils.cleanup import cleanup
from utils.console import print_markdown, print_step, print_substep
from utils.ffmpeg_install import ffmpeg_install
from utils.id import extract_id
from utils.version import checkversion
from utils.progress import progress_tracker
from video_creation.background import (
    chop_background,
    download_background_audio,
    download_background_video,
    get_background_config,
)
from video_creation.final_video import make_final_video
from video_creation.screenshot_downloader import get_screenshots_of_reddit_posts
from video_creation.voices import save_text_to_mp3

__VERSION__ = "4.0.0"

# Check if GUI mode is enabled
GUI_MODE = os.environ.get("REDDIT_BOT_GUI", "false").lower() == "true"

print(
    """
██████╗ ███████╗██████╗ ██████╗ ██╗████████╗    ██╗   ██╗██╗██████╗ ███████╗ ██████╗     ███╗   ███╗ █████╗ ██╗  ██╗███████╗██████╗
██╔══██╗██╔════╝██╔══██╗██╔══██╗██║╚══██╔══╝    ██║   ██║██║██╔══██╗██╔════╝██╔═══██╗    ████╗ ████║██╔══██╗██║ ██╔╝██╔════╝██╔══██╗
██████╔╝█████╗  ██║  ██║██║  ██║██║   ██║       ██║   ██║██║██║  ██║█████╗  ██║   ██║    ██╔████╔██║███████║█████╔╝ █████╗  ██████╔╝
██╔══██╗██╔══╝  ██║  ██║██║  ██║██║   ██║       ╚██╗ ██╔╝██║██║  ██║██╔══╝  ██║   ██║    ██║╚██╔╝██║██╔══██║██╔═██╗ ██╔══╝  ██╔══██╗
██║  ██║███████╗██████╔╝██████╔╝██║   ██║        ╚████╔╝ ██║██████╔╝███████╗╚██████╔╝    ██║ ╚═╝ ██║██║  ██║██║  ██╗███████╗██║  ██║
╚═╝  ╚═╝╚══════╝╚═════╝ ╚═════╝ ╚═╝   ╚═╝         ╚═══╝  ╚═╝╚═════╝ ╚══════╝ ╚═════╝     ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
"""
)
print_markdown(
    "### Reddit Video Maker Bot v4.0 - Now with Qwen TTS and Progress GUI!"
)
checkversion(__VERSION__)

reddit_id: str
reddit_object: Dict[str, str | list]


def main(POST_ID: Optional[str] = None) -> None:
    """Main video generation function with progress tracking."""
    global reddit_id, reddit_object

    try:
        # Step 1: Fetch Reddit Post
        progress_tracker.start_step("fetch_reddit", "Connecting to Reddit API...")

        reddit_object = get_subreddit_threads(POST_ID)
        reddit_id = extract_id(reddit_object)

        # Start job tracking
        progress_tracker.start_job(
            reddit_id=reddit_id,
            title=reddit_object.get("thread_title", "Unknown"),
            subreddit=reddit_object.get("subreddit", "Unknown"),
        )

        progress_tracker.update_step_progress("fetch_reddit", 50, f"Found post: {reddit_id}")
        print_substep(f"Thread ID is {reddit_id}", style="bold blue")
        progress_tracker.complete_step("fetch_reddit", f"Loaded {len(reddit_object.get('comments', []))} comments")

        # Step 2: Generate TTS Audio
        progress_tracker.start_step("generate_tts", "Initializing TTS engine...")
        length, number_of_comments = save_text_to_mp3(reddit_object)
        length = math.ceil(length)
        progress_tracker.complete_step("generate_tts", f"Generated audio for {number_of_comments} comments ({length}s)")

        # Step 3: Capture Screenshots
        progress_tracker.start_step("capture_screenshots", "Launching browser...")
        get_screenshots_of_reddit_posts(reddit_object, number_of_comments)

        # Set preview for screenshots
        screenshot_preview = f"assets/temp/{reddit_id}/png/title.png"
        if os.path.exists(screenshot_preview):
            progress_tracker.set_step_preview("capture_screenshots", f"/assets/temp/{reddit_id}/png/title.png")

        progress_tracker.complete_step("capture_screenshots", f"Captured {number_of_comments + 1} screenshots")

        # Step 4: Download Background
        progress_tracker.start_step("download_background", "Loading background config...")
        bg_config = {
            "video": get_background_config("video"),
            "audio": get_background_config("audio"),
        }
        progress_tracker.update_step_progress("download_background", 30, "Downloading video background...")
        download_background_video(bg_config["video"])
        progress_tracker.update_step_progress("download_background", 70, "Downloading audio background...")
        download_background_audio(bg_config["audio"])
        progress_tracker.complete_step("download_background", "Background assets ready")

        # Step 5: Process Background
        progress_tracker.start_step("process_background", "Chopping background to fit...")
        chop_background(bg_config, length, reddit_object)
        progress_tracker.complete_step("process_background", f"Background prepared for {length}s video")

        # Step 6: Compose Video
        progress_tracker.start_step("compose_video", "Starting video composition...")
        make_final_video(number_of_comments, length, reddit_object, bg_config)
        progress_tracker.complete_step("compose_video", "Video rendered successfully")

        # Step 7: Finalize
        progress_tracker.start_step("finalize", "Cleaning up temporary files...")
        subreddit = reddit_object.get("subreddit", "Unknown")
        output_path = f"/results/{subreddit}/"
        progress_tracker.complete_step("finalize", "Video generation complete!")

        # Mark job as completed
        progress_tracker.complete_job(output_path=output_path)
        print_step("Video generation completed successfully!")

    except Exception as e:
        # Handle errors and update progress
        current_step = progress_tracker.get_current_step()
        if current_step:
            progress_tracker.fail_step(current_step.id, str(e))
        progress_tracker.fail_job(str(e))
        raise


def run_many(times: int) -> None:
    """Run video generation multiple times."""
    for x in range(1, times + 1):
        print_step(
            f'on the {x}{("th", "st", "nd", "rd", "th", "th", "th", "th", "th", "th")[x % 10]} iteration of {times}'
        )
        main()
        Popen("cls" if name == "nt" else "clear", shell=True).wait()


def shutdown() -> NoReturn:
    """Clean up and exit."""
    if "reddit_id" in globals():
        print_markdown("## Clearing temp files")
        cleanup(reddit_id)

    print("Exiting...")
    sys.exit()


def start_gui_server():
    """Start the progress GUI server in background."""
    from progress_gui import run_gui_background
    print_step("Starting Progress GUI server...")
    run_gui_background()
    print_substep("Progress GUI available at http://localhost:5000", style="bold green")


if __name__ == "__main__":
    if sys.version_info.major != 3 or sys.version_info.minor not in [10, 11, 12]:
        print(
            "This program requires Python 3.10, 3.11, or 3.12. "
            "Please install a compatible Python version and try again."
        )
        sys.exit()

    ffmpeg_install()
    directory = Path().absolute()
    config = settings.check_toml(
        f"{directory}/utils/.config.template.toml", f"{directory}/config.toml"
    )
    config is False and sys.exit()

    # Validate Qwen TTS settings if selected
    if config["settings"]["tts"]["voice_choice"].lower() == "qwentts":
        if not config["settings"]["tts"].get("qwen_email") or not config["settings"]["tts"].get("qwen_password"):
            print_substep(
                "Qwen TTS requires 'qwen_email' and 'qwen_password' in config! "
                "Please configure these settings.",
                "bold red",
            )
            sys.exit()

    # Validate TikTok settings if selected
    if (
        not settings.config["settings"]["tts"]["tiktok_sessionid"]
        or settings.config["settings"]["tts"]["tiktok_sessionid"] == ""
    ) and config["settings"]["tts"]["voice_choice"].lower() == "tiktok":
        print_substep(
            "TikTok voice requires a sessionid! Check documentation on how to obtain one.",
            "bold red",
        )
        sys.exit()

    # Start GUI server if enabled
    if GUI_MODE:
        start_gui_server()

    try:
        if config["reddit"]["thread"]["post_id"]:
            for index, post_id in enumerate(config["reddit"]["thread"]["post_id"].split("+")):
                index += 1
                print_step(
                    f'on the {index}{("st" if index % 10 == 1 else ("nd" if index % 10 == 2 else ("rd" if index % 10 == 3 else "th")))} post of {len(config["reddit"]["thread"]["post_id"].split("+"))}'
                )
                main(post_id)
                Popen("cls" if name == "nt" else "clear", shell=True).wait()
        elif config["settings"]["times_to_run"]:
            run_many(config["settings"]["times_to_run"])
        else:
            main()
    except KeyboardInterrupt:
        shutdown()
    except ResponseException:
        print_markdown("## Invalid credentials")
        print_markdown("Please check your credentials in the config.toml file")
        shutdown()
    except Exception as err:
        config["settings"]["tts"]["tiktok_sessionid"] = "REDACTED"
        config["settings"]["tts"]["elevenlabs_api_key"] = "REDACTED"
        config["settings"]["tts"]["openai_api_key"] = "REDACTED"
        config["settings"]["tts"]["qwen_password"] = "REDACTED"
        print_step(
            f"Sorry, something went wrong! Try again, and feel free to report this issue on GitHub.\n"
            f"Version: {__VERSION__} \n"
            f"Error: {err} \n"
            f'Config: {config["settings"]}'
        )
        raise err
