import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'
import './HodReportsAudit.css'

export default function HodDepartmentAudit() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [type, setType] = useState('')
  const [search, setSearch] = useState('')
  const load = () => api.hodDepartmentAudit({ event_type: type, search, page: 1, page_size: 25 }).then(setData).catch((reason: any) => setError(reason.message || 'Department audit could not be loaded.'))
  useEffect(() => { void load() }, [type])
  if (error && !data) return <Empty icon="!" text={error} />
  if (!data) return <Spinner />
  const events = data.events || []
  const attendance = events.filter((event: any) => event.event_type === 'attendance').length
  const requests = events.filter((event: any) => String(event.event_type || '').includes('request')).length

  return <main className="hod-reports-page hod-audit-page fade-in">
    <header className="hod-courses-heading"><div><p>Read-only department activity</p><h1>Department Audit</h1><span>{data.department?.name || 'Department'} · scoped audit metadata only; sensitive narratives and payloads are not displayed.</span></div><button className="btn btn-out" onClick={load} type="button">Refresh</button></header>
    {error && <p className="hod-allocation-message error">{error}</p>}
    <section className="hod-audit-kpis" aria-label="Audit summary"><Stat value={data.pagination?.total ?? 0} label="Events in Result" /><Stat value={attendance} label="Attendance Events" /><Stat value={requests} label="Request Events" /></section>
    <section className="hod-audit-register">
      <header className="hod-audit-register-head"><div><p>Safe departmental audit trail</p><h2>Audit Register</h2></div><div className="hod-audit-filters"><label>Event Type<select value={type} onChange={event => setType(event.target.value)}><option value="">All event types</option>{(data.filters?.event_types || []).map((item: string) => <option key={item} value={item}>{title(item)}</option>)}</select></label><label>Search<input value={search} onChange={event => setSearch(event.target.value)} placeholder="Actor, action, reference" /></label><button className="btn btn-out" onClick={load} type="button">Search</button></div></header>
      <div className="hod-audit-table-wrap"><table className="hod-audit-table"><thead><tr><th>Timestamp</th><th>Actor</th><th>Office / Role</th><th>Event</th><th>Resource</th><th>Reference</th><th>Result</th></tr></thead><tbody>{events.map((event: any) => <tr key={event.id}><td className="hod-audit-time">{date(event.timestamp)}</td><td className="hod-audit-actor">{event.actor || '—'}</td><td>{event.actor_office || '—'}</td><td><b>{title(event.event_type)}</b><small>{event.action || 'Recorded'}</small></td><td>{event.resource || '—'}</td><td className="hod-audit-reference" title={event.reference_id || ''}>{event.reference_id || '—'}</td><td><span className={`hod-audit-result is-${String(event.result || 'recorded').replace(/[^a-z0-9]/gi, '-').toLowerCase()}`}>{event.result || 'Recorded'}</span></td></tr>)}{!events.length && <tr><td colSpan={7} className="hod-audit-empty">No department audit events match these filters.</td></tr>}</tbody></table></div>
    </section>
  </main>
}

function Stat({ value, label }: { value: any; label: string }) { return <article><b>{value}</b><span>{label}</span></article> }
function title(value: string) { return String(value || '—').replaceAll('_', ' ').replace(/\b\w/g, item => item.toUpperCase()) }
function date(value: string) { return value ? new Date(value).toLocaleString() : '—' }
