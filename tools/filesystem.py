import shutil
from pathlib import Path
from typing import Any, Dict, List


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def read_file(path: str) -> str:
    target = _resolve(path)
    if not target.exists():
        return f"File not found: {target}"
    if target.is_dir():
        return f"Path is a directory: {target}"
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return target.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except Exception as exc:
            return f"Error reading {target}: {exc}"
    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Error reading {target}: {exc}"


def write_file(path: str, content: str) -> str:
    target = _resolve(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {target}"
    except Exception as exc:
        return f"Error writing {target}: {exc}"


def list_dir(path: str) -> List[Dict[str, Any]]:
    target = _resolve(path)
    if not target.exists():
        return [{"error": f"Path not found: {target}"}]
    if not target.is_dir():
        return [{"error": f"Path is not a directory: {target}"}]
    items: List[Dict[str, Any]] = []
    try:
        for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            stat = item.stat()
            items.append(
                {
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": stat.st_size,
                }
            )
        return items
    except Exception as exc:
        return [{"error": f"Error listing {target}: {exc}"}]


def delete_path(path: str) -> str:
    target = _resolve(path)
    if not target.exists():
        return f"Path not found: {target}"
    try:
        if target.is_dir():
            shutil.rmtree(target)
            return f"Deleted directory {target}"
        target.unlink()
        return f"Deleted file {target}"
    except Exception as exc:
        return f"Error deleting {target}: {exc}"


def search_files(pattern: str, directory: str = ".") -> List[str]:
    base = _resolve(directory)
    if not base.exists():
        return [f"Path not found: {base}"]
    try:
        return [str(path) for path in base.rglob(pattern)]
    except Exception as exc:
        return [f"Error searching {base}: {exc}"]


def copy_file(src: str, dst: str) -> str:
    source = _resolve(src)
    dest = _resolve(dst)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return f"Copied {source} -> {dest}"
    except Exception as exc:
        return f"Error copying {source} -> {dest}: {exc}"


def move_file(src: str, dst: str) -> str:
    source = _resolve(src)
    dest = _resolve(dst)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))
        return f"Moved {source} -> {dest}"
    except Exception as exc:
        return f"Error moving {source} -> {dest}: {exc}"

