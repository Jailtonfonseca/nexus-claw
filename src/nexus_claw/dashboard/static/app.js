/* NexusClaw Orchestra Dashboard — Frontend */

let ws = null;
let statusData = null;
let autoRefresh = null;

// ─── Init ──────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  connectWebSocket();
  setupNavigation();
  setupModals();
  refreshStatus();
  autoRefresh = setInterval(refreshStatus, 5000);
});

// ─── WebSocket ─────────────────────────────────────────────

function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => {
    console.log('🔌 WebSocket conectado');
    document.getElementById('orchestrator-status').className = 'status-dot online';
    document.getElementById('orchestrator-label').textContent = 'Online';
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
    document.getElementById('orchestrator-status').className = 'status-dot';
    document.getElementById('orchestrator-label').textContent = 'Desconectado';
    setTimeout(connectWebSocket, 3000);
  };
}

// ─── Navigation ────────────────────────────────────────────

function setupNavigation() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();

      // Atualiza nav
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      item.classList.add('active');

      // Mostra view
      const view = item.dataset.view;
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById(`view-${view}`).classList.add('active');

      // Atualiza título
      const titles = { dashboard: 'Dashboard', workers: 'Workers', tasks: 'Tarefas', memory: 'Memória', settings: 'Config' };
      document.getElementById('view-title').textContent = titles[view] || view;

      if (view === 'workers') renderWorkersFull();
      if (view === 'tasks') renderTasksFull();
      if (view === 'memory') loadMemoryWorkerSelect();
    });
  });
}

// ─── API Calls ─────────────────────────────────────────────

async function api(path, method = 'GET', body = null) {
  try {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(path, opts);
    return await res.json();
  } catch (e) {
    console.error('API error:', e);
    return null;
  }
}

async function refreshStatus() {
  const data = await api('/api/status');
  if (data && data.orchestrator) {
    statusData = data;
    renderAll();
  }
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

  document.getElementById('stat-workers').textContent = workers.length;
  document.getElementById('stat-completed').textContent = totalTasks;
  document.getElementById('stat-queue').textContent = queue.length;
  document.getElementById('stat-active').textContent = active;
}

function renderWorkersDash() {
  const grid = document.getElementById('workers-grid-dash');
  const workers = statusData?.workers || [];

  if (workers.length === 0) {
    grid.innerHTML = '<div class="empty"><div class="icon">🤖</div><p>Nenhum worker ainda. Crie um!</p></div>';
    return;
  }

  grid.innerHTML = workers.slice(0, 6).map(w => createWorkerCard(w)).join('');
}

function renderWorkersFull() {
  const grid = document.getElementById('workers-grid-full');
  const workers = statusData?.workers || [];

  if (workers.length === 0) {
    grid.innerHTML = '<div class="empty"><div class="icon">🤖</div><p>Nenhum worker ainda. Clique em "+ Novo Worker"</p></div>';
    return;
  }

  grid.innerHTML = workers.map(w => createWorkerCard(w)).join('');
}

function createWorkerCard(w) {
  const statusClass = `status-${w.status}`;
  const statusLabels = { idle: '🟢 Pronto', running: '🔄 Executando', paused: '⏸️ Pausado', error: '❌ Erro', sleeping: '💤 Dormindo' };

  return `
    <div class="worker-card">
      <div class="header">
        <div>
          <div class="name">${w.name}</div>
          <span class="role">${w.role}</span>
        </div>
        <span class="status-badge ${statusClass}">${statusLabels[w.status] || w.status}</span>
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
  const tbody = document.getElementById('tasks-tbody');
  const tasks = statusData?.queue || [];

  if (tasks.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty">Nenhuma tarefa ainda</td></tr>';
    return;
  }

  const statusStyles = { pending: 'status-idle', completed: 'status-running', failed: 'status-error' };
  const statusLabels = { pending: '⏳ Pendente', completed: '✅ Completa', failed: '❌ Falhou' };

  tbody.innerHTML = tasks.slice(-5).reverse().map(t => `
    <tr>
      <td>${t.description}</td>
      <td>${t.assigned_to ? t.assigned_to.substring(0, 8) : '—'}</td>
      <td><span class="status-badge ${statusStyles[t.status] || ''}">${statusLabels[t.status] || t.status}</span></td>
      <td>${new Date(t.created_at).toLocaleTimeString()}</td>
    </tr>
  `).join('');
}

function renderTasksFull() {
  const tbody = document.getElementById('tasks-full-tbody');
  const tasks = statusData?.queue || [];

  if (tasks.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">Nenhuma tarefa ainda</td></tr>';
    return;
  }

  const statusLabels = { pending: '⏳ Pendente', completed: '✅ Completa', failed: '❌ Falhou' };

  tbody.innerHTML = tasks.slice().reverse().map(t => `
    <tr>
      <td style="font-family:monospace;font-size:11px">${t.id.substring(0, 12)}</td>
      <td>${t.description}</td>
      <td>${t.assigned_to ? t.assigned_to.substring(0, 8) : '—'}</td>
      <td>${'🔵'.repeat(t.priority + 1)}</td>
      <td>${statusLabels[t.status] || t.status}</td>
      <td>${new Date(t.created_at).toLocaleString()}</td>
    </tr>
  `).join('');
}

function updateBadges() {
  const workers = statusData?.workers || [];
  const tasks = statusData?.queue || [];
  document.getElementById('worker-count').textContent = workers.length;
  document.getElementById('task-count').textContent = tasks.length;
}

// ─── Worker Actions ────────────────────────────────────────

async function pauseWorker(id) {
  await api(`/api/workers/${id}/pause`, 'POST');
  await refreshStatus();
}

async function resumeWorker(id) {
  await api(`/api/workers/${id}/resume`, 'POST');
  await refreshStatus();
}

async function removeWorker(id) {
  if (!confirm('Remover este worker?')) return;
  await api(`/api/workers/${id}`, 'DELETE');
  await refreshStatus();
}

function delegateToWorker(workerId) {
  document.getElementById('task-worker-id').value = workerId;
  showModal('new-task');
}

async function showWorkerMemory(workerId) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelector('[data-view="memory"]').classList.add('active');
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById('view-memory').classList.add('active');
  document.getElementById('view-title').textContent = 'Memória';

  await loadMemoryWorkerSelect();
  document.getElementById('memory-worker-select').value = workerId;
  await loadMemory();
}

async function loadMemoryWorkerSelect() {
  const select = document.getElementById('memory-worker-select');
  const workers = statusData?.workers || [];
  select.innerHTML = '<option value="">Selecione...</option>' +
    workers.map(w => `<option value="${w.id}">${w.name} (${w.role})</option>`).join('');
}

async function loadMemory() {
  const workerId = document.getElementById('memory-worker-select').value;
  const category = document.getElementById('memory-category-select').value;
  const content = document.getElementById('memory-content');

  if (!workerId) {
    content.textContent = 'Selecione um worker para ver a memória.';
    return;
  }

  content.textContent = '🔄 Carregando...';
  const data = await api(`/api/workers/${workerId}/memory?category=${category}&limit=10`);
  if (data && data.items) {
    content.textContent = data.items.join('\n\n---\n\n') || '🧠 Nenhuma memória encontrada nesta categoria.';
  } else {
    content.textContent = '❌ Erro ao carregar memória.';
  }
}

// ─── Broadcast ─────────────────────────────────────────────

async function broadcast() {
  const input = document.getElementById('broadcast-input');
  if (!input.value.trim()) return;

  await api('/api/broadcast', 'POST', { message: input.value });
  input.value = '';
  alert('📢 Mensagem enviada para todos os workers!');
}

// ─── Modals ────────────────────────────────────────────────

function setupModals() {
  // Novo Worker
  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label>Nome do Worker</label>
      <input type="text" id="worker-name" placeholder="Ex: Analista de Marketing">
    </div>
    <div class="form-group">
      <label>Papel/Função</label>
      <input type="text" id="worker-role" placeholder="Ex: analyst, creator, assistant">
    </div>
    <div class="form-group">
      <label>Descrição</label>
      <textarea id="worker-desc" placeholder="O que este worker faz?"></textarea>
    </div>
    <div class="form-group">
      <label>System Prompt</label>
      <textarea id="worker-prompt" placeholder="Instruções de comportamento para o worker..."></textarea>
    </div>
    <div class="form-group">
      <label><input type="checkbox" id="worker-autonomous"> Modo Autônomo (worker decide o que fazer)</label>
    </div>
    <button class="btn btn-primary" onclick="createWorker()" style="width:100%;margin-top:8px">🤖 Criar Worker</button>
  `;

  // Nova Tarefa
  const taskModalHtml = `
    <div class="form-group">
      <label>Descrição da Tarefa</label>
      <textarea id="task-desc" placeholder="Descreva o que precisa ser feito..."></textarea>
    </div>
    <div class="form-group">
      <label>Worker específico (opcional)</label>
      <input type="text" id="task-worker-id" placeholder="Deixe vazio para o Orchestrator decidir">
    </div>
    <div class="form-group">
      <label>Papel (opcional - se não especificar worker)</label>
      <input type="text" id="task-role" placeholder="Ex: analyst, creator, assistant">
    </div>
    <div class="form-group">
      <label>Prioridade</label>
      <select id="task-priority">
        <option value="0">🟢 Normal</option>
        <option value="1">🟡 Alta</option>
        <option value="2">🔴 Crítica</option>
      </select>
    </div>
    <button class="btn btn-primary" onclick="createTask()" style="width:100%;margin-top:8px">📋 Delegar Tarefa</button>
  `;
}

function showModal(type) {
  const overlay = document.getElementById('modal-overlay');
  const title = document.getElementById('modal-title');
  const body = document.getElementById('modal-body');

  if (type === 'new-worker') {
    title.textContent = '🤖 Novo Worker';
    body.innerHTML = `
      <div class="form-group">
        <label>Nome do Worker</label>
        <input type="text" id="worker-name" placeholder="Ex: Analista de Marketing">
      </div>
      <div class="form-group">
        <label>Papel/Função</label>
        <input type="text" id="worker-role" placeholder="Ex: analyst, creator, assistant">
      </div>
      <div class="form-group">
        <label>Descrição</label>
        <textarea id="worker-desc" placeholder="O que este worker faz?"></textarea>
      </div>
      <div class="form-group">
        <label>System Prompt (opcional)</label>
        <textarea id="worker-prompt" placeholder="Instruções de comportamento para o worker..."></textarea>
      </div>
      <div class="form-group">
        <label><input type="checkbox" id="worker-autonomous"> Modo Autônomo</label>
      </div>
      <button class="btn btn-primary" onclick="createWorker()" style="width:100%;margin-top:8px">🤖 Criar Worker</button>
    `;
  } else if (type === 'new-task') {
    title.textContent = '📋 Nova Tarefa';
    const workers = statusData?.workers || [];
    body.innerHTML = `
      <div class="form-group">
        <label>Descrição da Tarefa</label>
        <textarea id="task-desc" placeholder="Descreva o que precisa ser feito..."></textarea>
      </div>
      <div class="form-group">
        <label>Worker (opcional)</label>
        <select id="task-worker-select">
          <option value="">— Orchestrator decide —</option>
          ${workers.map(w => `<option value="${w.id}">${w.name} (${w.role})</option>`).join('')}
        </select>
      </div>
      <div class="form-group">
        <label>Papel (opcional)</label>
        <input type="text" id="task-role" placeholder="Ex: analyst, creator, assistant">
      </div>
      <div class="form-group">
        <label>Prioridade</label>
        <select id="task-priority">
          <option value="0">🟢 Normal</option>
          <option value="1">🟡 Alta</option>
          <option value="2">🔴 Crítica</option>
        </select>
      </div>
      <button class="btn btn-primary" onclick="createTask()" style="width:100%;margin-top:8px">📋 Delegar Tarefa</button>
    `;
  }

  overlay.classList.add('open');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
}

// ─── Create Actions ────────────────────────────────────────

async function createWorker() {
  const name = document.getElementById('worker-name').value;
  const role = document.getElementById('worker-role').value;
  const desc = document.getElementById('worker-desc').value;
  const prompt = document.getElementById('worker-prompt').value;
  const autonomous = document.getElementById('worker-autonomous').checked;

  if (!name || !role) {
    alert('Nome e papel são obrigatórios!');
    return;
  }

  await api('/api/workers', 'POST', { name, role, description: desc, system_prompt: prompt, autonomous });
  closeModal();
  await refreshStatus();
}

async function createTask() {
  const desc = document.getElementById('task-desc').value;
  const workerSelect = document.getElementById('task-worker-select');
  const workerId = workerSelect ? workerSelect.value : '';
  const role = document.getElementById('task-role').value;
  const priority = parseInt(document.getElementById('task-priority').value);

  if (!desc) {
    alert('Descrição da tarefa é obrigatória!');
    return;
  }

  const result = await api('/api/tasks', 'POST', {
    description: desc,
    worker_id: workerId || null,
    role: role || null,
    priority,
  });

  closeModal();

  // Mostra resultado
  if (result) {
    alert(`✅ Tarefa concluída!\n\nWorker: ${result.assigned_to || 'N/A'}\nStatus: ${result.status}\n\n${result.result || result.error || ''}`);
  }

  await refreshStatus();
}

// ─── Keyboard Shortcuts ────────────────────────────────────

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
});
