#!/usr/bin/env python3
"""Render the metadata info panel as a PNG — NASA telemetry aesthetic."""

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


def render_info_panel(output_png, width, font_size,
                      filename="", subject="", recorder="", datetime_str="",
                      location="", playback_speed="", coordinates=""):
    """Render info panel — NASA/telemetry camera overlay aesthetic.

    All caps, monospace, tight layout with technical formatting.
    Optionally includes a retro map widget in the top-right corner.
    """

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

    # NASA telemetry colors
    value_color = (230, 230, 230)
    label_color = (120, 120, 120)
    separator_color = (50, 50, 50)
    bg_color = (8, 8, 8)

    padding_x = 30
    padding_y = 22
    line_gap = 8

    max_text_w = width - 2 * padding_x
    line_height = font.getbbox("AY")[3] - font.getbbox("AY")[1] + 2

    # Build entries — all uppercase
    entries = []
    if filename:
        entries.append(("FILE  ", os.path.basename(filename).upper()))
    if subject:
        entries.append(("SUBJ  ", subject.upper()))
    if recorder:
        entries.append(("REC   ", recorder.upper()))
    if datetime_str:
        entries.append(("DATE  ", datetime_str.upper()))
    if location:
        entries.append(("LOC   ", location.upper()))
    if playback_speed and not playback_speed.upper().startswith("1X"):
        entries.append(("SPEED ", playback_speed.upper()))

    if not entries:
        entries.append(("", ""))

    # Wrap long lines
    all_lines = []  # list of (label_or_none, text)
    for label, value in entries:
        full = label + value
        current = ""
        is_first = True
        for ch in full:
            test = current + ch
            if font.getlength(test) > max_text_w and current:
                all_lines.append((is_first, current))
                current = ch
                is_first = False
            else:
                current = test
        if current:
            all_lines.append((is_first, current))

    total_h = 2 * padding_y + len(all_lines) * line_height + (len(entries) - 1) * line_gap + 2
    img = Image.new('RGB', (width, total_h), color=bg_color)
    draw = ImageDraw.Draw(img)

    y = padding_y
    entry_idx = 0
    line_in_entry = 0
    for i, (is_first, text) in enumerate(all_lines):
        if is_first and i > 0:
            y += line_gap  # gap between entries

        # Split label from value on first line of each entry
        if is_first:
            # Find the double-space separator between label and value
            sep_pos = text.find("  ")
            if sep_pos >= 0:
                label_part = text[:sep_pos + 2]
                value_part = text[sep_pos + 2:]
                draw.text((padding_x, y), label_part, fill=label_color, font=font)
                lw = font.getlength(label_part)
                draw.text((padding_x + lw, y), value_part, fill=value_color, font=font)
            else:
                draw.text((padding_x, y), text, fill=value_color, font=font)
        else:
            # Continuation line — indent to match value position
            draw.text((padding_x, y), text, fill=value_color, font=font)

        y += line_height

    # Render map widget in top-right corner if coordinates provided
    if coordinates:
        from render_map_widget import render_map_widget, parse_coordinates
        coords = parse_coordinates(coordinates)
        if coords:
            map_size = max(total_h - 12, font_size * 5)
            map_img = render_map_widget(coords[0], coords[1],
                                        widget_size=map_size,
                                        font_size=max(10, font_size // 3))
            if map_img is not None:
                map_x = width - map_size - 6
                map_y = 6
                # Ensure panel is tall enough
                if map_size + 12 > total_h:
                    new_h = map_size + 12
                    new_img = Image.new('RGB', (width, new_h), color=bg_color)
                    new_img.paste(img, (0, 0))
                    img = new_img
                    draw = ImageDraw.Draw(img)
                    total_h = new_h
                img.paste(map_img, (map_x, map_y))

    # Bottom separator — thin line
    draw.line([(0, total_h - 1), (width, total_h - 1)],
              fill=separator_color, width=1)

    img.save(output_png)
    return total_h


def main():
    parser = argparse.ArgumentParser(description='Render info panel PNG')
    parser.add_argument('--output', required=True, help='Output PNG')
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--font-size', type=int, default=30)
    parser.add_argument('--filename', default='')
    parser.add_argument('--subject', default='')
    parser.add_argument('--recorder', default='')
    parser.add_argument('--datetime', default='')
    parser.add_argument('--location', default='')
    parser.add_argument('--playback-speed', default='')
    parser.add_argument('--coordinates', default='')

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
        font_size=args.font_size,
        filename=args.filename,
        subject=args.subject,
        recorder=args.recorder,
        datetime_str=datetime_str,
        location=args.location,
        playback_speed=args.playback_speed,
        coordinates=args.coordinates,
    )

    print(f"panel_height={panel_height}")


if __name__ == '__main__':
    main()
