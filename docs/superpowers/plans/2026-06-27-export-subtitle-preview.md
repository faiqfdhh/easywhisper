# Subtitle Preview + Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) for tracking.

**Goal:** Add in-app subtitle overlay on the video preview and export video files with burned-in subtitles.

**Architecture:** New `src/export.py` module wraps an ffmpeg call to burn subtitles. `src/app.py` gets a QLabel overlay on the video widget and a File > Export dialog offloaded to a background thread via the same QObject+QThread pattern used for transcription.

**Tech Stack:** Python 3.10+, PySide6, ffmpeg (already required).

---

### Task 1: Subtitle overlay in the editor

**Files:**
- Modify: `src/app.py:166-213` (editor page layout)
- Modify: `src/app.py:232-245` (_on_position handler)

- [ ] **Step 1: Create the overlay label and replace video layout with QGridLayout**

In `_build_editor`, after creating `video`, create `self._subtitle_label`. Replace the `QVBoxLayout` of the `top` widget with a `QGridLayout` so the video and label overlap in the same cell.

Change the `_build_editor` method around the video setup:

```python
def _build_editor(self):
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

    overlay = QLabel(self)
    overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    overlay.setWordWrap(True)
    overlay.setStyleSheet("""
        background-color: rgba(0, 0, 0, 160);
        color: white;
        font-size: 18px;
        padding: 8px 20px;
    """)
    overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    self._subtitle_label = overlay

    container = QWidget()
    grid = QGridLayout(container)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.addWidget(video, 0, 0)
    grid.addWidget(self._subtitle_label, 0, 0, Qt.AlignmentFlag.AlignBottom)

    top = QWidget()
    top_layout = QVBoxLayout(top)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.addWidget(container, 1)
    controls = QHBoxLayout()
    controls.addWidget(self._play)
    controls.addWidget(self._slider)
    top_layout.addLayout(controls)
    # ... rest unchanged
```

Also add `QGridLayout` to the imports:

```python
from PySide6.QtWidgets import (
    ..., QGridLayout,
    ...
)
```

- [ ] **Step 2: Update `_on_position` to set overlay text**

In the `_on_position` method, after selecting the matching row, set the overlay text:

```python
def _on_position(self, position_ms):
    self._slider.setValue(position_ms)
    seconds = position_ms / 1000
    found = False
    for row in range(self._table.rowCount()):
        start = srt.srt_timestamp_to_timedelta(self._table.item(row, 1).text()).total_seconds()
        end = srt.srt_timestamp_to_timedelta(self._table.item(row, 2).text()).total_seconds()
        if start <= seconds < end:
            self._table.selectRow(row)
            self._table.scrollToItem(
                self._table.item(row, 0), QAbstractItemView.ScrollHint.PositionAtCenter
            )
            self._subtitle_label.setText(self._table.item(row, 3).text())
            found = True
            break
    if not found:
        self._subtitle_label.clear()
```

- [ ] **Step 3: Run existing tests to confirm no regression**

```
python -m pytest
```
Expected: 3 passed

- [ ] **Step 4: Commit**

```
git add src/app.py
git commit -m "feat: overlay current subtitle on video during playback"
```

---

### Task 2: `src/export.py` module with tests

**Files:**
- Create: `src/export.py`
- Create: `tests/test_export.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_export.py`:

```python
"""Tests for ffmpeg subtitle burn-in."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch


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
            Path("/v.mp4"), Path("/v.srt"), Path("/v/o.mp4"),
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
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="ffmpeg: error")

    with patch("src.export.subprocess.run", side_effect=_fail), pytest.raises(RuntimeError, match="ffmpeg failed"):
        burn_subtitles(Path("/v.mp4"), Path("/v.srt"), Path("/v/o.mp4"))
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_export.py -v
```
Expected: ImportError (no module `src.export`)

- [ ] **Step 3: Write minimal implementation**

Create `src/export.py`:

```python
"""Burn subtitles into a video using ffmpeg."""
from __future__ import annotations

import subprocess
from pathlib import Path


def burn_subtitles(
    video: Path,
    srt: Path,
    output: Path,
    *,
    font_name: str = "Arial",
    font_size: int = 16,
    position: str = "bottom",
    ffmpeg: str = "ffmpeg",
) -> Path:
    alignment = "2" if position == "bottom" else "8"
    style = f"FontName={font_name},FontSize={font_size},Alignment={alignment}"
    cmd = [
        ffmpeg, "-y",
        "-i", str(video),
        "-vf", f"subtitles={srt}:force_style='{style}'",
        "-c:a", "copy",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (exit {result.returncode}): {result.stderr}")
    return output
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_export.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add src/export.py tests/test_export.py
git commit -m "feat: burn_subtitles() ffmpeg wrapper with style options"
```

---

### Task 3: Export UI in `app.py`

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Add new imports**

Add to the imports in `src/app.py`:

```python
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    ...  # keep existing, add:
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
)

from src.export import burn_subtitles
```

- [ ] **Step 2: Add Export menu action**

In `MainWindow.__init__`, add the Export action after the existing menu items:

```python
menu.addAction("Export Video\u2026").triggered.connect(self._export_video)
self._export_action = menu.actions()[-1]  # to disable when not on editor page
```

- [ ] **Step 3: Add helper to get current subtitles from table**

Add a helper method to `MainWindow`:

```python
def _get_current_subtitles(self):
    return [
        srt.Subtitle(
            index=int(self._table.item(row, 0).text()),
            start=srt.srt_timestamp_to_timedelta(self._table.item(row, 1).text()),
            end=srt.srt_timestamp_to_timedelta(self._table.item(row, 2).text()),
            content=self._table.item(row, 3).text(),
        )
        for row in range(self._table.rowCount())
    ]
```

Refactor `_save_srt` to use it:

```python
def _save_srt(self):
    if self._stack.currentIndex() != 2:
        return
    path, _ = QFileDialog.getSaveFileName(self, "Save SRT", "subtitles.srt", "SubRip (*.srt)")
    if not path:
        return
    write_srt(Path(path), self._get_current_subtitles())
    self.statusBar().showMessage(f"Saved {path}", 5000)
```

- [ ] **Step 4: Add ExportWorker class**

Add after `_Worker` (before `MainWindow`):

```python
class _ExportWorker(QObject):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, video, srt, output, font_name, font_size, position):
        super().__init__()
        self._video = video
        self._srt = srt
        self._output = output
        self._font_name = font_name
        self._font_size = font_size
        self._position = position

    def run(self):
        try:
            result = burn_subtitles(
                self._video, self._srt, self._output,
                font_name=self._font_name,
                font_size=self._font_size,
                position=self._position,
            )
            self.done.emit(str(result))
        except Exception as exc:
            self.failed.emit(str(exc))
```

- [ ] **Step 5: Add `_export_video` method to MainWindow**

Add to `MainWindow`:

```python
def _export_video(self):
    if self._stack.currentIndex() != 2:
        return
    video_path = Path(self._player.source().toLocalFile())
    if not video_path.is_file():
        return

    dialog = QDialog(self)
    dialog.setWindowTitle("Export Video")

    font_combo = QFontComboBox()
    font_combo.setCurrentFont(QFont("Arial"))

    size_spin = QSpinBox()
    size_spin.setRange(8, 72)
    size_spin.setValue(16)

    pos_combo = QComboBox()
    pos_combo.addItems(["Bottom", "Top"])

    default_out = video_path.with_name(video_path.stem + "_subtitled.mp4")
    output_edit = QLineEdit(str(default_out))
    browse_btn = QPushButton("Browse...")
    def browse():
        p, _ = QFileDialog.getSaveFileName(dialog, "Save Video", str(default_out), "MP4 (*.mp4)")
        if p:
            output_edit.setText(p)
    browse_btn.clicked.connect(browse)

    path_layout = QHBoxLayout()
    path_layout.addWidget(output_edit, 1)
    path_layout.addWidget(browse_btn)

    form = QFormLayout(dialog)
    form.addRow("Font:", font_combo)
    form.addRow("Size:", size_spin)
    form.addRow("Position:", pos_combo)
    form.addRow("Output:", path_layout)

    btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    btn_box.accepted.connect(dialog.accept)
    btn_box.rejected.connect(dialog.reject)
    form.addRow(btn_box)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    output_path = Path(output_edit.text())
    font_name = font_combo.currentFont().family()
    font_size = size_spin.value()
    position = pos_combo.currentText().lower()

    # Write current subtitles to temp SRT for ffmpeg
    srt_path = self._working_root / "export_temp.srt"
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    write_srt(srt_path, self._get_current_subtitles())

    self._export_thread = QThread(self)
    self._export_worker = _ExportWorker(
        video_path, srt_path, output_path,
        font_name=font_name,
        font_size=font_size,
        position=position,
    )
    self._export_worker.moveToThread(self._export_thread)
    self._export_thread.started.connect(self._export_worker.run)
    self._export_worker.done.connect(self._on_export_done)
    self._export_worker.failed.connect(self._on_export_failed)
    self._export_worker.done.connect(self._export_thread.quit)
    self._export_worker.failed.connect(self._export_thread.quit)
    self._export_thread.start()

    self._export_action.setEnabled(False)
    self.statusBar().showMessage("Exporting video...")
```

- [ ] **Step 6: Add export completion handlers**

Add to `MainWindow`:

```python
def _on_export_done(self, path):
    self._export_action.setEnabled(True)
    self.statusBar().showMessage(f"Exported {path}", 8000)

def _on_export_failed(self, message):
    self._export_action.setEnabled(True)
    self.statusBar().clearMessage()
    QMessageBox.critical(self, "Export failed", message)
```

- [ ] **Step 7: Run full test suite**

```
python -m pytest
```
Expected: 6 passed (3 existing + 3 new)

If `pip install -e .` is needed for the tests to resolve the new import, run it first.

- [ ] **Step 8: Commit**

```
git add src/app.py
git commit -m "feat: export video with burned-in subtitles and style options"
```

---

### Task 4: Final verification

- [ ] **Step 1: Run full test suite**

```
python -m pytest -v
```
Expected: 6 passed

- [ ] **Step 2: Manual smoke test**

```
easywhisper
```
Verify: app launches, video plays, subtitle overlay shows text, File > Export opens dialog.

- [ ] **Step 3: Commit any final tweaks**

```
git add -A
git commit -m "chore: final adjustments after verification"
```
