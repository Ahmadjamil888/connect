from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable


@dataclass
class ConfirmationDecision:
    allowed: bool
    prompt: str = ""
    reason: str = ""


class ConfirmationPolicy:
    def __init__(self, asker: Callable[[str], str] | None = None):
        self.asker = asker or input

    def confirm_delete(self, path: str) -> ConfirmationDecision:
        prompt = f"About to permanently delete: {path}\n Continue? (yes/no) "
        if not sys.stdin or not sys.stdin.isatty():
            return ConfirmationDecision(False, prompt=prompt, reason="non-interactive default=no")
        answer = (self.asker(prompt) or "").strip().lower()
        return ConfirmationDecision(answer == "yes", prompt=prompt, reason="" if answer == "yes" else "default=no")

    def confirm_purchase(self, description: str) -> ConfirmationDecision:
        prompt = f"About to spend money: {description}\n Continue? (yes/no) "
        if not sys.stdin or not sys.stdin.isatty():
            return ConfirmationDecision(False, prompt=prompt, reason="non-interactive default=no")
        answer = (self.asker(prompt) or "").strip().lower()
        return ConfirmationDecision(answer == "yes", prompt=prompt, reason="" if answer == "yes" else "default=no")

