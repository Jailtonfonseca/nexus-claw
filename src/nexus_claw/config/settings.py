"""Configurações centralizadas do NexusClaw.

Suporte a:
- Variáveis de ambiente (`.env`)
- Arquivo YAML (`~/.nexus/config.yml`)
- API de configuração visual (dashboard)
- Persistência bidirecional (load + save)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

# ─── Helpers ──────────────────────────────────────────────────

_DEFAULT_DATA_DIR = str(Path.home() / ".nexus")


def _get_data_dir() -> str:
    return os.getenv("NEXUS_DATA_DIR", _DEFAULT_DATA_DIR)


def _config_path() -> Path:
    return Path(_get_data_dir()) / "config.yml"


def _env_path() -> Path:
    return Path(_get_data_dir()) / ".env"


# ─── Config Models ───────────────────────────────────────────


@dataclass
class MemoryConfig:
    """Configuração do sistema de memória persistente."""
    backend: str = "file"
    base_dir: str = str(Path.home() / ".nexus" / "memory")
    auto_summarize: bool = True
    max_context_files: int = 50
    vector_model: str = "all-MiniLM-L6-v2"

    def to_dict(self) -> dict:
        return {
            "backend": self.backend,
            "base_dir": self.base_dir,
            "auto_summarize": self.auto_summarize,
            "max_context_files": self.max_context_files,
            "vector_model": self.vector_model,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryConfig":
        return cls(
            backend=data.get("backend", "file"),
            base_dir=data.get("base_dir", str(Path.home() / ".nexus" / "memory")),
            auto_summarize=data.get("auto_summarize", True),
            max_context_files=data.get("max_context_files", 50),
            vector_model=data.get("vector_model", "all-MiniLM-L6-v2"),
        )


@dataclass
class LLMConfig:
    """Configuração do provedor de LLM."""
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096

    def to_dict(self) -> dict:
        """Serializa para dict, escondendo a API key parcialmente."""
        d = {
            "provider": self.provider,
            "model": self.model,
            "api_key": self._mask_key(self.api_key) if self.api_key else "",
            "base_url": self.base_url or "",
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        return d

    def to_dict_full(self) -> dict:
        """Serializa com API key visível (para salvar no arquivo)."""
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key or "",
            "base_url": self.base_url or "",
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LLMConfig":
        return cls(
            provider=data.get("provider", "openai"),
            model=data.get("model", "gpt-4o-mini"),
            api_key=data.get("api_key") or None,
            base_url=data.get("base_url") or None,
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 4096),
        )

    @staticmethod
    def _mask_key(key: str) -> str:
        if len(key) <= 8:
            return "***" + key[-4:]
        return key[:4] + "****" + key[-4:]

    def provider_display(self) -> str:
        labels = {
            "openai": "OpenAI",
            "anthropic": "Anthropic (Claude)",
            "ollama": "Ollama (local)",
            "custom": "Custom (OpenAI-compatível)",
            "deepseek": "DeepSeek",
            "google": "Google (Gemini)",
        }
        return labels.get(self.provider, self.provider.capitalize())


@dataclass
class SkillConfig:
    """Configuração do sistema de skills."""
    enabled: bool = True
    dir: str = str(Path.home() / ".nexus" / "skills")
    auto_install: bool = False

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "dir": self.dir, "auto_install": self.auto_install}

    @classmethod
    def from_dict(cls, data: dict) -> "SkillConfig":
        return cls(
            enabled=data.get("enabled", True),
            dir=data.get("dir", str(Path.home() / ".nexus" / "skills")),
            auto_install=data.get("auto_install", False),
        )


@dataclass
class NexusConfig:
    """Configuração principal do NexusClaw."""
    name: str = "Nexus"
    data_dir: str = _DEFAULT_DATA_DIR
    log_level: str = "INFO"
    wake_interval_minutes: int = 30
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "data_dir": self.data_dir,
            "log_level": self.log_level,
            "wake_interval_minutes": self.wake_interval_minutes,
            "memory": self.memory.to_dict(),
            "llm": self.llm.to_dict(),
        }

    def to_dict_full(self) -> dict:
        return {
            "name": self.name,
            "data_dir": self.data_dir,
            "log_level": self.log_level,
            "wake_interval_minutes": self.wake_interval_minutes,
            "memory": self.memory.to_dict(),
            "llm": self.llm.to_dict_full(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NexusConfig":
        return cls(
            name=data.get("name", "Nexus"),
            data_dir=data.get("data_dir", _DEFAULT_DATA_DIR),
            log_level=data.get("log_level", "INFO"),
            wake_interval_minutes=data.get("wake_interval_minutes", 30),
            memory=MemoryConfig.from_dict(data.get("memory", {})),
            llm=LLMConfig.from_dict(data.get("llm", {})),
        )

    @classmethod
    def from_env(cls) -> "NexusConfig":
        """Carrega configuração a partir de variáveis de ambiente."""
        return cls(
            name=os.getenv("NEXUS_NAME", "Nexus"),
            data_dir=os.getenv("NEXUS_DATA_DIR", _DEFAULT_DATA_DIR),
            log_level=os.getenv("NEXUS_LOG_LEVEL", "INFO"),
            wake_interval_minutes=int(os.getenv("NEXUS_WAKE_INTERVAL", "30")),
            llm=LLMConfig(
                provider=os.getenv("LLM_PROVIDER", "openai"),
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                api_key=os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
                base_url=os.getenv("LLM_BASE_URL"),
            ),
        )


# ─── Load / Save ─────────────────────────────────────────────


def load_config(path: Optional[str] = None) -> NexusConfig:
    """Carrega configuração: YAML > env vars > defaults.

    Prioridade (maior > menor):
    1. YAML explícito (se passado)
    2. ~/.nexus/config.yml (se existir)
    3. Variáveis de ambiente
    4. Valores padrão
    """
    # Começa com env
    config = NexusConfig.from_env()

    # Tenta carregar YAML
    yaml_path = None
    if path and Path(path).exists():
        yaml_path = Path(path)
    elif _config_path().exists():
        yaml_path = _config_path()

    if yaml_path:
        import yaml
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            if "llm" in data:
                for k, v in data["llm"].items():
                    if v is not None:
                        setattr(config.llm, k, v)
            if "memory" in data:
                for k, v in data["memory"].items():
                    if v is not None:
                        if k == "auto_summarize":
                            v = bool(v)
                        setattr(config.memory, k, v)
            if "name" in data and data["name"]:
                config.name = data["name"]
            if "log_level" in data and data["log_level"]:
                config.log_level = data["log_level"]
            if "wake_interval_minutes" in data:
                config.wake_interval_minutes = int(data["wake_interval_minutes"])
        except Exception as e:
            import logging
            logging.warning(f"Erro ao carregar YAML: {e}")

    return config


def save_config(config: NexusConfig, path: Optional[str] = None) -> Path:
    """Salva configuração em YAML."""
    import yaml

    save_path = Path(path) if path else _config_path()
    save_path.parent.mkdir(parents=True, exist_ok=True)

    data = config.to_dict_full()

    with open(save_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return save_path
