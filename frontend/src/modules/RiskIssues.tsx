import { useEffect, useState } from 'react'
import { api } from '../api'
import { StatePill } from '../views/ui'

const categories = ['Academic', 'Student', 'Faculty/Workforce', 'Finance', 'Infrastructure', 'Operations', 'Compliance', 'Safety', 'Administration']
const levels = ['LOW', 'MEDIUM', 'HIGH']
const severities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

const emptyRisk = {
  title: '', description: '', category: 'Infrastructure', severity: 'MEDIUM',
  likelihood: 'MEDIUM', impact: 'MEDIUM', priority: 'MEDIUM', owner_id: '', due_at: '',
}

export default function RiskIssues() {
  const [risks, setRisks] = useState<any[]>([])
  const [owners, setOwners] = useState<any[]>([])
  const [summary, setSummary] = useState<any>({})
  const [filters, setFilters] = useState({ status: '', severity: '', category: '', owner_id: '' })
  const [selected, setSelected] = useState<any>(null)
  const [form, setForm] = useState<any>(emptyRisk)
  const [editing, setEditing] = useState(false)
  const [creating, setCreating] = useState(false)
  const [action, setAction] = useState({ description: '', owner_id: '', due_at: '' })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true); setError('')
    try {
      const [riskResponse, summaryResponse, ownerResponse] = await Promise.all([api.risks(filters), api.riskSummary(), api.riskOwners()])
      setRisks(riskResponse.risks || [])
      setSummary(summaryResponse.summary || {})
      setOwners(ownerResponse.owners || [])
    } catch (err: any) { setError(err?.message || 'Unable to load campus risks.') }
    finally { setLoading(false) }
  }

  async function openRisk(risk: any) {
    try { setSelected((await api.risk(risk.id)).risk) } catch (err: any) { setError(err?.message || 'Unable to load risk details.') }
  }

  useEffect(() => { void load() }, [filters.status, filters.severity, filters.category, filters.owner_id])

  function setField(key: string, value: any) { setForm((current: any) => ({ ...current, [key]: value })) }
  function dateValue(value: string) { return value ? new Date(value).toISOString() : null }

  async function saveRisk() {
    setError(''); setMessage('')
    try {
      const body = { ...form, due_at: dateValue(form.due_at), owner_id: form.owner_id || null }
      const response = editing ? await api.updateRisk(selected.id, body) : await api.createRisk(body)
      setSelected(response.risk); setCreating(false); setEditing(false); setMessage(editing ? 'Risk updated.' : 'Risk created.')
      await load()
    } catch (err: any) { setError(err?.message || 'Unable to save risk.') }
  }

  async function runRiskAction(name: string) {
    if (!selected) return
    setError(''); setMessage('')
    try {
      let response
      if (name === 'resolve') response = await api.resolveRisk(selected.id, 'Resolved by Campus Head', selected.resolution_notes || '')
      if (name === 'close') response = await api.closeRisk(selected.id, 'Closed after corrective action verification')
      if (name === 'escalate') response = await api.escalateRisk(selected.id, 'Serious campus risk requires higher authority')
      if (response?.risk) setSelected(response.risk)
      setMessage(`${name[0].toUpperCase() + name.slice(1)} completed.`); await load()
    } catch (err: any) { setError(err?.message || `Unable to ${name} risk.`) }
  }

  async function assign(ownerId: string) {
    if (!selected || !ownerId) return
    try { const response = await api.assignRisk(selected.id, ownerId); setSelected(response.risk); setMessage('Owner assigned.'); await load() }
    catch (err: any) { setError(err?.message || 'Unable to assign owner.') }
  }

  async function addAction() {
    if (!selected || !action.description.trim() || !action.owner_id) return setError('Corrective action description and owner are required.')
    try {
      const response = await api.createRiskAction(selected.id, { ...action, due_at: dateValue(action.due_at) })
      setSelected((current: any) => ({ ...current, actions: [...(current.actions || []), response.action] })); setAction({ description: '', owner_id: '', due_at: '' }); setMessage('Corrective action added.'); await load()
    } catch (err: any) { setError(err?.message || 'Unable to add corrective action.') }
  }

  async function actionUpdate(id: string, operation: 'complete' | 'verify') {
    try {
      const response = operation === 'complete' ? await api.completeRiskAction(id, 'Completed by Campus Head') : await api.verifyRiskAction(id)
      setSelected((current: any) => ({ ...current, actions: (current.actions || []).map((item: any) => item.id === id ? response.action : item) })); setMessage(`Corrective action ${operation}d.`)
    } catch (err: any) { setError(err?.message || `Unable to ${operation} corrective action.`) }
  }

  function beginEdit() {
    if (!selected) return
    setForm({ ...selected, due_at: selected.due_at ? selected.due_at.slice(0, 16) : '', owner_id: selected.owner_id || '' }); setEditing(true); setCreating(true)
  }

  return <div className="fade-in campus-head-page">
    <div className="page-head"><div><h1>Risk &amp; Issues</h1><p>Campus-scoped risks, corrective actions, and escalation status.</p></div><button className="btn btn-crimson" onClick={() => { setForm(emptyRisk); setEditing(false); setCreating(true) }}>Create Risk / Issue</button></div>
    {error && <div className="err-box">{error}</div>}{message && <div className="success-box">{message}</div>}
    <div className="campus-head-metrics risk-summary-metrics">
      <div className="campus-head-metric"><label>Open Risks</label><strong>{summary.open || 0}</strong></div>
      <div className="campus-head-metric"><label>High / Critical</label><strong>{summary.high_critical || 0}</strong></div>
      <div className="campus-head-metric"><label>Overdue Actions</label><strong>{summary.overdue_actions || 0}</strong></div>
      <div className="campus-head-metric"><label>Escalated</label><strong>{summary.escalated || 0}</strong></div>
      <div className="campus-head-metric"><label>Resolved</label><strong>{summary.resolved || 0}</strong></div>
    </div>
    <div className="campus-head-panel"><div className="risk-filters">
      <select className="select" value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}><option value="">All statuses</option><option value="OPEN">Open</option><option value="IN_PROGRESS">In progress</option><option value="RESOLVED">Resolved</option><option value="CLOSED">Closed</option></select>
      <select className="select" value={filters.severity} onChange={e => setFilters({ ...filters, severity: e.target.value })}><option value="">All severities</option>{severities.map(value => <option key={value}>{value}</option>)}</select>
      <select className="select" value={filters.category} onChange={e => setFilters({ ...filters, category: e.target.value })}><option value="">All categories</option>{categories.map(value => <option key={value}>{value}</option>)}</select>
      <select className="select" value={filters.owner_id} onChange={e => setFilters({ ...filters, owner_id: e.target.value })}><option value="">All owners</option>{owners.map(owner => <option key={owner.id} value={owner.id}>{owner.name}</option>)}</select>
    </div></div>
    {loading ? <div className="campus-head-panel"><Empty text="Loading campus risks..." /></div> : <div className="campus-head-panel"><div className="campus-head-table-wrap"><table className="campus-head-table"><thead><tr><th>Risk / Issue</th><th>Category</th><th>Severity</th><th>Priority</th><th>Owner</th><th>Status</th><th>Due</th></tr></thead><tbody>{risks.map(risk => <tr key={risk.id} onClick={() => openRisk(risk)} className="risk-row"><td><strong>{risk.title}</strong><small>{risk.description}</small></td><td>{risk.category}</td><td>{risk.severity}</td><td>{risk.priority}</td><td>{risk.owner}</td><td><StatePill s={risk.status} /></td><td>{risk.due_at ? new Date(risk.due_at).toLocaleDateString('en-IN') : 'No due date'}{risk.overdue && <small className="risk-overdue">Overdue</small>}</td></tr>)}{!risks.length && <tr><td colSpan={7}><Empty text="No campus risks match these filters." /></td></tr>}</tbody></table></div></div>}
    {creating && <RiskForm form={form} setField={setField} owners={owners} editing={editing} onCancel={() => setCreating(false)} onSave={saveRisk} />}
    {selected && !creating && <RiskDetail risk={selected} owners={owners} onClose={() => setSelected(null)} onEdit={beginEdit} onAssign={assign} onAction={runRiskAction} action={action} setAction={setAction} addAction={addAction} actionUpdate={actionUpdate} />}
  </div>
}

function RiskForm({ form, setField, owners, editing, onCancel, onSave }: any) {
  return <div className="modal-bg"><div className="modal risk-modal"><div className="modal-h"><h3>{editing ? 'Edit Risk / Issue' : 'Create Risk / Issue'}</h3><button className="modal-x" onClick={onCancel}>×</button></div><div className="modal-b risk-form-grid"><label>Title<input className="inp" value={form.title} onChange={e => setField('title', e.target.value)} /></label><label>Category<select className="select" value={form.category} onChange={e => setField('category', e.target.value)}>{categories.map(value => <option key={value}>{value}</option>)}</select></label><label className="risk-form-wide">Description<textarea className="inp" rows={3} value={form.description} onChange={e => setField('description', e.target.value)} /></label><label>Severity<select className="select" value={form.severity} onChange={e => setField('severity', e.target.value)}>{severities.map(value => <option key={value}>{value}</option>)}</select></label><label>Likelihood<select className="select" value={form.likelihood} onChange={e => setField('likelihood', e.target.value)}>{levels.map(value => <option key={value}>{value}</option>)}</select></label><label>Impact<select className="select" value={form.impact} onChange={e => setField('impact', e.target.value)}>{levels.map(value => <option key={value}>{value}</option>)}</select></label><label>Priority<select className="select" value={form.priority} onChange={e => setField('priority', e.target.value)}>{severities.map(value => <option key={value}>{value}</option>)}</select></label><label>Owner<select className="select" value={form.owner_id} onChange={e => setField('owner_id', e.target.value)}><option value="">Unassigned</option>{owners.map(owner => <option key={owner.id} value={owner.id}>{owner.name} · {owner.role}</option>)}</select></label><label>Due date<input className="inp" type="datetime-local" value={form.due_at} onChange={e => setField('due_at', e.target.value)} /></label></div><div className="modal-f"><button className="btn btn-out" onClick={onCancel}>Cancel</button><button className="btn btn-crimson" onClick={onSave}>{editing ? 'Save changes' : 'Create risk'}</button></div></div></div>
}

function RiskDetail({ risk, owners, onClose, onEdit, onAssign, onAction, action, setAction, addAction, actionUpdate }: any) {
  return <div className="modal-bg"><div className="modal risk-modal"><div className="modal-h"><div><h3>{risk.title}</h3><p>{risk.category} · {risk.campus_scope_id}</p></div><button className="modal-x" onClick={onClose}>×</button></div><div className="modal-b risk-detail"><div className="risk-detail-grid"><div><label>Status</label><strong><StatePill s={risk.status} /></strong></div><div><label>Severity</label><strong>{risk.severity}</strong></div><div><label>Likelihood / Impact</label><strong>{risk.likelihood} / {risk.impact}</strong></div><div><label>Priority</label><strong>{risk.priority}</strong></div><div><label>Owner</label><select className="select" value={risk.owner_id || ''} onChange={e => onAssign(e.target.value)}><option value="">Unassigned</option>{owners.map((owner: any) => <option key={owner.id} value={owner.id}>{owner.name}</option>)}</select></div><div><label>Due date</label><strong>{risk.due_at ? new Date(risk.due_at).toLocaleString('en-IN') : 'No due date'}</strong></div></div><p className="risk-description">{risk.description || 'No description provided.'}</p><h4>Corrective actions</h4><div className="risk-actions">{(risk.actions || []).map((item: any) => <div className="risk-action" key={item.id}><div><strong>{item.description}</strong><small>{item.owner} · {item.status} · {item.progress}%{item.overdue ? ' · OVERDUE' : ''}</small></div>{item.status === 'OPEN' || item.status === 'IN_PROGRESS' ? <button className="btn btn-out" onClick={() => actionUpdate(item.id, 'complete')}>Complete</button> : item.status === 'COMPLETED' ? <button className="btn btn-out" onClick={() => actionUpdate(item.id, 'verify')}>Verify</button> : <span className="status-chip status-approved">Verified</span>}</div>)}{!(risk.actions || []).length && <p className="workflow-empty">No corrective actions recorded.</p>}</div><div className="risk-action-create"><input className="inp" placeholder="Corrective action" value={action.description} onChange={e => setAction({ ...action, description: e.target.value })} /><select className="select" value={action.owner_id} onChange={e => setAction({ ...action, owner_id: e.target.value })}><option value="">Action owner</option>{owners.map((owner: any) => <option key={owner.id} value={owner.id}>{owner.name}</option>)}</select><input className="inp" type="datetime-local" value={action.due_at} onChange={e => setAction({ ...action, due_at: e.target.value })} /><button className="btn btn-out" onClick={addAction}>Add action</button></div></div><div className="modal-f risk-modal-actions"><button className="btn btn-out" onClick={onEdit}>Edit</button>{risk.available_actions?.includes('resolve') && <button className="btn btn-crimson" onClick={() => onAction('resolve')}>Resolve</button>}{risk.available_actions?.includes('close') && <button className="btn btn-crimson" onClick={() => onAction('close')}>Close</button>}{risk.available_actions?.includes('escalate') && <button className="btn btn-out" onClick={() => onAction('escalate')}>Escalate</button>}</div></div></div>
}

function Empty({ text }: { text: string }) { return <div className="campus-head-empty-metric"><span>{text}</span></div> }
