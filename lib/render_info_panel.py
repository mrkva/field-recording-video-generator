#!/usr/bin/env python3
"""Render the metadata info panel as a PNG — NASA telemetry aesthetic."""

import argparse
import re
import os
import unicodedata
from PIL import Image, ImageDraw, ImageFont


# Characters that don't decompose via NFKD normalization
_SPECIAL_TRANSLIT = {
    'ø': 'o', 'Ø': 'O', 'đ': 'd', 'Đ': 'D', 'ð': 'd', 'Ð': 'D',
    'ł': 'l', 'Ł': 'L', 'ß': 'ss', 'æ': 'ae', 'Æ': 'AE',
    'œ': 'oe', 'Œ': 'OE', 'þ': 'th', 'Þ': 'TH',
}


def transliterate(text):
    """Strip diacritical marks so text renders with basic Latin fonts.

    Š -> S, č -> c, ñ -> n, ü -> u, etc.
    """
    # Handle characters that don't decompose cleanly
    for orig, repl in _SPECIAL_TRANSLIT.items():
        if orig in text:
            text = text.replace(orig, repl)
    # NFD splits e.g. Š into S + combining caron; drop the combining marks
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


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
                      location="", playback_speed="", coordinates="",
                      sample_info="", dynamic_time=False, animated_map=False,
                      max_value_chars=32):
    """Render info panel — NASA/telemetry camera overlay aesthetic.

    All caps, monospace, tight layout with technical formatting.
    Optionally includes a retro map widget in the top-right corner.
    """

    font_paths = [
        os.path.join(os.path.dirname(__file__), "VCR_OSD_MONO.ttf"),
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

    # Build entries — all uppercase, transliterated for font compatibility
    # Label column is 7 chars wide (padded with spaces) for alignment
    label_width = 7
    entries = []
    if filename:
        entries.append(("FILE", transliterate(os.path.basename(filename)).upper()))
    if subject:
        entries.append(("SUBJ", transliterate(subject).upper()))
    if datetime_str:
        entries.append(("TIME", transliterate(datetime_str).upper()))
    if location:
        entries.append(("LOC", transliterate(location).upper()))
    if recorder:
        entries.append(("EQUIP", transliterate(recorder).upper()))
    if sample_info:
        entries.append(("SMPL", transliterate(sample_info).upper()))
    if playback_speed and not playback_speed.upper().startswith("1X"):
        entries.append(("SPEED", transliterate(playback_speed).upper()))

    if not entries:
        entries.append(("", ""))

    # Compute label column pixel width (fixed for alignment)
    label_col_text = "X" * label_width
    label_col_px = font.getlength(label_col_text)
    value_x = padding_x + label_col_px

    # Determine if map widget will be shown, to reserve space for it
    map_reserve_w = 0
    if coordinates:
        from render_map_widget import parse_coordinates
        coords = parse_coordinates(coordinates)
        if coords:
            # Estimate map size (will be computed properly later)
            est_lines = len(entries) + 1
            est_h = 2 * padding_y + est_lines * line_height + (len(entries) - 1) * line_gap + 2
            map_size = max(est_h - 12, font_size * 5)
            map_reserve_w = map_size + 16  # map width + margins

    max_value_w = width - value_x - padding_x - map_reserve_w

    # Character width for monospace font
    char_w = font.getlength("X")

    # Check which values overflow and need scrolling
    scroll_fields = []  # list of (label, y_pos, full_text, strip_png) — filled during rendering
    all_lines = []  # list of (label, value_text, needs_scroll)
    for label, value in entries:
        if len(value) > max_value_chars:
            all_lines.append((label, value, True))
        else:
            all_lines.append((label, value, False))

    total_h = 2 * padding_y + len(all_lines) * line_height + (len(all_lines) - 1) * line_gap + 2
    img = Image.new('RGB', (width, total_h), color=bg_color)
    draw = ImageDraw.Draw(img)

    # FFmpeg drawtext y= positions at top of rendered glyphs, while Pillow
    # draw.text y= includes the font's top bearing (ascent padding above glyphs).
    # Compute the offset so drawtext values align with Pillow-rendered labels.
    drawtext_y_offset = font.getbbox("A")[1]  # top bearing in pixels

    timecode_x = 0
    timecode_y = 0
    y = padding_y
    for i, (label, text, needs_scroll) in enumerate(all_lines):
        if i > 0:
            y += line_gap

        # Draw label padded to fixed column
        padded_label = label.ljust(label_width)
        draw.text((padding_x, y), padded_label, fill=label_color, font=font)

        # If dynamic_time, skip rendering the TIME value (drawtext will handle it)
        if dynamic_time and label == "TIME":
            timecode_x = int(value_x)
            timecode_y = int(y + drawtext_y_offset)
        elif needs_scroll:
            # Record scroll field for drawtext animation in ffmpeg
            scroll_fields.append((label, int(y + drawtext_y_offset), text))
        else:
            draw.text((value_x, y), text, fill=value_color, font=font)
        y += line_height

    # Render map widget in top-right corner if coordinates provided
    map_overlay_x = 0
    map_overlay_y = 0
    map_overlay_size = 0
    if coordinates:
        from render_map_widget import parse_coordinates
        coords = parse_coordinates(coordinates)
        if coords:
            map_size = max(total_h - 12, font_size * 5)
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

            if animated_map:
                # Leave map area dark for ffmpeg overlay animation
                map_overlay_x = map_x
                map_overlay_y = map_y
                map_overlay_size = map_size
            else:
                from render_map_widget import render_map_widget
                map_img = render_map_widget(coords[0], coords[1],
                                            widget_size=map_size)
                if map_img is not None:
                    img.paste(map_img, (map_x, map_y))

    # Bottom separator — thin line
    draw.line([(0, total_h - 1), (width, total_h - 1)],
              fill=separator_color, width=1)

    img.save(output_png)
    return (total_h, timecode_x, timecode_y, scroll_fields,
            int(value_x), max_value_chars,
            map_overlay_x, map_overlay_y, map_overlay_size)


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
    parser.add_argument('--sample-info', default='')
    parser.add_argument('--coordinates', default='')
    parser.add_argument('--dynamic-time', action='store_true',
                        help='Leave TIME value blank for drawtext overlay')
    parser.add_argument('--animated-map', action='store_true',
                        help='Reserve map space but leave blank for animated overlay')
    parser.add_argument('--max-value-chars', type=int, default=32,
                        help='Max characters for value fields before scrolling')
    args = parser.parse_args()

    datetime_str = args.datetime
    if not datetime_str and args.filename:
        detected = parse_datetime_from_filename(args.filename)
        if detected:
            datetime_str = detected
        else:
            datetime_str = "UNKNOWN"

    (panel_height, tc_x, tc_y, scroll_fields, val_x, max_chars,
     map_x, map_y, map_size) = render_info_panel(
        output_png=args.output,
        width=args.width,
        font_size=args.font_size,
        filename=args.filename,
        subject=args.subject,
        recorder=args.recorder,
        datetime_str=datetime_str,
        location=args.location,
        playback_speed=args.playback_speed,
        sample_info=args.sample_info,
        coordinates=args.coordinates,
        dynamic_time=args.dynamic_time,
        animated_map=args.animated_map,
        max_value_chars=args.max_value_chars,
    )

    print(f"panel_height={panel_height}")
    if args.dynamic_time:
        print(f"timecode_x={tc_x}")
        print(f"timecode_y={tc_y}")
    if args.animated_map and map_size > 0:
        print(f"map_x={map_x}")
        print(f"map_y={map_y}")
        print(f"map_size={map_size}")
    for label, y_pos, text in scroll_fields:
        # Escape colons and backslashes for safe parsing
        safe_text = text.replace('\\', '\\\\').replace(':', '\\:')
        print(f"scroll_field={y_pos}:{safe_text}")
    if scroll_fields:
        print(f"scroll_value_x={val_x}")
        print(f"scroll_max_chars={max_chars}")


if __name__ == '__main__':
    main()
