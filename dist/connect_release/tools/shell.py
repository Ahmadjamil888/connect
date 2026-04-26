from typing import Any, Dict, Optional

from ai_assistant import ShellSession


_session = ShellSession("nexus")


def run(command: str, cwd: Optional[str] = None, timeout: int = 60) -> Dict[str, Any]:
    return _session.execute(command, cwd=cwd, timeout=timeout)

