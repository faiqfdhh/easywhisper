"""UI-free orchestration: copy -> ffmpeg -> transcribe -> write SRT."""
from __future__ import annotations

import shutil
import subprocess
from collections import namedtuple
from pathlib import Path

from src.subtitles import write_srt

Result = namedtuple("Result", "video srt subtitles")


def extract_audio(video_path: Path, audio_path: Path, ffmpeg: str = "ffmpeg") -> Path:
    """Extract 16 kHz mono WAV (what Whisper expects) via ffmpeg."""
    cmd = [ffmpeg, "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", str(audio_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (exit {result.returncode}): {result.stderr}")
    return audio_path


def transcribe_video(video_path, engine, working_root, *, audio_extractor=extract_audio) -> Result:
    """engine: any object with .transcribe(audio_path) -> list[srt.Subtitle]."""
    video_path = Path(video_path)
    work = Path(working_root) / video_path.stem
    work.mkdir(parents=True, exist_ok=True)

    video = work / video_path.name
    shutil.copy2(video_path, video)

    audio = work / (video.stem + ".wav")
    audio_extractor(video, audio)

    subtitles = engine.transcribe(audio)

    srt_path = work / (video.stem + ".srt")
    write_srt(srt_path, subtitles)
    return Result(video, srt_path, subtitles)
