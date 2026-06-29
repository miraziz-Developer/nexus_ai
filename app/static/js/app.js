/**
 * Aether Nexus AI — Dashboard client
 * Horizon UI inspired · connects to FastAPI backend
 */

const API = '/api/v1';
let token = localStorage.getItem('nexus_token');
let user = JSON.parse(localStorage.getItem('nexus_user') || 'null');
let contracts = [];
let consensusChart = null;
let radarChart = null;
let selectedContractId = null;

// ── Utilities ─────────────────────────────────────────────────────────────

function headers() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

function showToast(msg, type = 'info') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `fixed bottom-6 right-6 glass rounded-xl px-5 py-3 shadow-glow text-sm z-50 max-w-sm ${
    type === 'error' ? 'border border-red-500/30 text-red-300' :
    type === 'success' ? 'border border-green-500/30 text-green-300' :
    'border border-nexus-500/30'
  }`;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 4000);
}

async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, { ...opts, headers: { ...headers(), ...opts.headers } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const msg = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map(d => d.msg).join(', ')
      : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function parseApiError(data, fallback = 'Request failed') {
  const detail = data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(d => d.msg || JSON.stringify(d)).join(', ');
  return fallback;
}

// ── Auth ──────────────────────────────────────────────────────────────────

function showAuthTab(tab) {
  const isLogin = tab === 'login';
  document.getElementById('login-form').classList.toggle('hidden', !isLogin);
  document.getElementById('register-form').classList.toggle('hidden', isLogin);

  document.getElementById('tab-login').className = isLogin
    ? 'auth-tab flex-1 py-2.5 rounded-lg text-sm font-medium bg-nexus-600/30 text-nexus-200 border border-nexus-500/30'
    : 'auth-tab flex-1 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:text-gray-200';
  document.getElementById('tab-register').className = !isLogin
    ? 'auth-tab flex-1 py-2.5 rounded-lg text-sm font-medium bg-emerald-600/20 text-emerald-200 border border-emerald-500/30'
    : 'auth-tab flex-1 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:text-gray-200';
}

document.getElementById('tab-login').addEventListener('click', () => showAuthTab('login'));
document.getElementById('tab-register').addEventListener('click', () => showAuthTab('register'));
document.getElementById('goto-register').addEventListener('click', () => showAuthTab('register'));
document.getElementById('goto-login').addEventListener('click', () => showAuthTab('login'));

function saveSession(data) {
  token = data.access_token;
  user = data.user;
  localStorage.setItem('nexus_token', token);
  localStorage.setItem('nexus_user', JSON.stringify(user));
  enterDashboard();
  showToast(`Welcome, ${user.name}! (${user.role})`, 'success');
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const loading = document.getElementById('login-loading');
  if (btn?.disabled) return;

  const body = { chutes_id: document.getElementById('login-chutes-id').value.trim() };
  try {
    if (btn) btn.disabled = true;
    if (loading) loading.classList.remove('hidden');

    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(parseApiError(data, `Sign in failed (${res.status})`));
    saveSession(data);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (btn) btn.disabled = false;
    if (loading) loading.classList.add('hidden');
  }
});

document.getElementById('register-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('register-btn');
  const loading = document.getElementById('register-loading');
  if (btn?.disabled) return;

  const body = {
    chutes_id: document.getElementById('register-chutes-id').value.trim(),
    name: document.getElementById('register-name').value.trim(),
    role: document.getElementById('register-role').value,
  };
  try {
    if (btn) btn.disabled = true;
    if (loading) loading.classList.remove('hidden');

    const res = await fetch(`${API}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(parseApiError(data, `Registration failed (${res.status})`));
    saveSession(data);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (btn) btn.disabled = false;
    if (loading) loading.classList.add('hidden');
  }
});

document.getElementById('logout-btn').addEventListener('click', () => {
  clearSession();
});

function enterDashboard() {
  document.getElementById('login-screen').classList.add('hidden');
  document.getElementById('dashboard').classList.remove('hidden');

  const isCompany = user.role === 'company';
  document.getElementById('user-name').textContent = user.name;
  document.getElementById('user-chutes-id').textContent = user.chutes_id;
  document.getElementById('avatar-initial').textContent = user.name[0].toUpperCase();
  document.getElementById('sidebar-role').textContent =
    isCompany ? '🏢 Company Dashboard' : '👨‍💻 Freelancer Dashboard';

  const sidebar = document.querySelector('#dashboard aside');
  sidebar?.classList.toggle('border-emerald-500/30', !isCompany);
  sidebar?.classList.toggle('border-surface-border', isCompany);

  document.getElementById('create-contract-panel').classList.toggle('hidden', !isCompany);
  document.getElementById('submit-work-panel').classList.toggle('hidden', isCompany);

  loadHealth();
  loadContracts().then(() => {
    switchView(isCompany ? 'overview' : 'contracts');
  });
}

function clearSession() {
  localStorage.removeItem('nexus_token');
  localStorage.removeItem('nexus_user');
  token = null;
  user = null;
  document.getElementById('dashboard').classList.add('hidden');
  document.getElementById('login-screen').classList.remove('hidden');
}

window.addEventListener('storage', (e) => {
  if (e.key === 'nexus_token' && !e.newValue && token) {
    clearSession();
    showToast('Signed out in another tab', 'info');
  }
});

// ── Health / Mock badge ───────────────────────────────────────────────────

async function loadHealth() {
  try {
    const h = await fetch('/health').then(r => r.json());
    const mockBadge = document.getElementById('mock-badge');
    const liveBadge = document.getElementById('live-badge');
    const c = h.chutes || {};
    const isLive = c.has_api_key && !c.mock_mode && c.production_ready !== false
      && c.last_inference_mode !== 'mock' && (c.fallback_count || 0) === 0;

    if (c.mock_mode || c.last_inference_mode === 'mock' || c.fallback_count > 0) {
      mockBadge.textContent = c.fallback_count > 0
        ? `Chutes Fallback (${c.fallback_count})`
        : 'Mock / Demo Mode';
      mockBadge.classList.remove('hidden');
    } else {
      mockBadge.classList.add('hidden');
    }

    if (liveBadge) {
      if (isLive || (c.has_api_key && !c.mock_mode)) {
        liveBadge.textContent = c.production_ready ? '● Chutes Live' : '● Chutes Ready';
        liveBadge.className = 'px-3 py-1 rounded-full text-xs bg-green-500/10 text-green-400 border border-green-500/20 agent-pulse';
      } else {
        liveBadge.textContent = '● Demo Mode';
        liveBadge.className = 'px-3 py-1 rounded-full text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20';
      }
    }
  } catch (_) {}
}

// ── Contracts ─────────────────────────────────────────────────────────────

async function loadContracts() {
  try {
    const data = await api('/contracts/list');
    contracts = data.contracts;
    renderContracts();
    updateStats();
    populateSubmitSelect();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function renderContracts() {
  const container = document.getElementById('contracts-list');
  if (!contracts.length) {
    container.innerHTML = '<p class="text-gray-500 text-sm">No contracts yet.</p>';
    return;
  }

  container.innerHTML = contracts.map(c => {
    const kpi = c.kpi_blueprint;
    const statusColor = {
      approved: 'text-green-400 bg-green-500/10 border-green-500/20',
      rejected: 'text-red-400 bg-red-500/10 border-red-500/20',
      verifying: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
      active: 'text-nexus-400 bg-nexus-500/10 border-nexus-500/20',
    }[c.status] || 'text-gray-400 bg-gray-500/10 border-gray-500/20';

    const mode = c.architect_inference_mode;
    const modeBadge = mode === 'mock'
      ? '<span class="px-2 py-0.5 rounded text-xs bg-amber-500/10 text-amber-400">mock inference</span>'
      : mode === 'chutes_live'
        ? '<span class="px-2 py-0.5 rounded text-xs bg-green-500/10 text-green-400">chutes live</span>'
        : '';

    return `
      <div class="p-4 rounded-xl bg-nexus-950/30 border border-surface-border hover:border-nexus-500/30 transition cursor-pointer contract-card" data-id="${c.contract_id}">
        <div class="flex items-start justify-between">
          <div>
            <h4 class="font-medium">${kpi?.task_title || 'Pending KPI Generation'}</h4>
            <p class="text-xs text-gray-500 mt-1">${c.contract_id.slice(0, 8)}… · ${new Date(c.created_at).toLocaleDateString()}</p>
          </div>
          <div class="flex flex-col items-end gap-1">
            <span class="px-2 py-1 rounded-lg text-xs border ${statusColor}">${c.status}</span>
            ${modeBadge}
          </div>
        </div>
        ${kpi ? `
          <div class="mt-3 flex flex-wrap gap-2">
            <span class="px-2 py-0.5 rounded text-xs bg-nexus-600/10 text-nexus-300">Coverage ≥ ${kpi.required_metrics.min_test_coverage_percent}%</span>
            <span class="px-2 py-0.5 rounded text-xs bg-nexus-600/10 text-nexus-300">Latency ≤ ${kpi.required_metrics.max_response_time_ms}ms</span>
            <span class="px-2 py-0.5 rounded text-xs bg-nexus-600/10 text-nexus-300">${kpi.required_metrics.strict_language}</span>
          </div>
        ` : ''}
      </div>
    `;
  }).join('');

  document.querySelectorAll('.contract-card').forEach(card => {
    card.addEventListener('click', () => selectContract(card.dataset.id));
  });
}

function populateSubmitSelect() {
  const sel = document.getElementById('submit-contract-id');
  const active = contracts.filter(c =>
    ['active', 'kpi_generated', 'submitted', 'rejected'].includes(c.status)
  );
  sel.innerHTML = '<option value="">Select active contract...</option>' +
    active.map(c => `<option value="${c.contract_id}">${c.kpi_blueprint?.task_title || c.contract_id.slice(0, 8)}</option>`).join('');
}

function updateStats() {
  document.getElementById('stat-contracts').textContent = contracts.length;
  document.getElementById('stat-approved').textContent = contracts.filter(c => c.status === 'approved').length;

  let inferences = 0;
  contracts.forEach(c => {
    if (c.architect_inference_id) inferences++;
    if (c.last_verification) inferences += 2;
  });
  document.getElementById('stat-inferences').textContent = inferences;

  const approved = contracts.filter(c => c.status === 'approved');
  const scored = approved.find(c => c.last_verification?.auditor?.consensus_score_percent);
  if (scored) {
    document.getElementById('stat-score').textContent =
      `${scored.last_verification.auditor.consensus_score_percent}%`;
  } else if (approved.length) {
    document.getElementById('stat-score').textContent = '100%';
  }
}

async function selectContract(id) {
  selectedContractId = id;
  try {
    const status = await api(`/verify/status/${id}`);
    renderActivityFeed(status.logs);
    renderAuditTrail(status.on_chain_records);
    const graph = await api(`/verify/consensus-graph/${id}`);
    renderConsensusChart(graph);
    renderRadarChart(graph);
    updateAgentStatuses(status.logs);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ── Create Contract (Company) ─────────────────────────────────────────────

document.getElementById('create-contract-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('create-contract-btn');
  const loading = document.getElementById('create-contract-loading');
  if (btn?.disabled) return;

  const body = {
    raw_task_description: document.getElementById('task-description').value.trim(),
    freelancer_chutes_id: document.getElementById('freelancer-id').value.trim() || null,
    budget_usd: parseFloat(document.getElementById('budget').value) || null,
  };
  try {
    if (btn) btn.disabled = true;
    if (loading) loading.classList.remove('hidden');
    showToast('Agent 1 (Architect) running on Chutes… 30–60 sec', 'info');
    document.getElementById('agent1-status').textContent = 'Status: running on Chutes…';
    const contract = await api('/contracts/create', { method: 'POST', body: JSON.stringify(body) });
    document.getElementById('agent1-status').textContent = `Status: completed ✓ (${contract.architect_inference_id?.slice(0, 16)}…)`;
    showToast(`KPI generated: ${contract.kpi_blueprint.task_title}`, 'success');
    await loadContracts();
    selectContract(contract.contract_id);
    switchView('contracts');
  } catch (err) {
    document.getElementById('agent1-status').textContent = 'Status: failed';
    showToast(err.message, 'error');
  } finally {
    if (btn) btn.disabled = false;
    if (loading) loading.classList.add('hidden');
  }
});

// ── Submit Work (Freelancer) ──────────────────────────────────────────────

document.getElementById('submit-work-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    contract_id: document.getElementById('submit-contract-id').value,
    github_url: document.getElementById('github-url').value.trim() || null,
    reported_test_coverage_percent: parseFloat(document.getElementById('reported-coverage').value),
    reported_response_time_ms: parseFloat(document.getElementById('reported-latency').value),
    notes: document.getElementById('artifact-notes').value.trim() || null,
  };
  try {
    showToast('Agents 2 + 3 running consensus pipeline…', 'info');
    document.getElementById('agent2-status').textContent = 'Status: running…';
    document.getElementById('agent3-status').textContent = 'Status: waiting…';

    const result = await api('/verify/submit', { method: 'POST', body: JSON.stringify(body) });

    document.getElementById('agent2-status').textContent = `Status: completed ✓ (${result.validator_output?.overall_score_percent}%)`;
    document.getElementById('agent3-status').textContent = `Status: ${result.auditor_output?.verdict} ✓`;

    const verdict = result.auditor_output?.verdict;
    showToast(
      `Verdict: ${verdict} — Payment: ${result.payment_recommendation_percent}%`,
      verdict === 'Approved' ? 'success' : 'error'
    );

    await loadContracts();
    selectContract(body.contract_id);
    switchView('agents');
  } catch (err) {
    document.getElementById('agent2-status').textContent = 'Status: failed';
    showToast(err.message, 'error');
  }
});

// ── Charts ────────────────────────────────────────────────────────────────

function renderConsensusChart(graph) {
  const opts = {
    series: [{ name: 'Agent Score', data: graph.scores || [0, 0, 0] }],
    chart: { type: 'bar', height: 280, toolbar: { show: false }, background: 'transparent' },
    plotOptions: { bar: { borderRadius: 8, columnWidth: '50%', distributed: true } },
    colors: ['#6366f1', '#f59e0b', '#10b981'],
    xaxis: { categories: graph.labels || ['Architect', 'Validator', 'Auditor'], labels: { style: { colors: '#9ca3af' } } },
    yaxis: { max: 100, labels: { style: { colors: '#9ca3af' } } },
    grid: { borderColor: '#2d3748' },
    dataLabels: { enabled: true, style: { colors: ['#fff'] } },
    legend: { show: false },
    theme: { mode: 'dark' },
  };
  if (consensusChart) { consensusChart.destroy(); }
  consensusChart = new ApexCharts(document.getElementById('consensus-chart'), opts);
  consensusChart.render();
}

function renderRadarChart(graph) {
  const scores = graph.scores || [0, 0, 0];
  const opts = {
    series: [{ name: 'KPI', data: scores }],
    chart: { type: 'radar', height: 280, toolbar: { show: false }, background: 'transparent' },
    xaxis: { categories: ['Architect', 'Validator', 'Auditor'] },
    yaxis: { show: false, max: 100 },
    colors: ['#818cf8'],
    fill: { opacity: 0.2 },
    stroke: { width: 2 },
    markers: { size: 4 },
    theme: { mode: 'dark' },
  };
  if (radarChart) { radarChart.destroy(); }
  radarChart = new ApexCharts(document.getElementById('radar-chart'), opts);
  radarChart.render();
}

// ── Activity & Audit ──────────────────────────────────────────────────────

function renderActivityFeed(logs) {
  const feed = document.getElementById('activity-feed');
  if (!logs?.length) {
    feed.innerHTML = '<p class="text-gray-500 text-sm">No activity yet.</p>';
    return;
  }
  feed.innerHTML = [...logs].reverse().map(l => `
    <div class="flex items-start gap-3 p-3 rounded-xl bg-nexus-950/30 border border-surface-border text-sm">
      <span class="text-lg">${agentIcon(l.agent)}</span>
      <div class="flex-1">
        <p class="font-medium">${l.agent} · ${l.step}</p>
        <p class="text-xs text-gray-400 mt-0.5">${l.detail || ''}</p>
        <p class="text-xs text-gray-600 mt-1">${new Date(l.timestamp).toLocaleString()}</p>
      </div>
      <span class="px-2 py-0.5 rounded text-xs ${
        l.status === 'completed' ? 'bg-green-500/10 text-green-400' :
        l.status === 'running' ? 'bg-amber-500/10 text-amber-400 agent-pulse' :
        l.status === 'failed' ? 'bg-red-500/10 text-red-400' :
        'bg-gray-500/10 text-gray-400'
      }">${l.status}</span>
    </div>
  `).join('');
}

function renderAuditTrail(records) {
  const trail = document.getElementById('audit-trail');
  if (!records?.length) {
    trail.innerHTML = '<p class="text-gray-500 text-sm">No audit records yet.</p>';
    return;
  }
  trail.innerHTML = records.map(r => `
    <div class="p-4 rounded-xl bg-nexus-950/30 border border-green-500/20">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-mono text-green-400">${r.audit_id?.slice(0, 12)}…</span>
        <span class="px-2 py-0.5 rounded text-xs ${
          r.verdict === 'Approved' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
        }">${r.verdict}</span>
      </div>
      <p class="text-sm text-gray-300">${r.auditor_summary || ''}</p>
      <p class="text-xs font-mono text-gray-500 mt-2 break-all">hash: ${r.audit_hash}</p>
      <p class="text-xs text-gray-600 mt-1">${r.timestamp} · ${r.network}</p>
    </div>
  `).join('');
}

function updateAgentStatuses(logs) {
  const agents = { architect: 'agent1-status', validator: 'agent2-status', auditor: 'agent3-status' };
  for (const [agent, elId] of Object.entries(agents)) {
    const relevant = logs.filter(l => l.agent === agent);
    const last = relevant[relevant.length - 1];
    if (last) {
      document.getElementById(elId).textContent =
        `Status: ${last.status}${last.score ? ` (${last.score}%)` : ''}${last.verdict ? ` — ${last.verdict}` : ''}`;
    }
  }
}

function agentIcon(agent) {
  return { architect: '🏗️', validator: '🔍', auditor: '⚖️', system: '⚙️' }[agent] || '📌';
}

// ── Navigation ────────────────────────────────────────────────────────────

function switchView(view) {
  document.querySelectorAll('.view-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById(`view-${view}`).classList.remove('hidden');

  document.querySelectorAll('.nav-btn').forEach(btn => {
    const active = btn.dataset.view === view;
    btn.className = `nav-btn w-full text-left px-4 py-3 rounded-xl text-sm font-medium ${
      active ? 'bg-nexus-600/20 text-nexus-300 border border-nexus-500/20' : 'text-gray-400 hover:bg-white/5'
    }`;
  });

  const titles = {
    overview: ['Overview', 'Multi-agent KPI verification dashboard'],
    contracts: ['Contracts', user?.role === 'company' ? 'Create and manage smart tasks' : 'View missions and submit work'],
    agents: ['Agent Pipeline', 'Chutes decentralized multi-agent consensus'],
    audit: ['Verification Audit', 'SHA-256 hashed consensus records'],
  };
  const [title, sub] = titles[view] || ['', ''];
  document.getElementById('page-title').textContent = title;
  document.getElementById('page-subtitle').textContent = sub;
}

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => switchView(btn.dataset.view));
});

// ── Init ──────────────────────────────────────────────────────────────────

async function initApp() {
  if (token && user) {
    try {
      await api('/contracts/list');
      enterDashboard();
      return;
    } catch (_) {
      clearSession();
    }
  }
  document.getElementById('login-screen').classList.remove('hidden');
}

initApp();

// Default charts on overview
renderConsensusChart({ labels: ['Architect', 'Validator', 'Auditor'], scores: [0, 0, 0] });
renderRadarChart({ scores: [0, 0, 0] });
