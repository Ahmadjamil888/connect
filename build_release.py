from __future__ import annotations

import json
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
PACKAGE = DIST / "connect_release"


INCLUDE = [
    "ai_assistant.py",
    "connect.bat",
    "install_connect_command.bat",
    "requirements.txt",
    "openclaw.json.example",
    "README.md",
    "OPENCLAW_PARITY.md",
    "gateway_runtime",
    "tools",
    "core",
]

FRONTEND_DIR = ROOT / "CUsersAdminDesktopconnect frontend"
FRONTEND_INCLUDE = [
    ".env.example",
    "index.html",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
    "vite.config.ts",
    "src",
    "public",
    "dist",
]


def main():
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True, exist_ok=True)
    for item in INCLUDE:
        source = ROOT / item
        target = PACKAGE / item
        if source.is_dir():
            shutil.copytree(source, target)
        elif source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    if FRONTEND_DIR.exists():
        frontend_target = PACKAGE / "connect frontend"
        frontend_target.mkdir(parents=True, exist_ok=True)
        for item in FRONTEND_INCLUDE:
            source = FRONTEND_DIR / item
            target = frontend_target / item
            if source.is_dir():
                shutil.copytree(source, target)
            elif source.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    manifest = {
        "name": "connect",
        "entrypoint": "ai_assistant.py",
        "launcher": "connect.bat",
        "created_from": str(ROOT),
    }
    (PACKAGE / "release_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    archive = DIST / "connect_release.zip"
    if archive.exists():
        archive.unlink()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zf:
        for path in PACKAGE.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(PACKAGE))
    print(str(archive))


if __name__ == "__main__":
    main()
