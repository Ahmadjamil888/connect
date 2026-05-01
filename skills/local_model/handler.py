"""
IMOS Local Model Connector.
Manage Ollama, LM Studio, and any OpenAI-compatible local endpoint.
"""
from __future__ import annotations

import subprocess
import os
import requests

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "list_ollama",
                "pull_ollama",
                "start_ollama",
                "test_endpoint",
                "set_active",
                "list_lmstudio",
                "status",
            ],
        },
        "model_name": {"type": "string"},
        "endpoint": {"type": "string"},
        "api_key": {"type": "string"},
    },
    "required": ["action"],
}

OLLAMA_BASE = "http://localhost:11434"
LMSTUDIO_BASE = "http://localhost:1234"


def _ollama_running() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _lmstudio_running() -> bool:
    try:
        r = requests.get(f"{LMSTUDIO_BASE}/v1/models", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def run(inputs, **_kwargs):
    action = str(inputs.get("action", "status")).strip().lower()

    if action == "status":
        ollama_ok = _ollama_running()
        lmstudio_ok = _lmstudio_running()
        models = []
        if ollama_ok:
            try:
                r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
                models = [m["name"] for m in r.json().get("models", [])]
            except Exception:
                pass
        return {
            "ok": True,
            "ollama": {"running": ollama_ok, "endpoint": OLLAMA_BASE, "models": models},
            "lmstudio": {"running": lmstudio_ok, "endpoint": LMSTUDIO_BASE},
        }

    if action == "list_ollama":
        if not _ollama_running():
            return {"ok": False, "error": "Ollama is not running. Start it with: ollama serve"}
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=10)
        models = r.json().get("models", [])
        return {
            "ok": True,
            "models": [{"name": m["name"], "size": m.get("size", 0)} for m in models],
        }

    if action == "pull_ollama":
        model_name = str(inputs.get("model_name", "")).strip()
        if not model_name:
            return {"ok": False, "error": "model_name is required"}
        r = subprocess.run(f"ollama pull {model_name}", shell=True, capture_output=True, text=True, timeout=600)
        return {"ok": r.returncode == 0, "output": (r.stdout + r.stderr)[-2000:]}

    if action == "start_ollama":
        subprocess.Popen("ollama serve", shell=True)
        import time; time.sleep(2)
        return {"ok": _ollama_running(), "message": "Ollama started" if _ollama_running() else "Ollama failed to start"}

    if action == "test_endpoint":
        endpoint = str(inputs.get("endpoint", OLLAMA_BASE)).strip()
        api_key = str(inputs.get("api_key", "")).strip() or "ollama"
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            r = requests.get(f"{endpoint}/v1/models", headers=headers, timeout=5)
            if r.status_code == 200:
                models = [m["id"] for m in r.json().get("data", [])]
                return {"ok": True, "endpoint": endpoint, "models": models}
            return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if action == "set_active":
        model_name = str(inputs.get("model_name", "")).strip()
        endpoint = str(inputs.get("endpoint", OLLAMA_BASE)).strip()
        api_key = str(inputs.get("api_key", "ollama")).strip() or "ollama"
        if not model_name:
            return {"ok": False, "error": "model_name is required"}
        try:
            from config.config import save_model_config
            save_model_config({
                "provider": "ollama",
                "model": model_name,
                "base_url": endpoint,
                "api_key": api_key,
            })
            return {"ok": True, "message": f"Active model set to {model_name} at {endpoint}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if action == "list_lmstudio":
        if not _lmstudio_running():
            return {"ok": False, "error": "LM Studio server not running. Start it from LM Studio app."}
        r = requests.get(f"{LMSTUDIO_BASE}/v1/models", timeout=5)
        models = [m["id"] for m in r.json().get("data", [])]
        return {"ok": True, "models": models, "endpoint": LMSTUDIO_BASE}

    return {"ok": False, "error": f"Unknown action: {action}"}
