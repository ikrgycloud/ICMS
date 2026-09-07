import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { Empty, PageHead, Pill, Spinner } from './kit'

type Filter = 'ALL' | 'PENDING' | 'URGENT' | 'TODAY' | 'COMPLETED'

export default function DecisionInbox() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [type, setType] = useState('ALL')
  const [priority, setPriority] = useState('ALL')
  const [status, setStatus] = useState('ALL')
  const [department, setDepartment] = useState('ALL')
  const [sort, setSort] = useState('urgent')
  const [filter, setFilter] = useState<Filter>('PENDING')
  const [selected, setSelected] = useState<any>(null)
  const [decision, setDecision] = useState<'approve' | 'return' | 'reject' | ''>('')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const searchRef = useRef<HTMLInputElement>(null)

  async function load() {
    setRefreshing(true); setError('')
    try { setData(await api.governanceInbox()) } catch (e: any) { setError(e.message || 'Approvals could not be loaded.') } finally { setRefreshing(false) }
  }
  useEffect(() => { load() }, [])
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => { if (event.key === '/' && document.activeElement?.tagName !== 'INPUT') { event.preventDefault(); searchRef.current?.focus() } }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [])

  const rows = useMemo(() => {
    if (!data) return []
    const source = filter === 'COMPLETED' ? data.history || [] : data.proposals || []
    const needle = query.trim().toLowerCase(); const today = new Date().toISOString().slice(0, 10)
    const filtered = source.filter((item: any) => {
      const matchesSearch = !needle || [item.title, item.type, item.requester, item.department, item.payload?.title].some(value => String(value || '').toLowerCase().includes(needle))
      const matchesType = type === 'ALL' || String(item.type || '').toUpperCase() === type
      const matchesPriority = priority === 'ALL' || item.priority === priority
      const matchesStatus = status === 'ALL' || (status === 'PENDING' ? !['APPROVED', 'REJECTED', 'RETURNED'].includes(item.state) : item.state === status)
      const matchesDepartment = department === 'ALL' || item.department === department
      const matchesFilter = filter === 'ALL' || filter === 'PENDING' || filter === 'COMPLETED' || (filter === 'URGENT' && ['Critical', 'High'].includes(item.priority)) || (filter === 'TODAY' && item.due_at?.slice(0, 10) === today)
      return matchesSearch && matchesType && matchesPriority && matchesStatus && matchesDepartment && matchesFilter
    })
    return filtered.sort((a: any, b: any) => {
      if (sort === 'newest') return String(b.updated_at || b.due_at || '').localeCompare(String(a.updated_at || a.due_at || ''))
      if (sort === 'oldest') return String(a.updated_at || a.due_at || '').localeCompare(String(b.updated_at || b.due_at || ''))
      if (sort === 'due') return String(a.due_at || '9999').localeCompare(String(b.due_at || '9999'))
      const rank: Record<string, number> = { Critical: 4, High: 3, Medium: 2, Low: 1 }
      return (rank[b.priority] || 0) - (rank[a.priority] || 0) || Number(b.overdue) - Number(a.overdue)
    })
  }, [data, filter, query, type, priority, status, department, sort])

  const departments = [...new Set((data?.proposals || []).map((item: any) => item.department).filter(Boolean))]
  const decide = async () => {
    if (!selected || !decision) return
    if (decision !== 'approve' && !reason.trim()) { setError('A reason is required for this decision.'); return }
    setSaving(true); setError('')
    const target = decision === 'approve' ? 'APPROVED' : decision === 'return' ? 'RETURNED' : 'REJECTED'
    try {
      await api.governanceTransition(selected.id, { target_state: target, expected_status_version: selected.status_version, reason: reason.trim() || 'Approved by Dean Academics' })
      setSelected(null); setDecision(''); setReason(''); window.dispatchEvent(new Event('icms:approval-updated')); await load()
    } catch (e: any) { setError(e.message || 'Approval could not be completed.') } finally { setSaving(false) }
  }
  if (!data) return error ? <div className="card card-pad calendar-banner warn">{error} <button className="btn btn-sm btn-out" onClick={load} type="button">Retry</button></div> : <Spinner />
  const summary = data.summary || { pending: data.count || 0, urgent: 0, due_today: 0, completed_month: 0 }
  return <div className="fade-in approvals-page">
    <PageHead title="My Approvals" sub="Review pending academic decisions and track completed actions." right={<button className={`btn btn-out ${refreshing ? 'is-loading' : ''}`} onClick={load} disabled={refreshing}>{refreshing ? 'Refreshing...' : 'Refresh'}</button>} />
    {error && <div className="calendar-banner warn">{error}</div>}
    <div className="approval-summary-grid">
      <Summary label="Pending decisions" value={summary.pending} tone="blue" active={filter === 'PENDING'} onClick={() => setFilter('PENDING')} />
      <Summary label="Urgent approvals" value={summary.urgent} tone="red" active={filter === 'URGENT'} onClick={() => setFilter('URGENT')} />
      <Summary label="Due today" value={summary.due_today} tone="amber" active={filter === 'TODAY'} onClick={() => setFilter('TODAY')} />
      <Summary label="Completed this month" value={summary.completed_month} tone="green" active={filter === 'COMPLETED'} onClick={() => setFilter('COMPLETED')} />
    </div>
    <section className="approval-filter-panel">
      <label className="approval-search"><span>Search approvals</span><input ref={searchRef} value={query} onChange={event => setQuery(event.target.value)} placeholder="Title, requester, department" /><kbd>/</kbd></label>
      <select value={type} onChange={event => setType(event.target.value)} aria-label="Approval type"><option value="ALL">All types</option><option value="CURRICULUM">Curriculum</option><option value="ALLOCATION">Faculty Allocation</option><option value="CALENDAR">Academic Calendar</option><option value="PROGRAM">Programs</option></select>
      <select value={priority} onChange={event => setPriority(event.target.value)} aria-label="Priority"><option value="ALL">All priorities</option>{['Critical', 'High', 'Medium', 'Low'].map(value => <option key={value}>{value}</option>)}</select>
      <select value={status} onChange={event => setStatus(event.target.value)} aria-label="Status"><option value="ALL">All statuses</option><option value="PENDING">Pending</option><option value="UNDER_REVIEW">In Review</option><option value="APPROVED">Approved</option><option value="RETURNED">Returned</option><option value="REJECTED">Rejected</option></select>
      <select value={department} onChange={event => setDepartment(event.target.value)} aria-label="Department"><option value="ALL">All departments</option>{departments.map((value: any) => <option key={value}>{value}</option>)}</select>
      <select value={sort} onChange={event => setSort(event.target.value)} aria-label="Sort approvals"><option value="urgent">Most urgent</option><option value="due">Due date</option><option value="newest">Newest</option><option value="oldest">Oldest</option></select>
    </section>
    <section className="approval-queue card">
      <div className="card-h"><div><h3>Approval queue</h3><span className="hint">{rows.length} visible decision{rows.length === 1 ? '' : 's'}</span></div><span className="approval-live-dot">Live queue</span></div>
      <div className="approval-table-wrap"><table className="approval-table"><thead><tr><th>Type</th><th>Subject</th><th>Requester</th><th>Department</th><th>Due</th><th>Priority</th><th>Status</th><th>Action</th></tr></thead><tbody>{rows.map((item: any) => <tr className={item.overdue ? 'is-overdue' : ''} key={item.id}><td><span className="approval-type">{String(item.type || '').replace('_', ' ')}</span></td><td><b>{item.title}</b><small>{item.payload?.rationale || item.payload?.description || 'Governed academic request'}</small></td><td>{item.requester || item.submitted_by || 'Unknown'}</td><td>{item.department || 'Institution scope'}</td><td>{item.due_at ? new Date(item.due_at).toLocaleDateString() : 'Not set'}{item.overdue && <small className="overdue-text">Overdue</small>}</td><td><span className={`approval-priority ${String(item.priority || 'Low').toLowerCase()}`}>{item.priority || 'Low'}</span></td><td><Pill s={item.status_label || item.state} /></td><td><button className="btn btn-sm btn-out" onClick={() => setSelected(item)} type="button">Review</button></td></tr>)}</tbody></table></div>
      {!rows.length && <div className="approval-empty"><strong>{filter === 'COMPLETED' ? 'No completed decisions yet' : 'All caught up'}</strong><span>{data.proposals.length ? 'No approvals match the current filters.' : 'There are no pending approvals in your scope.'}</span></div>}
    </section>
    {selected && <div className="approval-drawer-backdrop" onMouseDown={event => event.target === event.currentTarget && setSelected(null)}><aside className="approval-drawer" role="dialog" aria-modal="true" aria-label="Approval details"><div className="approval-drawer-head"><div><span className="approval-kicker">{selected.type}</span><h2>{selected.title}</h2></div><button className="approval-close" onClick={() => setSelected(null)} type="button" aria-label="Close approval details">×</button></div><div className="approval-detail-grid"><div><span>Status</span><b>{selected.status_label || selected.state}</b></div><div><span>Priority</span><b>{selected.priority || 'Low'}</b></div><div><span>Requester</span><b>{selected.requester || selected.submitted_by || 'Unknown'}</b></div><div><span>Department</span><b>{selected.department || 'Institution scope'}</b></div><div><span>Due date</span><b>{selected.due_at ? new Date(selected.due_at).toLocaleDateString() : 'Not set'}</b></div></div><section className="approval-detail-section"><h3>Request summary</h3><p>{selected.payload?.rationale || selected.payload?.description || 'No additional request summary was provided.'}</p></section><section className="approval-detail-section"><h3>Audit history</h3>{selected.events?.length ? selected.events.map((event: any, index: number) => <div className="approval-history-row" key={`${event.at}-${index}`}><b>{event.to_state}</b><span>{event.at ? new Date(event.at).toLocaleString() : 'Unknown time'} · {event.actor_id || 'System'}</span>{event.reason && <small>{event.reason}</small>}</div>) : <p>No audit history available.</p>}</section><div className="approval-drawer-actions">{decision ? <div className="approval-reason"><label>{decision === 'return' ? 'Reason for returning' : 'Reason for rejection'}<textarea value={reason} onChange={event => setReason(event.target.value)} placeholder="Required for this decision" /></label><button className="btn btn-out" onClick={() => { setDecision(''); setReason('') }} type="button">Cancel</button><button className="btn btn-crimson" disabled={saving} onClick={decide} type="button">{saving ? 'Saving...' : `Confirm ${decision}`}</button></div> : <><button className="btn btn-out" onClick={() => setDecision('return')} type="button">Return for revision</button><button className="btn btn-out" onClick={() => setDecision('reject')} type="button">Reject</button><button className="btn btn-crimson" onClick={() => setDecision('approve')} type="button">Approve</button></>}</div></aside></div>}
  </div>
}

function Summary({ label, value, tone, active, onClick }: { label: string; value: number; tone: string; active: boolean; onClick: () => void }) { return <button className={`approval-summary ${tone} ${active ? 'active' : ''}`} onClick={onClick} type="button"><span>{label}</span><b>{value}</b><small>View queue</small></button> }
