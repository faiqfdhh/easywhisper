from __future__ import annotations

import importlib
import subprocess
import sys


def check_python() -> tuple[bool, str]:
    ok = sys.version_info >= (3, 10)
    v = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return ok, f"Python {v}" + (" OK" if ok else " (need >= 3.10)")


def check_ffmpeg() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            line = result.stdout.split("\n")[0]
            return True, line
        return False, "ffmpeg returned an error"
    except FileNotFoundError:
        return False, "ffmpeg not found on PATH"
    except subprocess.TimeoutExpired:
        return False, "ffmpeg timed out"


def check_package(name: str, import_name: str | None = None) -> tuple[bool, str]:
    try:
        importlib.import_module(import_name or name)
        return True, f"{name} OK"
    except ImportError:
        return False, f"{name} not installed"


def check_cuda() -> tuple[bool, str]:
    try:
        import torch
        if torch.cuda.is_available():
            return True, "CUDA available"
        return False, "CUDA not available (CPU mode)"
    except ImportError:
        return False, "PyTorch not found"


def check_all() -> list[dict]:
    checks: list[dict] = []
    for name, ok, msg in [
        ("Python", *check_python()),
        ("ffmpeg", *check_ffmpeg()),
        ("PySide6", *check_package("PySide6")),
        ("faster-whisper", *check_package("faster-whisper", "faster_whisper")),
        ("srt", *check_package("srt")),
    ]:
        checks.append({"name": name, "ok": ok, "message": msg})
    return checks
