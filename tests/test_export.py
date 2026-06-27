"""Tests for ffmpeg subtitle burn-in."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


def _fake_run(args, **kwargs):
    """Return a CompletedProcess (success)."""
    return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")


def test_burn_subtitles_defaults():
    from src.export import burn_subtitles

    video = Path("/v/test.mp4")
    srt = Path("/v/sub.srt")
    output = Path("/v/out.mp4")

    with patch("src.export.subprocess.run", side_effect=_fake_run) as mock:
        burn_subtitles(video, srt, output)

    mock.assert_called_once()
    args = mock.call_args[0][0]
    assert "-i" in args
    i = args.index("-i")
    assert args[i + 1] == str(video)
    assert "-vf" in args
    vf = args[args.index("-vf") + 1]
    assert "subtitles=" + str(srt) in vf
    assert "FontName=Arial" in vf
    assert "FontSize=16" in vf
    assert "Alignment=2" in vf
    assert "-c:a" in args
    assert args[args.index("-c:a") + 1] == "copy"
    assert args[-1] == str(output)


def test_burn_subtitles_custom():
    from src.export import burn_subtitles

    with patch("src.export.subprocess.run", side_effect=_fake_run) as mock:
        burn_subtitles(
            Path("/v.mp4"),
            Path("/v.srt"),
            Path("/v/o.mp4"),
            font_name="Courier New",
            font_size=24,
            position="top",
        )

    vf = mock.call_args[0][0][mock.call_args[0][0].index("-vf") + 1]
    assert "FontName=Courier New" in vf
    assert "FontSize=24" in vf
    assert "Alignment=8" in vf


def test_burn_subtitles_failure():
    from src.export import burn_subtitles

    def _fail(args, **kwargs):
        return subprocess.CompletedProcess(
            args, returncode=1, stdout="", stderr="ffmpeg: error"
        )

    with (
        patch("src.export.subprocess.run", side_effect=_fail),
        pytest.raises(RuntimeError, match="ffmpeg failed"),
    ):
        burn_subtitles(Path("/v.mp4"), Path("/v.srt"), Path("/v/o.mp4"))
