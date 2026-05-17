"""Store de memória — persistência em arquivos Markdown."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class MemoryItem:
    """Um item individual de memória."""
    id: str
    category: str
    content: str
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Converte para formato Markdown legível."""
        meta = ""
        if self.metadata:
            meta = "\n".join(
                f"> {k}: {v}" for k, v in self.metadata.items()
            )
        header = f"---\nid: {self.id}\ncategory: {self.category}\ntimestamp: {self.timestamp}\n{meta}\n---"
        return f"{header}\n\n{self.content}"

    @classmethod
    def from_markdown(cls, text: str) -> "MemoryItem":
        """Converte de formato Markdown para objeto."""
        parts = text.split("---", 2)
        if len(parts) < 3:
            return cls(id="unknown", category="unknown", content=text)

        meta_block = parts[1].strip()
        content = parts[2].strip()

        metadata = {}
        item_id = "unknown"
        category = "unknown"
        timestamp = ""

        for line in meta_block.split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if key == "id":
                    item_id = value
                elif key == "category":
                    category = value
                elif key == "timestamp":
                    timestamp = value
                else:
                    try:
                        metadata[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        metadata[key] = value

        return cls(
            id=item_id,
            category=category,
            content=content,
            timestamp=timestamp,
            metadata=metadata,
        )


@dataclass
class MemoryCategory:
    """Uma categoria/pasta de memória."""
    name: str
    path: Path
    description: str = ""


class FileMemoryStore:
    """Store baseada em arquivos Markdown no sistema de arquivos."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    async def write(self, item: MemoryItem) -> Path:
        """Escreve um item de memória em arquivo."""
        cat_dir = self.base_dir / item.category
        cat_dir.mkdir(parents=True, exist_ok=True)

        file_path = cat_dir / f"{item.id}.md"
        file_path.write_text(item.to_markdown(), encoding="utf-8")
        return file_path

    async def read(self, file_path: Path) -> Optional[MemoryItem]:
        """Lê um item de memória de arquivo."""
        if not file_path.exists():
            return None
        text = file_path.read_text(encoding="utf-8")
        return MemoryItem.from_markdown(text)

    async def list(
        self,
        category_path: Path,
        limit: int = 50,
    ) -> list[MemoryItem]:
        """Lista itens de uma categoria, ordenados por data (mais recente primeiro)."""
        if not category_path.exists():
            return []

        files = sorted(
            category_path.glob("*.md"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        items = []
        for f in files[:limit]:
            item = await self.read(f)
            if item:
                items.append(item)
        return items

    async def delete(self, file_path: Path):
        """Remove um item de memória."""
        if file_path.exists():
            file_path.unlink()

    async def count(self, category_path: Path) -> int:
        """Conta itens em uma categoria."""
        if not category_path.exists():
            return 0
        return len(list(category_path.glob("*.md")))
