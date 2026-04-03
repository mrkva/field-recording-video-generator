#!/usr/bin/env python3
"""Render a transparent frequency scale overlay PNG for the right edge of the spectrogram viewport."""

import argparse
from PIL import Image, ImageDraw, ImageFont


def generate_tick_freqs(f_lo, f_hi):
    """Generate nice tick frequencies for the given range."""
    f_range = f_hi - f_lo

    # Choose step based on range, favoring denser ticks
    if f_range > 100000:
        step = 10000
    elif f_range > 40000:
        step = 5000
    elif f_range > 10000:
        step = 1000
    elif f_range > 5000:
        step = 1000
    elif f_range > 2000:
        step = 500
    elif f_range > 500:
        step = 100
    else:
        step = 50

    ticks = []
    f_val = step
    while f_val < f_hi:
        if f_val > f_lo:
            ticks.append(f_val)
        f_val += step
    return ticks


def format_freq(freq):
    """Format frequency as compact label: 1k, 2k, 10k, 500, etc."""
    if freq >= 1000:
        val = freq / 1000
        if val == int(val):
            return f"{int(val)}k"
        else:
            return f"{val:.1f}k"
    else:
        return f"{int(freq)}"


def render_freq_scale(output_png, width, height, freq_min, freq_max, font_size=42):
    """Render a transparent overlay with frequency scale on the right side."""

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

    # Smaller font for the "Hz" header
    header_font = None
    for fp in font_paths:
        try:
            header_font = ImageFont.truetype(fp, int(font_size * 0.7))
            break
        except Exception:
            continue
    if header_font is None:
        header_font = font

    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    f_lo = float(freq_min)
    f_hi = float(freq_max)

    tick_freqs = generate_tick_freqs(f_lo, f_hi)

    # Compute positions
    tick_positions = []
    for freq in tick_freqs:
        frac = (freq - f_lo) / (f_hi - f_lo + 1e-10)
        y = int((1.0 - frac) * height)
        y = max(0, min(height - 1, y))
        tick_positions.append((freq, y))

    # Measure max label width to position elements
    max_label_w = 0
    for freq, y in tick_positions:
        label = format_freq(freq)
        bbox = font.getbbox(label)
        lw = bbox[2] - bbox[0]
        if lw > max_label_w:
            max_label_w = lw

    hz_bbox = header_font.getbbox("Hz")
    hz_w = hz_bbox[2] - hz_bbox[0]
    max_label_w = max(max_label_w, hz_w)

    tick_len = 14
    gap = 10  # gap between tick and label
    panel_w = tick_len + gap + max_label_w + 20  # 20 = right padding
    panel_x = width - panel_w

    # Draw semi-transparent dark background strip on the right
    bg = Image.new('RGBA', (panel_w, height), (0, 0, 0, 140))
    img.paste(bg, (panel_x, 0), bg)

    # Recalculate draw after paste
    draw = ImageDraw.Draw(img)

    label_x = panel_x + tick_len + gap
    label_color = (220, 220, 220, 255)
    tick_color = (180, 180, 180, 200)
    dim_color = (140, 140, 140, 255)

    # Draw "Hz" header at top right
    hz_x = label_x + (max_label_w - hz_w) // 2
    draw.text((hz_x, 8), "Hz", fill=dim_color, font=header_font)

    # Draw ticks and labels
    for freq, y in tick_positions:
        label = format_freq(freq)

        # Tick mark
        draw.line([(panel_x, y), (panel_x + tick_len, y)],
                  fill=tick_color, width=2)

        # Label — right-aligned
        bbox = font.getbbox(label)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        lx = label_x + (max_label_w - lw)  # right-align
        ly = y - lh // 2 - 2

        # Clamp to image bounds
        ly = max(2, min(height - lh - 2, ly))

        draw.text((lx, ly), label, fill=label_color, font=font)

    img.save(output_png)


def main():
    parser = argparse.ArgumentParser(description='Render frequency scale overlay PNG')
    parser.add_argument('--output', required=True, help='Output PNG')
    parser.add_argument('--width', type=int, required=True, help='Viewport width')
    parser.add_argument('--height', type=int, required=True, help='Viewport height')
    parser.add_argument('--freq-min', type=float, required=True)
    parser.add_argument('--freq-max', type=float, required=True)
    parser.add_argument('--font-size', type=int, default=42)
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
