"""Dashboard Web do NexusClaw Orchestra.

Servidor FastAPI com WebSocket para status em tempo real.
Interface para gerenciar workers, tarefas e memória.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nexus_claw.orchestra.orchestrator import OrchestratorAgent

logger = logging.getLogger("nexus_claw.dashboard")

# Caminho absoluto para os arquivos estáticos
_PACKAGE_DIR = Path(__file__).parent
_STATIC_DIR = _PACKAGE_DIR / "static"

# ─── Models ───────────────────────────────────────────────────

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

# ─── App State ────────────────────────────────────────────────

orchestrator: Optional[OrchestratorAgent] = None
connected_websockets: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa o orquestrador na inicialização do servidor."""
    global orchestrator
    orchestrator = OrchestratorAgent()
    await orchestrator.start()

    # Workers padrão
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

# ─── App ──────────────────────────────────────────────────────

app = FastAPI(
    title="NexusClaw Orchestra Dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files (HTML, CSS, JS)
_STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ─── API Routes ──────────────────────────────────────────────

@app.get("/")
async def get_dashboard():
    """Serve o dashboard HTML."""
    html_file = _STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text())
    return HTMLResponse("<h1>NexusClaw Dashboard</h1><p>Build the UI...</p>")


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


# ─── WebSocket ───────────────────────────────────────────────

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


# ─── Main ────────────────────────────────────────────────────

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
║     API:                                         ║
║     GET  /api/status         — Status do sistema ║
║     POST /api/workers        — Criar worker      ║
║     POST /api/tasks          — Delegar tarefa    ║
║     POST /api/broadcast      — Broadcast mensagem║
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
