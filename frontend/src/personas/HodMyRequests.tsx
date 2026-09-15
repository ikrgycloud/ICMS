import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner } from '../modules/kit'

const label = (value?: string) => String(value || '—').replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase())
const date = (value?: string) => value ? new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value)) : '—'
const active = new Set(['submitted', 'under_review'])
const routes: Record<string, string> = { curriculum: 'hod_curriculum_requests', resource: 'hod_resource_requests', staffing: 'hod_staffing_requests', welfare: 'hod_student_welfare', hod_leave: 'hod_leave' }
const typeLabels: Record<string, string> = { curriculum: 'Curriculum', resource: 'Department Resources', staffing: 'Staffing', welfare: 'Welfare', hod_leave: 'HOD Leave' }

export default function HodMyRequests({ go, snapshot, onRefresh, embedded = false }: { go: (view: string) => void, snapshot?: any, onRefresh?: () => Promise<void> | void, embedded?: boolean }) {
  const [data, setData] = useState<any>(null); const [error, setError] = useState(''); const [refreshing, setRefreshing] = useState(false)
  const [search, setSearch] = useState(''); const [kind, setKind] = useState('all'); const [status, setStatus] = useState('all'); const [stage, setStage] = useState('all')
  const [detail, setDetail] = useState<any>(null); const [detailError, setDetailError] = useState('')
  const load = async () => {
    setRefreshing(true); setError('')
    try {
      if (onRefresh) { await onRefresh(); return }
      const response = await api.hodMyRequests()
      if (!response || !Array.isArray(response.requests)) throw new Error('The My Requests response is not in the expected requester-tracking format.')
      setData(response)
      setSearch(''); setKind('all'); setStatus('all'); setStage('all')
    } catch (caught: any) { setData(null); setError(caught.message || 'Your submitted requests could not be loaded.') }
    finally { setRefreshing(false) }
  }
  useEffect(() => { if (!snapshot) void load() }, [])
  useEffect(() => { if (snapshot) setData(snapshot) }, [snapshot])
  // `load` validates the contract before committing data. This keeps the
  // initial loading render safe without treating a malformed response as empty.
  const rows = data?.requests ?? []
  const kinds = useMemo(() => [...new Set(rows.map((row: any) => row.kind))], [rows])
  const statuses = useMemo(() => [...new Set(rows.map((row: any) => row.status).filter(Boolean))], [rows])
  const stages = useMemo(() => [...new Set(rows.map((row: any) => row.stage_label).filter(Boolean))], [rows])
  const visible = rows.filter((row: any) => (kind === 'all' || row.kind === kind) && (status === 'all' || row.status === status) && (stage === 'all' || row.stage_label === stage) && (!search.trim() || `${row.subject || ''} ${row.subject_meta || ''}`.toLowerCase().includes(search.trim().toLowerCase())))
  const counts = { total: rows.length, awaiting: rows.filter((row: any) => active.has(row.status)).length, approved: rows.filter((row: any) => row.status === 'approved').length, rejected: rows.filter((row: any) => row.status === 'rejected').length }
  const openDetail = async (row: any) => { setDetailError(''); setDetail({ loading: true, row }); try { const response = await requestDetail(row); setDetail({ row, payload: response }) } catch (caught: any) { setDetail(null); setDetailError(caught.message || 'Request details could not be loaded.') } }
  if (!data) return <section className={`hod-myrequests-page${embedded ? ' embedded' : ''}`}>{error ? <Empty icon="!" text={error} /> : <Spinner />}</section>
  return <section className={`hod-myrequests-page fade-in${embedded ? ' embedded' : ''}`}>
    <header className="hod-myrequests-head"><div><p>{data?.hod_name || 'Head of Department'}{data?.department?.name ? ` · ${data.department.name}` : ''}{data?.department?.campus ? ` · ${data.department.campus}` : ''}</p><h1>My Requests</h1><span>Track requests you submitted. Reviewer work is available separately in My Reviews.</span></div><button className="btn btn-out" type="button" onClick={() => void load()} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh'}</button></header>
    {error && <section className="hod-myrequests-error" role="alert"><b>Unable to load My Requests.</b><span>{error}</span><button className="btn btn-out" type="button" onClick={() => void load()}>Try again</button></section>}
    {data && <>
      <section className="hod-myrequests-kpis"><Metric label="Total Requests" value={counts.total} hint="Submitted by you" /><Metric label="Awaiting Review" value={counts.awaiting} hint="Active request states" tone="pending" /><Metric label="Approved" value={counts.approved} hint="Final request state" tone="approved" /><Metric label="Rejected" value={counts.rejected} hint="Final request state" tone="rejected" /></section>
      <section className="hod-myrequests-types" aria-label="Request type summary">{kinds.map((item: string) => { const typeRows = rows.filter((row: any) => row.kind === item); return <button key={item} type="button" onClick={() => setKind(item)}><span>{typeLabels[item] || label(item)}</span><b>{typeRows.length}</b><small>{typeRows.filter((row: any) => active.has(row.status)).length} awaiting review</small></button> })}</section>
      <section className="hod-myrequests-register"><header><div><p>Requester-owned register</p><h2>Submitted Requests</h2></div><small>{visible.length} of {rows.length} requests</small></header><div className="hod-myrequests-filters"><label>Search safe subject<input value={search} onChange={event => setSearch(event.target.value)} placeholder="Course, resource, role, student or roll" /></label><label>Request type<select value={kind} onChange={event => setKind(event.target.value)}><option value="all">All request types</option>{kinds.map((item: string) => <option key={item} value={item}>{typeLabels[item] || label(item)}</option>)}</select></label><label>Status<select value={status} onChange={event => setStatus(event.target.value)}><option value="all">All statuses</option>{statuses.map((item: string) => <option key={item} value={item}>{label(item)}</option>)}</select></label><label>Current stage<select value={stage} onChange={event => setStage(event.target.value)}><option value="all">All stages</option>{stages.map((item: string) => <option key={item} value={item}>{item}</option>)}</select></label><button className="hod-myrequests-clear" type="button" onClick={() => { setSearch(''); setKind('all'); setStatus('all'); setStage('all') }}>Clear</button></div>
        <div className="hod-myrequests-table-wrap"><table><thead><tr><th>Request Type</th><th>Subject</th><th>Submitted</th><th>Current Stage</th><th>Current Reviewer</th><th>Status</th><th>Last Updated</th><th /></tr></thead><tbody>{visible.map((row: any) => <tr key={`${row.kind}:${row.id}`}><td><span className={`hod-myrequests-type ${row.kind}`}>{typeLabels[row.kind] || label(row.kind)}</span></td><td><strong>{row.subject || '—'}</strong><small>{row.subject_meta || '—'}</small></td><td>{date(row.submitted_at)}</td><td>{row.stage_label || '—'}</td><td>{row.current_reviewer || '—'}</td><td><Status value={row.status} /></td><td>{date(row.updated_at)}</td><td><div className="hod-myrequests-actions"><button type="button" onClick={() => void openDetail(row)}>View</button><button type="button" onClick={() => go(routes[row.kind])}>Open</button></div></td></tr>)}{!visible.length && <tr><td colSpan={8}><div className="hod-myrequests-empty"><strong>{rows.length ? 'No requests match these filters.' : 'You have not submitted any supported requests.'}</strong><span>Only your curriculum, resource, staffing, welfare, and HOD leave requests are tracked here when present.</span></div></td></tr>}</tbody></table></div>
      </section>
    </>}
    {detail && <RequestDetail detail={detail} onClose={() => setDetail(null)} />}
    {detailError && <section className="hod-myrequests-error" role="alert"><b>Request detail unavailable.</b><span>{detailError}</span><button className="btn btn-out" type="button" onClick={() => setDetailError('')}>Dismiss</button></section>}
  </section>
}

async function requestDetail(row: any) { if (row.kind === 'curriculum') return (await api.hodCurriculumRequest(row.id)).request; if (row.kind === 'resource') return (await api.hodResourceRequest(row.id)).request; if (row.kind === 'staffing') return (await api.hodStaffingRequest(row.id)).request; if (row.kind === 'welfare') return (await api.hodStudentWelfareEscalation(row.id)).escalation; if (row.kind === 'hod_leave') return (await api.hodLeaveRequest(row.id)).leave_request; throw new Error('This request type has no supported detail endpoint.') }
function Metric({ label: metricLabel, value, hint, tone = '' }: any) { return <article className={`hod-myrequests-kpi ${tone}`}><span>{metricLabel}</span><b>{value}</b><small>{hint}</small></article> }
function Status({ value }: { value: string }) { return <span className={`hod-myrequests-status ${active.has(value) ? 'active' : value}`}>{label(value)}</span> }

function RequestDetail({ detail, onClose }: any) {
  if (detail.loading) return <Modal title="Request Detail" onClose={onClose}><div className="hod-myrequests-loading"><Spinner /><span>Loading authorized request detail…</span></div></Modal>
  const { row, payload } = detail
  return <Modal className="modal-wide" title={row.subject || 'Request Detail'} onClose={onClose} footer={<button className="btn btn-out" type="button" onClick={onClose}>Close</button>}>
    {row.kind === 'curriculum' && <CurriculumDetail request={payload} />}{row.kind === 'resource' && <ResourceDetail request={payload} />}{row.kind === 'staffing' && <StaffingDetail request={payload} />}{row.kind === 'welfare' && <WelfareDetail request={payload} />}{row.kind === 'hod_leave' && <LeaveDetail request={payload} />}
  </Modal>
}
function DetailGrid({ children }: any) { return <section className="hod-myrequests-detail"><div className="hod-myrequests-detail-grid">{children}</div></section> }
function Field({ label: fieldLabel, value }: any) { return <div><span>{fieldLabel}</span><b>{value || '—'}</b></div> }
function Timeline({ history }: any) { return <section className="hod-myrequests-timeline"><h3>Workflow History</h3>{history?.length ? history.map((item: any, index: number) => <article key={`${item.at}-${index}`}><b>{item.stage_label || 'Workflow action'}</b><span>{item.actor || '—'} · {label(item.decision)} · {date(item.at)}</span>{item.reason && <p>{item.reason}</p>}</article>) : <p>No decision history is recorded yet.</p>}</section> }
function CurriculumDetail({ request }: any) { return <><DetailGrid><Field label="Request type" value={label(request.request_type)} /><Field label="Program" value={request.program ? `${request.program.code} · ${request.program.name}` : '—'} /><Field label="Course" value={request.course ? `${request.course.code} · ${request.course.title}` : '—'} /><Field label="Status" value={label(request.status)} /></DetailGrid><DetailText title="Proposed change" value={request.proposed_change} /><DetailText title="Rationale" value={request.rationale} /><Timeline history={request.history} /></> }
function ResourceDetail({ request }: any) { return <><DetailGrid><Field label="Category" value={label(request.category)} /><Field label="Quantity" value={request.quantity ?? 'Not specified'} /><Field label="Estimated cost" value={request.estimated_cost == null ? 'Not specified' : request.estimated_cost} /><Field label="Status" value={label(request.status)} /></DetailGrid><DetailText title="Requirement" value={request.description} /><DetailText title="Justification" value={request.justification} /><Timeline history={request.history} /></> }
function StaffingDetail({ request }: any) { return <><DetailGrid><Field label="Request type" value={label(request.request_type)} /><Field label="Requested role" value={request.designation_or_role} /><Field label="Headcount" value={request.number_required} /><Field label="Required by" value={date(request.required_by_date)} /></DetailGrid><DetailText title="Justification" value={request.justification} /><Timeline history={request.history} /></> }
function WelfareDetail({ request }: any) { return <><section className="hod-myrequests-welfare"><b>Protected welfare record</b><span>This narrative was fetched only after opening the authorized welfare detail endpoint.</span></section><DetailGrid><Field label="Student" value={`${request.student?.name || '—'} · ${request.student?.roll_no || '—'}`} /><Field label="Concern type" value={label(request.concern_type)} /><Field label="Status" value={label(request.status)} /><Field label="Current stage" value={request.stage_label} /></DetailGrid><DetailText title="Protected welfare summary" value={request.summary} /><DetailText title="Protected escalation reason" value={request.escalation_reason} /><Timeline history={request.history} /></> }
function LeaveDetail({ request }: any) { return <><DetailGrid><Field label="Leave type" value={request.kind} /><Field label="Period" value={`${date(request.from_date)} to ${date(request.to_date)}`} /><Field label="Days" value={request.days} /><Field label="Status" value={label(request.status)} /></DetailGrid><DetailText title="Reason" value={request.reason} /><Timeline history={request.history} /></> }
function DetailText({ title, value }: any) { return <section className="hod-myrequests-detail-text"><h3>{title}</h3><p>{value || 'Not provided'}</p></section> }
