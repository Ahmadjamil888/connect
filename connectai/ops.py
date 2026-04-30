from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class CommandExecution:
    ok: bool
    command: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    log_path: str = ""


class AuditLogger:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "audit.jsonl"
        self._lock = threading.Lock()

    def append(self, kind: str, message: str, metadata: Dict[str, Any] | None = None):
        payload = {
            "ts": utcnow_iso(),
            "kind": kind,
            "message": message,
            "metadata": metadata or {},
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def tail(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-limit:]


class CostTracker:
    COST_PER_1K = {
        "claude-opus-4-5": {"input": 0.015, "output": 0.075},
        "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
        "claude-haiku-4-5": {"input": 0.00025, "output": 0.00125},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "o3-mini": {"input": 0.0011, "output": 0.0044},
        "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
        "llama-3.3-70b-versatile": {"input": 0.00059, "output": 0.00079},
        "llama-3.1-8b-instant": {"input": 0.00005, "output": 0.00008},
    }

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "cost.jsonl"
        self.summary_path = self.root / "cost_summary.json"
        self._lock = threading.Lock()
        if not self.summary_path.exists():
            self.summary_path.write_text(json.dumps(self._empty_summary(), indent=2), encoding="utf-8")

    def _empty_summary(self) -> Dict[str, Any]:
        return {
            "session_input": 0,
            "session_output": 0,
            "session_total_tokens": 0,
            "session_cost_usd": 0.0,
            "last_model": "",
            "last_input_tokens": 0,
            "last_output_tokens": 0,
            "last_cost_usd": 0.0,
        }

    def _load_summary(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.summary_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return self._empty_summary()

    def _save_summary(self, data: Dict[str, Any]):
        self.summary_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _rates_for(self, model: str) -> Dict[str, float]:
        if model in self.COST_PER_1K:
            return self.COST_PER_1K[model]
        for known, rates in self.COST_PER_1K.items():
            if model.startswith(known):
                return rates
        return {"input": 0.0, "output": 0.0}

    def record(self, model: str, input_tokens: int, output_tokens: int) -> Dict[str, Any]:
        rates = self._rates_for(model)
        cost = (input_tokens / 1000.0 * rates["input"]) + (output_tokens / 1000.0 * rates["output"])
        with self._lock:
            summary = self._load_summary()
            summary["session_input"] += int(input_tokens)
            summary["session_output"] += int(output_tokens)
            summary["session_total_tokens"] = summary["session_input"] + summary["session_output"]
            summary["session_cost_usd"] = round(float(summary["session_cost_usd"]) + cost, 6)
            summary["last_model"] = model
            summary["last_input_tokens"] = int(input_tokens)
            summary["last_output_tokens"] = int(output_tokens)
            summary["last_cost_usd"] = round(cost, 6)
            self._save_summary(summary)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "ts": utcnow_iso(),
                    "model": model,
                    "input_tokens": int(input_tokens),
                    "output_tokens": int(output_tokens),
                    "cost_usd": round(cost, 6),
                }) + "\n")
        return summary

    def summary(self) -> Dict[str, Any]:
        return self._load_summary()


class ApprovalPolicy:
    def __init__(self, config_loader, audit_logger: AuditLogger):
        self.config_loader = config_loader
        self.audit_logger = audit_logger

    def _mode(self) -> str:
        cfg = self.config_loader() or {}
        mode = str(cfg.get("approvals", {}).get("mode", "warn")).strip().lower()
        return mode or "warn"

    def evaluate_command(self, command: str) -> Dict[str, Any]:
        lowered = command.lower()
        patterns = [
            "rm -rf",
            "remove-item -recurse",
            "del /f",
            "format ",
            "mkfs",
            "shutdown",
            "restart-computer",
            "stop-computer",
            "reg delete",
            "rmdir /s",
        ]
        dangerous = any(pattern in lowered for pattern in patterns)
        mode = self._mode()
        result = {
            "allowed": True,
            "dangerous": dangerous,
            "mode": mode,
            "reason": "",
        }
        if dangerous and mode == "block":
            result["allowed"] = False
            result["reason"] = "Command blocked by destructive command policy."
        elif dangerous and mode == "warn":
            result["reason"] = "Dangerous command detected. Switch approvals.mode to allow-all to run it."
        self.audit_logger.append("approval_check", command, result)
        return result


class ShellRunner:
    def __init__(self, root: Path, audit_logger: AuditLogger, approval_policy: ApprovalPolicy):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.audit_logger = audit_logger
        self.approval_policy = approval_policy

    def run(self, command: str, cwd: str, timeout: int = 120) -> CommandExecution:
        policy = self.approval_policy.evaluate_command(command)
        if not policy["allowed"]:
            return CommandExecution(
                ok=False,
                command=command,
                cwd=cwd,
                returncode=1,
                stdout="",
                stderr=policy["reason"],
                duration_seconds=0.0,
            )

        command_id = uuid.uuid4().hex[:12]
        log_path = self.root / f"{command_id}.log"
        started = time.time()
        self.audit_logger.append("command_start", command, {"cwd": cwd, "timeout": timeout, "command_id": command_id})
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            bufsize=1,
        )
        stdout_chunks: List[str] = []
        stderr_chunks: List[str] = []

        def pump(stream, sink: List[str], stream_name: str):
            if stream is None:
                return
            with log_path.open("a", encoding="utf-8") as handle:
                for line in iter(stream.readline, ""):
                    if not line:
                        break
                    sink.append(line)
                    handle.write(f"[{stream_name}] {line}")
                    handle.flush()
                    self.audit_logger.append(
                        "command_output",
                        line.rstrip("\r\n"),
                        {
                            "command": command,
                            "cwd": cwd,
                            "command_id": command_id,
                            "stream": stream_name,
                        },
                    )

        stdout_thread = threading.Thread(target=pump, args=(process.stdout, stdout_chunks, "stdout"), daemon=True)
        stderr_thread = threading.Thread(target=pump, args=(process.stderr, stderr_chunks, "stderr"), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        timed_out = False
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            returncode = process.wait()
            self.audit_logger.append(
                "command_output",
                f"Command timed out after {timeout}s",
                {"command": command, "cwd": cwd, "command_id": command_id, "stream": "stderr"},
            )
            stderr_chunks.append(f"Command timed out after {timeout}s\n")

        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
        duration = round(time.time() - started, 3)
        execution = CommandExecution(
            ok=returncode == 0 and not timed_out,
            command=command,
            cwd=cwd,
            returncode=returncode,
            stdout="".join(stdout_chunks),
            stderr="".join(stderr_chunks),
            duration_seconds=duration,
            log_path=str(log_path),
        )
        self.audit_logger.append(
            "command_end",
            command,
            {
                "cwd": cwd,
                "returncode": returncode,
                "duration_seconds": duration,
                "log_path": str(log_path),
                "command_id": command_id,
                "timed_out": timed_out,
            },
        )
        return execution


@dataclass
class ManagedProcess:
    process_id: str
    pid: int
    name: str
    command: str
    cwd: str
    started_at: str = field(default_factory=utcnow_iso)
    status: str = "running"
    log_path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProcessRegistry:
    def __init__(self, root: Path, audit_logger: AuditLogger):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "processes.json"
        self.logs_dir = self.root / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.audit_logger = audit_logger

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if not self.index_path.exists():
            return {}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save(self, data: Dict[str, Dict[str, Any]]):
        self.index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def register(self, *, name: str, command: str, cwd: str, process: subprocess.Popen, metadata: Dict[str, Any] | None = None) -> ManagedProcess:
        process_id = uuid.uuid4().hex[:12]
        log_path = self.logs_dir / f"{process_id}.log"
        record = ManagedProcess(
            process_id=process_id,
            pid=process.pid,
            name=name,
            command=command,
            cwd=cwd,
            log_path=str(log_path),
            metadata=metadata or {},
        )
        data = self._load()
        data[process_id] = asdict(record)
        self._save(data)
        self.audit_logger.append("process_start", command, {"pid": process.pid, "cwd": cwd, "process_id": process_id})
        self._start_log_threads(process, log_path, process_id)
        return record

    def _start_log_threads(self, process: subprocess.Popen, log_path: Path, process_id: str):
        def pump(stream, prefix: str):
            if stream is None:
                return
            with log_path.open("a", encoding="utf-8") as handle:
                for line in iter(stream.readline, ""):
                    if not line:
                        break
                    handle.write(f"[{prefix}] {line}")
                    handle.flush()
                    self.audit_logger.append(
                        "process_output",
                        line.rstrip("\r\n"),
                        {
                            "process_id": process_id,
                            "pid": process.pid,
                            "stream": prefix,
                        },
                    )

        threading.Thread(target=pump, args=(process.stdout, "stdout"), daemon=True).start()
        threading.Thread(target=pump, args=(process.stderr, "stderr"), daemon=True).start()

        def watch():
            returncode = process.wait()
            data = self._load()
            row = data.get(process_id)
            if not row:
                return
            row["status"] = "exited"
            row["returncode"] = returncode
            row["ended_at"] = utcnow_iso()
            data[process_id] = row
            self._save(data)
            self.audit_logger.append("process_end", row["command"], {"pid": row["pid"], "returncode": returncode, "process_id": process_id})

        threading.Thread(target=watch, daemon=True).start()

    def list(self) -> List[Dict[str, Any]]:
        return list(self._load().values())

    def stop(self, process_id: str) -> Dict[str, Any]:
        data = self._load()
        row = data.get(process_id)
        if not row:
            return {"ok": False, "error": f"Unknown process: {process_id}"}
        pid = int(row["pid"])
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, timeout=30)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        row["status"] = "stopped"
        row["ended_at"] = utcnow_iso()
        data[process_id] = row
        self._save(data)
        self.audit_logger.append("process_stop", row["command"], {"pid": pid, "process_id": process_id})
        return {"ok": True, "process_id": process_id, "pid": pid}

    def tail_log(self, process_id: str, limit_chars: int = 4000) -> str:
        row = self._load().get(process_id)
        if not row:
            return ""
        log_path = Path(row.get("log_path", ""))
        if not log_path.exists():
            return ""
        return log_path.read_text(encoding="utf-8", errors="replace")[-limit_chars:]


@dataclass
class TaskRecord:
    task_id: str
    objective: str
    status: str
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)
    session_id: str = ""
    attempts: int = 0
    plan: List[Dict[str, Any]] = field(default_factory=list)
    outcomes: List[Dict[str, Any]] = field(default_factory=list)


class TaskManager:
    def __init__(self, root: Path, audit_logger: AuditLogger):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "tasks.json"
        self.audit_logger = audit_logger

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if not self.index_path.exists():
            return {}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save(self, data: Dict[str, Dict[str, Any]]):
        self.index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def create(self, objective: str, session_id: str, plan: List[Dict[str, Any]] | None = None) -> TaskRecord:
        task = TaskRecord(
            task_id=uuid.uuid4().hex[:12],
            objective=objective,
            session_id=session_id,
            status="running",
            plan=plan or [],
        )
        data = self._load()
        data[task.task_id] = asdict(task)
        self._save(data)
        self.audit_logger.append("task_create", objective, {"task_id": task.task_id, "session_id": session_id})
        return task

    def update(self, task: TaskRecord):
        data = self._load()
        task.updated_at = utcnow_iso()
        data[task.task_id] = asdict(task)
        self._save(data)

    def complete(self, task: TaskRecord, status: str, outcomes: List[Dict[str, Any]]):
        task.status = status
        task.outcomes = outcomes[-50:]
        self.update(task)
        self.audit_logger.append("task_complete", task.objective, {"task_id": task.task_id, "status": status})

    def list(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = list(self._load().values())
        rows.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return rows[:limit]


class TerminalSessionManager:
    def __init__(self, root: Path, audit_logger: AuditLogger):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.audit_logger = audit_logger
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _default_shell(self) -> List[str]:
        if os.name == "nt":
            return ["cmd.exe"]
        return [os.environ.get("SHELL", "/bin/bash")]

    def open(self, cwd: str, command: List[str] | None = None) -> Dict[str, Any]:
        session_id = uuid.uuid4().hex[:12]
        proc = subprocess.Popen(
            command or self._default_shell(),
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        session = {
            "session_id": session_id,
            "pid": proc.pid,
            "cwd": cwd,
            "process": proc,
            "buffer": "",
            "offset": 0,
            "created_at": utcnow_iso(),
        }
        self._sessions[session_id] = session
        self.audit_logger.append("terminal_open", "terminal session opened", {"session_id": session_id, "cwd": cwd, "pid": proc.pid})

        def pump():
            stream = proc.stdout
            if stream is None:
                return
            for line in iter(stream.readline, ""):
                if not line:
                    break
                with self._lock:
                    if session_id in self._sessions:
                        self._sessions[session_id]["buffer"] += line
                self.audit_logger.append("terminal_output", line.rstrip("\r\n"), {"session_id": session_id, "pid": proc.pid})

        threading.Thread(target=pump, daemon=True).start()
        return {"ok": True, "session_id": session_id, "pid": proc.pid, "cwd": cwd}

    def write(self, session_id: str, data: str) -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return {"ok": False, "error": f"Unknown terminal session: {session_id}"}
        proc = session["process"]
        if proc.stdin is None:
            return {"ok": False, "error": "Terminal stdin is unavailable."}
        proc.stdin.write(data)
        proc.stdin.flush()
        self.audit_logger.append("terminal_input", data[:200], {"session_id": session_id})
        return {"ok": True}

    def read(self, session_id: str) -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return {"ok": False, "error": f"Unknown terminal session: {session_id}"}
        with self._lock:
            offset = session["offset"]
            payload = session["buffer"][offset:]
            session["offset"] = len(session["buffer"])
        return {"ok": True, "output": payload, "session_id": session_id}

    def close(self, session_id: str) -> Dict[str, Any]:
        session = self._sessions.pop(session_id, None)
        if not session:
            return {"ok": False, "error": f"Unknown terminal session: {session_id}"}
        proc = session["process"]
        try:
            proc.terminate()
        except Exception:
            pass
        self.audit_logger.append("terminal_close", "terminal session closed", {"session_id": session_id, "pid": proc.pid})
        return {"ok": True, "session_id": session_id}

    def list(self) -> List[Dict[str, Any]]:
        rows = []
        for session_id, row in self._sessions.items():
            proc = row["process"]
            rows.append(
                {
                    "session_id": session_id,
                    "pid": proc.pid,
                    "cwd": row["cwd"],
                    "created_at": row["created_at"],
                    "returncode": proc.poll(),
                }
            )
        return rows
