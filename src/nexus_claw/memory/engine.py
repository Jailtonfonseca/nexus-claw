"""Motor de Memória Persistente — coração da memória do NexusClaw.

Arquitetura File-System Style:
- Memória organizada em categorias (pastas)
- Itens de memória como arquivos Markdown
- Busca semântica via embeddings (opcional)
- Monitoramento proativo com modo deep reasoning
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from nexus_claw.config.settings import MemoryConfig
from nexus_claw.memory.store import FileMemoryStore, MemoryCategory, MemoryItem

logger = logging.getLogger("nexus_claw.memory")


class MemoryEngine:
    """Motor principal de memória persistente.

    Gerencia o ciclo de vida da memória:
    escrita → indexação → sumarização → consolidação → poda
    """

    def __init__(self, config: MemoryConfig):
        self.config = config
        self.store = FileMemoryStore(Path(config.base_dir))
        self._categories: dict[str, MemoryCategory] = {}
        self._vector_index = None

    async def initialize(self):
        """Inicializa o motor de memória.

        Cria a estrutura base, carrega categorias existentes
        e prepara o índice vetorial (se configurado).
        """
        logger.info(f"🧠 Inicializando memória em: {self.config.base_dir}")

        # Garante estrutura de diretórios
        os.makedirs(self.config.base_dir, exist_ok=True)
        for cat_name in ["core", "long_term", "short_term", "working", "learned"]:
            cat_dir = Path(self.config.base_dir) / cat_name
            os.makedirs(cat_dir, exist_ok=True)
            self._categories[cat_name] = MemoryCategory(
                name=cat_name,
                path=cat_dir,
            )

        # Carrega índices
        self._load_indexes()
        logger.info(f"✅ Memória inicializada: {len(self._categories)} categorias")

    async def store(
        self,
        category: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> MemoryItem:
        """Armazena um item na memória."""
        if category not in self._categories:
            raise ValueError(f"Categoria '{category}' não existe")

        item = MemoryItem(
            id=self._generate_id(),
            category=category,
            content=content,
            metadata=metadata or {},
            timestamp=datetime.utcnow().isoformat(),
        )

        await self.store.write(item)
        await self._update_index(item)
        logger.debug(f"📝 Memória salva: {category}/{item.id}")
        return item

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> list[str]:
        """Busca na memória por conteúdo relevante.

        Usa busca semântica (se vector index disponível)
        ou fallback para busca textual.
        """
        if self._vector_index and self.config.backend == "chroma":
            return await self._vector_search(query, category, limit)
        return await self._text_search(query, category, limit)

    async def get_category(self, name: str) -> Optional[MemoryCategory]:
        """Retorna uma categoria de memória."""
        return self._categories.get(name)

    async def get_recent(self, category: str, limit: int = 5) -> list[str]:
        """Retorna itens recentes de uma categoria."""
        cat = self._categories.get(category)
        if not cat:
            return []
        items = await self.store.list(cat.path, limit=limit)
        return [item.content for item in items]

    async def summarize(self, category: str) -> Optional[str]:
        """Sumariza uma categoria de memória.

        Útil para compressão de contexto antes de poda.
        (A implementação do LLM será adicionada na v0.2)
        """
        items = await self.store.list(
            self._categories[category].path,
            limit=100,
        )
        if not items:
            return None
        summary = "\n".join(f"- {item.content[:200]}..." for item in items)
        return f"## Sumário: {category}\n\n{summary}"

    async def _text_search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> list[str]:
        """Busca textual simples por palavras-chave."""
        results = []
        query_lower = query.lower()
        words = set(query_lower.split())

        cats = [category] if category else self._categories
        for cat_name in cats:
            cat = self._categories[cat_name]
            items = await self.store.list(cat.path, limit=50)
            for item in items:
                content_lower = item.content.lower()
                # Score baseado em quantas palavras do query aparecem
                matches = sum(1 for w in words if w in content_lower)
                if matches > 0:
                    results.append((matches, item.content))

        results.sort(reverse=True, key=lambda x: x[0])
        return [content for _, content in results[:limit]]

    async def _vector_search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> list[str]:
        """Busca semântica via ChromaDB."""
        try:
            import chromadb
            client = chromadb.PersistentClient(
                path=str(Path(self.config.base_dir) / ".chroma")
            )
            collection = client.get_or_create_collection("nexus_memory")
            results = collection.query(
                query_texts=[query],
                n_results=limit,
            )
            return results.get("documents", [[]])[0]
        except Exception as e:
            logger.warning(f"Vector search falhou, fallback textual: {e}")
            return await self._text_search(query, category, limit)

    async def _update_index(self, item: MemoryItem):
        """Atualiza o índice vetorial (se disponível)."""
        if self.config.backend == "chroma":
            try:
                import chromadb
                client = chromadb.PersistentClient(
                    path=str(Path(self.config.base_dir) / ".chroma")
                )
                collection = client.get_or_create_collection("nexus_memory")
                collection.add(
                    documents=[item.content],
                    ids=[item.id],
                    metadatas=[{"category": item.category, **item.metadata}],
                )
            except Exception as e:
                logger.warning(f"Indexação vetorial falhou: {e}")

    def _load_indexes(self):
        """Carrega índices existentes."""
        index_file = Path(self.config.base_dir) / ".index.json"
        if index_file.exists():
            try:
                with open(index_file) as f:
                    json.load(f)  # valida apenas
            except json.JSONDecodeError:
                pass

    @staticmethod
    def _generate_id() -> str:
        return datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f") + "_" + os.urandom(2).hex()

    async def save(self):
        """Persiste estado atual da memória."""
        for cat in self._categories.values():
            if not cat.path.exists():
                cat.path.mkdir(parents=True)
        logger.info("💾 Memória salva com sucesso")
