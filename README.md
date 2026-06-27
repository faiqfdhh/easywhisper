# EasyWhisper

Transcribe video into editable SRT subtitles using a local [faster-whisper](https://github.com/SYSTRAN/faster-whisper) model. No API keys, no cloud calls.

## Quick Install

### 1. Install ffmpeg

ffmpeg must be on your PATH. If you already have it, verify with `ffmpeg -version`.

| Platform | Command |
|----------|---------|
| Windows  | `winget install Gyan.FFmpeg` |
| macOS    | `brew install ffmpeg` |
| Linux    | `sudo apt install ffmpeg` |

### 2. Install EasyWhisper

```bash
git clone https://github.com/YOUR_USERNAME/easywhisper
cd easywhisper
pip install -e .
```

> For development (pytest): `pip install -e .[dev]`

### 3. Launch

```bash
easywhisper
```

On first run, the app downloads the Whisper model automatically (about 1–10 GB depending on model size).

---

## Requirements

| Requirement | Min. version |
|-------------|-------------|
| Python      | 3.10        |
| ffmpeg      | any recent  |

**Python dependencies** (installed automatically by pip):

| Package       | Version |
|---------------|---------|
| PySide6       | >= 6.6  |
| faster-whisper | >= 1.0  |
| srt           | >= 3.5  |

---

## Troubleshooting installation

**`pip install -e .` fails**
Make sure you're in the `easywhisper/` directory (the one containing `pyproject.toml`). If Python is missing, download it from [python.org](https://python.org) (check "Add Python to PATH").

**`ffmpeg` not found**
- Windows: Restart your terminal after `winget install`, or add `C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin` (or wherever ffmpeg was installed) to your PATH.
- macOS: Run `brew install ffmpeg` if you have Homebrew, or download from [ffmpeg.org](https://ffmpeg.org).
- Linux: `sudo apt install ffmpeg` (Debian/Ubuntu), `sudo dnf install ffmpeg` (Fedora), or your distro's equivalent.

**`PySide6` fails to install**
PySide6 provides pre-built wheels for most systems. If it fails, you may need:
- **Linux:** `sudo apt install libxcb-cursor0` or similar X11 libraries.
- **Windows/macOS:** Ensure your Python architecture matches your OS (64-bit Python on 64-bit Windows).

---

## Usage

1. **File → Open Video...** and pick a file.
2. Choose model size and language in the transcription dialog.
3. Wait for transcription (first run downloads the model automatically).
4. Video plays on the left, subtitles on the right. The active cue highlights during playback.
5. Click any cue to seek the video to that timecode.
6. Edit timestamps and text directly in the subtitle table.
7. **File → Save SRT...** to export.

Working copies and intermediate files are stored in a `work/` folder in the current directory.

---

## Models

| Size  | Parameters | English-only | Multilingual | Required VRAM | Speed |
|-------|-----------|-------------|-------------|---------------|-------|
| tiny  | 39 M      | tiny.en     | tiny        | ~1 GB         | ~10x  |
| base  | 74 M      | base.en     | base        | ~1 GB         | ~7x   |
| small | 244 M     | small.en    | small       | ~2 GB         | ~4x   |
| medium| 769 M     | medium.en   | medium      | ~5 GB         | ~2x   |
| large | 1550 M    | --          | large       | ~10 GB        | 1x    |
| turbo | 809 M     | --          | turbo       | ~6 GB         | ~8x   |

**Recommendations:**
- **tiny / base** — quick tests, real-time use, low-resource hardware.
- **small** — good default, balanced speed and accuracy.
- **medium / large** — best accuracy, needs significant VRAM.
- **turbo** — best value, near-large quality at ~8x speed.

The `.en` variants are optimized for English-only transcription and perform better for that use case.

---

## Languages

99 languages supported. By default the app auto-detects the language; you can also specify one for better accuracy.

Afrikaans, Albanian, Amharic, Arabic, Armenian, Assamese, Azerbaijani, Bashkir, Basque, Belarusian, Bengali, Bosnian, Breton, Bulgarian, Burmese, Cantonese, Catalan, Chinese, Croatian, Czech, Danish, Dutch, English, Estonian, Faroese, Finnish, Flemish, French, Galician, Georgian, German, Greek, Gujarati, Haitian Creole, Hausa, Hawaiian, Hebrew, Hindi, Hungarian, Icelandic, Indonesian, Italian, Japanese, Javanese, Kannada, Kazakh, Khmer, Korean, Lao, Latin, Latvian, Lingala, Lithuanian, Luxembourgish, Macedonian, Malay, Malayalam, Maltese, Maori, Marathi, Mongolian, Myanmar (Burmese), Nepali, Norwegian, Nynorsk, Occitan, Pashto, Persian, Polish, Portuguese, Punjabi, Romanian, Russian, Sanskrit, Serbian, Shona, Sindhi, Sinhala, Slovak, Slovenian, Somali, Spanish, Sundanese, Swahili, Swedish, Tagalog, Tajik, Tamil, Tatar, Telugu, Thai, Tibetan, Turkish, Turkmen, Ukrainian, Urdu, Uzbek, Vietnamese, Welsh, Yiddish, Yoruba.

---

## System check

The app verifies your environment on startup (Python >= 3.10, ffmpeg on PATH, required packages). You can also run **Help → System Check** for a full report at any time.

---

## Development

```bash
pip install -e .[dev]
pytest
```

---

## License

MIT. See [LICENSE](LICENSE).
