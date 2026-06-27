"""Read and write SRT files using the srt library."""
from __future__ import annotations

from pathlib import Path

import srt


def write_srt(path: Path, subtitles: list[srt.Subtitle]) -> None:
    Path(path).write_text(srt.compose(subtitles), encoding="utf-8")


def read_srt(path: Path) -> list[srt.Subtitle]:
    return list(srt.parse(Path(path).read_text(encoding="utf-8")))
