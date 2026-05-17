"""Registro central de agentes do NexusClaw Orchestra."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nexus_claw.orchestra")


@dataclass
class AgentRecord:
    """Registro de um agente no sistema."""
    id: str
    name: str
    role: str
    status: str = "idle"  # idle | running | paused | error
    model: str = "gpt-4o-mini"
    skills: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_active: str = ""
    tasks_completed: int = 0
    total_tokens: int = 0
    config: dict = field(default_factory=dict)


class AgentRegistry:
    """Gerencia o registro de todos os agentes do sistema.

    Persiste em JSON para manter estado entre reinicializações.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._agents: dict[str, AgentRecord] = {}
        self._file = data_dir / "agents.json"

    def load(self):
        """Carrega agentes do arquivo de persistência."""
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text())
                for item in data:
                    record = AgentRecord(**item)
                    self._agents[record.id] = record
                logger.info(f"📋 {len(self._agents)} agentes carregados")
            except Exception as e:
                logger.warning(f"Erro ao carregar agentes: {e}")

    def save(self):
        """Persiste o registro de agentes."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = [asdict(a) for a in self._agents.values()]
        self._file.write_text(json.dumps(data, indent=2, default=str))

    def register(self, record: AgentRecord) -> AgentRecord:
        """Registra um novo agente."""
        self._agents[record.id] = record
        self.save()
        logger.info(f"✅ Agente registrado: {record.name} ({record.role})")
        return record

    def unregister(self, agent_id: str):
        """Remove um agente do registro."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            self.save()

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        """Retorna um agente pelo ID."""
        return self._agents.get(agent_id)

    def list(self) -> list[AgentRecord]:
        """Lista todos os agentes registrados."""
        return list(self._agents.values())

    def list_by_role(self, role: str) -> list[AgentRecord]:
        """Lista agentes por função."""
        return [a for a in self._agents.values() if a.role == role]

    def update_status(self, agent_id: str, status: str):
        """Atualiza o status de um agente."""
        if agent_id in self._agents:
            self._agents[agent_id].status = status
            self._agents[agent_id].last_active = datetime.utcnow().isoformat()
            self.save()

    def increment_tasks(self, agent_id: str, tokens: int = 0):
        """Incrementa contadores de tarefas do agente."""
        if agent_id in self._agents:
            self._agents[agent_id].tasks_completed += 1
            self._agents[agent_id].total_tokens += tokens
            self.save()
