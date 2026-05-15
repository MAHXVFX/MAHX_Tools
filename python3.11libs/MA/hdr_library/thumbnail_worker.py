import os
import subprocess

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt

from MA.common import HDR_EXTENSIONS
from MA.common import find_ffmpeg, _collect_hdr_files


SHARED_PLACEHOLDER_FILENAME = "_placeholder_gray.jpg"


class ThumbnailWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(list, list)
    error = Signal(str)

    def __init__(self, hdr_dir, cache_dir, parent=None):
        super().__init__(parent)
        self.hdr_dir = os.path.normpath(hdr_dir)
        self.cache_dir = os.path.normpath(cache_dir)
        self.ffmpeg_path = find_ffmpeg()
        self._shared_placeholder_path = os.path.join(self.cache_dir, SHARED_PLACEHOLDER_FILENAME)

    def run(self):
        try:
            thumbnails = []
            hdr_files, subfolders = _collect_hdr_files(self.hdr_dir)

            total = len(hdr_files)
            for idx, hdr_path in enumerate(hdr_files):
                try:
                    thumbnail_path, is_placeholder = self._generate_thumbnail(hdr_path)
                    thumbnails.append({
                        'hdr_path': hdr_path,
                        'thumbnail_path': thumbnail_path,
                        'filename': os.path.basename(hdr_path),
                        'is_placeholder': is_placeholder,
                    })
                    self.progress.emit(idx + 1, total)
                except Exception as e:
                    print(f"Error generating thumbnail for {hdr_path}: {e}")

            self.finished.emit(thumbnails, subfolders)
        except Exception as e:
            self.error.emit(str(e))

    def _generate_thumbnail(self, hdr_path):
        hdr_path = os.path.normpath(hdr_path)
        rel_path = os.path.relpath(hdr_path, self.hdr_dir)
        rel_path = rel_path.replace('\\', '/')
        thumbnail_rel = rel_path.rsplit('.', 1)[0] + '_Thumbnail.jpg'
        thumbnail_path = os.path.normpath(os.path.join(self.cache_dir, thumbnail_rel))

        if os.path.exists(thumbnail_path):
            if os.path.getsize(thumbnail_path) > 3000:
                return thumbnail_path, False
            os.remove(thumbnail_path)

        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)

        if self.ffmpeg_path:
            try:
                cmd = [
                    self.ffmpeg_path,
                    '-loglevel', 'error',
                    '-i', hdr_path,
                    '-vf', 'scale=256:256:force_original_aspect_ratio=decrease',
                    '-q:v', '2',
                    '-y',
                    thumbnail_path
                ]
                startup_kwargs = {}
                if os.name == 'nt':
                    startup_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                result = subprocess.run(cmd, capture_output=True, timeout=30, **startup_kwargs)
                thumbnail_path = os.path.normpath(thumbnail_path)
                if result.returncode == 0 and os.path.exists(thumbnail_path):
                    if os.path.getsize(thumbnail_path) > 3000:
                        return thumbnail_path, False
                elif result.returncode != 0:
                    print(f"ffmpeg failed for {hdr_path}: {result.stderr}")
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
            except Exception as e:
                print(f"ffmpeg exception for {hdr_path}: {e}")

        self._ensure_shared_placeholder()
        return self._shared_placeholder_path, True

    def _ensure_shared_placeholder(self):
        if os.path.exists(self._shared_placeholder_path):
            return
        os.makedirs(os.path.dirname(self._shared_placeholder_path), exist_ok=True)
        img = QImage(256, 256, QImage.Format_RGB32)
        img.fill(Qt.GlobalColor.darkGray)
        pixmap = QPixmap.fromImage(img)
        pixmap.save(self._shared_placeholder_path, "JPG", 85)
