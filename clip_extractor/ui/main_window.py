from __future__ import annotations

import os
import uuid
from typing import Dict, Optional, List

from PySide6 import QtWidgets, QtCore, QtGui

from clip_extractor.models.media import MediaFile, Segment
from clip_extractor.models.qt_models import FileListModel, SegmentTableModel
from clip_extractor.ffmpeg.exporter import FfmpegExporter, ExportTask


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, ff_bins: Dict[str, str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Clip Extractor")
        self._ff_bins = ff_bins

        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._global_order_counter = 0

        self._build_ui()
        self._connect_actions()
        self._restore_theme()

    # --- UI ---
    def _build_ui(self) -> None:
        toolbar = QtWidgets.QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QtCore.QSize(20, 20))
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)

        # Use standard icons from the style
        self.actionLoad = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton), "Load Files", self)
        self.actionClear = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon), "Clear All", self)
        self.actionExport = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton), "Export", self)
        self.actionTheme = QtGui.QAction(self.style().standardIcon(QtWidgets.QStyle.SP_DesktopIcon), "Theme", self)

        toolbar.addAction(self.actionLoad)
        toolbar.addAction(self.actionClear)
        toolbar.addSeparator()
        toolbar.addAction(self.actionExport)
        toolbar.addSeparator()
        toolbar.addAction(self.actionTheme)

        # Main Tab Widget
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tab 1: Clip Extractor
        self.tab_extractor = QtWidgets.QWidget()
        self._build_clip_extractor_tab(self.tab_extractor)
        self.tabs.addTab(self.tab_extractor, "Clip Extractor")

        # Tab 2: Merge Videos
        self.tab_merge = QtWidgets.QWidget()
        self._build_merge_tab(self.tab_merge)
        self.tabs.addTab(self.tab_merge, "Merge Videos")

    def _build_clip_extractor_tab(self, parent_widget: QtWidgets.QWidget) -> None:
        layout = QtWidgets.QVBoxLayout(parent_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Central split
        splitter = QtWidgets.QSplitter()
        
        # Left: Files + Segments
        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(12)

        # Files section with label
        files_label = QtWidgets.QLabel("<b>Media Files</b>")
        left_layout.addWidget(files_label)

        self.filesView = QtWidgets.QListView()
        self.filesView.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.fileModel = FileListModel()
        self.filesView.setModel(self.fileModel)
        self.filesView.setMinimumWidth(240)
        self.filesView.setMaximumHeight(180)

        left_layout.addWidget(self.filesView)

        # Segments section with label
        segments_header = QtWidgets.QHBoxLayout()
        self.segments_label = QtWidgets.QLabel("<b>Time Ranges</b>")
        self.current_file_label = QtWidgets.QLabel("<i>No file selected</i>")
        self.current_file_label.setStyleSheet("color: #666;")
        segments_header.addWidget(self.segments_label)
        segments_header.addStretch(1)
        segments_header.addWidget(self.current_file_label)
        left_layout.addLayout(segments_header)

        seg_actions = QtWidgets.QHBoxLayout()
        seg_actions.setSpacing(6)
        self.btnAddRange = QtWidgets.QPushButton("+ Add Range")
        self.btnDuplicate = QtWidgets.QPushButton("Duplicate")
        self.btnDelete = QtWidgets.QPushButton("Delete Selected")
        self.btnClearRanges = QtWidgets.QPushButton("Clear Ranges")
        seg_actions.addWidget(self.btnAddRange)
        seg_actions.addWidget(self.btnDuplicate)
        seg_actions.addWidget(self.btnDelete)
        seg_actions.addWidget(self.btnClearRanges)
        seg_actions.addStretch(1)
        left_layout.addLayout(seg_actions)

        self.segmentModel = SegmentTableModel()
        self.segmentsView = QtWidgets.QTableView()
        self.segmentsView.setModel(self.segmentModel)
        self.segmentsView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.segmentsView.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.segmentsView.setAlternatingRowColors(True)
        header = self.segmentsView.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        left_layout.addWidget(self.segmentsView, 1)

        splitter.addWidget(left)

        # Right: Quick Range Builder
        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)

        # Quick range builder group box
        quick_group = QtWidgets.QGroupBox("Quick Range Builder")
        quick_group_layout = QtWidgets.QVBoxLayout(quick_group)
        quick_group_layout.setSpacing(8)

        # Add info label
        info_label = QtWidgets.QLabel("<i>Ranges will be added to the selected file in the Media Files list</i>")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        quick_group_layout.addWidget(info_label)

        self.quickRowsContainer = QtWidgets.QVBoxLayout()
        self.quickRowsContainer.setSpacing(6)
        quick_group_layout.addLayout(self.quickRowsContainer)
        self._add_quick_rows(3)

        row_buttons = QtWidgets.QHBoxLayout()
        row_buttons.setSpacing(6)
        self.btnAddThree = QtWidgets.QPushButton("Add 3 More Rows")
        self.btnClearRows = QtWidgets.QPushButton("Clear All Rows")
        row_buttons.addWidget(self.btnAddThree)
        row_buttons.addWidget(self.btnClearRows)
        row_buttons.addStretch(1)
        quick_group_layout.addLayout(row_buttons)

        right_layout.addWidget(quick_group)

        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        # Give the segments table generous initial width; user can adjust later
        splitter.setSizes([900, 480])

        # Bottom: Export and status
        bottom = QtWidgets.QFrame()
        bottom.setFrameShape(QtWidgets.QFrame.StyledPanel)
        bottom_main_layout = QtWidgets.QVBoxLayout(bottom)
        bottom_main_layout.setContentsMargins(12, 12, 12, 12)
        bottom_main_layout.setSpacing(10)

        # First row: Export Settings
        settings_layout = QtWidgets.QHBoxLayout()
        settings_layout.setSpacing(8)

        # Export settings group
        export_group = QtWidgets.QGroupBox("Export Settings")
        export_layout = QtWidgets.QHBoxLayout(export_group)
        export_layout.setSpacing(8)

        self.cmbPreset = QtWidgets.QComboBox()
        self.cmbPreset.addItems(["Source", "High", "Medium", "Social/Light"])
        self.cmbResolution = QtWidgets.QComboBox()
        self.cmbResolution.addItems(["Auto (Recommended)", "Source", "4320p", "2160p", "1440p", "1080p", "720p", "480p"])
        self.cmbFps = QtWidgets.QComboBox()
        self.cmbFps.addItems(["Auto (Recommended)", "23.976", "24", "25", "29.97", "30", "50", "59.94", "60"])
        self.chkLetterbox = QtWidgets.QCheckBox("Letterbox to preserve aspect")
        self.chkWebOptimize = QtWidgets.QCheckBox("Web Optimize")

        export_layout.addWidget(QtWidgets.QLabel("Preset:"))
        export_layout.addWidget(self.cmbPreset)
        export_layout.addWidget(QtWidgets.QLabel("Resolution:"))
        export_layout.addWidget(self.cmbResolution)
        export_layout.addWidget(QtWidgets.QLabel("FPS:"))
        export_layout.addWidget(self.cmbFps)
        export_layout.addWidget(self.chkLetterbox)
        export_layout.addWidget(self.chkWebOptimize)
        export_layout.addStretch(1)

        settings_layout.addWidget(export_group)
        bottom_main_layout.addLayout(settings_layout)

        # Second row: Watermark controls
        wm_layout = QtWidgets.QHBoxLayout()
        wm_layout.setSpacing(8)

        self.grpWatermark = QtWidgets.QGroupBox("Watermark")
        wm_inner_layout = QtWidgets.QHBoxLayout(self.grpWatermark)
        wm_inner_layout.setSpacing(8)

        self.chkWatermark = QtWidgets.QCheckBox("Enable")
        self.txtWatermarkPath = QtWidgets.QLineEdit()
        self.txtWatermarkPath.setPlaceholderText("Select image...")
        self.btnBrowseWatermark = QtWidgets.QPushButton("Browse")
        self.spinScalePct = QtWidgets.QSpinBox()
        self.spinScalePct.setRange(5, 100)
        self.spinScalePct.setValue(20)
        self.spinScalePct.setSuffix("%")
        self.spinMarginL = QtWidgets.QSpinBox()
        self.spinMarginL.setRange(0, 200)
        self.spinMarginL.setValue(16)
        self.spinMarginL.setSuffix("px")
        self.spinMarginB = QtWidgets.QSpinBox()
        self.spinMarginB.setRange(0, 200)
        self.spinMarginB.setValue(16)
        self.spinMarginB.setSuffix("px")
        self.btnPreviewWatermark = QtWidgets.QPushButton("Preview")

        wm_inner_layout.addWidget(self.chkWatermark)
        wm_inner_layout.addWidget(QtWidgets.QLabel("File:"))
        wm_inner_layout.addWidget(self.txtWatermarkPath, 1)
        wm_inner_layout.addWidget(self.btnBrowseWatermark)
        wm_inner_layout.addWidget(QtWidgets.QLabel("Scale:"))
        wm_inner_layout.addWidget(self.spinScalePct)
        wm_inner_layout.addWidget(QtWidgets.QLabel("Left:"))
        wm_inner_layout.addWidget(self.spinMarginL)
        wm_inner_layout.addWidget(QtWidgets.QLabel("Bottom:"))
        wm_inner_layout.addWidget(self.spinMarginB)
        wm_inner_layout.addWidget(self.btnPreviewWatermark)

        wm_layout.addWidget(self.grpWatermark)
        bottom_main_layout.addLayout(wm_layout)

        # Third row: Export progress and controls
        progress_layout = QtWidgets.QHBoxLayout()
        progress_layout.setSpacing(8)

        self.lblStage = QtWidgets.QLabel("Idle")
        self.lblStage.setMinimumWidth(100)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(True)
        self.btnCancel = QtWidgets.QPushButton("Cancel")
        self.btnCancel.setEnabled(False)
        self.btnExport = QtWidgets.QPushButton("Export Clips")
        self.btnExport.setEnabled(False)
        self.btnExport.setMinimumHeight(32)
        self.btnExport.setMinimumWidth(120)

        progress_layout.addWidget(self.lblStage)
        progress_layout.addWidget(self.progress, 1)
        progress_layout.addWidget(self.btnCancel)
        progress_layout.addWidget(self.btnExport)

        bottom_main_layout.addLayout(progress_layout)

        layout.addWidget(splitter, 1)
        layout.addWidget(bottom, 0)

    def _build_merge_tab(self, parent_widget: QtWidgets.QWidget) -> None:
        layout = QtWidgets.QVBoxLayout(parent_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Top: File List and Controls
        top_layout = QtWidgets.QHBoxLayout()
        
        # File List
        self.mergeFilesView = QtWidgets.QListView()
        self.mergeFilesView.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.mergeFileModel = FileListModel()
        self.mergeFilesView.setModel(self.mergeFileModel)
        top_layout.addWidget(self.mergeFilesView, 1)

        # Controls
        controls_layout = QtWidgets.QVBoxLayout()
        self.btnMergeAdd = QtWidgets.QPushButton("Add Files")
        self.btnMergeRemove = QtWidgets.QPushButton("Remove")
        self.btnMergeUp = QtWidgets.QPushButton("Move Up")
        self.btnMergeDown = QtWidgets.QPushButton("Move Down")
        self.btnMergeClear = QtWidgets.QPushButton("Clear All")
        
        controls_layout.addWidget(self.btnMergeAdd)
        controls_layout.addWidget(self.btnMergeRemove)
        controls_layout.addSpacing(12)
        controls_layout.addWidget(self.btnMergeUp)
        controls_layout.addWidget(self.btnMergeDown)
        controls_layout.addSpacing(12)
        controls_layout.addWidget(self.btnMergeClear)
        controls_layout.addStretch(1)
        
        top_layout.addLayout(controls_layout)
        layout.addLayout(top_layout, 1)

        # Bottom: Export Settings
        bottom = QtWidgets.QGroupBox("Merge Export Settings")
        bottom_layout = QtWidgets.QHBoxLayout(bottom)
        
        self.cmbMergeRes = QtWidgets.QComboBox()
        self.cmbMergeRes.addItems(["Auto (Recommended)", "Source", "4320p", "2160p", "1440p", "1080p", "720p", "480p"])
        
        self.chkMergeWebOptimize = QtWidgets.QCheckBox("Web Optimize")
        
        self.btnMergeExport = QtWidgets.QPushButton("Merge & Export")
        self.btnMergeExport.setEnabled(False)
        self.btnMergeExport.setMinimumHeight(32)
        self.btnMergeExport.setMinimumWidth(120)

        bottom_layout.addWidget(QtWidgets.QLabel("Resolution:"))
        bottom_layout.addWidget(self.cmbMergeRes)
        bottom_layout.addWidget(self.chkMergeWebOptimize)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self.btnMergeExport)
        
        layout.addWidget(bottom)

        # Progress for Merge
        self.mergeProgress = QtWidgets.QProgressBar()
        self.mergeProgress.setRange(0, 100)
        self.mergeProgress.setTextVisible(True)
        self.lblMergeStage = QtWidgets.QLabel("Idle")
        
        prog_layout = QtWidgets.QHBoxLayout()
        prog_layout.addWidget(self.lblMergeStage)
        prog_layout.addWidget(self.mergeProgress, 1)
        
        layout.addLayout(prog_layout)

        # Shortcuts
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+O"), self, activated=self._on_load_files)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self._on_delete_selected_segments)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+E"), self, activated=self._on_export)
        # Minimal log console
        self._log_dock = QtWidgets.QDockWidget("Log")
        self._log_edit = QtWidgets.QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_dock.setWidget(self._log_edit)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self._log_dock)

    def _add_quick_rows(self, count: int) -> None:
        for _ in range(count):
            row = self._make_quick_row()
            self.quickRowsContainer.addLayout(row)

    def _make_quick_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(4)

        m_start = QtWidgets.QSpinBox()
        m_start.setRange(0, 24 * 60)
        m_start.setSuffix(" m")
        m_start.setAlignment(QtCore.Qt.AlignRight)

        s_start = QtWidgets.QSpinBox()
        s_start.setRange(0, 59)
        s_start.setSuffix(" s")
        s_start.setAlignment(QtCore.Qt.AlignRight)

        m_end = QtWidgets.QSpinBox()
        m_end.setRange(0, 24 * 60)
        m_end.setSuffix(" m")
        m_end.setAlignment(QtCore.Qt.AlignRight)

        s_end = QtWidgets.QSpinBox()
        s_end.setRange(0, 59)
        s_end.setSuffix(" s")
        s_end.setAlignment(QtCore.Qt.AlignRight)

        btn_add = QtWidgets.QPushButton("Add")
        btn_add.setMinimumWidth(60)
        btn_clear = QtWidgets.QPushButton("Clear")
        btn_clear.setMinimumWidth(60)

        def on_add_clicked() -> None:
            self._quick_add_segment(m_start.value(), s_start.value(), m_end.value(), s_end.value())

        def on_clear_clicked() -> None:
            m_start.setValue(0)
            s_start.setValue(0)
            m_end.setValue(0)
            s_end.setValue(0)

        btn_add.clicked.connect(on_add_clicked)
        btn_clear.clicked.connect(on_clear_clicked)

        for w in [m_start, s_start, m_end, s_end]:
            w.setMaximumWidth(80)

        row.addWidget(QtWidgets.QLabel("Start:"))
        row.addWidget(m_start)
        row.addWidget(s_start)
        row.addSpacing(8)
        row.addWidget(QtWidgets.QLabel("End:"))
        row.addWidget(m_end)
        row.addWidget(s_end)
        row.addSpacing(8)
        row.addWidget(btn_add)
        row.addWidget(btn_clear)
        row.addStretch(1)
        return row

    # --- Actions ---
    def _connect_actions(self) -> None:
        self.actionLoad.triggered.connect(self._on_load_files)
        self.actionClear.triggered.connect(self._on_clear_all)
        self.actionExport.triggered.connect(self._on_export)
        self.actionTheme.triggered.connect(self._toggle_theme)
        self.filesView.selectionModel().selectionChanged.connect(self._on_file_selected)
        self.btnAddThree.clicked.connect(lambda: self._add_quick_rows(3))
        self.btnClearRows.clicked.connect(self._on_clear_rows)
        self.btnAddRange.clicked.connect(self._on_add_range_dialog)
        self.btnDelete.clicked.connect(self._on_delete_selected_segments)
        self.btnClearRanges.clicked.connect(self._on_clear_ranges_for_file)
        self.btnCancel.clicked.connect(self._on_cancel_export)
        self.btnBrowseWatermark.clicked.connect(self._on_browse_watermark)
        self.btnPreviewWatermark.clicked.connect(self._on_preview_watermark)

        # Merge Actions
        self.btnMergeAdd.clicked.connect(self._on_merge_add_files)
        self.btnMergeRemove.clicked.connect(self._on_merge_remove_file)
        self.btnMergeUp.clicked.connect(self._on_merge_move_up)
        self.btnMergeDown.clicked.connect(self._on_merge_move_down)
        self.btnMergeClear.clicked.connect(self._on_merge_clear)
        self.btnMergeExport.clicked.connect(self._on_merge_export)

    def _on_merge_add_files(self) -> None:
        last_dir = QtCore.QSettings().value("last_dir", os.path.expanduser("~"))
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Add Videos to Merge", last_dir, "Videos (*.mp4 *.mov)")
        if not files:
            return
        QtCore.QSettings().setValue("last_dir", os.path.dirname(files[0]))
        for path in files:
            mf = MediaFile(id=str(uuid.uuid4()), path=path, info=None)
            self.mergeFileModel.add_file(mf)
            # Probe asynchronously
            self._probe_file_async(mf, model=self.mergeFileModel)
        self.btnMergeExport.setEnabled(self.mergeFileModel.rowCount() > 0)

    def _on_merge_remove_file(self) -> None:
        idxs = self.mergeFilesView.selectionModel().selectedIndexes()
        if idxs:
            self.mergeFileModel.remove_file(idxs[0].row())
        self.btnMergeExport.setEnabled(self.mergeFileModel.rowCount() > 0)

    def _on_merge_move_up(self) -> None:
        idxs = self.mergeFilesView.selectionModel().selectedIndexes()
        if not idxs: return
        row = idxs[0].row()
        if row > 0:
            self.mergeFileModel.move_row(row, row - 1)
            self.mergeFilesView.setCurrentIndex(self.mergeFileModel.index(row - 1))

    def _on_merge_move_down(self) -> None:
        idxs = self.mergeFilesView.selectionModel().selectedIndexes()
        if not idxs: return
        row = idxs[0].row()
        if row < self.mergeFileModel.rowCount() - 1:
            self.mergeFileModel.move_row(row, row + 1)
            self.mergeFilesView.setCurrentIndex(self.mergeFileModel.index(row + 1))

    def _on_merge_clear(self) -> None:
        self.mergeFileModel.clear()
        self.btnMergeExport.setEnabled(False)

    def _on_merge_export(self) -> None:
        files = self.mergeFileModel.files()
        if not files:
            return
        
        default_name = QtCore.QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
        out_name = f"merged_{default_name}.mp4"
        dest, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Merged Video", out_name, "MP4 (*.mp4)")
        if not dest:
            return

        # Create segments (full duration for each file)
        segments = []
        for i, f in enumerate(files):
            duration = f.info.duration if f.info else 0
            # If duration is unknown, we might have issues. For now assume probe finished.
            seg = Segment.new(f.id, 0.0, duration, i)
            segments.append(seg)

        # Resolution
        res_map = {
            "4320p": (7680, 4320),
            "2160p": (3840, 2160),
            "1440p": (2560, 1440),
            "1080p": (1920, 1080),
            "720p": (1280, 720),
            "480p": (854, 480),
        }
        res_text = self.cmbMergeRes.currentText()
        width = height = None
        if res_text in res_map:
            width, height = res_map[res_text]

        from clip_extractor.models.media import ExportProfile
        profile = ExportProfile(
            preset_name="Merge",
            codec="h264",
            crf=23,
            preset="medium",
            audio_bitrate="192k",
            fps=None, # Auto
            width=width,
            height=height,
            letterbox=True, # Always letterbox for merge to ensure uniform size
            web_optimize=self.chkMergeWebOptimize.isChecked()
        )

        lookup = {f.id: f.path for f in files}
        task = ExportTask(
            ffmpeg=self._ff_bins["ffmpeg"],
            segments=segments,
            file_lookup=lookup,
            profile=profile,
            output_path=dest,
        )

        self._exporter = FfmpegExporter(task)
        self._exporter.progressChanged.connect(lambda v, s: (self.mergeProgress.setValue(v), self.lblMergeStage.setText(s)))
        self._exporter.logLine.connect(self._append_log)
        self._exporter.finished.connect(self._on_merge_finished)
        
        self.mergeProgress.setValue(0)
        self.lblMergeStage.setText("Starting...")
        self.btnMergeExport.setEnabled(False)
        # Disable other tabs/controls if needed, or just let it run
        self._thread_pool.start(self._exporter)

    def _on_merge_finished(self, ok: bool, message: str) -> None:
        self.btnMergeExport.setEnabled(True)
        self.lblMergeStage.setText("Done" if ok else "Failed")
        if ok:
            QtWidgets.QMessageBox.information(self, "Merge complete", f"Saved to:\n{message}")
        else:
            QtWidgets.QMessageBox.warning(self, "Merge failed", message)

    def _on_load_files(self) -> None:
        last_dir = QtCore.QSettings().value("last_dir", os.path.expanduser("~"))
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Load Video Files", last_dir, "Videos (*.mp4 *.mov)")
        if not files:
            return
        QtCore.QSettings().setValue("last_dir", os.path.dirname(files[0]))
        for path in files:
            mf = MediaFile(id=str(uuid.uuid4()), path=path, info=None)
            row = self.fileModel.add_file(mf)
            if self.fileModel.rowCount() == 1:
                self.filesView.setCurrentIndex(self.fileModel.index(row))
            # Probe asynchronously
            self._probe_file_async(mf, self.fileModel)

    def _probe_file_async(self, media_file: MediaFile, model: FileListModel) -> None:
        from clip_extractor.ffmpeg.utils import probe_media_info

        class _ProbeWorker(QtCore.QObject):
            done = QtCore.Signal(object)

            def __init__(self, path: str, ffprobe: str):
                super().__init__()
                self._path = path
                self._ffprobe = ffprobe

        worker = _ProbeWorker(media_file.path, self._ff_bins["ffprobe"])
        # Keep a strong ref until finished to avoid GC while QRunnable runs
        if not hasattr(self, "_active_probe_workers"):
            self._active_probe_workers = []  # type: ignore[attr-defined]
        self._active_probe_workers.append(worker)  # type: ignore[attr-defined]

        class _ProbeRunnable(QtCore.QRunnable):
            def __init__(self, w: _ProbeWorker):
                super().__init__()
                self._w = w

            def run(self):
                info = probe_media_info(self._w._ffprobe, self._w._path)
                self._w.done.emit(info)

        def on_done(info):
            if info is None:
                QtWidgets.QMessageBox.warning(self, "Probe failed", f"Could not read media info for:\n{media_file.path}")
                return
            model.update_info(media_file.id, info)

        def on_done_and_cleanup(info):
            try:
                on_done(info)
            finally:
                try:
                    self._active_probe_workers.remove(worker)  # type: ignore[attr-defined]
                except Exception:
                    pass

        worker.done.connect(on_done_and_cleanup)
        self._thread_pool.start(_ProbeRunnable(worker))

    def _on_clear_all(self) -> None:
        self.fileModel.clear()
        self.segmentModel.set_current_file(None)
        self.btnExport.setEnabled(False)

    def _on_file_selected(self) -> None:
        idxs = self.filesView.selectionModel().selectedIndexes()
        file = self.fileModel.file_at(idxs[0].row()) if idxs else None
        self.segmentModel.set_current_file(file.id if file else None)

        # Update the current file label
        if file:
            filename = QtCore.QFileInfo(file.path).fileName()
            self.current_file_label.setText(f"<i>Editing: {filename}</i>")
            self.current_file_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        else:
            self.current_file_label.setText("<i>No file selected</i>")
            self.current_file_label.setStyleSheet("color: #666;")

    def _quick_add_segment(self, m_start: int, s_start: int, m_end: int, s_end: int) -> None:
        idxs = self.filesView.selectionModel().selectedIndexes()
        if not idxs:
            QtWidgets.QMessageBox.information(self, "No file selected", "Select a file to add ranges.")
            return
        file = self.fileModel.file_at(idxs[0].row())
        if not file or not file.info:
            QtWidgets.QMessageBox.information(self, "Not ready", "File info not ready yet.")
            return
        start = m_start * 60 + s_start
        end = m_end * 60 + s_end
        if end <= start or start < 0 or end > file.info.duration:
            QtWidgets.QMessageBox.warning(self, "Invalid range", "Check start/end and ensure within duration.")
            return
        self._global_order_counter += 1
        seg = Segment.new(file.id, float(start), float(end), self._global_order_counter)
        self.segmentModel.add_segment(file.id, seg)
        self.btnExport.setEnabled(True)

    def _on_add_range_dialog(self) -> None:
        # Simple dialog allowing one range entry
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Add Range")
        layout = QtWidgets.QFormLayout(dlg)
        m_start = QtWidgets.QSpinBox(); m_start.setRange(0, 24 * 60)
        s_start = QtWidgets.QSpinBox(); s_start.setRange(0, 59)
        m_end = QtWidgets.QSpinBox(); m_end.setRange(0, 24 * 60)
        s_end = QtWidgets.QSpinBox(); s_end.setRange(0, 59)
        layout.addRow("Start m:", m_start)
        layout.addRow("Start s:", s_start)
        layout.addRow("End m:", m_end)
        layout.addRow("End s:", s_end)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addRow(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self._quick_add_segment(m_start.value(), s_start.value(), m_end.value(), s_end.value())

    def _on_delete_selected_segments(self) -> None:
        rows = sorted({i.row() for i in self.segmentsView.selectionModel().selectedIndexes()})
        if rows:
            self.segmentModel.remove_rows(rows)

    def _on_clear_ranges_for_file(self) -> None:
        rows = list(range(self.segmentModel.rowCount()))
        self._on_delete_selected_segments() if not rows else self.segmentModel.remove_rows(rows)
        if self.segmentModel.rowCount() == 0:
            self.btnExport.setEnabled(False)

    def _on_clear_rows(self) -> None:
        # Clear quick entry rows but keep segments
        for i in range(self.quickRowsContainer.count()):
            item = self.quickRowsContainer.itemAt(i)
            if not item:
                continue
            layout = item.layout()
            if not layout:
                continue
            for j in range(layout.count()):
                w = layout.itemAt(j).widget()
                if isinstance(w, QtWidgets.QSpinBox):
                    w.setValue(0)

    def _on_export(self) -> None:
        # Gather segments in global order
        segments = self.segmentModel.all_segments_in_global_order()
        if not segments:
            return
        # Choose destination
        default_name = QtCore.QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
        out_name = f"export_{default_name}.mp4"
        dest, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export To", out_name, "MP4 (*.mp4)")
        if not dest:
            return
        # Build profile from UI (basic mapping; recommendations later)
        preset = self.cmbPreset.currentText()
        codec = "h264"
        crf, preset_speed, ab = 23, "medium", "192k"
        if preset == "High":
            crf, preset_speed, ab = 18, "slow", "320k"
        elif preset == "Medium":
            crf, preset_speed, ab = 22, "medium", "192k"
        elif preset == "Social/Light":
            crf, preset_speed, ab = 27, "faster", "128k"
        elif preset == "Source":
            crf, preset_speed, ab = 20, "medium", "192k"

        # Resolution
        res_map = {
            "4320p": (7680, 4320),
            "2160p": (3840, 2160),
            "1440p": (2560, 1440),
            "1080p": (1920, 1080),
            "720p": (1280, 720),
            "480p": (854, 480),
        }
        res_text = self.cmbResolution.currentText()
        width = height = None
        if res_text in res_map:
            width, height = res_map[res_text]

        # FPS
        fps = None
        fps_text = self.cmbFps.currentText()
        if fps_text not in ("Auto (Recommended)",):
            try:
                fps = float(fps_text)
            except Exception:
                fps = None

        from clip_extractor.models.media import ExportProfile
        profile = ExportProfile(
            preset_name=preset,
            codec=codec,
            crf=crf,
            preset=preset_speed,
            audio_bitrate=ab,
            fps=fps,
            width=width,
            height=height,
            letterbox=self.chkLetterbox.isChecked(),
            watermark_enabled=self.chkWatermark.isChecked(),
            watermark_path=self.txtWatermarkPath.text().strip() or None,
            watermark_scale_pct=self.spinScalePct.value(),
            watermark_margin_left=self.spinMarginL.value(),
            watermark_margin_bottom=self.spinMarginB.value(),
            web_optimize=self.chkWebOptimize.isChecked(),
        )

        # Build file lookup
        lookup = {f.id: f.path for f in self.fileModel.files()}
        task = ExportTask(
            ffmpeg=self._ff_bins["ffmpeg"],
            segments=segments,
            file_lookup=lookup,
            profile=profile,
            output_path=dest,
        )
        self._exporter = FfmpegExporter(task)
        self._exporter.progressChanged.connect(self._on_export_progress)
        self._exporter.logLine.connect(self._append_log)
        self._exporter.finished.connect(self._on_export_finished)
        self.progress.setValue(0)
        self.lblStage.setText("Starting...")
        self.btnCancel.setEnabled(True)
        self.btnExport.setEnabled(False)
        self._thread_pool.start(self._exporter)

    def _on_export_progress(self, value: int, stage: str) -> None:
        self.progress.setValue(value)
        self.lblStage.setText(stage)

    def _on_export_finished(self, ok: bool, message: str) -> None:
        self.btnCancel.setEnabled(False)
        self.btnExport.setEnabled(True)
        self.lblStage.setText("Done" if ok else "Failed")
        if ok:
            QtWidgets.QMessageBox.information(self, "Export complete", f"Saved to:\n{message}")
        else:
            QtWidgets.QMessageBox.warning(self, "Export failed", message)

    def _on_cancel_export(self) -> None:
        exp = getattr(self, "_exporter", None)
        if exp:
            exp.cancel()

    def _append_log(self, line: str) -> None:
        # Created in _build_ui
        if hasattr(self, "_log_edit"):
            self._log_edit.appendPlainText(line)

    def _on_browse_watermark(self) -> None:
        start = QtCore.QSettings().value("last_wm_dir", QtCore.QDir.homePath())
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Watermark Image", start, "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            QtCore.QSettings().setValue("last_wm_dir", QtCore.QFileInfo(path).absolutePath())
            self.txtWatermarkPath.setText(path)

    def _on_preview_watermark(self) -> None:
        """Preview watermark using the first loaded file."""
        if not self.chkWatermark.isChecked():
            QtWidgets.QMessageBox.information(self, "Preview", "Enable the watermark first.")
            return
        if not self.fileModel.files():
            QtWidgets.QMessageBox.information(self, "Preview", "Load a file to preview.")
            return
        wm_path = self.txtWatermarkPath.text().strip()
        if not wm_path or not QtCore.QFileInfo(wm_path).exists():
            QtWidgets.QMessageBox.warning(self, "Preview", "Select a valid watermark image.")
            return
        mf = self.fileModel.files()[0]
        if not mf.info:
            QtWidgets.QMessageBox.information(self, "Preview", "File info not ready.")
            return
        
        # Try with local watermark file first
        try:
            # Use the local watermark.png in the same folder as the script
            import os
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            local_wm = os.path.join(script_dir, "watermark.png")
            
            if os.path.exists(local_wm):
                self._log_edit.appendPlainText(f"Using local watermark: {local_wm}")
                wm_path = local_wm
            else:
                self._log_edit.appendPlainText(f"Local watermark not found, using: {wm_path}")
        except Exception as e:
            self._log_edit.appendPlainText(f"Error checking local watermark: {e}")
            
        # Create a short preview clip with watermark using ffmpeg, then play it
        try:
            import tempfile
            import os
            import subprocess
            
            # Parameters
            scale_pct = self.spinScalePct.value()
            margin_l = self.spinMarginL.value()
            margin_b = self.spinMarginB.value()
            
            ffmpeg = self._ff_bins.get("ffmpeg", "ffmpeg")
            ffplay = self._ff_bins.get("ffplay", "ffplay")
            
            # Create temp file
            fd, temp_path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
            
            self._log_edit.appendPlainText(f"Creating preview clip at: {temp_path}")
            
            # Build ffmpeg command to create short preview with watermark
            filter_complex = f"[1:v]scale=iw*{scale_pct}/100:-1[wm];[0:v][wm]overlay=x={margin_l}:y=H-h-{margin_b}[v]"
            
            # Take 5 seconds from the middle of the video
            duration = mf.info.duration if mf.info and mf.info.duration else 60
            middle = duration / 2
            start_time = max(0, middle - 2.5)  # 2.5 seconds before middle
            
            # Create short preview with watermark
            ffmpeg_cmd = [
                ffmpeg,
                "-y",  # Overwrite output file
                "-ss", str(start_time),  # Start time
                "-t", "5",  # Duration: 5 seconds
                "-i", mf.path,  # Video input
                "-i", wm_path,  # Watermark input
                "-filter_complex", filter_complex,
                "-map", "[v]",  # Use output from filter
                "-map", "0:a?",  # Include audio if available
                "-c:v", "libx264",  # Use H.264 codec
                "-preset", "ultrafast",  # Fast encoding
                "-crf", "23",  # Reasonable quality
                "-pix_fmt", "yuv420p",  # Compatible pixel format
                "-c:a", "aac",  # Audio codec
                "-b:a", "128k",  # Audio bitrate
                temp_path  # Output file
            ]
            
            self._log_edit.appendPlainText(f"Creating preview with command: {' '.join(ffmpeg_cmd)}")
            
            # Run ffmpeg to create preview
            try:
                result = subprocess.run(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode != 0:
                    self._log_edit.appendPlainText(f"Error creating preview: {result.stderr}")
                    QtWidgets.QMessageBox.warning(self, "Preview", f"Failed to create preview clip")
                    return
                    
                # Now play the preview with ffplay
                self._log_edit.appendPlainText(f"Playing preview: {temp_path}")
                
                # Create QProcess for ffplay
                process = QtCore.QProcess()
                
                # Connect signals
                process.readyReadStandardError.connect(
                    lambda: self._log_edit.appendPlainText(f"PLAY: {process.readAllStandardError().data().decode('utf-8', 'ignore').strip()}")
                )
                
                # Clean up temp file when done
                def cleanup_temp():
                    self._log_edit.appendPlainText(f"Preview finished, cleaning up")
                    try:
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                            self._log_edit.appendPlainText(f"Removed temp file: {temp_path}")
                    except Exception as e:
                        self._log_edit.appendPlainText(f"Error cleaning up: {e}")
                
                process.finished.connect(cleanup_temp)
                
                # Start ffplay with the temp file - with standard controls
                process.start(ffplay, [
                    "-window_title", "Watermark Preview", 
                    "-x", "800",  # Initial width
                    "-y", "450",  # Initial height (16:9 aspect ratio)
                    # No -noborder to allow normal window controls
                    # No -exitonkeydown/-exitonmousedown to allow normal interaction
                    # No -autoexit to allow full control over playback
                    # Standard ffplay controls will be available:
                    # - Space: Play/Pause
                    # - f: Toggle fullscreen
                    # - ESC: Exit fullscreen
                    # - q: Quit
                    # - Left/Right arrows: Seek
                    temp_path
                ])
                
                # Check if started
                if not process.waitForStarted(1000):
                    self._log_edit.appendPlainText(f"Failed to start ffplay")
                    QtWidgets.QMessageBox.warning(self, "Preview", "Failed to start preview player")
                    # Clean up if ffplay fails
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                else:
                    self._log_edit.appendPlainText("Preview playing")
                    
                    # Store reference to keep process alive
                    if not hasattr(self, "_preview_processes"):
                        self._preview_processes = []
                    self._preview_processes.append(process)
                
            except Exception as e:
                self._log_edit.appendPlainText(f"Error during preview: {e}")
                QtWidgets.QMessageBox.warning(self, "Preview", f"Error: {e}")
                # Clean up if there's an error
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass
            
        except Exception as e:
            self._log_edit.appendPlainText(f"Preview setup error: {e}")
            QtWidgets.QMessageBox.warning(self, "Preview", f"Failed to set up preview:\n{e}")

    # --- Theme ---
    def _toggle_theme(self) -> None:
        settings = QtCore.QSettings()
        theme = settings.value("theme", "light")
        new_theme = "dark" if theme == "light" else "light"
        settings.setValue("theme", new_theme)
        self._apply_theme(new_theme)

    def _restore_theme(self) -> None:
        self._apply_theme(QtCore.QSettings().value("theme", "light"))

    def _apply_theme(self, theme: str) -> None:
        if theme == "dark":
            self._set_dark_palette()
        else:
            self._set_light_palette()

    def _set_dark_palette(self) -> None:
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(37, 37, 38))
        palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(30, 30, 30))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(45, 45, 48))
        palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor(45, 45, 48))
        palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(38, 79, 120))
        palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.white)
        self.setPalette(palette)

    def _set_light_palette(self) -> None:
        self.setPalette(self.style().standardPalette())


