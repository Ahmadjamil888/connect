import os
from typing import Callable

import requests
from dotenv import load_dotenv

load_dotenv()

try:
    import anthropic
except Exception:
    anthropic = None

try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    from groq import Groq
except Exception:
    Groq = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-5",
    "openai": "gpt-4o",
    "openrouter": "openai/gpt-4o",
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-1.5-pro",
    "ollama": "llama3.2",
    "huggingface": "meta-llama/Meta-Llama-3-8B-Instruct",
}

PROVIDER_ORDER = [
    "anthropic",
    "openai",
    "openrouter",
    "groq",
    "gemini",
    "ollama",
    "huggingface",
]


def _normalize_messages(messages: list[dict], system: str) -> tuple[list[dict], str]:
    normalized_messages = []
    system_prompt = system.strip()

    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            content = "\n".join(parts)
        else:
            content = str(content)

        if role == "system":
            system_prompt = f"{system_prompt}\n\n{content}".strip()
            continue

        normalized_messages.append({"role": role, "content": content})

    return normalized_messages, system_prompt


def _provider_is_configured(provider: str) -> bool:
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY")) and anthropic is not None
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None
    if provider == "openrouter":
        return bool(os.getenv("OPENROUTER_API_KEY")) and OpenAI is not None
    if provider == "groq":
        return bool(os.getenv("GROQ_API_KEY")) and Groq is not None
    if provider == "gemini":
        return bool(os.getenv("GOOGLE_GEMINI_API_KEY")) and genai is not None
    if provider == "ollama":
        return True
    if provider == "huggingface":
        return bool(os.getenv("HUGGINGFACE_API_KEY"))
    return False


def _build_provider_chain() -> list[str]:
    selected = os.getenv("AI_PROVIDER", "groq").strip().lower() or "groq"
    ordered = [selected] + [provider for provider in PROVIDER_ORDER if provider != selected]
    return [provider for provider in ordered if _provider_is_configured(provider)]


def _message_text_from_openai_response(response) -> str:
    text = getattr(response.choices[0].message, "content", "")
    if isinstance(text, list):
        parts = []
        for item in text:
            if hasattr(item, "text"):
                parts.append(item.text)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(text).strip()


def _call_anthropic(messages: list[dict], system: str) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODELS["anthropic"]),
        system=system,
        max_tokens=4096,
        messages=messages,
    )
    return "".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip()


def _call_openai_compatible(
    messages: list[dict],
    system: str,
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> str:
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, *messages],
    )
    return _message_text_from_openai_response(response)


def _call_openai(messages: list[dict], system: str) -> str:
    return _call_openai_compatible(
        messages=messages,
        system=system,
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=os.getenv("OPENAI_MODEL", DEFAULT_MODELS["openai"]),
    )


def _call_openrouter(messages: list[dict], system: str) -> str:
    return _call_openai_compatible(
        messages=messages,
        system=system,
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        model=os.getenv("OPENROUTER_MODEL", DEFAULT_MODELS["openrouter"]),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )


def _call_groq(messages: list[dict], system: str) -> str:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", DEFAULT_MODELS["groq"]),
        messages=[{"role": "system", "content": system}, *messages],
    )
    return str(response.choices[0].message.content).strip()


def _call_gemini(messages: list[dict], system: str) -> str:
    genai.configure(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))
    model = genai.GenerativeModel(
        model_name=os.getenv("GOOGLE_GEMINI_MODEL", DEFAULT_MODELS["gemini"]),
        system_instruction=system,
    )
    prompt_parts = []
    for message in messages:
        prompt_parts.append(f"{message['role'].upper()}:\n{message['content']}")
    prompt_parts.append("ASSISTANT:")
    response = model.generate_content("\n\n".join(prompt_parts))
    return str(response.text).strip()


def _call_ollama(messages: list[dict], system: str) -> str:
    payload = {
        "model": os.getenv("OLLAMA_MODEL", DEFAULT_MODELS["ollama"]),
        "stream": False,
        "messages": [{"role": "system", "content": system}, *messages],
    }
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    response = requests.post(f"{host}/api/chat", json=payload, timeout=180)
    response.raise_for_status()
    data = response.json()
    return str(data.get("message", {}).get("content", "")).strip()


def _call_huggingface(messages: list[dict], system: str) -> str:
    headers = {
        "Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_KEY', '')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": os.getenv("HUGGINGFACE_MODEL", DEFAULT_MODELS["huggingface"]),
        "messages": [{"role": "system", "content": system}, *messages],
        "max_tokens": 4096,
    }
    response = requests.post(
        os.getenv("HUGGINGFACE_BASE_URL", "https://router.huggingface.co/v1/chat/completions"),
        headers=headers,
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    return str(data["choices"][0]["message"]["content"]).strip()


PROVIDER_CALLS: dict[str, Callable[[list[dict], str], str]] = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "openrouter": _call_openrouter,
    "groq": _call_groq,
    "gemini": _call_gemini,
    "ollama": _call_ollama,
    "huggingface": _call_huggingface,
}


def get_response(messages: list[dict], system: str) -> str:
    normalized_messages, normalized_system = _normalize_messages(messages, system)
    provider_chain = _build_provider_chain()
    failures = []

    if not provider_chain:
        raise RuntimeError("No AI providers are configured.")

    for provider in provider_chain:
        try:
            return PROVIDER_CALLS[provider](normalized_messages, normalized_system)
        except Exception as error:
            failures.append(f"{provider}: {error}")

    raise RuntimeError("All providers failed. " + " | ".join(failures))
