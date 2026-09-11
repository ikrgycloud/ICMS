import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, PageHead, Spinner } from './kit'

type Complaint = {
  id: string
  kind: string
  raised_by: string
  subject: string
  detail?: string
  status: 'open' | 'investigating' | 'resolved'
  severity: string
  created_at?: string | null
  investigation_notes?: string
  investigated_by?: string
  investigated_at?: string | null
  resolution_notes?: string
  resolved_by?: string
  resolved_at?: string | null
}

const newComplaint = () => ({ kind: 'Grievance', severity: 'normal', subject: '', detail: '' })

function stamp(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '—'
}

export default function Grievance({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [showRaise, setShowRaise] = useState(false)
  const [form, setForm] = useState(newComplaint)
  const [selected, setSelected] = useState<Complaint | null>(null)
  const [action, setAction] = useState<'investigate' | 'resolve' | null>(null)
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)

  async function load() {
    setError('')
    try {
      setData(await api.grievance())
    } catch (e: any) {
      setError(e.message || 'Unable to load complaints. Please try again.')
    }
  }

  useEffect(() => { load() }, [])

  async function viewComplaint(item: Complaint) {
    setError('')
    try {
      const result = await api.complaint(item.id)
      setSelected(result.complaint)
      setAction(null)
    } catch (e: any) {
      setError(e.message || 'Unable to load complaint details.')
    }
  }

  async function raise() {
    setBusy(true); setError(''); setMessage('')
    try {
      await api.raiseComplaint(form)
      setShowRaise(false); setForm(newComplaint())
      setMessage('Complaint raised successfully.')
      await load()
    } catch (e: any) {
      setError(e.message || 'The complaint could not be raised.')
    } finally { setBusy(false) }
  }

  async function submitAction() {
    if (!selected || !action) return
    setBusy(true); setError(''); setMessage('')
    try {
      const result = action === 'investigate'
        ? await api.investigateComplaint(selected.id, notes)
        : await api.resolveComplaint(selected.id, notes)
      setSelected(null)
      setAction(null); setNotes('')
      setMessage(action === 'investigate' ? 'Investigation started successfully.' : 'Complaint resolved successfully.')
      await load()
    } catch (e: any) {
      setError(e.message || 'The complaint workflow could not be updated.')
    } finally { setBusy(false) }
  }

  if (!data && !error) return <Spinner />
  const complaints: Complaint[] = data?.complaints || []
  const canRaise = !!(data?.can_raise ?? caps?.raise)
  const canInvestigate = !!data?.can_investigate
  const canResolve = !!data?.can_resolve

  return (
    <div className="fade-in">
      <PageHead title="Grievance & discipline" sub="Complaints intake, investigation and resolution"
        right={<button className="btn btn-brass" disabled={!canRaise || busy} onClick={() => setShowRaise(true)}>+ Raise complaint</button>} />

      {message && <div className="success-box" role="status">{message}</div>}
      {error && <div className="hostel-error" role="alert"><span>{error}</span><button className="btn btn-sm btn-out" onClick={() => { setError(''); load() }}>Retry</button></div>}

      <div className="card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Type</th><th>Raised by</th><th>Subject</th><th>Severity</th><th>Status</th><th style={{ textAlign: 'right' }}>Actions</th></tr></thead>
            <tbody>
              {complaints.map((complaint) => (
                <tr key={complaint.id}>
                  <td><span className={`tag ${complaint.kind === 'Ragging' ? 'tag-rose' : ''}`}>{complaint.kind}</span></td>
                  <td className="mono">{complaint.raised_by}</td>
                  <td><b>{complaint.subject}</b></td>
                  <td><span className={`pill s-${complaint.severity}`}>{complaint.severity}</span></td>
                  <td><span className={`pill s-${complaint.status}`}>{complaint.status}</span></td>
                  <td style={{ textAlign: 'right' }}>
                    <div className="row-actions">
                      <button className="btn btn-sm btn-out" onClick={() => viewComplaint(complaint)}>Details</button>
                      {complaint.status === 'open' && canInvestigate && <button className="btn btn-sm btn-out" onClick={() => { setSelected(complaint); setNotes(''); setAction('investigate') }}>Investigate</button>}
                      {complaint.status === 'investigating' && canResolve && <button className="btn btn-sm btn-teal" onClick={() => { setSelected(complaint); setNotes(''); setAction('resolve') }}>Resolve</button>}
                      {complaint.status !== 'resolved' && !canInvestigate && !canResolve && <span className="mono">Awaiting Grievance Office</span>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!complaints.length && <Empty icon="⚖" text="No complaints are available for this campus." />}
        </div>
      </div>

      {showRaise && <Modal title="Raise a complaint" onClose={() => !busy && setShowRaise(false)}
        footer={<><button className="btn btn-out" disabled={busy} onClick={() => setShowRaise(false)}>Cancel</button><button className="btn btn-brass" onClick={raise} disabled={busy || !form.subject.trim() || !form.detail.trim()}>{busy ? 'Submitting…' : 'Submit complaint'}</button></>}>
        <div className="form-row"><label>Type</label><select className="select" value={form.kind} disabled={busy} onChange={e => setForm({ ...form, kind: e.target.value })}><option>Grievance</option><option>Ragging</option><option>Discipline</option></select></div>
        <div className="form-row"><label>Severity</label><select className="select" value={form.severity} disabled={busy} onChange={e => setForm({ ...form, severity: e.target.value })}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="critical">Critical</option></select></div>
        <div className="form-row"><label>Subject</label><input className="inp" value={form.subject} disabled={busy} onChange={e => setForm({ ...form, subject: e.target.value })} /></div>
        <div className="form-row"><label>Details</label><textarea className="inp" rows={4} value={form.detail} disabled={busy} onChange={e => setForm({ ...form, detail: e.target.value })} /></div>
        <div className="success-box">Raised by is recorded from the signed-in account. Tenant and campus are recorded by the server.</div>
      </Modal>}

      {selected && !action && <Modal title="Complaint details" onClose={() => setSelected(null)} footer={<button className="btn btn-out" onClick={() => setSelected(null)}>Close</button>}>
        <div className="form-row"><label>Complaint</label><div><b>{selected.subject}</b><div className="mono">{selected.kind} · {selected.severity} · {selected.status}</div></div></div>
        <div className="form-row"><label>Raised by</label><div>{selected.raised_by} · {stamp(selected.created_at)}</div></div>
        <div className="form-row"><label>Details</label><div>{selected.detail || '—'}</div></div>
        <div className="form-row"><label>Investigation</label><div>{selected.investigation_notes || 'Not started'}{selected.investigated_by && <div className="mono">{selected.investigated_by} · {stamp(selected.investigated_at)}</div>}</div></div>
        <div className="form-row"><label>Resolution</label><div>{selected.resolution_notes || 'Not resolved'}{selected.resolved_by && <div className="mono">{selected.resolved_by} · {stamp(selected.resolved_at)}</div>}</div></div>
      </Modal>}

      {selected && action && <Modal title={action === 'investigate' ? 'Start investigation' : 'Resolve complaint'} onClose={() => !busy && setAction(null)}
        footer={<><button className="btn btn-out" disabled={busy} onClick={() => setAction(null)}>Cancel</button><button className="btn btn-brass" disabled={busy || !notes.trim()} onClick={submitAction}>{busy ? 'Saving…' : action === 'investigate' ? 'Save investigation' : 'Save resolution'}</button></>}>
        <div className="form-row"><label>Complaint</label><div><b>{selected.subject}</b><div className="mono">Current status: {selected.status}</div></div></div>
        <div className="form-row"><label>{action === 'investigate' ? 'Investigation notes and findings' : 'Resolution details and action taken'}</label><textarea className="inp" rows={5} value={notes} disabled={busy} onChange={e => setNotes(e.target.value)} /></div>
      </Modal>}
    </div>
  )
}
