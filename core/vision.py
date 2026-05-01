import base64
import io
import json
import os

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageGrab


load_dotenv()
VISION_MODEL = "claude-sonnet-4-5"


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
