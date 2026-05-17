"""Orquestração Multi-Agente do NexusClaw.

Sistema de agentes independentes gerenciados por um Orchestrator.
Cada agente tem sua própria memória persistente e pode operar de forma autônoma.
"""

from .orchestrator import OrchestratorAgent
from .worker import WorkerAgent, WorkerConfig, WorkerStatus
from .registry import AgentRegistry

__all__ = [
    "OrchestratorAgent",
    "WorkerAgent",
    "WorkerConfig",
    "WorkerStatus",
    "AgentRegistry",
]
