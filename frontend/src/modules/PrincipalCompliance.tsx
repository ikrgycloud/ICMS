import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Modal, PageHead, Spinner } from './kit'

type Filters = { q: string; category: string; status: string; priority: string }

const emptyFilters: Filters = { q: '', category: '', status: '', priority: '' }

export default function PrincipalCompliance({ go }: any) {
  const [data, setData] = useState<any>(null)
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const [selected, setSelected] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const requestVersion = useRef(0)

  const load = async (nextFilters = filters, resetScroll = false) => {
    const version = ++requestVersion.current
    if (resetScroll) window.scrollTo({ top: 0, behavior: 'auto' })
    setError('')
    setLoading(true)
    setData(previous => previous ? { ...previous, requirements: [] } : previous)
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

  const updateFilter = (key: keyof Filters, value: string) => {
    const next = { ...filters, [key]: value }
    setFilters(next)
    void load(next, true)
  }

  const openRequirement = async (item: any) => {
    setError('')
    try {
      const response = await api.complianceRequirement(item.id)
      setSelected(response?.requirement ? response : { requirement: response || item })
    } catch (e: any) {
      setError(e.message || 'Unable to load compliance requirement.')
    }
  }

  if (!data && !error) return <Spinner />
  if (error && !data) return <div className="empty-state"><h3>Unable to load accreditation and compliance data.</h3><p>{error}</p><button className="btn btn-crimson" onClick={() => void load()}>Retry</button></div>

  const requirements = data?.requirements || []
  return <div className="fade-in principal-operations">
    <PageHead title="Accreditation & Compliance" sub="Operational compliance requirements for your authorized campus." />
    {error && <div className="workflow-error">{error}<button className="btn btn-out" onClick={() => setError('')}>Dismiss</button></div>}
    <div className="operations-filter principal-compliance-filter">
      <input className="inp" value={filters.q} onChange={event => setFilters({ ...filters, q: event.target.value })} onKeyDown={event => event.key === 'Enter' && void load(filters, true)} placeholder="Search requirement or reference" />
      <select className="select" value={filters.category} onChange={event => updateFilter('category', event.target.value)}><option value="">All categories</option>{(data.filters?.categories || []).map((value: string) => <option key={value}>{value}</option>)}</select>
      <select className="select" value={filters.status} onChange={event => updateFilter('status', event.target.value)}><option value="">All statuses</option>{(data.filters?.statuses || []).map((value: string) => <option key={value}>{value}</option>)}</select>
      <select className="select" value={filters.priority} onChange={event => updateFilter('priority', event.target.value)}><option value="">All priorities</option>{(data.filters?.priorities || []).map((value: string) => <option key={value}>{value}</option>)}</select>
      <button className="btn btn-crimson" onClick={() => void load(filters, true)}>Filter</button>
      <button className="btn btn-out" onClick={() => { setFilters(emptyFilters); void load(emptyFilters, true) }}>Clear</button>
    </div>
    <section className="card">
      <div className="card-h"><h3>Compliance Requirements</h3><span className="hint">{requirements.length} in authorized campus{loading ? ' · Updating...' : ''}</span></div>
      <div className="tbl-scroll">
        <table className="tbl">
          <thead><tr><th>Requirement</th><th>Category</th><th>Responsible Department</th><th>Campus</th><th>Priority</th><th>Due Date</th><th>Status</th><th>Action</th></tr></thead>
          <tbody>{requirements.length ? requirements.map((item: any) => <tr key={item.id}>
            <td><b>{item.title}</b><small>{item.reference_code}</small></td>
            <td>{item.category}</td><td>{item.responsible_department || item.responsible_dep}</td><td>{item.campus}</td>
            <td><span className="tag">{item.priority}</span></td><td>{item.due_date || 'Not configured'}</td><td><span className="tag">{item.status}</span></td>
            <td><button className="btn btn-out" onClick={() => void openRequirement(item)}>View</button></td>
          </tr>) : <tr><td colSpan={8}><p className="principal-empty">No compliance requirements match these filters.</p></td></tr>}</tbody>
        </table>
      </div>
    </section>
    {selected && <RequirementModal detail={selected.requirement || selected} onClose={() => setSelected(null)} onRefresh={async () => { await openRequirement(selected.requirement || selected); await load(filters) }} go={go} />}
  </div>
}

function RequirementModal({ detail, onClose, onRefresh, go }: any) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const actions: string[] = Array.isArray(detail?.available_actions) ? detail.available_actions : []

  const action = async (kind: string) => {
    if ((kind === 'return' || kind === 'escalate') && !reason.trim()) {
      setError(`Please provide a reason before ${kind}ing this requirement.`)
      return
    }
    if (!detail?.workflow_id) return
    setBusy(kind); setError('')
    try {
      await api.decideWorkflow(detail.workflow_id, kind, reason)
      setReason('')
      await onRefresh()
    } catch (e: any) {
      setError(e.message || `Unable to ${kind} this compliance requirement.`)
    } finally {
      setBusy('')
    }
  }

  const terminal = ['approved', 'executed', 'rejected'].includes(detail?.state)
  return <Modal title="Compliance Requirement" onClose={onClose} className="principal-compliance-modal" footer={<>
    {error && <span className="workflow-error">{error}</span>}
    {!terminal && actions.includes('review') && <button className="btn btn-out" disabled={!!busy} onClick={() => void action('review')}>{busy === 'review' ? 'Reviewing...' : 'Review'}</button>}
    {!terminal && actions.includes('approve') && <button className="btn btn-teal" disabled={!!busy} onClick={() => void action('approve')}>{busy === 'approve' ? 'Approving...' : 'Approve'}</button>}
    {!terminal && actions.includes('reject') && <button className="btn btn-rose" disabled={!!busy} onClick={() => void action('reject')}>{busy === 'reject' ? 'Rejecting...' : 'Reject'}</button>}
    {!terminal && actions.includes('return') && <button className="btn btn-out" disabled={!!busy} onClick={() => void action('return')}>{busy === 'return' ? 'Returning...' : 'Return'}</button>}
    {!terminal && actions.includes('escalate') && <button className="btn btn-crimson" disabled={!!busy} onClick={() => void action('escalate')}>{busy === 'escalate' ? 'Escalating...' : 'Escalate'}</button>}
    {go && detail?.workflow_id && <button className="btn btn-out" onClick={() => { onClose(); go('approvals') }}>Open workflow</button>}
    <button className="btn btn-out" onClick={onClose}>Close</button>
  </>}>
    <div className="compliance-detail">
      <h3>{detail?.title || 'Compliance requirement'}</h3>
      <div className="compliance-detail-grid">
        <Info label="Reference" value={detail?.reference_code} /><Info label="Category" value={detail?.category} />
        <Info label="Responsible Department" value={detail?.responsible_department || detail?.responsible_dep} /><Info label="Campus" value={detail?.campus} />
        <Info label="Priority" value={detail?.priority} /><Info label="Due Date" value={detail?.due_date || 'Not configured'} />
        <Info label="Current Status" value={detail?.status || detail?.state} /><Info label="Evidence" value={detail?.evidence_reference || 'Not available'} />
      </div>
      <section className="compliance-detail-section"><h4>Description</h4><p>{detail?.description || detail?.detail || 'No description recorded.'}</p></section>
      {detail?.workflow_id ? <>
        <section className="compliance-detail-section"><h4>Workflow</h4><p className="mono">{detail.workflow_id} · {detail.state || 'Pending review'}</p></section>
        <label className="workflow-field workflow-reason">Reason / remarks<textarea className="inp" value={reason} onChange={event => setReason(event.target.value)} rows={3} placeholder="Optional note recorded in the audit trail" /></label>
      </> : <p className="principal-empty">Read-only oversight. This requirement is not linked to a decision workflow.</p>}
    </div>
  </Modal>
}

function Info({ label, value }: { label: string; value?: any }) {
  return <div className="snap"><span>{label}</span><b>{value || 'Not configured'}</b></div>
}
