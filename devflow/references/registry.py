from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml as _yaml

    _YAML_AVAILABLE = True
except ImportError:
    _yaml = None
    _YAML_AVAILABLE = False


class ReferenceRegistry:
    def __init__(self, references_dir: Path | str | None = None) -> None:
        if references_dir is None:
            self._dir = Path(__file__).parent
        else:
            self._dir = Path(references_dir)

        self._index: dict[str, dict[str, Any]] = {}
        self._cache: dict[str, str] = {}

        if self._dir.exists() and any(self._dir.glob("*.md")):
            self._build_index()

    def _build_index(self) -> None:
        for file_path in sorted(self._dir.glob("*.md")):
            meta = self._parse_front_matter(file_path)
            if meta is None or "name" not in meta:
                continue

            name = meta["name"]
            front_matter_text = file_path.read_text(encoding="utf-8-sig")
            fm_match = re.match(r"^---\s*\n(.*?)\n---", front_matter_text, re.DOTALL)
            fm_size = fm_match.end() if fm_match else 0
            char_count = max(0, len(front_matter_text) - fm_size)

            meta["file_path"] = file_path
            meta["char_count"] = char_count
            meta.setdefault("title", name)
            meta.setdefault("description", "")
            meta.setdefault("tags", [])
            meta.setdefault("version", "1.0")
            meta.setdefault("applicable_stages", [])
            meta.setdefault("priority", 0)

            self._index[name] = meta

    def get_document(
        self,
        name: str,
        section: str | None = None,
        max_chars: int = 2000,
    ) -> dict[str, Any] | None:
        if name not in self._index:
            return None

        content = self._load_content(name)

        if section is not None:
            content = self._extract_section(content, section)

        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n... (截断，如需特定章节请指定 section 参数)"

        return {
            "name": name,
            "title": self._index[name].get("title", name),
            "content": content,
        }

    def get_documents_for_stage(
        self,
        stage_name: str,
        max_total_chars: int = 4000,
    ) -> list[dict[str, Any]]:
        matched = [
            (meta["name"], meta.get("priority", 0))
            for meta in self._index.values()
            if stage_name in meta.get("applicable_stages", [])
        ]
        matched.sort(key=lambda x: x[1], reverse=True)

        results: list[dict[str, Any]] = []
        total_chars = 0

        for name, _ in matched:
            remaining = max_total_chars - total_chars
            if remaining <= 0:
                break

            doc = self.get_document(name, max_chars=remaining)
            if doc is None:
                continue

            total_chars += len(doc["content"])
            results.append(doc)

        return results

    def _extract_section(self, content: str, section_name: str) -> str:
        sections = re.split(r"^## ", content, flags=re.MULTILINE)
        target_lower = section_name.lower()

        for section in sections[1:]:
            lines = section.split("\n", 1)
            heading = lines[0].strip().lower()
            if target_lower in heading:
                return "## " + section

        return ""

    def _parse_front_matter(self, file_path: Path) -> dict[str, Any] | None:
        try:
            text = file_path.read_text(encoding="utf-8-sig")
        except OSError:
            return None

        match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not match:
            return None

        raw = match.group(1)

        if _YAML_AVAILABLE and _yaml is not None:
            try:
                result = _yaml.safe_load(raw)
                if isinstance(result, dict):
                    return result
                return None
            except Exception:
                return None

        return self._parse_simple_yaml(raw)

    @staticmethod
    def _parse_simple_yaml(raw: str) -> dict[str, Any] | None:
        result: dict[str, Any] = {}
        current_list_key: str | None = None
        current_list: list[str] = []

        for line in raw.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            list_item_match = re.match(r"^\s*-\s+(.+)$", stripped)
            if list_item_match:
                if current_list_key is not None:
                    current_list.append(list_item_match.group(1).strip())
                continue

            kv_match = re.match(r"^(\w[\w_]*)\s*:\s*(.*)$", stripped)
            if kv_match:
                if current_list_key is not None:
                    result[current_list_key] = current_list
                    current_list_key = None
                    current_list = []

                key = kv_match.group(1)
                value = kv_match.group(2).strip()

                if value == "":
                    current_list_key = key
                    current_list = []
                else:
                    if value.lower() in ("true", "false"):
                        result[key] = value.lower() == "true"
                    else:
                        try:
                            result[key] = int(value)
                        except ValueError:
                            try:
                                result[key] = float(value)
                            except ValueError:
                                result[key] = value

        if current_list_key is not None:
            result[current_list_key] = current_list

        return result if result else None

    def _load_content(self, name: str) -> str:
        if name in self._cache:
            return self._cache[name]

        meta = self._index.get(name)
        if meta is None:
            return ""

        file_path = meta.get("file_path")
        if file_path is None:
            return ""

        try:
            text = file_path.read_text(encoding="utf-8-sig")
        except OSError:
            return ""

        content = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, count=1, flags=re.DOTALL)
        self._cache[name] = content
        return content
