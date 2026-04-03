#!/usr/bin/env python3
"""Generate a high-precision logarithmic spectrogram as a wide PNG image."""

import argparse
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import spectrogram as scipy_spectrogram
from scipy.interpolate import interp1d
import matplotlib
matplotlib.use('Agg')
import matplotlib.cm as cm


def load_audio_mono(path):
    """Load WAV file and mix to mono float64."""
    sr, data = wavfile.read(path)
    # Convert to float64
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

    # Mix to mono
    if data.ndim > 1:
        data = data.mean(axis=1)

    return sr, data


def compute_spectrogram_chunk(audio, sr, nperseg, hop, freq_min, freq_max, height):
    """Compute log-frequency spectrogram for a chunk of audio."""
    f, t, Sxx = scipy_spectrogram(
        audio,
        fs=sr,
        window='hann',
        nperseg=nperseg,
        noverlap=nperseg - hop,
        scaling='spectrum',
        mode='magnitude'
    )

    # Convert to power and then dB
    Sxx = Sxx ** 2
    Sxx_dB = 10.0 * np.log10(Sxx + 1e-12)

    # Build log-frequency axis
    f_min = max(freq_min, f[1])  # avoid 0 Hz for log scale
    f_max = min(freq_max, f[-1])
    log_freqs = np.logspace(np.log10(f_min), np.log10(f_max), height)

    # Interpolate to log frequency scale (vectorized)
    Sxx_log = np.zeros((height, Sxx_dB.shape[1]), dtype=np.float32)
    for col_idx in range(Sxx_dB.shape[1]):
        interp_fn = interp1d(f, Sxx_dB[:, col_idx], bounds_error=False,
                             fill_value=-120.0, kind='linear')
        Sxx_log[:, col_idx] = interp_fn(log_freqs)

    return Sxx_log, log_freqs, t


def generate_spectrogram(input_wav, output_png, width, height,
                         colormap_name='inferno', freq_min=20, freq_max=None,
                         dynamic_range=90, original_sr=None):
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

    # Calculate target width
    total_frames = int(np.ceil(len(audio) / hop))
    pixels_per_second = max(100, min(400, width / max(duration, 0.1)))

    # Process in chunks for memory efficiency
    chunk_duration = 30  # seconds
    chunk_samples = int(chunk_duration * sr)
    overlap_samples = nperseg  # overlap between chunks

    all_columns = []
    pos = 0

    while pos < len(audio):
        end = min(pos + chunk_samples + overlap_samples, len(audio))
        chunk = audio[pos:end]

        if len(chunk) < nperseg:
            # Pad short final chunk
            chunk = np.pad(chunk, (0, nperseg - len(chunk)))

        Sxx_log, log_freqs, t = compute_spectrogram_chunk(
            chunk, sr, nperseg, hop, freq_min, freq_max, height
        )

        # Trim overlap columns (except for first chunk)
        if pos > 0 and Sxx_log.shape[1] > 0:
            overlap_cols = int(np.ceil(overlap_samples / hop))
            Sxx_log = Sxx_log[:, overlap_cols:]

        all_columns.append(Sxx_log)
        pos += chunk_samples

    if not all_columns:
        print("ERROR: No spectrogram data generated", file=sys.stderr)
        sys.exit(1)

    # Concatenate all chunks
    full_spec = np.concatenate(all_columns, axis=1)

    # Resize to target width
    from PIL import Image

    # Normalize to dynamic range
    vmax = full_spec.max()
    vmin = vmax - dynamic_range
    full_spec = np.clip(full_spec, vmin, vmax)
    full_spec = (full_spec - vmin) / (vmax - vmin + 1e-10)

    # Apply colormap
    cmap = matplotlib.colormaps.get_cmap(colormap_name)
    colored = cmap(full_spec)  # RGBA float [0,1]
    colored = (colored[:, :, :3] * 255).astype(np.uint8)

    # Flip vertically (low freq at bottom)
    colored = colored[::-1, :, :]

    # Resize to target dimensions
    img = Image.fromarray(colored)
    img = img.resize((width, height), Image.LANCZOS)

    # Draw frequency axis ticks on the left edge
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 11)
    except Exception:
        font = ImageFont.load_default()

    # Frequency tick marks (using original/display frequencies)
    freq_ratio = freq_max_display / freq_max if freq_max > 0 else 1.0
    tick_freqs = []
    f_val = 50
    while f_val <= freq_max_display:
        tick_freqs.append(f_val)
        if f_val < 200:
            f_val += 50
        elif f_val < 1000:
            f_val += 200
        elif f_val < 10000:
            f_val += 2000
        elif f_val < 50000:
            f_val += 10000
        else:
            f_val += 25000

    f_min_log = np.log10(max(freq_min, 20))
    f_max_log = np.log10(freq_max_display)

    for freq in tick_freqs:
        if freq < freq_min * freq_ratio or freq > freq_max_display:
            continue
        # Position in image (log scale, flipped)
        frac = (np.log10(freq) - f_min_log) / (f_max_log - f_min_log + 1e-10)
        y = int((1.0 - frac) * height)
        y = max(0, min(height - 1, y))

        # Tick line
        draw.line([(0, y), (5, y)], fill=(200, 200, 200), width=1)

        # Label
        if freq >= 1000:
            label = f"{freq/1000:.0f}k"
        else:
            label = f"{freq:.0f}"
        draw.text((7, y - 6), label, fill=(180, 180, 180), font=font)

    img.save(output_png, optimize=True)

    # Return metadata
    return {
        'width': width,
        'height': height,
        'duration': duration,
        'sample_rate': sr,
        'original_sample_rate': original_sr,
    }


def main():
    parser = argparse.ArgumentParser(description='Generate logarithmic spectrogram PNG')
    parser.add_argument('--input', required=True, help='Input WAV file')
    parser.add_argument('--output', required=True, help='Output PNG file')
    parser.add_argument('--width', type=int, required=True, help='Image width in pixels')
    parser.add_argument('--height', type=int, required=True, help='Image height in pixels')
    parser.add_argument('--colormap', default='inferno', help='Matplotlib colormap')
    parser.add_argument('--freq-min', type=float, default=20, help='Min frequency Hz')
    parser.add_argument('--freq-max', type=float, default=0, help='Max frequency Hz (0=Nyquist)')
    parser.add_argument('--dynamic-range', type=float, default=90, help='Dynamic range in dB')
    parser.add_argument('--original-sr', type=int, default=0, help='Original sample rate for labeling')
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
    )

    # Output metadata as key=value for shell consumption
    for k, v in info.items():
        print(f"{k}={v}")


if __name__ == '__main__':
    main()
