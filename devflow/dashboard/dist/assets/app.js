/* DevFlow Observatory — Vanilla JS Dashboard */

// === Config ===
const POLL_RUN_LIST = 5000;
const POLL_RUN_DETAIL = 2000;
const POLL_LLM_TRACE = 3000;
const POLL_ARTIFACT = 3000;

// === State ===
let selectedRunId = null;
let selectedStage = null;
let activeTab = 'artifact'; // 'artifact' | 'llm'
let runList = null;
let runDetail = null;
let llmCalls = null;
let artifactMarkdown = null;
let apiError = null;
let listTimer = null;
let detailTimer = null;
let llmTimer = null;
let artifactTimer = null;
let expandedLlmCalls = new Set();
let expandedPromptSections = new Set();

// === API ===
async function api(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// === Stage Definitions ===
const STAGE_DEFS = [
  { name: 'requirement_intake', label: '需求分析', icon: '🔍' },
  { name: 'solution_design', label: '方案设计', icon: '💡' },
  { name: 'code_generation', label: '代码生成', icon: '⚙️' },
  { name: 'test_generation', label: '测试生成', icon: '🧪' },
  { name: 'code_review', label: '代码评审', icon: '🛡️' },
  { name: 'delivery', label: '交付', icon: '📦' },
];
const STAGE_NAMES = Object.fromEntries(STAGE_DEFS.map(s => [s.name, s.label]));

// === Helpers ===
function statusBadge(status) {
  const map = {
    running: 'badge-cyan', success: 'badge-success', delivered: 'badge-success',
    failed: 'badge-destructive', blocked: 'badge-warning',
  };
  const labels = {
    running: '运行中', success: '已完成', delivered: '已交付',
    failed: '失败', blocked: '已阻塞', paused: '已暂停', pending: '等待中',
  };
  const cls = map[status] || 'badge-secondary';
  const label = labels[status] || status;
  return `<span class="badge ${cls}">${label}</span>`;
}

function formatDuration(ms) {
  if (ms == null) return '';
  if (ms < 1000) return `${ms}ms`;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rs = s % 60;
  if (m < 60) return `${m}m ${rs}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function formatTime(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function matchStage(defName, stageName) {
  return stageName.startsWith(defName) || defName.startsWith(stageName);
}

function llmCallKey(call, index) {
  const identity = call.response_path || call.request_path || `call-${index}`;
  const turn = call.turn ?? index + 1;
  return [selectedRunId || '', call.stage || '', turn, identity].join('|');
}

function promptSectionKey(callKey, label) {
  return `${callKey}|${label}`;
}

function simpleMarkdownToHtml(md) {
  if (!md) return '';
  let html = md.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  html = html.replace(/```[\s\S]*?```/g, (m) => {
    const code = m.replace(/```\w*\n?/, '').replace(/\n?```$/, '');
    return `<pre><code>${code}</code></pre>`;
  });
  html = html.replace(/^(#{1,3}) (.+)$/gm, (_, h, t) => `<h${h.length}>${t}</h${h.length}>`);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
  html = html.replace(/\n\n/g, '</p><p>');
  html = html.replace(/\n/g, '<br/>');
  return `<p>${html}</p>`;
}

// === Fetch Data ===
async function fetchActiveRun() {
  try { return await api('/api/v1/metrics/active-run'); } catch { return null; }
}

async function fetchRunList() {
  try {
    const r = await api('/api/v1/metrics/recent-runs?limit=20');
    return r.runs || [];
  } catch (e) {
    apiError = e.message;
    return null;
  }
}

async function fetchRunDetail(runId) {
  if (!runId) return null;
  try { return await api(`/api/v1/metrics/runs/${encodeURIComponent(runId)}/detail`); }
  catch { return null; }
}

async function fetchLlmTrace(runId) {
  if (!runId) return null;
  try {
    const r = await api(`/api/v1/metrics/runs/${encodeURIComponent(runId)}/llm-trace`);
    return r.llm_trace || [];
  } catch { return null; }
}

async function fetchArtifactMarkdown(runId, stage) {
  if (!runId || !stage) return null;
  try {
    const r = await api(`/api/v1/metrics/runs/${encodeURIComponent(runId)}/artifact-markdown?stage=${encodeURIComponent(stage)}`);
    return r.content || null;
  } catch { return null; }
}

// === Render Functions ===
function renderSidebar() {
  const el = document.getElementById('sidebar-list');
  if (!runList || runList.length === 0) {
    el.innerHTML = '<div style="padding:24px;text-align:center;color:hsl(var(--muted-foreground));font-size:13px;">暂无运行数据</div>';
    return;
  }
  el.innerHTML = runList.map(run => {
    const sel = run.run_id === selectedRunId ? 'selected' : '';
    const isActive = run.status === 'running' || run.status === 'paused';
    const shortId = run.run_id.length > 12 ? run.run_id.slice(0, 12) + '…' : run.run_id;
    const dot = isActive ? '<span class="ping-dot" style="width:8px;height:8px;display:inline-block;position:relative;margin-left:auto;flex-shrink:0;"></span>' : '';
    return `<button class="sidebar-item ${sel}" data-run-id="${run.run_id}">
      <span class="run-id mono-xs">${shortId}</span>
      <div class="run-meta">
        ${statusBadge(run.status)}
        ${dot}
      </div>
      <div class="run-time">${run.current_stage || '-'} · ${formatTime(run.started_at)}</div>
    </button>`;
  }).join('');

  el.querySelectorAll('.sidebar-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.runId;
      if (id !== selectedRunId) {
        selectedRunId = id;
        selectedStage = null;
        activeTab = 'artifact';
        expandedLlmCalls = new Set();
        expandedPromptSections = new Set();
        loadRunDetail();
        renderAll();
      }
    });
  });
}

function renderStepper() {
  const el = document.getElementById('pipeline-stepper');
  const stages = runDetail?.stages || [];
  if (stages.length === 0) { el.innerHTML = ''; return; }

  let html = '';
  STAGE_DEFS.forEach((def, i) => {
    const matched = stages.find(s => matchStage(def.name, s.name));
    const status = matched?.status;
    const duration = matched?.duration_ms;
    const isLast = i === STAGE_DEFS.length - 1;
    const isSuccess = status === 'success';

    const statusCls = status === 'running' ? 'running' : status === 'success' ? 'success' : status === 'failed' ? 'failed' : status === 'blocked' ? 'blocked' : '';
    const checkmark = isSuccess ? '✓' : def.icon;

    html += `<button class="step-item" data-stage="${def.name}">
      <div class="step-circle ${statusCls}">${checkmark}</div>
      <span class="step-label">${def.label}</span>
      ${isSuccess && duration != null ? `<span class="step-duration">${formatDuration(duration)}</span>` : ''}
    </button>`;

    if (!isLast) {
      const prevStage = i > 0 ? stages.find(s => matchStage(STAGE_DEFS[i - 1].name, s.name)) : null;
      const prevSuccess = prevStage?.status === 'success';
      const connCls = isSuccess && prevSuccess ? 'done' : '';
      html += `<div class="step-connector ${connCls}"></div>`;
    }
  });
  el.innerHTML = html;

  el.querySelectorAll('.step-item').forEach(btn => {
    btn.addEventListener('click', () => {
      selectedStage = btn.dataset.stage;
      activeTab = 'artifact';
      loadArtifact();
      renderRightPanel();
      renderStageCards();
    });
  });
}

function renderStageCards() {
  const el = document.getElementById('stage-cards');
  const stages = runDetail?.stages || [];
  const tokenSummary = runDetail?.token_summary || {};

  if (stages.length === 0) { el.innerHTML = ''; return; }

  el.innerHTML = stages.map(stage => {
    const displayName = STAGE_NAMES[stage.name] || stage.name;
    const tokenInfo = tokenSummary[stage.name];
    const sel = stage.name === selectedStage;

    let infoHtml = '';
    if (stage.duration_ms != null) {
      infoHtml += `<div class="stage-info-row"><span class="stage-info-label">耗时</span> ${formatDuration(stage.duration_ms)}</div>`;
    }
    if (tokenInfo?.model) {
      infoHtml += `<div class="stage-info-row"><span class="stage-info-label">模型</span> <span class="mono-xs">${tokenInfo.model}</span></div>`;
    }
    if (tokenInfo) {
      infoHtml += `<div class="stage-info-row"><span class="stage-info-label">Token</span> prompt: ${tokenInfo.prompt_tokens} / comp: ${tokenInfo.completion_tokens} / total: ${tokenInfo.total_tokens}</div>`;
      if (tokenInfo.provider) {
        infoHtml += `<div class="stage-info-row"><span class="stage-info-label">Provider</span> ${tokenInfo.provider}</div>`;
      }
    }

    // LLM duration from trace
    const stageLlmDuration = (llmCalls || [])
      .filter(c => c.stage === stage.name || stage.name.startsWith(c.stage) || c.stage.startsWith(stage.name))
      .reduce((sum, c) => sum + (c.duration_ms || 0), 0);
    if (stageLlmDuration > 0) {
      infoHtml += `<div class="stage-info-row"><span class="stage-info-label">LLM 耗时</span> ${formatDuration(stageLlmDuration)}</div>`;
    }

    return `<div class="stage-card" data-stage="${stage.name}" style="${sel ? 'border-color:hsl(var(--cyan))' : ''}">
      <div class="stage-card-header">
        <span class="stage-card-title">⚡ ${displayName}</span>
        ${statusBadge(stage.status)}
      </div>
      <div class="stage-card-body">${infoHtml}</div>
    </div>`;
  }).join('');

  el.querySelectorAll('.stage-card').forEach(card => {
    card.addEventListener('click', () => {
      selectedStage = card.dataset.stage;
      activeTab = 'artifact';
      loadArtifact();
      renderRightPanel();
      renderStageCards();
    });
  });
}

function renderRightPanel() {
  const el = document.getElementById('right-content');
  if (!selectedStage) {
    el.innerHTML = `<div class="tab-bar">
      <button class="tab-btn active">阶段产物</button>
      <button class="tab-btn">LLM 推理</button>
    </div>
    <div class="tab-content">
      <div class="tab-placeholder">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="m9 9 6 6"/><path d="m15 9-6 6"/></svg>
        <span>点击左侧阶段查看详情</span>
      </div>
    </div>`;
    return;
  }

  const stageLabel = STAGE_NAMES[selectedStage] || selectedStage;
  const filteredCalls = (llmCalls || []).filter(
    c => c.stage === selectedStage || selectedStage.startsWith(c.stage) || c.stage.startsWith(selectedStage)
  );

  let tabContentHtml = '';
  if (activeTab === 'artifact') {
    if (artifactMarkdown) {
      tabContentHtml = `<div class="artifact-md">${simpleMarkdownToHtml(artifactMarkdown)}</div>`;
    } else {
      tabContentHtml = `<div class="tab-placeholder">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="m9 9 6 6"/><path d="m15 9-6 6"/></svg>
        <span>暂无产物</span>
      </div>`;
    }
  } else {
    tabContentHtml = renderLlmCalls(filteredCalls);
  }

  el.innerHTML = `<div class="tab-bar">
    <button class="tab-btn ${activeTab === 'artifact' ? 'active' : ''}" data-tab="artifact">📄 阶段产物</button>
    <button class="tab-btn ${activeTab === 'llm' ? 'active' : ''}" data-tab="llm">🧠 LLM 推理</button>
  </div>
  <div class="tab-content">${tabContentHtml}</div>`;

  el.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      activeTab = btn.dataset.tab;
      renderRightPanel();
    });
  });

  // Bind LLM call toggles
  el.querySelectorAll('.llm-call-header').forEach(hdr => {
    hdr.addEventListener('click', () => {
      const key = hdr.parentElement.dataset.callKey;
      if (!key) return;
      if (expandedLlmCalls.has(key)) {
        expandedLlmCalls.delete(key);
        hdr.parentElement.classList.remove('open');
      } else {
        expandedLlmCalls.add(key);
        hdr.parentElement.classList.add('open');
      }
    });
  });
  el.querySelectorAll('.llm-prompt-toggle').forEach(toggle => {
    toggle.addEventListener('click', (event) => {
      event.stopPropagation();
      const key = toggle.parentElement.dataset.promptKey;
      if (!key) return;
      if (expandedPromptSections.has(key)) {
        expandedPromptSections.delete(key);
        toggle.parentElement.classList.remove('open');
      } else {
        expandedPromptSections.add(key);
        toggle.parentElement.classList.add('open');
      }
    });
  });
}

function renderLlmCalls(calls) {
  if (!calls || calls.length === 0) {
    return `<div class="tab-placeholder">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="m9 9 6 6"/><path d="m15 9-6 6"/></svg>
      <span>本阶段无 LLM 调用</span>
    </div>`;
  }

  return calls.map((call, i) => {
    const stageName = STAGE_NAMES[call.stage] || call.stage;
    const turnLabel = call.turn ?? (i + 1);
    const sysPrompt = call.system_prompt || call.system_prompt_summary || '';
    const usrPrompt = call.user_prompt || call.user_prompt_summary || '';
    const output = call.content || call.content_summary || '';
    const truncLen = 200;
    const callKey = llmCallKey(call, i);
    const openClass = expandedLlmCalls.has(callKey) ? ' open' : '';

    return `<div class="llm-call${openClass}" data-call-key="${callKey}">
      <div class="llm-call-header">
        <span style="display:flex;align-items:center;gap:6px;">
          <span class="badge badge-cyan" style="font-size:10px;">${stageName}</span>
          ${calls.length > 1 ? `<span style="font-size:10px;color:hsl(var(--muted-foreground));">#${turnLabel}</span>` : ''}
        </span>
        <span style="display:flex;align-items:center;gap:8px;font-size:12px;color:hsl(var(--muted-foreground));">
          <span>${call.duration_ms != null ? formatDuration(call.duration_ms) : '-'}</span>
          <span>${call.usage?.total_tokens ?? 0} tokens</span>
        </span>
      </div>
      <div class="llm-call-body">
        ${sysPrompt ? renderPromptSection('System Prompt', sysPrompt, truncLen, callKey) : ''}
        ${usrPrompt ? renderPromptSection('User Prompt', usrPrompt, truncLen, callKey) : ''}
        ${output ? renderPromptSection('模型输出', output, 500, callKey) : ''}
        <div class="llm-meta-grid">
          <div class="llm-meta-cell"><div class="label">prompt_tokens</div><div class="value">${call.usage?.prompt_tokens ?? '-'}</div></div>
          <div class="llm-meta-cell"><div class="label">completion_tokens</div><div class="value">${call.usage?.completion_tokens ?? '-'}</div></div>
          <div class="llm-meta-cell"><div class="label">total_tokens</div><div class="value">${call.usage?.total_tokens ?? '-'}</div></div>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:8px;font-size:11px;color:hsl(var(--muted-foreground));">
          <span>耗时: ${call.duration_ms != null ? formatDuration(call.duration_ms) : '-'}</span>
          <span>Provider: ${call.provider ?? '-'}</span>
          ${call.model ? `<span>模型: ${call.model}</span>` : ''}
          ${call.turn != null ? `<span>Turn: ${call.turn}</span>` : ''}
        </div>
      </div>
    </div>`;
  }).join('');
}

function renderPromptSection(label, content, truncLen, callKey) {
  const truncated = content.length > truncLen;
  const displayText = truncated ? content.slice(0, truncLen) + '…' : content;
  let formattedContent = displayText;
  if (label === '模型输出') {
    try { formattedContent = JSON.stringify(JSON.parse(displayText), null, 2); } catch {}
  }
  const key = promptSectionKey(callKey, label);
  const openClass = expandedPromptSections.has(key) ? ' open' : '';
  return `<div class="llm-prompt-section${openClass}" data-prompt-key="${key}">
    <button class="llm-prompt-toggle">💬 ${label} ${truncated ? '▼' : ''}</button>
    <div class="llm-prompt-content">${formattedContent}</div>
  </div>`;
}

function renderHeader() {
  const el = document.getElementById('header-run-id');
  el.textContent = selectedRunId || '';
}

function renderAll() {
  renderHeader();
  renderSidebar();
  renderStepper();
  renderStageCards();
  renderRightPanel();
}

function renderError() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <header id="header">
      <div class="header-left"><h1>DevFlow<span class="accent">Monitor</span></h1></div>
      <div class="header-center"></div>
      <div class="header-right">
        <button id="btn-refresh" class="btn-ghost" title="刷新">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        </button>
      </div>
    </header>
    <div class="error-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="hsl(var(--destructive))" stroke-width="2" width="64" height="64"><line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.56 9"/><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>
      <h1>API 服务连接失败</h1>
      <p>无法连接到后端 API 服务 (127.0.0.1:8080)，请确认服务已启动</p>
      <p class="mono-xs" style="font-size:11px;color:hsl(var(--muted-foreground)/0.6);">${apiError || ''}</p>
      <button id="btn-retry" class="btn-retry">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        重试连接
      </button>
    </div>`;

  document.getElementById('btn-retry')?.addEventListener('click', init);
  document.getElementById('btn-refresh')?.addEventListener('click', init);
}

function renderEmpty() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <header id="header">
      <div class="header-left"><h1>DevFlow<span class="accent">Monitor</span></h1></div>
      <div class="header-center"></div>
      <div class="header-right">
        <button id="btn-refresh" class="btn-ghost" title="刷新">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        </button>
        <span class="live-badge"><span class="ping-dot"></span><span class="static-dot"></span>实时监控</span>
      </div>
    </header>
    <div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="hsl(var(--muted-foreground)/0.4)" stroke-width="1.5" width="64" height="64"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
      <h1>Pipeline 执行监控</h1>
      <p>启动 DevFlow 后，Pipeline 运行将在此处实时展示</p>
      <p style="font-size:12px;color:hsl(var(--muted-foreground)/0.6);">🚀 使用 devflow start 启动流程</p>
    </div>`;

  document.getElementById('btn-refresh')?.addEventListener('click', init);
}

// === Data Loading ===
async function loadRunDetail() {
  if (!selectedRunId) return;
  runDetail = await fetchRunDetail(selectedRunId);
  llmCalls = await fetchLlmTrace(selectedRunId);
  artifactMarkdown = await fetchArtifactMarkdown(selectedRunId, selectedStage);
  renderStepper();
  renderStageCards();
  renderRightPanel();
  renderHeader();
}

async function loadArtifact() {
  artifactMarkdown = await fetchArtifactMarkdown(selectedRunId, selectedStage);
  if (activeTab === 'artifact') renderRightPanel();
}

function startPolling() {
  stopPolling();
  listTimer = setInterval(async () => {
    const newList = await fetchRunList();
    if (newList) { runList = newList; renderSidebar(); }
  }, POLL_RUN_LIST);

  detailTimer = setInterval(async () => {
    if (!selectedRunId) return;
    runDetail = await fetchRunDetail(selectedRunId);
    renderStepper();
    renderStageCards();
  }, POLL_RUN_DETAIL);

  llmTimer = setInterval(async () => {
    if (!selectedRunId) return;
    llmCalls = await fetchLlmTrace(selectedRunId);
    if (activeTab === 'llm') renderRightPanel();
  }, POLL_LLM_TRACE);

  artifactTimer = setInterval(async () => {
    if (!selectedRunId || !selectedStage) return;
    artifactMarkdown = await fetchArtifactMarkdown(selectedRunId, selectedStage);
    if (activeTab === 'artifact') renderRightPanel();
  }, POLL_ARTIFACT);
}

function stopPolling() {
  if (listTimer) clearInterval(listTimer);
  if (detailTimer) clearInterval(detailTimer);
  if (llmTimer) clearInterval(llmTimer);
  if (artifactTimer) clearInterval(artifactTimer);
  listTimer = detailTimer = llmTimer = artifactTimer = null;
}

// === Init ===
async function init() {
  stopPolling();
  apiError = null;
  try {
    runList = await fetchRunList();
    if (apiError) { renderError(); return; }
  } catch (e) {
    apiError = e.message;
    renderError();
    return;
  }

  if (!runList || runList.length === 0) {
    renderEmpty();
    // still poll for new runs
    startPolling();
    return;
  }

  // Auto-select active run or first run
  if (!selectedRunId) {
    const active = await fetchActiveRun();
    selectedRunId = (active && active.run_id) ? active.run_id : runList[0].run_id;
  }

  // Rebuild the full layout if it was error/empty
  const app = document.getElementById('app');
  if (!app.querySelector('#main-layout')) {
    app.innerHTML = `
    <header id="header">
      <div class="header-left"><h1>DevFlow<span class="accent">Monitor</span></h1>
        <svg class="icon-activity" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      </div>
      <div class="header-center"><span id="header-run-id" class="mono-xs"></span></div>
      <div class="header-right">
        <button id="btn-refresh" class="btn-ghost" title="刷新">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        </button>
        <span class="live-badge"><span class="ping-dot"></span><span class="static-dot"></span>实时监控</span>
      </div>
    </header>
    <div id="main-layout">
      <aside id="sidebar">
        <div class="sidebar-header">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>
          <span>Pipeline 运行</span>
        </div>
        <div id="sidebar-list" class="sidebar-scroll"></div>
      </aside>
      <main id="center-panel">
        <div id="pipeline-stepper"></div>
        <div id="stage-cards"></div>
      </main>
      <aside id="right-panel"><div id="right-content"></div></aside>
    </div>`;
    document.getElementById('btn-refresh')?.addEventListener('click', () => {
      loadRunDetail();
    });
  }

  await loadRunDetail();
  renderAll();
  startPolling();
}

document.addEventListener('DOMContentLoaded', init);
