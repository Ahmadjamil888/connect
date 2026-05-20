import json
from pathlib import Path


DEFAULT_POLICY = {
    "run_shell": "ask",
    "write_file": "allow",
    "append_file": "allow",
    "make_dir": "allow",
    "open_url": "allow",
    "open_app": "ask",
    "claude_code": "ask",
    "http_request": "allow",
    "read_file": "allow",
    "list_dir": "allow",
    "browser": "ask",
}


class Policy:
    def __init__(self) -> None:
        self.base_dir = Path.home() / ".imos"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / "policy.json"
        if not self.path.exists():
            self._write(DEFAULT_POLICY.copy())

    def _read(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
            if isinstance(data, dict):
                merged = DEFAULT_POLICY.copy()
                merged.update(data)
                return merged
        except Exception:
            pass
        return DEFAULT_POLICY.copy()

    def _write(self, data: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as file_handle:
            json.dump(data, file_handle, indent=2, ensure_ascii=False)

    def check(self, tool_name: str) -> str:
        return self._read().get(tool_name, "ask")

    def set(self, tool_name: str, value: str) -> None:
        if value not in {"allow", "ask", "deny"}:
            raise ValueError("Policy value must be allow, ask, or deny.")
        data = self._read()
        data[tool_name] = value
        self._write(data)

    def show(self) -> None:
        data = self._read()
        print("IMOS Policy")
        for key, value in data.items():
            print(f"  {key:<12} {value}")

    def all(self) -> dict:
        return self._read()
