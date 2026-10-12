import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import ReactMarkdown from 'react-markdown'
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, BarChart3, Check,
  CheckCheck, ChevronDown, ChevronRight, CircleAlert, Clock3, Download,
  File, FileSpreadsheet, FileText, FolderOpen, GitBranch, LayoutDashboard,
  LoaderCircle, Menu, MoreHorizontal, Plus, Search, Shield, ShieldCheck,
  Sparkles, UploadCloud, WandSparkles, X, Zap, Settings, History, FileSearch,
} from 'lucide-react'
import './style.css'
import './cockpit.css'
import { ApprovalsPage, EvidencePage, FailureReport, HistoryPage, MODE_LABELS, RecentRuns, ReportInsights, RiskMatrix, RunTelemetry, SettingsPage } from './cockpit'

const AGENT_ICONS = [GitBranch, Search, BarChart3, Shield, Zap]
const DEFAULT_AGENTS = [
  { id: 'planner', name: 'Planner Agent', role: '拆解决策目标与分析边界' },
  { id: 'research', name: 'Research Agent', role: '提取证据与数据来源' },
  { id: 'analyst', name: 'Analyst Agent', role: '量化趋势与关键指标' },
  { id: 'risk', name: 'Risk Reviewer Agent', role: '审查假设、反例与风险' },
  { id: 'action', name: 'Action Agent', role: '制定优先级与行动计划' },
]
const number = (value) => Number(value || 0).toLocaleString('en-US')
const time = (value) => value ? new Date(value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }) : '--:--'

async function api(path, options) {
  let response
  try {
    response = await fetch(`/api${path}`, { ...options, headers: { ...options?.headers } })
  } catch {
    throw new Error('无法连接后端服务，请确认 FastAPI 已在 8000 端口启动。')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `请求失败 (${response.status})`)
  }
  return response.json()
}

function StatusPill({ status, retryAttempt = 0, maxRetries = 1 }) {
  const labels = { pending: '待执行', queued: '待执行', running: '执行中', retrying: `恢复重试 (${retryAttempt || 1}/${maxRetries})`, completed: '已完成', failed: '失败', blocked: '已阻断', waiting_approval: '待审批' }
  return <span className={`status-pill status-${status || 'pending'}`}>
    <span className="status-dot" />{labels[status] || '等待中'}
  </span>
}

function Markdown({ children }) {
  return <div className="markdown"><ReactMarkdown>{children || ''}</ReactMarkdown></div>
}

function App() {
  const [view, setView] = useState('overview')
  const [bootstrap, setBootstrap] = useState(null)
  const [documents, setDocuments] = useState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [question, setQuestion] = useState('')
  const [mode, setMode] = useState('demo')
  const [run, setRun] = useState(null)
  const [history, setHistory] = useState([])
  const [selectedAgent, setSelectedAgent] = useState('planner')
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [mobileMenu, setMobileMenu] = useState(false)
  const [connection, setConnection] = useState('连接中')
  const [streamState, setStreamState] = useState('未连接')
  const [submitting, setSubmitting] = useState(false)
  const [approvals, setApprovals] = useState([])
  const inputRef = useRef(null)
  const cursorRef = useRef({})
  const submissionRef = useRef(false)
  const navItems = [['overview', '总览', LayoutDashboard], ['workflow', 'Agent 工作流', GitBranch], ['evidence', '证据中心', FileSearch], ['report', '决策报告', FileText], ['approvals', '待审批', ShieldCheck], ['history', '运行历史', History], ['settings', '配置', Settings]]

  const refresh = useCallback(async () => {
    try {
      const data = await api('/bootstrap')
      setBootstrap(data)
      setDocuments(data.documents)
      setQuestion((previous) => previous || data.default_question)
      setSelectedIds((previous) => previous.length ? previous : data.demo_document_ids)
      setHistory(data.runs)
      setApprovals(data.approvals || [])
      setConnection('已连接')
      setRun(previous => previous ? data.runs.find(item => item.id === previous.id) || previous : data.runs[0] || null)
      setError('')
    } catch (err) { setError(err.message); setConnection('已断开') }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const health = await api('/health')
        setConnection(health.status === 'ok' ? '已连接' : '异常')
        const data = await api('/bootstrap')
        setHistory(data.runs)
        setApprovals(data.approvals || [])
        setBootstrap(data)
      } catch { setConnection('已断开') }
    }, 10000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!run || !['queued', 'running'].includes(run.status)) { setStreamState(run ? '执行结束' : '未连接'); return undefined }
    const id = run.id
    const stream = new EventSource(`/api/runs/${id}/events?after=${cursorRef.current[id] || 0}`)
    stream.onopen = () => { setStreamState('已连接'); setConnection('已连接') }
    stream.onmessage = event => {
      const data = JSON.parse(event.data)
      if (data.event.event_id <= (cursorRef.current[id] || 0)) return
      cursorRef.current[id] = data.event.event_id
      setRun(current => current?.id === id ? data.run : current)
      if (!['queued', 'running'].includes(data.run.status)) {
        stream.close()
        setStreamState('执行结束')
        setHistory(items => [data.run, ...items.filter(item => item.id !== id)])
        api('/approvals').then(setApprovals).catch(err => setError(err.message))
      }
    }
    stream.onerror = () => { setStreamState('重连中'); setConnection('重连中') }
    return () => stream.close()
  }, [run?.id, run?.status])

  const currentAgents = run?.agents || DEFAULT_AGENTS.map((agent) => ({ ...agent, status: 'pending', output: '' }))
  const activeAgent = currentAgents.find((agent) => agent.id === selectedAgent) || currentAgents[0]
  const completedCount = currentAgents.filter((agent) => agent.status === 'completed').length
  const running = run && ['queued', 'running'].includes(run.status)
  const sameSources = (ids) => ids?.length === selectedIds.length && ids.every(id => selectedIds.includes(id))
  const showingCurrentRun = run && sameSources(run.document_ids)
  const showingDemoPreview = !run && sameSources(bootstrap?.demo_document_ids)
  const metrics = showingCurrentRun ? run.metrics : showingDemoPreview ? bootstrap?.metrics : null
  const metricSourceLabel = showingCurrentRun ? `当前任务 · ${run.id.slice(0, 8)} · ${run.status}` : showingDemoPreview ? '示例数据预览 · 尚未分析' : '已选资料待分析 · 尚无当前指标'
  const highRiskCount = metrics ? metrics.suppliers.filter(s => s.on_time < 90 || s.defect > 3).length : '—'
  const pendingApprovals = approvals.filter(a => ['pending', 'needs_evidence'].includes(a.status)).length
  const activeRuns = history.filter(r => ['queued', 'running'].includes(r.status)).length + (running && !history.some(r => r.id === run.id) ? 1 : 0)
  const maxSpend = metrics ? Math.max(...metrics.suppliers.map((supplier) => supplier.spend)) : 1

  async function upload(files) {
    const list = Array.from(files || [])
    if (!list.length) return
    if (list.some((file) => !/\.(pdf|csv|txt)$/i.test(file.name))) {
      setError('仅支持 PDF、CSV、TXT 文件。')
      return
    }
    setError('')
    setUploading(true)
    const form = new FormData()
    list.forEach((file) => form.append('files', file))
    try {
      const data = await api('/files', { method: 'POST', body: form })
      setDocuments((items) => [...items, ...data.documents])
      setSelectedIds((ids) => [...ids, ...data.documents.map((doc) => doc.id)])
    } catch (err) { setError(err.message) }
    finally { setUploading(false); if (inputRef.current) inputRef.current.value = '' }
  }

  async function startRun() {
    if (submissionRef.current) return
    setError('')
    if (mode === 'live' && !bootstrap?.live_available) {
      setError('请先完成模型配置')
      changeView('settings')
      return
    }
    if (!question.trim() || question.trim().length < 5) { setError('请输入至少 5 个字的决策问题。'); return }
    if (!selectedIds.length) { setError('请至少选择一份分析资料。'); return }
    submissionRef.current = true
    setSubmitting(true)
    try {
      const created = await api('/runs', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({ question: question.trim(), document_ids: selectedIds, mode }),
      })
      setRun(created)
      setHistory(items => [created, ...items])
      setSelectedAgent('planner')
      setView('workflow')
      setMobileMenu(false)
    } catch (err) { setError(err.message) } finally { submissionRef.current = false; setSubmitting(false) }
  }

  function changeView(next) { setView(next); setMobileMenu(false); window.scrollTo(0, 0) }
  function selectRun(item) { setRun(item); setSelectedIds(item.document_ids); setSelectedAgent('planner'); changeView('workflow') }
  async function retryRun() {
    try { const next = await api(`/runs/${run.id}/retry`, { method: 'POST' }); selectRun(next); setHistory(items => [next, ...items]) } catch (err) { setError(err.message) }
  }
  function toggleDocument(id) {
    setSelectedIds((items) => items.includes(id) ? items.filter((item) => item !== id) : [...items, id])
  }

  return <div className="app-shell">
    {mobileMenu && <button className="mobile-scrim" aria-label="关闭导航" onClick={() => setMobileMenu(false)} />}
    <aside className={`sidebar ${mobileMenu ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark"><ShieldCheck size={22} strokeWidth={2.2} /></div><div><strong>Sentinel<span>AI</span></strong><small>OPERATIONS COCKPIT / 2.0</small></div></div>
      <div className="workspace-selector"><span className="workspace-avatar">S</span><div><strong>Sentinel Workspace</strong><small>企业决策空间</small></div><ChevronDown size={14} /></div>
      <div className="nav-label">工作区</div>
      <nav className="primary-nav" aria-label="主导航">
        {navItems.map(([key, label, Icon]) => <button key={key} className={view === key ? 'active' : ''} onClick={() => changeView(key)}><Icon size={18} />{label}{key === 'approvals' && pendingApprovals > 0 && <span className="nav-count">{pendingApprovals}</span>}<ChevronRight size={15} className="nav-arrow" /></button>)}
      </nav>
      <div className="nav-label history-label">最近运行 <span>{history.length || '0'}</span></div>
      <div className="history-list">
        {history.length ? history.slice(0, 4).map((item) => <button key={item.id} className={run?.id === item.id ? 'history-item selected' : 'history-item'} onClick={() => selectRun(item)}>
          <span className="history-dot" /><span className="history-text">{item.question}</span><span className="history-time">{time(item.created_at)}</span>
        </button>) : <div className="history-empty">运行记录将在这里显示</div>}
      </div>
      <div className="sidebar-bottom">
        <div className="sidebar-note"><span className="note-icon"><ShieldCheck size={15} /></span><strong>人工审查边界</strong><p>建议需要审批，不自动执行外部操作。</p></div>
        <div className="sidebar-profile"><div className="profile-avatar">SA</div><div><strong>Hackathon Demo</strong><small>Workspace Admin</small></div><MoreHorizontal size={17} /></div>
      </div>
    </aside>

    <div className="app-content">
      <header className="topbar"><div className="topbar-left"><button className="icon-button menu-toggle" aria-label="打开导航" onClick={() => setMobileMenu(true)}><Menu size={20} /></button><span>SentinelAI</span><ChevronRight size={14} /><strong>{navItems.find(item => item[0] === view)?.[1]}</strong></div><div className="topbar-right"><span className={`mode-badge mode-${mode}`} title="新任务选择的运行模式">新建 {MODE_LABELS[mode]}</span>{run && <span className={`mode-badge mode-${run.mode}`} title="当前任务的实际执行模式">当前 {MODE_LABELS[run.mode]}</span>}<span className={`connection-label ${connection === '已连接' ? 'connected' : ''}`}><i />{connection}</span><span className="model-state">{bootstrap?.live_available ? bootstrap.model_config.model : '模型未配置'}</span><StatusPill status={run?.status} /></div></header>
      <main className="main-content">
        {error && <div className="error-banner" role="alert"><CircleAlert size={18} /><span>{error}</span><button aria-label="关闭错误提示" onClick={() => setError('')}><X size={16} /></button></div>}

        {view === 'overview' && <>
          <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> INTELLIGENT OPERATIONS COCKPIT</div><h1>决策情报总览</h1><p>供应链风险 · 证据追溯 · 多 Agent 审查 · 人工决策</p></div><div className="heading-actions"><button className="primary-button heading-button" onClick={() => changeView('settings')}><Settings size={17} /> 模型配置</button><button className="primary-button heading-button" onClick={() => document.getElementById('decision-input')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}><Plus size={17} /> 新建决策分析</button></div></div>
          {bootstrap && !bootstrap.live_available && <div className="model-setup-notice" role="status"><ShieldCheck size={19} /><span>Live 模式需要配置您自己的模型 API。Demo 模式无需配置。</span><button onClick={() => changeView('settings')}>模型配置 <ArrowRight size={16} /></button></div>}
          <div className="scenario-strip"><div className="scenario-icon"><Activity size={20} /></div><div className="scenario-copy"><span>供应链分析场景 <span className="mini-separator">/</span> SUPPLY CHAIN</span><strong>供应链韧性与交付风险评估</strong></div><span className="scenario-tag"><span />{selectedIds.some(id => documents.find(d => d.id === id)?.demo) ? '包含演示数据' : '已选上传资料'}</span></div>

          <div className="dashboard-grid"><div className="dashboard-main">
            <div className="section-heading"><div><span className="section-kicker">01 / DATA SNAPSHOT</span><h2>关键指标概览</h2></div><span className="section-caption">{metrics?.source || '暂无结构化指标'} · 单期快照</span></div>
            <div className="metric-source-state" role="status">{metricSourceLabel}</div>
            <div className="metric-grid">
              <div className="metric"><div className="metric-top"><span>供应商总数</span><span className="metric-icon teal"><FolderOpen size={18} /></span></div><div className="metric-value">{metrics?.count ?? '—'}<small>家</small></div><div className="metric-bottom"><span className="neutral-tag">样本总量</span> 活跃供应商</div></div>
              <div className="metric"><div className="metric-top"><span>高风险供应商</span><span className="metric-icon orange"><CircleAlert size={18} /></span></div><div className="metric-value">{highRiskCount}<small>家</small></div><div className="metric-bottom"><span className="negative-tag">需关注</span> 演示阈值</div></div>
              <div className="metric"><div className="metric-top"><span>待审批行动</span><span className="metric-icon blue"><ShieldCheck size={18} /></span></div><div className="metric-value">{pendingApprovals}<small>项</small></div><div className="metric-bottom"><span className="neutral-tag">人工门禁</span> 服务端状态</div></div>
              <div className="metric"><div className="metric-top"><span>当前运行任务</span><span className="metric-icon teal"><Activity size={18} /></span></div><div className="metric-value">{activeRuns}<small>/ 3</small></div><div className="metric-bottom"><span className="positive-tag">并发上限</span> 后端控制</div></div>
            </div>
            <RiskMatrix metrics={metrics} />

            <div className="section-heading analysis-heading"><div><span className="section-kicker">02 / SIGNAL ANALYSIS</span><h2>供应商表现</h2></div><span className="section-caption">来源：{metrics?.source || '无数据'}</span></div>
            <div className="chart-panel"><div className="panel-topline"><div><h3>交付表现与采购敞口</h3><p>比较供应商准时率和月度支出，快速定位风险集中区。</p></div><span className="panel-overline">{metrics?.count || 0} SUPPLIERS</span></div>
              <div className="supplier-table"><div className="supplier-table-head"><span>供应商 / 地区</span><span>准时交付率</span><span>月采购额</span><span>风险等级</span></div>
                {(metrics?.suppliers || []).map((supplier) => { const alert = supplier.on_time < 90 || supplier.defect > 3; return <div className="supplier-row" key={supplier.name}><div className="supplier-name"><span className={`supplier-avatar ${alert ? 'avatar-alert' : ''}`}>{supplier.name.charAt(0)}</span><div><strong>{supplier.name}</strong><small>{supplier.region}</small></div></div><div className="rate-cell"><div className="rate-line"><strong>{supplier.on_time}%</strong><div className="progress-track"><span className={alert ? 'bar-alert' : ''} style={{ width: `${supplier.on_time}%` }} /></div></div></div><div className="spend-cell"><span>${number(supplier.spend)}</span><div className="spend-track"><span style={{ width: `${maxSpend > 0 ? supplier.spend / maxSpend * 100 : 0}%` }} /></div></div><div><span className={`risk-badge ${alert ? 'risk-high' : 'risk-low'}`}><span />{alert ? '需关注' : '正常'}</span></div></div> })}
              </div><div className="chart-footnote"><CircleAlert size={14} /> 风险阈值：准时率 &lt; 90% 或缺陷率 &gt; 3%。仅用于演示，不代表实际风控标准。</div>
            </div>
            <RecentRuns runs={history} onSelect={selectRun} />

            <div className="section-heading workflow-heading"><div><span className="section-kicker">03 / AGENT ORCHESTRATION</span><h2>决策工作流</h2></div><button className="text-link" onClick={() => changeView('workflow')}>查看工作流 <ArrowRight size={15} /></button></div>
            <div className="workflow-preview">{currentAgents.map((agent, index) => { const Icon = AGENT_ICONS[index]; return <React.Fragment key={agent.id}><button onClick={() => { setSelectedAgent(agent.id); changeView('workflow') }} className={`preview-step ${agent.status === 'running' ? 'preview-active' : ''}`}><span className={`preview-icon ${agent.status}`}><Icon size={20} /></span><span className="preview-index">0{index + 1}</span><strong>{agent.name.replace(' Agent', '')}</strong><small>{agent.role.split('与')[0]}</small></button>{index < 4 && <div className="preview-connector"><ArrowRight size={15} /></div>}</React.Fragment> })}</div>
          </div>

            <aside className="right-rail" id="decision-input"><div className="rail-header"><div><span className="section-kicker">START A NEW RUN</span><h2>发起决策分析</h2></div><WandSparkles size={20} /></div><div className="rail-body">
              <label className="field-label" htmlFor="decision-question">决策问题 <span>01</span></label><textarea id="decision-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={1000} placeholder="输入需要分析的业务问题..." /><div className="field-hint">清晰的问题有助于 Agent 形成更聚焦的结论。</div>
              <div className="field-label document-label">分析资料 <span>{selectedIds.length} 已选择</span></div>
              <input ref={inputRef} type="file" accept=".pdf,.csv,.txt" multiple hidden onChange={(event) => upload(event.target.files)} />
              <button className={`upload-zone ${dragging ? 'dragging' : ''}`} onClick={() => inputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); upload(event.dataTransfer.files) }} disabled={uploading}><span className="upload-icon">{uploading ? <LoaderCircle size={22} className="spin" /> : <UploadCloud size={22} />}</span><strong>{uploading ? '正在上传…' : '点击或拖拽上传文件'}</strong><small>支持 PDF、CSV、TXT · 单文件最大 10 MB</small></button>
              <div className="files-list">{documents.map((doc) => <button className={`file-row ${selectedIds.includes(doc.id) ? 'file-selected' : ''}`} key={doc.id} onClick={() => toggleDocument(doc.id)} title={doc.name}><span className={`file-type-icon ${doc.type}`}>{doc.type === 'csv' ? <FileSpreadsheet size={17} /> : doc.type === 'pdf' ? <File size={17} /> : <FileText size={17} />}</span><span className="file-info"><strong>{doc.name}</strong><small>{doc.demo ? '演示文件' : '上传文件'} · {(doc.size / 1024).toFixed(1)} KB</small></span><span className="file-checkbox">{selectedIds.includes(doc.id) && <Check size={13} />}</span></button>)}</div>
              <div className="field-label mode-label">运行模式 <span>02</span></div><div className="mode-control"><button className={mode === 'demo' ? 'chosen' : ''} onClick={() => setMode('demo')}><Zap size={15} />Demo</button><button className={mode === 'live' ? 'chosen' : ''} onClick={() => setMode('live')} title={!bootstrap?.live_available ? '启动前需完成模型配置' : 'AutoGen 0.7.5'}><Sparkles size={15} />Live</button><button className={mode === 'replay' ? 'chosen' : ''} onClick={() => setMode('replay')}>Replay</button></div><div className="mode-explainer">{mode === 'demo' ? '规则演示 · 不执行 AI 推理' : mode === 'replay' ? '测试回放 · 不执行在线模型调用' : '在线模型调用 · 消耗 API 额度'}</div>
              <button className="run-button" onClick={startRun} disabled={Boolean(running) || submitting || uploading || !bootstrap}>{running || submitting ? <><LoaderCircle size={18} className="spin" /> Agent 正在运行</> : <><Sparkles size={18} /> 启动多 Agent 分析 <ArrowRight size={17} /></>}</button>
              <div className="privacy-note"><ShieldCheck size={16} /> 文件仅用于当前进程的分析，不会持久保存。</div>
            </div></aside>
          </div>
        </>}

        {view === 'workflow' && <><div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> MULTI-AGENT WORKFLOW</div><h1>Agent 工作流</h1><p>五个独立角色依次接力，从问题拆解到风险审查与行动建议。</p></div><StatusPill status={run?.status} /></div>
          <div className="run-summary"><div className="summary-main"><span className="section-kicker">CURRENT DECISION</span><h2>{run?.question || question || '等待决策任务'}</h2><div className="summary-meta"><span><Clock3 size={14} /> {run ? time(run.created_at) : '尚未运行'}</span><span><FolderOpen size={14} /> {run?.document_ids.length || selectedIds.length} 份资料</span><span><Zap size={14} /> {MODE_LABELS[run?.mode || mode]}</span></div></div><div className="run-progress"><span>任务进度</span><strong>{currentAgents.filter(a => ['completed', 'waiting_approval'].includes(a.status)).length}<small> / 5</small></strong><div className="run-progress-track"><span style={{ width: `${currentAgents.filter(a => ['completed', 'waiting_approval'].includes(a.status)).length * 20}%` }} /></div></div></div>
          {run?.error && <div className="run-failure"><CircleAlert size={17} />{run.error}</div>}
          <div className="section-heading workflow-full-heading"><div><span className="section-kicker">EXECUTION PIPELINE</span><h2>执行链路</h2></div><span className="section-caption">Planner → Research → Analyst → Risk Reviewer → Action</span></div>
          <div className="pipeline">{currentAgents.map((agent, index) => { const Icon = AGENT_ICONS[index]; return <React.Fragment key={agent.id}><button className={`pipeline-node ${selectedAgent === agent.id ? 'selected' : ''}`} onClick={() => setSelectedAgent(agent.id)}><div className="pipeline-node-top"><span className={`pipeline-icon ${agent.status}`}><Icon size={20} /></span><span className="pipeline-number">0{index + 1}</span></div><strong>{agent.name}</strong><small>{agent.role}</small><StatusPill status={agent.status} /><div className="node-runtime"><span>{agent.started_at ? agent.model || run?.model : '尚未执行'}</span><span>{agent.elapsed_seconds ?? '—'}s · {agent.evidence_count ?? 0} 证据</span></div>{(agent.summary || agent.blocked_reason) && <div className="node-summary" title={agent.summary || agent.blocked_reason}>{agent.summary || agent.blocked_reason}</div>}</button>{index < 4 && <span className={`pipeline-link ${agent.status === 'completed' ? 'linked' : ''}`}><ArrowRight size={18} /></span>}</React.Fragment> })}</div>
          <div className="agent-detail"><div className="agent-detail-header"><div className={`detail-icon ${activeAgent.status}`}>{React.createElement(AGENT_ICONS[currentAgents.indexOf(activeAgent)], { size: 23 })}</div><div><span className="section-kicker">AGENT OUTPUT / 0{currentAgents.indexOf(activeAgent) + 1}</span><h2>{activeAgent.name}</h2><p>{activeAgent.role}</p></div><StatusPill status={activeAgent.status} /></div><div className="agent-output">{activeAgent.output ? <Markdown>{activeAgent.output}</Markdown> : activeAgent.status === 'blocked' ? <div className="empty-output"><CircleAlert size={26} /><strong>当前阶段未执行</strong><span>{activeAgent.blocked_reason}</span></div> : activeAgent.status === 'running' ? <div className="empty-output"><LoaderCircle size={26} className="spin" /><strong>正在处理资料与前序结论</strong><span>完成后会在这里显示可追溯的阶段输出。</span></div> : <div className="empty-output"><span className="empty-output-icon"><FileText size={27} /></span><strong>等待 Agent 输出</strong><span>启动分析并选择 Agent 查看其阶段结论。</span></div>}</div><div className="detail-footer"><span><CheckCheck size={15} /> {activeAgent.completed_at ? `${activeAgent.status === 'failed' ? '失败于' : '完成于'} ${time(activeAgent.completed_at)}` : activeAgent.status === 'blocked' ? '因上游失败未执行' : '输出将在此显示'}</span>{run?.report && <button onClick={() => changeView('report')}>查看完整报告 <ArrowRight size={15} /></button>}</div></div>
          <RunTelemetry run={run} agent={activeAgent} connection={streamState} onRetry={retryRun} />
        </>}

        {view === 'report' && <><div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> DECISION REPORT</div><h1>决策报告</h1><p>包含规划、证据、量化分析、风险审查与行动方案的完整记录。</p></div>{run?.report && <a className="primary-button heading-button" href={`/api/runs/${run.id}/report`} download="sentinelai-report.md"><Download size={17} /> 下载 Markdown</a>}</div>
          {run?.report ? <><ReportInsights run={run} /><div className="report-layout"><div className="report-paper"><div className="report-paper-heading"><span className="report-mark"><ShieldCheck size={17} /> SENTINELAI REPORT</span><span>RUN / {run.id.slice(0, 8).toUpperCase()}</span></div><Markdown>{run.report}</Markdown></div><aside className="report-aside"><span className="section-kicker">REPORT DETAILS</span><h3>报告信息</h3><div className="report-meta-row"><span>状态</span><StatusPill status={run.status} /></div><div className="report-meta-row"><span>分析模式</span><strong>{MODE_LABELS[run.mode]}</strong></div><div className="report-meta-row"><span>证据文件</span><strong>{run.document_ids.length} 份</strong></div><div className="report-meta-row"><span>参与 Agent</span><strong>5 个</strong></div><div className="report-meta-row"><span>生成时间</span><strong>{time(run.completed_at)}</strong></div><div className="report-notice"><Shield size={17} /><p>建议由业务负责人复核数据与结论后执行。</p></div><button className="primary-button" onClick={() => changeView('approvals')}>审查行动建议 <ArrowRight size={15} /></button></aside></div></> : run?.status === 'failed' ? <FailureReport run={run} onWorkflow={() => { setSelectedAgent(run.agents.find(a => a.status === 'failed')?.id || 'planner'); changeView('workflow') }} onNew={() => changeView('overview')} /> : <div className="report-empty"><span><FileText size={32} /></span><h2>还没有生成报告</h2><p>{running ? 'Agent 正在协作中，完成后报告将自动出现在这里。' : '先运行一次决策分析，即可查看和下载 Markdown 报告。'}</p><button className="primary-button" onClick={() => changeView(running ? 'workflow' : 'overview')}>{running ? '查看执行进度' : '发起分析'} <ArrowRight size={16} /></button></div>}
        </>}
        {view === 'evidence' && <EvidencePage run={run} />}
        {view === 'approvals' && <ApprovalsPage approvals={approvals} api={api} onUpdate={refresh} onSelect={id => { const target = history.find(item => item.id === id); if (target) selectRun(target) }} setError={setError} />}
        {view === 'history' && <HistoryPage runs={history} onSelect={selectRun} />}
        {view === 'settings' && <SettingsPage config={bootstrap?.model_config} api={api} setError={setError} onSaved={refresh} />}
      </main>
      <footer className="app-footer"><span>© 2026 SentinelAI · Intelligent Operations Cockpit</span><span>EVIDENCE → ANALYSIS → REVIEW → APPROVAL <span className="footer-dot">●</span> V2.0</span></footer>
    </div>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
