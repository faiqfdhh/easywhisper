"""Burn subtitles into a video using ffmpeg."""
from __future__ import annotations

import subprocess
from pathlib import Path


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
    # ponytail: relative path + cwd avoids Windows drive-letter colon escaping bugs in the subtitles filter
    vf = f"subtitles={srt_path.name}:force_style='{style}'"
    cmd = [ffmpeg, "-y", "-i", str(video), "-vf", vf, "-c:a", "copy", str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(srt_path.parent))
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (exit {result.returncode}): {result.stderr}")
    return output
