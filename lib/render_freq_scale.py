#!/usr/bin/env python3
"""Render frequency scale overlay — military/industrial camera HUD style.

No background panel. Text and tick marks drawn directly with black outline
for readability against any spectrogram content. Like a drone camera OSD.
"""

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


def draw_outlined_text(draw, x, y, text, font, fill=(255, 255, 255, 255),
                       outline=(0, 0, 0, 255), thickness=2):
    """Draw text with black outline for readability on any background."""
    for dx in range(-thickness, thickness + 1):
        for dy in range(-thickness, thickness + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, fill=outline, font=font)
    draw.text((x, y), text, fill=fill, font=font)


def draw_outlined_line(draw, coords, fill=(255, 255, 255, 200),
                       outline=(0, 0, 0, 180), width=2):
    """Draw a line with dark outline for visibility."""
    x0, y0, x1, y1 = coords
    # Draw outline (thicker)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            draw.line([(x0 + dx, y0 + dy), (x1 + dx, y1 + dy)],
                      fill=outline, width=width)
    # Draw main line
    draw.line([(x0, y0), (x1, y1)], fill=fill, width=width)


def render_freq_scale(output_png, width, height, freq_min, freq_max, font_size=38):
    """Render frequency scale — no background, outlined text + ticks."""

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

    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    f_lo = float(freq_min)
    f_hi = float(freq_max)

    majors, minors = generate_tick_freqs(f_lo, f_hi)

    # Measure max label width for alignment
    max_label_w = 0
    for freq in majors:
        label = format_freq(freq)
        bbox = font.getbbox(label)
        lw = bbox[2] - bbox[0]
        if lw > max_label_w:
            max_label_w = lw

    # Layout from right edge
    right_margin = 10
    major_tick_len = 24
    minor_tick_len = 12
    gap = 6

    # Right edge of labels aligns to (width - right_margin)
    label_right = width - right_margin
    label_left = label_right - max_label_w
    tick_end = label_left - gap
    major_tick_start = tick_end - major_tick_len
    minor_tick_start = tick_end - minor_tick_len

    # Colors — white with black outline, like drone/camera OSD
    text_color = (255, 255, 255, 240)
    dim_text_color = (180, 180, 180, 200)
    tick_color = (255, 255, 255, 200)
    minor_tick_color = (180, 180, 180, 140)
    outline_color = (0, 0, 0, 220)

    # Vertical reference line along tick ends
    draw_outlined_line(draw, (tick_end, 0, tick_end, height),
                       fill=(255, 255, 255, 80), outline=(0, 0, 0, 60), width=1)

    # Minor ticks — thin, no label
    for freq in minors:
        y = freq_to_y(freq, f_lo, f_hi, height)
        draw_outlined_line(draw, (minor_tick_start, y, tick_end, y),
                           fill=minor_tick_color, outline=(0, 0, 0, 100), width=1)

    # Major ticks + labels
    for freq in majors:
        y = freq_to_y(freq, f_lo, f_hi, height)
        label = format_freq(freq)

        # Major tick
        draw_outlined_line(draw, (major_tick_start, y, tick_end, y),
                           fill=tick_color, outline=outline_color, width=2)

        # Label — right-aligned
        bbox = font.getbbox(label)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        lx = label_right - lw
        ly = y - lh // 2 - 2
        ly = max(2, min(height - lh - 2, ly))

        draw_outlined_text(draw, lx, ly, label, font,
                           fill=text_color, outline=outline_color, thickness=3)

    # "FREQ HZ" header at top right — small, dim
    hdr_bbox = small_font.getbbox("FREQ HZ")
    hdr_w = hdr_bbox[2] - hdr_bbox[0]
    hdr_x = label_right - hdr_w
    draw_outlined_text(draw, hdr_x, 8, "FREQ HZ", small_font,
                       fill=dim_text_color, outline=outline_color, thickness=2)

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
