"""Tipos de dados do núcleo do NexusClaw."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class MemoryLevel(Enum):
    """Níveis de memória - do mais volátil ao mais persistente."""
    WORKING = "working"       # Sessão atual
    SHORT_TERM = "short_term" # Últimas 24h
    LONG_TERM = "long_term"   # Marcado como importante
    CORE = "core"             # Identidade e regras permanentes


@dataclass
class Task:
    """Uma tarefa para o agente executar."""
    id: str
    description: str
    priority: int = 0  # 0=normal, 1=alta, 2=crítica
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: TaskStatus = TaskStatus.PENDING
    context: dict[str, Any] = field(default_factory=dict)
    skills_required: list[str] = field(default_factory=list)


@dataclass
class TaskResult:
    """Resultado da execução de uma tarefa."""
    task_id: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    memory_updates: list[dict] = field(default_factory=list)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContext:
    """Contexto completo do agente em execução."""
    agent_name: str = "Nexus"
    session_id: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    current_task: Optional[Task] = None
    memory: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
