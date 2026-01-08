from __future__ import annotations

import json
import subprocess
from typing import Optional

from clip_extractor.models.media import MediaInfo


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _parse_rate(rate_str: str) -> tuple[int, int]:
    if not rate_str or rate_str == "0/0":
        return 0, 1
    if "/" in rate_str:
        num_s, den_s = rate_str.split("/", 1)
        num = _safe_int(num_s, 0)
        den = _safe_int(den_s, 1) or 1
        return num, den
    try:
        # e.g. "30"
        num = int(float(rate_str))
        return num, 1
    except Exception:
        return 0, 1


def probe_media_info(ffprobe_path: str, media_path: str) -> Optional[MediaInfo]:
    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-show_streams",
        "-select_streams",
        "v:0",
        "-show_format",
        "-of",
        "json",
        media_path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except Exception:
        return None
    try:
        meta = json.loads(proc.stdout)
    except Exception:
        return None
    streams = meta.get("streams", [])
    fmt = meta.get("format", {})
    if not streams:
        return None
    v = streams[0]
    width = _safe_int(v.get("width"), 0)
    height = _safe_int(v.get("height"), 0)
    rate = v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1"
    fps_num, fps_den = _parse_rate(rate)
    duration = float(fmt.get("duration") or v.get("duration") or 0.0)
    codec = v.get("codec_name") or fmt.get("format_name") or "unknown"
    pix_fmt = v.get("pix_fmt") or "unknown"
    bitrate = None
    br = fmt.get("bit_rate") or v.get("bit_rate")
    try:
        bitrate = int(br) if br is not None else None
    except Exception:
        bitrate = None
    return MediaInfo(
        width=width,
        height=height,
        fps_num=fps_num,
        fps_den=fps_den,
        duration=duration,
        codec=codec,
        pix_fmt=pix_fmt,
        bitrate=bitrate,
    )



