#!/usr/bin/env python3
"""Generate a reassigned spectrogram as a wide PNG image.

Reassignment sharpens time-frequency localization by shifting energy from
each STFT bin to its instantaneous frequency and group delay, producing
much tighter harmonic ridges than a standard spectrogram.  Requires three
STFTs per frame (standard window, time-ramped window, derivative window).
"""

import argparse
import sys
import numpy as np
from scipy.io import wavfile
from scipy.ndimage import gaussian_filter
import matplotlib
matplotlib.use('Agg')
from PIL import Image


def load_audio_mono(path):
    """Load WAV file and mix to mono float64."""
    sr, data = wavfile.read(path)
    if data.dtype == np.int16:
        data = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float64) / 2147483648.0
    elif data.dtype == np.uint8:
        data = (data.astype(np.float64) - 128.0) / 128.0
    elif data.dtype in (np.float32, np.float64):
        data = data.astype(np.float64)
    else:
        data = data.astype(np.float64)

    if data.ndim > 1:
        data = data.mean(axis=1)

    return sr, data


def _stft(audio, window, fft_size, hop):
    """Compute STFT with a given window. Returns complex matrix [freq, time]."""
    n_frames = max(1, 1 + (len(audio) - fft_size) // hop)
    # Build frames via stride tricks (vectorized, no Python loop)
    shape = (n_frames, fft_size)
    strides = (audio.strides[0] * hop, audio.strides[0])
    frames = np.lib.stride_tricks.as_strided(audio, shape=shape, strides=strides)
    windowed = frames * window[np.newaxis, :]
    # rfft along the last axis, then transpose to [freq, time]
    return np.fft.rfft(windowed, axis=1).T


def compute_reassigned_spectrogram(audio, sr, fft_size=1024, hop_size=128,
                                   freq_min=20, freq_max=None,
                                   width=None, height=None,
                                   dynamic_range=60):
    """Compute a reassigned spectrogram and return a normalized 2D grid.

    Returns (grid, f_edges, t_edges) where grid is [freq_bins, time_bins].
    """
    if freq_max is None or freq_max <= 0:
        freq_max = sr / 2.0

    n = fft_size
    # Standard Hann window
    window = 0.5 * (1 - np.cos(2 * np.pi * np.arange(n) / n))
    # Time-ramped window: t[n] * w[n]
    t_ramp = np.arange(n, dtype=np.float64)
    tw_window = t_ramp * window
    # Derivative window: dw/dt  (analytic for Hann)
    dw_window = (np.pi / n) * np.sin(2 * np.pi * np.arange(n) / n)

    # Three STFTs
    S_w = _stft(audio, window, n, hop_size)
    S_tw = _stft(audio, tw_window, n, hop_size)
    S_dw = _stft(audio, dw_window, n, hop_size)

    n_freq, n_time = S_w.shape
    mag_sq = np.abs(S_w) ** 2

    # Magnitude threshold: discard bins below -dynamic_range dB from peak
    peak = mag_sq.max()
    threshold = peak * 10 ** (-dynamic_range / 10)
    mask = mag_sq > threshold

    # Nominal time and frequency coordinates
    t_centers = np.arange(n_time) * hop_size / sr
    f_centers = np.arange(n_freq) * sr / n

    t_grid, f_grid = np.meshgrid(t_centers, f_centers)

    # Reassigned coordinates (only where mask is True)
    ratio_tw = np.zeros_like(S_w)
    ratio_dw = np.zeros_like(S_w)
    ratio_tw[mask] = S_tw[mask] / S_w[mask]
    ratio_dw[mask] = S_dw[mask] / S_w[mask]

    # t_hat = t + Re(S_tw / S_w) / sr  (time-ramped gives sample offset)
    t_hat = np.where(mask, t_grid + np.real(ratio_tw) / sr, t_grid)
    # f_hat = f - Im(S_dw / S_w) / (2*pi)  (derivative gives freq offset)
    f_hat = np.where(mask, f_grid - np.imag(ratio_dw) / (2 * np.pi), f_grid)

    # Energy to accumulate
    energy = np.where(mask, mag_sq, 0)

    # Target grid dimensions
    duration = len(audio) / sr
    if width is None:
        width = n_time
    if height is None:
        height = n_freq

    t_edges = np.linspace(0, duration, width + 1)
    f_edges = np.linspace(freq_min, freq_max, height + 1)

    # Accumulate into reassigned grid using histogram2d
    grid, _, _ = np.histogram2d(
        f_hat[mask].ravel(),
        t_hat[mask].ravel(),
        bins=[f_edges, t_edges],
        weights=energy[mask].ravel(),
    )

    # Light Gaussian smoothing to fill sparse gaps between reassigned bins.
    # Without this, the histogram has a grid-like pattern of empty cells
    # because reassigned coordinates land on a sparse subset of output bins.
    # sigma ~1.0 pixel is just enough to close the gaps without blurring
    # the sharpness that reassignment provides.
    grid = gaussian_filter(grid, sigma=1.0)

    return grid, f_edges, t_edges


def generate_reassigned_spectrogram(input_wav, output_png, width, height,
                                    colormap_name='inferno', freq_min=20,
                                    freq_max=None, dynamic_range=60,
                                    original_sr=None, grid_lines=False,
                                    fft_window=1024):
    """Generate a wide reassigned spectrogram PNG from a WAV file."""

    sr, audio = load_audio_mono(input_wav)
    duration = len(audio) / sr

    if freq_max is None or freq_max <= 0:
        freq_max = sr / 2.0
    if original_sr and original_sr > 0:
        freq_max_display = original_sr / 2.0
    else:
        freq_max_display = freq_max
        original_sr = sr

    fft_size = fft_window if fft_window > 0 else 1024
    hop_size = fft_size // 8  # 87.5% overlap, same as standard method

    # Process in chunks for memory efficiency
    chunk_duration = 30  # seconds
    chunk_samples = int(chunk_duration * sr)
    # Overlap between chunks to avoid boundary artifacts
    overlap_samples = fft_size * 2

    all_chunks = []
    pos = 0

    while pos < len(audio):
        end = min(pos + chunk_samples + overlap_samples, len(audio))
        chunk = audio[pos:end]

        if len(chunk) < fft_size:
            chunk = np.pad(chunk, (0, fft_size - len(chunk)))

        # Compute reassigned spectrogram for this chunk
        chunk_grid, f_edges, t_edges = compute_reassigned_spectrogram(
            chunk, sr,
            fft_size=fft_size,
            hop_size=hop_size,
            freq_min=freq_min,
            freq_max=freq_max,
            width=int(np.ceil(len(chunk) / len(audio) * width)),
            height=height,
            dynamic_range=dynamic_range,
        )

        # Trim overlap columns (except for first chunk)
        if pos > 0 and chunk_grid.shape[1] > 0:
            overlap_cols = int(np.ceil(overlap_samples / len(chunk) * chunk_grid.shape[1]))
            chunk_grid = chunk_grid[:, overlap_cols:]

        all_chunks.append(chunk_grid)
        pos += chunk_samples

    if not all_chunks:
        print("ERROR: No spectrogram data generated", file=sys.stderr)
        sys.exit(1)

    # Concatenate all chunks
    full_grid = np.concatenate(all_chunks, axis=1)

    # Convert to dB scale
    full_grid = 10.0 * np.log10(full_grid + 1e-12)

    # Normalize to dynamic range
    vmax = full_grid.max()
    vmin = vmax - dynamic_range
    full_grid = np.clip(full_grid, vmin, vmax)
    full_grid = (full_grid - vmin) / (vmax - vmin + 1e-10)

    # Apply colormap
    cmap = matplotlib.colormaps.get_cmap(colormap_name)
    colored = cmap(full_grid)
    colored = (colored[:, :, :3] * 255).astype(np.uint8)

    # Flip vertically (low freq at bottom)
    colored = colored[::-1, :, :]

    # Resize to exact target dimensions
    img = Image.fromarray(colored)
    img = img.resize((width, height), Image.LANCZOS)

    # Draw frequency grid lines if requested
    if grid_lines:
        img_arr = np.array(img)

        f_lo = float(freq_min)
        f_hi = float(freq_max)
        f_range = f_hi - f_lo

        if f_range > 100000:
            step = 10000
        elif f_range > 40000:
            step = 5000
        elif f_range > 10000:
            step = 1000
        elif f_range > 5000:
            step = 1000
        elif f_range > 2000:
            step = 500
        elif f_range > 500:
            step = 100
        else:
            step = 50

        f_val = step
        while f_val < f_hi:
            if f_val > f_lo:
                frac = (f_val - f_lo) / (f_hi - f_lo + 1e-10)
                y = int((1.0 - frac) * height)
                y = max(0, min(height - 1, y))
                blend = 0.12
                row = img_arr[y].astype(np.float32)
                grid_color = np.array([180, 220, 180], dtype=np.float32)
                img_arr[y] = (row * (1 - blend) + grid_color * blend).astype(np.uint8)
            f_val += step

        img = Image.fromarray(img_arr)

    img.save(output_png, optimize=True)

    return {
        'width': width,
        'height': height,
        'duration': duration,
        'sample_rate': sr,
        'original_sample_rate': original_sr,
    }


def main():
    parser = argparse.ArgumentParser(description='Generate reassigned spectrogram PNG')
    parser.add_argument('--input', required=True, help='Input WAV file')
    parser.add_argument('--output', required=True, help='Output PNG file')
    parser.add_argument('--width', type=int, required=True, help='Image width in pixels')
    parser.add_argument('--height', type=int, required=True, help='Image height in pixels')
    parser.add_argument('--colormap', default='inferno', help='Matplotlib colormap')
    parser.add_argument('--freq-min', type=float, default=20, help='Min frequency Hz')
    parser.add_argument('--freq-max', type=float, default=0, help='Max frequency Hz (0=Nyquist)')
    parser.add_argument('--dynamic-range', type=float, default=60, help='Dynamic range in dB')
    parser.add_argument('--original-sr', type=int, default=0, help='Original sample rate')
    parser.add_argument('--grid', action='store_true', help='Draw frequency grid lines')
    parser.add_argument('--fft-window', type=int, default=1024, help='FFT window size')
    args = parser.parse_args()

    info = generate_reassigned_spectrogram(
        input_wav=args.input,
        output_png=args.output,
        width=args.width,
        height=args.height,
        colormap_name=args.colormap,
        freq_min=args.freq_min,
        freq_max=args.freq_max if args.freq_max > 0 else None,
        dynamic_range=args.dynamic_range,
        original_sr=args.original_sr if args.original_sr > 0 else None,
        grid_lines=args.grid,
        fft_window=args.fft_window,
    )

    for k, v in info.items():
        print(f"{k}={v}")


if __name__ == '__main__':
    main()
