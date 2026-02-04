"""
Progress tracking module for Reddit Video Maker Bot.
Provides real-time progress updates via WebSocket for the GUI.
"""
import os
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Callable
from enum import Enum
from pathlib import Path


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Step:
    id: str
    name: str
    description: str
    status: StepStatus = StepStatus.PENDING
    progress: float = 0.0
    message: str = ""
    preview_path: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "preview_path": self.preview_path,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "duration": (self.completed_at - self.started_at) if self.completed_at and self.started_at else None,
        }


@dataclass
class VideoJob:
    id: str
    reddit_id: str
    title: str
    subreddit: str
    status: StepStatus = StepStatus.PENDING
    steps: List[Step] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    output_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self):
        return {
            "id": self.id,
            "reddit_id": self.reddit_id,
            "title": self.title,
            "subreddit": self.subreddit,
            "status": self.status.value,
            "steps": [step.to_dict() for step in self.steps],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "output_path": self.output_path,
            "thumbnail_path": self.thumbnail_path,
            "error": self.error,
            "overall_progress": self.get_overall_progress(),
        }

    def get_overall_progress(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return (completed / len(self.steps)) * 100


class ProgressTracker:
    """
    Singleton progress tracker that manages video generation jobs and steps.
    Provides callbacks for real-time GUI updates.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if ProgressTracker._initialized:
            return
        ProgressTracker._initialized = True

        self.current_job: Optional[VideoJob] = None
        self.job_history: List[VideoJob] = []
        self._update_callbacks: List[Callable] = []
        self._preview_dir = Path("assets/temp/previews")
        self._preview_dir.mkdir(parents=True, exist_ok=True)

    def add_update_callback(self, callback: Callable):
        """Register a callback function to be called on progress updates."""
        self._update_callbacks.append(callback)

    def remove_update_callback(self, callback: Callable):
        """Remove a callback function."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)

    def _notify_update(self):
        """Notify all registered callbacks of a progress update."""
        data = self.get_status()
        for callback in self._update_callbacks:
            try:
                callback(data)
            except Exception as e:
                print(f"Error in progress callback: {e}")

    def start_job(self, reddit_id: str, title: str, subreddit: str) -> VideoJob:
        """Start a new video generation job."""
        job = VideoJob(
            id=f"job_{int(time.time())}_{reddit_id}",
            reddit_id=reddit_id,
            title=title,
            subreddit=subreddit,
            status=StepStatus.IN_PROGRESS,
            steps=self._create_default_steps(),
        )
        self.current_job = job
        self._notify_update()
        return job

    def _create_default_steps(self) -> List[Step]:
        """Create the default pipeline steps."""
        return [
            Step(
                id="fetch_reddit",
                name="Fetch Reddit Post",
                description="Fetching post and comments from Reddit",
            ),
            Step(
                id="generate_tts",
                name="Generate Audio",
                description="Converting text to speech using Qwen TTS",
            ),
            Step(
                id="capture_screenshots",
                name="Capture Screenshots",
                description="Taking screenshots of Reddit comments",
            ),
            Step(
                id="download_background",
                name="Download Background",
                description="Downloading and preparing background video/audio",
            ),
            Step(
                id="process_background",
                name="Process Background",
                description="Chopping background to fit video length",
            ),
            Step(
                id="compose_video",
                name="Compose Video",
                description="Combining all elements into final video",
            ),
            Step(
                id="finalize",
                name="Finalize",
                description="Final processing and cleanup",
            ),
        ]

    def start_step(self, step_id: str, message: str = ""):
        """Mark a step as in progress."""
        if not self.current_job:
            return

        for step in self.current_job.steps:
            if step.id == step_id:
                step.status = StepStatus.IN_PROGRESS
                step.started_at = time.time()
                step.message = message
                step.progress = 0
                break

        self._notify_update()

    def update_step_progress(self, step_id: str, progress: float, message: str = ""):
        """Update the progress of a step."""
        if not self.current_job:
            return

        for step in self.current_job.steps:
            if step.id == step_id:
                step.progress = min(100, max(0, progress))
                if message:
                    step.message = message
                break

        self._notify_update()

    def set_step_preview(self, step_id: str, preview_path: str):
        """Set a preview image/video for a step."""
        if not self.current_job:
            return

        for step in self.current_job.steps:
            if step.id == step_id:
                step.preview_path = preview_path
                break

        self._notify_update()

    def complete_step(self, step_id: str, message: str = ""):
        """Mark a step as completed."""
        if not self.current_job:
            return

        for step in self.current_job.steps:
            if step.id == step_id:
                step.status = StepStatus.COMPLETED
                step.completed_at = time.time()
                step.progress = 100
                if message:
                    step.message = message
                break

        self._notify_update()

    def fail_step(self, step_id: str, error: str):
        """Mark a step as failed."""
        if not self.current_job:
            return

        for step in self.current_job.steps:
            if step.id == step_id:
                step.status = StepStatus.FAILED
                step.completed_at = time.time()
                step.error = error
                step.message = f"Failed: {error}"
                break

        self.current_job.status = StepStatus.FAILED
        self.current_job.error = error
        self._notify_update()

    def skip_step(self, step_id: str, reason: str = ""):
        """Mark a step as skipped."""
        if not self.current_job:
            return

        for step in self.current_job.steps:
            if step.id == step_id:
                step.status = StepStatus.SKIPPED
                step.completed_at = time.time()
                step.message = reason or "Skipped"
                break

        self._notify_update()

    def complete_job(self, output_path: str, thumbnail_path: Optional[str] = None):
        """Mark the current job as completed."""
        if not self.current_job:
            return

        self.current_job.status = StepStatus.COMPLETED
        self.current_job.completed_at = time.time()
        self.current_job.output_path = output_path
        self.current_job.thumbnail_path = thumbnail_path

        self.job_history.append(self.current_job)
        self._notify_update()

    def fail_job(self, error: str):
        """Mark the current job as failed."""
        if not self.current_job:
            return

        self.current_job.status = StepStatus.FAILED
        self.current_job.completed_at = time.time()
        self.current_job.error = error

        self.job_history.append(self.current_job)
        self._notify_update()

    def get_status(self) -> dict:
        """Get the current status of all jobs."""
        return {
            "current_job": self.current_job.to_dict() if self.current_job else None,
            "job_history": [job.to_dict() for job in self.job_history[-10:]],  # Last 10 jobs
        }

    def get_current_step(self) -> Optional[Step]:
        """Get the currently active step."""
        if not self.current_job:
            return None

        for step in self.current_job.steps:
            if step.status == StepStatus.IN_PROGRESS:
                return step
        return None


# Global progress tracker instance
progress_tracker = ProgressTracker()
