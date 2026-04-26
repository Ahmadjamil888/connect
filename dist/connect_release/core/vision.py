import base64
import io
import json
import os

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageGrab


load_dotenv()
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
FALLBACK_VISION_MODEL = "llama-3.2-11b-vision-preview"


def _get_client():
    try:
        from groq import Groq
    except ModuleNotFoundError as exc:
        raise RuntimeError("vision unavailable: missing dependency 'groq'") from exc
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("vision unavailable: GROQ_API_KEY is not configured")
    return Groq(api_key=api_key)


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
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{screen_b64}"},
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
    ]
    try:
        response = client.chat.completions.create(model=VISION_MODEL, messages=messages, max_tokens=500)
        return response.choices[0].message.content
    except Exception as exc:
        try:
            fallback = client.chat.completions.create(
                model=FALLBACK_VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "A screen image was captured but the preferred vision model is unavailable. "
                            f"Return a concise fallback note. Error: {exc}"
                        ),
                    }
                ],
                max_tokens=200,
            )
            return fallback.choices[0].message.content
        except Exception:
            return f"Screen description unavailable: {exc}"


def find_on_screen(thing_to_find: str) -> dict:
    screen_b64 = get_screen_b64()
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{screen_b64}"},
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
            max_tokens=200,
        )
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except Exception:
            return {"found": False, "description": content}
    except Exception as exc:
        return {"found": False, "description": f"Vision lookup unavailable: {exc}"}
