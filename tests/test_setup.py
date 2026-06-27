"""Tests for dependency checker."""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


def _fake_ffmpeg_ok(args, **kwargs):
    import subprocess
    return subprocess.CompletedProcess(
        args, returncode=0, stdout="ffmpeg version 6.0 Copyright (c) ...\n", stderr=""
    )


def _fake_ffmpeg_fail(args, **kwargs):
    import subprocess
    return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="error")


def test_check_python_ok():
    from src.setup import check_python
    ok, msg = check_python()
    assert ok is True
    assert "Python" in msg
    assert "OK" in msg


@patch("src.setup.subprocess.run", side_effect=_fake_ffmpeg_ok)
def test_check_ffmpeg_ok(mock_run):
    from src.setup import check_ffmpeg
    ok, msg = check_ffmpeg()
    assert ok is True
    assert "ffmpeg" in msg


@patch("src.setup.subprocess.run", side_effect=_fake_ffmpeg_fail)
def test_check_ffmpeg_fails(mock_run):
    from src.setup import check_ffmpeg
    ok, msg = check_ffmpeg()
    assert ok is False


@patch("src.setup.subprocess.run", side_effect=FileNotFoundError)
def test_check_ffmpeg_not_found(mock_run):
    from src.setup import check_ffmpeg
    ok, msg = check_ffmpeg()
    assert ok is False
    assert "not found" in msg


@patch("src.setup.importlib.import_module")
def test_check_package_ok(mock_import):
    from src.setup import check_package
    ok, msg = check_package("foo")
    assert ok is True
    assert "OK" in msg


@patch("src.setup.importlib.import_module", side_effect=ImportError)
def test_check_package_missing(mock_import):
    from src.setup import check_package
    ok, msg = check_package("foo")
    assert ok is False
    assert "not installed" in msg


@patch("src.setup.check_python")
@patch("src.setup.check_ffmpeg")
@patch("src.setup.check_package")
def test_check_all_returns_expected_keys(mock_pkg, mock_ff, mock_py):
    mock_py.return_value = (True, "Python OK")
    mock_ff.return_value = (True, "ffmpeg OK")
    mock_pkg.return_value = (True, "srt OK")

    from src.setup import check_all
    results = check_all()
    names = {c["name"] for c in results}
    expected = {"Python", "ffmpeg", "PySide6", "faster-whisper", "srt"}
    assert names == expected
    for c in results:
        assert "ok" in c
        assert "message" in c
