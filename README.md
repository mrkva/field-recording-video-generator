# field-recording-video-generator

Generate videos from WAV field recordings with scrolling logarithmic spectrogram, playback cursor, metadata overlay, and optional photo.

## Dependencies

```
apt install ffmpeg sox python3
pip install numpy scipy matplotlib Pillow
```

## Usage

```bash
./field-recording-video-generator recording.wav
```

The program will interactively ask for:

- **Recorded subject** — what was recorded
- **Recorded with** — recording device
- **Date/time** — auto-detected from filename (YYYYMMDD_HHMMSS patterns)
- **Location** — optional
- **Playback speed** — for ultrasonic content (e.g. `192000:44100` to slow a 192kHz bat recording to audible range)
- **Preset** — `square` (1080x1080) or `reel` (1080x1920)
- **Photo** — optional image to include in the video

## Playback speed

For ultrasonic recordings (e.g. bat echolocation at 192kHz), use the playback speed setting to reinterpret the sample rate. This slows the audio to make ultrasound audible without altering the output sample rate.

Formats:
- `192000:44100` — reinterpret 192kHz as 44.1kHz (4.35× slower)
- `4.35` — slow by a factor of 4.35
- `1x` — normal speed (default)

## Presets

| Preset | Resolution | Use case |
|--------|-----------|----------|
| `square` | 1080×1080 | Instagram post, general social media |
| `reel` | 1080×1920 | Instagram/TikTok reel (9:16 vertical) |

## Output

- Video: H.264, CRF 18, slow preset
- Audio: AAC 320kbps
- Container: MP4 with faststart flag
