/* NexusClaw Orchestra Dashboard — Frontend */
/* ============================================ */

let ws = null;
let statusData = null;
let autoRefresh = null;
let configData = null;

// ─── Init ──────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  connectWebSocket();
  setupNavigation();
  setupModals();
  setupModelSuggestions();
  refreshStatus();
  autoRefresh = setInterval(refreshStatus, 5000);
  loadEnvInfo();
});

// ─── WebSocket ─────────────────────────────────────────────

function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => {
    console.log('🔌 WebSocket conectado');
    el('orchestrator-status').className = 'status-dot online';
    el('orchestrator-label').textContent = 'Online';
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === 'status' || msg.type === 'status_update') {
        statusData = msg.data;
        renderAll();
      }
    } catch (e) {}
  };

  ws.onclose = () => {
    console.log('🔌 WebSocket desconectado, reconectando...');
    el('orchestrator-status').className = 'status-dot';
    el('orchestrator-label').textContent = 'Desconectado';
    setTimeout(connectWebSocket, 3000);
  };
}

// ─── Shorthand ─────────────────────────────────────────────

function el(id) { return document.getElementById(id); }

// ─── Navigation ────────────────────────────────────────────

function setupNavigation() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      item.classList.add('active');

      const view = item.dataset.view;
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      el(`view-${view}`).classList.add('active');

      const titles = { dashboard: 'Dashboard', workers: 'Workers', tasks: 'Tarefas', memory: 'Memória', settings: 'Config' };
      el('view-title').textContent = titles[view] || view;

      if (view === 'workers') renderWorkersFull();
      if (view === 'tasks') renderTasksFull();
      if (view === 'memory') loadMemoryWorkerSelect();
      if (view === 'settings') { loadConfig(); loadEnvInfo(); }
    });
  });
}

// ─── API Calls ─────────────────────────────────────────────

async function api(path, method = 'GET', body = null) {
  try {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(path, opts);
    const data = await res.json();
    if (!res.ok && data.detail) throw new Error(data.detail);
    return data;
  } catch (e) {
    console.error('API error:', e);
    throw e;
  }
}

async function refreshStatus() {
  try {
    const data = await api('/api/status');
    if (data && data.orchestrator) {
      statusData = data;
      renderAll();
    }
  } catch (e) {}
}

// ─── Render ────────────────────────────────────────────────

function renderAll() {
  if (!statusData) return;
  renderStats();
  renderWorkersDash();
  renderTasks();
  updateBadges();
}

function renderStats() {
  const workers = statusData.workers || [];
  const queue = statusData.queue || [];
  const totalTasks = workers.reduce((s, w) => s + (w.tasks_completed || 0), 0);
  const active = workers.filter(w => w.status === 'idle' || w.status === 'running').length;

  el('stat-workers').textContent = workers.length;
  el('stat-completed').textContent = totalTasks;
  el('stat-queue').textContent = queue.length;
  el('stat-active').textContent = active;
}

function renderWorkersDash() {
  const grid = el('workers-grid-dash');
  const workers = statusData?.workers || [];
  if (workers.length === 0) {
    grid.innerHTML = '<div class="empty"><div class="icon">🤖</div><p>Nenhum worker ainda. Crie um!</p></div>';
    return;
  }
  grid.innerHTML = workers.slice(0, 6).map(w => createWorkerCard(w)).join('');
}

function renderWorkersFull() {
  const grid = el('workers-grid-full');
  const workers = statusData?.workers || [];
  if (workers.length === 0) {
    grid.innerHTML = '<div class="empty"><div class="icon">🤖</div><p>Nenhum worker ainda. Clique em "+ Novo Worker"</p></div>';
    return;
  }
  grid.innerHTML = workers.map(w => createWorkerCard(w)).join('');
}

function createWorkerCard(w) {
  const statusClass = `status-${w.status}`;
  const labels = { idle: '🟢 Pronto', running: '🔄 Executando', paused: '⏸️ Pausado', error: '❌ Erro', sleeping: '💤 Dormindo' };
  return `
    <div class="worker-card">
      <div class="header">
        <div>
          <div class="name">${w.name}</div>
          <span class="role">${w.role}</span>
        </div>
        <span class="status-badge ${statusClass}">${labels[w.status] || w.status}</span>
      </div>
      <div class="stats">
        <span>✅ ${w.tasks_completed || 0} tarefas</span>
        <span>🆔 ${w.id}</span>
      </div>
      <div class="actions">
        <button class="btn btn-secondary" onclick="showWorkerMemory('${w.id}')">🧠 Memória</button>
        <button class="btn btn-secondary" onclick="delegateToWorker('${w.id}')">📋 Tarefa</button>
        ${w.status === 'paused'
          ? `<button class="btn btn-primary" onclick="resumeWorker('${w.id}')">▶️ Retomar</button>`
          : `<button class="btn btn-secondary" onclick="pauseWorker('${w.id}')">⏸️ Pausar</button>`
        }
        <button class="btn btn-danger" onclick="removeWorker('${w.id}')">✕</button>
      </div>
    </div>
  `;
}

function renderTasks() {
  const tbody = el('tasks-tbody');
  const tasks = statusData?.queue || [];
  if (tasks.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty">Nenhuma tarefa ainda</td></tr>';
    return;
  }
  const sStyles = { pending: 'status-idle', completed: 'status-running', failed: 'status-error' };
  const sLabels = { pending: '⏳ Pendente', completed: '✅ Completa', failed: '❌ Falhou' };
  tbody.innerHTML = tasks.slice(-5).reverse().map(t => `
    <tr><td>${t.description}</td>
    <td>${t.assigned_to ? t.assigned_to.substring(0, 8) : '—'}</td>
    <td><span class="status-badge ${sStyles[t.status] || ''}">${sLabels[t.status] || t.status}</span></td>
    <td>${new Date(t.created_at).toLocaleTimeString()}</td></tr>
  `).join('');
}

function renderTasksFull() {
  const tbody = el('tasks-full-tbody');
  const tasks = statusData?.queue || [];
  if (tasks.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">Nenhuma tarefa ainda</td></tr>';
    return;
  }
  const sLabels = { pending: '⏳ Pendente', completed: '✅ Completa', failed: '❌ Falhou' };
  tbody.innerHTML = tasks.slice().reverse().map(t => `
    <tr><td style="font-family:monospace;font-size:11px">${t.id.substring(0,12)}</td>
    <td>${t.description}</td>
    <td>${t.assigned_to ? t.assigned_to.substring(0,8) : '—'}</td>
    <td>${'🔵'.repeat(t.priority+1)}</td>
    <td>${sLabels[t.status] || t.status}</td>
    <td>${new Date(t.created_at).toLocaleString()}</td></tr>
  `).join('');
}

function updateBadges() {
  const workers = statusData?.workers || [];
  const tasks = statusData?.queue || [];
  el('worker-count').textContent = workers.length;
  el('task-count').textContent = tasks.length;
}

// ─── Worker Actions ────────────────────────────────────────

async function pauseWorker(id) { await api(`/api/workers/${id}/pause`, 'POST'); await refreshStatus(); }
async function resumeWorker(id) { await api(`/api/workers/${id}/resume`, 'POST'); await refreshStatus(); }
async function removeWorker(id) { if (!confirm('Remover este worker?')) return; await api(`/api/workers/${id}`, 'DELETE'); await refreshStatus(); }

function delegateToWorker(workerId) {
  const sel = el('task-worker-select');
  if (sel) sel.value = workerId;
  showModal('new-task');
}

async function showWorkerMemory(workerId) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  qs('[data-view="memory"]').classList.add('active');
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  el('view-memory').classList.add('active');
  el('view-title').textContent = 'Memória';
  await loadMemoryWorkerSelect();
  el('memory-worker-select').value = workerId;
  await loadMemory();
}

async function loadMemoryWorkerSelect() {
  const workers = statusData?.workers || [];
  el('memory-worker-select').innerHTML = '<option value="">Selecione...</option>' +
    workers.map(w => `<option value="${w.id}">${w.name} (${w.role})</option>`).join('');
}

async function loadMemory() {
  const workerId = el('memory-worker-select').value;
  const category = el('memory-category-select').value;
  const content = el('memory-content');
  if (!workerId) { content.textContent = 'Selecione um worker para ver a memória.'; return; }
  content.textContent = '🔄 Carregando...';
  const data = await api(`/api/workers/${workerId}/memory?category=${category}&limit=10`);
  content.textContent = (data && data.items) ? (data.items.join('\n\n---\n\n') || '🧠 Nenhuma memória.') : '❌ Erro ao carregar memória.';
}

function qs(s) { return document.querySelector(s); }

// ─── Broadcast ─────────────────────────────────────────────

async function broadcast() {
  const input = el('broadcast-input');
  if (!input.value.trim()) return;
  await api('/api/broadcast', 'POST', { message: input.value });
  input.value = '';
  alert('📢 Mensagem enviada para todos os workers!');
}

// ─── Modals ────────────────────────────────────────────────

function setupModals() {
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
}

function showModal(type) {
  const overlay = el('modal-overlay');
  const title = el('modal-title');
  const body = el('modal-body');

  if (type === 'new-worker') {
    title.textContent = '🤖 Novo Worker';
    body.innerHTML = `
      <div class="form-group"><label>Nome</label><input type="text" id="worker-name" placeholder="Ex: Analista"></div>
      <div class="form-group"><label>Papel</label><input type="text" id="worker-role" placeholder="analyst, creator, assistant"></div>
      <div class="form-group"><label>Descrição</label><textarea id="worker-desc" placeholder="O que faz?"></textarea></div>
      <div class="form-group"><label>System Prompt</label><textarea id="worker-prompt" placeholder="Instruções..."></textarea></div>
      <div class="form-group"><label><input type="checkbox" id="worker-autonomous"> Modo Autônomo</label></div>
      <button class="btn btn-primary" onclick="createWorker()" style="width:100%;margin-top:8px">🤖 Criar Worker</button>`;
  } else if (type === 'new-task') {
    title.textContent = '📋 Nova Tarefa';
    const workers = statusData?.workers || [];
    body.innerHTML = `
      <div class="form-group"><label>Descrição</label><textarea id="task-desc" placeholder="O que precisa ser feito?"></textarea></div>
      <div class="form-group"><label>Worker</label><select id="task-worker-select"><option value="">— Orchestrator decide —</option>
        ${workers.map(w => `<option value="${w.id}">${w.name} (${w.role})</option>`).join('')}</select></div>
      <div class="form-group"><label>Prioridade</label><select id="task-priority">
        <option value="0">🟢 Normal</option><option value="1">🟡 Alta</option><option value="2">🔴 Crítica</option></select></div>
      <button class="btn btn-primary" onclick="createTask()" style="width:100%;margin-top:8px">📋 Delegar</button>`;
  }
  overlay.classList.add('open');
}

function closeModal() { el('modal-overlay').classList.remove('open'); }

async function createWorker() {
  const name = el('worker-name').value;
  const role = el('worker-role').value;
  if (!name || !role) { alert('Nome e papel são obrigatórios!'); return; }
  await api('/api/workers', 'POST', {
    name, role,
    description: el('worker-desc').value,
    system_prompt: el('worker-prompt').value,
    autonomous: el('worker-autonomous').checked,
  });
  closeModal();
  await refreshStatus();
}

async function createTask() {
  const desc = el('task-desc').value;
  if (!desc) { alert('Descrição é obrigatória!'); return; }
  const sel = el('task-worker-select');
  const result = await api('/api/tasks', 'POST', {
    description: desc,
    worker_id: sel ? sel.value : null,
    priority: parseInt(el('task-priority').value),
  });
  closeModal();
  if (result) alert(`✅ Tarefa concluída!\n\nWorker: ${result.assigned_to || 'N/A'}\nStatus: ${result.status}\n\n${result.result || result.error || ''}`);
  await refreshStatus();
}


// ═══════════════════════════════════════════════════════════════
// ⚙️ CONFIGURAÇÃO VISUAL
// ═══════════════════════════════════════════════════════════════

// ─── Tabs ─────────────────────────────────────────────────

function switchTab(tabId) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  qs(`.tab[data-tab="${tabId}"]`).classList.add('active');
  el(tabId).classList.add('active');
}

// ─── Load Config ──────────────────────────────────────────

async function loadConfig() {
  try {
    el('config-status-msg').textContent = '🔄 Carregando...';
    const data = await api('/api/config');
    configData = data;
    populateConfigForm(data);
    el('config-status-msg').textContent = '✅ Configuração carregada';
  } catch (e) {
    el('config-status-msg').textContent = '❌ Erro ao carregar: ' + e.message;
  }
}

// ─── Populate Form ────────────────────────────────────────

function populateConfigForm(data) {
  // LLM
  if (data.llm) {
    el('cfg-llm-provider').value = data.llm.provider || 'openai';
    el('cfg-llm-model').value = data.llm.model || '';
    // API Key: coloca placeholder "salva" se houver key, nunca o valor mascarado
    const apiKeyInput = el('cfg-llm-apikey');
    if (data.llm.api_key && data.llm.api_key.includes('****')) {
      apiKeyInput.value = '';
      apiKeyInput.placeholder = '🔑 Chave já salva. Digite para substituir';
    } else {
      apiKeyInput.value = data.llm.api_key || '';
      apiKeyInput.placeholder = 'sk-... ou leave empty for Ollama';
    }
    el('cfg-llm-baseurl').value = data.llm.base_url || '';
    el('cfg-llm-temperature').value = data.llm.temperature || 0.7;
    el('cfg-llm-temp-value').textContent = data.llm.temperature || 0.7;
    el('cfg-llm-maxtokens').value = data.llm.max_tokens || 4096;
    onLLMProviderChange();
  }

  // Memory
  if (data.memory) {
    el('cfg-memory-backend').value = data.memory.backend || 'file';
    el('cfg-memory-basedir').value = data.memory.base_dir || '';
    el('cfg-memory-vectormodel').value = data.memory.vector_model || '';
    el('cfg-memory-maxfiles').value = data.memory.max_context_files || 50;
    el('cfg-memory-autosummarize').checked = data.memory.auto_summarize !== false;
  }

  // Agent
  el('cfg-agent-name').value = data.name || 'Nexus';
  el('cfg-agent-loglevel').value = data.log_level || 'INFO';
  el('cfg-agent-wakeinterval').value = data.wake_interval_minutes || 30;
}

// ─── Gather Config from Form ──────────────────────────────

function gatherConfig() {
  return {
    name: el('cfg-agent-name').value || 'Nexus',
    log_level: el('cfg-agent-loglevel').value || 'INFO',
    wake_interval_minutes: parseInt(el('cfg-agent-wakeinterval').value) || 30,
    llm: {
      provider: el('cfg-llm-provider').value,
      model: el('cfg-llm-model').value,
      api_key: el('cfg-llm-apikey').value,
      base_url: el('cfg-llm-baseurl').value,
      temperature: parseFloat(el('cfg-llm-temperature').value) || 0.7,
      max_tokens: parseInt(el('cfg-llm-maxtokens').value) || 4096,
    },
    memory: {
      backend: el('cfg-memory-backend').value,
      base_dir: el('cfg-memory-basedir').value,
      vector_model: el('cfg-memory-vectormodel').value,
      max_context_files: parseInt(el('cfg-memory-maxfiles').value) || 50,
      auto_summarize: el('cfg-memory-autosummarize').checked,
    },
  };
}

// ─── Save Config ──────────────────────────────────────────

async function saveConfig() {
  const btn = document.querySelector('.config-footer .btn-primary');
  btn.textContent = '💾 Salvando...';
  btn.disabled = true;

  try {
    const body = gatherConfig();

    // Segurança: se o campo de API key está vazio e já havia uma chave salva,
    // não envie string vazia (não sobrescreve a chave existente)
    if (!body.llm.api_key && configData && configData.llm && configData.llm.api_key) {
      delete body.llm.api_key;
    }

    const result = await api('/api/config', 'PUT', body);
    el('config-status-msg').textContent = '✅ ' + (result.message || 'Salvo com sucesso!');
    configData = result.config;
    // Atualiza campos com dados mascarados de volta
    if (result.config) populateConfigForm(result.config);
  } catch (e) {
    el('config-status-msg').textContent = '❌ Erro ao salvar: ' + e.message;
  }

  btn.textContent = '💾 Salvar Configuração';
  btn.disabled = false;
}

// ─── LLM Provider Change ──────────────────────────────────

const MODEL_SUGGESTIONS = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4o-2024-11-20', 'gpt-4-turbo', 'gpt-3.5-turbo', 'o1', 'o1-mini', 'o3-mini'],
  anthropic: ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229'],
  ollama: ['llama3.2', 'llama3.1', 'mistral', 'mixtral', 'codellama', 'phi3', 'gemma2', 'qwen2', 'deepseek-coder'],
  deepseek: ['deepseek-chat', 'deepseek-coder', 'deepseek-reasoner'],
  google: ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'],
  custom: ['gpt-4o-mini', 'gpt-4o', 'claude-3-5-sonnet'],
};

function onLLMProviderChange() {
  const provider = el('cfg-llm-provider').value;
  const showKey = !['ollama'].includes(provider);
  const showBaseUrl = ['ollama', 'custom'].includes(provider);

  // Mostra/esconde campos
  const keyGroup = el('cfg-llm-apikey').closest('.form-group');
  const urlGroup = el('cfg-llm-baseurl').closest('.form-group');
  if (keyGroup) keyGroup.style.display = showKey ? '' : 'none';
  if (urlGroup) urlGroup.style.display = showBaseUrl ? '' : 'none';

  // Sugestões de modelo
  const suggestions = MODEL_SUGGESTIONS[provider] || [];
  const container = el('model-suggestions');
  if (suggestions.length > 0) {
    container.innerHTML = suggestions.map(m =>
      `<div class="suggestion" onclick="selectModel('${m}')">${m}</div>`
    ).join('');
    container.classList.add('show');
  } else {
    container.classList.remove('show');
  }
}

function setupModelSuggestions() {
  // Esconde sugestões ao clicar em qualquer lugar fora do campo de modelo
  document.addEventListener('click', (e) => {
    const container = el('model-suggestions');
    const modelInput = el('cfg-llm-model');
    if (!e.target.closest('#cfg-llm-model-group') && !e.target.closest('.model-suggestions')) {
      container.classList.remove('show');
    }
  });

  // Esconde ao mudar de foco do input de modelo
  const modelInput = el('cfg-llm-model');
  if (modelInput) {
    modelInput.addEventListener('blur', () => {
      setTimeout(() => el('model-suggestions').classList.remove('show'), 200);
    });
    modelInput.addEventListener('focus', () => {
      const provider = el('cfg-llm-provider').value;
      const suggestions = MODEL_SUGGESTIONS[provider] || [];
      if (suggestions.length > 0) {
        el('model-suggestions').classList.add('show');
      }
    });
  }

  // Esconde ao focar em QUALQUER outro input da config
  document.querySelectorAll('.form-section input, .form-section select, .form-section textarea').forEach(input => {
    if (input.id !== 'cfg-llm-model') {
      input.addEventListener('focus', () => {
        el('model-suggestions').classList.remove('show');
      });
    }
  });

  // Limpa o placeholder mascarado da API key ao focar no campo
  const apiKeyInput = el('cfg-llm-apikey');
  if (apiKeyInput) {
    apiKeyInput.addEventListener('focus', function() {
      if (this.value.includes('****')) {
        this.value = '';
      }
    });
  }
}

function selectModel(model) {
  el('cfg-llm-model').value = model;
  el('model-suggestions').classList.remove('show');
}

// ─── Toggle Password ──────────────────────────────────────

function togglePassword(id) {
  const input = el(id);
  input.type = input.type === 'password' ? 'text' : 'password';
}

// ─── Test LLM ─────────────────────────────────────────────

async function testLLMConfig() {
  const resultEl = el('cfg-llm-test-result');
  resultEl.className = 'test-result loading';
  resultEl.textContent = '🔄 Testando conexão...';

  try {
    const body = {
      provider: el('cfg-llm-provider').value,
      model: el('cfg-llm-model').value,
      api_key: el('cfg-llm-apikey').value,
      base_url: el('cfg-llm-baseurl').value,
      temperature: parseFloat(el('cfg-llm-temperature').value) || 0.7,
      max_tokens: parseInt(el('cfg-llm-maxtokens').value) || 4096,
    };

    const result = await api('/api/config/test-llm', 'POST', body);
    resultEl.className = 'test-result success';
    resultEl.textContent = result.message || '✅ Conexão OK!';
  } catch (e) {
    resultEl.className = 'test-result error';
    resultEl.textContent = e.message || '❌ Falha na conexão';
  }
}

// ─── System Info ──────────────────────────────────────────

async function loadEnvInfo() {
  const info = el('sys-info');
  try {
    const data = await api('/api/config/env');
    info.innerHTML = `
      <div class="sys-row"><span class="sys-label">Versão</span><span class="sys-value">${data.version}</span></div>
      <div class="sys-row"><span class="sys-label">Python</span><span class="sys-value">${data.python}</span></div>
      <div class="sys-row"><span class="sys-label">Plataforma</span><span class="sys-value">${data.platform}</span></div>
      <div class="sys-row"><span class="sys-label">Hostname</span><span class="sys-value">${data.hostname}</span></div>
      <div class="sys-row"><span class="sys-label">Data Directory</span><span class="sys-value">${data.data_dir}</span></div>
      <div class="sys-row"><span class="sys-label">Config YAML</span>
        <span class="sys-value">${data.config_file_exists ? '✅ Existe' : '❌ Não existe (será criado ao salvar)'}</span></div>
      <div class="sys-row"><span class="sys-label">Tamanho dos Dados</span><span class="sys-value">${data.data_dir_size_mb} MB</span></div>
      <div class="sys-row"><span class="sys-label">Workers Ativos</span><span class="sys-value">${data.workers_count}</span></div>
    `;
  } catch (e) {
    info.innerHTML = `<div class="sys-row"><span class="sys-label">Erro</span><span class="sys-value">${e.message}</span></div>`;
  }
}

// ─── Quick Actions ────────────────────────────────────────

async function restartOrchestrator() {
  if (!confirm('Reiniciar o orquestrador? Isso vai parar todos os workers.')) return;
  el('config-status-msg').textContent = '🔄 Reiniciando servidor...';
  // Na prática, o servidor precisaria ser reiniciado externamente.
  // Por enquanto, apenas recarregamos o status.
  await refreshStatus();
  el('config-status-msg').textContent = '✅ Recarregado (reinicie o servidor manualmente para aplicar)';
}

async function reloadConfig() {
  await loadConfig();
  await loadEnvInfo();
}
