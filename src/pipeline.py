"""UI-free orchestration: copy -> ffmpeg -> transcribe -> write SRT."""
from __future__ import annotations

import shutil
import subprocess
from collections import namedtuple
from datetime import datetime
from pathlib import Path

from src.subtitles import write_srt

Result = namedtuple("Result", "video srt subtitles")


def _log(msg: str):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")


def extract_audio(video_path: Path, audio_path: Path, ffmpeg: str = "ffmpeg") -> Path:
    """Extract 16 kHz mono WAV for Whisper using ffmpeg."""
    cmd = [ffmpeg, "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", str(audio_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (exit {result.returncode}): {result.stderr}")
    return audio_path


def transcribe_video(video_path, engine, working_root, *, audio_extractor=extract_audio, progress_callback=None) -> Result:
    """engine: any object with .transcribe(audio_path) -> list[srt.Subtitle]."""
    def _report(stage, pct):
        if progress_callback:
            progress_callback(stage, pct)

    video_path = Path(video_path)
    work = Path(working_root) / video_path.stem
    work.mkdir(parents=True, exist_ok=True)

    _report("Copying video...", 5)
    _log("Copying video to working directory...")
    video = work / video_path.name
    shutil.copy2(video_path, video)
    _log(f"  Copied to {video}")

    _report("Extracting audio...", 10)
    _log("Extracting audio (16 kHz mono WAV)...")
    audio = work / (video.stem + ".wav")
    audio_extractor(video, audio)
    _log(f"  Audio extracted: {audio}")

    _report("Transcribing...", 15)
    _log("Transcribing with Whisper...")
    
    def _transcribe_progress(pct, msg="Transcribing..."):
        overall_pct = 15 + int(pct * 0.8)
        _report(msg, overall_pct)

    subtitles = engine.transcribe(audio, progress_callback=_transcribe_progress)

    _report("Writing subtitles...", 98)
    _log(f"Writing {len(subtitles)} subtitles to SRT...")
    srt_path = work / (video.stem + ".srt")
    write_srt(srt_path, subtitles)

    _report("Done", 100)
    _log(f"Done - output: {srt_path}")
    return Result(video, srt_path, subtitles)
