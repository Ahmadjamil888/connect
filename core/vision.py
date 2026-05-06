import base64
import io
import json
import os
import re
from urllib.parse import urlparse

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageGrab


load_dotenv()
VISION_MODEL = "claude-sonnet-4-5"
VISION_MODELS = {
    "groq": "llama-3.2-90b-vision-preview",
    "openai": "gpt-4o",
    "anthropic": "claude-3-5-sonnet-20241022",
    "gemini": "gemini-2.0-flash",
    "openrouter": "openai/gpt-4o",
}


def _get_client():
    try:
        import anthropic
    except ModuleNotFoundError as exc:
        raise RuntimeError("vision unavailable: missing dependency 'anthropic'") from exc
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("vision unavailable: ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=api_key)


def get_screen_b64() -> str:
    """Capture the full screen and return a compact base64 PNG."""
    try:
        screenshot = ImageGrab.grab()
    except Exception as exc:
        screenshot = Image.new("RGB", (1280, 720), color=(24, 24, 24))
        draw = ImageDraw.Draw(screenshot)
        draw.text((40, 40), f"Screen capture unavailable: {exc}", fill=(255, 255, 255))
    screenshot = screenshot.resize((1280, 720))
    buf = io.BytesIO()
    screenshot.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def describe_screen() -> str:
    screen_b64 = get_screen_b64()
    client = _get_client()
    try:
        response = client.messages.create(
            model=VISION_MODEL,
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screen_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Describe what is on screen right now. Include the active window, visible text, "
                                "buttons, inputs, and the current UI state. Be specific."
                            ),
                        },
                    ],
                }
            ],
        )
        return "".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip()
    except Exception as exc:
        return f"Screen description unavailable: {exc}"


def find_on_screen(thing_to_find: str) -> dict:
    screen_b64 = get_screen_b64()
    client = _get_client()
    try:
        response = client.messages.create(
            model=VISION_MODEL,
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screen_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                f'Find: "{thing_to_find}" on screen.\n'
                                'If found, respond with JSON only: {"found": true, "x": <x_coordinate>, '
                                '"y": <y_coordinate>, "description": "<what you see>"}\n'
                                'If not found: {"found": false, "description": "<what is on screen instead>"}'
                            ),
                        },
                    ],
                }
            ],
        )
        content = "".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip()
        try:
            return json.loads(content)
        except Exception:
            return {"found": False, "description": content}
    except Exception as exc:
        return {"found": False, "description": f"Vision lookup unavailable: {exc}"}


def _find_provider_by_type(ptype: str) -> dict | None:
    from core import model_manager

    for provider in model_manager.load_providers():
        if str(provider.get("type", "")).strip().lower() == ptype and provider.get("enabled", True):
            return provider
    return None


def _call_vision(provider: dict, vision_model: str, image_path: str, prompt: str) -> str:
    if not os.path.exists(image_path):
        return "UNKNOWN"
    if os.path.getsize(image_path) < 1000:
        return "UNKNOWN"
    with open(image_path, "rb") as handle:
        b64 = base64.b64encode(handle.read()).decode()
    ptype = str(provider.get("type", "groq")).strip().lower() or "groq"
    try:
        if ptype == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=provider["api_key"])
            message = client.messages.create(
                model=vision_model,
                max_tokens=50,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
            return "".join(block.text for block in message.content if getattr(block, "type", "") == "text").strip()
        if ptype in {"openai", "groq", "openrouter"}:
            from openai import OpenAI

            base_url = provider.get("base_url") or "https://api.openai.com/v1"
            client = OpenAI(api_key=provider["api_key"], base_url=base_url)
            response = client.chat.completions.create(
                model=vision_model,
                max_tokens=50,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
            return str(response.choices[0].message.content or "").strip()
        if ptype == "gemini":
            import google.generativeai as genai

            genai.configure(api_key=provider["api_key"])
            model = genai.GenerativeModel(vision_model)
            image = Image.open(image_path)
            response = model.generate_content([prompt, image])
            return str(response.text or "").strip()
    except Exception:
        return "UNKNOWN"
    return "UNKNOWN"


def _browser_domain_fallback(prompt: str) -> str:
    lowered = str(prompt or "").lower()
    if not any(term in lowered for term in ["website", "domain", "url", "address bar"]):
        return "UNKNOWN"
    try:
        import pyperclip
        from tools.computer_control import press_key
        import time

        press_key("ctrl+l")
        time.sleep(0.2)
        press_key("ctrl+c")
        time.sleep(0.2)
        value = str(pyperclip.paste() or "").strip()
        press_key("escape")
        if not value:
            return "UNKNOWN"
        parsed = urlparse(value if "://" in value else f"https://{value}")
        domain = parsed.netloc or parsed.path
        return domain or "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def ask_vision(image_path: str, prompt: str) -> str:
    from core import model_manager

    provider = model_manager.get_default()
    if not provider:
        return "UNKNOWN"
    ptype = str(provider.get("type", "groq")).strip().lower() or "groq"
    vision_model = VISION_MODELS.get(ptype)
    if vision_model:
        result = _call_vision(provider, vision_model, image_path, prompt)
        if result and result.strip().upper() != "UNKNOWN":
            return result
    for fallback_type, fallback_model in VISION_MODELS.items():
        fallback = _find_provider_by_type(fallback_type)
        if fallback:
            result = _call_vision(fallback, fallback_model, image_path, prompt)
            if result and result.strip().upper() != "UNKNOWN":
                return result
    return _browser_domain_fallback(prompt)


def ask_vision_coordinates(image_path: str, prompt: str) -> dict | None:
    result = ask_vision(image_path, prompt)
    patterns = [
        r"\(?\s*(\d{2,4})\s*,\s*(\d{2,4})\s*\)?",
        r"x\s*[=:]\s*(\d{2,4}).*?y\s*[=:]\s*(\d{2,4})",
        r"(\d{2,4})\s+(\d{2,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, result, re.IGNORECASE)
        if not match:
            continue
        x, y = int(match.group(1)), int(match.group(2))
        try:
            import pyautogui

            sw, sh = pyautogui.size()
            if 0 < x < sw and 0 < y < sh:
                return {"x": x, "y": y}
        except Exception:
            if 0 < x < 3840 and 0 < y < 2160:
                return {"x": x, "y": y}
    return None
