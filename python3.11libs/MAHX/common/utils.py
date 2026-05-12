import os
import shutil

from .constants import _MAHX_TOOLS_DIR, HDR_EXTENSIONS


def find_ffmpeg():
    bundled_ffmpeg = os.path.join(_MAHX_TOOLS_DIR, 'ffmpeg.exe')
    if os.path.exists(bundled_ffmpeg):
        return bundled_ffmpeg
    hfs = os.environ.get('HFS', '')
    if hfs:
        hffmpeg_path = os.path.join(hfs, 'bin', 'hffmpeg.exe')
        if os.path.exists(hffmpeg_path):
            return hffmpeg_path
        ffmpeg_path = os.path.join(hfs, 'bin', 'ffmpeg.exe')
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path
    hffmpeg_path = shutil.which('hffmpeg')
    if hffmpeg_path:
        return hffmpeg_path
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return ffmpeg_path
    return None


def _collect_hdr_files(base_dir):
    hdr_files = []
    subfolders = []
    if not os.path.exists(base_dir):
        return hdr_files, subfolders

    try:
        for item in os.listdir(base_dir):
            item_path = os.path.normpath(os.path.join(base_dir, item))
            if os.path.isfile(item_path):
                if any(item.lower().endswith(ext) for ext in HDR_EXTENSIONS):
                    hdr_files.append(item_path)
            elif os.path.isdir(item_path):
                subfolders.append(item)
                try:
                    for sub_item in os.listdir(item_path):
                        sub_item_path = os.path.normpath(os.path.join(item_path, sub_item))
                        if os.path.isfile(sub_item_path):
                            if any(sub_item.lower().endswith(ext) for ext in HDR_EXTENSIONS):
                                hdr_files.append(sub_item_path)
                except (PermissionError, OSError):
                    pass
    except (PermissionError, OSError):
        pass
    return hdr_files, subfolders
