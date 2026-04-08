# sonogram

A shell script that turns a WAV audio recording into a video with a scrolling
linear spectrogram, metadata overlay, and playback cursor. The visual style is
inspired by NASA telemetry displays and industrial camera footage.

> **Fair warning:** This tool was vibe-coded with AI assistance. It works, but
> it has rough edges. Use at your own risk, expect quirks, and feel free to fix
> things. No warranty, no guarantees, no refunds.

## What it produces

- Scrolling linear spectrogram with configurable FFT window and frequency range
- Info panel with recording metadata (file, subject, date, location, equipment, sample info, playback speed)
- Optional retro monochrome map widget showing recording coordinates
- Green glow playback cursor
- Optional frequency grid overlay
- Optional photo band
- 60 fps output at 1080x1080 (square) or 1080x1920 (reel)

## Install

### System dependencies

```bash
# macOS
brew install ffmpeg sox python3

# Ubuntu / Debian
sudo apt install ffmpeg sox python3 python3-venv

# Arch
sudo pacman -S ffmpeg sox python
```

### Clone and run

```bash
git clone https://github.com/mrkva/sonogram.git
cd sonogram
./sonogram recording.wav
```

Python packages (numpy, scipy, matplotlib, Pillow) are installed automatically
into a local `.venv/` on first run. No system-wide pip installs needed.

To add to your PATH:

```bash
sudo ln -sf "$(pwd)/sonogram" /usr/local/bin/sonogram
```

## Usage

### Command line

```bash
./sonogram recording.wav
```

### Web interface

```bash
./web.py                   # opens at http://localhost:5000
./web.py --port 8080       # custom port
./web.py --host 0.0.0.0   # listen on all interfaces
```

Drop a WAV file on the page, fill in the metadata, and hit Generate. Progress
updates stream in real-time. Works from any browser on any OS.

### Interactive prompts (CLI)

The CLI walks you through an interactive dialogue:

| Prompt | Default | Description |
|---|---|---|
| Date/time | auto-detected from filename or file metadata | ISO format, e.g. `2024-03-15T14:30:22` |
| Recorded subject | -- | What was recorded |
| Recorded with | -- | Equipment used |
| Location | *(optional)* | Recording location name |
| Coordinates | *(optional, if location set)* | `lat,lon` for the map widget |
| Freq min (Hz) | `20` | Spectrogram lower bound |
| Freq max (Hz) | Nyquist | Spectrogram upper bound |
| Playback speed | 1x | `SOURCE:TARGET` (e.g. `192000:44100`) or divisor |
| Preset | `square` | `square` (1080x1080) or `reel` (1080x1920) |
| Photo | *(optional)* | Path to a photo to embed in the video |
| Frequency grid | `y` | Draw grid lines on the spectrogram |
| FFT window size | `2048` | STFT window (e.g. `512`, `1024`, `4096`, `8192`) |
| Normalize audio | `y` | Two-pass loudnorm to -16 LUFS |
| Output file | `{input}_video.mp4` | Output path |

### Playback speed

For ultrasonic recordings (e.g. bat echolocation at 192kHz), use the playback
speed setting to reinterpret the sample rate. This slows the audio to make
ultrasound audible without altering the output sample rate.

Formats:
- `192000:44100` -- reinterpret 192kHz as 44.1kHz (4.35x slower)
- `4.35` -- slow by a factor of 4.35
- `1x` -- normal speed (default)

### FFT window size

The spectrogram is computed using a Short-Time Fourier Transform with a Hann
window and 87.5% overlap. The window size controls the trade-off between time
and frequency resolution:

- **Smaller windows** (512, 1024) -- better time resolution, good for
  transient-heavy recordings (clicks, impacts, birdsong)
- **Larger windows** (4096, 8192) -- better frequency resolution, good for
  tonal content (drones, engines, sustained notes)

## How it works

1. **Probe** the input WAV for sample rate, bit depth, channels, duration, and codec
2. **Prepare audio** -- optionally reinterpret sample rate for ultrasonic
   recordings (`asetrate` + `aresample`), then normalize loudness with a
   two-pass `loudnorm` filter
3. **Generate spectrogram** -- compute STFT in 30-second chunks (for memory
   efficiency), apply colormap, and write a wide PNG strip
4. **Render overlays** -- info panel, frequency scale, cursor image, and
   optional map widget (fetched from OpenStreetMap tiles with a retro
   dark/inverted filter)
5. **Compose video** -- ffmpeg scrolls (crops) across the spectrogram strip,
   overlays the cursor and frequency scale, and stacks the info panel on top

## Presets

Presets live in `presets/` and set video dimensions, font size, and frame rate:

| Preset | Resolution | Use case |
|--------|-----------|----------|
| `square` | 1080x1080 | Instagram post, general use |
| `reel` | 1080x1920 | Instagram/TikTok reel, vertical stories |

## Output

- Video: H.264, CRF 18, slow preset, 60 fps
- Audio: AAC 256 kbps
- Container: MP4 with faststart flag

## Project structure

```
sonogram                          # main shell script (CLI)
web.py                            # web interface (Flask)
templates/index.html              # web UI
lib/
  generate_spectrogram.py         # STFT + spectrogram image
  render_info_panel.py            # metadata overlay panel
  render_freq_scale.py            # frequency scale on left edge
  render_map_widget.py            # OSM-based retro map widget
presets/
  square.conf
  reel.conf
requirements.txt
```

## License

Do whatever you want with it.
