import { useEffect, useState } from 'react'
import { api } from '../api'
import { StatePill } from '../views/ui'

const priorities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

export default function CampusEscalations() {
  const [rows, setRows] = useState<any[]>([]), [risks, setRisks] = useState<any[]>([]), [filters, setFilters] = useState({ status: '', priority: '', source_type: '' })
  const [creating, setCreating] = useState(false), [form, setForm] = useState({ source_ref: '', reason: '', priority: 'HIGH', due_at: '' })
  const [selected, setSelected] = useState<any>(null), [reason, setReason] = useState(''), [error, setError] = useState(''), [message, setMessage] = useState('')

  async function load() {
    try { const [escalations, riskResponse] = await Promise.all([api.escalations(filters), api.risks()]); setRows(escalations.escalations || []); setRisks(riskResponse.risks || []) }
    catch (err: any) { setError(err?.message || 'Unable to load campus escalations.') }
  }
  useEffect(() => { void load() }, [filters.status, filters.priority, filters.source_type])
  function dateValue(value: string) { return value ? new Date(value).toISOString() : null }
  async function create() {
    try { const response = await api.createEscalation({ ...form, due_at: dateValue(form.due_at), source_type: 'risk' }); setCreating(false); setSelected(response.escalation); setMessage('Escalation draft created.'); await load() }
    catch (err: any) { setError(err?.message || 'Unable to create escalation.') }
  }
  async function change(name: string) {
    if (!selected) return
    try {
      const methods: any = { submit: api.submitEscalation, follow_up: api.followUpEscalation, resolve: api.resolveEscalation, close: api.closeEscalation }
      const response = await methods[name](selected.id, reason); setSelected(response.escalation); setReason(''); setMessage(`Escalation ${name.replace('_', ' ')} completed.`); await load()
    } catch (err: any) { setError(err?.message || `Unable to ${name} escalation.`) }
  }
  return <div className="fade-in campus-head-page">
    <div className="page-head"><div><h1>Escalations</h1><p>Campus-scoped matters routed by authority policy.</p></div><button className="btn btn-crimson" onClick={() => setCreating(true)}>Create escalation</button></div>
    {error && <div className="err-box">{error}</div>}{message && <div className="success-box">{message}</div>}
    <div className="campus-head-panel"><div className="risk-filters"><select className="select" value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}><option value="">All statuses</option>{['DRAFT', 'SUBMITTED', 'RECEIVED', 'FOLLOW_UP', 'RESOLVED', 'CLOSED'].map(value => <option key={value}>{value}</option>)}</select><select className="select" value={filters.priority} onChange={e => setFilters({ ...filters, priority: e.target.value })}><option value="">All priorities</option>{priorities.map(value => <option key={value}>{value}</option>)}</select><select className="select" value={filters.source_type} onChange={e => setFilters({ ...filters, source_type: e.target.value })}><option value="">All sources</option><option value="risk">Risk</option></select></div></div>
    <div className="campus-head-panel"><div className="campus-head-table-wrap"><table className="campus-head-table"><thead><tr><th>Escalation</th><th>Source</th><th>Priority</th><th>Destination</th><th>Status</th><th>Due</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} className="risk-row" onClick={() => setSelected(row)}><td><strong>{row.reason || 'Campus escalation'}</strong><small>{row.id}</small></td><td>{row.source_type} · {row.source_ref}</td><td>{row.priority}</td><td>{row.destination}</td><td><StatePill s={row.status} /></td><td>{row.due_at ? new Date(row.due_at).toLocaleDateString('en-IN') : 'No due date'}{row.overdue && <small className="risk-overdue">Overdue</small>}</td></tr>)}{!rows.length && <tr><td colSpan={6}><div className="campus-head-empty-metric"><span>No campus escalations available.</span></div></td></tr>}</tbody></table></div></div>
    {creating && <div className="modal-bg"><div className="modal risk-modal"><div className="modal-h"><h3>Create escalation</h3><button className="modal-x" onClick={() => setCreating(false)}>×</button></div><div className="modal-b risk-form-grid"><label>Related risk<select className="select" value={form.source_ref} onChange={e => setForm({ ...form, source_ref: e.target.value })}><option value="">Select risk</option>{risks.map(risk => <option key={risk.id} value={risk.id}>{risk.title} · {risk.severity}</option>)}</select></label><label>Priority<select className="select" value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })}>{priorities.map(value => <option key={value}>{value}</option>)}</select></label><label>Due date<input className="inp" type="datetime-local" value={form.due_at} onChange={e => setForm({ ...form, due_at: e.target.value })} /></label><label className="risk-form-wide">Reason<textarea className="inp" rows={4} value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} /></label></div><div className="modal-f"><button className="btn btn-out" onClick={() => setCreating(false)}>Cancel</button><button className="btn btn-crimson" onClick={create}>Create draft</button></div></div></div>}
    {selected && <div className="modal-bg"><div className="modal risk-modal"><div className="modal-h"><div><h3>Escalation detail</h3><p>{selected.destination} · {selected.priority}</p></div><button className="modal-x" onClick={() => setSelected(null)}>×</button></div><div className="modal-b risk-detail"><div className="risk-detail-grid"><div><label>Status</label><strong><StatePill s={selected.status} /></strong></div><div><label>Source</label><strong>{selected.source_type} · {selected.source_ref}</strong></div><div><label>Destination</label><strong>{selected.destination}</strong></div></div><p className="risk-description">{selected.reason}</p><textarea className="inp" rows={3} placeholder="Reason / follow-up note" value={reason} onChange={e => setReason(e.target.value)} /></div><div className="modal-f risk-modal-actions">{selected.status === 'DRAFT' && <button className="btn btn-crimson" onClick={() => change('submit')}>Submit</button>}{['SUBMITTED', 'RECEIVED'].includes(selected.status) && <button className="btn btn-out" onClick={() => change('follow_up')}>Follow up</button>}{!['RESOLVED', 'CLOSED'].includes(selected.status) && <button className="btn btn-crimson" onClick={() => change('resolve')}>Resolve</button>}</div></div></div>}
  </div>
}
