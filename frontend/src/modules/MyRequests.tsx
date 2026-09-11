import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, PageHead, Pill, Spinner } from './kit'

type Filter = 'ALL' | 'DRAFT' | 'IN_REVIEW' | 'RETURNED' | 'COMPLETED'

export default function MyRequests({ go }: { go?: (view: string) => void }) {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [type, setType] = useState('ALL')
  const [status, setStatus] = useState<Filter>('ALL')
  const [sort, setSort] = useState('updated')
  const [selected, setSelected] = useState<any>(null)
  const [saving, setSaving] = useState(false)

  async function load() {
    setError('')
    try { setData(await api.myRequests()) } catch (e: any) { setError(e.message || 'Requests could not be loaded.') }
  }
  useEffect(() => { load() }, [])

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const result = (data?.requests || []).filter((item: any) => {
      const matchesQuery = !needle || [item.title, item.type, item.department, item.id].some(value => String(value || '').toLowerCase().includes(needle))
      const matchesType = type === 'ALL' || item.type === type.toLowerCase()
      const matchesStatus = status === 'ALL' || (status === 'DRAFT' ? item.state === 'DRAFT' : status === 'IN_REVIEW' ? ['SUBMITTED', 'RESUBMITTED', 'UNDER_REVIEW', 'ESCALATED'].includes(item.state) : status === 'RETURNED' ? ['RETURNED', 'CLARIFICATION_REQUIRED'].includes(item.state) : ['APPROVED', 'IMPLEMENTED', 'CLOSED', 'REJECTED'].includes(item.state))
      return matchesQuery && matchesType && matchesStatus
    })
    return result.sort((a: any, b: any) => sort === 'newest' ? String(b.created_at || '').localeCompare(String(a.created_at || '')) : sort === 'oldest' ? String(a.created_at || '').localeCompare(String(b.created_at || '')) : String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
  }, [data, query, type, status, sort])

  async function submit(item: any) {
    setSaving(true); setError('')
    try { await api.transitionMyRequest(item.id, { target_state: item.state === 'RETURNED' || item.state === 'CLARIFICATION_REQUIRED' ? 'RESUBMITTED' : 'SUBMITTED', expected_status_version: item.status_version, reason: item.state === 'DRAFT' ? 'Request submitted' : 'Request resubmitted' }); await setSelected(null); await load() } catch (e: any) { setError(e.message || 'Unable to update this request.') } finally { setSaving(false) }
  }

  if (!data) return error ? <div className="card card-pad calendar-banner warn">{error} <button className="btn btn-sm btn-out" onClick={load} type="button">Retry</button></div> : <Spinner />
  const summary = data.summary || {}
  return <div className="fade-in my-requests-page">
    <PageHead title="My Requests" sub="Track requests you submitted and monitor their progress." right={<button className="btn btn-out" onClick={load} type="button">Refresh</button>} />
    {error && <div className="calendar-banner warn">{error}</div>}
    <div className="my-request-summary">
      <Summary label="All requests" value={summary.all || 0} active={status === 'ALL'} onClick={() => setStatus('ALL')} />
      <Summary label="Drafts" value={summary.drafts || 0} active={status === 'DRAFT'} onClick={() => setStatus('DRAFT')} />
      <Summary label="In review" value={summary.in_review || 0} active={status === 'IN_REVIEW'} onClick={() => setStatus('IN_REVIEW')} />
      <Summary label="Needs revision" value={summary.needs_revision || 0} active={status === 'RETURNED'} onClick={() => setStatus('RETURNED')} />
      <Summary label="Completed" value={summary.completed || 0} active={status === 'COMPLETED'} onClick={() => setStatus('COMPLETED')} />
    </div>
    <section className="my-request-filters">
      <label><span>Search requests</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Title, request ID, department" /></label>
      <select value={type} onChange={event => setType(event.target.value)} aria-label="Request type"><option value="ALL">All request types</option><option value="curriculum">Curriculum</option><option value="allocation">Faculty allocation</option><option value="calendar">Academic calendar</option><option value="program">Program</option></select>
      <select value={sort} onChange={event => setSort(event.target.value)} aria-label="Sort requests"><option value="updated">Recently updated</option><option value="newest">Newest</option><option value="oldest">Oldest</option></select>
      <button className="btn btn-crimson" onClick={() => go?.('curriculum')} type="button">+ New Request</button>
    </section>
    <section className="my-request-queue card">
      <div className="card-h"><div><h3>Request history</h3><span className="hint">{rows.length} visible request{rows.length === 1 ? '' : 's'}</span></div></div>
      <div className="my-request-table-wrap"><table className="my-request-table"><thead><tr><th>Type</th><th>Request</th><th>Scope / Department</th><th>Submitted</th><th>Last updated</th><th>Status</th><th>Next action</th><th /></tr></thead><tbody>{rows.map((item: any) => <tr key={item.id}><td>{String(item.type || '').replace('_', ' ')}</td><td><b>{item.title}</b><small>{item.id}</small></td><td>{item.department}</td><td>{formatDate(item.submitted_at)}</td><td>{formatDate(item.updated_at)}</td><td><Pill s={item.state} /></td><td><span className="my-request-next">{nextAction(item.state)}</span></td><td><button className="btn btn-sm btn-out" onClick={() => setSelected(item)} type="button">View</button></td></tr>)}</tbody></table></div>
      {!rows.length && <div className="my-request-empty"><strong>{data.requests.length ? 'No requests match your filters' : 'No requests yet'}</strong><span>{data.requests.length ? 'Clear filters or try another search.' : "You haven't submitted any academic requests."}</span>{!data.requests.length && <button className="btn btn-crimson" onClick={() => go?.('curriculum')} type="button">+ New Request</button>}</div>}
    </section>
    {selected && <div className="my-request-backdrop" onMouseDown={event => event.target === event.currentTarget && setSelected(null)}><aside className="my-request-drawer" role="dialog" aria-modal="true" aria-label="Request details"><header><div><span className="my-request-kicker">{selected.type}</span><h2>{selected.title}</h2></div><button onClick={() => setSelected(null)} type="button" aria-label="Close request details">×</button></header><div className="my-request-meta"><div><span>Status</span><b>{selected.state}</b></div><div><span>Department</span><b>{selected.department}</b></div><div><span>Submitted</span><b>{formatDate(selected.submitted_at)}</b></div><div><span>Updated</span><b>{formatDate(selected.updated_at)}</b></div></div><section><h3>Request summary</h3><p>{selected.payload?.rationale || selected.payload?.description || 'No additional request summary provided.'}</p></section><section><h3>Workflow timeline</h3>{selected.events?.length ? selected.events.map((event: any, index: number) => <div className="my-request-event" key={`${event.at}-${index}`}><b>{event.to_state}</b><span>{formatDateTime(event.at)} · {event.actor_id}</span>{event.reason && <small>{event.reason}</small>}</div>) : <p>No workflow events recorded.</p>}</section><footer>{(selected.state === 'DRAFT' || selected.state === 'RETURNED' || selected.state === 'CLARIFICATION_REQUIRED') && <button className="btn btn-crimson" disabled={saving} onClick={() => submit(selected)} type="button">{saving ? 'Saving...' : selected.state === 'DRAFT' ? 'Submit request' : 'Revise & Resubmit'}</button>}{selected.state === 'DRAFT' && <button className="btn btn-out" onClick={() => go?.('curriculum')} type="button">Edit in Curriculum</button>}<button className="btn btn-out" onClick={() => setSelected(null)} type="button">Close</button></footer></aside></div>}
  </div>
}

function Summary({ label, value, active, onClick }: { label: string; value: number; active: boolean; onClick: () => void }) { return <button className={`my-request-summary-card ${active ? 'active' : ''}`} onClick={onClick} type="button"><span>{label}</span><b>{value}</b><small>View requests</small></button> }
function formatDate(value: string | null | undefined) { return value ? new Date(value).toLocaleDateString() : '—' }
function formatDateTime(value: string | null | undefined) { return value ? new Date(value).toLocaleString() : 'Unknown time' }
function nextAction(state: string) { if (state === 'DRAFT') return 'Edit / Submit'; if (['RETURNED', 'CLARIFICATION_REQUIRED'].includes(state)) return 'Revise & Resubmit'; if (['APPROVED', 'IMPLEMENTED'].includes(state)) return 'View implementation'; if (state === 'REJECTED') return 'View reason'; return 'Awaiting reviewer' }
