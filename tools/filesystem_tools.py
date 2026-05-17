from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path
from typing import Any


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def read_file(path: str) -> dict[str, Any]:
    try:
        target = _resolve(path)
        content = target.read_text(encoding="utf-8")
        return {"status": "success", "path": str(target), "content": content, "bytes_read": len(content.encode("utf-8"))}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "path": path}


def write_file(path: str, content: str, mode: str = "write") -> dict[str, Any]:
    try:
        target = _resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if mode == "append":
            with target.open("a", encoding="utf-8") as handle:
                handle.write(content)
        else:
            target.write_text(content, encoding="utf-8")
        return {"status": "success", "path": str(target), "bytes_written": len(content.encode("utf-8")), "mode": mode}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "path": path}


def create_directory(path: str) -> dict[str, Any]:
    try:
        target = _resolve(path)
        target.mkdir(parents=True, exist_ok=True)
        return {"status": "success", "path": str(target)}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "path": path}


def _tree(path: Path, depth: int) -> dict[str, Any]:
    node = {"name": path.name, "path": str(path), "type": "directory" if path.is_dir() else "file"}
    if path.is_dir() and depth > 0:
        children = []
        for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            children.append(_tree(child, depth - 1))
        node["children"] = children
    return node


def list_directory(path: str, depth: int = 2) -> dict[str, Any]:
    try:
        target = _resolve(path)
        return {"status": "success", "path": str(target), "tree": _tree(target, depth)}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "path": path}


def delete_file(path: str) -> dict[str, Any]:
    try:
        target = _resolve(path)
        existed = target.exists()
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return {"status": "success", "path": str(target), "deleted": existed}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "path": path}


def move_file(src: str, dst: str) -> dict[str, Any]:
    try:
        source = _resolve(src)
        target = _resolve(dst)
        target.parent.mkdir(parents=True, exist_ok=True)
        final_path = shutil.move(str(source), str(target))
        return {"status": "success", "source": str(source), "destination": str(target), "final_path": str(Path(final_path).resolve())}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "source": src, "destination": dst}


def search_files(root: str, pattern: str = "*", content_search: str | None = None) -> dict[str, Any]:
    try:
        base = _resolve(root)
        matches: list[dict[str, Any]] = []
        for dirpath, _dirnames, filenames in os.walk(base):
            for filename in filenames:
                if not fnmatch.fnmatch(filename, pattern):
                    continue
                target = Path(dirpath) / filename
                if content_search:
                    try:
                        content = target.read_text(encoding="utf-8")
                    except Exception:
                        continue
                    if content_search not in content:
                        continue
                matches.append({"path": str(target.resolve()), "name": filename})
        return {"status": "success", "root": str(base), "pattern": pattern, "matches": matches, "count": len(matches)}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "root": root}
