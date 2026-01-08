import os
import sys
from PySide6 import QtWidgets, QtCore


def _apply_high_dpi_attributes() -> None:
    # Qt6 enables high-DPI scaling by default; keep as no-op to avoid deprecation warnings.
    return None


def locate_ff_binaries() -> dict:
    """Return paths for ffmpeg/ffprobe/ffplay expected to be next to the app.

    On Windows, users will place the binaries next to this script/exe.
    """
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    suffix = ".exe" if os.name == "nt" else ""
    return {
        "ffmpeg": os.path.join(base_dir, f"ffmpeg{suffix}"),
        "ffprobe": os.path.join(base_dir, f"ffprobe{suffix}"),
        "ffplay": os.path.join(base_dir, f"ffplay{suffix}"),
    }


def main() -> int:
    _apply_high_dpi_attributes()
    app = QtWidgets.QApplication(sys.argv)
    app.setOrganizationName("ClipExtractor")
    app.setApplicationName("Clip Extractor")

    from clip_extractor.ui.main_window import MainWindow

    ff_bins = locate_ff_binaries()
    window = MainWindow(ff_bins=ff_bins)
    window.resize(1280, 800)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())


