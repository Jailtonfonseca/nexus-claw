"""Dashboard Web do NexusClaw Orchestra.

Servidor FastAPI com WebSocket para status em tempo real.
Interface para gerenciar configurações, workers, tarefas e memória.
"""

from __future__ import annotations

import json
import logging
import os
import platform
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from nexus_claw.config.settings import (
    LLMConfig,
    MemoryConfig,
    NexusConfig,
    SkillConfig,
    load_config,
    save_config,
)
from nexus_claw.orchestra.orchestrator import OrchestratorAgent

logger = logging.getLogger("nexus_claw.dashboard")

# ─── Static files ──────────────────────────────────────────

_PACKAGE_DIR = Path(__file__).parent
_STATIC_DIR = _PACKAGE_DIR / "static"


# ─── Pydantic Models ───────────────────────────────────────

class WorkerCreate(BaseModel):
    name: str
    role: str
    description: str = ""
    system_prompt: str = ""
    autonomous: bool = False


class TaskDelegate(BaseModel):
    description: str
    worker_id: Optional[str] = None
    role: Optional[str] = None
    priority: int = 0


class BroadcastMsg(BaseModel):
    message: str


class LLMSettingsModel(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


class MemorySettingsModel(BaseModel):
    backend: str = "file"
    base_dir: str = ""
    auto_summarize: bool = True
    max_context_files: int = 50
    vector_model: str = "all-MiniLM-L6-v2"


class FullConfigModel(BaseModel):
    name: str = "Nexus"
    log_level: str = "INFO"
    wake_interval_minutes: int = 30
    llm: LLMSettingsModel = Field(default_factory=LLMSettingsModel)
    memory: MemorySettingsModel = Field(default_factory=MemorySettingsModel)


class LLMTestModel(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


# ─── App State ─────────────────────────────────────────────

orchestrator: Optional[OrchestratorAgent] = None
connected_websockets: set[WebSocket] = set()
current_config: Optional[NexusConfig] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa orquestrador e carrega configurações."""
    global orchestrator, current_config

    # Carrega config
    current_config = load_config()

    # Cria orquestrador
    orchestrator = OrchestratorAgent(data_dir=current_config.data_dir)
    await orchestrator.start()

    # Workers padrão (se vazio)
    if not orchestrator._workers:
        await orchestrator.add_worker(
            name="Analista",
            role="analyst",
            description="Analisa dados, pesquisa informações e gera relatórios",
            system_prompt="Você é um analista de dados especializado em pesquisa e análise.",
        )
        await orchestrator.add_worker(
            name="Criador",
            role="creator",
            description="Cria conteúdo, escreve textos e gera ideias criativas",
            system_prompt="Você é um criador de conteúdo especializado em escrita criativa.",
        )
        await orchestrator.add_worker(
            name="Assistente",
            role="assistant",
            description="Assistente geral para tarefas diversas",
            system_prompt="Você é um assistente versátil pronto para ajudar em qualquer tarefa.",
        )

    yield

    await orchestrator.stop()


# ─── App ──────────────────────────────────────────────────

app = FastAPI(
    title="NexusClaw Orchestra Dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files
_STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ═══════════════════════════════════════════════════════════
# 🏠 PÁGINA PRINCIPAL
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def get_dashboard():
    """Serve o dashboard HTML."""
    html_file = _STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text())
    return HTMLResponse("<h1>NexusClaw Dashboard</h1><p>Build the UI...</p>")


# ═══════════════════════════════════════════════════════════
# ⚙️ CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════

_CONFIG_PATH_ENV_VAR = "NEXUS_CONFIG_PATH"


def _get_config() -> NexusConfig:
    """Retorna config atual (com fallback)."""
    global current_config
    if current_config is None:
        current_config = load_config()
    return current_config


def _save_config_to_disk(config: NexusConfig):
    """Persiste configuração e atualiza estado global."""
    global current_config
    path = os.getenv(_CONFIG_PATH_ENV_VAR)
    saved = save_config(config, path)
    current_config = config
    logger.info(f"⚙️ Configuração salva em: {saved}")
    return saved


def _model_to_llm_config(m: LLMSettingsModel) -> LLMConfig:
    return LLMConfig(
        provider=m.provider,
        model=m.model,
        api_key=m.api_key or None,
        base_url=m.base_url or None,
        temperature=m.temperature,
        max_tokens=m.max_tokens,
    )


def _model_to_memory_config(m: MemorySettingsModel) -> MemoryConfig:
    return MemoryConfig(
        backend=m.backend,
        base_dir=m.base_dir or str(Path.home() / ".nexus" / "memory"),
        auto_summarize=m.auto_summarize,
        max_context_files=m.max_context_files,
        vector_model=m.vector_model,
    )


def _config_to_response(c: NexusConfig) -> dict:
    """Converte NexusConfig para dict de resposta (API key mascarada)."""
    return {
        "name": c.name,
        "data_dir": c.data_dir,
        "log_level": c.log_level,
        "wake_interval_minutes": c.wake_interval_minutes,
        "llm": c.llm.to_dict(),
        "memory": c.memory.to_dict(),
    }


@app.get("/api/config")
async def get_config():
    """Retorna configuração atual."""
    config = _get_config()
    return _config_to_response(config)


@app.put("/api/config")
async def update_config(data: FullConfigModel):
    """Atualiza e persiste a configuração."""
    config = _get_config()

    # Atualiza campos principais
    config.name = data.name
    config.log_level = data.log_level
    config.wake_interval_minutes = data.wake_interval_minutes

    # LLM
    config.llm = _model_to_llm_config(data.llm)

    # Memory
    config.memory = _model_to_memory_config(data.memory)

    # Salva
    _save_config_to_disk(config)

    return {
        "status": "saved",
        "message": "Configuração salva com sucesso!",
        "config": _config_to_response(config),
    }


@app.post("/api/config/test-llm")
async def test_llm_connection(data: LLMTestModel):
    """Testa conexão com o LLM configurado."""
    import httpx

    llm = _model_to_llm_config(data)

    messages = [
        {"role": "system", "content": "Responda apenas com a palavra 'OK'."},
        {"role": "user", "content": "Teste de conexão. Responda apenas OK."},
    ]

    try:
        if llm.provider == "ollama":
            url = f"{llm.base_url or 'http://localhost:11434'}/api/chat"
            payload = {"model": llm.model, "messages": messages, "stream": False}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return {"status": "ok", "message": f"✅ Ollama ({llm.model}) respondendo!"}

        else:
            from openai import AsyncOpenAI

            client_kwargs = {"api_key": llm.api_key, "timeout": 15}
            if llm.base_url:
                client_kwargs["base_url"] = llm.base_url

            client = AsyncOpenAI(**client_kwargs)
            resp = await client.chat.completions.create(
                model=llm.model,
                messages=messages,
                max_tokens=10,
                temperature=0.1,
            )
            content = resp.choices[0].message.content.strip()
            return {"status": "ok", "message": f"✅ {llm.provider_display()} respondendo! Resposta: {content[:100]}"}

    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "unauthorized" in error_msg.lower() or "authentication" in error_msg.lower():
            raise HTTPException(status_code=400, detail=f"❌ Erro de autenticação. Verifique sua API Key.")
        if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
            raise HTTPException(status_code=408, detail=f"❌ Tempo limite excedido. Verifique a URL e conectividade.")
        raise HTTPException(status_code=400, detail=f"❌ Erro: {error_msg[:200]}")


@app.get("/api/config/env")
async def get_env_info():
    """Retorna informações do ambiente (sem dados sensíveis)."""
    config = _get_config()
    data_dir = Path(config.data_dir)
    config_file = data_dir / "config.yml"
    env_file = data_dir / ".env"

    return {
        "version": "0.1.0",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "hostname": platform.node(),
        "data_dir": str(data_dir),
        "config_file_exists": config_file.exists(),
        "env_file_exists": env_file.exists(),
        "data_dir_size_mb": _get_dir_size_mb(data_dir),
        "workers_count": len(orchestrator._workers) if orchestrator else 0,
    }


def _get_dir_size_mb(path: Path) -> float:
    """Calcula tamanho aproximado do diretório em MB."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except Exception:
        pass
    return round(total / (1024 * 1024), 2)


# ═══════════════════════════════════════════════════════════
# 🤖 WORKERS
# ═══════════════════════════════════════════════════════════

@app.get("/api/status")
async def get_status():
    """Retorna status completo do sistema."""
    if not orchestrator:
        return JSONResponse({"error": "Orchestrator não inicializado"}, status_code=503)
    return await orchestrator.get_system_status()


@app.post("/api/workers")
async def create_worker(data: WorkerCreate):
    """Cria um novo worker."""
    if not orchestrator:
        return JSONResponse({"error": "Orchestrator não inicializado"}, status_code=503)
    worker = await orchestrator.add_worker(
        name=data.name,
        role=data.role,
        description=data.description,
        system_prompt=data.system_prompt,
        autonomous=data.autonomous,
    )
    return worker.get_info()


@app.delete("/api/workers/{worker_id}")
async def delete_worker(worker_id: str):
    """Remove um worker."""
    if not orchestrator:
        return JSONResponse({"error": "Orchestrator não inicializado"}, status_code=503)
    await orchestrator.remove_worker(worker_id)
    return {"status": "removed", "id": worker_id}


@app.post("/api/workers/{worker_id}/pause")
async def pause_worker(worker_id: str):
    """Pausa um worker."""
    if not orchestrator:
        return JSONResponse({"error": "Orchestrator não inicializado"}, status_code=503)
    await orchestrator.pause_worker(worker_id)
    return {"status": "paused"}


@app.post("/api/workers/{worker_id}/resume")
async def resume_worker(worker_id: str):
    """Retoma um worker."""
    if not orchestrator:
        return JSONResponse({"error": "Orchestrator não inicializado"}, status_code=503)
    await orchestrator.resume_worker(worker_id)
    return {"status": "resumed"}


@app.get("/api/workers/{worker_id}/memory")
async def get_worker_memory(worker_id: str, category: str = "short_term", limit: int = 10):
    """Recupera memória de um worker."""
    if not orchestrator:
        return JSONResponse({"error": "Orchestrator não inicializado"}, status_code=503)
    memory = await orchestrator.get_worker_memory(worker_id, category, limit)
    return {"worker_id": worker_id, "category": category, "items": memory}


# ═══════════════════════════════════════════════════════════
# 📋 TAREFAS
# ═══════════════════════════════════════════════════════════

@app.post("/api/tasks")
async def delegate_task(data: TaskDelegate):
    """Delega uma tarefa para um worker."""
    if not orchestrator:
        return JSONResponse({"error": "Orchestrator não inicializado"}, status_code=503)
    task = await orchestrator.delegate_task(
        description=data.description,
        worker_id=data.worker_id,
        role=data.role,
        priority=data.priority,
    )
    return {
        "id": task.id,
        "description": task.description,
        "assigned_to": task.assigned_to,
        "status": task.status,
        "result": task.result,
        "error": task.error,
    }


@app.post("/api/broadcast")
async def broadcast(data: BroadcastMsg):
    """Envia mensagem para todos os workers."""
    if not orchestrator:
        return JSONResponse({"error": "Orchestrator não inicializado"}, status_code=503)
    await orchestrator.broadcast_message(data.message)
    return {"status": "broadcasted", "message": data.message}


# ═══════════════════════════════════════════════════════════
# 🔌 WEBSOCKET
# ═══════════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para atualizações em tempo real."""
    await websocket.accept()
    connected_websockets.add(websocket)
    logger.info(f"🔌 WebSocket conectado ({len(connected_websockets)} total)")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("action") == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg.get("action") == "get_status":
                if orchestrator:
                    status = await orchestrator.get_system_status()
                    await websocket.send_json({"type": "status", "data": status})

    except WebSocketDisconnect:
        connected_websockets.discard(websocket)
        logger.info(f"🔌 WebSocket desconectado ({len(connected_websockets)} restantes)")


async def broadcast_status():
    """Envia status atualizado para todos os WebSockets conectados."""
    if not orchestrator or not connected_websockets:
        return
    status = await orchestrator.get_system_status()
    dead = set()
    for ws in connected_websockets:
        try:
            await ws.send_json({"type": "status_update", "data": status})
        except Exception:
            dead.add(ws)
    connected_websockets -= dead


# ═══════════════════════════════════════════════════════════
# 🚀 MAIN
# ═══════════════════════════════════════════════════════════

def main(host: str = "0.0.0.0", port: int = 8200):
    """Inicia o servidor do dashboard."""
    import uvicorn
    print(f"""
╔══════════════════════════════════════════════════╗
║     🌐 NexusClaw Orchestra Dashboard            ║
║                                                  ║
║     http://{host}:{port}                        ║
║     WebSocket: ws://{host}:{port}/ws            ║
║                                                  ║
║     📋 API:                                      ║
║     GET  /api/config        — Configuração       ║
║     PUT  /api/config        — Salvar config      ║
║     POST /api/config/test-llm — Testar LLM      ║
║     GET  /api/config/env    — Info do ambiente   ║
║     GET  /api/status        — Status do sistema  ║
║     POST /api/workers       — Criar worker      ║
║     POST /api/tasks         — Delegar tarefa    ║
║     POST /api/broadcast     — Broadcast         ║
╚══════════════════════════════════════════════════╝
""")
    uvicorn.run(
        "nexus_claw.dashboard.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
