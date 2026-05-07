#!/usr/bin/env python3
"""
Web interface for field-recording-video-generator.
Wraps the existing shell script pipeline with a drag-and-drop UI.

Usage:
    ./web.py                   # starts on http://localhost:5000
    ./web.py --port 8080       # custom port
    ./web.py --host 0.0.0.0    # listen on all interfaces
"""

import argparse
import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from flask import (Flask, Response, jsonify, render_template, request,
                   send_file)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR / "lib"
PRESETS_DIR = SCRIPT_DIR / "presets"
VENV_PYTHON = SCRIPT_DIR / ".venv" / "bin" / "python3"
UPLOAD_DIR = SCRIPT_DIR / "uploads"
OUTPUT_DIR = SCRIPT_DIR / "outputs"

app = Flask(__name__, template_folder=str(SCRIPT_DIR / "templates"))

# Active jobs: job_id -> {status, progress_queue, output_file, ...}
jobs = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_python():
    """Return path to the venv python, or system python as fallback."""
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def probe_audio(filepath):
    """Probe a WAV file and return metadata dict."""
    def ffprobe_field(entry, fallback=""):
        try:
            out = subprocess.check_output(
                ["ffprobe", "-v", "error", "-select_streams", "a:0",
                 "-show_entries", f"stream={entry}", "-of", "csv=p=0",
                 filepath],
                stderr=subprocess.DEVNULL, text=True
            ).strip()
            return out if out and out != "N/A" else fallback
        except Exception:
            return fallback

    sample_rate = ffprobe_field("sample_rate", "48000")
    channels = ffprobe_field("channels", "1")

    # Duration from format (more reliable)
    try:
        duration = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "format=duration", "-of", "csv=p=0",
             filepath],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        if not duration or duration == "N/A":
            duration = subprocess.check_output(
                ["sox", "--info", "-D", filepath],
                stderr=subprocess.DEVNULL, text=True
            ).strip()
    except Exception:
        duration = "0"

    # Bit depth with fallback chain
    bit_depth = ffprobe_field("bits_per_raw_sample", "")
    if not bit_depth or bit_depth == "0":
        bit_depth = ffprobe_field("bits_per_sample", "")

    codec_name = ffprobe_field("codec_name", "")
    audio_format = ""

    if codec_name in ("pcm_f32le", "pcm_f32be", "pcm_f64le", "pcm_f64be"):
        audio_format = "FLOAT"

    if not bit_depth or bit_depth == "0":
        codec_map = {
            "pcm_f32": "32", "pcm_s32": "32", "pcm_f64": "64",
            "pcm_s24": "24", "pcm_s16": "16", "pcm_u16": "16",
            "pcm_s8": "8", "pcm_u8": "8",
        }
        for prefix, bits in codec_map.items():
            if codec_name.startswith(prefix):
                bit_depth = bits
                break
        else:
            bit_depth = "16"

    sample_info = f"{sample_rate}HZ {bit_depth}BIT"
    if audio_format:
        sample_info += f" {audio_format}"

    # Date detection from filename
    detected_date = ""
    basename = os.path.basename(filepath)
    # ISO-ish: 2024-03-15_14-30-22
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})[_\-T](\d{2})-(\d{2})-(\d{2})', basename)
    if m:
        y, mo, d, h, mi, s = m.groups()
        if 1990 <= int(y) <= 2099:
            detected_date = f"{y}-{mo}-{d}T{h}:{mi}:{s}"
    if not detected_date:
        m = re.search(r'(\d{4})(\d{2})(\d{2})[_\-T](\d{2})(\d{2})(\d{2})', basename)
        if m:
            y, mo, d, h, mi, s = m.groups()
            if 1990 <= int(y) <= 2099:
                detected_date = f"{y}-{mo}-{d}T{h}:{mi}:{s}"
    if not detected_date:
        try:
            stat = os.stat(filepath)
            ts = getattr(stat, 'st_birthtime', None) or stat.st_mtime
            import datetime
            detected_date = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%dT%H:%M:%S')
        except Exception:
            pass

    return {
        "sample_rate": int(sample_rate),
        "channels": int(channels),
        "duration": float(duration),
        "bit_depth": bit_depth,
        "audio_format": audio_format,
        "sample_info": sample_info,
        "detected_date": detected_date,
        "filename": basename,
    }


def parse_playback_speed(speed_input, orig_sr):
    """Parse speed input, return (speed_factor, effective_rate, label)."""
    if not speed_input or speed_input in ("1x", "1"):
        return 1.0, orig_sr, "1x (native)"

    if ":" in speed_input:
        source, target = speed_input.split(":")
        source, target = float(source), float(target)
        factor = source / target
        return factor, int(target), f"{int(source)}Hz → {int(target)}Hz ({factor:.2f}× slower)"

    factor = float(speed_input)
    eff = int(orig_sr / factor)
    return factor, eff, f"{factor}× slower"


def load_preset(name):
    """Load a preset config file, return dict."""
    conf = {}
    path = PRESETS_DIR / f"{name}.conf"
    if not path.exists():
        path = PRESETS_DIR / "square.conf"
    with open(path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                conf[k.strip()] = int(v.strip())
    return conf


def run_pipeline(job_id, input_path, params):
    """Run the full generation pipeline in a background thread."""
    job = jobs[job_id]
    q = job["progress_queue"]
    python = get_python()

    def send(stage, message, pct=0):
        q.put({"stage": stage, "message": message, "percent": pct})

    try:
        tmpdir = tempfile.mkdtemp(prefix="frvg_web_")
        job["tmpdir"] = tmpdir

        # Load preset
        preset = load_preset(params.get("preset", "square"))
        video_w = preset["VIDEO_WIDTH"]
        video_h = preset["VIDEO_HEIGHT"]
        photo_band_h = preset.get("PHOTO_BAND_HEIGHT", 280)
        info_font_size = preset.get("INFO_FONT_SIZE", 30)
        fps = preset.get("FPS", 60)

        # Parse speed
        speed_factor, effective_rate, playback_label = parse_playback_speed(
            params.get("playback_speed", "1x"),
            int(params.get("sample_rate", 48000))
        )
        duration = float(params.get("duration", 0))
        effective_duration = duration * speed_factor

        # Probe for sample info
        sample_info = params.get("sample_info", "")
        freq_min = params.get("freq_min", "20")
        freq_max = params.get("freq_max", str(int(params.get("sample_rate", 48000)) // 2))
        fft_window = params.get("fft_window", "2048")

        # -----------------------------------------------------------
        # Stage 1: Prepare audio
        # -----------------------------------------------------------
        send(1, "Preparing audio...", 5)
        prepared_audio = os.path.join(tmpdir, "prepared_audio.wav")

        af_chain = ""
        if speed_factor != 1.0:
            af_chain = f"asetrate={effective_rate},aresample=48000"

        normalize = params.get("normalize", "y")
        if normalize in ("y", "Y", "yes"):
            # Measure loudness, apply fixed gain — no dynamic compression
            measure_cmd = ["ffmpeg", "-hide_banner", "-i", input_path]
            base_filter = f"{af_chain}," if af_chain else ""
            measure_cmd += ["-af", f"{base_filter}loudnorm=I=-16:TP=-1.5:LRA=50:print_format=json",
                           "-f", "null", "-"]
            result = subprocess.run(measure_cmd, capture_output=True, text=True)
            m = re.search(r'\{[^{}]+\}', result.stderr, re.DOTALL)
            if m:
                d = json.loads(m.group())
                measured_i = float(d['input_i'])
                measured_tp = float(d['input_tp'])
                gain = -16.0 - measured_i
                headroom = -1.5 - measured_tp
                if gain > headroom:
                    gain = headroom
                af_chain = f"{af_chain},volume={gain:.2f}dB" if af_chain else f"volume={gain:.2f}dB"

        encode_cmd = ["ffmpeg", "-y", "-v", "warning", "-i", input_path]
        if af_chain:
            encode_cmd += ["-af", af_chain]
        encode_cmd += ["-ar", "48000", "-c:a", "pcm_s24le", prepared_audio]
        subprocess.run(encode_cmd, check=True, capture_output=True)
        send(1, "Audio prepared.", 20)

        # -----------------------------------------------------------
        # Stage 2: Render info panel
        # -----------------------------------------------------------
        send(2, "Rendering info panel...", 25)
        info_png = os.path.join(tmpdir, "info_panel.png")

        panel_cmd = [
            python, str(LIB_DIR / "render_info_panel.py"),
            "--output", info_png,
            "--width", str(video_w),
            "--font-size", str(info_font_size),
            "--filename", params.get("filename", ""),
            "--subject", params.get("subject", ""),
            "--recorder", params.get("recorder", ""),
            "--datetime", params.get("datetime", ""),
            "--location", params.get("location", ""),
            "--playback-speed", playback_label,
            "--sample-info", sample_info,
            "--coordinates", params.get("coordinates", ""),
        ]
        panel_out = subprocess.check_output(panel_cmd, text=True)
        info_panel_height = 200  # default
        for line in panel_out.strip().splitlines():
            if line.startswith("panel_height="):
                info_panel_height = int(line.split("=")[1])
        send(2, "Info panel rendered.", 30)

        # -----------------------------------------------------------
        # Stage 3: Generate spectrogram
        # -----------------------------------------------------------
        send(3, "Generating spectrogram (this may take a while)...", 35)
        spec_png = os.path.join(tmpdir, "spectrogram.png")
        pps = 200
        spec_total_w = max(int(math.ceil(pps * effective_duration)), video_w)
        spec_total_w = min(spec_total_w, 300000)

        spec_h = video_h - info_panel_height

        spec_cmd = [
            python, str(LIB_DIR / "generate_spectrogram.py"),
            "--input", input_path,
            "--output", spec_png,
            "--width", str(spec_total_w),
            "--height", str(spec_h),
            "--colormap", "inferno",
            "--freq-min", str(freq_min),
            "--freq-max", str(freq_max),
            "--original-sr", str(params.get("sample_rate", 48000)),
            "--fft-window", str(fft_window),
            "--dynamic-range", "90",
        ]
        if params.get("grid", "y") in ("y", "Y", "yes"):
            spec_cmd.append("--grid")
        subprocess.run(spec_cmd, check=True, capture_output=True)
        send(3, "Spectrogram generated.", 60)

        # -----------------------------------------------------------
        # Stage 4: Render frequency scale
        # -----------------------------------------------------------
        send(4, "Rendering frequency scale...", 65)
        freq_scale_png = os.path.join(tmpdir, "freq_scale.png")
        subprocess.run([
            python, str(LIB_DIR / "render_freq_scale.py"),
            "--output", freq_scale_png,
            "--width", str(video_w),
            "--height", str(spec_h),
            "--freq-min", str(freq_min),
            "--freq-max", str(freq_max),
            "--font-size", str(info_font_size),
        ], check=True, capture_output=True)
        send(4, "Frequency scale rendered.", 70)

        # -----------------------------------------------------------
        # Stage 5: Compose video
        # -----------------------------------------------------------
        send(5, "Compositing video with ffmpeg...", 75)

        # Generate cursor image
        cursor_png = os.path.join(tmpdir, "cursor.png")
        subprocess.run([
            python, "-c", f"""
from PIL import Image
import numpy as np
w, h = 21, {spec_h}
pixels = np.zeros((h, w, 4), dtype=np.uint8)
for dx in range(-10, 11):
    dist = abs(dx)
    if dist <= 1: alpha, r, g, b = 240, 0, 255, 120
    elif dist <= 3: alpha, r, g, b = 80, 200, 255, 220
    elif dist <= 6: alpha, r, g, b = 35, 255, 255, 255
    else: alpha, r, g, b = 12, 255, 255, 255
    x = 10 + dx
    if 0 <= x < w:
        pixels[:, x] = [r, g, b, alpha]
Image.fromarray(pixels).save('{cursor_png}')
"""
        ], check=True, capture_output=True)

        # Build ffmpeg filter graph
        scroll_rate = spec_total_w / effective_duration
        half_vw = video_w / 2.0
        crop_x = f"min(max(0,{scroll_rate}*t-{half_vw}),{spec_total_w}-{video_w})"
        cursor_x = f"({scroll_rate}*t)-min(max(0,{scroll_rate}*t-{half_vw}),{spec_total_w}-{video_w})-10"

        output_file = os.path.join(str(OUTPUT_DIR), f"{job_id}.mp4")

        # thread_queue_size avoids ffmpeg 7.x scheduler stalls on image inputs.
        inputs = [
            "-thread_queue_size", "1024", "-loop", "1", "-i", spec_png,
            "-thread_queue_size", "1024", "-loop", "1", "-i", info_png,
            "-thread_queue_size", "1024", "-i", prepared_audio,
            "-thread_queue_size", "1024", "-loop", "1", "-i", cursor_png,
            "-thread_queue_size", "1024", "-loop", "1", "-i", freq_scale_png,
        ]

        fc = (
            f"[0:v]crop=w={video_w}:h={spec_h}:x='{crop_x}':y=0[spec_cropped];"
            f"[3:v]loop=-1:size=1[cur_loop];"
            f"[spec_cropped][cur_loop]overlay=x='{cursor_x}':y=0:shortest=1[spec_cursor];"
            f"[4:v]loop=-1:size=1[scale_loop];"
            f"[spec_cursor][scale_loop]overlay=x=0:y=0:shortest=1[spec_final];"
            f"[1:v]scale={video_w}:{info_panel_height}[info];"
            f"[info][spec_final]vstack[combined];"
            f"[combined]format=yuv420p[outv]"
        )

        # -t bounds the duration; -shortest is omitted — in ffmpeg 7.x it can
        # propagate EOF before the AAC encoder receives a frame, producing
        # "Could not open encoder before EOF" and an empty file.
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-v", "warning",
            *inputs,
            "-filter_complex", fc,
            "-map", "[outv]", "-map", "2:a",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-c:a", "aac", "-b:a", "256k",
            "-ac", "2",
            "-r", str(fps),
            "-t", str(effective_duration),
            "-movflags", "+faststart",
            output_file,
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)

        job["output_file"] = output_file
        job["status"] = "done"
        send(5, "Done!", 100)

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        q.put({"stage": -1, "message": f"Error: {e}", "percent": -1})
    finally:
        # Clean temp dir
        tmpdir_path = job.get("tmpdir")
        if tmpdir_path and os.path.isdir(tmpdir_path):
            shutil.rmtree(tmpdir_path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    """Upload a WAV file and return its probed metadata."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No filename"}), 400

    UPLOAD_DIR.mkdir(exist_ok=True)
    # Keep original filename for metadata detection, prefix with uuid to avoid collisions
    safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
    filepath = str(UPLOAD_DIR / safe_name)
    f.save(filepath)

    try:
        info = probe_audio(filepath)
        info["filepath"] = filepath
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate", methods=["POST"])
def generate():
    """Start video generation. Returns a job ID for progress tracking."""
    data = request.get_json()
    if not data or "filepath" not in data:
        return jsonify({"error": "Missing filepath"}), 400

    filepath = data["filepath"]
    if not os.path.isfile(filepath):
        return jsonify({"error": "File not found"}), 404

    OUTPUT_DIR.mkdir(exist_ok=True)

    job_id = uuid.uuid4().hex[:12]
    job = {
        "status": "running",
        "progress_queue": queue.Queue(),
        "output_file": None,
        "error": None,
    }
    jobs[job_id] = job

    params = {
        "filename": data.get("filename", os.path.basename(filepath)),
        "subject": data.get("subject", ""),
        "recorder": data.get("recorder", ""),
        "datetime": data.get("datetime", ""),
        "location": data.get("location", ""),
        "coordinates": data.get("coordinates", ""),
        "freq_min": data.get("freq_min", "20"),
        "freq_max": data.get("freq_max", ""),
        "playback_speed": data.get("playback_speed", "1x"),
        "preset": data.get("preset", "square"),
        "grid": data.get("grid", "y"),
        "fft_window": data.get("fft_window", "2048"),
        "normalize": data.get("normalize", "y"),
        "sample_rate": data.get("sample_rate", 48000),
        "duration": data.get("duration", 0),
        "sample_info": data.get("sample_info", ""),
    }

    t = threading.Thread(target=run_pipeline, args=(job_id, filepath, params), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/api/progress/<job_id>")
def progress(job_id):
    """SSE endpoint for progress updates."""
    if job_id not in jobs:
        return jsonify({"error": "Unknown job"}), 404

    def stream():
        q = jobs[job_id]["progress_queue"]
        while True:
            try:
                msg = q.get(timeout=30)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("percent", 0) >= 100 or msg.get("percent", 0) < 0:
                    break
            except queue.Empty:
                # Keep-alive
                yield f"data: {json.dumps({'stage': 0, 'message': 'waiting...', 'percent': -2})}\n\n"

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/download/<job_id>")
def download(job_id):
    """Download the generated video."""
    if job_id not in jobs:
        return jsonify({"error": "Unknown job"}), 404

    job = jobs[job_id]
    if job["status"] != "done" or not job.get("output_file"):
        return jsonify({"error": "Not ready"}), 400

    return send_file(job["output_file"], as_attachment=True,
                     download_name="field_recording_video.mp4")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web UI for field-recording-video-generator")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    UPLOAD_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"\n  Field Recording Video Generator — Web UI")
    print(f"  http://{args.host}:{args.port}\n")

    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
