import React, { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Check, ChevronRight, Clock3, FileSearch, Save, ShieldCheck, Wifi, X } from 'lucide-react'

export const MODE_LABELS = { demo: 'DEMO · 规则演示', live: 'LIVE · 在线模型', replay: 'REPLAY · 测试回放' }
const tokenLimit = (value, fallback) => value == null ? fallback : `${value} tokens`
const stateLabels = { pending: '待审批', needs_evidence: '需补充资料', approved: '已批准', rejected: '已驳回', verified: '来源可定位', unverified: '待验证', conflict: '存在冲突' }
const eventLabels = { 'task.created': '任务创建', 'task.started': '任务开始', 'agent.started': 'Agent 开始', 'agent.progress': 'Agent 请求', 'agent.completed': 'Agent 完成', 'agent.failed': 'Agent 失败', 'agent.blocked': 'Agent 已阻断', 'agent.attempt_failed': '请求失败记录', 'agent.retrying': '仅一次恢复重试', 'tool.started': '工具开始', 'tool.completed': '工具完成', 'review.required': '人工审查', 'task.completed': '执行完成', 'task.failed': '任务失败' }

export function FailureReport({ run, onWorkflow, onNew }) {
  const failed = run.agents.find(agent => agent.status === 'failed')
  const completed = run.agents.filter(agent => ['completed', 'waiting_approval'].includes(agent.status))
  const unstarted = run.agents.filter(agent => ['blocked', 'pending', 'queued'].includes(agent.status))
  const error = failed?.error_details || run.error_details
  return <section className="failure-report" role="status"><span className="section-kicker">RUN FAILED · {MODE_LABELS[run.mode]}</span><h2>分析未完成，报告未生成</h2><p>任务已停止，保留已完成阶段的输出；未执行阶段不会自动继续。</p><dl>
    <div><dt>失败阶段</dt><dd>{failed?.name || '任务初始化'}</dd></div>
    <div><dt>错误类型</dt><dd>{error?.code || 'UNKNOWN_ERROR'}{error?.reason ? ` / ${error.reason}` : ''}</dd></div>
    <div><dt>错误说明</dt><dd>{error?.message || run.error || '执行失败'}</dd></div>
    <div><dt>已完成阶段</dt><dd>{completed.map(agent => agent.name).join('、') || '无'}</dd></div>
    <div><dt>未执行阶段</dt><dd>{unstarted.map(agent => agent.name).join('、') || '无'}</dd></div>
  </dl><div className="failure-next"><strong>下一步建议</strong><p>{error?.code === 'MODEL_TIMEOUT' ? `查看 ${failed?.name || '任务'} 的请求截止时间${failed?.request_timeout_seconds ? `（${failed.request_timeout_seconds} 秒）` : ''}和输入规模，确认模型服务后再决定手动重跑。` : '先查看失败阶段和证据详情，核对配置或资料，再决定是否重新运行。'}重跑 Live 会重新调用模型并消耗额度，本次没有自动重跑。</p></div><div className="failure-actions"><button className="primary-button" onClick={onWorkflow}>查看失败工作流 <ArrowRight size={16} /></button><button className="primary-button" onClick={onNew}>返回资料与问题 <ArrowRight size={16} /></button></div></section>
}

export function RiskMatrix({ metrics }) {
  const suppliers = metrics?.suppliers || []
  return <section className="risk-viz"><div className="viz-heading"><div><span className="section-kicker">RISK INTELLIGENCE</span><h3>交付 × 质量风险矩阵</h3></div><span className="source-chip">{metrics?.source || '无数据'}</span></div>
    <div className="matrix-layout"><div className="matrix-chart"><span className="matrix-y">缺陷率 (%)</span><svg viewBox="0 0 480 245" role="img" aria-label="供应商风险矩阵：横轴准时交付率百分比，纵轴缺陷率百分比">
      <rect x="40" y="10" width="249" height="106" fill="#422d30" /><rect x="289" y="10" width="166" height="106" fill="#34312a" /><rect x="40" y="116" width="249" height="105" fill="#34312a" /><rect x="289" y="116" width="166" height="105" fill="#193a33" />
      {[80, 85, 90, 95, 100].map(n => <g key={n}><line x1={40 + (n - 75) / 25 * 415} x2={40 + (n - 75) / 25 * 415} y1="10" y2="221" stroke="#ffffff12" /><text x={40 + (n - 75) / 25 * 415} y="239" textAnchor="middle" fill="#8c9d9d" fontSize="10">{n}</text></g>)}
      {[0, 3, 6].map(n => <g key={n}><line x1="40" x2="455" y1={221 - n / 6 * 211} y2={221 - n / 6 * 211} stroke="#ffffff18" /><text x="29" y={224 - n / 6 * 211} textAnchor="end" fill="#8c9d9d" fontSize="10">{n}</text></g>)}
      <line x1="289" x2="289" y1="10" y2="221" stroke="#d0a66d" strokeDasharray="4 4" /><line x1="40" x2="455" y1="115.5" y2="115.5" stroke="#d0a66d" strokeDasharray="4 4" />
      {suppliers.map((s, i) => <g key={s.name}><circle cx={40 + Math.max(0, Math.min(25, s.on_time - 75)) / 25 * 415} cy={221 - Math.min(s.defect, 6) / 6 * 211} r="7" fill={s.on_time < 90 || s.defect > 3 ? '#f09b80' : '#b6de81'} stroke="#142223" strokeWidth="3"><title>{s.name}: {s.on_time}% 准时率 / {s.defect}% 缺陷率</title></circle><text x={40 + Math.max(0, Math.min(25, s.on_time - 75)) / 25 * 415 - 13} y={221 - Math.min(s.defect, 6) / 6 * 211 - 12} fill="#d8e4dc" fontSize="10">{s.name.split(' ')[0]}</text></g>)}
    </svg><span className="matrix-x">准时交付率 (%) · 轴范围 75–100 / 0–6，超范围点贴边</span></div><div className="matrix-key"><span><i className="key-high" />需关注：准时率 &lt; 90% 或缺陷率 &gt; 3%</span><span><i className="key-low" />正常：未触发演示阈值</span><p>单期供应商快照，简单平均。阈值为演示规则，需由业务团队确认。</p></div></div>
  </section>
}

export function RecentRuns({ runs, onSelect }) {
  return <section className="recent-runs"><div className="section-heading"><h2>最近任务及报告</h2><span className="section-caption">当前进程记录</span></div>{!runs.length ? <div className="compact-empty">暂无运行记录</div> : runs.slice(0, 4).map(run => <button key={run.id} onClick={() => onSelect(run)} className="recent-run-row"><span className={`run-led ${run.status}`} /><div><strong>{run.question}</strong><small>{MODE_LABELS[run.mode]} · {run.model} · {new Date(run.created_at).toLocaleTimeString('zh-CN')}</small></div><span>{run.report ? '报告已生成' : run.status}</span><ChevronRight size={16} /></button>)}</section>
}

export function RunTelemetry({ run, agent, onRetry, connection }) {
  return <><div className="telemetry-strip"><span>事件连接 <b>{connection}</b></span><span>任务耗时 <b>{run?.elapsed_seconds ?? '—'}s</b></span><span>Token 用量 <b>{run?.budget?.observed_tokens ?? '未提供'}</b></span><span>预算预留 <b>{run?.budget?.reserved_tokens ?? 0} / {run?.budget?.limit ?? '未设本地上限'}</b></span></div>
    <div className="agent-meta"><div><span>模型标识</span><strong>{agent.model || run?.model || '尚未执行'}</strong></div><div><span>实际耗时 / 请求次数</span><strong>{agent.elapsed_seconds ?? '—'}s / {agent.attempts ?? 0}</strong></div><div><span>相关证据</span><strong>{agent.evidence_count ?? 0} 条</strong></div><div><span>真实工具调用</span><strong>{agent.tools?.join(', ') || '无'}</strong></div></div>
    <div className="input-summary"><span>INPUT CONTEXT</span>{agent.input_summary || '等待资料与上游输出'}</div>
    {agent.first_failure && <div className="recovery-history"><strong>首次失败 · {agent.first_failure.code}</strong><p>{agent.first_failure.message}</p><span>恢复请求：{agent.retry_attempt || 0} / {agent.max_retries ?? 1}；最多一次，不执行外部操作。</span>{agent.attempt_history?.map(attempt => <div key={attempt.attempt}>请求 {attempt.attempt} · {attempt.status} · {attempt.elapsed_seconds ?? '—'}s{attempt.error ? ` · ${attempt.error.code}` : ''}</div>)}</div>}
    {(agent.error_details || run?.error_details) && <div className="failure-detail"><strong>{(agent.error_details || run.error_details).code}</strong><p>{(agent.error_details || run.error_details).message}</p><button className="primary-button" onClick={onRetry}>重新运行失败任务 <ArrowRight size={15} /></button></div>}
    <section className="event-timeline"><div className="section-heading"><h2>执行事件时间线</h2><span className="section-caption">后端事件 · {run?.events?.length || 0} 条</span></div>{!(run?.events?.length) ? <div className="compact-empty">等待任务事件</div> : <div className="timeline-entries">{[...run.events].reverse().map(event => <div key={event.event_id} className="timeline-event"><time>{new Date(event.timestamp).toLocaleTimeString('zh-CN', { hour12: false })}</time><span className={`event-dot ${event.type.includes('failed') ? 'failed' : ''}`} /><strong>{eventLabels[event.type] || event.type}</strong><span>{event.stage}</span><p>{event.payload.summary || event.payload.tool || event.payload.message || event.payload.decision || event.payload.mode || ''}</p><small>#{event.event_id}</small></div>)}</div>}</section>
  </>
}

export function EvidencePage({ run }) {
  const [search, setSearch] = useState('')
  const [source, setSource] = useState('')
  const [supplier, setSupplier] = useState('')
  const [kind, setKind] = useState('')
  const [verification, setVerification] = useState('')
  const evidence = run?.evidence || []
  const filtered = evidence.filter(e => (!source || e.source_file === source) && (!supplier || e.supplier === supplier) && (!kind || e.risk_type === kind) && (!verification || e.verification_status === verification) && JSON.stringify(e).toLowerCase().includes(search.toLowerCase()))
  return <><div className="page-heading"><div><div className="eyebrow">EVIDENCE & PROVENANCE</div><h1>证据中心</h1><p>文件原文、Python 计算指标和分析假设分别记录。</p></div><span className="source-chip">{evidence.length} 条证据</span></div>
    <div className="filter-toolbar"><input aria-label="搜索证据" placeholder="搜索证据、摘录或关联结论" value={search} onChange={e => setSearch(e.target.value)} /><select aria-label="来源文件" value={source} onChange={e => setSource(e.target.value)}><option value="">全部来源</option>{[...new Set(evidence.map(e => e.source_file))].map(x => <option key={x}>{x}</option>)}</select><select aria-label="供应商筛选" value={supplier} onChange={e => setSupplier(e.target.value)}><option value="">全部供应商</option>{[...new Set(evidence.map(e => e.supplier).filter(Boolean))].map(x => <option key={x}>{x}</option>)}</select><select aria-label="风险类型" value={kind} onChange={e => setKind(e.target.value)}><option value="">全部风险类型</option>{[...new Set(evidence.map(e => e.risk_type))].map(x => <option key={x}>{x}</option>)}</select><select aria-label="验证状态" value={verification} onChange={e => setVerification(e.target.value)}><option value="">全部验证状态</option>{['verified', 'unverified', 'conflict'].map(x => <option key={x} value={x}>{stateLabels[x]}</option>)}</select></div>
    {!filtered.length ? <div className="report-empty"><FileSearch size={30} /><h2>{evidence.length ? '没有符合筛选的证据' : '运行分析后建立证据目录'}</h2><p>每条原始证据保留文件名和页码、记录号或行号。</p></div> : <div className="evidence-list">{filtered.map(e => <article className="evidence-item" key={e.evidence_id}><div className="evidence-item-header"><code>{e.evidence_id}</code><span className={`verification ${e.verification_status}`}>{stateLabels[e.verification_status]}</span><span className="evidence-kind">{e.kind === 'computed' ? 'Python 计算' : e.kind === 'fact' ? '文件事实' : '模型假设'}</span>{e.demo_data && <span className="source-chip">演示数据</span>}</div><h3>{e.source_file} <small>{e.source_location}</small></h3><pre>{typeof e.supporting_excerpt === 'object' ? JSON.stringify(e.supporting_excerpt, null, 2) : e.supporting_excerpt}</pre><div className="evidence-claims"><strong>关联结论</strong>{e.related_claim.length ? e.related_claim.map((claim, i) => <p key={i}>{claim}</p>) : <p>尚无结论引用</p>}</div></article>)}</div>}
  </>
}

export function ApprovalsPage({ approvals, api, onUpdate, onSelect, setError }) {
  const [notes, setNotes] = useState({})
  const [busy, setBusy] = useState('')
  const [session, setSession] = useState(false)
  async function decision(action, choice) {
    if ((notes[action.id] || '').trim().length < 3) { setError('请填写至少 3 个字的审批意见。'); return }
    setBusy(action.id)
    try {
      if (!session) { await api('/session', { method: 'POST' }); setSession(true) }
      await api(`/approvals/${action.id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision: choice, note: notes[action.id] }) })
      await onUpdate()
      setError('')
    } catch (err) { setSession(false); setError(err.message) } finally { setBusy('') }
  }
  return <><div className="page-heading"><div><div className="eyebrow">HUMAN-IN-THE-LOOP</div><h1>待审批</h1><p>批准代表授权，系统不会执行外部采购或合同变更。</p></div><span className="source-chip">本机 Reviewer 会话</span></div>{!approvals.length ? <div className="report-empty"><ShieldCheck size={30} /><h2>暂无行动审批</h2><p>完成 Agent 分析后，高影响行动会进入此处。</p></div> : <div className="approvals-list">{approvals.map(action => <article className="approval-item" key={action.id}><div className="approval-top"><span className={`approval-state ${action.status}`}>{stateLabels[action.status]}</span><span>{MODE_LABELS[action.mode]}</span><button onClick={() => onSelect(action.task_id)}>关联任务 <ArrowRight size={14} /></button></div><h2>{action.title}</h2><p>{action.reason}</p><dl><div><dt>负责人</dt><dd>{action.owner}</dd></div><div><dt>截止时间</dt><dd>{action.deadline}</dd></div><div><dt>影响范围</dt><dd>{action.impact}</dd></div><div><dt>证据</dt><dd>{action.evidence_ids.join(' / ') || '缺失'}</dd></div></dl><div className="review-note"><ShieldCheck size={16} /><div><strong>Reviewer · {action.reviewer_opinion.decision}</strong><p>{action.reviewer_opinion.findings.join('；') || '没有额外审查发现'}</p></div></div>{['pending', 'needs_evidence'].includes(action.status) && <div className="approval-controls"><label>审批意见<textarea aria-label={`审批意见 ${action.title}`} value={notes[action.id] || ''} onChange={e => setNotes({ ...notes, [action.id]: e.target.value })} placeholder="填写核验结果或补充资料要求" /></label><div className="approval-buttons"><button disabled={busy === action.id || action.status === 'needs_evidence'} onClick={() => decision(action, 'approved')}><Check size={15} /> 批准</button><button disabled={busy === action.id} onClick={() => decision(action, 'rejected')}><X size={15} /> 驳回</button><button disabled={busy === action.id} onClick={() => decision(action, 'needs_evidence')}><FileSearch size={15} /> 补充资料</button></div></div>}{action.audit.map((entry, i) => <div className="approval-audit" key={i}>{entry.actor} · {stateLabels[entry.decision]} · {entry.note} · {new Date(entry.timestamp).toLocaleString('zh-CN')}</div>)}</article>)}</div>}</>
}

export function HistoryPage({ runs, onSelect }) {
  return <><div className="page-heading"><div><div className="eyebrow">RUN REGISTRY</div><h1>运行历史</h1><p>保留当前进程内的任务、事件与决策产出。</p></div><span className="source-chip">{runs.length} 个任务</span></div><RecentRuns runs={runs} onSelect={onSelect} /><div className="history-registry">{runs.slice(4).map(run => <button key={run.id} onClick={() => onSelect(run)}><strong>{run.question}</strong><span>{MODE_LABELS[run.mode]} · {run.status}</span><ArrowRight size={16} /></button>)}</div></>
}

export function SettingsPage({ config, api, setError, onSaved }) {
  const [busy, setBusy] = useState('')
  const [result, setResult] = useState(null)
  const [baseURL, setBaseURL] = useState('https://api.deepseek.com/v1')
  const [model, setModel] = useState('deepseek-chat')
  const [key, setKey] = useState('')
  const [outputTokens, setOutputTokens] = useState('0')
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    if (!config) return
    setBaseURL(config.configured ? config.base_url || '' : 'https://api.deepseek.com/v1')
    setModel(config.configured ? config.model : 'deepseek-chat')
    setOutputTokens(String(config.max_output_tokens ?? 0))
    setKey('')
  }, [config?.configured, config?.base_url, config?.model, config?.max_output_tokens])

  async function submit(testConnection) {
    setBusy(testConnection ? 'test' : 'save')
    setError('')
    setResult(null)
    try {
      await api('/session', { method: 'POST' })
      await api('/model/config', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service_type: 'openai_compatible', base_url: baseURL.trim(), api_key: key,
          model: model.trim(), max_output_tokens: Number(outputTokens || 0) }) })
      setKey('')
      setSaved(true)
      await onSaved()
      if (testConnection) setResult(await api('/model/test', { method: 'POST' }))
    } catch (err) {
      setError(err.message)
      setResult({ ok: false, model: model.trim(), error: { message: err.message } })
    } finally { setKey(''); setBusy('') }
  }
  return <><div className="page-heading"><div><div className="eyebrow">MODEL & EXECUTION POLICY</div><h1>配置</h1><p>AI 模型设置 · 使用您自己的模型 API</p></div><span className={`verification ${config?.configured ? 'verified' : 'unverified'}`}>{config?.configured ? '配置完整 · 可主动测试' : '模型未配置'}</span></div>
    <section className="settings-section"><h2>模型配置</h2><form className="model-config-form" onSubmit={event => { event.preventDefault(); submit(false) }}>
      <label>模型服务类型<select aria-label="模型服务类型" defaultValue="openai_compatible"><option value="openai_compatible">OpenAI Compatible</option></select><small>支持 DeepSeek、OpenAI 及其他兼容 Chat Completions 接口。</small></label>
      <label>API Base URL<input aria-label="API Base URL" type="url" required maxLength={500} value={baseURL} onChange={event => { setBaseURL(event.target.value); setResult(null) }} placeholder="https://api.deepseek.com/v1" /></label>
      <label>API Key<input aria-label="API Key" type="password" autoComplete="off" spellCheck={false} maxLength={8192} value={key} onChange={event => { setKey(event.target.value); setResult(null) }} placeholder={config?.configured ? '留空可沿用当前地址的已保存密钥' : '输入您自己的 API Key'} /><small>提交或离开页面后输入框清空；密钥不回传、不存浏览器，不写入仓库。更换地址需重新输入。</small></label>
      <label>Model Name<input aria-label="Model Name" required maxLength={160} value={model} onChange={event => { setModel(event.target.value); setResult(null) }} placeholder="deepseek-chat" /></label>
      <label>最大输出 Token（可选）<input aria-label="最大输出 Token" type="number" min="0" max="1000000" step="1" value={outputTokens} onChange={event => { setOutputTokens(event.target.value); setResult(null) }} /><small>沿用当前值；0表示不设置本地上限，服务端仍有自身限制。</small></label>
      <div className="model-config-actions"><button className="primary-button" type="submit" disabled={Boolean(busy)}><Save size={16} />{busy === 'save' ? '保存中…' : '保存配置'}</button><button className="primary-button" type="button" disabled={Boolean(busy)} onClick={event => { if (event.currentTarget.form.reportValidity()) submit(true) }}><Wifi size={16} />{busy === 'test' ? '正在测试…' : '测试连接'}</button></div>
    </form><p className="settings-description">配置仅保存在当前后端进程内存中，刷新页面可继续使用，重启服务后恢复环境变量或本地 .env。测试连接会发送一次最小模型请求并消耗额度；保存配置不会调用模型。</p>
    {saved && <div className="model-config-result" role="status">配置已保存在当前进程，未写入文件。</div>}
    {result && <div className={`model-config-result ${result.ok ? 'test-ok' : 'test-error'}`} role={result.ok ? 'status' : 'alert'}><strong>{result.ok ? result.message : result.error.message}</strong><span>模型：{result.model || model}{result.elapsed_seconds != null ? ` · ${result.elapsed_seconds}s` : ''}</span>{result.ok && result.response_summary && <span>{result.response_summary}</span>}</div>}
    </section><section className="settings-section"><h2>执行与审查政策</h2><div className="settings-grid">{[['协议', 'OpenAI Chat Completions'], ['配置来源', config?.configuration_source === 'process_memory' ? '当前进程内存' : '环境变量 / 本地 .env'], ['请求超时', `${config?.timeout_seconds ?? '—'}s`], ['输出长度', tokenLimit(config?.max_output_tokens, '由服务端决定')], ['任务时间上限', `${config?.task_timeout_seconds ?? '—'}s`], ['编排框架', 'AutoGen 0.7.5']].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div></section></>
}

export function ReportInsights({ run }) {
  return <div className="report-insights"><div className="report-insight-top"><div><span className="section-kicker">DECISION READINESS</span><h2>{run.review?.decision === 'needs_evidence' ? '证据不足，需补充资料' : run.status === 'waiting_approval' ? '分析完成 · 待人工审批' : '分析记录已就绪'}</h2><p>{MODE_LABELS[run.mode]} · {run.model}</p></div><span className="readiness-mark"><ShieldCheck size={26} /></span></div><div className="report-summary-grid"><div><span>Reviewer</span><strong>{run.review?.decision || '—'}</strong></div><div><span>证据目录</span><strong>{run.evidence?.length || 0} 条</strong></div><div><span>行动建议</span><strong>{run.approvals?.length || 0} 项</strong></div><div><span>事实/计算引用覆盖</span><strong>{run.confidence?.cited_claims || 0} / {run.confidence?.total_claims || 0}</strong></div></div><p className="coverage-note">引用覆盖仅代表 ID 可定位，不是语义核实或校准概率。单期资料不提供趋势；需补充历史数据。</p><h3>供应商风险排名</h3><div className="report-ranking">{run.risk_ranking?.length ? run.risk_ranking.map((risk, i) => <div key={i}><b>{String(i + 1).padStart(2, '0')}</b><strong>{risk.supplier}</strong><span className={`risk-badge risk-${risk.level === 'high' ? 'high' : 'low'}`}>{risk.level}</span><p>{risk.reason}</p><code>{risk.evidence_ids.join(' / ') || '无证据引用'}</code></div>) : <div className="compact-empty">当前资料未生成供应商风险排名</div>}</div></div>
}
