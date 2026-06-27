"""PySide6 UI and entry point."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import srt

_FONT_PATH = Path(__file__).parent / "fonts" / "Raleway-VariableFont_wght.ttf"
_ARROW_PATH = Path(__file__).parent / "down-arrow.svg"
_VIDEO_EXTS = frozenset({".mp4", ".mkv", ".mov", ".avi", ".webm"})
from PySide6.QtCore import QCoreApplication, QObject, QSettings, QThread, QUrl, Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QFontDatabase, QAction, QShortcut, QKeySequence
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QCompleter,
    QDialog,
    QMenu,
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
    QPlainTextEdit,
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
from src.models import MODEL_SPECS, SORTED_LANGUAGES
from src.pipeline import Result, transcribe_video
from src.setup import check_all
from src.subtitles import write_srt
from src.transcription import FasterWhisperEngine

_SETTINGS_ORG = "easywhisper"
_SETTINGS_APP = "whisper-subtitle-studio"


def _log(msg: str):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")


class Theme:
    BG_PAGE = "#0a0a0a"
    BG_SURFACE = "#171717"
    BG_HOVER = "#262626"
    BG_ACCENT = "#3b82f6"
    BG_ACCENT_HOVER = "#2563eb"
    BG_ACCENT_MUTED = "#1e3a8a"
    BG_TABLE_ALT = "#0f0f0f"
    TEXT_PRIMARY = "#f5f5f5"
    TEXT_SECONDARY = "#a3a3a3"
    TEXT_MUTED = "#737373"
    TEXT_WHITE = "#ffffff"
    TEXT_SUCCESS = "#22c55e"
    TEXT_ERROR = "#ef4444"
    BORDER = "#262626"
    BORDER_LIGHT = "#171717"
    BORDER_ACCENT = "#3b82f6"
    RADIUS = "8px"
    RADIUS_LG = "12px"
    RADIUS_XL = "24px"
    FONT_XS = "8pt"
    FONT_SM = "9pt"
    FONT_MD = "10pt"
    FONT_LG = "11pt"
    FONT_XL = "14pt"
    FONT_2XL = "18pt"


class _CancelledError(Exception):
    pass


class _Worker(QObject):
    """Runs the pipeline off the UI thread."""

    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str, int)

    def __init__(self, video: Path, working_root: Path, model_size: str, language: str | None):
        super().__init__()
        self._video = video
        self._working_root = working_root
        self._model_size = model_size
        self._language = language
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        try:
            spec = MODEL_SPECS.get(self._model_size, {})
            lang_label = self._language or "auto-detect"
            _log("Starting transcription")
            _log(f"  Video:   {self._video.name}")
            _log(f"  Model:   {self._model_size} ({spec.get('parameters', '?')} params, {spec.get('speed', '?')} speed)")
            _log(f"  Lang:    {lang_label}")
            _log(f"  Device:  cpu  Compute: int8")

            def on_progress(stage, pct):
                if pct % 5 == 0 or "Done" in stage:
                    _log(f"  [{pct:3d}%] {stage}")
                self.progress.emit(stage, pct)
                if self._cancel_requested:
                    raise _CancelledError()
            engine = FasterWhisperEngine(
                model_size=self._model_size,
                language=self._language,
            )
            result = transcribe_video(
                self._video, engine, self._working_root,
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


class _TranscriptionConfigDialog(QDialog):
    """Dialog for selecting model size and language before transcription."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transcription Settings")
        self.setMinimumWidth(520)
        self.setModal(True)
        self.setStyleSheet(f"""
            _TranscriptionConfigDialog {{
                background: {Theme.BG_SURFACE};
            }}
        """)

        self._selected_model = "base"
        self._selected_language: str | None = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 24, 28, 24)

        title = QLabel("Transcription Settings")
        title.setStyleSheet(
            f"font-size: {Theme.FONT_XL}; font-weight: 700; color: {Theme.TEXT_PRIMARY}; letter-spacing: -0.3px;"
        )
        layout.addWidget(title)

        lang_section = QVBoxLayout()
        lang_section.setSpacing(8)

        lang_label = QLabel("Language")
        lang_label.setStyleSheet(
            f"font-size: {Theme.FONT_XS}; font-weight: 600; color: {Theme.TEXT_MUTED}; "
            "text-transform: uppercase; letter-spacing: 0.5px;"
        )
        lang_section.addWidget(lang_label)

        self._lang_combo = QComboBox()
        self._lang_combo.setEditable(True)
        self._lang_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._lang_combo.setPlaceholderText("Type to filter or select a language...")
        self._lang_combo.addItem("Auto-detect", None)
        self._lang_combo.insertSeparator(1)
        english_idx = -1
        for i, (code, name) in enumerate(SORTED_LANGUAGES, start=2):
            self._lang_combo.addItem(f"{name} ({code})", code)
            if code == "en":
                english_idx = i
        
        if english_idx >= 0:
            self._lang_combo.setCurrentIndex(english_idx)
        self._lang_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 8px 12px;
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_PRIMARY};
                font-size: {Theme.FONT_LG};
                min-height: 20px;
            }}
            QComboBox:hover {{
                border-color: {Theme.BORDER_ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 28px;
            }}
            QComboBox::down-arrow {{
                image: url({_ARROW_PATH.as_posix()});
                width: 16px;
                height: 16px;
            }}
            QComboBox QAbstractItemView {{
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_PRIMARY};
                selection-background-color: {Theme.BG_ACCENT};
                selection-color: {Theme.TEXT_WHITE};
                border: 1px solid {Theme.BORDER};
                outline: none;
            }}
        """)
        lang_section.addWidget(self._lang_combo)

        completer = self._lang_combo.completer()
        if completer:
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.popup().setStyleSheet(f"""
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_PRIMARY};
                selection-background-color: {Theme.BG_ACCENT};
                selection-color: {Theme.TEXT_WHITE};
                border: 1px solid {Theme.BORDER};
                outline: none;
            """)

        lang_hint = QLabel("Specifying a language can improve transcription accuracy")
        lang_hint.setStyleSheet(f"font-size: {Theme.FONT_SM}; color: {Theme.TEXT_MUTED}; margin-top: -2px;")
        lang_section.addWidget(lang_hint)

        layout.addLayout(lang_section)

        separator = _separator_widget()
        layout.addWidget(separator)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 10px 24px;
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_LG};
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_SECONDARY};
                font-size: {Theme.FONT_LG};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_HOVER};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._start_btn = QPushButton("Start Transcription")
        self._start_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 10px 28px;
                border: none;
                border-radius: {Theme.RADIUS_LG};
                background: {Theme.BG_ACCENT};
                color: {Theme.TEXT_WHITE};
                font-size: {Theme.FONT_LG};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.BG_ACCENT_HOVER};
            }}
        """)
        self._start_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self._start_btn)

        layout.addLayout(btn_layout)



    def model_size(self) -> str:
        return "turbo"

    def language(self) -> str | None:
        idx = self._lang_combo.currentIndex()
        return self._lang_combo.itemData(idx)


def _separator_widget() -> QWidget:
    sep = QWidget()
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background: {Theme.BORDER};")
    return sep


class _SetupDialog(QDialog):
    """Shows dependency check results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Check")
        self.setMinimumWidth(460)
        self.setModal(True)
        self.setStyleSheet(f"_SetupDialog {{ background: {Theme.BG_SURFACE}; }}")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("System Check")
        title.setStyleSheet(f"font-size: 12pt; font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(title)

        self._checks = check_all()
        all_ok = True
        for c in self._checks:
            row = QHBoxLayout()
            icon_color = Theme.TEXT_SUCCESS if c["ok"] else Theme.TEXT_ERROR
            icon = QLabel("\u2713" if c["ok"] else "\u2717")
            icon.setStyleSheet(
                f"font-size: 12pt; color: {icon_color}; font-weight: bold;"
            )
            name = QLabel(c["name"])
            name.setStyleSheet(f"font-size: {Theme.FONT_MD}; font-weight: 600; color: {Theme.TEXT_PRIMARY}; min-width: 100px;")
            msg = QLabel(c["message"])
            msg.setStyleSheet(f"font-size: {Theme.FONT_MD}; color: {icon_color};")
            msg.setWordWrap(True)
            row.addWidget(icon)
            row.addWidget(name)
            row.addWidget(msg, 1)
            layout.addLayout(row)
            if not c["ok"]:
                all_ok = False

        layout.addSpacing(8)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 28px;
                border: none;
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_ACCENT};
                color: {Theme.TEXT_WHITE};
                font-size: {Theme.FONT_MD};
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {Theme.BG_ACCENT_HOVER}; }}
        """)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("easywhisper")
        self._settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        self._working_root = Path.cwd() / "work"
        self._thread = None
        self._worker = None

        self._stack = QStackedWidget(self)
        self._stack.setStyleSheet(f"QStackedWidget {{ background: {Theme.BG_PAGE}; }}")
        self.setCentralWidget(self._stack)
        self.setStyleSheet(f"QMainWindow {{ background: {Theme.BG_PAGE}; }}")

        self._welcome_page = self._build_welcome()
        self._processing_page = self._build_processing()
        self._editor_page = self._build_editor()

        self._stack.addWidget(self._welcome_page)
        self._stack.addWidget(self._processing_page)
        self._stack.addWidget(self._editor_page)

        self._stack.setCurrentIndex(0)

        self.setAcceptDrops(True)

        menu = self.menuBar().addMenu("&File")
        menu.addAction("Open Video\u2026").triggered.connect(self._open_video)
        menu.addAction("New Video").triggered.connect(self._go_home)
        menu.addAction("Save SRT\u2026").triggered.connect(self._save_srt)
        menu.addAction("Export Video\u2026").triggered.connect(self._export_video)
        self._export_action = menu.actions()[-1]

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction("System Check\u2026").triggered.connect(self._show_setup_dialog)
        help_menu.addAction("About\u2026").triggered.connect(self._show_about_dialog)

        QCoreApplication.instance().aboutToQuit.connect(self._on_quit)

        self._run_startup_check()

    # --- pages ---

    def _build_welcome(self):
        page = QWidget()
        page.setObjectName("welcome")
        page.setStyleSheet(
            f"#welcome {{ border: 2px dashed {Theme.BORDER}; border-radius: {Theme.RADIUS_XL}; margin: 24px; background: {Theme.BG_SURFACE}; }}"
        )
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(0)

        title = QLabel("easywhisper")
        title.setStyleSheet(
            f"font-size: {Theme.FONT_2XL}; font-weight: 700; color: {Theme.TEXT_PRIMARY}; border: none; letter-spacing: -0.5px;"
        )

        desc = QLabel(
            "Transcribe video into editable subtitles.\n"
            "Runs locally. No uploads, no API keys."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"font-size: {Theme.FONT_LG}; color: {Theme.TEXT_MUTED}; border: none; margin-top: 8px;")

        steps = QLabel(
            "\u2003\u2460 Pick a video file\n"
            "\u2003\u2461 Choose model and language\n"
            "\u2003\u2462 Auto-transcribe\n"
            "\u2003\u2463 Edit timestamps and text\n"
            "\u2003\u2464 Save SRT"
        )
        steps.setStyleSheet(f"line-height: 1.8; color: {Theme.TEXT_SECONDARY}; border: none; font-size: {Theme.FONT_LG};")

        drop_label = QLabel("Drag and drop a video file here")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: {Theme.FONT_LG}; border: none;")

        btn = QPushButton("Choose Video")
        btn.setMinimumHeight(44)
        btn.clicked.connect(self._open_video)
        btn.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_LG};
                padding: 12px 32px;
                font-size: {Theme.FONT_LG};
                font-weight: 600;
                color: {Theme.TEXT_PRIMARY};
                background: {Theme.BG_SURFACE};
            }}
            QPushButton:hover {{
                background: {Theme.BG_HOVER};
                border-color: {Theme.BORDER_ACCENT};
            }}
        """)

        self._welcome_status = QLabel()
        self._welcome_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._welcome_status.setStyleSheet(f"font-size: {Theme.FONT_SM}; color: {Theme.TEXT_MUTED}; border: none; margin-top: 8px;")

        layout.addStretch()
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(desc, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(32)
        layout.addWidget(steps, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(32)
        layout.addWidget(drop_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(self._welcome_status, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

        return page

    def _build_processing(self):
        page = QWidget()
        page.setStyleSheet(f"background: {Theme.BG_SURFACE};")
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._progress_label = QLabel("Starting\u2026")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label.setStyleSheet(f"font-size: 12pt; color: {Theme.TEXT_PRIMARY};")

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedWidth(400)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_PAGE};
                font-size: {Theme.FONT_SM};
                color: {Theme.TEXT_PRIMARY};
                text-align: center;
                height: 16px;
            }}
            QProgressBar::chunk {{
                background: {Theme.BG_ACCENT};
                border-radius: 5px;
            }}
        """)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self._cancel_transcription)
        cancel.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                padding: 8px 20px;
                font-size: {Theme.FONT_MD};
                color: {Theme.TEXT_SECONDARY};
                background: {Theme.BG_SURFACE};
            }}
            QPushButton:hover {{
                background: {Theme.BG_HOVER};
            }}
        """)

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
        video.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        video.customContextMenuRequested.connect(self._show_video_context_menu)
        self._player.setVideoOutput(video)
        self._play = QPushButton("Play", self)
        self._play.clicked.connect(self._toggle_play)
        self._play.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                padding: 6px 16px;
                font-size: {Theme.FONT_MD};
                color: {Theme.TEXT_PRIMARY};
                background: {Theme.BG_SURFACE};
            }}
            QPushButton:hover {{ background: {Theme.BG_HOVER}; }}
        """)
        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.sliderMoved.connect(self._player.setPosition)
        self._player.durationChanged.connect(lambda d: self._slider.setRange(0, d))
        self._player.positionChanged.connect(self._on_position)

        self._subtitle_label = QLabel("")
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setMinimumHeight(80)
        self._subtitle_label.setStyleSheet(f"""
            background-color: {Theme.BG_PAGE};
            color: {Theme.TEXT_PRIMARY};
            font-size: 16pt;
            font-weight: 600;
            padding: 12px 20px;
            border-top: 1px solid {Theme.BORDER};
            border-bottom: 1px solid {Theme.BORDER};
        """)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        top_layout.addWidget(video, 1)
        top_layout.addWidget(self._subtitle_label, 0)
        
        controls = QHBoxLayout()
        controls.setContentsMargins(12, 12, 12, 12)
        controls.addWidget(self._play)
        controls.addWidget(self._slider)

        self._time_label = QLabel("00:00:00.000 / 00:00:00.000", self)
        self._time_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: {Theme.FONT_MD}; font-family: monospace;")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        controls.addWidget(self._time_label)

        top_layout.addLayout(controls)

        space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space_shortcut.activated.connect(self._toggle_play)
        left_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        left_shortcut.activated.connect(lambda: self._player.setPosition(max(0, self._player.position() - 5000)))
        right_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        right_shortcut.activated.connect(lambda: self._player.setPosition(min(self._player.duration(), self._player.position() + 5000)))

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["#", "Start", "End", "Text"])
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {Theme.BORDER};
                gridline-color: {Theme.BORDER_LIGHT};
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_PRIMARY};
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {Theme.BG_ACCENT};
                color: {Theme.TEXT_WHITE};
            }}
            QTableWidget::item:hover {{
                background-color: {Theme.BG_HOVER};
            }}
            QTableWidget::item:selected:hover {{
                background-color: {Theme.BG_ACCENT_HOVER};
            }}
            QHeaderView::section {{
                background: {Theme.BG_PAGE};
                padding: 6px 8px;
                border: none;
                border-bottom: 1px solid {Theme.BORDER};
                font-weight: 600;
                font-size: {Theme.FONT_SM};
                color: {Theme.TEXT_MUTED};
            }}
        """)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.cellClicked.connect(self._seek_to_row)
        self._table.itemChanged.connect(self._on_table_edit)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(top)
        split.addWidget(self._table)
        split.setStretchFactor(0, 6)
        split.setStretchFactor(1, 1)
        split.setHandleWidth(8)
        split.setStyleSheet(f"""
            QSplitter::handle {{
                background: {Theme.BG_PAGE};
                border-top: 1px solid {Theme.BORDER};
                border-bottom: 1px solid {Theme.BORDER};
                height: 8px;
            }}
            QSplitter::handle:hover {{
                background: {Theme.BORDER_ACCENT};
            }}
        """)

        page = QWidget()
        page.setStyleSheet(f"background: {Theme.BG_SURFACE};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(split)
        return page

    # --- navigation ---

    def _go_home(self):
        self._player.setSource(QUrl())
        self._table.setRowCount(0)
        self._stack.setCurrentIndex(0)
        self._welcome_page.setStyleSheet(
            f"#welcome {{ border: 2px dashed {Theme.BORDER}; border-radius: {Theme.RADIUS_XL}; margin: 24px; background: {Theme.BG_SURFACE}; }}"
        )

    # --- drag & drop ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(
            url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in _VIDEO_EXTS
            for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()
            if self._stack.currentIndex() == 0:
                self._welcome_page.setStyleSheet(
                    f"#welcome {{ border: 2px dashed {Theme.BORDER_ACCENT}; border-radius: {Theme.RADIUS_XL}; margin: 24px; background: {Theme.BG_ACCENT_MUTED}; }}"
                )

    def dragLeaveEvent(self, event):
        if self._stack.currentIndex() == 0:
            self._welcome_page.setStyleSheet(
                f"#welcome {{ border: 2px dashed {Theme.BORDER}; border-radius: {Theme.RADIUS_XL}; margin: 24px; background: {Theme.BG_SURFACE}; }}"
            )

    def dropEvent(self, event):
        self._welcome_page.setStyleSheet(
            f"#welcome {{ border: 2px dashed {Theme.BORDER}; border-radius: {Theme.RADIUS_XL}; margin: 24px; background: {Theme.BG_SURFACE}; }}"
        )
        for url in event.mimeData().urls():
            if url.isLocalFile():
                p = Path(url.toLocalFile())
                if p.suffix.lower() in _VIDEO_EXTS:
                    self._start_transcription(p)
                    event.acceptProposedAction()
                    return

    # --- player handlers ---

    def _show_video_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Theme.BG_SURFACE};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 16px;
                font-size: {Theme.FONT_MD};
            }}
            QMenu::item:selected {{
                background-color: {Theme.BG_ACCENT};
                color: {Theme.TEXT_WHITE};
            }}
            QMenu::separator {{
                height: 1px;
                background: {Theme.BORDER};
                margin: 4px 0;
            }}
        """)

        jump_back = QAction("Jump Back 5s", self)
        jump_back.triggered.connect(lambda: self._player.setPosition(max(0, self._player.position() - 5000)))
        menu.addAction(jump_back)

        jump_forward = QAction("Jump Forward 5s", self)
        jump_forward.triggered.connect(lambda: self._player.setPosition(min(self._player.duration(), self._player.position() + 5000)))
        menu.addAction(jump_forward)

        menu.addSeparator()

        speed_menu = menu.addMenu("Playback Speed")
        speed_menu.setStyleSheet(menu.styleSheet())
        
        rates = [0.5, 1.0, 1.25, 1.5, 2.0]
        current_rate = self._player.playbackRate()
        for r in rates:
            label = f"{r}x" if r != 1.0 else "1.0x (Normal)"
            action = QAction(label, self)
            action.setCheckable(True)
            if abs(current_rate - r) < 0.01:
                action.setChecked(True)
            action.triggered.connect(lambda checked, rate=r: self._player.setPlaybackRate(rate))
            speed_menu.addAction(action)

        menu.exec(self.sender().mapToGlobal(pos))

    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._play.setText("Play")
        else:
            self._player.play()
            self._play.setText("Pause")

    def _format_time(self, ms: int) -> str:
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    def _on_position(self, position_ms):
        self._slider.setValue(position_ms)
        duration_ms = self._player.duration()
        self._time_label.setText(f"{self._format_time(position_ms)} / {self._format_time(duration_ms)}")
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

    def _show_error_dialog(self, title: str, message: str):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(460)
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {Theme.BG_SURFACE};
            }}
            QPlainTextEdit {{
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_PAGE};
                color: {Theme.TEXT_PRIMARY};
                font-size: {Theme.FONT_MD};
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        text = QPlainTextEdit(message, dialog)
        text.setReadOnly(True)
        text.setMaximumHeight(200)
        layout.addWidget(text)
        btn_layout = QHBoxLayout()
        copy = QPushButton("Copy")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(message))
        copy.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 20px;
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_SECONDARY};
                font-size: {Theme.FONT_MD};
            }}
            QPushButton:hover {{ background: {Theme.BG_HOVER}; }}
        """)
        ok = QPushButton("OK")
        ok.clicked.connect(dialog.accept)
        ok.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 24px;
                border: none;
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_ACCENT};
                color: {Theme.TEXT_WHITE};
                font-size: {Theme.FONT_MD};
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {Theme.BG_ACCENT_HOVER}; }}
        """)
        btn_layout.addStretch()
        btn_layout.addWidget(copy)
        btn_layout.addWidget(ok)
        layout.addLayout(btn_layout)
        dialog.exec()

    def _seek_to_row(self, row, _column):
        start = srt.srt_timestamp_to_timedelta(self._table.item(row, 1).text())
        self._player.setPosition(int(start.total_seconds() * 1000))

    # --- pipeline ---

    def _open_video(self):
        last_dir = self._settings.value("last_directory", "")
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", last_dir, "Video (*.mp4 *.mkv *.mov *.avi *.webm);;All (*)"
        )
        if not path:
            return
        self._start_transcription(Path(path))

    def _start_transcription(self, video: Path):
        dialog = _TranscriptionConfigDialog(self)
        checks = check_all()
        critical_failures = [c for c in checks if not c["ok"] and c["name"] != "faster-whisper"]

        if critical_failures:
            names = [c["name"] for c in critical_failures]
            dialog._start_btn.setEnabled(False)
            dialog._start_btn.setText(f"Missing: {', '.join(names)}")
            dialog._start_btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 10px 28px;
                    border: none;
                    border-radius: {Theme.RADIUS_LG};
                    background: {Theme.TEXT_MUTED};
                    color: {Theme.TEXT_WHITE};
                    font-size: {Theme.FONT_LG};
                    font-weight: 600;
                }}
            """)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._settings.setValue("last_directory", str(video.parent))

        model_size = dialog.model_size()
        language = dialog.language()

        self._stack.setCurrentIndex(1)
        self._progress_bar.setValue(0)
        self._progress_label.setText("Starting\u2026")

        self._thread = QThread(self)
        self._worker = _Worker(video, self._working_root, model_size, language)
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
        if not hasattr(self, "_progress_anim"):
            self._progress_anim = QPropertyAnimation(self._progress_bar, b"value")
            self._progress_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        self._progress_anim.stop()
        self._progress_anim.setDuration(10000)
        self._progress_anim.setStartValue(self._progress_bar.value())
        self._progress_anim.setEndValue(pct)
        self._progress_anim.start()

    def _on_done(self, result: Result):
        self._last_result = result
        _log(f"Transcription complete - {len(result.subtitles)} subtitles, video loaded in player")
        self._player.setSource(QUrl.fromLocalFile(str(result.video)))
        self._table.blockSignals(True)
        self._table.setRowCount(len(result.subtitles))
        for row, sub in enumerate(result.subtitles):
            self._table.setItem(row, 0, QTableWidgetItem(str(sub.index)))
            self._table.setItem(row, 1, QTableWidgetItem(srt.timedelta_to_srt_timestamp(sub.start)))
            self._table.setItem(row, 2, QTableWidgetItem(srt.timedelta_to_srt_timestamp(sub.end)))
            self._table.setItem(row, 3, QTableWidgetItem(sub.content))
        self._table.blockSignals(False)
        self._stack.setCurrentIndex(2)

    def _on_failed(self, message):
        self._go_home()
        self._show_error_dialog("Transcription failed", message)

    def _on_table_edit(self, item):
        if not getattr(self, "_last_result", None):
            return
        
        try:
            write_srt(self._last_result.srt, self._get_current_subtitles())
        except Exception as e:
            _log(f"Error saving SRT on edit: {e}")

        if self._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self._on_position(self._player.position())

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
        write_srt(self._last_result.srt, self._get_current_subtitles())
        self.statusBar().showMessage(f"Saved {self._last_result.srt}", 5000)

    def _export_video(self):
        if self._stack.currentIndex() != 2:
            return
        video_path = Path(self._player.source().toLocalFile())
        if not video_path.is_file():
            return
        if getattr(self, "_export_thread", None) and self._export_thread.isRunning():
            return

        _log("Export video dialog opened")
        dialog = QDialog(self)
        dialog.setWindowTitle("Export Video")
        dialog.setMinimumWidth(480)
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {Theme.BG_SURFACE};
            }}
            QLabel {{
                font-size: {Theme.FONT_MD};
                color: {Theme.TEXT_SECONDARY};
            }}
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_PRIMARY};
                font-size: {Theme.FONT_MD};
            }}
            QLineEdit:focus {{
                border-color: {Theme.BORDER_ACCENT};
            }}
            QSpinBox {{
                padding: 8px 12px;
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_PRIMARY};
                font-size: {Theme.FONT_MD};
                min-height: 20px;
            }}
            QSpinBox:focus {{
                border-color: {Theme.BORDER_ACCENT};
            }}
            QFontComboBox {{
                padding: 8px 12px;
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_PRIMARY};
                font-size: {Theme.FONT_MD};
                min-height: 20px;
            }}
            QFontComboBox:hover {{
                border-color: {Theme.BORDER_ACCENT};
            }}
            QFontComboBox::drop-down {{
                border: none;
                width: 28px;
            }}
            QFontComboBox::down-arrow {{
                image: url({_ARROW_PATH.as_posix()});
                width: 16px;
                height: 16px;
            }}
        """)

        font_combo = QFontComboBox()
        font_combo.setCurrentFont(QFont("Arial"))

        size_spin = QSpinBox()
        size_spin.setRange(8, 72)
        size_spin.setValue(16)

        pos_combo = QComboBox()
        pos_combo.addItems(["Bottom", "Top"])
        pos_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 8px 12px;
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_PRIMARY};
                font-size: {Theme.FONT_MD};
                min-height: 20px;
            }}
            QComboBox:hover {{
                border-color: {Theme.BORDER_ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 28px;
            }}
            QComboBox::down-arrow {{
                image: url({_ARROW_PATH.as_posix()});
                width: 16px;
                height: 16px;
            }}
        """)

        default_out = video_path.with_name(video_path.stem + "_subtitled.mp4")
        output_edit = QLineEdit(str(default_out))
        browse_btn = QPushButton("Browse...")
        browse_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 16px;
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_SECONDARY};
                font-size: {Theme.FONT_MD};
            }}
            QPushButton:hover {{
                background: {Theme.BG_HOVER};
            }}
        """)
        def browse():
            p, _ = QFileDialog.getSaveFileName(dialog, "Save Video", str(default_out), "MP4 (*.mp4)")
            if p:
                output_edit.setText(p)
        browse_btn.clicked.connect(browse)

        path_layout = QHBoxLayout()
        path_layout.addWidget(output_edit, 1)
        path_layout.addWidget(browse_btn)

        form = QFormLayout(dialog)
        form.setSpacing(12)
        form.setContentsMargins(24, 20, 24, 20)
        form.addRow("Font:", font_combo)
        form.addRow("Size:", size_spin)
        form.addRow("Position:", pos_combo)
        form.addRow("Output:", path_layout)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        btn_box.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 24px;
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_SURFACE};
                color: {Theme.TEXT_SECONDARY};
                font-size: {Theme.FONT_MD};
                font-weight: 500;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_HOVER};
            }}
            QPushButton[text="OK"] {{
                background: {Theme.BG_ACCENT};
                color: {Theme.TEXT_WHITE};
                border: none;
                font-weight: 600;
            }}
            QPushButton[text="OK"]:hover {{
                background: {Theme.BG_ACCENT_HOVER};
            }}
        """)
        form.addRow(btn_box)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        output_path = Path(output_edit.text())
        font_name = font_combo.currentFont().family()
        font_size = size_spin.value()
        position = pos_combo.currentText().lower()

        self._export_temp_srt = self._working_root / "export_temp.srt"
        self._export_temp_srt.parent.mkdir(parents=True, exist_ok=True)
        write_srt(self._export_temp_srt, self._get_current_subtitles())

        self._export_thread = QThread(self)
        self._export_worker = _ExportWorker(
            video_path, self._export_temp_srt, output_path,
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
        self._export_temp_srt.unlink(missing_ok=True)
        _log(f"Export done - {path}")
        self.statusBar().showMessage(f"Exported {path}", 8000)

    def _on_export_failed(self, message):
        self._export_action.setEnabled(True)
        self._export_temp_srt.unlink(missing_ok=True)
        _log(f"Export failed: {message}")
        self.statusBar().clearMessage()
        self._show_error_dialog("Export failed", message)

    # --- startup check ---

    def _run_startup_check(self):
        checks = check_all()
        failures = [c for c in checks if not c["ok"]]
        if not failures:
                return
        names = [c["name"] for c in failures]
        self._welcome_status.setText(f"Setup issue: {', '.join(names)} \u2717  (Help \u2192 System Check)")
        self._welcome_status.setStyleSheet(f"font-size: {Theme.FONT_SM}; color: {Theme.TEXT_ERROR}; border: none; margin-top: 8px;")
        if any(c["name"] == "ffmpeg" for c in failures):
            self.statusBar().showMessage("ffmpeg not found. Install ffmpeg and restart.", 15000)

    def _show_setup_dialog(self):
        dialog = _SetupDialog(self)
        dialog.exec()

    # --- persistence ---

    def _on_quit(self):
        self._settings.sync()

    def _show_about_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("About EasyWhisper")
        dialog.setMinimumWidth(480)
        dialog.setStyleSheet(f"QDialog {{ background: {Theme.BG_SURFACE}; }}")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(32, 32, 32, 28)
        layout.setSpacing(16)

        title = QLabel("EasyWhisper")
        title.setStyleSheet(f"font-size: 24pt; font-weight: 800; color: {Theme.TEXT_PRIMARY}; border: none; letter-spacing: -0.5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "A minimal desktop app that transcribes video into editable SRT "
            "subtitles using a local faster-whisper model. Transcription runs "
            "fully locally with no API keys and no cloud calls."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"font-size: {Theme.FONT_MD}; color: {Theme.TEXT_SECONDARY}; border: none; line-height: 1.5;")
        layout.addWidget(desc)

        layout.addSpacing(8)

        credit = QLabel("Created by Muhammad Faiq Fadhlullah")
        credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit.setStyleSheet(f"font-size: {Theme.FONT_MD}; color: {Theme.TEXT_MUTED}; border: none;")
        layout.addWidget(credit)

        version = QLabel("Version 0.1.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(f"font-size: {Theme.FONT_SM}; color: {Theme.TEXT_MUTED}; border: none;")
        layout.addWidget(version)

        layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 28px;
                border: none;
                border-radius: {Theme.RADIUS};
                background: {Theme.BG_ACCENT};
                color: {Theme.TEXT_WHITE};
                font-size: {Theme.FONT_MD};
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {Theme.BG_ACCENT_HOVER}; }}
        """)
        ok_btn.clicked.connect(dialog.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        dialog.exec()


def main() -> int:
    app = QApplication(sys.argv)
    font_id = QFontDatabase.addApplicationFont(str(_FONT_PATH))
    if font_id >= 0:
        families = QFontDatabase.applicationFontFamilies(font_id)
        family = families[0] if families else "Segoe UI"
    else:
        family = "Segoe UI"
    app.setFont(QFont(family, 13))
    window = MainWindow()
    window.resize(1200, 720)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
