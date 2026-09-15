import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

const validStatuses = ['present', 'absent', 'late', 'excused']
const presentStatuses = new Set(['present', 'late', 'excused'])
const statusLabel = (value = '') => value.replaceAll('_', ' ')
const correctionLabel = (item: any) => item.status === 'applied' ? 'Applied' : item.status === 'returned' ? 'Returned' : item.status === 'rejected' ? 'Rejected' : ({ 1: 'Class Coordinator Review', 2: 'HOD Review', 3: 'Vice Principal Review' } as Record<number, string>)[item.current_stage] || statusLabel(item.status)

export default function FacultyAttendance() {
  const [home, setHome] = useState<any>(null), [sessions, setSessions] = useState<any[]>([]), [selected, setSelected] = useState<any>(null)
  const [roster, setRoster] = useState<any[]>([]), [statuses, setStatuses] = useState<Record<string, string>>({}), [corrections, setCorrections] = useState<Record<string, any>>({})
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10)), [saving, setSaving] = useState(false), [message, setMessage] = useState('')
  const [correctionTarget, setCorrectionTarget] = useState<any>(null), [requestedStatus, setRequestedStatus] = useState('absent'), [reason, setReason] = useState('')

  const load = async (onDate = date) => { try { const [faculty, sessionData] = await Promise.all([api.facultyHome(), api.facultyClassSessions(onDate)]); setHome(faculty); setSessions(sessionData.sessions || []) } catch { setHome({ error: true }) } }
  useEffect(() => { load() }, [])
  const updateSession = (session: any) => { setSelected(session); setSessions(current => current.map(item => item.id === session.id ? session : item)) }
  const loadCorrections = async () => { const data = await api.attendanceCorrections('mine'); setCorrections(Object.fromEntries((data.corrections || []).map((item: any) => [item.attendance_record_id, item]))) }
  const loadRoster = async (session: any) => {
    const result = await api.attendanceRoster(session.section_id, session.id), loaded = result.roster || []
    setRoster(loaded)
    setStatuses(Object.fromEntries(loaded.map((student: any) => [student.student_id, validStatuses.includes(student.session_status) ? student.session_status : ''])))
    if (session.status === 'attendance_finalized') await loadCorrections()
  }
  const open = async (session: any) => {
    setMessage(''); setRoster([]); setStatuses({}); setSelected(session)
    if (session.checked_in_at || session.status === 'attendance_finalized') try { await loadRoster(session) } catch (error: any) { setMessage(error.message || 'Could not load the class roster.') }
  }
  const checkIn = async () => {
    if (!selected) return
    setSaving(true); setMessage('')
    try { const response = await api.checkInClassSession(selected.id); updateSession(response.session); await loadRoster(response.session) }
    catch (error: any) { setMessage(error.message || 'Could not check into this class session.') } finally { setSaving(false) }
  }
  const save = async () => {
    if (!selected) return false
    const presentIds = roster.filter(student => presentStatuses.has(statuses[student.student_id])).map(student => student.student_id)
    const absentIds = roster.filter(student => statuses[student.student_id] === 'absent').map(student => student.student_id)
    await api.markAttendance({ section_id: selected.section_id, class_session_id: selected.id, present_ids: presentIds, absent_ids: absentIds, on_date: selected.session_date || date })
    await loadRoster(selected); return true
  }
  const saveDraft = async () => { setSaving(true); setMessage(''); try { await save(); setMessage('Attendance draft saved. Finalize only when the register is complete.') } catch (error: any) { setMessage(error.message || 'Could not save attendance.') } finally { setSaving(false) } }
  const fullyMarked = roster.length > 0 && roster.every(student => validStatuses.includes(statuses[student.student_id]))
  const finalized = selected?.status === 'attendance_finalized', checkedIn = Boolean(selected?.checked_in_at) || selected?.status === 'checked_in' || finalized
  const finalize = async () => {
    if (!selected || !fullyMarked) return
    setSaving(true); setMessage('')
    try { await save(); const response = await api.finalizeClassSessionAttendance(selected.id); updateSession(response.session); await loadRoster(response.session); await load(date); setMessage('Attendance finalized. Use Attendance Corrections for any later change.') }
    catch (error: any) { setMessage(error.message || 'Could not finalize attendance.') } finally { setSaving(false) }
  }
  const submitCorrection = async () => {
    if (!correctionTarget) return
    setSaving(true); setMessage('')
    try { const existing = corrections[correctionTarget.attendance_record_id]; if (existing?.status === 'returned') { await api.updateAttendanceCorrection(existing.id, { attendance_record_id: correctionTarget.attendance_record_id, requested_status: requestedStatus, reason }); await api.resubmitAttendanceCorrection(existing.id) } else await api.createAttendanceCorrection({ attendance_record_id: correctionTarget.attendance_record_id, requested_status: requestedStatus, reason }); await loadCorrections(); setCorrectionTarget(null); setMessage('Attendance correction submitted for the configured approval workflow.') }
    catch (error: any) { setMessage(error.message || 'Could not submit the attendance correction.') } finally { setSaving(false) }
  }
  if (!home) return <Spinner />
  if (home.error) return <Empty icon="!" text="Attendance data could not be loaded." />
  const sections = home.sections || [], cards = [['Sections', sections.length], ['Students', home.kpis?.students || 0], ['Sessions', sessions.length], ['Pending', sessions.filter(item => item.status !== 'attendance_finalized').length]]
  const rosterStep = finalized || fullyMarked ? 'done' : checkedIn ? 'active' : ''
  return <main className="attendance-workspace fade-in">
    <section className="att-heading"><h1>Attendance</h1><p>Select a scheduled class session, check in to that session, and record its roster.</p></section>
    <section className="att-kpis">{cards.map(([name, value], index) => <article className={`att-kpi a${index}`} key={String(name)}><div><b>{value}</b><small>{name}</small></div></article>)}</section>
    <section className="att-layout"><div><div className="att-filters"><label>Date<input type="date" value={date} onChange={event => { setDate(event.target.value); setSelected(null); setRoster([]); load(event.target.value) }} /></label></div><article className="att-register"><header><h2>Class Sessions</h2></header><div className="att-table-wrap"><table className="att-table"><thead><tr><th>Course</th><th>Section</th><th>Time</th><th>Room</th><th>Status</th><th>Action</th></tr></thead><tbody>{sessions.map(session => <tr key={session.id}><td><b>{session.course_code}</b> {session.course_title}</td><td>{session.section}</td><td>{session.scheduled_start ? new Date(session.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-'}</td><td>{session.room || '-'}</td><td><em>{statusLabel(session.status)}</em></td><td><button onClick={() => open(session)} type="button">Open roster</button></td></tr>)}{!sessions.length && <tr><td colSpan={6}>No active timetable sessions for this date.</td></tr>}</tbody></table></div></article></div><aside className="att-aside"><article><header><h2>Attendance Flow</h2></header><ol className="attendance-flow"><li className={selected ? 'done' : 'active'}>Select class session</li><li className={checkedIn ? 'done' : selected ? 'active' : ''}>Check in to the session</li><li className={rosterStep}>Mark active roster</li><li className={finalized ? 'done' : fullyMarked ? 'active' : ''}>Finalize attendance</li></ol></article></aside></section>
    {message && !selected && <p className="att-message">{message}</p>}
    {selected && <div className="att-modal-backdrop"><section className="att-modal" role="dialog" aria-modal="true"><header><div><h2>{selected.course_code} - Section {selected.section}</h2><p>{selected.session_date || date} · {statusLabel(selected.status)}</p></div><button onClick={() => setSelected(null)} type="button" aria-label="Close attendance roster">×</button></header>{!checkedIn ? <div className="att-modal-body att-locked"><p>Attendance is locked until you check in to this class session.</p><button disabled={saving} onClick={checkIn} type="button">{saving ? 'Checking in...' : 'Check in to session'}</button></div> : <><div className="att-roster-summary"><span>Total Students <b>{roster.length}</b></span><span>Present <b>{roster.filter(student => presentStatuses.has(statuses[student.student_id])).length}</b></span><span>Absent <b>{roster.filter(student => statuses[student.student_id] === 'absent').length}</b></span><span>Not Marked <b>{roster.filter(student => !validStatuses.includes(statuses[student.student_id])).length}</b></span></div><div className="att-modal-body"><table className="att-roster-table"><thead><tr><th>Roll No</th><th>Student Name</th><th>Attendance</th></tr></thead><tbody>{roster.map(student => { const correction = corrections[student.attendance_record_id]; return <tr key={student.student_id}><td>{student.roll_no}</td><td>{student.name}<small>Overall attendance: {student.pct == null ? '—' : `${student.pct}%`}</small></td><td>{finalized ? <>{statusLabel(student.session_status || 'Not marked')}{student.attendance_record_id && <div>{correction ? <small className="att-correction-status">{correctionLabel(correction)}</small> : <button type="button" onClick={() => { setCorrectionTarget(student); setRequestedStatus(student.session_status === 'present' ? 'absent' : 'present'); setReason('') }}>Request correction</button>}</div>}</> : <div className="att-status-controls"><button type="button" className={statuses[student.student_id] === 'present' ? 'selected' : ''} onClick={() => setStatuses(current => ({ ...current, [student.student_id]: 'present' }))}>Present</button><button type="button" className={statuses[student.student_id] === 'absent' ? 'selected' : ''} onClick={() => setStatuses(current => ({ ...current, [student.student_id]: 'absent' }))}>Absent</button></div>}</td></tr> })}</tbody></table>{!roster.length && <p>No active students found for this section.</p>}</div>{message && <p className="att-message">{message}</p>}<footer><button onClick={() => setSelected(null)} type="button">Cancel</button>{!finalized && <><button disabled={saving || !roster.length} onClick={() => setStatuses(Object.fromEntries(roster.map(student => [student.student_id, 'present'])))} type="button">Mark All Present</button><button disabled={saving || !fullyMarked} onClick={saveDraft} type="button">{saving ? 'Saving...' : 'Save attendance'}</button><button disabled={saving || !fullyMarked} onClick={finalize} type="button">Finalize</button></>}</footer></>}</section></div>}
    {correctionTarget && <div className="att-modal-backdrop"><section className="att-modal att-correction-modal" role="dialog" aria-modal="true"><header><div><h2>Request correction</h2><p>{selected?.course_code} · Section {selected?.section} · {correctionTarget.name}</p></div><button type="button" onClick={() => setCorrectionTarget(null)}>×</button></header><div className="att-modal-body"><p>Current attendance: <b>{statusLabel(correctionTarget.session_status)}</b></p><label>Requested attendance<select value={requestedStatus} onChange={event => setRequestedStatus(event.target.value)}>{validStatuses.filter(status => status !== correctionTarget.session_status).map(status => <option key={status} value={status}>{statusLabel(status)}</option>)}</select></label><label>Reason<textarea value={reason} onChange={event => setReason(event.target.value)} /></label></div><footer><button type="button" onClick={() => setCorrectionTarget(null)}>Cancel</button><button type="button" disabled={saving || !reason.trim()} onClick={submitCorrection}>{saving ? 'Submitting...' : 'Submit correction'}</button></footer></section></div>}
  </main>
}
