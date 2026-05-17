"""Sistema de Skills (plugins) do NexusClaw.

Skills são módulos extensíveis que adicionam capacidades ao agente.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("nexus_claw.skills")


class SkillRegistry:
    """Registra e gerencia skills do NexusClaw."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills: dict[str, Any] = {}

    def load_all(self):
        """Carrega todas as skills disponíveis."""
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True)
            return

        for skill_file in self.skills_dir.glob("*.py"):
            if skill_file.name.startswith("_"):
                continue
            self._load_skill(skill_file)

        logger.info(f"🔌 {len(self._skills)} skills carregadas")

    def _load_skill(self, path: Path):
        """Carrega uma skill específica."""
        try:
            spec = importlib.util.spec_from_file_location(
                path.stem, path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "register"):
                    skill = module.register()
                    self._skills[skill["name"]] = skill
                    logger.info(f"  ✅ Skill: {skill['name']}")
        except Exception as e:
            logger.warning(f"  ⚠️  Skill {path.name}: {e}")

    def get(self, name: str) -> Any:
        """Retorna uma skill pelo nome."""
        return self._skills.get(name)

    def list(self) -> list[str]:
        """Lista todas as skills disponíveis."""
        return list(self._skills.keys())
