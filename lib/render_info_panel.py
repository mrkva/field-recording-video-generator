#!/usr/bin/env python3
"""Render the metadata info panel as a PNG image."""

import argparse
import re
import os
from PIL import Image, ImageDraw, ImageFont


def parse_datetime_from_filename(filename):
    """Extract date/time from common field recorder filename patterns.

    Supported patterns:
    - YYYYMMDD_HHMMSS / YYYYMMDD-HHMMSS
    - YYMMDD_HHMMSS / YYMMDD-HHMMSS
    - Prefixed variants: ZOOM0001_YYYYMMDD_HHMMSS, SM4_YYYYMMDD_HHMMSS, etc.
    """
    basename = os.path.splitext(os.path.basename(filename))[0]

    # Try YYYYMMDD_HHMMSS (8+6 digits)
    m = re.search(r'(\d{4})(\d{2})(\d{2})[_\-T](\d{2})(\d{2})(\d{2})', basename)
    if m:
        y, mo, d, h, mi, s = m.groups()
        y_int = int(y)
        if 1990 <= y_int <= 2099:
            return f"{y}-{mo}-{d}T{h}:{mi}:{s}"

    # Try YYMMDD_HHMMSS (6+6 digits, but not matching 8-digit year blocks)
    m = re.search(r'(?<!\d)(\d{2})(\d{2})(\d{2})[_\-](\d{2})(\d{2})(\d{2})(?!\d)', basename)
    if m:
        y, mo, d, h, mi, s = m.groups()
        y_int = int(y)
        century = "20" if y_int < 80 else "19"
        return f"{century}{y}-{mo}-{d}T{h}:{mi}:{s}"

    return None


def render_info_panel(output_png, width, height, font_size, line_spacing,
                      filename="", subject="", recorder="", datetime_str="",
                      location="", playback_speed=""):
    """Render the info panel with industrial monospace aesthetic."""

    img = Image.new('RGB', (width, height), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
        font_bold = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
        font_bold = font

    text_color = (220, 220, 220)
    label_color = (130, 130, 130)
    margin_left = 32
    margin_top = 24

    lines = []
    if filename:
        lines.append(("FILE", os.path.basename(filename)))
    if subject:
        lines.append(("SUBJECT", subject))
    if recorder:
        lines.append(("RECORDER", recorder))
    if datetime_str:
        lines.append(("DATE", datetime_str))
    if location:
        lines.append(("LOCATION", location))
    if playback_speed and playback_speed != "1x":
        lines.append(("PLAYBACK", playback_speed))

    y = margin_top
    for label, value in lines:
        # Draw label in dim color
        label_text = f"{label}: "
        draw.text((margin_left, y), label_text, fill=label_color, font=font_bold)
        # Draw value in brighter color
        label_width = draw.textlength(label_text, font=font_bold)
        draw.text((margin_left + label_width, y), value, fill=text_color, font=font)
        y += line_spacing

    # Thin separator line at bottom
    draw.line([(0, height - 1), (width, height - 1)], fill=(60, 60, 60), width=1)

    img.save(output_png)


def main():
    parser = argparse.ArgumentParser(description='Render info panel PNG')
    parser.add_argument('--output', required=True, help='Output PNG')
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    parser.add_argument('--font-size', type=int, default=22)
    parser.add_argument('--line-spacing', type=int, default=28)
    parser.add_argument('--filename', default='')
    parser.add_argument('--subject', default='')
    parser.add_argument('--recorder', default='')
    parser.add_argument('--datetime', default='')
    parser.add_argument('--location', default='')
    parser.add_argument('--playback-speed', default='')

    args = parser.parse_args()

    # Auto-detect datetime from filename if not provided
    datetime_str = args.datetime
    if not datetime_str and args.filename:
        detected = parse_datetime_from_filename(args.filename)
        if detected:
            datetime_str = detected
        else:
            datetime_str = "Unknown"

    render_info_panel(
        output_png=args.output,
        width=args.width,
        height=args.height,
        font_size=args.font_size,
        line_spacing=args.line_spacing,
        filename=args.filename,
        subject=args.subject,
        recorder=args.recorder,
        datetime_str=datetime_str,
        location=args.location,
        playback_speed=args.playback_speed,
    )


if __name__ == '__main__':
    main()
