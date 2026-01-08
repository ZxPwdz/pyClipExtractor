from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass(slots=True)
class MediaInfo:
    width: int
    height: int
    fps_num: int
    fps_den: int
    duration: float
    codec: str
    pix_fmt: str
    bitrate: Optional[int] = None

    @property
    def fps(self) -> float:
        try:
            return self.fps_num / self.fps_den if self.fps_den else float(self.fps_num)
        except Exception:
            return 0.0

    def badge_text(self) -> str:
        fps_value = f"{self.fps:.2f}" if self.fps else "?"
        minutes = int(self.duration // 60) if self.duration else 0
        seconds = int(round(self.duration % 60)) if self.duration else 0
        dur_text = f"{minutes}m{seconds:02d}s"
        br_text = f" • {int(self.bitrate/1000)} kbps" if self.bitrate else ""
        return f"{self.width}×{self.height} • {fps_value} fps • {self.codec} • {dur_text}{br_text}"


@dataclass(slots=True)
class MediaFile:
    id: str
    path: str
    info: Optional[MediaInfo] = None


@dataclass(slots=True)
class Segment:
    id: str
    file_id: str
    start: float
    end: float
    order: int

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @staticmethod
    def new(file_id: str, start: float, end: float, order: int) -> "Segment":
        return Segment(id=str(uuid.uuid4()), file_id=file_id, start=start, end=end, order=order)


@dataclass(slots=True)
class ExportProfile:
    preset_name: str
    codec: str
    crf: Optional[int]
    preset: Optional[str]
    audio_bitrate: Optional[str]
    fps: Optional[float]
    width: Optional[int]
    height: Optional[int]
    letterbox: bool = False
    # Watermark settings
    watermark_enabled: bool = False
    watermark_path: Optional[str] = None
    watermark_scale_pct: Optional[int] = None  # percent of base width
    watermark_margin_left: int = 16
    watermark_margin_bottom: int = 16
    web_optimize: bool = False



