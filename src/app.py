"""PySide6 UI and entry point."""
from __future__ import annotations

import sys
from pathlib import Path

import srt
from PySide6.QtCore import QObject, QThread, QUrl, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.export import burn_subtitles

from src.pipeline import Result, transcribe_video
from src.subtitles import write_srt
from src.transcription import FasterWhisperEngine


class _CancelledError(Exception):
    pass


class _Worker(QObject):
    """Runs the pipeline off the UI thread."""

    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str, int)

    def __init__(self, video: Path, working_root: Path):
        super().__init__()
        self._video = video
        self._working_root = working_root
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        try:
            def on_progress(stage, pct):
                self.progress.emit(stage, pct)
                if self._cancel_requested:
                    raise _CancelledError()
            result = transcribe_video(
                self._video, FasterWhisperEngine(), self._working_root,
                progress_callback=on_progress,
            )
            self.done.emit(result)
        except _CancelledError:
            pass
        except Exception as exc:
            self.failed.emit(str(exc))


class _ExportWorker(QObject):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, video, srt_path, output, font_name, font_size, position):
        super().__init__()
        self._video = video
        self._srt_path = srt_path
        self._output = output
        self._font_name = font_name
        self._font_size = font_size
        self._position = position

    def run(self):
        try:
            result = burn_subtitles(
                self._video, self._srt_path, self._output,
                font_name=self._font_name,
                font_size=self._font_size,
                position=self._position,
            )
            self.done.emit(str(result))
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whisper Subtitle Studio")
        self._working_root = Path.cwd() / "work"
        self._thread = None
        self._worker = None

        self._stack = QStackedWidget(self)
        self.setCentralWidget(self._stack)

        self._welcome_page = self._build_welcome()
        self._processing_page = self._build_processing()
        self._editor_page = self._build_editor()

        self._stack.addWidget(self._welcome_page)
        self._stack.addWidget(self._processing_page)
        self._stack.addWidget(self._editor_page)

        self._stack.setCurrentIndex(0)

        menu = self.menuBar().addMenu("&File")
        menu.addAction("Open Video\u2026").triggered.connect(self._open_video)
        menu.addAction("New Video").triggered.connect(self._go_home)
        menu.addAction("Save SRT\u2026").triggered.connect(self._save_srt)
        menu.addAction("Export Video\u2026").triggered.connect(self._export_video)
        self._export_action = menu.actions()[-1]

    # --- pages ---

    def _build_welcome(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Whisper Subtitle Studio")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        desc = QLabel(
            "Transcribe video into editable subtitles.\n"
            "Runs locally. No uploads, no API keys."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        steps = QLabel(
            "\u2003\u2460 Pick a video file\n"
            "\u2003\u2461 Auto-transcribe\n"
            "\u2003\u2462 Edit timestamps and text\n"
            "\u2003\u2463 Save SRT"
        )
        steps.setStyleSheet("line-height: 1.6;")

        btn = QPushButton("Choose Video")
        btn.setMinimumHeight(44)
        btn.clicked.connect(self._open_video)

        layout.addStretch()
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(8)
        layout.addWidget(desc, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(24)
        layout.addWidget(steps, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(32)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

        return page

    def _build_processing(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._progress_label = QLabel("Starting\u2026")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label.setStyleSheet("font-size: 16px;")

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedWidth(400)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self._cancel_transcription)

        layout.addStretch()
        layout.addWidget(self._progress_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(self._progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(16)
        layout.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

        return page

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

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["#", "Start", "End", "Text"])
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(True)
        self._table.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.cellClicked.connect(self._seek_to_row)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(top)
        split.addWidget(self._table)
        split.setStretchFactor(0, 6)
        split.setStretchFactor(1, 1)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(split)
        return page

    # --- navigation ---

    def _go_home(self):
        self._player.setSource(QUrl())
        self._table.setRowCount(0)
        self._stack.setCurrentIndex(0)

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
        self._start_transcription(Path(path))

    def _start_transcription(self, video: Path):
        self._stack.setCurrentIndex(1)
        self._progress_bar.setValue(0)
        self._progress_label.setText("Starting\u2026")

        self._thread = QThread(self)
        self._worker = _Worker(video, self._working_root)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.done.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _cancel_transcription(self):
        if self._worker:
            self._worker.cancel()
        self._go_home()

    def _on_progress(self, stage: str, pct: int):
        self._progress_label.setText(stage)
        self._progress_bar.setValue(pct)

    def _on_done(self, result: Result):
        self._player.setSource(QUrl.fromLocalFile(str(result.video)))
        self._table.setRowCount(len(result.subtitles))
        for row, sub in enumerate(result.subtitles):
            self._table.setItem(row, 0, QTableWidgetItem(str(sub.index)))
            self._table.setItem(row, 1, QTableWidgetItem(srt.timedelta_to_srt_timestamp(sub.start)))
            self._table.setItem(row, 2, QTableWidgetItem(srt.timedelta_to_srt_timestamp(sub.end)))
            self._table.setItem(row, 3, QTableWidgetItem(sub.content))
        self._stack.setCurrentIndex(2)

    def _on_failed(self, message):
        self._go_home()
        QMessageBox.critical(self, "Transcription failed", message)

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

    def _save_srt(self):
        if self._stack.currentIndex() != 2:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save SRT", "subtitles.srt", "SubRip (*.srt)")
        if not path:
            return
        write_srt(Path(path), self._get_current_subtitles())
        self.statusBar().showMessage(f"Saved {path}", 5000)

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

    def _on_export_done(self, path):
        self._export_action.setEnabled(True)
        self.statusBar().showMessage(f"Exported {path}", 8000)

    def _on_export_failed(self, message):
        self._export_action.setEnabled(True)
        self.statusBar().clearMessage()
        QMessageBox.critical(self, "Export failed", message)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 700)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
