import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner } from '../modules/kit'

const statIcons = ['C', 'T', 'A', 'M', 'W', 'R']
const quickActions = [['Mark Attendance', 'attendance'], ['Create Assignment', 'assignments'], ['Create Assessment', 'assessments'], ['Enter Marks', 'assessments'], ['Messages', 'messages'], ['Course Materials', 'course_materials']]

function dateLabel(value: string) {
  return value ? new Date(value).toLocaleDateString(undefined, { day: '2-digit', month: 'short' }) : '-'
}

export default function FacultyHome({ user, go }: { user: any; go: (v: string) => void }) {
  const [home, setHome] = useState<any>(null)
  const [showSections, setShowSections] = useState(false)

  useEffect(() => {
    setHome(null)
    api.facultyHome().then(setHome).catch((error: any) => setHome({ error: error.message || true }))
  }, [user?.active_role])

  if (!home) return <Spinner />
  if (home.error) return <Empty icon="!" text={typeof home.error === 'string' ? home.error : 'Professor overview could not be loaded.'} />

  const profile = home.profile || {}, kpis = home.kpis || {}, dashboard = home.dashboard || {}
  const sections = home.sections || [], schedule = home.teaching_schedule || [], pending = home.pending_tasks || []
  const mentoring = dashboard.mentoring || {}, research = dashboard.research || {}, requests = dashboard.requests || {}, upcoming = dashboard.upcoming || []
  const classes = schedule.filter((row: any) => row.date === new Date().toISOString().slice(0, 10))
  const attendanceRisk = sections.filter((row: any) => row.attendance_pct != null && row.attendance_pct < 75).length
  const stats = [['Assigned Courses', kpis.assigned_courses ?? new Set(sections.map((row: any) => row.course_code)).size], ["Today's Classes", classes.length], ['Pending Attendance', kpis.pending_attendance || 0], ['Pending Marks / Returned', kpis.returned_marks ? `${kpis.marks_reviews || 0} / ${kpis.returned_marks}` : (kpis.marks_reviews || 0)], ['Active Assignments', kpis.active_assignments || 0], ['Advisees at Risk', kpis.at_risk_advisees || 0]]

  return <main className="prof-overview fade-in">
    <div className="prof-heading"><div><h1>Welcome, {profile.name || 'Professor'}</h1><p>Teaching, student support, research, and request activity from your active responsibilities.</p></div><button className="prof-primary" onClick={() => go('my_schedule')} type="button">View Full Schedule</button></div>
    <section className="prof-stat-grid">{stats.map(([label, value], index) => <article className={`prof-stat p${index} ${index === 0 ? 'prof-stat-action' : ''}`} key={String(label)} onClick={index === 0 ? () => setShowSections(true) : undefined} role={index === 0 ? 'button' : undefined} tabIndex={index === 0 ? 0 : undefined}><span>{statIcons[index]}</span><div><b>{value}</b><small>{label}{index === 0 ? ' - View details' : ''}</small></div></article>)}</section>
    <section className="prof-layout"><div className="prof-left">
      <article className="prof-card prof-schedule"><header><h2>Today's Schedule</h2><button onClick={() => go('my_schedule')} type="button">View full schedule</button></header><div className="prof-card-body">{classes.map((item: any, index: number) => <div className="prof-class" key={item.id}><i className={`prof-dot d${index}`} /><time>{item.time || 'Time pending'}</time><div><b>{item.course_code} {item.subject}</b><p><span>{item.section || 'Section'}</span><span>{item.room || 'Room pending'}</span></p></div><em>{index === 0 ? 'Current' : 'Upcoming'}</em></div>)}{!classes.length && <Empty icon="-" text="No classes scheduled for today." />}</div></article>
      <article className="prof-card prof-sections"><header><h2>Teaching Status</h2><button onClick={() => go('attendance')} type="button">Open attendance</button></header><div className="prof-table-wrap"><table className="prof-table"><thead><tr><th>Course</th><th>Section</th><th>Students</th><th>Attendance</th><th>Next Activity</th></tr></thead><tbody>{sections.map((row: any, index: number) => <tr key={row.id}><td><b>{row.course_code} {row.title}</b></td><td>{row.section}</td><td>{row.enrolled || 0}</td><td>{row.attendance_pct == null ? '-' : `${Math.round(row.attendance_pct)}%`}</td><td>{pending[index]?.title || 'No pending activity'}</td></tr>)}{!sections.length && <tr><td colSpan={5}>No active sections assigned.</td></tr>}</tbody></table></div></article>
    </div><div className="prof-right">
      <article className="prof-card"><header><h2>Teaching Alerts</h2></header><div className="prof-alerts"><div><span>A</span>Pending attendance <b>{kpis.pending_attendance || 0}</b></div><div><span>M</span>Marks in review <b>{kpis.marks_reviews || 0}</b></div><div><span>R</span>Returned marks <b>{kpis.returned_marks || 0}</b></div><div><span>!</span>Attendance below 75% <b>{attendanceRisk}</b></div></div></article>
      <div className="prof-two"><article className="prof-card"><header><h2>Upcoming Due Items</h2></header><div className="prof-checks">{upcoming.map((item: any, index: number) => <button onClick={() => go(item.route)} key={`${item.kind}-${index}`} type="button"><i />{item.title}<small>{dateLabel(item.due_at)}</small></button>)}{!upcoming.length && <p>No upcoming assignment or assessment due items.</p>}</div></article><article className="prof-card"><header><h2>Mentoring Summary</h2></header><div className="prof-mentor-stats"><span><b>{mentoring.advisees || 0}</b>Assigned Advisees</span><span><b>{mentoring.active_cases || 0}</b>Active Cases</span><span><b>{mentoring.at_risk_advisees || 0}</b>At-risk Advisees</span></div></article></div>
      <article className="prof-card prof-research"><header><h2>Research and Requests</h2></header><div>{[['P', research.active_projects || 0, 'Active Projects'], ['U', research.publications || 0, 'Publications'], ['W', requests.active || 0, 'Active Requests'], ['H', requests.total || 0, 'Request History']].map(row => <span key={row[2]}><i>{row[0]}</i><b>{row[1]}</b><small>{row[2]}</small></span>)}</div></article>
    </div></section>
    <article className="prof-card prof-actions"><header><h2>Quick Actions</h2></header><div>{quickActions.map(([label, route]) => <button key={label} onClick={() => go(route)} type="button"><i>+</i>{label}</button>)}</div></article>
    {showSections && <Modal title="My Courses and Sections" onClose={() => setShowSections(false)} className="prof-sections-modal" footer={<button className="btn btn-out" onClick={() => setShowSections(false)} type="button">Close</button>}><div className="prof-table-wrap"><table className="prof-table"><thead><tr><th>Course</th><th>Term</th><th>Section</th><th>Schedule</th><th>Room</th><th>Students</th></tr></thead><tbody>{sections.map((section: any) => <tr key={section.id}><td><b>{section.course_code}</b><br />{section.title}</td><td>{section.term || '-'}</td><td>{section.section}</td><td>{section.schedule || 'Not scheduled'}</td><td>{section.room || 'Not assigned'}</td><td>{section.enrolled || 0}</td></tr>)}{!sections.length && <tr><td colSpan={6}>No active sections assigned.</td></tr>}</tbody></table></div></Modal>}
  </main>
}
