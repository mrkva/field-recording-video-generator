# Sonogram Aesthetic — NASA Telemetry / Drone HUD

A visual style spec to share with a new Claude Code session as a starter point
for building tools (video processors, generators, overlays) that look like
Sonogram. All values below are pulled directly from the working code in
`lib/render_*.py`, not interpretive — copy them verbatim.

## One-line summary

NASA mission-control telemetry crossed with a military drone OSD: black
backgrounds, all-caps monospace, bright-white values on dim-gray labels, hairline
separators, retro inverted maps with crosshair, and a green plasma playback
cursor.

## Font (non-negotiable)

**VCR OSD Mono** is the primary face. It's a free font (Riciery Leal, 2007) that
imitates the on-screen display of consumer VCRs/CRTs. It carries the entire
aesthetic — without it the look collapses into "generic monospace UI".

Download: search "VCR OSD Mono Riciery Leal" — it's on dafont, 1001fonts, and
similar archives. Place the `.ttf` in your project's font assets directory.

```
VCR_OSD_MONO.ttf            # primary, always preferred
DejaVuSansMono-Bold         # Linux fallback
LiberationMono-Bold         # Linux fallback
Menlo                       # macOS fallback
```

Pillow load pattern (copy verbatim):

```python
FONT_PATHS = [
    os.path.join(os.path.dirname(__file__), "VCR_OSD_MONO.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/System/Library/Fonts/Menlo.ttc",
]

def load_font(size):
    for fp in FONT_PATHS:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()
```

For ffmpeg `drawtext`, the same file is passed as `fontfile=…`.

**Typography rules**

- ALL CAPS for every label and value.
- Monospace, fixed-pitch — never proportional.
- Transliterate diacritics to ASCII before render (Š→S, č→c, ñ→n, ü→u). The
  VCR font has a basic Latin glyph set. The `transliterate()` function in
  `lib/render_info_panel.py` (lines 12–34) handles this; reuse it.
- Numbers use technical notation: `1K`, `2K`, `10K`, `500` (not `1000`,
  `2000`), `48000HZ 24BIT`, `51.07N 0.03E`, ISO 8601 datetimes
  (`2026-05-31T14:30:22`).
- Label/value alignment uses a fixed-width label column (typically 7 chars
  padded with spaces) so values line up vertically:
  ```
  FILE    RECORDING_001.WAV
  SUBJ    NIGHT FOREST
  TIME    2026-05-31T14:30:22
  LOC     ASHDOWN FOREST, UK
  EQUIP   ZOOM F3 + MKH8020 (PAIR)
  SMPL    48000HZ 24BIT
  ```

## Color palette

The codebase uses RGB tuples. Hex equivalents shown for design-tool use.

### Info panel (NASA telemetry)

| Role        | RGB             | Hex      |
|-------------|-----------------|----------|
| Background  | `(8, 8, 8)`     | `#080808` |
| Value text  | `(230, 230, 230)` | `#E6E6E6` |
| Label text  | `(120, 120, 120)` | `#787878` |
| Separator   | `(50, 50, 50)`  | `#323232` |

The background is *almost* black but not quite — pure `#000000` reads as
"empty"; `#080808` reads as "powered-on display".

### HUD overlay (drone camera)

| Role            | RGBA                  |
|-----------------|-----------------------|
| Primary white   | `(255, 255, 255, 230)` |
| Dim white       | `(160, 160, 160, 200)` |
| Bracket / chrome | `(255, 255, 255, 120)` |
| Outline (everywhere) | `(0, 0, 0, 255)` |
| Status footer   | `(255, 255, 255, 100)` |
| Freq tick major | `(255, 255, 255, 180)` |
| Freq tick minor | `(180, 180, 180, 100)` |

Layout: 20 px margin, 50 px L-bracket corners, 2 px line weight, hairline
vertical reference line (`alpha=60`) connecting major ticks.

### Map widget (retro inverted)

| Role            | RGB             |
|-----------------|-----------------|
| Tile bg fallback | `(40, 40, 40)`  |
| Inverted ramp max | `(140, 140, 140)` (clamped — never full white) |
| Grid lines      | `(60, 60, 60)`  |
| Crosshair       | `(255, 255, 255)` |
| Border          | `(180, 180, 180)` |
| Coord text bg   | `(0, 0, 0)`     |
| Coord text fg   | `(220, 220, 220)` |
| Zoom HUD text   | `(180, 180, 180)` |

### Playback cursor (green plasma)

Symmetric glow around a single column. Width 21 px, height = spectrogram
height. Distance from center governs color + alpha:

| Distance | RGB              | Alpha |
|----------|------------------|-------|
| 0–1 px   | `(0, 255, 120)`  | 240 — bright green core |
| 2–3 px   | `(200, 255, 220)` | 80 — cyan-tinged inner glow |
| 4–6 px   | `(255, 255, 255)` | 35 — white mid glow |
| 7–10 px  | `(255, 255, 255)` | 12 — faint outer glow |

### Spectrogram colormap

Default: matplotlib `inferno`. Alternatives offered in the CLI: `gray_r`
(white background, black data — print-friendly), `viridis`, `magma`, `hot`.
Dynamic range default 55 dB; configurable 40–90.

## Drawing techniques

### Outlined text (readable on any background)

The HUD never assumes the background — every overlay glyph gets a black
outline, drawn by stamping the text 8 times in a `(±t, ±t)` ring around the
target and then drawing the fill on top.

```python
def outlined_text(draw, x, y, text, font,
                  fill=(255, 255, 255, 230),
                  outline=(0, 0, 0, 255),
                  thickness=2):
    for dx in range(-thickness, thickness + 1):
        for dy in range(-thickness, thickness + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, fill=outline, font=font)
    draw.text((x, y), text, fill=fill, font=font)
```

Thickness 2 for labels, 3 for headline text. Same trick on lines for the
frequency scale ticks. Source: `lib/render_freq_scale.py:68-89`,
`lib/render_hud_overlay.py:36-55`.

### Frame brackets (corner Ls)

Four L-shaped marks at the corners, not a full rectangle. 50 px arms, 2 px
weight, 20 px inset from the frame edge, alpha 120 white. Implementation in
`lib/render_hud_overlay.py:136-149`.

### Retro map filter

Convert OSM tiles to a dark inverted grayscale "scope" image:

1. Crop tile mosaic square around the lat/lon.
2. Resize to widget size (LANCZOS).
3. Luma weights `0.299 R + 0.587 G + 0.114 B`.
4. Normalize to `[0, 1]`.
5. **Invert** (`1.0 - gray`) — roads/buildings now bright on dark.
6. Sigmoid contrast: `1 / (1 + exp(-10 * (gray - 0.5)))`.
7. Clamp max brightness to 140 (so it never blows out to pure white).
8. Stack as RGB.

Source: `lib/render_map_widget.py:61-93`. Tiles come from OpenStreetMap
(`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) with a polite
`User-Agent: yourapp/1.0` header and an 8 s timeout; on any failure return
`None` and let the caller render a dark fallback with just the crosshair.

### Crosshair (targeting reticle)

Centered on the data point. Outer ring + four arms with a gap before the
center (so the dot is unobscured) + a small filled dot. All white.

- Ring radius: `max(10, widget_size // 14)`
- Inner radius (arm gap): `max(4, ring // 3)`
- Arm length: `max(16, widget_size // 10)`
- Stroke: 2 px
- Center dot: 5×5 filled

Source: `lib/render_map_animation.py:35-47`.

### Grid overlay

Quarters only — 3 vertical + 3 horizontal lines so the center line lands
exactly on the crosshair. Color `(60, 60, 60)`, 1 px.

### Zoom / scan HUD

Top corners of the map widget. `Z03`…`Z13` zoom label top-left, `SCAN`
(switches to `LOCK` at zoom ≥ 11) top-right. Both in dim gray
`(180, 180, 180)`. Source: `lib/render_map_animation.py:59-69`.

### Hairline separator

A single 1-px line at the bottom of the info panel in `(50, 50, 50)`. Not a
border — just a divider. Source: `lib/render_info_panel.py:222-224`.

### Scrolling long values

If a value exceeds the column width (default 32 chars), it scrolls
character-by-character at 1 char/sec after a 5-second initial hold. The text
wraps with a ` • ` (U+2022 bullet) delimiter. Implementation uses one ffmpeg
`drawtext` filter per cycle position with `enable='eq(mod(…))'` — see
`build_ffmpeg_command()` in `sonogram` (the bash entry-point).

### Animated map zoom

For dynamic clips: render one map frame per zoom level from 3 (continent)
to 13 (street). Hold each level for 2 seconds. Use as an ffmpeg image
sequence (`-framerate fps -i map_%06d.png`) and overlay on the corner.
Source: `lib/render_map_animation.py:129-169`.

## Layout patterns

- **Padding**: 30 px horizontal, 22 px vertical inside the info panel; 8 px
  line gap; line height = font's `getbbox("AY")` height + 2.
- **Margins** on HUD overlay: 20 px from frame edge.
- **Panel width**: matches video width (1080 / 1920 / 2160 depending on
  preset).
- **Preset dimensions** Sonogram ships:

| Preset | Resolution | Use case |
|--------|-----------|----------|
| `square` | 1080×1080 | Instagram post |
| `reel` | 1080×1920 | TikTok / Reels |
| `ig_reel` | 1080×1920, safe zones | Reels w/ UI insets |
| `landscape` | 1920×1080 | YouTube / general |

When you build new layouts, use the same `WIDTH × HEIGHT` × `FPS` (60 default,
30 for low-power) preset model, and let each preset optionally override font
size, photo-band height, and encoder flags.

## ffmpeg encoder defaults

- Video: `libx264 -preset slow -crf 18 -pix_fmt yuv420p`
- Audio: `aac -b:a 256k`
- Container: `mp4 -movflags +faststart`
- Frame rate: 60 fps (30 for low-power presets)
- `-t duration` to bound output; **avoid `-shortest`** — in ffmpeg 7.x it can
  propagate EOF to the AAC encoder before it gets a frame.
- `-thread_queue_size 1024` on every image input.
- AAC sample rate must be ≤ 96 kHz — resample first if your source is higher.

## Anti-patterns (don't do these)

- Don't use a proportional or anti-aliased modern UI font. Loses the OSD
  feel instantly.
- Don't use pure `#000000` backgrounds. `#080808` reads as a "live" display;
  pure black reads as "no signal".
- Don't use colorful UI accents. The palette is grayscale + one accent
  (green for the cursor only). Color belongs in *data* (the inferno
  spectrogram, the map tile content), never in chrome.
- Don't draw borders around the entire info panel — use the corner brackets
  or a single bottom hairline.
- Don't soften anything. No drop shadows, no rounded corners, no gradients.
  Hard edges, pixel-aligned lines, 1–3 px strokes.
- Don't show map tiles in their natural colors. Always invert + sigmoid +
  clamp.
- Don't try to display a green cursor without the cyan/white glow halo —
  the halo is what makes it look like a CRT scan line and not a filled
  rectangle.

## Reference files in the Sonogram repo

When wiring a new tool, these are the canonical implementations to read:

| File | Owns |
|------|------|
| `lib/render_info_panel.py` | Telemetry panel, label/value layout, scroll detection |
| `lib/render_hud_overlay.py` | Full-frame drone HUD with corner brackets |
| `lib/render_freq_scale.py` | Outlined text + tick marks for axis overlays |
| `lib/render_map_widget.py` | OSM fetch + retro filter + crosshair |
| `lib/render_map_animation.py` | Zoom-pull animation frames |
| `lib/render_timecode.py` | Standalone timecode glyph renderer |
| `lib/generate_spectrogram.py` | Inferno colormap, dynamic range |
| `presets/*.conf` | Per-preset dimensions and encoder overrides |
