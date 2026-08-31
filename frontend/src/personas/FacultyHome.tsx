import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

const statIcons = ['⌑', '▤', '♧', '▣', '▧', '♙']
const quickActions = [
  ['♧', 'Mark Attendance', 'attendance'], ['▧', 'Create Assignment', 'academics'],
  ['▣', 'Create Assessment', 'examinations'], ['✎', 'Enter Marks', 'examinations'],
  ['▱', 'Message Students', 'students'], ['⇧', 'Upload Materials', 'academics'],
]

function greeting() { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening' }
function initials(name: string) { return name.split(' ').map(x => x[0]).slice(0, 2).join('') }

export default function FacultyHome({ user, go }: { user: any; go: (v: string) => void }) {
  const [home, setHome] = useState<any>(null)
  useEffect(() => { setHome(null); api.facultyHome().then(setHome).catch(() => setHome({ error: true })) }, [user?.active_role])
  if (!home) return <Spinner />
  if (home.error) return <Empty icon="!" text="Professor overview could not be loaded." />

  const profile = home.profile || {}, kpis = home.kpis || {}, sections = home.sections || []
  const schedule = home.teaching_schedule || [], pending = home.pending_tasks || [], notes = home.announcements || []
  const today = new Date().toISOString().slice(0, 10)
  const classes = schedule.filter((x: any) => x.date === today)
  const totalStudents = kpis.students ?? sections.reduce((n: number, x: any) => n + (x.enrolled || 0), 0)
  const assessments = home.performance?.assessments ?? 0
  const attendanceRisk = Math.max(0, sections.filter((x: any) => x.attendance_pct != null && x.attendance_pct < 75).length)
  const associate = user?.office_n === 12 ? home.associate_context || {} : null
  const stats = associate ? [
    ['Assigned Courses', associate.assigned_courses ?? 0], ['Assigned Sections', sections.length], ['Students Mapped', totalStudents],
    ['Classes This Week', kpis.classes_this_week ?? 0], ['Attendance Pending', attendanceRisk], ['Marks Pending', kpis.marks_entry_pending ?? 0],
  ] : [
    ['Assigned Courses', kpis.sections ?? sections.length], ['Total Sections', sections.length], ['Students Mapped', totalStudents],
    ['Classes Today', classes.length], ['Pending Assessments', kpis.marks_entry_pending ?? assessments], ['Research Scholars', 0],
  ]
  const title = profile.name ? profile.name.replace(/^Dr\.\s*/i, '') : 'Professor'

  return <main className="prof-overview fade-in">
    <div className="prof-heading"><div><h1>Welcome, {associate ? 'Associate Professor' : 'Professor'}</h1><p>{associate ? 'Mid-senior faculty responsible for assigned teaching, coordination, and student advising.' : 'Senior teaching &amp; research faculty delivering courses, mentoring students, and guiding academic progress.'}</p></div><button className="prof-primary" onClick={() => go('my_schedule')} type="button">▣ &nbsp; View Full Schedule</button></div>
    <section className="prof-stat-grid">{stats.map(([label, value], i) => <article className={`prof-stat p${i}`} key={String(label)}><span>{statIcons[i]}</span><div><b>{value}</b><small>{label}</small></div></article>)}</section>
    <section className="prof-layout">
      <div className="prof-left">
        <article className="prof-card prof-schedule"><header><h2>▣ &nbsp; Today’s Schedule</h2><button onClick={() => go('my_schedule')} type="button">View full schedule</button></header><div className="prof-card-body">
          {classes.map((item: any, i: number) => <div className="prof-class" key={item.id}><i className={`prof-dot d${i}`} /><time>{item.time || 'Time pending'}</time><div><b>{item.course_code} {item.subject}</b><p><span>{item.section || 'Section'}</span><span>{item.room || 'Room TBD'}</span><span>Lecture</span></p></div><em>{i === 0 ? 'Ongoing' : i === 1 ? 'Upcoming' : 'Later'}</em></div>)}
          {!classes.length && <Empty icon="○" text="No classes scheduled for today." />}
        </div></article>
        <article className="prof-card prof-sections"><header><h2>▤ &nbsp; My Sections</h2><button onClick={() => go('academics')} type="button">View all sections</button></header><div className="prof-table-wrap"><table className="prof-table"><thead><tr><th>Course</th><th>Section</th><th>Students</th><th>Attendance Avg</th><th>Next Activity</th><th>Action</th></tr></thead><tbody>
          {sections.map((x: any, i: number) => <tr key={x.id}><td><b>{x.course_code} {x.title}</b></td><td>{x.section}</td><td>{x.enrolled || 0}</td><td><span className="prof-progress"><i style={{ width: `${x.attendance_pct || 0}%` }} /></span>{x.attendance_pct == null ? '—' : `${Math.round(x.attendance_pct)}%`}</td><td><b>{pending[i]?.title || 'No activity'}</b></td><td><button onClick={() => go('academics')} type="button">Open</button></td></tr>)}
          {!sections.length && <tr><td colSpan={6}>No sections assigned.</td></tr>}</tbody></table></div></article>
      </div>
      <div className="prof-right">
        <article className="prof-card"><header><h2>♧ &nbsp; Teaching Alerts</h2></header><div className="prof-alerts"><div><span>♧</span>{attendanceRisk || 0} section(s) below 75% attendance <b>{attendanceRisk}</b></div><div><span>▧</span>{pending.length} academic task(s) require attention <b>{pending.length}</b></div><div><span>▣</span>{kpis.marks_entry_pending || 0} marks submissions due <b>{kpis.marks_entry_pending || 0}</b></div><div><span>♧</span>Attendance review requests pending <b>0</b></div></div></article>
        <div className="prof-two"><article className="prof-card"><header><h2>▧ &nbsp; Pending Academic Work</h2></header><div className="prof-checks">{pending.slice(0,4).map((x:any) => <button onClick={() => go(x.kind === 'attendance' ? 'attendance' : 'examinations')} key={x.id} type="button"><i />{x.title}</button>)}{!pending.length && <p>No pending academic work.</p>}</div></article>
        <article className="prof-card"><header><h2>♧ &nbsp; Mentoring &amp; Students</h2></header><div className="prof-mentor-stats"><span><b>{totalStudents}</b>Advisee Students</span><span><b>{attendanceRisk}</b>At-risk Students</span><span><b>{classes.length}</b>Meetings this week</span></div><div className="prof-student-list">{sections.slice(0,2).map((x:any, i:number) => <div key={x.id}><i>{initials(x.title || `S${i}`)}</i><p><b>{x.title}</b><small>{x.course_code} · {x.section}</small></p><em>{x.attendance_pct == null ? 'Review' : `${Math.round(x.attendance_pct)}% attendance`}</em></div>)}</div></article></div>
        <article className="prof-card prof-research"><header><h2>♧ &nbsp; Research Snapshot</h2></header><div>{[['♙','0','Active Projects'],['♧','0','Research Scholars'],['▧','0','Draft Papers'],['▣','0','Upcoming Review']].map(x => <span key={x[2]}><i>{x[0]}</i><b>{x[1]}</b><small>{x[2]}</small></span>)}</div></article>
      </div>
    </section>
    <article className="prof-card prof-actions"><header><h2>ϟ &nbsp; Quick Actions</h2></header><div>{quickActions.map(([icon,label,route]) => <button key={label} onClick={() => go(route)} type="button"><i>{icon}</i>{label}</button>)}</div></article>
  </main>
}
