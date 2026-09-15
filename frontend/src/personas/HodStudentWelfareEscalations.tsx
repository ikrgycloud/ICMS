import { FormEvent, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Modal, Spinner } from '../modules/kit'

type Escalation = {
  id: string; concern_type: string; status: string; current_stage: number
  stage_label: string; current_reviewer: string; submitted_at: string
  student?: { id: string; name: string; roll_no: string }
}

const label = (value?: string) => String(value || '—').replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase())
const date = (value?: string) => value ? new Date(value).toLocaleDateString() : '—'

export default function HodStudentWelfareEscalations() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [detail, setDetail] = useState<any>(null)
  const [detailError, setDetailError] = useState('')
  const [status, setStatus] = useState('all')
  const [concern, setConcern] = useState('all')
  const [search, setSearch] = useState('')

  const load = async () => {
    setRefreshing(true); setError('')
    try { setData(await api.hodStudentWelfareEscalations()) }
    catch (caught: any) { setError(caught.message || 'Student welfare escalations could not be loaded.') }
    finally { setRefreshing(false) }
  }
  useEffect(() => { void load() }, [])

  const rows: Escalation[] = data?.escalations || []
  const filtered = useMemo(() => rows.filter(row => {
    const matchesStatus = status === 'all' || row.status === status
    const matchesConcern = concern === 'all' || row.concern_type === concern
    const identity = `${row.student?.name || ''} ${row.student?.roll_no || ''}`.toLowerCase()
    return matchesStatus && matchesConcern && identity.includes(search.trim().toLowerCase())
  }), [rows, status, concern, search])
  const count = (state: string) => rows.filter(row => row.status === state).length

  const openDetail = async (id: string) => {
    setDetailError(''); setDetail({ loading: true })
    try { setDetail((await api.hodStudentWelfareEscalation(id)).escalation) }
    catch (caught: any) { setDetail(null); setDetailError(caught.message || 'The protected escalation detail could not be loaded.') }
  }

  if (!data && !error) return <main className="hod-welfare-page"><Spinner /></main>
  return <main className="hod-welfare-page fade-in">
    <header className="hod-welfare-header">
      <div>
        <p className="hod-welfare-eyebrow">{data?.department?.name || 'Your department'}{data?.department?.campus ? ` · ${data.department.campus}` : ''}</p>
        <h1>Student Welfare Escalations</h1>
        <span>Submit department student-support concerns to the authorized Dean Student Affairs reviewer.</span>
      </div>
      <div className="hod-welfare-header-actions">
        <button className="btn btn-out" type="button" onClick={() => void load()} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh'}</button>
        <button className="btn btn-crimson" type="button" onClick={() => setCreateOpen(true)}>New Escalation</button>
      </div>
    </header>

    {error && <section className="hod-welfare-notice" role="alert"><b>Unable to load the register.</b><span>{error}</span><button className="btn btn-out" type="button" onClick={() => void load()}>Try again</button></section>}
    {data && <>
      <section className="hod-welfare-kpis" aria-label="Escalation status summary">
        <Metric value={rows.length} label="Total Escalations" hint="Submitted by your HOD account" />
        <Metric value={count('submitted') + count('under_review')} label="Awaiting Decision" hint="With Dean Student Affairs" tone="pending" />
        <Metric value={count('approved')} label="Approved" hint="Final workflow state" tone="approved" />
        <Metric value={count('rejected')} label="Rejected" hint="Final workflow state" tone="rejected" />
      </section>

      <section className="hod-welfare-register">
        <div className="hod-welfare-register-head"><div><h2>Escalation Register</h2><p>Register entries contain operational metadata only. Protected narrative is available from an authorized record detail.</p></div></div>
        <div className="hod-welfare-filters">
          <label>Search student<input value={search} onChange={event => setSearch(event.target.value)} placeholder="Name or roll number" /></label>
          <label>Status<select value={status} onChange={event => setStatus(event.target.value)}><option value="all">All statuses</option>{['submitted', 'under_review', 'approved', 'rejected'].map(item => <option key={item} value={item}>{label(item)}</option>)}</select></label>
          <label>Concern type<select value={concern} onChange={event => setConcern(event.target.value)}><option value="all">All concern types</option>{(data.options?.concern_types || []).map((item: string) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
          <button className="hod-welfare-clear" type="button" onClick={() => { setSearch(''); setStatus('all'); setConcern('all') }}>Clear filters</button>
        </div>
        <div className="hod-welfare-table-wrap"><table className="hod-welfare-table"><thead><tr><th>Student</th><th>Concern Type</th><th>Submitted</th><th>Reviewer / Stage</th><th>Status</th><th aria-label="Actions" /></tr></thead><tbody>
          {filtered.map(row => <tr key={row.id}><td><strong>{row.student?.name || '—'}</strong><span>{row.student?.roll_no || '—'}</span></td><td>{label(row.concern_type)}</td><td>{date(row.submitted_at)}</td><td>{row.current_reviewer || row.stage_label || 'Completed'}</td><td><span className={`hod-welfare-badge is-${row.status}`}>{label(row.status)}</span></td><td><button className="hod-welfare-detail-button" type="button" onClick={() => void openDetail(row.id)}>View detail</button></td></tr>)}
          {!filtered.length && <tr><td colSpan={6}><div className="hod-welfare-empty"><strong>{rows.length ? 'No entries match these filters.' : 'No welfare escalations submitted.'}</strong><span>{rows.length ? 'Adjust or clear filters to review the register.' : 'Create an escalation only when a department student-support concern requires formal review.'}</span></div></td></tr>}
        </tbody></table></div>
      </section>
    </>}
    {createOpen && <WelfareForm data={data} onClose={() => setCreateOpen(false)} onSaved={() => { setCreateOpen(false); void load() }} />}
    {detail && <WelfareDetail detail={detail} onClose={() => setDetail(null)} />}
    {detailError && <section className="hod-welfare-notice" role="alert"><b>Protected detail unavailable.</b><span>{detailError}</span><button className="btn btn-out" type="button" onClick={() => setDetailError('')}>Dismiss</button></section>}
  </main>
}

function Metric({ value, label: metricLabel, hint, tone = '' }: { value: number; label: string; hint: string; tone?: string }) {
  return <article className={`hod-welfare-kpi ${tone}`}><span>{metricLabel}</span><strong>{value}</strong><small>{hint}</small></article>
}

function WelfareForm({ data, onClose, onSaved }: any) {
  const [form, setForm] = useState({ student_id: '', concern_type: '', summary: '', escalation_reason: '', source_mentoring_case_id: '' })
  const [error, setError] = useState(''); const [saving, setSaving] = useState(false)
  const selectedStudentCases = (data?.options?.source_mentoring_cases || []).filter((item: any) => item.student_id === form.student_id)
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(''); setSaving(true)
    try { await api.createHodStudentWelfareEscalation(form); onSaved() }
    catch (caught: any) { setError(caught.message || 'The escalation could not be submitted.') }
    finally { setSaving(false) }
  }
  return <Modal title="New Student Welfare Escalation" onClose={onClose} footer={<><button className="btn btn-out" type="button" onClick={onClose}>Cancel</button><button className="btn btn-crimson" form="hod-welfare-form" type="submit" disabled={saving}>{saving ? 'Submitting…' : 'Submit for Review'}</button></>}>
    <form id="hod-welfare-form" className="hod-welfare-form" onSubmit={submit}>
      <p className="hod-welfare-form-note">The request is routed to Dean Student Affairs. Narrative entered here is protected and never shown in the register.</p>
      {error && <p className="hod-welfare-form-error" role="alert">{error}</p>}
      <label>Student<select required value={form.student_id} onChange={event => setForm({ ...form, student_id: event.target.value, source_mentoring_case_id: '' })}><option value="">Select a department student</option>{(data?.options?.students || []).map((student: any) => <option key={student.id} value={student.id}>{student.name} · {student.roll_no}</option>)}</select></label>
      <label>Concern type<select required value={form.concern_type} onChange={event => setForm({ ...form, concern_type: event.target.value })}><option value="">Select concern type</option>{(data?.options?.concern_types || []).map((item: string) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
      {selectedStudentCases.length > 0 && <label>Related HOD mentoring referral <select value={form.source_mentoring_case_id} onChange={event => setForm({ ...form, source_mentoring_case_id: event.target.value })}><option value="">No linked referral</option>{selectedStudentCases.map((item: any) => <option key={item.id} value={item.id}>Referral reference · {label(item.status)}</option>)}</select></label>}
      <label>Welfare summary<textarea required maxLength={2000} value={form.summary} onChange={event => setForm({ ...form, summary: event.target.value })} /></label>
      <label>Escalation reason<textarea required maxLength={4000} value={form.escalation_reason} onChange={event => setForm({ ...form, escalation_reason: event.target.value })} /></label>
    </form>
  </Modal>
}

function WelfareDetail({ detail, onClose }: any) {
  if (detail.loading) return <Modal title="Authorized Welfare Detail" onClose={onClose}><div className="hod-welfare-detail-loading"><Spinner /><span>Loading protected record…</span></div></Modal>
  return <Modal title="Authorized Welfare Detail" onClose={onClose} footer={<button className="btn btn-out" type="button" onClick={onClose}>Close</button>}>
    <section className="hod-welfare-detail">
      <div className="hod-welfare-detail-meta"><div><span>Student</span><strong>{detail.student?.name || '—'}</strong><small>{detail.student?.roll_no || '—'}</small></div><div><span>Concern type</span><strong>{label(detail.concern_type)}</strong></div><div><span>Status</span><strong>{label(detail.status)}</strong></div></div>
      <div className="hod-welfare-protected"><span>Protected welfare summary</span><p>{detail.summary || 'Not provided'}</p></div>
      <div className="hod-welfare-protected"><span>Protected escalation reason</span><p>{detail.escalation_reason || 'Not provided'}</p></div>
      <div className="hod-welfare-history"><h3>Decision History</h3>{detail.history?.length ? detail.history.map((item: any, index: number) => <div key={`${item.at}-${index}`}><strong>{item.stage_label || `Stage ${item.stage}`}</strong><span>{label(item.decision)} · {date(item.at)}</span>{item.comment && <p>{item.comment}</p>}</div>) : <p>No decision has been recorded yet.</p>}</div>
    </section>
  </Modal>
}
