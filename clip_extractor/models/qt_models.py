from __future__ import annotations

from typing import List, Optional, Dict, Any
from PySide6 import QtCore

from .media import MediaFile, MediaInfo, Segment


class FileListModel(QtCore.QAbstractListModel):
    FileObjectRole = QtCore.Qt.UserRole + 1

    def __init__(self, files: Optional[List[MediaFile]] = None, parent=None) -> None:
        super().__init__(parent)
        self._files: List[MediaFile] = files or []

    # Basic model API
    def rowCount(self, parent=QtCore.QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._files)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> Any:  # type: ignore[override]
        if not index.isValid():
            return None
        f = self._files[index.row()]
        if role == QtCore.Qt.DisplayRole:
            if f.info:
                return f"{QtCore.QFileInfo(f.path).fileName()}\n{f.info.badge_text()}"
            return f"{QtCore.QFileInfo(f.path).fileName()}\n(Probing...)"
        if role == FileListModel.FileObjectRole:
            return f
        return None

    def add_file(self, media_file: MediaFile) -> int:
        self.beginInsertRows(QtCore.QModelIndex(), len(self._files), len(self._files))
        self._files.append(media_file)
        self.endInsertRows()
        return len(self._files) - 1

    def clear(self) -> None:
        if not self._files:
            return
        self.beginRemoveRows(QtCore.QModelIndex(), 0, len(self._files) - 1)
        self._files.clear()
        self.endRemoveRows()

    def update_info(self, file_id: str, info: MediaInfo) -> None:
        for row, f in enumerate(self._files):
            if f.id == file_id:
                f.info = info
                top_left = self.index(row)
                bottom_right = self.index(row)
                self.dataChanged.emit(top_left, bottom_right, [QtCore.Qt.DisplayRole])
                break

    def file_at(self, row: int) -> Optional[MediaFile]:
        if 0 <= row < len(self._files):
            return self._files[row]
        return None

    def files(self) -> List[MediaFile]:
        return list(self._files)

    def file_by_id(self, file_id: str) -> Optional[MediaFile]:
        for f in self._files:
            if f.id == file_id:
                return f
        return None


class SegmentTableModel(QtCore.QAbstractTableModel):
    ColumnHeaders = ["#", "Start (mm:ss)", "End (mm:ss)", "Duration", "Order"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._segments_by_file: Dict[str, List[Segment]] = {}
        self._current_file_id: Optional[str] = None

    def set_current_file(self, file_id: Optional[str]) -> None:
        if self._current_file_id == file_id:
            return
        self.beginResetModel()
        self._current_file_id = file_id
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        segs = self._segments_by_file.get(self._current_file_id or "", [])
        return len(segs)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:  # type: ignore[override]
        return len(self.ColumnHeaders)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):  # type: ignore[override]
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            return self.ColumnHeaders[section]
        return str(section + 1)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        segs = self._segments_by_file.get(self._current_file_id or "", [])
        seg = segs[index.row()]
        if role == QtCore.Qt.DisplayRole:
            col = index.column()
            if col == 0:
                return str(index.row() + 1)
            if col == 1:
                return self._format_mmss(seg.start)
            if col == 2:
                return self._format_mmss(seg.end)
            if col == 3:
                return self._format_mmss(seg.duration)
            if col == 4:
                return str(seg.order)
        return None

    @staticmethod
    def _format_mmss(seconds: float) -> str:
        total = int(round(seconds))
        m, s = divmod(total, 60)
        return f"{m}:{s:02d}"

    # Segment manipulation
    def add_segment(self, file_id: str, segment: Segment) -> int:
        segs = self._segments_by_file.setdefault(file_id, [])
        row = len(segs)
        if self._current_file_id == file_id:
            self.beginInsertRows(QtCore.QModelIndex(), row, row)
            segs.append(segment)
            self.endInsertRows()
        else:
            segs.append(segment)
        return row

    def remove_rows(self, rows: List[int]) -> None:
        file_id = self._current_file_id
        if not file_id:
            return
        segs = self._segments_by_file.get(file_id, [])
        if not segs:
            return
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(segs):
                self.beginRemoveRows(QtCore.QModelIndex(), row, row)
                segs.pop(row)
                self.endRemoveRows()

    def segments_for_file(self, file_id: str) -> List[Segment]:
        return list(self._segments_by_file.get(file_id, []))

    def all_segments_in_global_order(self) -> List[Segment]:
        # Flatten and sort by 'order'
        all_segs: List[Segment] = []
        for segs in self._segments_by_file.values():
            all_segs.extend(segs)
        return sorted(all_segs, key=lambda s: s.order)


