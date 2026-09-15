import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner } from '../modules/kit'
import HodMyRequests from './HodMyRequests'
import HodReviewInbox from './HodReviewInbox'
import './HodWorkflowCenter.css'

type Tab = 'submitted' | 'pending' | 'processed'

const processedLabels: Record<string, string> = {
  faculty_leave: 'Faculty Leave', attendance_correction: 'Attendance Correction', marks_submission: 'Marks Submission',
}
const title = (value?: string) => String(value || '—').replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase())
const when = (value?: string) => value ? new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '—'

export default function HodWorkflowCenter({ go }: { go: (view: string) => void }) {
  const [tab, setTab] = useState<Tab>('submitted')
  const [submitted, setSubmitted] = useState<any>(null)
  const [reviews, setReviews] = useState<any>(null)
  const [processed, setProcessed] = useState<any>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [refreshing, setRefreshing] = useState(false)

  const load = async () => {
    setRefreshing(true)
    const results = await Promise.allSettled([api.hodMyRequests(), api.hodReviews(), api.hodProcessedReviews()])
    const nextErrors: Record<string, string> = {}
    const [myRequests, pending, history] = results
    if (myRequests.status === 'fulfilled' && Array.isArray(myRequests.value?.requests)) setSubmitted(myRequests.value)
    else { setSubmitted(null); nextErrors.submitted = myRequests.status === 'rejected' ? myRequests.reason?.message || 'Submitted requests could not be loaded.' : 'Submitted requests returned an invalid response.' }
    if (pending.status === 'fulfilled' && Array.isArray(pending.value?.reviews)) setReviews(pending.value)
    else { setReviews(null); nextErrors.pending = pending.status === 'rejected' ? pending.reason?.message || 'Pending reviews could not be loaded.' : 'Pending reviews returned an invalid response.' }
    if (history.status === 'fulfilled' && Array.isArray(history.value?.processed)) setProcessed(history.value)
    else { setProcessed(null); nextErrors.processed = history.status === 'rejected' ? history.reason?.message || 'Processed history could not be loaded.' : 'Processed history returned an invalid response.' }
    setErrors(nextErrors); setRefreshing(false)
  }
  useEffect(() => { void load() }, [])

  const submittedCount = submitted?.requests?.length
  const pendingCount = reviews?.counts?.total_pending
  const approved = processed?.counts?.approved
  const returnedOrRejected = processed ? (processed.counts?.returned || 0) + (processed.counts?.rejected || 0) : undefined
  const department = submitted?.department || reviews?.department || processed?.department

  return <main className="hod-workflow-page fade-in">
    <header className="hod-workflow-head">
      <div><p>{department?.name || 'Department'}{department?.campus ? ` · ${department.campus}` : ''}</p><h1>Workflow Center</h1><span>Track requests you submitted and review workflows currently assigned to you.</span></div>
      <button className="btn btn-out" type="button" onClick={() => void load()} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh'}</button>
    </header>
    <section className="hod-workflow-summary" aria-label="Workflow center summary">
      <Summary label="My Submitted" value={submittedCount} hint="Initiator-owned requests" />
      <Summary label="Pending My Review" value={pendingCount} hint="Current reviewer assignments" tone="pending" />
      <Summary label="Approved By Me" value={approved} hint="Persisted HOD decisions" tone="approved" />
      <Summary label="Returned / Rejected" value={returnedOrRejected} hint="Persisted HOD decisions" tone="returned" />
    </section>
    <nav className="hod-workflow-tabs" aria-label="Workflow Center views">
      <button className={tab === 'submitted' ? 'active' : ''} type="button" onClick={() => setTab('submitted')}>My Submitted Requests</button>
      <button className={tab === 'pending' ? 'active' : ''} type="button" onClick={() => setTab('pending')}>Pending My Review</button>
      <button className={tab === 'processed' ? 'active' : ''} type="button" onClick={() => setTab('processed')}>Processed By Me</button>
    </nav>
    {tab === 'submitted' && (submitted ? <HodMyRequests go={go} snapshot={submitted} onRefresh={load} embedded /> : <SourceError message={errors.submitted} onRetry={load} />)}
    {tab === 'pending' && (reviews ? <HodReviewInbox snapshot={reviews} onRefresh={load} embedded /> : <SourceError message={errors.pending} onRetry={load} />)}
    {tab === 'processed' && (processed ? <ProcessedReviews data={processed} /> : <SourceError message={errors.processed} onRetry={load} />)}
  </main>
}

function Summary({ label, value, hint, tone = '' }: any) { return <article className={tone}><span>{label}</span><b>{typeof value === 'number' ? value : '—'}</b><small>{hint}</small></article> }
function SourceError({ message, onRetry }: { message?: string, onRetry: () => Promise<void> | void }) { return <section className="hod-workflow-source-error" role="alert"><b>Workflow data is unavailable.</b><span>{message || 'This workflow source could not be loaded.'}</span><button className="btn btn-out" type="button" onClick={() => void onRetry()}>Try again</button></section> }

function ProcessedReviews({ data }: { data: any }) {
  const [query, setQuery] = useState(''), [type, setType] = useState('all'), [detail, setDetail] = useState<any>(null)
  const rows = data.processed || []
  const types = useMemo(() => [...new Set(rows.map((row: any) => row.workflow_type))], [rows])
  const visible = rows.filter((row: any) => (type === 'all' || row.workflow_type === type) && `${row.subject || ''} ${row.requester || ''}`.toLowerCase().includes(query.toLowerCase()))
  return <section className="hod-workflow-processed">
    <section className="hod-workflow-register">
      <header><div><p>Approval-history ownership</p><h2>Processed By Me</h2></div><small>{visible.length} persisted decision{visible.length === 1 ? '' : 's'}</small></header>
      <div className="hod-workflow-filters"><label>Search safe subject<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Requester, subject, or reference" /></label><label>Workflow type<select value={type} onChange={event => setType(event.target.value)}><option value="all">All workflow types</option>{types.map((item: string) => <option key={item} value={item}>{processedLabels[item] || title(item)}</option>)}</select></label></div>
      <div className="hod-workflow-table-wrap"><table><thead><tr><th>Workflow Type</th><th>Requester</th><th>Subject</th><th>My Decision</th><th>Decision Date</th><th>Resulting Stage</th><th>Status</th><th /></tr></thead><tbody>
        {visible.map((row: any) => <tr key={row.id}><td><span className={`hod-workflow-kind ${row.workflow_type}`}>{processedLabels[row.workflow_type] || title(row.workflow_type)}</span></td><td>{row.requester || '—'}</td><td><strong>{row.subject || '—'}</strong></td><td><span className={`hod-workflow-decision ${row.decision}`}>{title(row.decision)}</span></td><td>{when(row.decision_at)}</td><td>{row.resulting_stage || '—'}</td><td><span className={`hod-workflow-status ${row.final ? 'final' : 'active'}`}>{row.final ? 'Final' : title(row.status || row.workflow_state)}</span></td><td><button className="hod-workflow-view" type="button" onClick={() => setDetail(row)}>View</button></td></tr>)}
        {!visible.length && <tr><td colSpan={8}><Empty icon="✓" text={rows.length ? 'No processed decisions match these filters.' : 'No persisted HOD decisions are available yet.'} /></td></tr>}
      </tbody></table></div>
    </section>
    {detail && <Modal title="Processed Decision" onClose={() => setDetail(null)} footer={<button className="btn btn-out" type="button" onClick={() => setDetail(null)}>Close</button>}><section className="hod-workflow-detail"><div><span>Workflow type</span><b>{processedLabels[detail.workflow_type] || title(detail.workflow_type)}</b></div><div><span>Requester</span><b>{detail.requester || '—'}</b></div><div><span>Subject</span><b>{detail.subject || '—'}</b></div><div><span>My decision</span><b>{title(detail.decision)}</b></div><div><span>Decision date</span><b>{when(detail.decision_at)}</b></div><div><span>Resulting stage</span><b>{detail.resulting_stage || '—'}</b></div></section>{detail.decision_reason && <section className="hod-workflow-reason"><h3>My decision comment</h3><p>{detail.decision_reason}</p></section>}<p className="hod-workflow-readonly">This is a read-only Approval history record. It cannot be acted on again from Workflow Center.</p></Modal>}
  </section>
}
