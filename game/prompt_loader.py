import os
from pathlib import Path
from typing import Optional


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptLoader:
    _cache: dict[str, str] = {}

    def load(self, path: str) -> Optional[str]:
        if path in self._cache:
            return self._cache[path]

        full_path = PROMPTS_DIR / path
        if full_path.exists():
            content = full_path.read_text(encoding="utf-8").strip()
            self._cache[path] = content
            return content
        return None

    def load_core(self) -> str:
        parts = []
        for name in ["system", "narrative_style"]:
            content = self.load(f"core/{name}.md")
            if content:
                parts.append(content)
        return "\n\n".join(parts)

    def load_genre(self, genre: str) -> Optional[str]:
        return self.load(f"genres/{genre}.md")

    def load_situation(self, situation: str) -> Optional[str]:
        return self.load(f"situations/{situation}.md")

    def get_available_situations(self) -> list[str]:
        situations_dir = PROMPTS_DIR / "situations"
        if situations_dir.exists():
            return [f.stem for f in situations_dir.glob("*.md")]
        return []

    def clear_cache(self):
        self._cache.clear()
