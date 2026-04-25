import base64
import hashlib
import json
import platform
from pathlib import Path

from cryptography.fernet import Fernet

from tools import browser


def _config_key() -> str:
    return hashlib.sha256(platform.node().encode()).hexdigest()[:32]


def _fernet() -> Fernet:
    raw = hashlib.sha256(_config_key().encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def _vault_path() -> Path:
    base = Path.home() / ".ai_assistant"
    base.mkdir(parents=True, exist_ok=True)
    return base / "credentials.enc.json"


def save_credential(service: str, username: str, password: str) -> str:
    vault = _vault_path()
    data = {}
    if vault.exists():
        try:
            data = json.loads(vault.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    token = _fernet().encrypt(json.dumps({"username": username, "password": password}).encode()).decode()
    data[service] = token
    vault.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return f"Saved credential for {service}"


def get_credential(service: str):
    vault = _vault_path()
    if not vault.exists():
        return {"error": f"No credentials stored for {service}"}
    try:
        data = json.loads(vault.read_text(encoding="utf-8"))
        token = data[service]
        return json.loads(_fernet().decrypt(token.encode()).decode())
    except Exception as exc:
        return {"error": f"Failed to load credential for {service}: {exc}"}


def login_to_service(service: str, url: str) -> str:
    cred = get_credential(service)
    if "error" in cred:
        return cred["error"]
    browser.navigate(url)
    page = browser._get_page()
    user_selectors = ["input[type='email']", "input[name='email']", "input[name='username']", "input[type='text']"]
    pass_selectors = ["input[type='password']", "input[name='password']"]
    submit_selectors = ["button[type='submit']", "input[type='submit']", "button"]
    for selector in user_selectors:
        if page.locator(selector).count():
            page.locator(selector).first.fill(cred["username"])
            break
    for selector in pass_selectors:
        if page.locator(selector).count():
            page.locator(selector).first.fill(cred["password"])
            break
    for selector in submit_selectors:
        if page.locator(selector).count():
            page.locator(selector).first.click()
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            return f"Submitted login for {service} at {page.url}"
    return f"Filled credentials for {service}, but no submit control was found"

