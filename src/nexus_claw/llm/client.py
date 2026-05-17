"""Cliente LLM multi-provedor com fallback."""

from __future__ import annotations

import logging
from typing import Optional

from nexus_claw.config.settings import LLMConfig

logger = logging.getLogger("nexus_claw.llm")


class LLMClient:
    """Cliente LLM que suporta múltiplos provedores.

    Suporta: OpenAI, Anthropic, Ollama, e qualquer API compatível com OpenAI.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
        self._init_client()

    def _init_client(self):
        """Inicializa o cliente apropriado baseado no provedor."""
        provider = self.config.provider

        if provider == "openai" or provider == "custom":
            self._init_openai()
        elif provider == "anthropic":
            self._init_anthropic()
        elif provider == "ollama":
            self._init_ollama()
        else:
            raise ValueError(f"Provedor LLM desconhecido: {provider}")

    def _init_openai(self):
        """Inicializa cliente compatível com OpenAI."""
        try:
            from openai import AsyncOpenAI
            kwargs = {"api_key": self.config.api_key or "sk-placeholder"}
            if self.config.base_url:
                kwargs["base_url"] = self.config.base_url
            self._client = AsyncOpenAI(**kwargs)
            logger.info(f"📡 LLM: OpenAI compatível ({self.config.model})")
        except ImportError:
            logger.warning("openai não instalado. Use: pip install openai")
            self._client = None

    def _init_anthropic(self):
        """Inicializa cliente Anthropic."""
        try:
            import anthropic
            self._client = anthropic.AsyncAnthropic(
                api_key=self.config.api_key or ""
            )
            logger.info(f"📡 LLM: Anthropic ({self.config.model})")
        except ImportError:
            logger.warning("anthropic não instalado. Use: pip install anthropic")
            self._client = None

    def _init_ollama(self):
        """Inicializa cliente Ollama (localhost)."""
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                base_url=self.config.base_url or "http://localhost:11434/v1",
                api_key="ollama",
            )
            logger.info(f"📡 LLM: Ollama ({self.config.model})")
        except ImportError:
            logger.warning("openai não instalado")
            self._client = None

    async def chat(self, prompt: str, system: Optional[str] = None) -> str:
        """Envia um prompt para o LLM e retorna a resposta."""
        if not self._client:
            return "[LLM não configurado — instale as dependências e configure a API key]"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            if self.config.provider == "anthropic":
                return await self._anthropic_chat(messages)
            return await self._openai_chat(messages)

        except Exception as e:
            logger.error(f"Erro na chamada LLM: {e}")
            return f"[Erro na comunicação com o LLM: {e}]"

    async def _openai_chat(self, messages: list) -> str:
        """Chamada via API compatível com OpenAI."""
        response = await self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return response.choices[0].message.content or ""

    async def _anthropic_chat(self, messages: list) -> str:
        """Chamada via API Anthropic."""
        # Converte formato OpenAI -> Anthropic
        system = None
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        response = await self._client.messages.create(
            model=self.config.model,
            system=system,
            messages=anthropic_messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        return response.content[0].text if response.content else ""

    async def embed(self, text: str) -> list[float]:
        """Gera embedding para um texto."""
        try:
            if hasattr(self._client, "embeddings"):
                response = await self._client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text,
                )
                return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Embedding falhou: {e}")
        return []
