from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from typing import List, Optional, Dict, Iterable

from PySide6 import QtCore

from clip_extractor.models.media import Segment, ExportProfile


@dataclass(slots=True)
class ExportTask:
    ffmpeg: str
    segments: List[Segment]
    file_lookup: Dict[str, str]  # file_id -> path
    profile: ExportProfile
    output_path: str


class FfmpegExporter(QtCore.QObject, QtCore.QRunnable):
    progressChanged = QtCore.Signal(int, str)
    logLine = QtCore.Signal(str)
    finished = QtCore.Signal(bool, str)

    def __init__(self, task: ExportTask) -> None:
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)
        self.setAutoDelete(True)
        self._task = task
        self._cancelled = False

    @QtCore.Slot()
    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        ok, msg = self._run()
        self.finished.emit(ok, msg)

    def _run(self) -> tuple[bool, str]:
        # Prepare temp directory
        tmp_dir = tempfile.mkdtemp(prefix="clipx_")
        try:
            cut_paths: List[str] = []
            total = len(self._task.segments)
            for idx, seg in enumerate(self._task.segments, start=1):
                if self._cancelled:
                    return False, "Cancelled"
                self.progressChanged.emit(int((idx - 1) / max(1, total) * 70), f"Extracting {idx}/{total}")
                cut_out = os.path.join(tmp_dir, f"cut_{idx:03d}.mp4")
                ok, err = self._cut_segment(seg, cut_out)
                if not ok:
                    return False, err
                cut_paths.append(cut_out)

            if self._cancelled:
                return False, "Cancelled"
            self.progressChanged.emit(80, "Concatenating")
            ok, err = self._concat_cuts(cut_paths, self._task.output_path)
            if not ok:
                return False, err
            self.progressChanged.emit(100, "Done")
            return True, self._task.output_path
        finally:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    def _build_scale_filter(self) -> Optional[str]:
        p = self._task.profile
        if not p.width or not p.height:
            return None
        # Even dimensions and letterbox if requested
        w = p.width
        h = p.height
        if p.letterbox:
            return (
                f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease:flags=bicubic," 
                f"pad=w={w}:h={h}:x=(ow-iw)/2:y=(oh-ih)/2:color=black"
            )
        return f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease:flags=bicubic"

    def _maybe_overlay_watermark(self, vf_chain: List[str]) -> List[str]:
        p = self._task.profile
        if not p.watermark_enabled or not p.watermark_path:
            return vf_chain
        # Scale watermark relative to input size using percent of input width
        scale_pct = p.watermark_scale_pct or 20
        margin_l = max(0, p.watermark_margin_left)
        margin_b = max(0, p.watermark_margin_bottom)
        wm = p.watermark_path

        # Log watermark info
        self.logLine.emit(f"Adding watermark: {wm}")
        self.logLine.emit(f"Scale: {scale_pct}%, Margins: Left={margin_l}px, Bottom={margin_b}px")

        # Build filter_complex that combines video scaling (if any) with watermark overlay
        # If there's a scale filter already, we need to integrate it into the filter_complex
        if vf_chain:
            # Combine video scale with watermark overlay
            # [0:v] -> scale -> [scaled], [1:v] -> scale watermark -> [wm], [scaled]+[wm] -> overlay
            video_scale = vf_chain[0]  # e.g., "scale=w=1920:h=1080:..."
            filter_str = f"[0:v]{video_scale}[scaled];[1:v]scale=iw*{scale_pct}/100:-1[wm];[scaled][wm]overlay=x={margin_l}:y=H-h-{margin_b}"
        else:
            # No video scaling, just overlay watermark on original video
            filter_str = f"[1:v]scale=iw*{scale_pct}/100:-1[wm];[0:v][wm]overlay=x={margin_l}:y=H-h-{margin_b}"

        # Replace vf_chain with the combined filter_complex
        return [filter_str]

    def _video_codec_args(self) -> List[str]:
        p = self._task.profile
        if p.codec.lower() in ("h264", "libx264"):
            codec = "libx264"
        elif p.codec.lower() in ("h265", "hevc", "libx265"):
            codec = "libx265"
        else:
            codec = "libx264"
        args = ["-c:v", codec]
        if p.crf is not None:
            args += ["-crf", str(p.crf)]
        if p.preset:
            args += ["-preset", p.preset]
        args += ["-pix_fmt", "yuv420p"]
        if p.fps:
            args += ["-r", f"{p.fps}"]
        return args

    def _audio_codec_args(self) -> List[str]:
        p = self._task.profile
        args = ["-c:a", "aac"]
        if p.audio_bitrate:
            args += ["-b:a", p.audio_bitrate]
        return args

    def _cut_segment(self, seg: Segment, out_path: str) -> tuple[bool, str]:
        src = self._task.file_lookup.get(seg.file_id)
        if not src:
            return False, "Missing source for segment"
        vf_chain: List[str] = []
        scale = self._build_scale_filter()
        if scale:
            vf_chain.append(scale)
        vf_chain = self._maybe_overlay_watermark(vf_chain)

        cmd = [
            self._task.ffmpeg,
            "-y",
            "-ss",
            f"{seg.start}",
            "-to",
            f"{seg.end}",
            "-i",
            src,
        ]
        # watermark input if needed
        profile = self._task.profile
        if profile.watermark_enabled and profile.watermark_path:
            cmd += ["-i", profile.watermark_path]

        # Apply filters
        if vf_chain:
            # Check if watermark is being applied (needs filter_complex)
            if profile.watermark_enabled and profile.watermark_path:
                # Use filter_complex for watermark overlay
                # vf_chain[0] contains the complete filter_complex string
                cmd += ["-filter_complex", vf_chain[0]]
                # Log the filter command being used
                self.logLine.emit(f"Filter command: -filter_complex {vf_chain[0]}")
            else:
                # Use simple -vf for non-watermark filters
                cmd += ["-vf", ",".join(vf_chain)]
                # Log the filter command being used
                self.logLine.emit(f"Filter command: -vf {','.join(vf_chain)}")
        cmd += self._video_codec_args()
        cmd += self._audio_codec_args()
        cmd += [out_path]
        return self._run_cmd(cmd)

    def _concat_cuts(self, cuts: List[str], output: str) -> tuple[bool, str]:
        # For simplicity and container safety, re-mux by concat demuxer if codecs match.
        # Here we copy streams since cuts are encoded uniformly.
        list_path = output + ".concat.txt"
        try:
            with open(list_path, "w", encoding="utf-8") as f:
                for p in cuts:
                    f.write(f"file '{p}'\n")
            cmd = [
                self._task.ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_path,
                "-c",
                "copy",
                output,
            ]
            if self._task.profile.web_optimize:
                # Insert before output
                cmd.insert(-1, "-movflags")
                cmd.insert(-1, "+faststart")

            ok, err = self._run_cmd(cmd)
            if not ok:
                # Fallback to filter concat re-encode
                args: List[str] = [self._task.ffmpeg, "-y"]
                for p in cuts:
                    args += ["-i", p]
                n = len(cuts)
                filter_complex = f"concat=n={n}:v=1:a=1[v][a]"
                args += [
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[v]",
                    "-map",
                    "[a]",
                ]
                args += self._video_codec_args()
                args += self._audio_codec_args()
                if self._task.profile.web_optimize:
                    args += ["-movflags", "+faststart"]
                args += [output]
                return self._run_cmd(args)
            return True, ""
        finally:
            try:
                if os.path.exists(list_path):
                    os.remove(list_path)
            except Exception:
                pass

    def _run_cmd(self, cmd: List[str]) -> tuple[bool, str]:
        try:
            with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True,
            ) as proc:
                while True:
                    if self._cancelled:
                        proc.terminate()
                        return False, "Cancelled"
                    line = proc.stderr.readline()
                    if not line:
                        if proc.poll() is not None:
                            break
                    else:
                        self.logLine.emit(line.rstrip())
                code = proc.wait()
                return (code == 0), ("exit code " + str(code) if code else "")
        except Exception as e:
            return False, str(e)



