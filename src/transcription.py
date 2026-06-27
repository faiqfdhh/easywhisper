"""faster-whisper engine with lazy import."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import srt


class FasterWhisperEngine:
    def __init__(self, model_size="base", language=None, device="cpu", compute_type="int8"):
        self._model_size = model_size
        self._language = language
        self._device = device
        self._compute_type = compute_type
        self._model = None

    def transcribe(self, audio_path: Path) -> list[srt.Subtitle]:
        if self._model is None:
            from faster_whisper import WhisperModel  # lazy: heavy import

            self._model = WhisperModel(
                self._model_size, device=self._device, compute_type=self._compute_type
            )
        segments, _info = self._model.transcribe(str(audio_path), language=self._language)
        return [
            srt.Subtitle(
                index=i,
                start=timedelta(seconds=s.start),
                end=timedelta(seconds=s.end),
                content=s.text.strip(),
            )
            for i, s in enumerate(segments, start=1)
        ]
