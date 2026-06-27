from datetime import timedelta
from pathlib import Path

import pytest
import srt

import src.pipeline as pipeline
from src.pipeline import transcribe_video
from src.subtitles import read_srt


class FakeEngine:
    def __init__(self):
        self.audio = None

    def transcribe(self, audio_path):
        self.audio = audio_path
        return [srt.Subtitle(index=1, start=timedelta(0), end=timedelta(seconds=1), content="hi")]


def test_transcribe_video_full_flow(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    engine = FakeEngine()

    def fake_extract(video_in, audio_out):
        Path(audio_out).write_bytes(b"wav")
        return audio_out

    result = transcribe_video(video, engine, tmp_path / "work", audio_extractor=fake_extract)

    assert result.video.exists() and result.video.name == "clip.mp4"
    assert engine.audio == result.video.parent / "clip.wav"
    assert result.subtitles[0].content == "hi"
    assert read_srt(result.srt) == result.subtitles


def test_extract_audio_raises_on_ffmpeg_failure(monkeypatch, tmp_path):
    class FakeCompleted:
        returncode = 1
        stderr = "boom"

    monkeypatch.setattr(pipeline.subprocess, "run", lambda cmd, **kw: FakeCompleted())
    with pytest.raises(RuntimeError):
        pipeline.extract_audio(tmp_path / "in.mp4", tmp_path / "out.wav")
