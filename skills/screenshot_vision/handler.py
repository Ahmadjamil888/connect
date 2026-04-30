from __future__ import annotations

import base64
import io
from pathlib import Path

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "monitor_index": {"type": "integer"},
        "analyze": {"type": "boolean"},
    },
}


def _capture_png_b64(monitor_index: int = 1):
    import mss
    from PIL import Image

    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        shot = sct.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        if image.width > 1280:
            ratio = 1280 / image.width
            image = image.resize((1280, int(image.height * ratio)), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue(), base64.standard_b64encode(buffer.getvalue()).decode()


def _analyze_with_anthropic(question: str, image_b64: str, model_config: dict):
    import anthropic

    client = anthropic.Anthropic(api_key=model_config.get("api_key", ""))
    response = client.messages.create(
        model=model_config.get("model", "claude-sonnet-4-5"),
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": question},
            ],
        }],
    )
    return response.content[0].text


def run(inputs, *, workspace: str, model_config: dict, **_kwargs):
    monitor_index = int(inputs.get("monitor_index", 1) or 1)
    question = str(inputs.get("question", "Describe the current screen and any visible errors.")).strip()
    analyze = bool(inputs.get("analyze", True))
    png_bytes, image_b64 = _capture_png_b64(monitor_index)
    path = Path(workspace) / "connectai_screenshot.png"
    path.write_bytes(png_bytes)
    payload = {"ok": True, "path": str(path), "bytes": len(png_bytes)}
    if analyze:
        provider = str(model_config.get("provider", "")).strip().lower()
        if provider == "anthropic":
            payload["analysis"] = _analyze_with_anthropic(question, image_b64, model_config)
        else:
            payload["analysis"] = "Screenshot captured. Vision analysis is currently implemented for Anthropic-compatible image inputs."
    return payload
