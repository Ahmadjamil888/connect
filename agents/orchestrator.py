import json
from rich.console import Console
from rich.theme import Theme

from config.config import get_client
from tools.definitions import TOOLS
from tools.executor import execute_tool

theme = Theme({
    "agent": "bright_cyan",
    "tool":  "bright_yellow",
    "result":"dim white",
    "error": "bright_red",
    "done":  "bright_green",
    "label": "bold bright_white",
})
console = Console(theme=theme, highlight=False, markup=True)

SYSTEM = """You are Connect AI  a fully autonomous agent that controls a real computer and builds complete software products from scratch. You have access to:
- bash: run any shell command
- write_file / read_file / list_dir: full filesystem access  
- browser_action: control a real Chromium browser
- web_search: search the internet
- deploy_vercel / deploy_netlify: deploy to production
- github_push: commit and push code
- spawn_agent: delegate to specialist sub-agents (coder, designer, researcher, devops, browser)

Behave like an expert engineer who just sat down at a keyboard. Start working immediately. Never print a plan or numbered steps before acting  just act. Think out loud in short sentences as you go. Use tools in parallel when it makes sense. When something fails, diagnose it and try a different approach without asking. When completely finished, say DONE and give a one-paragraph summary of what was built and any live URLs."""


def _run_anthropic(client, model, messages, workspace, model_config):
    tool_calls_pending = []
    try:
        with client.messages.stream(
            model=model,
            max_tokens=8192,
            system=SYSTEM + f"\n\nWorkspace: {workspace}",
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for event in stream:
                etype = type(event).__name__
                if etype == "RawContentBlockDeltaEvent":
                    d = event.delta
                    if hasattr(d, "text") and d.text:
                        console.print(d.text, end="", style="agent")
            final = stream.get_final_message()
        console.print()
        for block in final.content:
            if getattr(block, "type", None) == "tool_use":
                tool_calls_pending.append(block)
        return final.content, final.stop_reason, tool_calls_pending
    except ValueError as e:
        console.print(f"\n[error]{e}[/error]")
        console.print("[error]Run /setup to configure your API key.[/error]")
        return [], "end_turn", []
    except Exception as e:
        console.print(f"\n[error]API error: {e}[/error]")
        return [], "end_turn", []


def _run_openai_compat(client, model, messages, workspace, model_config):
    import openai

    oai_msgs = [{"role": "system", "content": SYSTEM + f"\n\nWorkspace: {workspace}"}]
    for m in messages:
        if isinstance(m.get("content"), list):
            parts = []
            for block in m["content"]:
                if isinstance(block, dict):
                    if block.get("type") == "tool_result":
                        parts.append({"role": "tool", "tool_call_id": block["tool_use_id"], "content": block["content"]})
                    elif block.get("type") == "text":
                        parts.append({"role": m["role"], "content": block["text"]})
            oai_msgs.extend(parts)
        else:
            oai_msgs.append({"role": m["role"], "content": m.get("content", "")})

    oai_tools = []
    for t in TOOLS:
        oai_tools.append({"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}})

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=oai_msgs,
            tools=oai_tools,
            stream=True,
            max_tokens=8192,
        )
    except openai.RateLimitError as e:
        message = str(e)
        if "retry in" in message.lower():
            retry_hint = message[message.lower().find("retry in"):]
            console.print(f"\n[error]Quota exceeded for {model}.[/error]")
            console.print(f"[error]{retry_hint}[/error]")
        else:
            console.print(f"\n[error]Quota exceeded for {model}. Check billing or rate limits.[/error]")
        console.print("[error]Use /setup or /use to switch providers, or wait for quota reset.[/error]")
        return [], "end_turn", []
    except Exception as e:
        console.print(f"\n[error]API error: {e}[/error]")
        return [], "end_turn", []

    full_text = ""
    tool_calls_raw = {}

    try:
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue
            if delta.content:
                console.print(delta.content, end="", style="agent")
                full_text += delta.content
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_raw:
                        tool_calls_raw[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls_raw[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_raw[idx]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_raw[idx]["arguments"] += tc.function.arguments
    except openai.RateLimitError as e:
        console.print(f"\n[error]Quota exceeded while streaming response: {e}[/error]")
        console.print("[error]Use /setup or /use to switch providers, or wait for quota reset.[/error]")
        return [], "end_turn", []
    except Exception as e:
        console.print(f"\n[error]Streaming error: {e}[/error]")
        return [], "end_turn", []

    console.print()

    class FakeBlock:
        def __init__(self, id, name, input):
            self.type = "tool_use"
            self.id = id
            self.name = name
            self.input = input

    class FakeText:
        def __init__(self, text):
            self.type = "text"
            self.text = text

    content = [FakeText(full_text)] if full_text else []
    tool_calls_pending = []

    for tc in tool_calls_raw.values():
        try:
            inp = json.loads(tc["arguments"]) if tc["arguments"] else {}
        except Exception:
            inp = {}
        fb = FakeBlock(tc["id"], tc["name"], inp)
        content.append(fb)
        tool_calls_pending.append(fb)

    stop_reason = "tool_use" if tool_calls_pending else "end_turn"
    return content, stop_reason, tool_calls_pending


def _run_bedrock(client, model, messages, workspace, model_config):
    import json as _json

    bedrock_msgs = []
    for m in messages:
        role = m["role"]
        content = m.get("content", "")
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    parts.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": block["tool_use_id"], "content": block["content"]}]})
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append({"role": role, "content": [{"type": "text", "text": block["text"]}]})
            bedrock_msgs.extend(parts)
        else:
            bedrock_msgs.append({"role": role, "content": [{"type": "text", "text": str(content)}]})

    body = _json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8192,
        "system": SYSTEM + f"\n\nWorkspace: {workspace}",
        "messages": bedrock_msgs,
        "tools": TOOLS,
    })

    response = client.invoke_model_with_response_stream(modelId=model, body=body)
    full_text = ""
    tool_calls_pending = []

    for event in response["body"]:
        chunk = _json.loads(event["chunk"]["bytes"])
        if chunk.get("type") == "content_block_delta":
            text = chunk.get("delta", {}).get("text", "")
            if text:
                console.print(text, end="", style="agent")
                full_text += text

    console.print()

    class FakeText:
        def __init__(self, text):
            self.type = "text"
            self.text = text

    return [FakeText(full_text)], "end_turn", tool_calls_pending


def run_orchestrator(goal: str, model_config: dict, workspace: str):
    client = get_client(model_config)
    provider = model_config.get("provider", "anthropic")
    model = model_config.get("model", "claude-opus-4-5")
    messages = [{"role": "user", "content": goal}]

    for iteration in range(50):
        if provider == "anthropic" or provider == "gcp":
            content, stop_reason, tool_calls = _run_anthropic(client, model, messages, workspace, model_config)
        elif provider == "bedrock":
            content, stop_reason, tool_calls = _run_bedrock(client, model, messages, workspace, model_config)
        else:
            content, stop_reason, tool_calls = _run_openai_compat(client, model, messages, workspace, model_config)

        if stop_reason == "end_turn" or not tool_calls:
            break

        tool_results = []
        for block in tool_calls:
            console.print(f"\n[tool] {block.name}[/tool] [result]{json.dumps(block.input)[:120]}[/result]")
            result = execute_tool(block.name, block.input, workspace, model_config)
            preview = str(result)[:300]
            console.print(f"[result]   {preview}[/result]")
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(result)})

        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": tool_results})

    console.print("\n[done] Done[/done]")
