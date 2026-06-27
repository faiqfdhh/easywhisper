"""Burn subtitles into a video using ffmpeg."""
from __future__ import annotations

import subprocess
from pathlib import Path


def burn_subtitles(
    video: Path,
    srt: Path,
    output: Path,
    *,
    font_name: str = "Arial",
    font_size: int = 16,
    position: str = "bottom",
    ffmpeg: str = "ffmpeg",
) -> Path:
    alignment = "2" if position == "bottom" else "8"
    style = f"FontName={font_name},FontSize={font_size},Alignment={alignment}"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video),
        "-vf",
        f"subtitles={srt}:force_style='{style}'",
        "-c:a",
        "copy",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}): {result.stderr}"
        )
    return output
