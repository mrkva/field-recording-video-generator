#!/usr/bin/env python3
"""Render timecode frames as individual PNGs (one per second).

Generates transparent PNG images showing the current time in ISO format.
Used as an image-sequence overlay in the video pipeline.
"""

import argparse
import datetime
import os
import sys

from PIL import Image, ImageDraw, ImageFont


def render_timecode_frames(output_dir, start_datetime, duration_seconds,
                           font_size=34, speed_factor=1.0, margin=20):
    """Render one transparent PNG per second with the current timestamp."""

    # Load font
    lib_dir = os.path.dirname(__file__)
    font_paths = [
        os.path.join(lib_dir, "VCR_OSD_MONO.ttf"),
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

    # Parse start datetime
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d'):
        try:
            start_dt = datetime.datetime.strptime(start_datetime, fmt)
            break
        except ValueError:
            continue
    else:
        print("ERROR: Could not parse datetime", file=sys.stderr)
        sys.exit(1)

    # Calculate number of video seconds
    video_seconds = int(duration_seconds) + 1

    # Measure text size for consistent frame dimensions
    sample_text = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
    bbox = font.getbbox(sample_text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    frame_w = text_w + margin * 2
    frame_h = text_h + margin

    for i in range(video_seconds):
        # Recording time for this video second
        recording_offset = i / speed_factor
        current_dt = start_dt + datetime.timedelta(seconds=recording_offset)
        timestamp = current_dt.strftime("%Y-%m-%dT%H:%M:%S")

        img = Image.new('RGBA', (frame_w, frame_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Shadow
        draw.text((margin + 2, 2), timestamp, fill=(0, 0, 0, 200), font=font)
        # Text
        draw.text((margin, 0), timestamp, fill=(230, 230, 230, 255), font=font)

        img.save(os.path.join(output_dir, f"tc_{i:06d}.png"))

    print(f"tc_frame_w={frame_w}")
    print(f"tc_frame_h={frame_h}")
    print(f"tc_frame_count={video_seconds}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Render timecode frames')
    parser.add_argument('--output-dir', required=True, help='Output directory for PNGs')
    parser.add_argument('--start-datetime', required=True, help='Start datetime ISO')
    parser.add_argument('--duration', type=float, required=True, help='Video duration in seconds')
    parser.add_argument('--font-size', type=int, default=34)
    parser.add_argument('--speed-factor', type=float, default=1.0)
    parser.add_argument('--margin', type=int, default=20)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    render_timecode_frames(
        output_dir=args.output_dir,
        start_datetime=args.start_datetime,
        duration_seconds=args.duration,
        font_size=args.font_size,
        speed_factor=args.speed_factor,
        margin=args.margin,
    )
