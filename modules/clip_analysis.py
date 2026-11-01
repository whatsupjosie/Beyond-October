"""Measured technical analysis of a video clip (no AI model required).

Everything reported here is computed from the file with ffprobe/ffmpeg and
numpy: format, sharpness, exposure, hard cuts, loudness, noise floor. These
are measurements, not verdicts. What cannot be measured this way (story,
Dutch angle, crossing the 180-degree line, whether a cut is a "bad" jump cut)
is listed in `not_measured` so no caller presents a guess as analysis.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

MAX_BYTES = 2 * 1024 ** 3
MAX_SECONDS = 15 * 60
_W, _H = 320, 180
_SAMPLE_FPS = 6
_TIMEOUT = 120

NOT_MEASURED = [
    "story, performance, or pacing quality",
    "Dutch angle (tilted horizon)",
    "whether a cut crosses the 180-degree line",
    "whether a hard cut is a jarring jump cut or an intentional edit",
]


class ClipAnalysisError(RuntimeError):
    pass


def _run(cmd: List[str], *, binary: bool = False) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=_TIMEOUT, check=False, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as exc:
        raise ClipAnalysisError("Analysis timed out") from exc


def _tools() -> None:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise ClipAnalysisError("ffmpeg/ffprobe are not installed")


def probe(path: Path) -> Dict[str, Any]:
    r = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", "--", str(path)])
    if r.returncode != 0:
        raise ClipAnalysisError("ffprobe could not read this file as media")
    info = json.loads(r.stdout or b"{}")
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float(info.get("format", {}).get("duration") or (v or {}).get("duration") or 0)
    fps = None
    if v and v.get("avg_frame_rate") and "/" in v["avg_frame_rate"]:
        n, d = v["avg_frame_rate"].split("/")
        fps = round(float(n) / float(d), 3) if float(d) else None
    return {
        "duration_s": round(dur, 2),
        "container": info.get("format", {}).get("format_name"),
        "bitrate_kbps": round(int(info["format"]["bit_rate"]) / 1000) if info.get("format", {}).get("bit_rate") else None,
        "video": None if not v else {"codec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"), "fps": fps},
        "audio": None if not a else {"codec": a.get("codec_name"), "sample_rate": int(a.get("sample_rate") or 0), "channels": a.get("channels")},
    }


def _frames(path: Path) -> np.ndarray:
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-an", "-vf",
           f"fps={_SAMPLE_FPS},scale={_W}:{_H},format=gray", "-f", "rawvideo", "-"]
    r = _run(cmd)
    if r.returncode != 0:
        raise ClipAnalysisError("Could not decode video frames")
    raw = np.frombuffer(r.stdout, dtype=np.uint8)
    n = raw.size // (_W * _H)
    return raw[: n * _W * _H].reshape(n, _H, _W)


def _laplacian_var(frame: np.ndarray) -> float:
    f = frame.astype(np.float32)
    lap = f[1:-1, 1:-1] * -4 + f[:-2, 1:-1] + f[2:, 1:-1] + f[1:-1, :-2] + f[1:-1, 2:]
    return float(lap.var())


def _video_metrics(frames: np.ndarray) -> Dict[str, Any]:
    if len(frames) == 0:
        return {}
    sharp = np.array([_laplacian_var(f) for f in frames])
    mean_luma = frames.reshape(len(frames), -1).mean(axis=1)
    flat = frames.reshape(len(frames), -1)
    crushed = float((flat <= 8).mean())
    blown = float((flat >= 247).mean())
    hist = np.stack([np.bincount(f.ravel() >> 3, minlength=32) for f in frames]).astype(np.float32)
    hist /= hist.sum(axis=1, keepdims=True)
    diffs = 0.5 * np.abs(np.diff(hist, axis=0)).sum(axis=1) if len(frames) > 1 else np.array([])
    pix = np.abs(np.diff(frames.astype(np.int16), axis=0)).mean(axis=(1, 2)) if len(frames) > 1 else np.array([])
    cuts: List[float] = []
    for i in range(len(diffs)):
        # A hard cut changes the luminance histogram AND most pixels at once.
        if diffs[i] > 0.25 and pix[i] > 18 and (i == 0 or diffs[i] > 2.5 * max(diffs[i - 1], 0.02)):
            cuts.append(round((i + 1) / _SAMPLE_FPS, 2))
    med = float(np.median(sharp))
    soft = [round(i / _SAMPLE_FPS, 1) for i in range(len(sharp)) if med > 0 and sharp[i] < 0.4 * med]
    return {
        "sharpness_median": round(med, 1),
        "sharpness_min": round(float(sharp.min()), 1),
        "soft_moments_s": soft[:20],
        "soft_fraction": round(len(soft) / len(sharp), 3),
        "mean_brightness_0_255": round(float(mean_luma.mean()), 1),
        "crushed_blacks_fraction": round(crushed, 3),
        "blown_highlights_fraction": round(blown, 3),
        "hard_cuts_at_s": cuts,
        "frames_sampled": int(len(frames)),
    }


def _audio_metrics(path: Path) -> Dict[str, Any]:
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    r = _run(cmd)
    if r.returncode != 0 or len(r.stdout) < 3200:
        return {}
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    win = 800  # 50 ms at 16 kHz
    n = len(x) // win
    if n < 4:
        return {}
    rms = np.sqrt((x[: n * win].reshape(n, win) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    peak = 20 * math.log10(max(float(np.abs(x).max()), 1e-9))
    clipped = float((np.abs(x) >= 0.999).mean())
    floor, loud = float(np.percentile(db, 10)), float(np.percentile(db, 95))
    return {
        "peak_dbfs": round(peak, 1),
        "clipped_sample_fraction": round(clipped, 5),
        "noise_floor_dbfs": round(floor, 1),
        "loud_level_dbfs": round(loud, 1),
        "approx_signal_to_noise_db": round(loud - floor, 1),
        "silent_whole_track": bool(db.max() < -70),
    }


def findings(info: Dict[str, Any], v: Dict[str, Any], a: Dict[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    vid = info.get("video") or {}
    if vid.get("height") and vid["height"] < 720:
        out.append({"area": "resolution", "note": f"{vid.get('width')}x{vid['height']} is below 720p; fine detail and keying/tracking will be limited."})
    if v:
        if v["soft_fraction"] >= 0.15:
            out.append({"area": "focus", "note": f"About {round(v['soft_fraction']*100)}% of sampled moments are much softer than the clip's typical sharpness (around {', '.join(str(t) for t in v['soft_moments_s'][:5])} s). Could be missed focus, motion blur, or intentional."})
        if v["sharpness_median"] < 8 and v["soft_fraction"] < 0.15:
            out.append({"area": "focus", "note": f"The whole clip has very little fine detail (sharpness {v['sharpness_median']}). That means soft focus or heavy blur, but a plain, dark, or flat scene also scores low, so check it by eye."})
        if v["blown_highlights_fraction"] > 0.05:
            out.append({"area": "exposure", "note": f"{round(v['blown_highlights_fraction']*100)}% of pixels are near pure white; highlights may be clipped."})
        if v["crushed_blacks_fraction"] > 0.25:
            out.append({"area": "exposure", "note": f"{round(v['crushed_blacks_fraction']*100)}% of pixels are near pure black; shadow detail may be lost."})
        if v["mean_brightness_0_255"] < 50:
            out.append({"area": "exposure", "note": "The clip is dark overall."})
    if a:
        if a.get("silent_whole_track"):
            out.append({"area": "audio", "note": "The audio track is silent."})
        else:
            if a["clipped_sample_fraction"] > 0.001:
                out.append({"area": "audio", "note": "Audio clips (hits full scale); distortion is likely and cannot be fully repaired."})
            if a["approx_signal_to_noise_db"] < 20:
                out.append({"area": "audio", "note": f"Noise is high: only about {a['approx_signal_to_noise_db']} dB between the loud parts and the background. Noise reduction (for example in Audacity) may help."})
            if a["loud_level_dbfs"] < -30:
                out.append({"area": "audio", "note": "The recording level is low; normalizing will raise the noise with it."})
    elif info.get("audio") is None:
        out.append({"area": "audio", "note": "The file has no audio track."})
    return out


def analyze_technical(path: str | Path) -> Dict[str, Any]:
    _tools()
    p = Path(path)
    if not p.is_file():
        raise ClipAnalysisError("File not found")
    if p.stat().st_size > MAX_BYTES:
        raise ClipAnalysisError("File too large to analyze")
    info = probe(p)
    if not info.get("video"):
        raise ClipAnalysisError("No video stream found")
    if info["duration_s"] > MAX_SECONDS:
        raise ClipAnalysisError(f"Clip is longer than {MAX_SECONDS // 60} minutes")
    v = _video_metrics(_frames(p))
    a = _audio_metrics(p) if info.get("audio") else {}
    return {"level": "technical", "file": p.name, "format": info, "video": v, "audio": a,
            "findings": findings(info, v, a), "not_measured": NOT_MEASURED}


def render_as_repete(result: Dict[str, Any]) -> str:
    """Speak the measured result in RePete's voice, without overclaiming."""
    f, v = result["format"], result["video"]
    vid = f["video"]
    lines = [f"Okay, technical pass on {result['file']}. {vid['width']}x{vid['height']}, {vid['fps']} fps, {f['duration_s']} seconds."]
    if v.get("hard_cuts_at_s"):
        cuts = v["hard_cuts_at_s"]
        lines.append(f"I count {len(cuts)} hard cut{'s' if len(cuts) != 1 else ''}, at about {', '.join(str(c) for c in cuts[:8])} s. I can see where the cuts are. I can't tell you whether any of them is a bad jump cut.")
    else:
        lines.append("I don't see any hard cuts. It plays as one continuous shot.")
    if result["findings"]:
        for item in result["findings"]:
            lines.append(f"{item['area'].capitalize()}: {item['note']}")
    else:
        lines.append("Nothing in the technical numbers jumped out at me.")
    lines.append("What I can't tell you from measurements alone: " + "; ".join(result["not_measured"]) + ". For those I need my speaking model connected.")
    return "\n".join(lines)
