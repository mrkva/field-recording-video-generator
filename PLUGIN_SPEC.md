# field-recording-video-generator — Plugin Integration Spec

## What it does

Generates a video from a WAV audio file (field recording). The output video contains:
- A horizontally scrolling logarithmic spectrogram with playback cursor
- A frequency scale overlay (left edge, outlined text + tick marks)
- A metadata info panel (top, NASA telemetry aesthetic) with fields: FILE, SUBJ, TIME, LOC, EQUIP, SMPL, SPEED
- Optional animated map widget (top-right corner, zooms from continent to street level)
- Optional photo band (bottom)
- Normalized audio (flat volume gain to -16 LUFS target)

## Architecture

### Entry point
`field-recording-video-generator` — Bash script (~900 lines). Orchestrates a 6-stage pipeline:

1. **Audio probe** — `ffprobe` extracts sample rate, channels, bit depth, duration, BWF metadata (`creation_time`, `time_reference`, `encoded_by`)
2. **Info panel render** — Python (`lib/render_info_panel.py`) generates a PNG with metadata fields. Returns panel height, timecode position, scroll field data, map overlay position
3. **Spectrogram render** — Python (`lib/generate_spectrogram.py`) generates a full-width PNG spectrogram (logarithmic frequency axis, configurable FFT window)
4. **Frequency scale render** — Python (`lib/render_freq_scale.py`) generates a transparent PNG overlay with frequency tick marks and labels
5. **Map animation render** — Python (`lib/render_map_animation.py`) generates PNG frame sequence for progressive zoom (zoom 3→14)
6. **FFmpeg compositing** — Assembles all layers into final video with scrolling crop, cursor overlay, drawtext filters (dynamic timecode, scrolling text), map animation overlay

### Data flow

```
WAV file
  │
  ├─► ffprobe ──► metadata (sample_rate, duration, BWF tags)
  │
  ├─► generate_spectrogram.py ──► spectrogram.png (full-width × SPEC_HEIGHT)
  │
  ├─► render_info_panel.py ──► info_panel.png + metadata stdout:
  │     panel_height=N, timecode_x=N, timecode_y=N,
  │     scroll_field=Y:TEXT, map_x=N, map_y=N, map_size=N
  │
  ├─► render_freq_scale.py ──► freq_scale.png (transparent RGBA overlay)
  │
  ├─► render_map_animation.py ──► map_frames/map_NNNNNN.png (image sequence)
  │
  └─► ffmpeg filter_complex:
        [spectrogram] → crop+scroll → overlay cursor → overlay freq_scale → [spec_final]
        [info_panel] → scale → [info]
        [info] + [spec_final] → vstack → [combined]
        [combined] + [map_animation] → overlay → [map_combined]
        [map_combined] → drawtext(scroll) → drawtext(timecode) → [outv]
        [audio] → volume gain → [outa]
```

### Preset system
Config files in `presets/` define output dimensions:
- `reel.conf` — 1080x1920 (vertical, default)
- `square.conf` — 1080x1080
- `landscape.conf` — 1920x1080

Each preset sets: `VIDEO_WIDTH`, `VIDEO_HEIGHT`, `PHOTO_BAND_HEIGHT`, `INFO_FONT_SIZE`, `FPS`

### Key parameters for integration

| Parameter | Description | Default |
|-----------|-------------|---------|
| Input WAV | Source audio file | Required |
| `--quick` | Skip interactive dialogue, use test defaults | Off |
| `--output` | Output video path | `outputs/<input_name>.mp4` |
| Preset | Video dimensions profile | `reel` |
| Subject | Recording subject description | Empty |
| Location | Recording location | Empty |
| Coordinates | Lat,lon for map widget | Empty |
| Recorder | Equipment used | Auto from BWF `encoded_by` |
| Playback speed | Speedup factor (e.g., 2x) | 1x |
| FFT window | Spectrogram FFT size | 2048 |
| Freq range | Min/max frequency for spectrogram | 0 to Nyquist |
| Timecode | Show dynamic time in panel | Off |
| Freq grid | Show grid lines on spectrogram | Off |

### Dependencies
- **System**: ffmpeg (with libfreetype/drawtext), ffprobe, sox, python3
- **Python**: numpy, scipy, matplotlib, Pillow, flask (for web UI)
- **Font**: VCR_OSD_MONO.ttf (bundled in `lib/`, fallback to DejaVu/Liberation/Menlo)
- **Network**: OSM tile server (for map widget, graceful fallback if unavailable)

### Web interface
`web.py` — Flask app with drag-and-drop upload, SSE progress streaming, video download. Wraps the same pipeline.

## How to integrate as a plugin

### Programmatic usage (non-interactive)
The script can be called non-interactively by providing all parameters as environment variables or by using `--quick` mode. For plugin integration:

1. **Simplest**: Shell out to the script with `--quick` flag and override defaults via environment or by creating a temp config
2. **Better**: Import the Python modules directly:
   - `lib/generate_spectrogram.py` — `generate_spectrogram(input_wav, output_png, width, height, ...)`
   - `lib/render_info_panel.py` — `render_info_panel(output_png, width, font_size, ...)`
   - `lib/render_freq_scale.py` — `render_freq_scale(output_png, width, height, freq_min, freq_max, ...)`
   - `lib/render_map_widget.py` — `render_map_widget(lat, lon, widget_size, ...)`
   - `lib/render_map_animation.py` — `render_map_animation(output_dir, lat, lon, widget_size, duration, fps, ...)`
3. **Build ffmpeg command**: The `build_ffmpeg_command()` bash function constructs the full filter_complex. To replicate in Python, follow the filter chain described in the data flow section above.

### Input requirements
- WAV format (any sample rate, bit depth, mono or stereo)
- BWF metadata optional but used when present (creation_time, time_reference, encoded_by)

### Output
- H.264 MP4, `-preset medium -crf 18`, pixel format yuv420p
- Audio: AAC 192k (or copy if compatible)
- Duration matches input audio (adjusted for playback speed)

### Visual style
All text rendering uses VCR OSD Mono font in ALL CAPS. Info panel: dark background (8,8,8), dim gray labels (120,120,120), bright white values (230,230,230). Map widget: inverted grayscale with sigmoid contrast, crosshair overlay, coordinate text. Frequency scale: white outlined text on transparent background. Overall aesthetic: NASA telemetry / military HUD / surveillance camera.
