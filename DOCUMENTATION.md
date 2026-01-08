# Clip Extractor - Technical Documentation

## Overview

Clip Extractor is a modern desktop GUI application built with Python and PySide6 for extracting multiple video segments and merging them into a single output file. The application uses FFmpeg for all video processing operations and provides an intuitive interface for managing video files, defining segments, and exporting merged content.

## Architecture

### Core Components

```
clip_extractor/
├── __init__.py                 # Package initialization
├── models/
│   ├── media.py               # Data models (MediaFile, Segment, ExportProfile)
│   └── qt_models.py           # Qt model classes for UI data binding
├── ffmpeg/
│   ├── utils.py               # FFprobe utilities for media analysis
│   └── exporter.py            # FFmpeg export pipeline with async processing
└── ui/
    └── main_window.py         # Main application window and UI logic
```

### Entry Point
- `main.py` - Application entry point with FFmpeg binary detection and high-DPI setup

## Data Models

### MediaFile
```python
@dataclass(slots=True)
class MediaFile:
    id: str                     # Unique identifier (UUID)
    path: str                   # File system path
    info: Optional[MediaInfo]   # Media metadata (probed asynchronously)
```

### MediaInfo
```python
@dataclass(slots=True)
class MediaInfo:
    width: int                  # Video width in pixels
    height: int                 # Video height in pixels
    fps_num: int                # Frame rate numerator
    fps_den: int                # Frame rate denominator
    duration: float             # Duration in seconds
    codec: str                  # Video codec name
    pix_fmt: str                # Pixel format
    bitrate: Optional[int]      # Bitrate in bits per second
```

**Key Methods:**
- `fps` property: Calculates actual FPS from numerator/denominator
- `badge_text()`: Formats media info for UI display (e.g., "1920×1080 • 29.97 fps • H.264 • 6m12s")

### Segment
```python
@dataclass(slots=True)
class Segment:
    id: str                     # Unique identifier (UUID)
    file_id: str                # Reference to MediaFile.id
    start: float                # Start time in seconds
    end: float                  # End time in seconds
    order: int                  # Global merge order
```

**Key Methods:**
- `duration` property: Calculates segment duration (end - start)
- `new()`: Static factory method for creating new segments with auto-generated UUIDs

### ExportProfile
```python
@dataclass(slots=True)
class ExportProfile:
    preset_name: str            # Human-readable preset name
    codec: str                  # Video codec (h264, h265)
    crf: Optional[int]          # Constant Rate Factor for quality
    preset: Optional[str]       # FFmpeg preset (slow, medium, fast)
    audio_bitrate: Optional[str] # Audio bitrate (e.g., "192k")
    fps: Optional[float]        # Target frame rate
    width: Optional[int]        # Target width
    height: Optional[int]       # Target height
    letterbox: bool             # Whether to letterbox for aspect preservation
```

## Qt Models (MV Pattern)

### FileListModel
Extends `QAbstractListModel` to provide data for the file list view.

**Key Methods:**
- `add_file()`: Adds a new MediaFile to the model
- `update_info()`: Updates MediaInfo for an existing file (called after async probe)
- `file_at()`: Retrieves MediaFile by row index
- `files()`: Returns all loaded files

**Data Roles:**
- `Qt.DisplayRole`: Returns formatted filename and media info badge
- `FileObjectRole`: Returns the actual MediaFile object

### SegmentTableModel
Extends `QAbstractTableModel` to manage segments for the currently selected file.

**Columns:**
1. "#" - Row number
2. "Start (mm:ss)" - Start time formatted as minutes:seconds
3. "End (mm:ss)" - End time formatted as minutes:seconds
4. "Duration" - Calculated duration
5. "Order" - Global merge order

**Key Methods:**
- `set_current_file()`: Switches context to segments for a specific file
- `add_segment()`: Adds a new segment to the current file
- `remove_rows()`: Removes selected segments
- `all_segments_in_global_order()`: Returns all segments across all files, sorted by order

## FFmpeg Integration

### Media Probing (utils.py)

The `probe_media_info()` function uses FFprobe to extract metadata:

```python
def probe_media_info(ffprobe_path: str, media_path: str) -> Optional[MediaInfo]:
    cmd = [
        ffprobe_path,
        "-v", "error",
        "-show_streams",
        "-select_streams", "v:0",  # First video stream only
        "-show_format",
        "-of", "json",
        media_path,
    ]
```

**Process:**
1. Executes FFprobe with JSON output
2. Parses JSON response to extract video stream and format information
3. Handles frame rate parsing (supports both "30/1" and "30" formats)
4. Returns structured MediaInfo object or None on failure

### Export Pipeline (exporter.py)

The `FfmpegExporter` class implements the complete export workflow:

#### ExportTask
```python
@dataclass(slots=True)
class ExportTask:
    ffmpeg: str                 # Path to ffmpeg binary
    segments: List[Segment]     # Segments to export in order
    file_lookup: Dict[str, str] # file_id -> file_path mapping
    profile: ExportProfile      # Export settings
    output_path: str            # Destination file path
```

#### Export Process

1. **Segment Cutting**: Each segment is cut individually with uniform encoding:
   ```bash
   ffmpeg -ss <start> -to <end> -i "<src>" -vf "<scalefilter>" -r <fps> \
          -c:v libx264 -preset <preset> -crf <crf> -pix_fmt yuv420p \
          -c:a aac -b:a <abitrate> "<tempN>.mp4"
   ```

2. **Scaling Filter**: Handles resolution changes and letterboxing:
   ```python
   def _build_scale_filter(self) -> Optional[str]:
       if letterbox:
           return f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease:flags=bicubic," \
                  f"pad=w={w}:h={h}:x=(ow-iw)/2:y=(oh-ih)/2:color=black"
       else:
           return f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease:flags=bicubic"
   ```

3. **Concatenation**: Uses FFmpeg's concat demuxer for efficiency:
   ```bash
   ffmpeg -f concat -safe 0 -i concat.txt -c copy "<output>.mp4"
   ```
   Falls back to filter-based concat if demuxer fails.

#### Quality Presets

| Preset | CRF | Preset | Audio | Use Case |
|--------|-----|--------|-------|----------|
| Source | 20 | medium | 192k | Match source quality |
| High | 18 | slow | 320k | Maximum quality |
| Medium | 22 | medium | 192k | Balanced quality/size |
| Social/Light | 27 | faster | 128k | Upload-friendly |

## User Interface

### Main Window Layout

The UI follows a three-panel design:

1. **Left Panel**: File list and segment management
2. **Right Panel**: Quick range builder with multiple input rows
3. **Bottom Bar**: Export settings and progress

### Key UI Components

#### File Management
- **Load Files**: Multi-select file dialog for .mp4/.mov files
- **File List**: Shows filename and media info badge
- **Async Probing**: Media info is probed in background threads

#### Segment Management
- **Quick Add Rows**: Three default rows for rapid segment entry
- **Add Range Dialog**: Modal dialog for precise time entry
- **Segment Table**: Displays all segments for selected file
- **Global Order**: Segments maintain global merge order across files

#### Export Settings
- **Preset Dropdown**: Quality presets (Source, High, Medium, Social/Light)
- **Resolution Dropdown**: Auto, Source, or specific resolutions (480p-4320p)
- **FPS Dropdown**: Auto or specific frame rates
- **Letterbox Checkbox**: Aspect ratio preservation option

### Threading and Async Operations

#### Media Probing
```python
class _ProbeWorker(QtCore.QObject):
    done = QtCore.Signal(object)

class _ProbeRunnable(QtCore.QRunnable):
    def run(self):
        info = probe_media_info(self._w._ffprobe, self._w._path)
        self._w.done.emit(info)
```

**Process:**
1. Creates QObject worker with signal
2. Wraps in QRunnable for thread pool execution
3. Emits signal when probe completes
4. UI updates file model with results

#### Export Processing
The `FfmpegExporter` runs in a separate thread and emits:
- `progressChanged(int, str)`: Progress percentage and stage description
- `logLine(str)`: FFmpeg output for debugging
- `finished(bool, str)`: Success status and message

### Theme System

The application supports light/dark themes using QPalette:

```python
def _set_dark_palette(self) -> None:
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(37, 37, 38))
    palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    # ... additional color mappings
    self.setPalette(palette)
```

Theme preference is persisted using QSettings.

## Error Handling

### Media Probing Failures
- Invalid file formats
- Corrupted video files
- Missing FFprobe binary
- Network timeouts for remote files

### Export Failures
- Insufficient disk space
- Invalid segment ranges
- Codec compatibility issues
- FFmpeg binary missing or corrupted

### UI Error Handling
- File selection validation
- Segment range validation (end > start, within duration)
- Export destination validation
- Progress cancellation support

## Performance Considerations

### Memory Management
- Segments stored as lightweight data classes
- Qt models provide efficient data binding
- Temporary files cleaned up after export
- Strong references maintained for async operations

### Threading
- Media probing runs in thread pool to avoid UI blocking
- Export operations run in separate thread with progress reporting
- Qt signals ensure thread-safe UI updates

### FFmpeg Optimization
- Stream copy when possible (no re-encoding)
- Uniform intermediate format for reliable concatenation
- Efficient scaling with bicubic interpolation
- Even dimension enforcement for codec compatibility

## Configuration and Settings

### QSettings Storage
- `theme`: Light/dark theme preference
- `last_dir`: Last used directory for file dialogs

### FFmpeg Binary Detection
```python
def locate_ff_binaries() -> dict:
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    suffix = ".exe" if os.name == "nt" else ""
    return {
        "ffmpeg": os.path.join(base_dir, f"ffmpeg{suffix}"),
        "ffprobe": os.path.join(base_dir, f"ffprobe{suffix}"),
        "ffplay": os.path.join(base_dir, f"ffplay{suffix}"),
    }
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+O | Load Files |
| Delete | Delete selected segments |
| Ctrl+E | Export |
| Ctrl+S | Save Project (planned) |

## Future Enhancements

### Planned Features
1. **Project Save/Load**: JSON-based project files with file path validation
2. **Smart Recommendations**: Automatic export settings based on source analysis
3. **Drag-and-Drop Reordering**: Visual segment reordering with drag support
4. **Video Preview**: Inline preview using FFplay or QtMultimedia
5. **Advanced Presets**: HEVC support, custom quality settings
6. **Timeline View**: Visual timeline for global segment management

### Technical Improvements
1. **Stream Copy Optimization**: Keyframe-aware cutting for faster exports
2. **Batch Processing**: Multiple export jobs with queue management
3. **Progress Estimation**: More accurate progress based on FFmpeg time parsing
4. **Error Recovery**: Automatic retry for transient failures
5. **Plugin System**: Extensible preset and codec support

## Dependencies

### Required
- Python 3.10+
- PySide6 6.5+
- FFmpeg binaries (ffmpeg, ffprobe, ffplay)

### Optional
- PyInstaller (for packaging)
- Additional codecs (for broader format support)

## Build and Distribution

### Development Setup
```bash
pip install -r requirements.txt
python main.py
```

### Windows Launcher
The `run_clip_extractor.bat` script provides:
- Python installation check
- Automatic PySide6 installation
- FFmpeg binary validation
- Error handling and user feedback

### PyInstaller Packaging
```bash
pyinstaller --noconfirm --name ClipExtractor --windowed main.py
```

## Testing Strategy

### Unit Tests (Planned)
- MediaInfo parsing and validation
- Segment duration calculations
- Export profile generation
- FFmpeg command construction

### Integration Tests (Planned)
- End-to-end export workflows
- File format compatibility
- Error condition handling
- UI responsiveness during long operations

## Security Considerations

### File System Access
- User-selected file paths only
- Temporary file cleanup
- No arbitrary command execution

### FFmpeg Security
- Quoted command arguments
- Input validation for all parameters
- No shell injection vulnerabilities

## Conclusion

Clip Extractor demonstrates a modern approach to desktop video processing applications, combining the power of FFmpeg with an intuitive Qt-based interface. The architecture emphasizes separation of concerns, async processing, and user experience while maintaining code clarity and extensibility.

The modular design allows for easy feature additions and the robust error handling ensures reliability across diverse video formats and system configurations.

