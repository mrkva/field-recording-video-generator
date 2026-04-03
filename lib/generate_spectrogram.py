#!/usr/bin/env python3
"""Generate a high-precision linear spectrogram as a wide PNG image."""

import argparse
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import spectrogram as scipy_spectrogram
import matplotlib
matplotlib.use('Agg')
from PIL import Image, ImageDraw, ImageFont


def load_audio_mono(path):
    """Load WAV file and mix to mono float64."""
    sr, data = wavfile.read(path)
    if data.dtype == np.int16:
        data = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float64) / 2147483648.0
    elif data.dtype == np.uint8:
        data = (data.astype(np.float64) - 128.0) / 128.0
    elif data.dtype == np.float32 or data.dtype == np.float64:
        data = data.astype(np.float64)
    else:
        data = data.astype(np.float64)

    if data.ndim > 1:
        data = data.mean(axis=1)

    return sr, data


def compute_spectrogram_chunk(audio, sr, nperseg, hop):
    """Compute linear-frequency spectrogram for a chunk of audio."""
    f, t, Sxx = scipy_spectrogram(
        audio,
        fs=sr,
        window='hann',
        nperseg=nperseg,
        noverlap=nperseg - hop,
        scaling='spectrum',
        mode='magnitude'
    )

    Sxx = Sxx ** 2
    Sxx_dB = 10.0 * np.log10(Sxx + 1e-12)

    return Sxx_dB, f, t


def generate_spectrogram(input_wav, output_png, width, height,
                         colormap_name='inferno', freq_min=20, freq_max=None,
                         dynamic_range=90, original_sr=None, grid=False):
    """Generate a wide spectrogram PNG from a WAV file."""

    sr, audio = load_audio_mono(input_wav)
    duration = len(audio) / sr

    if freq_max is None or freq_max <= 0:
        freq_max = sr / 2.0
    if original_sr and original_sr > 0:
        freq_max_display = original_sr / 2.0
    else:
        freq_max_display = freq_max
        original_sr = sr

    # STFT parameters
    if sr >= 96000:
        nperseg = 8192
    elif sr >= 44100:
        nperseg = 4096
    else:
        nperseg = 2048
    hop = nperseg // 8  # 87.5% overlap

    # Process in chunks for memory efficiency
    chunk_duration = 30  # seconds
    chunk_samples = int(chunk_duration * sr)
    overlap_samples = nperseg

    all_columns = []
    pos = 0

    while pos < len(audio):
        end = min(pos + chunk_samples + overlap_samples, len(audio))
        chunk = audio[pos:end]

        if len(chunk) < nperseg:
            chunk = np.pad(chunk, (0, nperseg - len(chunk)))

        Sxx_dB, f, t = compute_spectrogram_chunk(chunk, sr, nperseg, hop)

        # Trim overlap columns (except for first chunk)
        if pos > 0 and Sxx_dB.shape[1] > 0:
            overlap_cols = int(np.ceil(overlap_samples / hop))
            Sxx_dB = Sxx_dB[:, overlap_cols:]

        all_columns.append(Sxx_dB)
        pos += chunk_samples

    if not all_columns:
        print("ERROR: No spectrogram data generated", file=sys.stderr)
        sys.exit(1)

    # Concatenate all chunks
    full_spec = np.concatenate(all_columns, axis=1)

    # Crop to freq range
    freq_bin_min = 0
    freq_bin_max = len(f)
    if freq_min > 0:
        freq_bin_min = max(0, np.searchsorted(f, freq_min))
    if freq_max < f[-1]:
        freq_bin_max = min(len(f), np.searchsorted(f, freq_max) + 1)
    full_spec = full_spec[freq_bin_min:freq_bin_max, :]
    f_cropped = f[freq_bin_min:freq_bin_max]

    # Normalize to dynamic range
    vmax = full_spec.max()
    vmin = vmax - dynamic_range
    full_spec = np.clip(full_spec, vmin, vmax)
    full_spec = (full_spec - vmin) / (vmax - vmin + 1e-10)

    # Apply colormap
    cmap = matplotlib.colormaps.get_cmap(colormap_name)
    colored = cmap(full_spec)
    colored = (colored[:, :, :3] * 255).astype(np.uint8)

    # Flip vertically (low freq at bottom)
    colored = colored[::-1, :, :]

    # Resize to target dimensions
    img = Image.fromarray(colored)
    img = img.resize((width, height), Image.LANCZOS)

    # Convert to numpy for grid drawing (much faster for wide images)
    img_arr = np.array(img)

    # Draw frequency axis ticks on the left edge
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    # Linear frequency tick marks
    freq_ratio = freq_max_display / freq_max if freq_max > 0 else 1.0
    f_display_min = f_cropped[0] * freq_ratio
    f_display_max = f_cropped[-1] * freq_ratio

    # Generate nice tick values
    tick_freqs = []
    # Choose tick spacing based on range
    f_range = f_display_max - f_display_min
    if f_range > 100000:
        step = 20000
    elif f_range > 40000:
        step = 10000
    elif f_range > 15000:
        step = 5000
    elif f_range > 5000:
        step = 2000
    elif f_range > 2000:
        step = 500
    else:
        step = 100

    f_val = step
    while f_val <= f_display_max:
        if f_val >= f_display_min:
            tick_freqs.append(f_val)
        f_val += step

    # Compute tick Y positions
    tick_positions = []
    for freq in tick_freqs:
        frac = (freq - f_display_min) / (f_display_max - f_display_min + 1e-10)
        y = int((1.0 - frac) * height)
        y = max(0, min(height - 1, y))
        tick_positions.append((freq, y))

    # Draw grid lines via numpy (fast for wide images)
    if grid:
        for freq, y in tick_positions:
            blend = 0.12
            row = img_arr[y].astype(np.float32)
            grid_color = np.array([180, 220, 180], dtype=np.float32)
            img_arr[y] = (row * (1 - blend) + grid_color * blend).astype(np.uint8)
        # Rebuild PIL image from modified array
        img = Image.fromarray(img_arr)
        draw = ImageDraw.Draw(img)

    # Draw tick marks + labels on left edge
    for freq, y in tick_positions:
        draw.line([(0, y), (6, y)], fill=(200, 200, 200), width=1)

        if freq >= 1000:
            label = f"{freq/1000:.0f}K"
        else:
            label = f"{freq:.0f}"
        draw.text((8, y - 8), label, fill=(200, 200, 200), font=font)

    img.save(output_png, optimize=True)

    return {
        'width': width,
        'height': height,
        'duration': duration,
        'sample_rate': sr,
        'original_sample_rate': original_sr,
    }


def main():
    parser = argparse.ArgumentParser(description='Generate spectrogram PNG')
    parser.add_argument('--input', required=True, help='Input WAV file')
    parser.add_argument('--output', required=True, help='Output PNG file')
    parser.add_argument('--width', type=int, required=True, help='Image width in pixels')
    parser.add_argument('--height', type=int, required=True, help='Image height in pixels')
    parser.add_argument('--colormap', default='inferno', help='Matplotlib colormap')
    parser.add_argument('--freq-min', type=float, default=20, help='Min frequency Hz')
    parser.add_argument('--freq-max', type=float, default=0, help='Max frequency Hz (0=Nyquist)')
    parser.add_argument('--dynamic-range', type=float, default=90, help='Dynamic range in dB')
    parser.add_argument('--original-sr', type=int, default=0, help='Original sample rate for labeling')
    parser.add_argument('--grid', action='store_true', help='Draw frequency grid lines')
    args = parser.parse_args()

    info = generate_spectrogram(
        input_wav=args.input,
        output_png=args.output,
        width=args.width,
        height=args.height,
        colormap_name=args.colormap,
        freq_min=args.freq_min,
        freq_max=args.freq_max if args.freq_max > 0 else None,
        dynamic_range=args.dynamic_range,
        original_sr=args.original_sr if args.original_sr > 0 else None,
        grid=args.grid,
    )

    for k, v in info.items():
        print(f"{k}={v}")


if __name__ == '__main__':
    main()
