"""Runtime paths shared by source and PyInstaller builds."""

from pathlib import Path
import sys


def resource_path(relative_path: str) -> Path:
    """Return a bundled asset path when packaged, or a source-tree path."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path
