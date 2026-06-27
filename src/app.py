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
        menu.addAction("Open Video\u2026").triggered.connect(self._open_video)
        menu.addAction("Save SRT\u2026").triggered.connect(self._save_srt)

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
        self.statusBar().showMessage("Transcribing\u2026 this may take a while.")
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
