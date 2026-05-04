from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from setup.autostart import enable_autostart


def ensure_chime(audio_dir: Path) -> Path:
    audio_dir.mkdir(parents=True, exist_ok=True)
    chime = audio_dir / "chime.wav"
    if chime.exists():
        return chime
    import numpy as np
    from scipy.io import wavfile

    t = np.linspace(0, 0.3, 8000)
    tone = (np.sin(2 * np.pi * 880 * t) * 0.3 * 32767).astype(np.int16)
    wavfile.write(chime, 8000, tone)
    return chime


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    chime = ensure_chime(repo_root / "audio")
    enable_autostart(repo_root)
    service = repo_root / "service" / "imos_service.py"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    subprocess.Popen([str(pythonw), str(service)], cwd=str(repo_root))
    print(f"IMOS service installed and started from {service}")
    print(f"Chime ready at {chime}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
