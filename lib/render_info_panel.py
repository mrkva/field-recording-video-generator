#!/usr/bin/env python3
"""Render the metadata info panel as a PNG image with pixelated font."""

import argparse
import re
import os
from PIL import Image, ImageDraw, ImageFont


def parse_datetime_from_filename(filename):
    """Extract date/time from common field recorder filename patterns."""
    basename = os.path.splitext(os.path.basename(filename))[0]

    m = re.search(r'(\d{4})-(\d{2})-(\d{2})[T_ \-](\d{2})[_\-:](\d{2})[_\-:](\d{2})', basename)
    if m:
        y, mo, d, h, mi, s = m.groups()
        if 1990 <= int(y) <= 2099:
            return f"{y}-{mo}-{d}T{h}:{mi}:{s}"

    m = re.search(r'(\d{4})(\d{2})(\d{2})[_\-T](\d{2})(\d{2})(\d{2})', basename)
    if m:
        y, mo, d, h, mi, s = m.groups()
        if 1990 <= int(y) <= 2099:
            return f"{y}-{mo}-{d}T{h}:{mi}:{s}"

    m = re.search(r'(?<!\d)(\d{2})(\d{2})(\d{2})[_\-](\d{2})(\d{2})(\d{2})(?!\d)', basename)
    if m:
        y, mo, d, h, mi, s = m.groups()
        century = "20" if int(y) < 80 else "19"
        return f"{century}{y}-{mo}-{d}T{h}:{mi}:{s}"

    return None


def render_info_panel(output_png, width, pixel_scale,
                      filename="", subject="", recorder="", datetime_str="",
                      location="", playback_speed=""):
    """Render info panel with pixelated monospace aesthetic.

    Renders at low resolution then scales up with nearest-neighbor
    for a chunky pixel look. All text is uppercase.
    """

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 12)
    except Exception:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 12)
        except Exception:
            font = ImageFont.load_default()

    text_color = (220, 220, 220)
    label_color = (140, 140, 140)
    padding_x = 10
    padding_y = 8
    line_height = 16
    line_gap = 2

    # Low-res canvas width
    lo_w = width // pixel_scale

    # Build lines with wrapping — all text uppercase
    entries = []
    if filename:
        entries.append(("FILE: ", os.path.basename(filename).upper()))
    if subject:
        entries.append(("SUBJECT: ", subject.upper()))
    if recorder:
        entries.append(("RECORDER: ", recorder.upper()))
    if datetime_str:
        entries.append(("DATE: ", datetime_str.upper()))
    if location:
        entries.append(("LOCATION: ", location.upper()))
    if playback_speed and playback_speed != "1x":
        entries.append(("PLAYBACK: ", playback_speed.upper()))

    if not entries:
        entries.append(("", ""))

    max_text_w = lo_w - 2 * padding_x

    # Pre-compute wrapped lines
    wrapped_lines = []
    for label, value in entries:
        full_text = label + value
        # Character-level wrapping
        current_line = ""
        for ch in full_text:
            test = current_line + ch
            if font.getlength(test) > max_text_w and current_line:
                wrapped_lines.append(current_line)
                current_line = ch
            else:
                current_line = test
        if current_line:
            wrapped_lines.append(current_line)
        # Add a blank gap between entries
        wrapped_lines.append(None)

    # Remove trailing None
    while wrapped_lines and wrapped_lines[-1] is None:
        wrapped_lines.pop()

    # Calculate low-res height
    visible_lines = sum(1 for l in wrapped_lines if l is not None)
    gap_lines = sum(1 for l in wrapped_lines if l is None)
    lo_h = (2 * padding_y + visible_lines * line_height +
            gap_lines * (line_gap + 2) + 2)

    # Render at low res
    img = Image.new('RGB', (lo_w, lo_h), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)

    y = padding_y
    for line in wrapped_lines:
        if line is None:
            y += line_gap + 2
            continue
        # Color the label portion dim, value bright
        # Detect label by looking for ": " prefix
        drawn = False
        for sep_idx in range(len(line)):
            if line[sep_idx:sep_idx+2] == ": ":
                label_part = line[:sep_idx+2]
                value_part = line[sep_idx+2:]
                draw.text((padding_x, y), label_part, fill=label_color, font=font)
                lw = font.getlength(label_part)
                draw.text((padding_x + lw, y), value_part, fill=text_color, font=font)
                drawn = True
                break
        if not drawn:
            # Continuation line — all bright
            draw.text((padding_x, y), line, fill=text_color, font=font)
        y += line_height

    # Separator line at bottom
    draw.line([(0, lo_h - 1), (lo_w, lo_h - 1)], fill=(50, 50, 50), width=1)

    # Scale up with nearest-neighbor for pixel effect
    final_h = lo_h * pixel_scale
    img = img.resize((width, final_h), Image.NEAREST)

    img.save(output_png)
    return final_h


def main():
    parser = argparse.ArgumentParser(description='Render info panel PNG')
    parser.add_argument('--output', required=True, help='Output PNG')
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--pixel-scale', type=int, default=3)
    parser.add_argument('--filename', default='')
    parser.add_argument('--subject', default='')
    parser.add_argument('--recorder', default='')
    parser.add_argument('--datetime', default='')
    parser.add_argument('--location', default='')
    parser.add_argument('--playback-speed', default='')

    args = parser.parse_args()

    datetime_str = args.datetime
    if not datetime_str and args.filename:
        detected = parse_datetime_from_filename(args.filename)
        if detected:
            datetime_str = detected
        else:
            datetime_str = "UNKNOWN"

    panel_height = render_info_panel(
        output_png=args.output,
        width=args.width,
        pixel_scale=args.pixel_scale,
        filename=args.filename,
        subject=args.subject,
        recorder=args.recorder,
        datetime_str=datetime_str,
        location=args.location,
        playback_speed=args.playback_speed,
    )

    print(f"panel_height={panel_height}")


if __name__ == '__main__':
    main()
