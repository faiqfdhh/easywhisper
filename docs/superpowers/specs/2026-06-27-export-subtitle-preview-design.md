# Subtitle Preview + Export Design

## Overview

Two tightly scoped additions to EasyWhisper:
1. Show the current subtitle text overlaid on the video during playback.
2. Export a new video file with subtitles burned in (hardcoded) via ffmpeg, with basic style controls.

No new runtime dependencies. ffmpeg is already required.

---

## Subtitle Preview

### Layout

The editor page currently wraps `QVideoWidget` in a `QVBoxLayout` (the `top` widget). Replace this with a `QGridLayout` so the video widget and a QLabel can occupy the same cell. The label appears on top of the video, positioned at the bottom center.

```
  ┌──────────────────────┐
  │                      │
  │     QVideoWidget     │
  │                      │
  │   ┌──────────────┐   │
  │   │ Hello world  │   │  ← QLabel overlay
  │   └──────────────┘   │
  └──────────────────────┘
```

### Behavior

- `_on_position()` already identifies the active subtitle row. After selecting it, set `self._subtitle_label.setText(content)`.
- If no subtitle matches the current time, set text to empty string.
- The label gets `WA_TransparentForMouseEvents` — clicks/focus pass through to the video.

### Styling

```
background-color: rgba(0, 0, 0, 160);
color: white;
font-size: 18px;
padding: 6px 14px;
border-radius: 4px;
```

---

## Export

### New module: `src/export.py`

```python
def burn_subtitles(
    video: Path,
    srt: Path,
    output: Path,
    *,
    font_name: str = "Arial",
    font_size: int = 16,
    position: str = "bottom",  # "bottom" or "top"
    ffmpeg: str = "ffmpeg",
) -> Path
```

Constructs and runs:

```
ffmpeg -y -i <video> -vf "subtitles=<srt>:force_style='FontName=<font>,FontSize=<size>,Alignment=<2|8>'"
       -c:a copy <output>
```

Alignment: `2` = bottom center, `8` = top center.

Raises `RuntimeError` if ffmpeg fails.

The `ffmpeg=` parameter is injectable for testing.

### Export dialog

Small modeless or modal dialog opened from **File > Export Video...** (only enabled on the editor page):

- **Font family:** `QFontComboBox` (shows system fonts)
- **Font size:** `QSpinBox` (8–72, default 16)
- **Position:** `QComboBox` (Bottom / Top)
- **Output path:** `QLineEdit` + browse button (default: `<video>_subtitled.mp4`)
- **Export button** — starts the background task

### Background thread

A lightweight `ExportWorker` (same `QObject` + `QThread` pattern as `_Worker`):

```python
class _ExportWorker(QObject):
    done = Signal(str)   # output path
    failed = Signal(str)

    def __init__(self, video, srt, output, font_name, font_size, position):
        ...

    def run(self):
        result = burn_subtitles(...)
        self.done.emit(str(result))
```

While running, a simple `QProgressBar` dialog or the existing processing page shows "Exporting video..." (indeterminate mode — ffmpeg doesn't report progress easily).

### Integration

Menu action added in `MainWindow.__init__`:

```python
menu.addAction("Export Video\u2026").triggered.connect(self._export_video)
```

---

## Testing

- `tests/test_export.py` — mock subprocess, verify ffmpeg command string is correct for each parameter combination.
- Manual: export a real short video and verify the output has text burned in.
- Existing tests must continue to pass.

---

## Files changed

| File | Change |
|------|--------|
| `src/export.py` | **New** — `burn_subtitles()` function |
| `src/app.py` | Editor overlay label, export menu action, export dialog, ExportWorker |
| `tests/test_export.py` | **New** — mock-based ffmpeg command tests |

No changes to `pyproject.toml`, `src/pipeline.py`, or `src/subtitles.py`.
