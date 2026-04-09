# sonogram

A shell script that turns a WAV audio recording into a video with a scrolling
linear spectrogram, metadata overlay, and playback cursor. The visual style is
inspired by NASA telemetry displays and industrial camera footage.

> **Fair warning:** This tool was vibe-coded with AI assistance. It works, but
> it has rough edges. Use at your own risk, expect quirks, and feel free to fix
> things. No warranty, no guarantees, no refunds.

## What it produces

- Scrolling linear spectrogram with configurable FFT window and frequency range
- Two spectrogram methods: standard STFT and reassigned (sharper harmonic ridges)
- Info panel with recording metadata (file, subject, date, location, equipment, sample info, playback speed)
- Optional retro monochrome map widget showing recording coordinates
- Green glow playback cursor
- Optional frequency tick marks on the spectrogram edge
- Optional photo band
- Overwrite protection — prompts before replacing existing output files
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

Drop a WAV file on the page, fill in the metadata, choose your spectrogram
method and FFT window, and hit Generate. Progress updates stream in real-time.
Works from any browser on any OS.

### Automatic metadata detection

Sonogram reads metadata from several sources (in priority order) and
pre-fills the interactive prompts so you usually just press Enter:

| Source | What it provides |
|---|---|
| **iXML chunk** (in WAV) | Scene/note (subject), location name, GPS coordinates, recorder + microphone models |
| **BWF tags** (in WAV) | Origination date/time, `time_reference` for accurate timecode, `encoded_by` for equipment |
| **session.frm.txt** sidecar | Session title, equipment, location, coordinates, per-file start times |
| **Filename** | Date/time parsed from patterns like `2024-03-15T14_30_22` or `20240315_143022` |
| **File timestamps** | Creation/modification time as a last resort |

If your recorder embeds iXML (e.g. Sound Devices, Zoom F-series, Tascam
recorders with metadata enabled), sonogram will extract the scene name,
location, GPS coordinates, and equipment details automatically. Paired
microphones are detected and shown as e.g. `DPA 4006A (PAIR)`.

Diacritical characters in metadata (Š, č, ñ, ü, etc.) are automatically
transliterated to basic ASCII for reliable rendering with the monospace
overlay font.

### Interactive prompts (CLI)

The CLI walks you through an interactive dialogue, grouped by concern:

**Metadata** — auto-populated from iXML / BWF / sidecar when available

| Prompt | Default | Description |
|---|---|---|
| Date/time | auto-detected | ISO format, e.g. `2024-03-15T14:30:22` |
| Recorded subject | from iXML scene/note | What was recorded |
| Recorded with | from iXML/BWF | Equipment used |
| Location | from iXML | Recording location name |
| Coordinates | from iXML GPS | `lat,lon` for the map widget |

**Audio**

| Prompt | Default | Description |
|---|---|---|
| Playback speed | `1x` | `SOURCE:TARGET` (e.g. `192000:44100`) or divisor |
| Normalize audio | `y` | Flat volume gain to -16 LUFS |

**Spectrogram**

| Prompt | Default | Description |
|---|---|---|
| Method | `standard` | `standard` (classic STFT) or `reassigned` (sharper ridges, slower) |
| Freq min (Hz) | `20` | Spectrogram lower bound |
| Freq max (Hz) | Nyquist | Spectrogram upper bound |
| FFT window size | varies | Depends on method — see [FFT window size](#fft-window-size) |
| Detail (px/sec) | `200` | Pixels per second of audio; higher = more detail |
| Dynamic range (dB) | `55` | Lower = more contrast |

**Output**

| Prompt | Default | Description |
|---|---|---|
| Preset | `ig_reel` | `ig_reel` / `reel` / `square` / `landscape` |
| Photo | *(optional)* | Path to a photo to embed in the video |
| Timecode | auto if BWF | Running timecode overlay in info panel |
| Output file | `{input}_video.mp4` | Output path |

### Playback speed

For ultrasonic recordings (e.g. bat echolocation at 192kHz), use the playback
speed setting to reinterpret the sample rate. This slows the audio to make
ultrasound audible without altering the output sample rate.

Formats:
- `192000:44100` -- reinterpret 192kHz as 44.1kHz (4.35x slower)
- `4.35` -- slow by a factor of 4.35
- `1x` -- normal speed (default)

### Spectrogram method

Two methods are available for spectrogram generation:

- **Standard** — classic Short-Time Fourier Transform. Reliable, fast, good
  for all content types. The window size directly controls the trade-off
  between time and frequency resolution.
- **Reassigned** — computes three STFTs per frame to estimate instantaneous
  frequency and group delay, then shifts energy to its true time-frequency
  position. Produces much sharper harmonic ridges and tighter chirp lines,
  especially at smaller FFT windows. About 3x slower than standard.

Reassignment is most effective on tonal and harmonic content (birdsong,
musical instruments, bat echolocation). For broadband noise (rain, wind,
surf), the standard method may look better.

### FFT window size

Both methods use a Hann window with 87.5% overlap. The window size controls
the trade-off between time and frequency resolution:

- **Smaller windows** (512, 1024) — better time resolution, good for fast
  trills, clicks, and transients
- **Larger windows** (4096, 8192) — better frequency resolution, good for
  tonal content (drones, engines, sustained notes)

The reassigned method recovers frequency detail from smaller windows, so you
can use a small window for time resolution without losing frequency sharpness.

Recommended defaults:

| Content | Standard | Reassigned |
|---|---|---|
| Birdsong, fast trills | 1024 | 512 |
| General / mixed | 2048 | 1024 |
| Tonal, slow-evolving | 4096 | 2048 |

## How it works

1. **Probe** the input WAV for sample rate, bit depth, channels, duration, and codec
2. **Read metadata** -- extract iXML chunk, BWF tags, and `session.frm.txt`
   sidecar for subject, location, GPS, equipment, and timestamps
3. **Prepare audio** -- optionally reinterpret sample rate for ultrasonic
   recordings (`asetrate` + `aresample`), then normalize loudness with a
   flat volume gain to -16 LUFS
4. **Generate spectrogram** -- compute STFT (or reassigned STFT) in 30-second
   chunks (for memory efficiency), apply colormap, and write a wide PNG strip
5. **Render overlays** -- info panel, frequency scale, cursor image, and
   optional map widget (fetched from OpenStreetMap tiles with a retro
   dark/inverted filter)
6. **Compose video** -- ffmpeg scrolls (crops) across the spectrogram strip,
   overlays the cursor and frequency scale, and stacks the info panel on top

## Presets

Presets live in `presets/` and set video dimensions, font size, and frame rate:

| Preset | Resolution | Use case |
|--------|-----------|----------|
| `ig_reel` | 1080x1920 | Instagram/TikTok reel with safe zones (default) |
| `reel` | 1080x1920 | Vertical, full-bleed |
| `square` | 1080x1080 | Instagram post, general use |
| `landscape` | 1920x1080 | YouTube, desktop |

## Output

- Video: H.264, CRF 18, slow preset, 60 fps
- Audio: AAC 256 kbps
- Container: MP4 with faststart flag

## Project structure

```
sonogram                              # main shell script (CLI)
web.py                                # web interface (Flask)
templates/index.html                  # web UI
lib/
  generate_spectrogram.py             # standard STFT spectrogram
  generate_spectrogram_reassigned.py  # reassigned spectrogram
  render_info_panel.py                # metadata overlay panel
  render_freq_scale.py                # frequency scale on left edge
  render_map_widget.py                # OSM-based retro map widget
  render_map_animation.py             # animated map zoom sequence
  render_hud_overlay.py               # HUD overlay graphics
  render_timecode.py                  # running timecode overlay
presets/
  ig_reel.conf
  reel.conf
  square.conf
  landscape.conf
requirements.txt
```

## License

Do whatever you want with it.
