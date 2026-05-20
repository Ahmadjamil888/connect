import json
import threading
from datetime import datetime
from pathlib import Path


class Memory:
    def __init__(self) -> None:
        self.base_dir = Path.home() / ".imos"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / "memory.json"
        self._lock = threading.Lock()
        if not self.path.exists():
            self._write({"log": []})

    def _read(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
            if isinstance(data, dict):
                data.setdefault("log", [])
                return data
        except Exception:
            pass
        return {"log": []}

    def _write(self, data: dict) -> None:
        with self._lock:
            try:
                with open(self.path, "w", encoding="utf-8") as file_handle:
                    json.dump(data, file_handle, indent=2, ensure_ascii=False)
            except Exception as error:
                print(f"Warning: failed to write memory: {error}")

    def save(self, key, value) -> None:
        data = self._read()
        data[key] = value
        self._write(data)

    def get(self, key):
        return self._read().get(key)

    def append_log(self, entry: str) -> None:
        data = self._read()
        log = data.setdefault("log", [])
        log.append(f"{datetime.now().isoformat()} | {entry}")
        self._write(data)

    def get_log(self, n: int = 20) -> list[str]:
        log = self._read().get("log", [])
        return log[-n:]

    def all(self) -> dict:
        return self._read()

    def clear(self) -> None:
        self._write({"log": []})
