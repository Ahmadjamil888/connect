TOOLS = [
    {
        "name": "bash",
        "description": "Run any shell command on the user's machine.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a file from disk.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files and directories in a path.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web for current information.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "browser_action",
        "description": "Control the browser: navigate, click, type, screenshot, or get HTML.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["navigate", "click", "type", "screenshot", "get_html"],
                },
                "url": {"type": "string"},
                "selector": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "deploy_vercel",
        "description": "Deploy the current project to Vercel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string"},
                "project_name": {"type": "string"},
            },
            "required": ["project_dir"],
        },
    },
    {
        "name": "deploy_netlify",
        "description": "Deploy a static site to Netlify.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dist_dir": {"type": "string"},
                "site_name": {"type": "string"},
            },
            "required": ["dist_dir"],
        },
    },
    {
        "name": "github_push",
        "description": "Commit and push local changes to GitHub.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_dir": {"type": "string"},
                "commit_message": {"type": "string"},
            },
            "required": ["repo_dir", "commit_message"],
        },
    },
    {
        "name": "spawn_agent",
        "description": "Spawn a specialist sub-agent to handle a task autonomously.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "enum": ["coder", "designer", "researcher", "devops", "browser"],
                },
                "task": {"type": "string"},
                "context": {"type": "string"},
            },
            "required": ["agent_type", "task"],
        },
    },
]
