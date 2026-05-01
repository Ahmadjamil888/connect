from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, simpledialog

try:
    import keyboard
except ModuleNotFoundError as exc:
    raise SystemExit("Missing dependency: keyboard. Install it with `pip install keyboard`.") from exc

from connectai.jarvis import JarvisRuntime


runtime = JarvisRuntime()
root = tk.Tk()
root.withdraw()
busy_lock = threading.Lock()


def _show_response(text: str):
    try:
        messagebox.showinfo("Jarvis", text[:4000] if text else "No response.")
    finally:
        if busy_lock.locked():
            busy_lock.release()


def _run_prompt():
    if not busy_lock.acquire(blocking=False):
        return
    prompt = simpledialog.askstring("Jarvis", "Ask Jarvis")
    if prompt is None or not prompt.strip():
        busy_lock.release()
        return

    def worker():
        try:
            response = runtime.process(prompt.strip())
        except Exception as exc:
            response = f"Jarvis error: {exc}"
        root.after(0, lambda: _show_response(response))

    threading.Thread(target=worker, daemon=True).start()


def main():
    keyboard.add_hotkey("ctrl+space", lambda: root.after(0, _run_prompt))
    try:
        root.mainloop()
    finally:
        keyboard.unhook_all_hotkeys()


if __name__ == "__main__":
    main()
