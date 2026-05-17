# 🦀 NexusClaw — Autonomous AI Assistant with Persistent Memory

<p align="center">
  <img src="https://img.shields.io/github/stars/Jailtonfonseca/nexus-claw?style=social" alt="GitHub stars">
  <img src="https://img.shields.io/github/license/Jailtonfonseca/nexus-claw" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/status-alpha-yellow" alt="Status">
</p>

<p align="center">
  <b>🤖 Seu assistente pessoal autônomo com memória que nunca esquece.</b>
  <br>
  Funciona 24/7, aprende continuamente, mantém memória persistente entre sessões.
</p>

---

## ✨ Destaques

- 🧠 **Memória Persistente** — guarda tudo em arquivos Markdown. Nada se perde entre sessões.
- 🔌 **Multi-LLM** — OpenAI, Anthropic, Ollama, ou qualquer API compatível.
- 🗂️ **Memória Organizada** — categorias hierárquicas (core, long_term, short_term, working).
- 🔍 **Busca Inteligente** — busca textual + semântica (ChromaDB opcional).
- 📦 **Sistema de Skills** — plugins extensíveis em Python.
- 💻 **CLI Completa** — modo interativo, tarefa única ou daemon.
- 🚀 **Local-First** — 100% privado, zero dependência de nuvem.
- 🎨 **Interface Rica** — logs coloridos, tabelas, painéis com Rich+Typer.

## 🚀 Quick Start

```bash
# Instalar
pip install nexus-claw

# Modo interativo
nexus --interactive

# Executar tarefa única
nexus run --task "Pesquise as últimas notícias de IA"

# Modo daemon (execução contínua)
nexus run --daemon

# Ver memória
nexus memory
nexus memory --search "aprendizados importantes"
```

## 📦 Instalação

### Via pip (em breve)

```bash
pip install nexus-claw
```

### Da fonte

```bash
git clone https://github.com/Jailtonfonseca/nexus-claw.git
cd nexus-claw
pip install -e ".[dev]"
```

## 🗺️ Arquitetura

```
nexus-claw/
├── src/nexus_claw/
│   ├── core/            # Agente principal e tipos
│   │   ├── agent.py     # NexusAgent — coração do sistema
│   │   └── types.py     # Task, TaskResult, AgentContext
│   ├── memory/          # 🧠 Sistema de memória persistente
│   │   ├── engine.py    # MemoryEngine — ciclo de vida da memória
│   │   └── store.py     # FileMemoryStore — persistência em Markdown
│   ├── llm/             # 🤖 Integração com LLMs
│   │   └── client.py    # LLMClient — multi-provedor com fallback
│   ├── skills/          # 🔌 Sistema de plugins
│   │   └── __init__.py  # SkillRegistry
│   ├── config/          # ⚙️ Configuração
│   │   └── settings.py  # NexusConfig, load_config
│   ├── orchestra/       # 🎪 Multi-Agent Orchestration
│   │   ├── orchestrator.py  # OrchestratorAgent — CEO digital
│   │   ├── worker.py        # WorkerAgent — agentes independentes
│   │   └── registry.py      # AgentRegistry — registro persistente
│   ├── dashboard/       # 🌐 Web Dashboard
│   │   ├── server.py    # FastAPI + WebSocket
│   │   └── static/      # HTML/CSS/JS frontend
│   └── cli/             # 💻 Interface de linha de comando
│       └── main.py      # CLI com Typer + Rich
├── pyproject.toml
└── README.md
```

## 🎪 Multi-Agent Orchestra

O NexusClaw possui um sistema de **orquestração multi-agente** que permite gerenciar múltiplos workers autônomos.

### Conceitos

| Componente | Descrição |
|-----------|-----------|
| 🎪 **OrchestratorAgent** | CEO digital — gerencia workers, delega tarefas, coordena comunicação |
| 🤖 **WorkerAgent** | Agente independente com memória própria e capacidade de ação |
| 📋 **AgentRegistry** | Registro persistente de todos os agentes no sistema |

### Workers

Cada Worker possui:
- 🧠 **Memória persistente** própria
- 🎭 **Papel/função** definida (analyst, creator, assistant...)
- ⚡ **Modo autônomo** — decide o que fazer sem supervisão
- 🔒 **Isolamento** — cada worker tem seu próprio contexto e histórico

### Uso via CLI

```bash
# Iniciar o Orchestrator com workers padrão
nexus orchestra --workers 3

# Listar workers e status
nexus orchestra status

# Delegar tarefa específica para um worker
nexus orchestra task "Pesquise tendências de IA" --role analyst
```

## 🌐 Web Dashboard

Interface web para gerenciar o sistema de orquestração visualmente.

```bash
# Instalar com dependências do dashboard
pip install "nexus-claw[dashboard]"

# Iniciar o dashboard
nexus dashboard
# Acesse: http://localhost:8200

# Porta customizada
nexus dashboard --port 8080 --host 127.0.0.1
```

### Funcionalidades do Dashboard

- 📊 **Status em tempo real** via WebSocket
- 🤖 **Gerenciar Workers**: criar, pausar, retomar, remover
- 📋 **Delegar tarefas** para workers específicos
- 🧠 **Consultar memória** de cada worker
- 📢 **Broadcast** de mensagens para todos os workers
- 🔄 **Auto-refresh** a cada 5 segundos

### API REST

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/status` | Status completo do sistema |
| POST | `/api/workers` | Criar novo worker |
| DELETE | `/api/workers/{id}` | Remover worker |
| POST | `/api/workers/{id}/pause` | Pausar worker |
| POST | `/api/workers/{id}/resume` | Retomar worker |
| GET | `/api/workers/{id}/memory` | Memória do worker |
| POST | `/api/tasks` | Delegar tarefa |
| POST | `/api/broadcast` | Broadcast para workers |

## 🧠 Sistema de Memória

Inspirado pelo [memU](https://github.com/memU) e pela arquitetura file-system-style do OpenClaw.

### Categorias

| Categoria | Persistência | Uso |
|-----------|-------------|-----|
| `core`    | 🔒 Permanente | Identidade, regras, configuração |
| `long_term` | 💾 Importante | Aprendizados marcados como relevantes |
| `short_term` | 📝 Sessões | Últimas ações e interações |
| `working` | ⚡ Volátil | Contexto da sessão atual |
| `learned` | 🧠 Automático | Padrões descobertos pelo agente |

### Formato
Cada memória é um arquivo Markdown com frontmatter YAML:

```markdown
---
id: 20260517_123456_abcd
category: long_term
timestamp: 2026-05-17T12:34:56
priority: high
---

# Aprendizado: Otimização de Prompts

Ao usar chain-of-thought, a precisão aumentou 40%...
```

## ⚙️ Configuração

Via variáveis de ambiente:

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
export LLM_MODEL=gpt-4o-mini
export NEXUS_WAKE_INTERVAL=30
```

Ou arquivo YAML (`~/.nexus/config.yml`):

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  api_key: sk-...
memory:
  backend: file
  base_dir: ~/.nexus/memory
```

## 🛠️ Desenvolvimento

```bash
# Setup dev
pip install -e ".[dev]"

# Testes
pytest

# Lint
ruff check src/
black src/

# Type check
mypy src/
```

## 📜 Licença

MIT © [Jailton Fonseca](https://github.com/Jailtonfonseca)

---

<p align="center">
  <sub>Feito com ☕ e 🦀 por Jailton Fonseca</sub>
  <br>
  <sub>Inspirado por OpenClaw, memU e a comunidade open-source de IA</sub>
</p>
