"""Agente Worker Independente do NexusClaw.

Cada Worker é um agente autônomo com:
- Própria memória persistente
- Papel/função definida
- Capacidade de executar tarefas sem supervisão
- Histórico e aprendizado próprios
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from nexus_claw.config.settings import LLMConfig, MemoryConfig
from nexus_claw.core.agent import NexusAgent
from nexus_claw.core.types import Task, TaskResult

logger = logging.getLogger("nexus_claw.orchestra.worker")


class WorkerStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    SLEEPING = "sleeping"


@dataclass
class WorkerConfig:
    """Configuração de um Worker Agent."""
    id: str = ""
    name: str = "Worker"
    role: str = "assistant"
    description: str = ""
    system_prompt: str = ""
    skills: list[str] = field(default_factory=list)
    llm: Optional[LLMConfig] = None
    memory: Optional[MemoryConfig] = None
    autonomous: bool = False  # Se pode iniciar tarefas por conta própria
    wake_interval: int = 60  # segundos entre ciclos autônomos


class WorkerAgent:
    """Agente Worker independente.

    Pode ser controlado pelo Orchestrator ou operar de forma autônoma.
    Cada Worker tem sua própria identidade, memória e capacidade de decisão.
    """

    def __init__(self, config: WorkerConfig):
        self.config = config
        if not config.id:
            config.id = uuid.uuid4().hex[:8]

        self.id = config.id
        self.name = config.name
        self.role = config.role
        self.status = WorkerStatus.IDLE

        # Prepara NexusConfig completo ANTES de criar o agente interno
        from nexus_claw.config.settings import NexusConfig, load_config

        node_config = load_config()
        if config.llm:
            node_config.llm = config.llm
        if config.memory:
            node_config.memory = config.memory

        # Agente interno com configuração já completa
        self._agent = NexusAgent(config=node_config, name=config.name)

        self._tasks_completed = 0
        self._total_tokens = 0
        self._running = False

        logger.info(f"🤖 Worker '{config.name}' [{config.role}] criado. ID: {config.id}")

    async def start(self):
        """Inicializa o worker e sua memória."""
        self._running = True
        await self._agent.start()

        if self.config.system_prompt:
            await self._agent.memory.store(
                category="core",
                content=f"# System Prompt do Worker\n\n{self.config.system_prompt}",
                metadata={"type": "system_prompt"},
            )

        self.status = WorkerStatus.IDLE
        logger.info(f"✅ Worker '{self.name}' pronto")

    async def stop(self):
        """Para o worker graciosamente."""
        self._running = False
        self.status = WorkerStatus.IDLE
        await self._agent.stop()
        logger.info(f"🛑 Worker '{self.name}' desligado")

    async def execute_task(self, description: str, context: Optional[dict] = None) -> TaskResult:
        """Executa uma tarefa delegada.

        O worker usa sua própria memória e contexto para executar.
        """
        self.status = WorkerStatus.RUNNING

        task = Task(
            id=f"{self.id}_{int(datetime.utcnow().timestamp())}",
            description=description,
            priority=1,
            context=context or {},
        )

        result = await self._agent.process_task(task)

        self._tasks_completed += 1
        if result.success:
            self.status = WorkerStatus.IDLE
        else:
            self.status = WorkerStatus.ERROR

        # Registra aprendizado
        await self._agent.memory.store(
            category="short_term",
            content=f"## Tarefa Executada\n\n**Descrição:** {description}\n**Resultado:** {'✅ Sucesso' if result.success else '❌ Falha'}\n\n{result.output or result.error}",
            metadata={"task_id": task.id, "success": result.success},
        )

        return result

    async def autonomous_cycle(self):
        """Ciclo autônomo - worker decide o que fazer.

        Usado quando autonomous=True. O worker consulta sua memória
        e decide a próxima ação.
        """
        if not self.config.autonomous:
            return

        self.status = WorkerStatus.RUNNING

        prompt = f"""Você é {self.name}, um agente autônomo com papel de {self.role}.
Com base na sua memória e tarefas recentes, decida qual a melhor ação a tomar agora.
Se não houver nada a fazer, responda "IDLE". 
Se houver algo, descreva a ação em uma frase."""

        task = Task(
            id=f"auto_{self.id}_{int(datetime.utcnow().timestamp())}",
            description=prompt,
            priority=0,
        )

        result = await self._agent.process_task(task)

        if result.output and "IDLE" not in result.output.upper():
            logger.info(f"🔄 Worker '{self.name}' ação autônoma: {result.output[:100]}")
            await self.execute_task(result.output)

        self.status = WorkerStatus.IDLE

    async def run_autonomous_loop(self):
        """Loop autônomo contínuo."""
        if not self.config.autonomous:
            logger.warning(f"Worker '{self.name}' não é autônomo")
            return

        logger.info(f"🔄 Worker '{self.name}' iniciando loop autônomo")
        while self._running:
            await self.autonomous_cycle()
            await asyncio.sleep(self.config.wake_interval)

    def get_info(self) -> dict:
        """Retorna informações do worker para o dashboard."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "status": self.status.value,
            "tasks_completed": self._tasks_completed,
            "total_tokens": self._total_tokens,
            "autonomous": self.config.autonomous,
            "description": self.config.description,
        }
