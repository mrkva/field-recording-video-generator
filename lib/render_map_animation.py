#!/usr/bin/env python3
"""Render progressive map zoom animation frames — military targeting aesthetic.

Generates a sequence of map images from continent view (zoom ~3) to street
level (zoom 14), each with retro filter, crosshair, and coordinate overlay.
Frames are used as an image sequence in the ffmpeg pipeline.
"""

import argparse
import os
import sys
from render_map_widget import (
    fetch_tiles, apply_retro_filter, latlon_to_tile,
    latlon_to_pixel_offset, parse_coordinates
)
from PIL import Image, ImageDraw, ImageFont


def load_font(size):
    """Load font with standard fallback chain."""
    font_paths = [
        os.path.join(os.path.dirname(__file__), "VCR_OSD_MONO.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    for fp in font_paths:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_crosshair(draw, cx, cy, widget_size):
    """Draw targeting crosshair at center."""
    xh = (255, 255, 255)
    r = max(10, widget_size // 14)
    r_inner = max(4, r // 3)
    arm = max(16, widget_size // 10)

    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=xh, width=2)
    draw.line([(cx - arm, cy), (cx - r_inner, cy)], fill=xh, width=2)
    draw.line([(cx + r_inner, cy), (cx + arm, cy)], fill=xh, width=2)
    draw.line([(cx, cy - arm), (cx, cy - r_inner)], fill=xh, width=2)
    draw.line([(cx, cy + r_inner), (cx, cy + arm)], fill=xh, width=2)
    draw.ellipse([(cx - 2, cy - 2), (cx + 2, cy + 2)], fill=xh)


def draw_grid(draw, widget_size):
    """Draw targeting grid overlay."""
    grid_spacing = widget_size // 4
    for gx in range(grid_spacing, widget_size, grid_spacing):
        draw.line([(gx, 0), (gx, widget_size - 1)], fill=(60, 60, 60), width=1)
    for gy in range(grid_spacing, widget_size, grid_spacing):
        draw.line([(0, gy), (widget_size - 1, gy)], fill=(60, 60, 60), width=1)


def draw_zoom_hud(draw, widget_size, zoom, font):
    """Draw zoom level indicator and scanning text."""
    # Zoom level indicator top-left
    zoom_text = f"Z{zoom:02d}"
    draw.text((6, 4), zoom_text, fill=(180, 180, 180), font=font)

    # Scanning indicator top-right (blinking effect handled by frame timing)
    scan_text = "LOCK" if zoom >= 12 else "SCAN"
    bbox = font.getbbox(scan_text)
    tw = bbox[2] - bbox[0]
    draw.text((widget_size - tw - 6, 4), scan_text, fill=(180, 180, 180), font=font)


def render_map_frame(lat, lon, zoom, widget_size, font):
    """Render a single map frame at the given zoom level."""
    result = fetch_tiles(lat, lon, zoom=zoom)
    if result is None:
        # Create fallback dark frame with crosshair
        img = Image.new('RGB', (widget_size, widget_size), (8, 8, 8))
        draw = ImageDraw.Draw(img)
        cx, cy = widget_size // 2, widget_size // 2
        draw_crosshair(draw, cx, cy, widget_size)
        draw.rectangle([(0, 0), (widget_size - 1, widget_size - 1)],
                       outline=(180, 180, 180), width=2)
        draw_zoom_hud(draw, widget_size, zoom, font)
        return img

    canvas, center_x, center_y = result

    # Crop centered on exact location
    half = widget_size * 3 // 4
    cropped = canvas.crop((
        center_x - half, center_y - half,
        center_x + half, center_y + half
    ))

    # Apply retro filter
    img = apply_retro_filter(cropped, widget_size)
    draw = ImageDraw.Draw(img)

    # Grid overlay
    draw_grid(draw, widget_size)

    # Crosshair
    cx, cy = widget_size // 2, widget_size // 2
    draw_crosshair(draw, cx, cy, widget_size)

    # Border
    draw.rectangle([(0, 0), (widget_size - 1, widget_size - 1)],
                   outline=(180, 180, 180), width=2)

    # Zoom HUD
    draw_zoom_hud(draw, widget_size, zoom, font)

    # Coordinate text at bottom
    coord_font_size = max(12, widget_size // 10)
    coord_font = load_font(coord_font_size)
    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"
    coord_text = f"{abs(lat):.2f}{lat_dir} {abs(lon):.2f}{lon_dir}"
    bbox = coord_font.getbbox(coord_text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    text_y = widget_size - th - 8
    draw.rectangle([(4, text_y - 2), (tw + 8, widget_size - 4)], fill=(0, 0, 0))
    draw.text((6, text_y), coord_text, fill=(220, 220, 220), font=coord_font)

    return img


def render_map_animation(output_dir, lat, lon, widget_size, duration, fps,
                         zoom_start=3, zoom_end=14):
    """Render map zoom animation frames.

    Generates one frame per video frame with zoom interpolated from
    zoom_start to zoom_end. Uses discrete zoom levels (integer) with
    the transition happening over the video duration.

    Returns the number of frames generated.
    """
    os.makedirs(output_dir, exist_ok=True)

    font_size = max(12, widget_size // 12)
    font = load_font(font_size)

    total_frames = int(duration * fps)
    zoom_levels = list(range(zoom_start, zoom_end + 1))
    num_zooms = len(zoom_levels)

    # Pre-render one image per zoom level, then duplicate for frame timing
    # This avoids re-fetching tiles for every frame
    zoom_images = {}
    for z in zoom_levels:
        sys.stderr.write(f"\r  Fetching map tiles zoom {z}/{zoom_end}...")
        sys.stderr.flush()
        zoom_images[z] = render_map_frame(lat, lon, z, widget_size, font)

    sys.stderr.write("\r  Writing map frames...                    \n")
    sys.stderr.flush()

    # Distribute frames across zoom levels
    # Spend less time on low zooms, more on mid-range for dramatic effect
    # Use an ease-in curve: zoom accelerates at start, decelerates at end
    for frame_idx in range(total_frames):
        t = frame_idx / max(1, total_frames - 1)  # 0.0 to 1.0

        # Ease-out curve: fast zoom at start, settling at end
        eased_t = 1.0 - (1.0 - t) ** 2.5

        zoom_float = zoom_start + eased_t * (zoom_end - zoom_start)
        zoom_int = min(zoom_end, max(zoom_start, int(zoom_float)))

        img = zoom_images[zoom_int]
        img.save(os.path.join(output_dir, f"map_{frame_idx:06d}.png"))

    return total_frames


def main():
    parser = argparse.ArgumentParser(description='Render map zoom animation frames')
    parser.add_argument('--output-dir', required=True, help='Output directory for frame PNGs')
    parser.add_argument('--coordinates', required=True, help='Lat,lon string')
    parser.add_argument('--size', type=int, required=True, help='Widget size in px')
    parser.add_argument('--duration', type=float, required=True, help='Video duration in seconds')
    parser.add_argument('--fps', type=int, required=True, help='Video frame rate')
    parser.add_argument('--zoom-start', type=int, default=3, help='Starting zoom level')
    parser.add_argument('--zoom-end', type=int, default=14, help='Ending zoom level')
    args = parser.parse_args()

    coords = parse_coordinates(args.coordinates)
    if coords is None:
        print("Could not parse coordinates", file=sys.stderr)
        sys.exit(1)

    lat, lon = coords
    num_frames = render_map_animation(
        output_dir=args.output_dir,
        lat=lat, lon=lon,
        widget_size=args.size,
        duration=args.duration,
        fps=args.fps,
        zoom_start=args.zoom_start,
        zoom_end=args.zoom_end,
    )
    print(f"map_frames={num_frames}")


if __name__ == '__main__':
    main()
