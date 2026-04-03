#!/usr/bin/env python3
"""Render a retro pixelated map widget showing recording location.

Fetches real OSM tiles, applies B&W pixelated retro filter, adds crosshair.
Falls back gracefully (returns None) if tiles can't be fetched.
"""

import math
import io
import urllib.request
from PIL import Image, ImageDraw, ImageFont
import numpy as np


def latlon_to_tile(lat, lon, zoom):
    """Convert lat/lon to OSM tile x, y coordinates."""
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    lat_rad = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)
    return x, y


def latlon_to_pixel_offset(lat, lon, zoom, tile_x, tile_y):
    """Get pixel offset within a tile for exact lat/lon position."""
    n = 2 ** zoom
    x_frac = (lon + 180) / 360 * n - tile_x
    lat_rad = math.radians(lat)
    y_frac = (1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n - tile_y
    return int(x_frac * 256), int(y_frac * 256)


def fetch_tiles(lat, lon, zoom=13):
    """Fetch a 3x3 grid of OSM tiles centered on lat/lon. Returns PIL Image or None."""
    tx, ty = latlon_to_tile(lat, lon, zoom)
    tile_size = 256
    canvas = Image.new('RGB', (tile_size * 3, tile_size * 3), (40, 40, 40))

    for dx in range(-1, 2):
        for dy in range(-1, 2):
            url = f'https://tile.openstreetmap.org/{zoom}/{tx + dx}/{ty + dy}.png'
            req = urllib.request.Request(url, headers={
                'User-Agent': 'field-recording-video-generator/1.0'
            })
            try:
                data = urllib.request.urlopen(req, timeout=8).read()
                tile = Image.open(io.BytesIO(data))
                canvas.paste(tile, ((dx + 1) * tile_size, (dy + 1) * tile_size))
            except Exception:
                return None

    # Get pixel offset for the exact location within center tile
    px_off, py_off = latlon_to_pixel_offset(lat, lon, zoom, tx, ty)
    center_x = tile_size + px_off
    center_y = tile_size + py_off

    return canvas, center_x, center_y


def apply_retro_filter(img, widget_size):
    """Apply B&W pixelated retro filter to a map image."""
    # Crop square around center
    cx, cy = img.size[0] // 2, img.size[1] // 2
    half = min(cx, cy, widget_size)
    cropped = img.crop((cx - half, cy - half, cx + half, cy + half))

    # Resize to widget size
    cropped = cropped.resize((widget_size, widget_size), Image.Resampling.LANCZOS)

    # Convert to grayscale
    arr = np.array(cropped).astype(float)
    gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2])

    # Normalize to full range
    g_min, g_max = gray.min(), gray.max()
    if g_max > g_min:
        gray = (gray - g_min) / (g_max - g_min)
    else:
        gray = gray * 0

    # Invert: dark background with bright features (roads, buildings pop)
    gray = 1.0 - gray

    # Aggressive S-curve contrast to separate features from background
    # Sigmoid-like: pushes darks darker, lights lighter
    gray = 1.0 / (1.0 + np.exp(-10 * (gray - 0.5)))

    # Scale to dark range: max brightness ~140 for dark theme
    gray = (gray * 140).clip(0, 255).astype(np.uint8)

    result = np.stack([gray, gray, gray], axis=-1)
    return Image.fromarray(result)


def render_map_widget(lat, lon, widget_size=180, font_size=0):
    """Render a retro map widget. Returns PIL Image or None if tiles unavailable."""

    if font_size <= 0:
        font_size = max(12, widget_size // 10)

    result = fetch_tiles(lat, lon, zoom=14)
    if result is None:
        return None

    canvas, center_x, center_y = result

    # Crop centered on exact location — tighter crop for more zoom
    half = widget_size * 3 // 4
    cropped = canvas.crop((
        center_x - half, center_y - half,
        center_x + half, center_y + half
    ))

    # Apply retro filter
    img = apply_retro_filter(cropped, widget_size)
    draw = ImageDraw.Draw(img)

    # Grid lines — 4 divisions so center line aligns with crosshair
    grid_spacing = widget_size // 4
    for gx in range(grid_spacing, widget_size, grid_spacing):
        draw.line([(gx, 0), (gx, widget_size - 1)], fill=(60, 60, 60), width=1)
    for gy in range(grid_spacing, widget_size, grid_spacing):
        draw.line([(0, gy), (widget_size - 1, gy)], fill=(60, 60, 60), width=1)

    # Crosshair at center (exactly on grid intersection)
    cx, cy = widget_size // 2, widget_size // 2
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

    # Border
    draw.rectangle([(0, 0), (widget_size - 1, widget_size - 1)],
                   outline=(180, 180, 180), width=2)

    # Coordinate text at bottom
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

    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"
    coord_text = f"{abs(lat):.2f}{lat_dir} {abs(lon):.2f}{lon_dir}"
    bbox = font.getbbox(coord_text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    # Dark background behind text for readability
    text_y = widget_size - th - 8
    draw.rectangle([(4, text_y - 2), (tw + 8, widget_size - 4)],
                   fill=(0, 0, 0))
    draw.text((6, text_y), coord_text, fill=(220, 220, 220), font=font)

    return img


def parse_coordinates(text):
    """Try to parse coordinates from a string. Returns (lat, lon) or None.

    Accepts formats:
    - "51.07, 0.03"
    - "51.07N, 0.03E"
    - "51.07N 0.03E"
    - "-51.07, 0.03"
    """
    import re

    # Try decimal with N/S/E/W
    m = re.match(
        r'^\s*(-?\d+\.?\d*)\s*([NSns])[\s,]+(-?\d+\.?\d*)\s*([EWew])\s*$',
        text
    )
    if m:
        lat = float(m.group(1))
        if m.group(2).upper() == 'S':
            lat = -lat
        lon = float(m.group(3))
        if m.group(4).upper() == 'W':
            lon = -lon
        return lat, lon

    # Try plain decimal pair
    m = re.match(r'^\s*(-?\d+\.?\d*)\s*[,\s]+\s*(-?\d+\.?\d*)\s*$', text)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon

    return None


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Render retro map widget')
    parser.add_argument('--output', required=True, help='Output PNG')
    parser.add_argument('--coordinates', required=True, help='Lat,lon string')
    parser.add_argument('--size', type=int, default=180, help='Widget size in px')
    parser.add_argument('--font-size', type=int, default=12)
    args = parser.parse_args()

    coords = parse_coordinates(args.coordinates)
    if coords is None:
        print("Could not parse coordinates")
        import sys
        sys.exit(1)

    lat, lon = coords
    img = render_map_widget(lat, lon, widget_size=args.size, font_size=args.font_size)
    if img is None:
        print("map=none")
    else:
        img.save(args.output)
        print(f"map=ok")
