"""Agente autônomo NexusClaw — coração do sistema."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from nexus_claw.config.settings import NexusConfig
from nexus_claw.core.types import AgentContext, Task, TaskResult, TaskStatus
from nexus_claw.llm.client import LLMClient
from nexus_claw.memory.engine import MemoryEngine

logger = logging.getLogger("nexus_claw")


class NexusAgent:
    """Agente autônomo com memória persistente.

    O NexusAgent funciona 24/7, aprende continuamente
    e mantém memória entre sessões.
    """

    def __init__(
        self,
        config: Optional[NexusConfig] = None,
        name: str = "Nexus",
    ):
        self.config = config or NexusConfig.from_env()
        self.name = name

        # Inicializa subsistemas
        self.llm = LLMClient(self.config.llm)
        self.memory = MemoryEngine(self.config.memory)
        self.context = AgentContext(
            agent_name=name,
            session_id=uuid.uuid4().hex[:12],
        )

        self._running = False
        self._skills: dict = {}

        logger.info(f"🤖 NexusClaw '{name}' inicializado. Sessão: {self.context.session_id}")

    async def start(self):
        """Inicia o agente — carrega memória e prepara ambiente."""
        logger.info("🚀 Iniciando NexusClaw...")
        await self.memory.initialize()
        core_memory = await self.memory.get_category("core")
        if not core_memory:
            await self._init_core_memory()
        self._running = True
        logger.info("✅ NexusClaw pronto para ação!")

    async def stop(self):
        """Para o agente graciosamente."""
        self._running = False
        await self.memory.save()
        logger.info("🛑 NexusClaw desligado. Memória salva.")

    async def process_task(self, task: Task) -> TaskResult:
        """Processa uma tarefa: busca contexto, executa, registra na memória."""
        start = datetime.utcnow()
        task.status = TaskStatus.RUNNING
        self.context.current_task = task

        try:
            # 1. Busca contexto relevante da memória
            context = await self._gather_context(task)

            # 2. Monta prompt com contexto + memória
            prompt = self._build_prompt(task, context)

            # 3. Executa via LLM
            response = await self.llm.chat(prompt)

            # 4. Extrai aprendizados e salva na memória
            await self._learn(task, response)

            duration = (datetime.utcnow() - start).total_seconds() * 1000
            task.status = TaskStatus.COMPLETED

            return TaskResult(
                task_id=task.id,
                success=True,
                output=response,
                duration_ms=duration,
            )

        except Exception as e:
            duration = (datetime.utcnow() - start).total_seconds() * 1000
            task.status = TaskStatus.FAILED
            logger.error(f"❌ Task {task.id} falhou: {e}")
            return TaskResult(
                task_id=task.id,
                success=False,
                error=str(e),
                duration_ms=duration,
            )

    async def _gather_context(self, task: Task) -> dict:
        """Reúne contexto da memória para enriquecer a tarefa."""
        context = {"task": task.description}

        # Memória de curto prazo (últimas ações)
        recent = await self.memory.search("recent", limit=5)
        if recent:
            context["recent_actions"] = recent

        # Memória de longo prazo relevante
        relevant = await self.memory.search(task.description, limit=3)
        if relevant:
            context["relevant_memories"] = relevant

        return context

    def _build_prompt(self, task: Task, context: dict) -> str:
        """Constrói o prompt completo com contexto e memória."""
        prompt = f"""Você é {self.name}, um assistente autônomo com memória persistente.

## TAREFA ATUAL
{task.description}

## CONTEXTO DA MEMÓRIA
"""
        if context.get("recent_actions"):
            prompt += "\n### Ações Recentes\n"
            for item in context["recent_actions"]:
                prompt += f"- {item}\n"

        if context.get("relevant_memories"):
            prompt += "\n### Memórias Relevantes\n"
            for item in context["relevant_memories"]:
                prompt += f"- {item}\n"

        prompt += f"""
## INSTRUÇÕES
1. Analise a tarefa usando o contexto disponível
2. Execute a ação necessária
3. Extraia aprendizados para memória futura
4. Responda de forma clara e direta
"""
        return prompt

    async def _learn(self, task: Task, response: str):
        """Extrai aprendizados da execução e salva na memória."""
        await self.memory.store(
            category="short_term",
            content=f"Task: {task.description}\nResult: {response[:500]}",
            metadata={"task_id": task.id, "priority": task.priority},
        )

    async def _init_core_memory(self):
        """Inicializa a memória central com a identidade do agente."""
        await self.memory.store(
            category="core",
            content=f"""# Identidade do {self.name}

- Nome: {self.name}
- Propósito: Assistente autônomo com memória persistente
- Versão: 0.1.0
- Criado por: Jailton Fonseca
- Data de criação: {datetime.utcnow().isoformat()}
- Habilidades: Processamento de tarefas, memória persistente,
  aprendizado contínuo, integração com LLMs
""",
            metadata={"type": "identity", "permanent": True},
        )
