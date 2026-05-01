"""
IMOS Clean PC skill — delete temp files and report freed space in MB.
Returns freed_mb as a float so verification passes.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "confirm": {"type": "boolean"},
    },
}


def run(inputs, **_kwargs):
    confirm = bool(inputs.get("confirm", False))
    if not confirm:
        return {
            "ok": False,
            "error": "Refusing to clean temp files without confirm=true.",
            "freed_mb": 0.0,
        }

    targets = {Path(tempfile.gettempdir())}
    if os.name == "nt":
        windows_temp = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Temp"
        targets.add(windows_temp)

    removed = 0
    errors = 0
    freed_bytes = 0

    for target in targets:
        if not target.exists():
            continue
        for child in target.iterdir():
            try:
                size = 0
                if child.is_dir():
                    # Calculate size before deletion
                    for f in child.rglob("*"):
                        try:
                            if f.is_file():
                                size += f.stat().st_size
                        except Exception:
                            pass
                    shutil.rmtree(child, ignore_errors=False)
                else:
                    try:
                        size = child.stat().st_size
                    except Exception:
                        size = 0
                    child.unlink()
                freed_bytes += size
                removed += 1
            except Exception:
                errors += 1

    freed_mb = round(freed_bytes / (1024 * 1024), 2)
    return {
        "ok": True,
        "freed_mb": freed_mb,
        "freed_bytes": freed_bytes,
        "removed": removed,
        "errors": errors,
        "message": f"Temp cleanup complete. Freed {freed_mb} MB. Removed={removed}, errors={errors}",
    }
