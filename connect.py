from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from core.agent_engine import AgentEngine
from core.tool_registry import ToolRegistry


def main() -> None:
    load_dotenv()
    registry = ToolRegistry()
    engine = AgentEngine(registry)
    print("CONNECT real-action REPL")
    print("Commands: /tools, /audit, /policy, /clear, /exit")
    while True:
        try:
            raw = input("connect> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        if raw == "/exit":
            break
        if raw == "/tools":
            for name in registry.names():
                print(name)
            continue
        if raw == "/audit":
            for row in engine.audit.tail(20):
                print(json.dumps(row, ensure_ascii=False))
            continue
        if raw == "/policy":
            granted = sorted(engine.consent.blanket_grants)
            print(json.dumps({"blanket_grants": granted}, ensure_ascii=False))
            continue
        if raw == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            continue
        print(engine.ask(raw))


if __name__ == "__main__":
    main()
