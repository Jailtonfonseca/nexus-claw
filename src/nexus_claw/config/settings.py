"""Configurações centralizadas do NexusClaw."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class MemoryConfig:
    """Configuração do sistema de memória persistente."""
    backend: str = "file"  # file | chroma | sqlite
    base_dir: str = str(Path.home() / ".nexus" / "memory")
    auto_summarize: bool = True
    max_context_files: int = 50
    vector_model: str = "all-MiniLM-L6-v2"  # sentence-transformers model


@dataclass
class LLMConfig:
    """Configuração do provedor de LLM."""
    provider: str = "openai"  # openai | anthropic | ollama | custom
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class SkillConfig:
    """Configuração do sistema de skills."""
    enabled: bool = True
    dir: str = str(Path.home() / ".nexus" / "skills")
    auto_install: bool = False


@dataclass
class NexusConfig:
    """Configuração principal do NexusClaw."""
    name: str = "Nexus"
    data_dir: str = str(Path.home() / ".nexus")
    log_level: str = "INFO"
    wake_interval_minutes: int = 30
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    @classmethod
    def from_env(cls) -> "NexusConfig":
        """Carrega configuração a partir de variáveis de ambiente."""
        return cls(
            name=os.getenv("NEXUS_NAME", "Nexus"),
            data_dir=os.getenv("NEXUS_DATA_DIR", str(Path.home() / ".nexus")),
            log_level=os.getenv("NEXUS_LOG_LEVEL", "INFO"),
            wake_interval_minutes=int(os.getenv("NEXUS_WAKE_INTERVAL", "30")),
            llm=LLMConfig(
                provider=os.getenv("LLM_PROVIDER", "openai"),
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                api_key=os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
                base_url=os.getenv("LLM_BASE_URL"),
            ),
        )


def load_config(path: Optional[str] = None) -> NexusConfig:
    """Carrega configuração de um arquivo YAML opcional, com fallback para env."""
    if path and Path(path).exists():
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        # Merge básico - em produção usaria pydantic-settings
        config = NexusConfig.from_env()
        if data:
            if "llm" in data:
                for k, v in data["llm"].items():
                    setattr(config.llm, k, v)
            if "memory" in data:
                for k, v in data["memory"].items():
                    setattr(config.memory, k, v)
        return config
    return NexusConfig.from_env()
