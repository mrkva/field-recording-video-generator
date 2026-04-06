#!/usr/bin/env python3
"""Render full-frame military drone HUD overlay.

All metadata, frequency scale, corner brackets, and status indicators
as a single transparent RGBA PNG overlaid on the spectrogram viewport.
"""

import argparse
import os
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Font loading
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def outlined_text(draw, x, y, text, font, fill=(255, 255, 255, 230),
                  outline=(0, 0, 0, 255), thickness=2):
    """Text with black outline — readable on any background."""
    for dx in range(-thickness, thickness + 1):
        for dy in range(-thickness, thickness + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, fill=outline, font=font)
    draw.text((x, y), text, fill=fill, font=font)


def outlined_line(draw, coords, fill=(255, 255, 255, 180),
                  outline=(0, 0, 0, 140), width=2):
    """Line with dark outline."""
    x0, y0, x1, y1 = coords
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            draw.line([(x0 + dx, y0 + dy), (x1 + dx, y1 + dy)],
                      fill=outline, width=width)
    draw.line([(x0, y0), (x1, y1)], fill=fill, width=width)


# ---------------------------------------------------------------------------
# Frequency scale (right edge)
# ---------------------------------------------------------------------------
def generate_tick_freqs(f_lo, f_hi):
    f_range = f_hi - f_lo
    if f_range > 100000:
        major, minor = 10000, 5000
    elif f_range > 40000:
        major, minor = 5000, 1000
    elif f_range > 10000:
        major, minor = 2000, 1000
    elif f_range > 5000:
        major, minor = 1000, 500
    elif f_range > 2000:
        major, minor = 500, 100
    elif f_range > 500:
        major, minor = 200, 100
    else:
        major, minor = 50, 10

    majors = []
    f = major
    while f < f_hi:
        if f > f_lo:
            majors.append(f)
        f += major

    minors = []
    f = minor
    major_set = set(majors)
    while f < f_hi:
        if f > f_lo and f not in major_set:
            minors.append(f)
        f += minor

    return majors, minors


def format_freq(freq):
    if freq >= 1000:
        val = freq / 1000
        return f"{int(val)}K" if val == int(val) else f"{val:.1f}K"
    return f"{int(freq)}"


def freq_to_y(freq, f_lo, f_hi, height):
    frac = (freq - f_lo) / (f_hi - f_lo + 1e-10)
    y = int((1.0 - frac) * height)
    return max(0, min(height - 1, y))


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render_hud_overlay(output_png, width, height,
                       filename="", subject="", recorder="", datetime_str="",
                       location="", playback_speed="",
                       freq_min=20, freq_max=22050,
                       font_size=28):
    """Render the complete HUD overlay as a single transparent PNG."""

    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = load_font(font_size)
    font_sm = load_font(int(font_size * 0.75))
    font_lg = load_font(int(font_size * 1.2))

    # Colors
    white = (255, 255, 255, 230)
    dim = (160, 160, 160, 200)
    outline = (0, 0, 0, 255)
    bracket_color = (255, 255, 255, 120)

    margin = 20
    bracket_len = 50
    bracket_w = 2

    # ── Corner brackets ──────────────────────────────────────────────
    corners = [
        # Top-left
        ((margin, margin, margin + bracket_len, margin), (margin, margin, margin, margin + bracket_len)),
        # Top-right
        ((width - margin - bracket_len, margin, width - margin, margin), (width - margin, margin, width - margin, margin + bracket_len)),
        # Bottom-left
        ((margin, height - margin, margin + bracket_len, height - margin), (margin, height - margin - bracket_len, margin, height - margin)),
        # Bottom-right
        ((width - margin - bracket_len, height - margin, width - margin, height - margin), (width - margin, height - margin - bracket_len, width - margin, height - margin)),
    ]
    for h_line, v_line in corners:
        draw.line([h_line[:2], h_line[2:]], fill=bracket_color, width=bracket_w)
        draw.line([v_line[:2], v_line[2:]], fill=bracket_color, width=bracket_w)

    # ── Top-left: metadata ───────────────────────────────────────────
    x = margin + 8
    y = margin + 8
    line_h = int(font_size * 1.35)

    if filename:
        basename = os.path.basename(filename).upper()
        # Truncate if too long (leave room for right side elements)
        max_chars = (width - 300) // (font_size * 0.6)
        if len(basename) > max_chars:
            basename = basename[:int(max_chars) - 3] + "..."
        outlined_text(draw, x, y, basename, font, fill=dim, thickness=2)
        y += line_h

    if subject:
        outlined_text(draw, x, y, subject.upper(), font_lg, fill=white, thickness=3)
        y += int(font_size * 1.6)

    if recorder:
        outlined_text(draw, x, y, "REC " + recorder.upper(), font_sm, fill=dim, thickness=2)
        y += int(font_size * 1.0)

    if location:
        outlined_text(draw, x, y, "LOC " + location.upper(), font_sm, fill=dim, thickness=2)
        y += int(font_size * 1.0)

    # ── Top-right: date/time + status ────────────────────────────────
    if datetime_str:
        dt_text = datetime_str.upper()
        bbox = font.getbbox(dt_text)
        dt_w = bbox[2] - bbox[0]
        outlined_text(draw, width - margin - dt_w - 8, margin + 8,
                      dt_text, font, fill=white, thickness=2)

    # Playback speed indicator (below datetime, right-aligned)
    if playback_speed and not playback_speed.upper().startswith("1X"):
        spd_text = "SPD " + playback_speed.upper()
        bbox = font_sm.getbbox(spd_text)
        spd_w = bbox[2] - bbox[0]
        outlined_text(draw, width - margin - spd_w - 8, margin + 8 + line_h,
                      spd_text, font_sm, fill=dim, thickness=2)

    # ── Bottom-left: status line ─────────────────────────────────────
    status_y = height - margin - int(font_size * 1.0)
    outlined_text(draw, margin + 8, status_y,
                  "AUDIO SPECTROGRAM", font_sm, fill=(255, 255, 255, 100),
                  thickness=2)

    # ── Right edge: frequency scale ──────────────────────────────────
    f_lo = float(freq_min)
    f_hi = float(freq_max)
    majors, minors = generate_tick_freqs(f_lo, f_hi)

    freq_font = load_font(int(font_size * 1.15))
    freq_font_sm = load_font(int(font_size * 0.55))

    # Measure max label width
    max_lbl_w = 0
    for freq in majors:
        bbox = freq_font.getbbox(format_freq(freq))
        w_ = bbox[2] - bbox[0]
        if w_ > max_lbl_w:
            max_lbl_w = w_

    major_tick_len = 24
    minor_tick_len = 12
    gap = 6
    right_pad = 10
    tick_end_x = width - right_pad - max_lbl_w - gap
    major_tick_start = tick_end_x - major_tick_len
    minor_tick_start = tick_end_x - minor_tick_len
    label_x = tick_end_x + gap

    # Vertical reference line
    outlined_line(draw, (tick_end_x, margin + bracket_len + 10,
                         tick_end_x, height - margin - bracket_len - 10),
                  fill=(255, 255, 255, 60), outline=(0, 0, 0, 40), width=1)

    # "FREQ HZ" header
    hdr_text = "FREQ HZ"
    hdr_bbox = freq_font_sm.getbbox(hdr_text)
    hdr_w = hdr_bbox[2] - hdr_bbox[0]
    outlined_text(draw, width - right_pad - hdr_w, margin + bracket_len + 14,
                  hdr_text, freq_font_sm, fill=(180, 180, 180, 160),
                  thickness=1)

    # Minor ticks
    for freq in minors:
        fy = freq_to_y(freq, f_lo, f_hi, height)
        outlined_line(draw, (minor_tick_start, fy, tick_end_x, fy),
                      fill=(180, 180, 180, 100), outline=(0, 0, 0, 60), width=1)

    # Major ticks + labels
    for freq in majors:
        fy = freq_to_y(freq, f_lo, f_hi, height)
        label = format_freq(freq)

        outlined_line(draw, (major_tick_start, fy, tick_end_x, fy),
                      fill=(255, 255, 255, 180), outline=(0, 0, 0, 140), width=2)

        # Bracket notch
        draw.line([(major_tick_start, fy - 3), (major_tick_start, fy + 3)],
                  fill=(255, 255, 255, 140), width=1)

        bbox = freq_font.getbbox(label)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        lx = label_x + (max_lbl_w - lw)  # right-align
        ly = fy - lh // 2 - 2
        ly = max(2, min(height - lh - 2, ly))

        outlined_text(draw, lx, ly, label, freq_font,
                      fill=(255, 255, 255, 220), thickness=3)

    img.save(output_png)
    return height


def main():
    parser = argparse.ArgumentParser(description='Render HUD overlay PNG')
    parser.add_argument('--output', required=True)
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    parser.add_argument('--font-size', type=int, default=28)
    parser.add_argument('--filename', default='')
    parser.add_argument('--subject', default='')
    parser.add_argument('--recorder', default='')
    parser.add_argument('--datetime', default='')
    parser.add_argument('--location', default='')
    parser.add_argument('--playback-speed', default='')
    parser.add_argument('--freq-min', type=float, default=20)
    parser.add_argument('--freq-max', type=float, default=22050)
    args = parser.parse_args()

    render_hud_overlay(
        output_png=args.output,
        width=args.width,
        height=args.height,
        font_size=args.font_size,
        filename=args.filename,
        subject=args.subject,
        recorder=args.recorder,
        datetime_str=args.datetime,
        location=args.location,
        playback_speed=args.playback_speed,
        freq_min=args.freq_min,
        freq_max=args.freq_max,
    )


if __name__ == '__main__':
    main()
