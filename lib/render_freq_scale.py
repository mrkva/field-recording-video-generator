#!/usr/bin/env python3
"""Render a transparent frequency scale overlay — NASA telemetry aesthetic."""

import argparse
from PIL import Image, ImageDraw, ImageFont


def generate_tick_freqs(f_lo, f_hi):
    """Generate tick frequencies: major and minor."""
    f_range = f_hi - f_lo

    if f_range > 100000:
        major_step, minor_step = 10000, 5000
    elif f_range > 40000:
        major_step, minor_step = 5000, 1000
    elif f_range > 10000:
        major_step, minor_step = 2000, 1000
    elif f_range > 5000:
        major_step, minor_step = 1000, 500
    elif f_range > 2000:
        major_step, minor_step = 500, 100
    elif f_range > 500:
        major_step, minor_step = 200, 100
    else:
        major_step, minor_step = 50, 10

    majors = []
    f_val = major_step
    while f_val < f_hi:
        if f_val > f_lo:
            majors.append(f_val)
        f_val += major_step

    minors = []
    f_val = minor_step
    while f_val < f_hi:
        if f_val > f_lo and f_val not in majors:
            minors.append(f_val)
        f_val += minor_step

    return majors, minors


def format_freq(freq):
    """Format frequency: 1K, 2K, 10K, 500, etc."""
    if freq >= 1000:
        val = freq / 1000
        if val == int(val):
            return f"{int(val)}K"
        else:
            return f"{val:.1f}K"
    else:
        return f"{int(freq)}"


def freq_to_y(freq, f_lo, f_hi, height):
    """Convert frequency to Y pixel position."""
    frac = (freq - f_lo) / (f_hi - f_lo + 1e-10)
    y = int((1.0 - frac) * height)
    return max(0, min(height - 1, y))


def render_freq_scale(output_png, width, height, freq_min, freq_max, font_size=38):
    """Render NASA telemetry frequency scale overlay."""

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    font = None
    for fp in font_paths:
        try:
            font = ImageFont.truetype(fp, font_size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    small_font = None
    for fp in font_paths:
        try:
            small_font = ImageFont.truetype(fp, int(font_size * 0.55))
            break
        except Exception:
            continue
    if small_font is None:
        small_font = font

    header_font = None
    for fp in font_paths:
        try:
            header_font = ImageFont.truetype(fp, int(font_size * 0.65))
            break
        except Exception:
            continue
    if header_font is None:
        header_font = font

    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    f_lo = float(freq_min)
    f_hi = float(freq_max)

    majors, minors = generate_tick_freqs(f_lo, f_hi)

    # Measure max label width
    max_label_w = 0
    for freq in majors:
        label = format_freq(freq)
        bbox = font.getbbox(label)
        lw = bbox[2] - bbox[0]
        if lw > max_label_w:
            max_label_w = lw

    # Panel dimensions
    major_tick_len = 20
    minor_tick_len = 10
    gap = 8
    right_pad = 14
    panel_w = major_tick_len + gap + max_label_w + right_pad + 4
    panel_x = width - panel_w

    # Semi-transparent dark background
    bg = Image.new('RGBA', (panel_w, height), (5, 8, 5, 160))
    img.paste(bg, (panel_x, 0), bg)
    draw = ImageDraw.Draw(img)

    # Colors — green-tinted telemetry
    label_color = (180, 210, 180, 255)       # muted green-white
    major_tick_color = (120, 160, 120, 220)  # dim green
    minor_tick_color = (60, 80, 60, 140)     # very dim green
    header_color = (100, 130, 100, 200)      # dim header
    bracket_color = (80, 110, 80, 180)       # bracket lines

    # Vertical rule line along panel left edge
    draw.line([(panel_x + 1, 0), (panel_x + 1, height)],
              fill=bracket_color, width=1)

    # Header: "FREQ" and "HZ" stacked
    hdr_x = panel_x + major_tick_len + gap
    draw.text((hdr_x, 6), "FREQ", fill=header_color, font=small_font)
    h1_bbox = small_font.getbbox("FREQ")
    draw.text((hdr_x, 6 + (h1_bbox[3] - h1_bbox[1]) + 2), "HZ", fill=header_color, font=small_font)

    # Draw minor ticks
    for freq in minors:
        y = freq_to_y(freq, f_lo, f_hi, height)
        draw.line([(panel_x + 2, y), (panel_x + 2 + minor_tick_len, y)],
                  fill=minor_tick_color, width=1)

    # Draw major ticks with labels
    label_x = panel_x + major_tick_len + gap
    for freq in majors:
        y = freq_to_y(freq, f_lo, f_hi, height)
        label = format_freq(freq)

        # Major tick — thicker
        draw.line([(panel_x + 2, y), (panel_x + 2 + major_tick_len, y)],
                  fill=major_tick_color, width=2)

        # Small bracket marks at tick ends
        draw.line([(panel_x + 2, y - 3), (panel_x + 2, y + 3)],
                  fill=major_tick_color, width=1)

        # Label — right-aligned
        bbox = font.getbbox(label)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        lx = label_x + (max_label_w - lw)
        ly = y - lh // 2 - 2

        # Clamp
        ly = max(2, min(height - lh - 2, ly))

        draw.text((lx, ly), label, fill=label_color, font=font)

    # Bottom and top border lines
    draw.line([(panel_x, 0), (width, 0)], fill=bracket_color, width=1)
    draw.line([(panel_x, height - 1), (width, height - 1)], fill=bracket_color, width=1)

    img.save(output_png)


def main():
    parser = argparse.ArgumentParser(description='Render frequency scale overlay PNG')
    parser.add_argument('--output', required=True, help='Output PNG')
    parser.add_argument('--width', type=int, required=True, help='Viewport width')
    parser.add_argument('--height', type=int, required=True, help='Viewport height')
    parser.add_argument('--freq-min', type=float, required=True)
    parser.add_argument('--freq-max', type=float, required=True)
    parser.add_argument('--font-size', type=int, default=38)
    args = parser.parse_args()

    render_freq_scale(
        output_png=args.output,
        width=args.width,
        height=args.height,
        freq_min=args.freq_min,
        freq_max=args.freq_max,
        font_size=args.font_size,
    )


if __name__ == '__main__':
    main()
