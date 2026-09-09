import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

export default function FacultyAttendance() {
  const [home, setHome] = useState<any>(null)
  const [sessions, setSessions] = useState<any[]>([])
  const [selected, setSelected] = useState<any>(null)
  const [roster, setRoster] = useState<any[]>([])
  const [present, setPresent] = useState<Set<string>>(new Set())
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  const load = async (targetDate = date) => {
    try {
      const [faculty, sessionData] = await Promise.all([api.facultyHome(), api.facultyClassSessions(targetDate)])
      setHome(faculty)
      setSessions(sessionData.sessions || [])
    } catch { setHome({ error: true }) }
  }

  useEffect(() => { load() }, [])

  const open = async (session: any) => {
    try {
      const result = await api.attendanceRoster(session.section_id, session.id)
      setRoster(result.roster || [])
      setPresent(new Set((result.roster || []).map((student: any) => student.student_id)))
      setSelected(session)
      setMessage('')
    } catch (error: any) { setMessage(error.message || 'Could not load the class roster.') }
  }

  const checkIn = async () => {
    if (!selected) return
    setSaving(true)
    try {
      await api.checkInClassSession(selected.id)
      setSelected({ ...selected, status: 'checked_in', checked_in_at: new Date().toISOString() })
      await load()
    } catch (error: any) { setMessage(error.message || 'Could not check into this class session.') }
    finally { setSaving(false) }
  }

  const save = async () => {
    if (!selected) return
    setSaving(true)
    try {
      const ids = roster.map(student => student.student_id)
      await api.markAttendance({ section_id: selected.section_id, class_session_id: selected.id, present_ids: ids.filter(id => present.has(id)), absent_ids: ids.filter(id => !present.has(id)), on_date: date })
      setMessage('Attendance saved. Finalize the session when the register is complete.')
    } catch (error: any) { setMessage(error.message || 'Could not save attendance.') }
    finally { setSaving(false) }
  }

  const finalize = async () => {
    if (!selected) return
    setSaving(true)
    try { await api.finalizeClassSessionAttendance(selected.id); setSelected(null); setMessage('Attendance finalized.'); await load() }
    catch (error: any) { setMessage(error.message || 'Could not finalize attendance.') }
    finally { setSaving(false) }
  }

  if (!home) return <Spinner />
  if (home.error) return <Empty icon="!" text="Attendance data could not be loaded." />
  const sections = home.sections || []
  const cards = [['Sections', sections.length], ['Students', home.kpis?.students || 0], ['Sessions', sessions.length], ['Pending', sessions.filter(item => item.status !== 'attendance_finalized').length]]

  return <main className="attendance-workspace fade-in">
    <section className="att-heading"><h1>Attendance</h1><p>Select a scheduled class session, check in, and record its roster.</p></section>
    <section className="att-kpis">{cards.map(([label, value], index) => <article className={`att-kpi a${index}`} key={String(label)}><div><b>{value}</b><small>{label}</small></div></article>)}</section>
    <section className="att-layout"><div><div className="att-filters"><label>Date<input type="date" value={date} onChange={event => { setDate(event.target.value); setSelected(null); load(event.target.value) }} /></label></div>
      <article className="att-register"><header><h2>Class Sessions</h2></header><div className="att-table-wrap"><table className="att-table"><thead><tr><th>Course</th><th>Section</th><th>Time</th><th>Room</th><th>Status</th><th>Action</th></tr></thead><tbody>{sessions.map(session => <tr key={session.id}><td><b>{session.course_code}</b> {session.course_title}</td><td>{session.section}</td><td>{session.scheduled_start ? new Date(session.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-'}</td><td>{session.room || '-'}</td><td><em>{session.status.replace('_', ' ')}</em></td><td><button onClick={() => open(session)} type="button">Open roster</button></td></tr>)}{!sessions.length && <tr><td colSpan={6}>No active timetable sessions for this date.</td></tr>}</tbody></table></div></article>
    </div><aside className="att-aside"><article><header><h2>Attendance Flow</h2></header><ol className="attendance-flow"><li>Select class session</li><li>Check in to the session</li><li>Mark active roster</li><li>Finalize attendance</li></ol></article></aside></section>
    {message && !selected && <p className="att-message">{message}</p>}
    {selected && <div className="att-modal-backdrop"><section className="att-modal"><header><h2>{selected.course_code} - Section {selected.section}</h2><button onClick={() => setSelected(null)} type="button">x</button></header>
      {!selected.checked_in_at && selected.status === 'scheduled' ? <div className="att-modal-body"><p>Attendance is locked until you check in to this class session.</p><button disabled={saving} onClick={checkIn} type="button">{saving ? 'Checking in...' : 'Check in to session'}</button></div> : <><div className="att-modal-body">{roster.map(student => <label key={student.student_id}><input type="checkbox" checked={present.has(student.student_id)} onChange={event => setPresent(current => { const next = new Set(current); event.target.checked ? next.add(student.student_id) : next.delete(student.student_id); return next })} /><span><b>{student.roll_no}</b> {student.name}<small>Overall attendance: {student.pct == null ? '-' : `${student.pct}%`}</small></span></label>)}{!roster.length && <p>No enrolled students found.</p>}</div>{message && <p className="att-message">{message}</p>}<footer><button onClick={() => setSelected(null)} type="button">Cancel</button><button disabled={saving || !roster.length} onClick={save} type="button">{saving ? 'Saving...' : 'Save attendance'}</button><button disabled={saving} onClick={finalize} type="button">Finalize</button></footer></>}
    </section></div>}
  </main>
}
