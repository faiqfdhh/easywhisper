"""Burn subtitles into a video using ffmpeg."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _escape_filter_path(p: Path) -> str:
    s = p.as_posix()
    s = s.replace("\\", "\\\\")
    s = s.replace(":", "\\:")
    s = s.replace(",", "\\,")
    return s


def burn_subtitles(
    video: Path,
    srt_path: Path,
    output: Path,
    *,
    font_name: str = "Arial",
    font_size: int = 16,
    position: str = "bottom",
    ffmpeg: str = "ffmpeg",
) -> Path:
    if position not in ("bottom", "top"):
        raise ValueError(f"position must be 'bottom' or 'top', got {position!r}")
    alignment = "2" if position == "bottom" else "8"
    style = f"FontName={font_name},FontSize={font_size},Alignment={alignment}"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video),
        "-vf",
        f"subtitles={_escape_filter_path(srt_path)}:force_style='{style}'",
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
