from __future__ import annotations

import atexit
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from typing import Iterable

import pyttsx3
import speech_recognition as sr


HOME = Path.home()
IMOS_HOME = HOME / ".imos"
PID_FILE = IMOS_HOME / "wake_service.pid"
LOG_FILE = IMOS_HOME / "wake_service.log"
WINDOWS_AUTOSTART = HOME / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/imos-wake.cmd"
LINUX_AUTOSTART = HOME / ".config/autostart/imos-wake.desktop"
MAC_AUTOSTART = HOME / "Library/LaunchAgents/com.imos.wake.plist"
WAKE_PHRASES = ("imos", "hey imos", "hi imos", "hi")
GREETING = "Hi sir, how's going."


def _ensure_home() -> None:
    IMOS_HOME.mkdir(parents=True, exist_ok=True)


def _log(message: str) -> None:
    _ensure_home()
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _is_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        if os.name == "nt":
            output = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                check=False,
            )
            return str(pid) in output.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _write_pid() -> None:
    _ensure_home()
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _clear_pid() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _pythonw() -> str:
    candidate = Path(sys.executable)
    if os.name == "nt":
        possible = candidate.with_name("pythonw.exe")
        if possible.exists():
            return str(possible)
    return sys.executable


def _launch_imos_session() -> None:
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(["powershell", "-NoExit", "-Command", "imos"], creationflags=creationflags)
        return
    if sys.platform == "darwin":
        script = 'tell application "Terminal" to do script "imos"'
        subprocess.Popen(["osascript", "-e", script])
        return

    candidates: list[list[str]] = [
        ["x-terminal-emulator", "-e", "imos"],
        ["gnome-terminal", "--", "imos"],
        ["konsole", "-e", "imos"],
        ["xfce4-terminal", "-e", "imos"],
        ["xterm", "-e", "imos"],
    ]
    for command in candidates:
        try:
            subprocess.Popen(command)
            return
        except Exception:
            continue
    subprocess.Popen([sys.executable, "-m", "imos.cli"])


def _speak(message: str) -> None:
    try:
        engine = pyttsx3.init()
        engine.say(message)
        engine.runAndWait()
    except Exception as exc:
        _log(f"speech_error {exc}")


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _matches_wake_phrase(text: str, phrases: Iterable[str]) -> bool:
    normalized = _normalize(text)
    for phrase in phrases:
        target = _normalize(phrase)
        if normalized == target:
            return True
        if normalized.startswith(f"{target} "):
            return True
        if normalized.endswith(f" {target}"):
            return True
    return False


def _install_autostart_file() -> Path:
    _ensure_home()
    if os.name == "nt":
        WINDOWS_AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
        WINDOWS_AUTOSTART.write_text(f'@echo off\r\n"{_pythonw()}" -m imos.wake_service run\r\n', encoding="utf-8")
        return WINDOWS_AUTOSTART

    if sys.platform == "darwin":
        MAC_AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
        MAC_AUTOSTART.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.imos.wake</string>
  <key>ProgramArguments</key>
  <array>
    <string>{sys.executable}</string>
    <string>-m</string>
    <string>imos.wake_service</string>
    <string>run</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{LOG_FILE}</string>
  <key>StandardErrorPath</key><string>{LOG_FILE}</string>
</dict>
</plist>
""",
            encoding="utf-8",
        )
        return MAC_AUTOSTART

    LINUX_AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    LINUX_AUTOSTART.write_text(
        f"""[Desktop Entry]
Type=Application
Name=IMOS Wake Service
Exec={sys.executable} -m imos.wake_service run
X-GNOME-Autostart-enabled=true
Terminal=false
""",
        encoding="utf-8",
    )
    return LINUX_AUTOSTART


def uninstall_autostart() -> list[Path]:
    removed: list[Path] = []
    for path in (WINDOWS_AUTOSTART, LINUX_AUTOSTART, MAC_AUTOSTART):
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed


def start_background() -> str:
    existing = _read_pid()
    if _is_running(existing):
        return f"already running ({existing})"
    _ensure_home()
    stdout = LOG_FILE.open("a", encoding="utf-8")
    stderr = LOG_FILE.open("a", encoding="utf-8")
    kwargs: dict[str, object] = {"stdout": stdout, "stderr": stderr}
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([sys.executable, "-m", "imos.wake_service", "run"], **kwargs)
    return "started"


def stop_background() -> str:
    pid = _read_pid()
    if not _is_running(pid):
        _clear_pid()
        return "not running"
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False, capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
    finally:
        _clear_pid()
    return f"stopped ({pid})"


def status() -> dict[str, object]:
    pid = _read_pid()
    return {
        "running": _is_running(pid),
        "pid": pid,
        "log_file": str(LOG_FILE),
        "autostart_files": [str(path) for path in (WINDOWS_AUTOSTART, LINUX_AUTOSTART, MAC_AUTOSTART) if path.exists()],
    }


def run_service() -> None:
    existing = _read_pid()
    if _is_running(existing) and existing != os.getpid():
        _log(f"wake_service_already_running pid={existing}")
        return

    _ensure_home()
    _write_pid()
    atexit.register(_clear_pid)
    _log("wake_service_started")

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    stop_event = threading.Event()
    last_trigger = 0.0

    def _shutdown(*_: object) -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _shutdown)
        except Exception:
            pass

    try:
        microphone = sr.Microphone()
    except Exception as exc:
        _log(f"microphone_error {exc}")
        return

    with microphone as source:
        try:
            recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception as exc:
            _log(f"ambient_error {exc}")

    def callback(_: sr.Recognizer, audio: sr.AudioData) -> None:
        nonlocal last_trigger
        try:
            transcript = recognizer.recognize_google(audio)
            _log(f"heard {transcript}")
        except sr.UnknownValueError:
            return
        except Exception as exc:
            _log(f"recognition_error {exc}")
            return
        if not _matches_wake_phrase(transcript, WAKE_PHRASES):
            return
        now = time.monotonic()
        if now - last_trigger < 10:
            return
        last_trigger = now
        _log("wake_phrase_detected")
        _speak(GREETING)
        _launch_imos_session()

    stop_listening = recognizer.listen_in_background(microphone, callback, phrase_time_limit=3)
    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    finally:
        stop_listening(wait_for_stop=False)
        _log("wake_service_stopped")


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    command = args[0] if args else "run"
    if command == "run":
        run_service()
        return
    if command == "start":
        print(start_background())
        return
    if command == "stop":
        print(stop_background())
        return
    if command == "status":
        print(status())
        return
    if command == "install":
        print(_install_autostart_file())
        return
    if command == "uninstall":
        print(uninstall_autostart())
        return
    raise SystemExit(f"Unknown wake command: {command}")


if __name__ == "__main__":
    main()
