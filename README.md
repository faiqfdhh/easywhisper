# Whisper Subtitle Studio

A minimal, lightweight desktop app that transcribes video into editable SRT
subtitles using a local [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
model. It pairs a synced video player with an inline subtitle editor in one
window. Transcription runs fully locally -- no API keys, no cloud calls. The only
network access is the one-time model download on first run.

## Features

- Select a video; the app extracts audio, transcribes it, and writes an SRT.
- Choose from 6 model sizes with full detail on parameters, VRAM, and speed.
- Specify transcription language (99 languages supported) or use auto-detect.
- Synced playback: the active cue highlights as the video plays.
- Click a cue to seek the video to its start.
- Edit cue text and timestamps inline, then save the SRT.
- One-click export video with burned-in subtitles.
- Automatic system check on startup verifies ffmpeg, Python, and packages.

## Prerequisite: ffmpeg

ffmpeg must be installed and on your `PATH`; the app calls it as a subprocess to
extract audio and burn subtitles.

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

1. **File -> Open Video...** and pick a file.
2. **Choose your model and language** in the transcription settings dialog.
3. Wait for transcription (first run downloads the Whisper model automatically).
4. Video loads on the left, subtitles on the right.
5. Play; the current cue highlights. Click a cue to seek to it.
6. Edit timestamps (`HH:MM:SS,mmm`) and text directly in the table.
7. **File -> Save SRT...** to write your edits.

Working copies and intermediate files go under a `work/` folder in the current
directory.

## Available Models

| Size | Parameters | English-only | Multilingual | Required VRAM | Relative Speed |
|------|-----------|-------------|-------------|---------------|----------------|
| tiny | 39 M | tiny.en | tiny | ~1 GB | ~10x |
| base | 74 M | base.en | base | ~1 GB | ~7x |
| small | 244 M | small.en | small | ~2 GB | ~4x |
| medium | 769 M | medium.en | medium | ~5 GB | ~2x |
| large | 1550 M | -- | large | ~10 GB | 1x |
| turbo | 809 M | -- | turbo | ~6 GB | ~8x |

The `.en` models are optimized for English-only transcription and tend to perform
better, especially `tiny.en` and `base.en`. The `turbo` model is an optimized
version of `large-v3` offering near-large accuracy with much faster speed.

**Recommendations:**
- **tiny** / **base**: Quick tests, real-time use, or limited hardware.
- **small**: Good default balancing speed and accuracy.
- **medium** / **large**: Best quality; needs more VRAM.
- **turbo**: Best value -- near-large quality at ~8x speed.

## Available Languages

The app supports 99 languages for transcription. By default, the language is
auto-detected from the audio. You can also specify a language to improve accuracy:

Afrikaans, Albanian, Amharic, Arabic, Armenian, Assamese, Azerbaijani, Bashkir,
Basque, Belarusian, Bengali, Bosnian, Breton, Bulgarian, Burmese, Cantonese,
Catalan, Chinese, Croatian, Czech, Danish, Dutch, English, Estonian, Faroese,
Finnish, Flemish, French, Galician, Georgian, German, Greek, Gujarati, Haitian
Creole, Hausa, Hawaiian, Hebrew, Hindi, Hungarian, Icelandic, Indonesian,
Italian, Japanese, Javanese, Kannada, Kazakh, Khmer, Korean, Lao, Latin, Latvian,
Lingala, Lithuanian, Luxembourgish, Macedonian, Malay, Malayalam, Maltese,
Maori, Marathi, Mongolian, Myanmar (Burmese), Nepali, Norwegian, Nynorsk,
Occitan, Pashto, Persian, Polish, Portuguese, Punjabi, Romanian, Russian,
Sanskrit, Serbian, Shona, Sindhi, Sinhala, Slovak, Slovenian, Somali, Spanish,
Sundanese, Swahili, Swedish, Tagalog, Tajik, Tamil, Tatar, Telugu, Thai,
Tibetan, Turkish, Turkmen, Ukrainian, Urdu, Uzbek, Vietnamese, Welsh, Yiddish,
Yoruba.

## System Check

The app automatically verifies your setup on startup:
- Python version (needs >= 3.10)
- ffmpeg on PATH
- Required Python packages (PySide6, faster-whisper, srt)

If anything is missing, a warning appears on the welcome page. You can also run
**Help -> System Check** at any time for a full report.

## Development

```bash
pip install -e .[dev]
pytest
```

## Credits

- [OpenAI Whisper](https://github.com/openai/whisper) -- the original model.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) -- the inference
  engine this app uses.

## License

MIT. See [LICENSE](LICENSE); the upstream OpenAI Whisper notice is preserved
there.

## Future work

- Export formats beyond SRT (VTT, ASS).
