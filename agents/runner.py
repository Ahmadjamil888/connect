import json
from rich.console import Console

from config.config import get_client
from tools.definitions import TOOLS
from tools.executor import execute_tool

console = Console(highlight=False)

AGENT_PERSONAS = {
    "coder":      "You are an expert software engineer. Write complete working code. Run it. Fix all errors. Never leave TODOs.",
    "designer":   "You are a senior UI/UX designer and frontend developer. Build complete visually polished HTML/CSS/JS. Test by reading files back.",
    "researcher": "You are a research analyst. Search thoroughly. Synthesize findings with sources. Save results to files.",
    "devops":     "You are a DevOps engineer. Set up infrastructure fully. Deploy completely. Verify by checking output URLs.",
    "browser":    "You are a browser automation expert. Navigate, interact, extract data precisely.",
}

AGENT_TOOLS = {
    "coder":      ["bash", "write_file", "read_file", "list_dir", "web_search"],
    "designer":   ["write_file", "read_file", "list_dir", "web_search", "browser_action"],
    "researcher": ["web_search", "browser_action", "write_file", "read_file"],
    "devops":     ["bash", "write_file", "read_file", "deploy_vercel", "deploy_netlify", "github_push"],
    "browser":    ["browser_action", "write_file", "read_file"],
}


def spawn_agent(agent_type, task, context, workspace, model_config) -> str:
    client = get_client(model_config)
    provider = model_config.get("provider", "anthropic")
    model = model_config.get("model", "claude-opus-4-5")
    allowed_tools = [t for t in TOOLS if t["name"] in AGENT_TOOLS[agent_type]]
    system = AGENT_PERSONAS[agent_type]
    if context:
        system += f"\n\nContext:\n{context}"
    messages = [{"role": "user", "content": f"Task: {task}\nWorkspace: {workspace}"}]
    last_text = ""

    for _ in range(30):
        if provider in ("anthropic", "gcp"):
            with client.messages.stream(
                model=model, max_tokens=8192, system=system,
                tools=allowed_tools, messages=messages,
            ) as stream:
                for event in stream:
                    etype = type(event).__name__
                    if etype == "RawContentBlockDeltaEvent":
                        d = event.delta
                        if hasattr(d, "text") and d.text:
                            console.print(f"  [{agent_type}] {d.text}", end="")
                final = stream.get_final_message()
            console.print()
            content = final.content
            stop_reason = final.stop_reason
            tool_calls = [b for b in content if getattr(b, "type", None) == "tool_use"]
            text_blocks = [b.text for b in content if getattr(b, "type", None) == "text"]
            last_text = " ".join(text_blocks)
        else:
            from openai import OpenAI
            oai_msgs = [{"role": "system", "content": system}] + [{"role": m["role"], "content": m.get("content", "")} for m in messages]
            oai_tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in allowed_tools]
            stream = client.chat.completions.create(model=model, messages=oai_msgs, tools=oai_tools, stream=True, max_tokens=8192)
            full_text = ""
            tool_calls = []
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    console.print(delta.content, end="")
                    full_text += delta.content
            console.print()
            last_text = full_text
            stop_reason = "end_turn"

        if stop_reason == "end_turn" or not tool_calls:
            break

        tool_results = []
        for block in tool_calls:
            result = execute_tool(block.name, block.input, workspace, model_config)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(result)})

        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": tool_results})

    return last_text or "Agent completed."
