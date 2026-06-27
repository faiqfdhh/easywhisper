# Whisper Subtitle Studio

A minimal, lightweight desktop app that transcribes video into editable SRT
subtitles using a local [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
model. It pairs a synced video player with an inline subtitle editor in one
window. Transcription runs fully locally -- no API keys, no cloud calls. The only
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

1. **File -> Open Video...** and pick a file.
2. Wait for transcription (first run also downloads the Whisper model).
3. Video loads on the left, subtitles on the right.
4. Play; the current cue highlights. Click a cue to seek to it.
5. Edit timestamps (`HH:MM:SS,mmm`) and text directly in the table.
6. **File -> Save SRT...** to write your edits.

Working copies and intermediate files go under a `work/` folder in the current
directory.

## Development

```bash
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
- Selectable model size / language / device in the UI.
