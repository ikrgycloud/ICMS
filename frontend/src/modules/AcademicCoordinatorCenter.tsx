import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { PageHead, Spinner } from './kit'

const workflow = [
  ['Approved Curriculum', 'approved'], ['Academic Calendar Draft', 'draft'], ['Dean Academic Review', 'review'],
  ['Vice Principal Operational Review', 'review'], ['Publish Academic Calendar', 'published'], ['Semester / Term Setup', 'ready'],
]
const execution = ['Course Offerings', 'HOD Inputs', 'Approved Faculty Allocation', 'Sections Ready', 'Timetable Plan', 'Conflict Engine', 'Resolve / Replan', 'HOD Review', 'Vice Principal Timetable Approval', 'Publish Timetable', 'Faculty Portal + Student Portal', 'Class Session Generated', 'Faculty Self Check-in', 'Student Attendance']
export default function AcademicCoordinatorCenter({ onNavigate }: { onNavigate?: (view: string) => void }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => {
    Promise.all([api.sections(), api.courses(), api.academicCalendar(), api.academicRollovers(), api.attendanceSections(), api.notifications()])
      .then(([sections, courses, calendar, rollovers, attendance, notifications]) => setData({ sections, courses, calendar, rollovers, attendance, notifications }))
      .catch(() => setData({ sections: { sections: [] }, courses: { courses: [] }, calendar: { entries: [] }, rollovers: { rollovers: [] }, attendance: { sections: [] }, notifications: { notifications: [] } }))
  }, [])
  const stats = useMemo(() => {
    if (!data) return []
    const sections = data.sections.sections || [], courses = data.courses.courses || [], cal = data.calendar.entries || [], rollovers = data.rollovers.rollovers || []
    const coverage = sections.length ? Math.round(sections.filter((x: any) => x.schedule && x.schedule !== 'TBD').length / sections.length * 100) : 0
    const current = rollovers.find((x: any) => x.status !== 'approved') || rollovers[0]
    return [['Programs in Scope', new Set(courses.map((x: any) => x.program || x.dept)).size, 'programs'], ['Course Offerings', courses.length, 'courses'], ['Sections Planned', sections.length, 'sections'], ['Timetable Coverage', `${coverage}%`, 'scheduled'], ['Active Conflicts', 0, 'needs review'], ['Calendar Changes Pending', cal.filter((x: any) => ['draft', 'pending'].includes(String(x.status).toLowerCase())).length, 'items'], ['Curriculum Execution Issues', 0, 'open issues'], ['Needs My Action', current?.status === 'draft' ? (current.decisions || []).filter((x: any) => x.decision === 'pending').length : 0, 'reviews']]
  }, [data])
  if (!data) return <Spinner />
  const sections = data.sections.sections || [], coverage = stats[3]?.[1] || '0%'
  return <div className="coordinator-center fade-in">
    <main className="coordinator-main"><PageHead title="Academic Coordinator Command Center" sub="Coordinate, review and monitor the complete academic operating cycle." />
      <div className="coordinator-banner"><div><span>Operational readiness</span><strong>{coverage === '100%' ? 'Ready for delivery' : 'In preparation'}</strong><p>Live view across curriculum, calendar, sections, timetable and attendance.</p></div><div className="coordinator-banner-meta"><b>Office 17</b><span>Coordination scope</span></div></div>
      <section className="coordinator-stat-grid">{stats.map(([label, value, hint]) => <article key={String(label)}><span>{label}</span><b>{value}</b><small>{hint}</small></article>)}</section>
      <section className="coordinator-card"><header><div><h2>Academic calendar workflow</h2><p>Prepare and move the academic cycle through its approval hierarchy.</p></div><span className="coordinator-state">Coordinator prepares &amp; submits</span></header><div className="coordinator-flow">{workflow.map(([label, state], i) => <div className={`coordinator-flow-step ${i < 1 ? 'done' : i === 1 ? 'current' : ''}`} key={label}><i>{i + 1}</i><strong>{label}</strong><small>{state === 'review' ? 'Approval gate' : state}</small>{i < workflow.length - 1 && <em>→</em>}</div>)}</div></section>
      <section className="coordinator-two-col"><article className="coordinator-card"><header><div><h2>Curriculum execution</h2><p>Approved curriculum → Curriculum Officer → Track execution</p></div></header><div className="coordinator-readiness"><div><span>Offering ready?</span><b className="ok">YES</b></div><div><span>Scheduling ready?</span><b className={sections.length ? 'ok' : 'warn'}>{sections.length ? 'YES' : 'NO'}</b></div><div><span>Coverage on track?</span><b className={coverage === '100%' ? 'ok' : 'warn'}>{coverage === '100%' ? 'YES' : 'IN PROGRESS'}</b></div></div><div className="coordinator-issue">{sections.length ? 'Track execution across active sections and timetable coverage.' : 'Create a gap / issue and route it to the HOD, then Dean Academics.'}</div></article><article className="coordinator-card"><header><div><h2>Academic readiness</h2><p>Operational checkpoints from live records.</p></div></header><div className="coordinator-checks"><div><span>Sections with timetable</span><b>{sections.filter((x: any) => x.schedule && x.schedule !== 'TBD').length} / {sections.length}</b></div><div><span>Attendance sections</span><b>{(data.attendance.sections || []).length}</b></div><div><span>Open rollover reviews</span><b>{(data.rollovers.rollovers || []).filter((x: any) => x.status !== 'approved').length}</b></div></div></article></section>
      <section className="coordinator-card"><header><div><h2>End-to-end academic delivery</h2><p>Operational hand-offs from offering to attendance.</p></div></header><div className="coordinator-delivery-flow">{execution.map((item, i) => <div className={i < 4 ? 'ready' : i === 5 ? 'attention' : ''} key={item}><i>{i + 1}</i><span>{item}</span></div>)}</div></section>
      <div className="coordinator-roles"><strong>Connected roles</strong><span>Dean Academics</span><span>Vice Principal</span><span>HODs</span><span>Program Coordinators</span><span>Curriculum Officer</span><span>Timetable Officer</span><span>Faculty</span><span>Students</span><span>Exam Controller</span><span>Facilities</span><span>HR</span></div>
    </main></div>
}
