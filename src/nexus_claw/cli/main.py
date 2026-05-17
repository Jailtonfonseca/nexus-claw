"""CLI principal do NexusClaw com Typer."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from nexus_claw import __version__
from nexus_claw.config.settings import load_config
from nexus_claw.core.agent import NexusAgent
from nexus_claw.core.types import Task

app = typer.Typer(
    name="nexus-claw",
    help="NexusClaw — Autonomous AI Assistant with Persistent Memory",
    add_completion=False,
)
console = Console()

BANNER = """
╔═══════════════════════════════════════════╗
║     ███╗   ██╗███████╗██╗  ██╗██╗   ██╗ ███████╗
║     ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║ ██╔════╝
║     ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║ ███████╗
║     ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║ ╚════██║
║     ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝ ███████║
║     ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝  ╚══════╝
║                                                 ║
║  Autonomous AI Assistant                        ║
║  with Persistent Memory                         ║
║  v{version:<39}║
╚═══════════════════════════════════════════╝
"""


def _setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )


@app.callback()
def main_callback(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Caminho do arquivo de configuração"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log detalhado"),
):
    """NexusClaw CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose


@app.command()
def version():
    """Mostra a versão do NexusClaw."""
    console.print(f"NexusClaw v{__version__}")


@app.command()
def run(
    ctx: typer.Context,
    name: str = typer.Option("Nexus", "--name", "-n", help="Nome do agente"),
    task: Optional[str] = typer.Option(
        None, "--task", "-t", help="Tarefa única a executar"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Modo interativo"
    ),
    daemon: bool = typer.Option(
        False, "--daemon", "-d", help="Modo daemon (execução contínua)"
    ),
):
    """Inicia o agente NexusClaw."""
    _setup_logging("DEBUG" if ctx.obj.get("verbose") else "INFO")
    console.print(Panel(BANNER.format(version=__version__), style="bold cyan"))

    config = load_config(str(ctx.obj["config_path"]) if ctx.obj["config_path"] else None)
    agent = NexusAgent(config=config, name=name)

    asyncio.run(_run_agent(agent, task, interactive, daemon))


@app.command()
def memory(
    ctx: typer.Context,
    category: str = typer.Option("all", "--cat", "-c", help="Categoria de memória"),
    limit: int = typer.Option(10, "--limit", "-l", help="Limite de itens"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Buscar na memória"),
):
    """Gerencia a memória persistente."""
    _setup_logging()
    config = load_config()

    async def _show_memory():
        from nexus_claw.memory.engine import MemoryEngine
        mem = MemoryEngine(config.memory)
        await mem.initialize()

        if search:
            console.print(f"\n🔍 Buscando: '{search}'")
            results = await mem.search(search, limit=limit)
            for r in results:
                console.print(f"  • {r[:200]}")
            return

        if category == "all":
            table = Table(title="📦 Categorias de Memória")
            table.add_column("Categoria", style="cyan")
            table.add_column("Itens", style="green")
            table.add_column("Diretório", style="dim")

            for cat_name in ["core", "long_term", "short_term", "working", "learned"]:
                cat = await mem.get_category(cat_name)
                if cat:
                    count = len(list(cat.path.glob("*.md")))
                    table.add_row(cat_name, str(count), str(cat.path))
            console.print(table)
        else:
            items = await mem.get_recent(category, limit)
            console.print(f"\n📝 Últimos {len(items)} itens em '{category}':")
            for item in items:
                console.print(Panel(item[:500], style="dim"))

    asyncio.run(_show_memory())


async def _run_agent(
    agent: NexusAgent,
    task: Optional[str] = None,
    interactive: bool = False,
    daemon: bool = False,
):
    """Executa o agente com base nos parâmetros."""
    await agent.start()

    if task:
        # Modo tarefa única
        t = Task(id="manual", description=task, priority=1)
        result = await agent.process_task(t)
        if result.success:
            console.print(f"\n✅ Resultado:\n{result.output}")
        else:
            console.print(f"\n❌ Erro: {result.error}")

    elif interactive:
        # Modo interativo
        console.print("\n💬 Modo interativo. Digite 'sair' para encerrar.\n")
        while True:
            try:
                user_input = console.input("[bold cyan]❯[/bold cyan] ")
                if user_input.lower() in ("sair", "exit", "quit"):
                    break
                t = Task(id="interactive", description=user_input, priority=0)
                result = await agent.process_task(t)
                if result.success:
                    console.print(f"\n{result.output}\n")
                else:
                    console.print(f"\n[red]Erro: {result.error}[/red]\n")
            except (KeyboardInterrupt, EOFError):
                break

    elif daemon:
        # Modo daemon
        console.print("🔄 Modo daemon — executando ciclos automáticos...")
        try:
            while True:
                t = Task(
                    id=f"cycle_{len(agent.context.state)}",
                    description="Verificar tarefas pendentes e executar ações automáticas",
                    priority=0,
                )
                result = await agent.process_task(t)
                if result.success:
                    console.print(f"⏱️  Ciclo completo: {result.duration_ms:.0f}ms")
                await asyncio.sleep(agent.config.wake_interval_minutes * 60)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass

    else:
        console.print("[yellow]Use --task, --interactive ou --daemon[/yellow]")

    await agent.stop()


if __name__ == "__main__":
    app()
