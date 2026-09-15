import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

const stageLabel = (item: any) => ({ 1: 'Class Coordinator Review', 2: 'HOD Review', 3: 'Vice Principal Review' } as Record<number, string>)[item.current_stage] || item.status.replaceAll('_', ' ')

export default function FacultyAttendanceCorrections() {
  const [rows, setRows] = useState<any[] | null>(null), [message, setMessage] = useState(''), [busy, setBusy] = useState('')
  const [returning, setReturning] = useState<any>(null), [comment, setComment] = useState('')
  const load = async () => { try { const result = await api.attendanceCorrections('inbox'); setRows(result.corrections || []) } catch (error: any) { setMessage(error.message || 'Could not load attendance correction reviews.'); setRows([]) } }
  useEffect(() => { load() }, [])
  const decide = async (item: any, action: string, note = '') => {
    setBusy(item.id); setMessage('')
    try { await api.decideAttendanceCorrection(item.id, { action, comment: note }); setReturning(null); setComment(''); await load() }
    catch (error: any) { setMessage(error.message || 'Could not record the review decision.') } finally { setBusy('') }
  }
  if (rows === null) return <Spinner />
  return <main className="attendance-workspace fade-in"><section className="att-heading"><div><h1>Attendance Correction Reviews</h1><p>Only attendance corrections currently assigned to you are shown.</p></div></section>{message && <p className="att-message">{message}</p>}<article className="att-register"><header><h2>My review inbox</h2><span>{rows.length} assigned</span></header><div className="att-table-wrap"><table className="att-table"><thead><tr><th>Student</th><th>Course / Section</th><th>Session</th><th>Change requested</th><th>Current stage</th><th>Action</th></tr></thead><tbody>{rows.map(item => <tr key={item.id}><td><b>{item.student}</b></td><td><b>{item.course_code}</b> · Section {item.section}</td><td>{item.session_date} {item.session_time ? `· ${new Date(item.session_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : ''}</td><td>{item.original_status} → {item.requested_status}<span>{item.reason}</span></td><td>{stageLabel(item)}</td><td><div className="row-actions"><button disabled={busy === item.id} onClick={() => decide(item, 'approve')} type="button">Approve</button><button disabled={busy === item.id} onClick={() => { setReturning(item); setComment('') }} type="button">Return / Reject</button></div></td></tr>)}{!rows.length && <tr><td colSpan={6}><Empty text="No attendance corrections are currently assigned to you." /></td></tr>}</tbody></table></div></article>{returning && <div className="att-modal-backdrop"><section className="att-modal" role="dialog" aria-modal="true"><header><div><h2>Return or reject correction</h2><p>{returning.student} · {returning.course_code} Section {returning.section}</p></div><button type="button" onClick={() => setReturning(null)}>×</button></header><div className="att-modal-body"><label>Safe reviewer comment<textarea value={comment} onChange={event => setComment(event.target.value)} /></label></div><footer><button type="button" onClick={() => setReturning(null)}>Cancel</button><button type="button" disabled={busy === returning.id || !comment.trim()} onClick={() => decide(returning, 'return', comment)}>Return</button><button type="button" disabled={busy === returning.id || !comment.trim()} onClick={() => decide(returning, 'reject', comment)}>Reject</button></footer></section></div>}</main>
}
