from typing import Any, Callable, Dict, List


class Tool:
    def __init__(self, name: str, description: str, parameters: dict, fn: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.fn = fn

    def to_groq_definition(self) -> dict:
        properties = {}
        required = []
        for key, value in self.parameters.items():
            schema = dict(value)
            if schema.pop("required", False):
                required.append(key)
            properties[key] = schema
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, name: str, description: str, parameters: dict, fn: Callable):
        self._tools[name] = Tool(name, description, parameters, fn)

    def execute(self, name: str, args: dict) -> str:
        if name not in self._tools:
            return f"Unknown tool: {name}. Available: {list(self._tools.keys())}"
        try:
            result = self._tools[name].fn(**args)
            return str(result) if result is not None else "Done"
        except Exception as exc:
            return f"Tool error ({name}): {exc}"

    def get_tool_definitions(self) -> List[dict]:
        return [tool.to_groq_definition() for tool in self._tools.values()]

    def list_names(self) -> List[str]:
        return list(self._tools.keys())


def build_registry() -> ToolRegistry:
    from core import vision
    from tools import browser, computer_control, filesystem, pc_manager, research, screen_control, shell
    from tools.whatsapp import send_whatsapp
    from skills.computer_control import handler as computer_control_handler
    from skills.universal_runtime import handler as universal_runtime_handler
    from skills.vibe_coder import handler as vibe_coder_handler

    registry = ToolRegistry()
    registry.register(
        "navigate_to",
        "Open URL in browser",
        {"url": {"type": "string", "description": "URL to navigate to", "required": True}},
        browser.navigate,
    )
    registry.register(
        "click_on_screen",
        "Click element by text, selector, or coordinates",
        {"text": {"type": "string"}, "selector": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}},
        browser.click_element,
    )
    registry.register(
        "type_into_field",
        "Type text into a form field",
        {"selector": {"type": "string"}, "text_label": {"type": "string"}, "value": {"type": "string", "required": True}},
        browser.type_into,
    )
    registry.register("read_browser_page", "Get text content of current browser page", {}, browser.get_page_text)
    registry.register("browser_screenshot", "Screenshot current browser page as base64", {}, browser.get_page_screenshot_b64)
    registry.register(
        "research_web",
        "Search web and read pages to get current information",
        {"query": {"type": "string", "description": "Research question", "required": True}, "num_results": {"type": "integer", "description": "Number of results to read"}},
        research.search_and_read,
    )
    registry.register(
        "find_best_approach",
        "Research the best tool/framework/service for a job",
        {"job_description": {"type": "string", "required": True}},
        research.find_best_tool_for_job,
    )
    registry.register("take_screenshot", "Capture current screen state", {}, vision.get_screen_b64)
    registry.register("describe_screen", "Describe what is currently on screen", {}, vision.describe_screen)
    registry.register(
        "find_on_screen",
        "Find UI element on screen and get coordinates",
        {"thing_to_find": {"type": "string", "required": True}},
        vision.find_on_screen,
    )
    registry.register(
        "mouse_click",
        "Click at screen coordinates",
        {"x": {"type": "integer", "required": True}, "y": {"type": "integer", "required": True}},
        screen_control.click_at,
    )
    registry.register("keyboard_type", "Type text using keyboard", {"text": {"type": "string", "required": True}}, screen_control.type_text)
    registry.register("keyboard_shortcut", "Press keyboard shortcut like Ctrl+C, Alt+F4", {"keys": {"type": "string", "required": True}}, screen_control.shortcut)
    registry.register("read_file", "Read file contents", {"path": {"type": "string", "required": True}}, filesystem.read_file)
    registry.register(
        "write_file",
        "Write content to file",
        {"path": {"type": "string", "required": True}, "content": {"type": "string", "required": True}},
        filesystem.write_file,
    )
    registry.register("list_directory", "List files in directory", {"path": {"type": "string", "required": True}}, filesystem.list_dir)
    registry.register("delete_file", "Delete a file or folder", {"path": {"type": "string", "required": True}}, filesystem.delete_path)
    registry.register(
        "search_files",
        "Find files matching pattern",
        {"pattern": {"type": "string", "required": True}, "directory": {"type": "string"}},
        filesystem.search_files,
    )
    registry.register(
        "run_command",
        "Execute terminal/CMD command",
        {"command": {"type": "string", "required": True}, "cwd": {"type": "string"}, "timeout": {"type": "integer"}},
        shell.run,
    )
    registry.register("list_processes", "List running processes", {"filter_name": {"type": "string"}}, pc_manager.list_processes)
    registry.register("kill_process", "Kill a process by name or PID", {"name": {"type": "string"}, "pid": {"type": "integer"}}, pc_manager.kill_process)
    registry.register("get_system_info", "Get CPU, RAM, disk usage", {}, pc_manager.system_info)
    registry.register("clean_pc", "Delete temp files and free up space", {"confirm": {"type": "boolean"}}, pc_manager.clean_temp)
    cc_properties = {
        key: dict(value)
        for key, value in computer_control_handler.TOOL_SCHEMA.get("properties", {}).items()
    }
    for key in computer_control_handler.TOOL_SCHEMA.get("required", []):
        if key in cc_properties:
            cc_properties[key]["required"] = True
    registry.register(
        "computer_control",
        "Perform desktop computer control actions",
        cc_properties,
        computer_control_handler.run,
    )
    vibe_properties = {
        key: dict(value)
        for key, value in vibe_coder_handler.TOOL_SCHEMA.get("properties", {}).items()
    }
    for key in vibe_coder_handler.TOOL_SCHEMA.get("required", []):
        if key in vibe_properties:
            vibe_properties[key]["required"] = True
    registry.register(
        "vibe_coder",
        "Build or migrate projects using local scaffolds and browser-based vibe coding tools",
        vibe_properties,
        vibe_coder_handler.run,
    )
    runtime_properties = {
        key: dict(value)
        for key, value in universal_runtime_handler.TOOL_SCHEMA.get("properties", {}).items()
    }
    for key in universal_runtime_handler.TOOL_SCHEMA.get("required", []):
        if key in runtime_properties:
            runtime_properties[key]["required"] = True
    registry.register(
        "universal_runtime",
        "Operate browsers, browser-based AI tools, and social apps through the shared IMOS runtime session",
        runtime_properties,
        universal_runtime_handler.run,
    )
    registry.register(
        "send_whatsapp",
        "Send a WhatsApp message by finding the contact directly in WhatsApp Desktop or WhatsApp Web",
        {
            "contact_name": {"type": "string", "required": True},
            "message": {"type": "string", "required": True},
        },
        send_whatsapp,
    )
    registry.register("computer_control.click", "Click at screen coordinates", {"x": {"type": "integer", "required": True}, "y": {"type": "integer", "required": True}}, computer_control.click)
    registry.register("computer_control.click_element", "Click an element on screen using an image path", {"image_path": {"type": "string", "required": True}}, computer_control.click_element)
    registry.register("computer_control.type_text", "Type text into the active window", {"text": {"type": "string", "required": True}}, computer_control.type_text)
    registry.register("computer_control.screenshot", "Capture and save a desktop screenshot", {}, computer_control.screenshot)
    registry.register("computer_control.open_app", "Open a desktop application", {"name": {"type": "string", "required": True}}, computer_control.open_app)
    registry.register("computer_control.hover", "Move the pointer to a screen coordinate", {"x": {"type": "integer", "required": True}, "y": {"type": "integer", "required": True}}, computer_control.hover)
    registry.register("computer_control.press_key", "Press a key or key combination", {"key": {"type": "string", "required": True}}, computer_control.press_key)
    registry.register("computer_control.scroll", "Scroll the mouse wheel", {"x": {"type": "integer"}, "y": {"type": "integer"}, "amount": {"type": "integer", "required": True}}, computer_control.scroll)
    registry.register("computer_control.focus_window", "Focus a desktop window by title", {"title": {"type": "string", "required": True}}, computer_control.focus_window)
    registry.register("computer_control.find_on_screen", "Locate an element on screen using an image path", {"image_path": {"type": "string", "required": True}}, computer_control.find_on_screen)
    return registry
