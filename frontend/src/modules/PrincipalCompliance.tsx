import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Modal, PageHead, Spinner } from './kit'

export default function PrincipalCompliance({ go }: any) {
  const emptyFilters = { q: '', category: '', status: '', priority: '' }
  const [data, setData] = useState<any>(null), [filters, setFilters] = useState<any>(emptyFilters), [selected, setSelected] = useState<any>(null), [error, setError] = useState(''), [loading, setLoading] = useState(false)
  const requestVersion = useRef(0)
  const load = async (nextFilters = filters, resetScroll = false) => {
    const version = ++requestVersion.current
    if (resetScroll) window.scrollTo({ top: 0, behavior: 'auto' })
    setError('')
    setLoading(true)
    setData((previous: any) => previous ? { ...previous, requirements: [] } : previous)
    try {
      const response = await api.complianceRequirements(nextFilters)
      if (version === requestVersion.current) setData(response)
    } catch (e: any) {
      if (version === requestVersion.current) setError(e.message || 'Unable to load accreditation and compliance data.')
    } finally {
      if (version === requestVersion.current) setLoading(false)
    }
  }
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' })
    void load(emptyFilters)
  }, [])
  const updateFilter = (key: string, value: string) => {
    const next = { ...filters, [key]: value }
    setFilters(next)
    void load(next, true)
  }
  const clear = () => {
    setFilters(emptyFilters)
    void load(emptyFilters, true)
  }
  if (!data && !error) return <Spinner />
  if (error) return <div className="empty-state"><h3>Unable to load accreditation and compliance data.</h3><p>{error}</p><button className="btn btn-crimson" onClick={load}>Retry</button></div>
  return <div className="fade-in principal-operations"><PageHead title="Accreditation & Compliance" sub="Operational compliance requirements for your authorized campus." />
    <div className="operations-filter principal-compliance-filter"><input className="inp" value={filters.q} onChange={e => setFilters({ ...filters, q: e.target.value })} onKeyDown={e => e.key === 'Enter' && void load(filters, true)} placeholder="Search requirement or reference"/><select className="select" value={filters.category} onChange={e => updateFilter('category', e.target.value)}><option value="">All categories</option>{(data.filters?.categories || []).map((x: string) => <option key={x}>{x}</option>)}</select><select className="select" value={filters.status} onChange={e => updateFilter('status', e.target.value)}><option value="">All statuses</option>{(data.filters?.statuses || []).map((x: string) => <option key={x}>{x}</option>)}</select><select className="select" value={filters.priority} onChange={e => updateFilter('priority', e.target.value)}><option value="">All priorities</option>{(data.filters?.priorities || []).map((x: string) => <option key={x}>{x}</option>)}</select><button className="btn btn-crimson" onClick={() => void load(filters, true)}>Filter</button><button className="btn btn-out" onClick={clear}>Clear</button></div>
    <section className="card"><div className="card-h"><h3>Compliance Requirements</h3><span className="hint">{data.requirements.length} in authorized campus{loading ? ' · Updating…' : ''}</span></div><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Requirement</th><th>Category</th><th>Responsible Department</th><th>Campus</th><th>Priority</th><th>Due Date</th><th>Status</th><th>Action</th></tr></thead><tbody>{data.requirements.length ? data.requirements.map((item: any) => <tr key={item.id}><td><b>{item.title}</b><small>{item.reference_code}</small></td><td>{item.category}</td><td>{item.responsible_department}</td><td>{item.campus}</td><td><span className="tag">{item.priority}</span></td><td>{item.due_date || 'Not configured'}</td><td><span className="tag">{item.status}</span></td><td><button className="btn btn-out" onClick={() => api.complianceRequirement(item.id).then(setSelected).catch((e: any) => setError(e.message || 'Unable to load compliance requirement.'))}>View</button></td></tr>) : <tr><td colSpan={8}><p className="principal-empty">No compliance requirements match these filters.</p></td></tr>}</tbody></table></div></section>
    {selected && <RequirementModal detail={selected.requirement} onClose={() => setSelected(null)} onRefresh={() => { api.complianceRequirement(selected.requirement.id).then(setSelected); load() }} go={go}/>}</div>
}

function RequirementModal({ detail, onClose, onRefresh, go }: any) {
  const [reason, setReason] = useState(''), [busy, setBusy] = useState(''), [error, setError] = useState('')
  const action = async (kind: string) => { if (kind === 'return' && !reason.trim()) { setError('Please provide a reason before returning this requirement.'); return }; setBusy(kind); setError(''); try { await api.decideWorkflow(detail.workflow_id, kind, reason); setReason(''); await onRefresh() } catch (e: any) { setError(e.message || `Unable to ${kind} this compliance requirement.`) } finally { setBusy('') } }
  const terminal = ['approved', 'executed', 'rejected'].includes(detail.status)
  return <Modal title="Compliance Requirement" className="principal-compliance-modal" onClose={onClose} footer={<><button className="btn btn-teal" disabled={!!busy || terminal} onClick={() => action('review')}>{busy === 'review' ? 'Reviewing...' : 'Review'}</button><button className="btn btn-rose" disabled={!!busy || terminal} onClick={() => action('return')}>{busy === 'return' ? 'Returning...' : 'Return'}</button><button className="btn btn-out" disabled={!!busy || terminal} onClick={() => action('escalate')}>{busy === 'escalate' ? 'Escalating...' : 'Escalate'}</button><button className="btn btn-brass" onClick={() => { sessionStorage.setItem('workflow-open', detail.workflow_id); go?.('workflows') }}>View Workflow</button></>}><div className="compliance-detail"><h3>{detail.title}</h3>{error && <div className="err-box">{error}</div>}<Info label="Reference" value={detail.reference_code}/><Info label="Category" value={detail.category}/><Info label="Responsible Department" value={detail.responsible_department}/><Info label="Campus" value={detail.campus}/><Info label="Priority" value={detail.priority}/><Info label="Due Date" value={detail.due_date || 'Not configured'}/><Info label="Current Status" value={detail.status}/><Info label="Evidence" value={detail.evidence_reference || 'Not available'}/><p>{detail.description}</p><h4>Decision History</h4>{detail.history.length ? detail.history.map((item: any) => <div className="snap" key={item.id}><span>{item.decision} · {item.stage}</span><b>{item.actor}</b><small>{item.reason || 'No remarks'} · {item.at}</small></div>) : <p className="principal-empty">No workflow decisions have been recorded.</p>}<label>Reason / Remarks<textarea className="inp" rows={4} value={reason} onChange={e => setReason(e.target.value)} placeholder="Required when returning; recorded in workflow history and audit."/></label></div></Modal>
}
function Info({ label, value }: any) { return <div className="snap"><span>{label}</span><b>{value}</b></div> }
