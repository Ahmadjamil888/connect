from __future__ import annotations

from tools.email_manager import send_email

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "to": {"type": "string"},
        "subject": {"type": "string"},
        "body": {"type": "string"},
        "from_addr": {"type": "string"},
    },
    "required": ["to", "subject", "body"],
}


def run(inputs, **_kwargs):
    return send_email(
        to=str(inputs["to"]),
        subject=str(inputs["subject"]),
        body=str(inputs["body"]),
        from_addr=str(inputs.get("from_addr", "")) or None,
    )
