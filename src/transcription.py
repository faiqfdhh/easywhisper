"""faster-whisper engine with lazy import."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import srt


def _log(msg: str):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")


class FasterWhisperEngine:
    def __init__(self, model_size="base", language=None, device="cpu", compute_type="int8"):
        self._model_size = model_size
        self._language = language
        self._device = device
        self._compute_type = compute_type
        self._model = None

    def transcribe(self, audio_path: Path) -> list[srt.Subtitle]:
        if self._model is None:
            from time import perf_counter

            from faster_whisper import WhisperModel  # lazy: heavy import

            _log(f"Loading Whisper model '{self._model_size}' on {self._device} ({self._compute_type})...")
            t0 = perf_counter()
            self._model = WhisperModel(
                self._model_size, device=self._device, compute_type=self._compute_type
            )
            elapsed = perf_counter() - t0
            _log(f"Model loaded in {elapsed:.1f}s")

        _log(f"Transcribing {audio_path.name}...")
        segments, info = self._model.transcribe(
            str(audio_path),
            language=self._language,
        )

        _log(f"  Audio duration: {info.duration:.0f}s")
        if info.language:
            _log(f"  Detected language: {info.language} (probability: {info.language_probability:.2f})")

        subtitles = []
        for i, s in enumerate(segments, start=1):
            subtitles.append(
                srt.Subtitle(
                    index=i,
                    start=timedelta(seconds=s.start),
                    end=timedelta(seconds=s.end),
                    content=s.text.strip(),
                )
            )
            if i % 10 == 0 or i == 1:
                _log(f"  Processed segment {i}")
        _log(f"  Done - {len(subtitles)} segments extracted")
        return subtitles
