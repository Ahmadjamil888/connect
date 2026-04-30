from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List


@dataclass
class LoadedSkill:
    name: str
    description: str
    schema: Dict[str, Any]
    handler: Any
    directory: Path
    source: str

    def to_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.schema,
        }


class SkillRegistry:
    def __init__(self, workspace_root: Path, bundled_root: Path | None = None, extra_dirs: Iterable[Path] | None = None):
        self.workspace_root = workspace_root
        self.bundled_root = bundled_root or (Path.cwd() / "skills")
        self.extra_dirs = [Path(item) for item in (extra_dirs or [])]

    def search_roots(self) -> List[tuple[str, Path]]:
        home = Path.home()
        roots = [
            ("extra", path) for path in self.extra_dirs
        ] + [
            ("bundled", self.bundled_root),
            ("managed", home / ".connectai" / "skills"),
            ("personal_agents", home / ".agents" / "skills"),
            ("project_agents", self.workspace_root / ".agents" / "skills"),
            ("workspace", self.workspace_root / "skills"),
        ]
        return roots

    def _load_handler_module(self, name: str, handler_path: Path):
        spec = importlib.util.spec_from_file_location(f"connectai_skill_{name}_{abs(hash(str(handler_path)))}", handler_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load skill handler: {handler_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _load_skill(self, source: str, directory: Path) -> LoadedSkill | None:
        skill_md = directory / "SKILL.md"
        handler_py = directory / "handler.py"
        if not skill_md.exists() or not handler_py.exists():
            return None
        module = self._load_handler_module(directory.name, handler_py)
        description = skill_md.read_text(encoding="utf-8").strip()
        schema = getattr(module, "TOOL_SCHEMA", {"type": "object", "properties": {}})
        handler = getattr(module, "run")
        return LoadedSkill(
            name=directory.name,
            description=description.splitlines()[0].lstrip("# ").strip() or directory.name,
            schema=schema,
            handler=handler,
            directory=directory,
            source=source,
        )

    def load_all(self) -> List[LoadedSkill]:
        loaded: Dict[str, LoadedSkill] = {}
        for source, root in self.search_roots():
            if not root.exists() or not root.is_dir():
                continue
            for directory in sorted(root.iterdir()):
                if not directory.is_dir():
                    continue
                skill = self._load_skill(source, directory)
                if skill is None:
                    continue
                loaded[skill.name] = skill
        return sorted(loaded.values(), key=lambda item: item.name)
