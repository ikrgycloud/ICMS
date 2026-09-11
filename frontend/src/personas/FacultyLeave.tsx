import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner } from '../modules/kit'

const blank = { kind: 'Casual', from_date: '', to_date: '', half_day: false, reason: '' }
const title = (value: string) => (value || '').replace(/_/g, ' ').replace(/\b\w/g, part => part.toUpperCase())
const dates = (value: string) => value ? new Date(`${value}T00:00:00`).toLocaleDateString() : '-'
const activeLeaveStatuses = ['submitted', 'resubmitted', 'under_review', 'approved']

export default function FacultyLeave() {
  const [data, setData] = useState<any>(null)
  const [editing, setEditing] = useState<any>(null)
  const [form, setForm] = useState<any>(blank)
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const load = () => api.facultyLeaveRequests().then(setData).catch(() => setData({ error: true }))

  useEffect(() => { load() }, [])

  const errorMessage = (error: any, candidate?: any) => {
    const detail = error?.message || 'Could not save leave request.'
    if (!/overlap/i.test(detail) || !candidate?.from_date || !candidate?.to_date) return detail
    const conflict = (data?.leave_requests || []).find((row: any) =>
      row.id !== candidate.id && activeLeaveStatuses.includes(row.status) &&
      row.from_date <= candidate.to_date && row.to_date >= candidate.from_date)
    return conflict
      ? `Cannot submit this leave request because it overlaps an existing active leave request from ${dates(conflict.from_date)} to ${dates(conflict.to_date)}.`
      : 'Cannot submit this leave request because it overlaps an existing active leave request.'
  }

  const open = (row?: any, readOnly = false) => {
    setEditing(row ? { ...row, editable: !readOnly && Boolean(row.editable) } : 'new')
    setForm(row
      ? { kind: row.kind, from_date: row.from_date, to_date: row.to_date, half_day: row.half_day, reason: row.reason }
      : blank)
    setMessage('')
  }

  const save = async (action: string) => {
    setSaving(true)
    setMessage('')
    try {
      const body = { ...form, action }
      if (editing === 'new') await api.createFacultyLeave(body)
      else await api.updateFacultyLeave(editing.id, body)
      setEditing(null)
      await load()
    } catch (error: any) {
      setMessage(errorMessage(error, editing === 'new' ? form : { ...form, id: editing.id }))
    } finally {
      setSaving(false)
    }
  }

  const cancel = async (row: any) => {
    if (!window.confirm('Cancel this leave request?')) return
    setSaving(true)
    setMessage('')
    try {
      await api.cancelFacultyLeave(row.id)
      await load()
    } catch (error: any) {
      setMessage(errorMessage(error, row))
    } finally {
      setSaving(false)
    }
  }

  const submitRow = async (row: any) => {
    setSaving(true)
    setMessage('')
    try {
      await api.updateFacultyLeave(row.id, {
        kind: row.kind,
        from_date: row.from_date,
        to_date: row.to_date,
        half_day: row.half_day,
        reason: row.reason,
        action: row.status === 'returned' ? 'resubmit' : 'submit',
      })
      await load()
    } catch (error: any) {
      setMessage(errorMessage(error, row))
    } finally {
      setSaving(false)
    }
  }

  if (!data) return <Spinner />
  if (data.error) return <Empty icon="!" text="Leave requests could not be loaded." />

  const canEdit = editing === 'new' || Boolean(editing?.editable)
  const reviewerComment = editing && editing !== 'new'
    ? editing.reviewer_comment || editing.returned_comment || ''
    : ''

  return <main className="assess-workspace fade-in">
    <section className="assess-heading">
      <h1>Leave &amp; Requests</h1>
      <p>Create and track your leave requests through the configured approval chain.</p>
    </section>
    <article className="assess-register">
      <header><h2>My Leave Requests</h2><button onClick={() => open()} type="button">Request Leave</button></header>
      <div className="assess-table-wrap">
        <table className="assess-table">
          <thead><tr><th>Leave Type</th><th>From</th><th>To</th><th>Days</th><th>Status</th><th>Current Stage</th><th>Submitted At</th><th>Action</th></tr></thead>
          <tbody>
            {data.leave_requests.map((row: any) => <tr key={row.id}>
              <td><b>{row.kind}</b></td><td>{dates(row.from_date)}</td><td>{dates(row.to_date)}</td><td>{row.days}</td>
              <td>{title(row.status)}</td><td>{row.stage_label}</td><td>{row.submitted_at ? new Date(row.submitted_at).toLocaleString() : '-'}</td>
              <td><span className="row-actions">
                {row.editable && <button onClick={() => open(row)} type="button">Edit</button>}
                {row.status === 'returned' && <button onClick={() => open(row, true)} type="button">View</button>}
                {row.status === 'draft' && <button disabled={saving} onClick={() => submitRow(row)} type="button">Submit</button>}
                {row.status === 'returned' && <button disabled={saving} onClick={() => submitRow(row)} type="button">Resubmit</button>}
                {['draft', 'returned', 'submitted', 'resubmitted', 'under_review'].includes(row.status) && <button disabled={saving} onClick={() => cancel(row)} type="button">Cancel</button>}
                {!row.editable && row.status !== 'returned' && <button onClick={() => open(row, true)} type="button">View</button>}
              </span></td>
            </tr>)}
            {!data.leave_requests.length && <tr><td colSpan={8}>No leave requests yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </article>
    {message && <p className="att-message">{message}</p>}
    {editing && <Modal
      title={editing === 'new' ? 'Request Leave' : (canEdit ? 'Edit Leave Request' : 'Leave Request')}
      onClose={() => setEditing(null)}
      footer={<>
        <button className="btn btn-out" onClick={() => setEditing(null)} type="button">Close</button>
        {canEdit && <>
          <button className="btn btn-out" disabled={saving} onClick={() => save('draft')} type="button">Save Draft</button>
          <button className="btn btn-crimson" disabled={saving} onClick={() => save(editing?.status === 'returned' ? 'resubmit' : 'submit')} type="button">
            {saving ? 'Saving...' : (editing?.status === 'returned' ? 'Resubmit' : 'Submit')}
          </button>
        </>}
      </>}
    >
      {message && <p className="att-message" role="alert">{message}</p>}
      {reviewerComment && <div className="marks-draft-message"><b>{editing.status === 'returned' ? 'Return Reason' : 'Reviewer Comment'}</b><p>{reviewerComment}</p></div>}
      <div className="form-row"><label>Leave Type</label><select className="select" disabled={!canEdit} value={form.kind} onChange={e => setForm({ ...form, kind: e.target.value })}><option>Casual</option><option>Medical</option><option>Earned</option><option>Duty</option></select></div>
      <div className="grid-2">
        <div className="form-row"><label>From Date</label><input className="inp" disabled={!canEdit} type="date" value={form.from_date} onChange={e => setForm({ ...form, from_date: e.target.value })} /></div>
        <div className="form-row"><label>To Date</label><input className="inp" disabled={!canEdit} type="date" value={form.to_date} onChange={e => setForm({ ...form, to_date: e.target.value })} /></div>
      </div>
      <label><input disabled={!canEdit} type="checkbox" checked={form.half_day} onChange={e => setForm({ ...form, half_day: e.target.checked })} /> Half day (single date only)</label>
      <div className="form-row"><label>Reason</label><textarea className="inp" disabled={!canEdit} value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} /></div>
      {editing.history?.length > 0 && <div className="form-row"><label>History</label>{editing.history.map((item: any, index: number) => <p key={index}><b>{item.stage_label}</b> - {item.actor}: {item.decision}{item.reason ? ` - ${item.reason}` : ''}</p>)}</div>}
    </Modal>}
  </main>
}


