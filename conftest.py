import time
import urllib.request
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent

os.environ.setdefault("IMOS_AUTO_CONSENT", "agree")


@pytest.fixture(scope="session")
def dashboard_base_url():
    from ai_assistant import build_gateway
    from config.config import load_config

    cfg = load_config()
    workspace = cfg.get("workspace", str(ROOT))
    build_gateway(workspace)
    url = "http://127.0.0.1:8766"
    for _ in range(30):
        try:
            with urllib.request.urlopen(url + "/api/status", timeout=2) as response:
                if int(getattr(response, "status", 0)) == 200:
                    return url
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"Dashboard server did not become ready at {url}")
