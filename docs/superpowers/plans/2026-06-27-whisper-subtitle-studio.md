# Whisper Subtitle Studio Implementation Plan (minimal)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A lightweight local desktop app that transcribes a video into editable SRT subtitles using faster-whisper, with a synced player and inline cue editor in one window.

**Architecture:** Four `src` modules. `transcription.py` (faster-whisper engine, lazy-imported), `subtitles.py` (SRT read/write — thin wrappers over the `srt` library), `pipeline.py` (UI-free orchestration: copy → ffmpeg → transcribe → write; injects the audio extractor so it tests without ffmpeg), `app.py` (all PySide6 UI + entry point). The cue/segment model is `srt.Subtitle` (already a dependency), not a custom class. The engine is duck-typed — any object with `.transcribe(audio_path) -> list[srt.Subtitle]` — so it stays swappable without a formal interface.

**Tech Stack:** Python 3.10+, PySide6 (QMediaPlayer), faster-whisper, `srt`, ffmpeg (subprocess), pyproject.toml.

## Global Constraints

- Python 3.10+ (`X | None` syntax fine on 3.10).
- Runtime deps exactly: `PySide6`, `faster-whisper`, `srt`. Nothing else.
- No cloud calls, no API keys. Only network is the one-time faster-whisper model download.
- ffmpeg assumed on PATH; invoked only as a subprocess. Documented in README.
- Cross-platform: Windows, macOS, Linux.
- UI holds no business logic — renders state, emits/handles signals only.
- License: MIT preserving the upstream OpenAI Whisper notice. README credits OpenAI Whisper + faster-whisper.
- Import root is `src`; console entry point `easywhisper = "src.app:main"`.

---

## File Structure

```
easywhisper/
├── src/
│   ├── __init__.py
│   ├── transcription.py   # FasterWhisperEngine (lazy faster_whisper import)
│   ├── subtitles.py       # read_srt / write_srt (srt lib wrappers)
│   ├── pipeline.py        # extract_audio + transcribe_video + Result
│   └── app.py             # PySide6 player + editor + window + main()
├── tests/
│   ├── __init__.py
│   ├── test_subtitles.py
│   └── test_pipeline.py
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
└── requirements-dev.txt
```

Why this small: cue model = `srt.Subtitle`; engine interface = duck typing (one impl, no Protocol); timestamps = `srt` lib helpers; media copy + ffmpeg live in `pipeline.py`; all UI in `app.py`. Skipped abstractions add when a second engine or export format actually arrives.

---

### Task 1: Scaffold, packaging, license

**Files:**
- Create: `.gitignore`, `LICENSE`, `pyproject.toml`, `requirements-dev.txt`
- Create: `src/__init__.py`, `tests/__init__.py` (empty)

**Interfaces:**
- Consumes: nothing.
- Produces: importable `src` package; `pip install -e .[dev]` works; `pytest` collects (exit 5, no tests yet).

- [ ] **Step 1: Init git**

```bash
git init
```

- [ ] **Step 2: `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
build/
dist/
.venv/
venv/
.pytest_cache/
*.spec
work/
*.srt
*.wav
.DS_Store
```

- [ ] **Step 3: `LICENSE` (MIT + preserved Whisper notice)**

```text
MIT License

Copyright (c) 2026 Whisper Subtitle Studio contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

This software builds on OpenAI Whisper and faster-whisper. The original
OpenAI Whisper license notice is preserved below.

Copyright (c) 2022 OpenAI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "easywhisper"
version = "0.1.0"
description = "Lightweight local desktop app to transcribe video into editable SRT subtitles using faster-whisper."
readme = "README.md"
requires-python = ">=3.10"
license = { file = "LICENSE" }
dependencies = [
    "PySide6>=6.6",
    "faster-whisper>=1.0",
    "srt>=3.5",
]

[project.optional-dependencies]
dev = ["pytest>=7.4"]

[project.scripts]
easywhisper = "src.app:main"

[tool.setuptools]
packages = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 5: `requirements-dev.txt`**

```text
-e .[dev]
```

- [ ] **Step 6: Empty `__init__.py` files**

Create empty: `src/__init__.py`, `tests/__init__.py`.

- [ ] **Step 7: Install + verify**

Run: `pip install -e .[dev]`
Then: `pytest -q`
Expected: installs cleanly; "no tests ran" (exit 5) — fine here.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: scaffold repo, packaging, license"
```

---

### Task 2: Subtitle read/write

**Files:**
- Create: `src/subtitles.py`
- Test: `tests/test_subtitles.py`

**Interfaces:**
- Consumes: the `srt` library.
- Produces:
  - `write_srt(path: Path, subtitles: list[srt.Subtitle]) -> None`
  - `read_srt(path: Path) -> list[srt.Subtitle]`
  - Cue model is `srt.Subtitle(index, start: timedelta, end: timedelta, content)` — no custom class.

- [ ] **Step 1: Write the failing test**

`tests/test_subtitles.py`:

```python
from datetime import timedelta

import srt

from src.subtitles import read_srt, write_srt


def test_round_trip(tmp_path):
    subs = [
        srt.Subtitle(index=1, start=timedelta(0), end=timedelta(seconds=1.5), content="hello"),
        srt.Subtitle(index=2, start=timedelta(seconds=2), end=timedelta(seconds=3.25), content="world"),
    ]
    path = tmp_path / "subs.srt"
    write_srt(path, subs)
    assert path.exists()
    assert read_srt(path) == subs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_subtitles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.subtitles'`.

- [ ] **Step 3: Write minimal implementation**

`src/subtitles.py`:

```python
"""SRT read/write. The cue model is srt.Subtitle; this is the whole module."""
from __future__ import annotations

from pathlib import Path

import srt


def write_srt(path: Path, subtitles: list[srt.Subtitle]) -> None:
    Path(path).write_text(srt.compose(subtitles), encoding="utf-8")


def read_srt(path: Path) -> list[srt.Subtitle]:
    return list(srt.parse(Path(path).read_text(encoding="utf-8")))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_subtitles.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/subtitles.py tests/test_subtitles.py
git commit -m "feat: SRT read/write over srt library"
```

---

### Task 3: Pipeline (copy + ffmpeg + orchestration)

**Files:**
- Create: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: stdlib `shutil`, `subprocess`; `write_srt` from `src/subtitles.py`; the `srt` library (return type).
- Produces:
  - `Result(video: Path, srt: Path, subtitles: list[srt.Subtitle])` — `namedtuple`.
  - `extract_audio(video_path: Path, audio_path: Path, ffmpeg: str = "ffmpeg") -> Path` — 16 kHz mono WAV; raises `RuntimeError` on non-zero exit.
  - `transcribe_video(video_path, engine, working_root, *, audio_extractor=extract_audio) -> Result` — `engine` is any object with `.transcribe(audio_path) -> list[srt.Subtitle]`. Flow: working dir `working_root/<stem>` → copy video → extract `<stem>.wav` → `engine.transcribe` → write `<stem>.srt`. `audio_extractor` injected so tests skip ffmpeg.

- [ ] **Step 1: Write the failing test**

`tests/test_pipeline.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.pipeline'`.

- [ ] **Step 3: Write minimal implementation**

`src/pipeline.py`:

```python
"""UI-free orchestration: copy -> ffmpeg -> transcribe -> write SRT."""
from __future__ import annotations

import shutil
import subprocess
from collections import namedtuple
from pathlib import Path

from src.subtitles import write_srt

Result = namedtuple("Result", "video srt subtitles")


def extract_audio(video_path: Path, audio_path: Path, ffmpeg: str = "ffmpeg") -> Path:
    """Extract 16 kHz mono WAV (what Whisper expects) via ffmpeg."""
    cmd = [ffmpeg, "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", str(audio_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (exit {result.returncode}): {result.stderr}")
    return audio_path


def transcribe_video(video_path, engine, working_root, *, audio_extractor=extract_audio) -> Result:
    """engine: any object with .transcribe(audio_path) -> list[srt.Subtitle]."""
    video_path = Path(video_path)
    work = Path(working_root) / video_path.stem
    work.mkdir(parents=True, exist_ok=True)

    video = work / video_path.name
    shutil.copy2(video_path, video)

    audio = work / (video.stem + ".wav")
    audio_extractor(video, audio)

    subtitles = engine.transcribe(audio)

    srt_path = work / (video.stem + ".srt")
    write_srt(srt_path, subtitles)
    return Result(video, srt_path, subtitles)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline orchestration with injected audio extractor"
```

---

### Task 4: faster-whisper engine

**Files:**
- Create: `src/transcription.py`

**Interfaces:**
- Consumes: stdlib `datetime.timedelta`; the `srt` library; `faster_whisper` (lazy).
- Produces: `FasterWhisperEngine(model_size="base", language=None, device="cpu", compute_type="int8")` with `transcribe(audio_path: Path) -> list[srt.Subtitle]`. `faster_whisper` is imported on first `transcribe`, so importing this module is cheap and tests of other modules never load it. Indices are 1-based; segment text stripped.

> No unit test: the segment→Subtitle mapping is exercised end-to-end via the manual launch (Task 6), and the `FakeEngine` in Task 3 covers the pipeline's use of the same shape. A model-mocking test would be more scaffolding than the four-line mapping is worth. ponytail: add a mocked test if the mapping grows logic.

- [ ] **Step 1: Write the engine**

`src/transcription.py`:

```python
"""faster-whisper engine. Lazy import keeps the heavy dep off other modules."""
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
```

- [ ] **Step 2: Smoke-import**

Run: `python -c "import src.transcription; print('ok')"`
Expected: prints `ok` (no model download — import is lazy).

- [ ] **Step 3: Commit**

```bash
git add src/transcription.py
git commit -m "feat: faster-whisper engine"
```

---

### Task 5: UI + entry point

**Files:**
- Create: `src/app.py`

**Interfaces:**
- Consumes: PySide6; `transcribe_video` + `Result` (pipeline); `write_srt` (subtitles); `FasterWhisperEngine` (transcription); the `srt` library (`timedelta_to_srt_timestamp`, `srt_timestamp_to_timedelta`).
- Produces:
  - `MainWindow(QMainWindow)` — left: QMediaPlayer video + play button + seek slider; right: 4-column table (`#`, `Start`, `End`, `Text`), editable. File menu: "Open Video…", "Save SRT…".
  - Synced highlight: player `positionChanged` selects the row whose `[start, end)` contains the position. Click a row → seek player to its start. Timestamps shown/parsed with `srt` lib helpers (`HH:MM:SS,mmm`).
  - Pipeline runs on a `QThread` (`_Worker`) so the UI stays responsive; on finish loads the video + fills the table; on error shows a message box.
  - `main() -> int` — builds QApplication, shows the window, runs the loop. Bound to the `easywhisper` console script.

> UI validated by import-smoke + manual launch, not unit tests — Qt multimedia over a real video isn't worth a harness, and the spec scopes tests to the subtitle and pipeline modules.

- [ ] **Step 1: Write the app**

`src/app.py`:

```python
"""PySide6 UI (player + editor + window) and entry point. No business logic."""
from __future__ import annotations

import sys
from pathlib import Path

import srt
from PySide6.QtCore import QObject, QThread, QUrl, Qt, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.pipeline import Result, transcribe_video
from src.subtitles import write_srt
from src.transcription import FasterWhisperEngine


class _Worker(QObject):
    """Runs the pipeline off the UI thread."""

    done = Signal(object)   # Result
    failed = Signal(str)

    def __init__(self, video: Path, working_root: Path):
        super().__init__()
        self._video = video
        self._working_root = working_root

    def run(self):
        try:
            self.done.emit(transcribe_video(self._video, FasterWhisperEngine(), self._working_root))
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whisper Subtitle Studio")
        self._working_root = Path.cwd() / "work"
        self._thread = None
        self._worker = None

        # --- player (left) ---
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(QAudioOutput(self))
        video = QVideoWidget(self)
        self._player.setVideoOutput(video)
        self._play = QPushButton("Play", self)
        self._play.clicked.connect(self._toggle_play)
        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.sliderMoved.connect(self._player.setPosition)
        self._player.durationChanged.connect(lambda d: self._slider.setRange(0, d))
        self._player.positionChanged.connect(self._on_position)

        left = QWidget(self)
        lv = QVBoxLayout(left)
        lv.addWidget(video, 1)
        controls = QHBoxLayout()
        controls.addWidget(self._play)
        controls.addWidget(self._slider)
        lv.addLayout(controls)

        # --- editor (right) ---
        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(["#", "Start", "End", "Text"])
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.cellClicked.connect(self._seek_to_row)

        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.addWidget(left)
        split.addWidget(self._table)
        split.setStretchFactor(0, 2)
        self.setCentralWidget(split)

        menu = self.menuBar().addMenu("&File")
        menu.addAction("Open Video…").triggered.connect(self._open_video)
        menu.addAction("Save SRT…").triggered.connect(self._save_srt)

    # --- player handlers ---
    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._play.setText("Play")
        else:
            self._player.play()
            self._play.setText("Pause")

    def _on_position(self, position_ms):
        self._slider.setValue(position_ms)
        seconds = position_ms / 1000
        # ponytail: linear scan per tick; fine for subtitle counts. Index by start if it ever isn't.
        for row in range(self._table.rowCount()):
            start = srt.srt_timestamp_to_timedelta(self._table.item(row, 1).text()).total_seconds()
            end = srt.srt_timestamp_to_timedelta(self._table.item(row, 2).text()).total_seconds()
            if start <= seconds < end:
                self._table.selectRow(row)
                return

    def _seek_to_row(self, row, _column):
        start = srt.srt_timestamp_to_timedelta(self._table.item(row, 1).text())
        self._player.setPosition(int(start.total_seconds() * 1000))

    # --- pipeline ---
    def _open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", "", "Video (*.mp4 *.mkv *.mov *.avi *.webm);;All (*)"
        )
        if not path:
            return
        self.statusBar().showMessage("Transcribing… this may take a while.")
        self._thread = QThread(self)
        self._worker = _Worker(Path(path), self._working_root)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.done.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _on_done(self, result: Result):
        self._player.setSource(QUrl.fromLocalFile(str(result.video)))
        self._table.setRowCount(len(result.subtitles))
        for row, sub in enumerate(result.subtitles):
            self._table.setItem(row, 0, QTableWidgetItem(str(sub.index)))
            self._table.setItem(row, 1, QTableWidgetItem(srt.timedelta_to_srt_timestamp(sub.start)))
            self._table.setItem(row, 2, QTableWidgetItem(srt.timedelta_to_srt_timestamp(sub.end)))
            self._table.setItem(row, 3, QTableWidgetItem(sub.content))
        self.statusBar().showMessage(f"Done. SRT at {result.srt}", 5000)

    def _on_failed(self, message):
        self.statusBar().clearMessage()
        QMessageBox.critical(self, "Transcription failed", message)

    def _save_srt(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save SRT", "subtitles.srt", "SubRip (*.srt)")
        if not path:
            return
        subs = [
            srt.Subtitle(
                index=int(self._table.item(row, 0).text()),
                start=srt.srt_timestamp_to_timedelta(self._table.item(row, 1).text()),
                end=srt.srt_timestamp_to_timedelta(self._table.item(row, 2).text()),
                content=self._table.item(row, 3).text(),
            )
            for row in range(self._table.rowCount())
        ]
        write_srt(Path(path), subs)
        self.statusBar().showMessage(f"Saved {path}", 5000)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 700)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-import**

Run: `python -c "import src.app; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Launch (manual smoke test)**

Run: `easywhisper`
Expected: window titled "Whisper Subtitle Studio" opens — player + play/slider on the left, empty 4-column subtitle table on the right; File menu has "Open Video…" and "Save SRT…". Close to exit. (Needs a display; on Linux a multimedia backend.)

- [ ] **Step 4: Commit**

```bash
git add src/app.py
git commit -m "feat: PySide6 UI, synced editor, threaded pipeline, entry point"
```

---

### Task 6: README + final verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# Whisper Subtitle Studio

A minimal, lightweight desktop app that transcribes video into editable SRT
subtitles using a local [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
model. It pairs a synced video player with an inline subtitle editor in one
window. Transcription runs fully locally — no API keys, no cloud calls. The only
network access is the one-time model download on first run.

## Features

- Select a video; the app extracts audio, transcribes it, and writes an SRT.
- Synced playback: the active cue highlights as the video plays.
- Click a cue to seek the video to its start.
- Edit cue text and timestamps inline, then save the SRT.

## Prerequisite: ffmpeg

ffmpeg must be installed and on your `PATH`; the app calls it as a subprocess to
extract audio.

- **Windows:** `winget install Gyan.FFmpeg`
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg` (or your distro equivalent)

Verify: `ffmpeg -version`

## Install

```bash
git clone <repo-url>
cd easywhisper
pip install -e .          # add [dev] for pytest
```

## Usage

```bash
easywhisper
```

1. **File → Open Video…** and pick a file.
2. Wait for transcription (first run also downloads the Whisper model).
3. Video loads on the left, subtitles on the right.
4. Play; the current cue highlights. Click a cue to seek to it.
5. Edit timestamps (`HH:MM:SS,mmm`) and text directly in the table.
6. **File → Save SRT…** to write your edits.

Working copies and intermediate files go under a `work/` folder in the current
directory.

## Development

```bash
pytest
```

## Credits

- [OpenAI Whisper](https://github.com/openai/whisper) — the original model.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — the inference
  engine this app uses.

## License

MIT. See [LICENSE](LICENSE); the upstream OpenAI Whisper notice is preserved
there.

## Future work

- Export formats beyond SRT (VTT, ASS).
- Selectable model size / language / device in the UI.
```

- [ ] **Step 2: Commit README**

```bash
git add README.md
git commit -m "docs: README with ffmpeg prereq, install, usage, credits"
```

- [ ] **Step 3: Full suite + imports**

Run: `pytest -q`
Expected: all pass (test_subtitles, test_pipeline).

Run: `python -c "import src.app, src.pipeline, src.transcription, src.subtitles; print('all imports ok')"`
Expected: `all imports ok`.

- [ ] **Step 4: Confirm entry point installed**

Run:
```bash
python -c "import importlib.metadata as m; print([e.name for e in m.entry_points(group='console_scripts') if e.name=='easywhisper'])"
```
Expected: `['easywhisper']`.

---

## Self-Review

**Spec coverage (deliverables):**
1. Runnable skeleton, open→pipeline→SRT — Tasks 3, 5.
2. faster-whisper against the engine contract (duck-typed `.transcribe`) — Tasks 3, 4.
3. Cue model + SRT read/write — Task 2 (`srt.Subtitle` + `read_srt`/`write_srt`).
4. File copy + ffmpeg extraction — Task 3 (`transcribe_video` copy step, `extract_audio`).
5. Player synced to highlighting + click-to-seek — Task 5.
6. Inline edit text + timestamps + save — Task 5.
7. pyproject + console entry point — Tasks 1, 5.
8. README — Task 6.
9. MIT LICENSE + Whisper notice — Task 1.
10. Tests for subtitle module + pipeline — Tasks 2, 3.

**Deliberate simplifications (vs spec's per-file layout):** cue/segment model = `srt.Subtitle`; engine "interface" = duck typing (no Protocol, one impl); timestamp formatting = `srt` lib helpers; media/files folded into `pipeline.py`; player/editor/window folded into `app.py`. Add the split back when a second engine, a second export format, or a UI that outgrows one file actually arrives.

**Placeholder scan:** none — every code step is complete; every command shows expected output.

**Type consistency:** `srt.Subtitle(index,start,end,content)` everywhere; `Result(video,srt,subtitles)`; `transcribe_video(video_path,engine,working_root,*,audio_extractor=)`; `extract_audio(video_path,audio_path,ffmpeg=)`; engine `.transcribe(audio_path)`; `write_srt(path,subtitles)`/`read_srt(path)` — consistent across producers and consumers.
```
