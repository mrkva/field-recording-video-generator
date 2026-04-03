#!/usr/bin/env python3
"""Render the metadata info panel as a PNG image."""

import argparse
import re
import os
from PIL import Image, ImageDraw, ImageFont


def parse_datetime_from_filename(filename):
    """Extract date/time from common field recorder filename patterns."""
    basename = os.path.splitext(os.path.basename(filename))[0]

    # ISO with separators: 2026-03-08T07_47_03
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})[T_ \-](\d{2})[_\-:](\d{2})[_\-:](\d{2})', basename)
    if m:
        y, mo, d, h, mi, s = m.groups()
        if 1990 <= int(y) <= 2099:
            return f"{y}-{mo}-{d}T{h}:{mi}:{s}"

    # Compact: YYYYMMDD_HHMMSS
    m = re.search(r'(\d{4})(\d{2})(\d{2})[_\-T](\d{2})(\d{2})(\d{2})', basename)
    if m:
        y, mo, d, h, mi, s = m.groups()
        if 1990 <= int(y) <= 2099:
            return f"{y}-{mo}-{d}T{h}:{mi}:{s}"

    # Short year: YYMMDD_HHMMSS
    m = re.search(r'(?<!\d)(\d{2})(\d{2})(\d{2})[_\-](\d{2})(\d{2})(\d{2})(?!\d)', basename)
    if m:
        y, mo, d, h, mi, s = m.groups()
        century = "20" if int(y) < 80 else "19"
        return f"{century}{y}-{mo}-{d}T{h}:{mi}:{s}"

    return None


def render_info_panel(output_png, width, font_size,
                      filename="", subject="", recorder="", datetime_str="",
                      location="", playback_speed=""):
    """Render the info panel with industrial monospace aesthetic.

    Auto-sizes height to fit content tightly. Returns actual height.
    """

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", font_size)
    except Exception:
        try:
            # macOS fallback
            font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", font_size)
        except Exception:
            font = ImageFont.load_default()

    text_color = (220, 220, 220)
    label_color = (140, 140, 140)
    padding_x = 28
    padding_y = 20
    line_gap = 6  # tight spacing between lines

    lines = []
    if filename:
        lines.append(("FILE: ", os.path.basename(filename)))
    if subject:
        lines.append(("SUBJECT: ", subject))
    if recorder:
        lines.append(("RECORDER: ", recorder))
    if datetime_str:
        lines.append(("DATE: ", datetime_str))
    if location:
        lines.append(("LOCATION: ", location))
    if playback_speed and playback_speed != "1x":
        lines.append(("PLAYBACK: ", playback_speed))

    if not lines:
        lines.append(("", ""))

    # Measure line height from the font
    line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
    total_text_height = len(lines) * line_height + (len(lines) - 1) * line_gap
    panel_height = total_text_height + 2 * padding_y + 2  # +2 for separator line

    img = Image.new('RGB', (width, panel_height), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)

    y = padding_y
    for label, value in lines:
        draw.text((padding_x, y), label, fill=label_color, font=font)
        label_w = draw.textlength(label, font=font)
        draw.text((padding_x + label_w, y), value, fill=text_color, font=font)
        y += line_height + line_gap

    # Separator line at bottom
    draw.line([(0, panel_height - 1), (width, panel_height - 1)],
              fill=(50, 50, 50), width=1)

    img.save(output_png)
    return panel_height


def main():
    parser = argparse.ArgumentParser(description='Render info panel PNG')
    parser.add_argument('--output', required=True, help='Output PNG')
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--font-size', type=int, default=22)
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

    panel_height = render_info_panel(
        output_png=args.output,
        width=args.width,
        font_size=args.font_size,
        filename=args.filename,
        subject=args.subject,
        recorder=args.recorder,
        datetime_str=datetime_str,
        location=args.location,
        playback_speed=args.playback_speed,
    )

    # Output actual height for the shell script to use
    print(f"panel_height={panel_height}")


if __name__ == '__main__':
    main()
