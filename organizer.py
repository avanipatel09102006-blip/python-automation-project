"""File-organising engine. Safety rules:
 - only folders inside the user's home folder (never the home itself, drives or system paths)
 - top-level files only; symlinks, hidden files and half-downloaded files are skipped
 - nothing is ever deleted or overwritten (name clashes get ' (1)', ' (2)' ...)
 - every move can be undone."""
import os
import shutil
import time
from pathlib import Path

CATEGORIES = {
    "Images": "jpg jpeg png gif bmp webp svg heic tiff ico",
    "Documents": "pdf doc docx txt rtf odt xls xlsx csv ppt pptx md",
    "Videos": "mp4 mkv avi mov wmv flv webm",
    "Audio": "mp3 wav aac flac ogg m4a",
    "Archives": "zip rar 7z tar gz bz2",
    "Code": "py js html css json java c cpp php sql xml ipynb",
    "Installers": "exe msi dmg apk deb",
}
EXT_MAP = {f".{e}": cat for cat, exts in CATEGORIES.items() for e in exts.split()}
PARTIAL = {".crdownload", ".part", ".tmp", ".download", ".opdownload"}
SKIP_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
MIN_AGE_SECONDS = 10          # recently-changed files may still be downloading


def category_for(name):
    return EXT_MAP.get(Path(name).suffix.lower(), "Others")


def _norm(p):
    return os.path.normcase(str(p))


def validate_folder(path_str):
    """Return (resolved Path, None) or (None, error message)."""
    try:
        p = Path(path_str.strip().strip('"')).expanduser().resolve()
        home = Path.home().resolve()
    except (OSError, RuntimeError, ValueError):
        return None, "That path is not valid."
    if not p.is_dir():
        return None, "Folder not found. Check the path."
    try:
        inside = os.path.commonpath([_norm(p), _norm(home)]) == _norm(home)
    except ValueError:             # different drives
        inside = False
    if not inside or _norm(p) == _norm(home):
        return None, "For safety, choose a folder inside your user folder (for example Downloads), not the user folder itself."
    if _norm(p) == _norm(Path(__file__).parent):
        return None, "You cannot organise this application's own folder."
    return p, None


def plan(folder, min_age=MIN_AGE_SECONDS):
    items, now = [], time.time()
    for e in os.scandir(folder):
        try:
            if not e.is_file(follow_symlinks=False) or e.name.startswith(".") or e.name.lower() in SKIP_NAMES:
                continue
            if Path(e.name).suffix.lower() in PARTIAL:
                continue
            st = e.stat()
            if now - st.st_mtime < min_age:
                continue
            items.append({"name": e.name, "category": category_for(e.name), "size": st.st_size})
        except OSError:
            continue
    return sorted(items, key=lambda i: (i["category"], i["name"].lower()))


def unique_path(directory, name):
    target, stem, ext, n = Path(directory) / name, Path(name).stem, Path(name).suffix, 1
    while target.exists():
        target = Path(directory) / f"{stem} ({n}){ext}"
        n += 1
    return target


def execute(folder, items):
    moves, errors = [], 0
    for it in items:
        src = Path(folder) / it["name"]
        try:
            dest_dir = Path(folder) / it["category"]
            dest_dir.mkdir(exist_ok=True)
            dst = unique_path(dest_dir, it["name"])
            shutil.move(str(src), str(dst))
            moves.append({"src": str(src), "dst": str(dst), "category": it["category"], "size": it["size"]})
        except OSError:
            errors += 1
    return moves, errors


def restore(moves):
    restored = missing = 0
    for m in reversed(moves):
        dst, src = Path(m["dst"]), Path(m["src"])
        if not dst.exists():
            missing += 1
            continue
        try:
            target = src if not src.exists() else unique_path(src.parent, src.name)
            shutil.move(str(dst), str(target))
            restored += 1
            try:
                dst.parent.rmdir()          # remove the category folder only if it is now empty
            except OSError:
                pass
        except OSError:
            missing += 1
    return restored, missing
