import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner } from '../modules/kit'
import './HodMyLeave.css'

const blank = { kind: '', from_date: '', to_date: '', reason: '' }

export default function HodMyLeave() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [form, setForm] = useState(blank)
  const [showForm, setShowForm] = useState(false)
  const [detail, setDetail] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const load = async () => {
    setError('')
    try { setData(await api.hodLeaveRequests()) }
    catch (reason: any) { setError(reason.message || 'Your leave requests could not be loaded.') }
  }
  useEffect(() => { void load() }, [])
  if (error && !data) return <Empty icon="!" text={error} />
  if (!data) return <Spinner />

  const rows = data.leave_requests || []
  const pending = rows.filter((row: any) => ['submitted', 'under_review'].includes(row.status)).length
  const approved = rows.filter((row: any) => row.status === 'approved').length
  const rejected = rows.filter((row: any) => row.status === 'rejected').length
  const openDetail = async (row: any) => {
    setError('')
    try { setDetail(await api.hodLeaveRequest(row.id)) }
    catch (reason: any) { setError(reason.message || 'Leave request details could not be loaded.') }
  }
  const submit = async () => {
    if (!form.kind.trim() || !form.from_date || !form.to_date || !form.reason.trim()) { setError('Leave type, dates, and reason are required.'); return }
    if (form.from_date > form.to_date) { setError('From date cannot be after to date.'); return }
    setSaving(true); setError(''); setNotice('')
    try {
      await api.createHodLeaveRequest({ kind: form.kind.trim(), from_date: form.from_date, to_date: form.to_date, reason: form.reason.trim() })
      setShowForm(false); setForm(blank); setNotice('Leave request submitted for Vice Principal review.'); await load()
    } catch (reason: any) { setError(reason.message || 'Leave request could not be submitted.') }
    finally { setSaving(false) }
  }
  const cancel = async (row: any) => {
    if (!window.confirm('Cancel this leave request?')) return
    setSaving(true); setError(''); setNotice('')
    try { await api.cancelHodLeaveRequest(row.id); setNotice('Leave request cancelled.'); await load(); if (detail?.leave_request?.id === row.id) setDetail(null) }
    catch (reason: any) { setError(reason.message || 'Leave request could not be cancelled.') }
    finally { setSaving(false) }
  }

  return <main className="hod-leave-page fade-in">
    <header className="hod-leave-head"><div><p>Self-service leave</p><h1>My Leave</h1><span>Submit and track your leave requests through the configured campus approval chain.</span></div><button className="btn btn-primary" type="button" onClick={() => { setError(''); setShowForm(true) }}>New Leave Request</button></header>
    {error && <p className="hod-leave-message error" role="alert">{error}</p>}{notice && <p className="hod-leave-message">{notice}</p>}
    <section className="hod-leave-kpis" aria-label="Leave request summary"><Kpi value={rows.length} label="Total Requests" /><Kpi value={pending} label="Pending" tone="pending" /><Kpi value={approved} label="Approved" tone="approved" /><Kpi value={rejected} label="Rejected" tone="rejected" /></section>
    <section className="hod-leave-register"><header><div><p>Requester-owned tracking</p><h2>My Leave Requests</h2><span>Requests are reviewed by the routed Vice Principal, then Principal.</span></div><button className="btn btn-out" type="button" onClick={load}>Refresh</button></header><div className="hod-leave-table-wrap"><table><thead><tr><th>Leave Type</th><th>From</th><th>To</th><th>Days</th><th>Reason</th><th>Current Stage</th><th>Status</th><th>Submitted On</th><th>Action</th></tr></thead><tbody>{rows.map((row: any) => <tr key={row.id}><td><b>{row.kind}</b></td><td>{dateOnly(row.from_date)}</td><td>{dateOnly(row.to_date)}</td><td>{row.days}</td><td className="hod-leave-reason" title={row.reason}>{row.reason}</td><td>{row.stage_label || '—'}<small>{row.current_reviewer || ''}</small></td><td><Status value={row.status} /></td><td>{dateTime(row.submitted_at)}</td><td><div className="hod-leave-actions"><button type="button" onClick={() => void openDetail(row)}>View</button>{row.cancellable && <button type="button" disabled={saving} onClick={() => void cancel(row)}>Cancel</button>}</div></td></tr>)}{!rows.length && <tr><td colSpan={9} className="hod-leave-empty">You have not submitted any leave requests.</td></tr>}</tbody></table></div></section>
    {showForm && <Modal title="New Leave Request" onClose={() => !saving && setShowForm(false)} footer={<><button className="btn btn-out" type="button" disabled={saving} onClick={() => setShowForm(false)}>Cancel</button><button className="btn btn-primary" type="button" disabled={saving} onClick={() => void submit()}>{saving ? 'Submitting…' : 'Submit Request'}</button></>}><div className="hod-leave-form"><p>Submission routes automatically to the configured campus Vice Principal. The Principal is the final reviewer.</p><label>Leave Type<input value={form.kind} onChange={event => setForm({ ...form, kind: event.target.value })} placeholder="Enter the applicable leave type" /></label><div className="hod-leave-form-dates"><label>From<input type="date" value={form.from_date} onChange={event => setForm({ ...form, from_date: event.target.value })} /></label><label>To<input type="date" value={form.to_date} onChange={event => setForm({ ...form, to_date: event.target.value })} /></label></div><label>Reason<textarea value={form.reason} onChange={event => setForm({ ...form, reason: event.target.value })} /></label></div></Modal>}
    {detail?.leave_request && <Modal title="Leave Request Details" onClose={() => setDetail(null)} footer={<button className="btn btn-out" type="button" onClick={() => setDetail(null)}>Close</button>}><LeaveDetail request={detail.leave_request} /></Modal>}
  </main>
}

function Kpi({ value, label, tone = '' }: { value: any; label: string; tone?: string }) { return <article className={tone}><b>{value}</b><span>{label}</span></article> }
function Status({ value }: { value: string }) { return <span className={`hod-leave-status ${value}`}>{String(value || '—').replaceAll('_', ' ')}</span> }
function LeaveDetail({ request }: { request: any }) { return <div className="hod-leave-detail"><div className="hod-leave-detail-grid"><Info label="Leave type" value={request.kind} /><Info label="Period" value={`${dateOnly(request.from_date)} – ${dateOnly(request.to_date)}`} /><Info label="Days" value={request.days} /><Info label="Status" value={request.status} /><Info label="Current stage" value={request.stage_label} /><Info label="Current reviewer" value={request.current_reviewer || '—'} /></div><section><h3>Reason</h3><p>{request.reason}</p></section><section><h3>Workflow History</h3>{request.history?.length ? request.history.map((item: any, index: number) => <article key={index}><b>{item.stage_label}</b><span>{item.actor} · {item.decision}</span><small>{dateTime(item.at)}</small>{item.reason && <p>{item.reason}</p>}</article>) : <p>No reviewer decision has been recorded yet.</p>}</section></div> }
function Info({ label, value }: { label: string; value: any }) { return <div><span>{label}</span><b>{value ?? '—'}</b></div> }
function dateOnly(value: string) { return value ? new Date(`${value}T00:00:00`).toLocaleDateString() : '—' }
function dateTime(value: string) { return value ? new Date(value).toLocaleString() : '—' }
