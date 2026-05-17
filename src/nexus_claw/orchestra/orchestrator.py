"""Orquestrador NexusClaw — o agente principal que gerencia workers.

Funciona como um CEO digital:
- Delega tarefas para workers especializados
- Monitora desempenho e saúde do sistema
- Gerencia fila de tarefas
- Coordena comunicação entre workers
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from nexus_claw.config.settings import NexusConfig
from nexus_claw.core.agent import NexusAgent
from nexus_claw.core.types import Task, TaskResult, TaskStatus
from nexus_claw.orchestra.registry import AgentRecord, AgentRegistry
from nexus_claw.orchestra.worker import WorkerAgent, WorkerConfig, WorkerStatus

logger = logging.getLogger("nexus_claw.orchestra")


@dataclass
class OrchestraTask:
    """Tarefa no sistema de orquestração."""
    id: str
    description: str
    assigned_to: Optional[str] = None
    priority: int = 0
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class OrchestratorAgent:
    """Agente Orquestrador Principal — o CEO do sistema.

    Gerencia workers, fila de tarefas, e coordena a execução.
    """

    def __init__(self, data_dir: str = "~/.nexus"):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Agente principal (CEO)
        self._ceo = NexusAgent(name="Orchestrator")

        # Registro de workers
        self.registry = AgentRegistry(self.data_dir)
        self._workers: dict[str, WorkerAgent] = {}

        # Fila de tarefas
        self._task_queue: list[OrchestraTask] = []
        self._max_queue_size = 100

        # Controle
        self._running = False
        self._lock = asyncio.Lock()

        logger.info("🎪 Orchestrator Agent inicializado")

    async def start(self):
        """Inicia o orquestrador e carrega workers."""
        self._running = True
        await self._ceo.start()
        self.registry.load()

        # Recarrega workers do registro
        for record in self.registry.list():
            if record.status != "paused":
                config = WorkerConfig(
                    id=record.id,
                    name=record.name,
                    role=record.role,
                    skills=record.skills,
                )
                worker = WorkerAgent(config)
                await worker.start()
                self._workers[record.id] = worker

        logger.info(f"🎪 Orchestrator pronto — {len(self._workers)} workers ativos")

    async def stop(self):
        """Para todos os workers e o orquestrador."""
        self._running = False
        for worker in self._workers.values():
            await worker.stop()
        self.registry.save()
        await self._ceo.stop()
        logger.info("🎪 Orchestrator desligado")

    async def add_worker(
        self,
        name: str,
        role: str,
        description: str = "",
        system_prompt: str = "",
        autonomous: bool = False,
    ) -> WorkerAgent:
        """Adiciona um novo worker ao sistema."""
        config = WorkerConfig(
            name=name,
            role=role,
            description=description,
            system_prompt=system_prompt,
            autonomous=autonomous,
        )

        worker = WorkerAgent(config)
        await worker.start()

        # Registra
        self._workers[worker.id] = worker
        self.registry.register(AgentRecord(
            id=worker.id,
            name=name,
            role=role,
            skills=config.skills,
        ))

        # Anuncia ao CEO
        await self._ceo.memory.store(
            category="short_term",
            content=f"## Novo Worker Adicionado\n\n**Nome:** {name}\n**Papel:** {role}\n**ID:** {worker.id}\n\n{description}",
        )

        logger.info(f"➕ Worker '{name}' [{role}] adicionado ao sistema")
        return worker

    async def remove_worker(self, worker_id: str):
        """Remove um worker do sistema."""
        if worker_id in self._workers:
            await self._workers[worker_id].stop()
            del self._workers[worker_id]
            self.registry.unregister(worker_id)
            logger.info(f"➖ Worker {worker_id} removido")

    async def delegate_task(
        self,
        description: str,
        worker_id: Optional[str] = None,
        role: Optional[str] = None,
        priority: int = 0,
    ) -> OrchestraTask:
        """Delega uma tarefa para o worker mais adequado.

        Se worker_id for especificado, delega diretamente.
        Se role for especificado, escolhe o melhor worker daquele papel.
        Se nenhum for especificado, o Orchestrator decide.
        """
        task = OrchestraTask(
            id=f"task_{len(self._task_queue)}_{datetime.utcnow().timestamp()}",
            description=description,
            priority=priority,
        )

        # Escolhe worker alvo
        target_id = worker_id

        if not target_id and role:
            # Encontra worker pelo papel
            role_workers = [
                w for w in self._workers.values()
                if w.role == role and w.status == WorkerStatus.IDLE
            ]
            if role_workers:
                # Round-robin simples
                target_id = role_workers[0].id

        if not target_id:
            # Orchestrator decide qual worker usar
            target_id = await self._decide_worker(description)

        if target_id and target_id in self._workers:
            task.assigned_to = target_id
            worker = self._workers[target_id]

            # Executa
            result = await worker.execute_task(description)

            task.status = "completed" if result.success else "failed"
            task.result = result.output
            task.error = result.error

            # Atualiza registro
            self.registry.update_status(target_id, result.status)
            if result.success:
                self.registry.increment_tasks(target_id)
        else:
            task.status = "failed"
            task.error = "Nenhum worker disponível para esta tarefa"
            logger.warning(f"⚠️ Tarefa '{description[:50]}...' não pôde ser delegada")

        self._task_queue.append(task)
        if len(self._task_queue) > self._max_queue_size:
            self._task_queue.pop(0)

        return task

    async def _decide_worker(self, description: str) -> Optional[str]:
        """Orchestrator decide qual worker é melhor para a tarefa."""
        if not self._workers:
            return None

        workers_info = "\n".join([
            f"- {w.id}: {w.name} ({w.role}) - {w.status.value}"
            for w in self._workers.values()
        ])

        prompt = f"""## DECISÃO: Qual worker deve executar esta tarefa?

### Tarefa
{description}

### Workers disponíveis
{workers_info}

### Instrução
Responda APENAS com o ID do worker mais adequado. Ex: abc12345
Se nenhum for adequado, responda "NENHUM".
"""

        task = Task(
            id=f"decide_{datetime.utcnow().timestamp()}",
            description=prompt,
        )
        result = await self._ceo.process_task(task)

        if result.success and result.output:
            decision = result.output.strip().split("\n")[0].strip()
            if decision in self._workers:
                return decision

        # Fallback: primeiro worker idle
        for wid, w in self._workers.items():
            if w.status == WorkerStatus.IDLE:
                return wid
        return None

    async def broadcast_message(self, message: str):
        """Envia uma mensagem para todos os workers."""
        for worker in self._workers.values():
            await worker.execute_task(
                f"[MENSAGEM DO ORQUESTRADOR] {message}"
            )

    async def get_system_status(self) -> dict:
        """Retorna status completo do sistema para o dashboard."""
        workers_info = []
        for worker in self._workers.values():
            info = worker.get_info()
            info["last_active"] = self.registry.get(worker.id).last_active if self.registry.get(worker.id) else ""
            workers_info.append(info)

        return {
            "orchestrator": {
                "name": "Orchestrator",
                "status": "running" if self._running else "stopped",
                "workers_count": len(self._workers),
                "queue_size": len(self._task_queue),
            },
            "workers": workers_info,
            "queue": [
                {
                    "id": t.id,
                    "description": t.description[:100],
                    "assigned_to": t.assigned_to,
                    "status": t.status,
                    "priority": t.priority,
                    "created_at": t.created_at,
                }
                for t in self._task_queue[-20:]  # Últimas 20
            ],
        }

    async def get_worker_memory(self, worker_id: str, category: str = "short_term", limit: int = 10) -> list:
        """Recupera memória de um worker específico."""
        worker = self._workers.get(worker_id)
        if not worker:
            return []
        return await worker._agent.memory.get_recent(category, limit)

    async def pause_worker(self, worker_id: str):
        """Pausa um worker."""
        worker = self._workers.get(worker_id)
        if worker:
            worker.status = WorkerStatus.PAUSED
            self.registry.update_status(worker_id, "paused")

    async def resume_worker(self, worker_id: str):
        """Retoma um worker pausado."""
        worker = self._workers.get(worker_id)
        if worker:
            worker.status = WorkerStatus.IDLE
            self.registry.update_status(worker_id, "idle")
