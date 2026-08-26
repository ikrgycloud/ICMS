import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

export default function FacultyHome({ user, go }: { user: any; go: (v: string) => void })
  const [home, setHome] = useState<any>(null)
  useEffect(() => { api.facultyHome().then(setHome).catch(() => setHome({ error: true })) }, [user?.active_role])
  if (!home) return <Spinner />
  if (home.error) return <Empty icon="!" text="Professor overview could not be loaded." />
  const { profile, kpis, sections = [], pending_tasks: pending = [], announcements = [], performance = {}, role_context: roleContext, teaching_schedule: schedule = [], attendance_trend: trend = [], marks_distribution: distribution = [] } = home
  const initials = (profile.name || 'P').split(' ').map((part: string) => part[0]).slice(0, 2).join('')
  const metric = (value: any, suffix = '') => value == null ? '—' : `${value}${suffix}`
  const totalMarks = distribution.reduce((sum: number, item: any) => sum + item.value, 0)
  return <div className="faculty-overview fade-in">
    <section className="faculty-hero"><div className="faculty-hero-avatar">{initials}</div><div className="faculty-identity"><h1>{profile.name}</h1><p>{profile.emp_id} · {roleContext?.active_role || profile.designation} · {profile.department || 'Department not set'}</p><span>✉ {profile.email || 'Email not set'} {profile.phone && <> <i /> ☎ {profile.phone}</>}</span>{roleContext?.available_roles?.length > 1 && <small className="faculty-role-note">Role access: {roleContext.available_roles.join(' · ')}</small>}</div><HeroCount icon="▤" value={kpis.sections} label="Sections"/><HeroCount icon="♙" value={kpis.students} label="Students"/><HeroCount icon="▣" value={kpis.classes_this_week} label="Classes this week"/></section>
    <div className="faculty-kpis"><Metric icon="▤" title="My Sections" value={kpis.sections} note="Active sections" tone="mint"/><Metric icon="♙" title="Enrolled Students" value={kpis.students} note="Across my sections" tone="blue"/><Metric icon="▣" title="Classes This Week" value={kpis.classes_this_week} note="From teaching schedule" tone="purple"/><Metric icon="☑" title="Pending Tasks" value={kpis.pending_tasks} note="Require your action" tone="orange"/><Metric icon="↗" title="Average Attendance" value={metric(kpis.average_attendance, '%')} note="Across my sections" tone="teal"/><Metric icon="✎" title="Marks Entry Pending" value={kpis.marks_entry_pending ?? 0} note="Assessments pending" tone="rose"/></div>
    <div className="faculty-overview-grid faculty-primary-grid">
      <section className="faculty-card faculty-sections"><CardHead title="My Sections" action="View all →" onClick={() => go('academics')}/>{sections.length ? sections.map((section: any) => <button className="faculty-section-row" key={section.id} onClick={() => go('attendance')}><b>{section.section}</b><div><strong>{section.course_code} · {section.title}</strong><span>{section.schedule || 'Schedule pending'} · {section.room || 'Room pending'}</span></div><div><strong>{section.enrolled} / {section.capacity}</strong><span>Enrolled</span></div><div><strong>{metric(section.attendance_pct, '%')}</strong><span>Attendance</span><i><em style={{ width: `${section.attendance_pct || 0}%` }}/></i></div></button>) : <Empty icon="Sections" text="No sections are assigned this term." />}</section>
      <section className="faculty-card faculty-timetable"><CardHead title="Teaching Schedule (This Week)" action="View all →" onClick={() => go('my_schedule')}/>{schedule.length ? <div className="faculty-table"><div className="faculty-table-head"><span>Day / Time</span><span>Section</span><span>Subject</span><span>Room</span></div>{schedule.slice(0, 4).map((item: any) => <button key={item.id} onClick={() => go('my_schedule')}><span>{item.day} {item.time}</span><span>{item.course_code}({item.section})</span><strong>{item.subject}</strong><em>{item.room}</em></button>)}</div> : <Empty icon="Schedule" text="No scheduled classes this week." />}</section>
      <section className="faculty-card"><CardHead title="Pending Tasks" action="View all →" onClick={() => go('examinations')}/>{pending.length ? pending.map((task: any) => <button className="faculty-list-row" key={task.id} onClick={() => go(task.kind === 'attendance' ? 'attendance' : 'examinations')}><b>{task.kind === 'attendance' ? 'A' : 'M'}</b><div><strong>{task.title}</strong><span>{task.course}</span></div><em>{task.due || `${task.count} pending`}</em></button>) : <Empty icon="✓" text="No pending attendance or marks tasks." />}</section>

import { DecisionToast, Empty, Modal, Spinner } from '../modules/kit'

export default function FacultyHome({ user, go }: { user: any; go: (v: string) => void }) {
  const [home, setHome] = useState<any>(null)
  const [sections, setSections] = useState<any>(null)
  const [sel, setSel] = useState<any>(null)
  const [students, setStudents] = useState<any>(null)
  const [tasks, setTasks] = useState<any>({ assignments: [] })
  const [assessments, setAssessments] = useState<any>({ assessments: [] })
  const [showTask, setShowTask] = useState(false)
  const [showAssessment, setShowAssessment] = useState(false)
  const [decision, setDecision] = useState<any>(null)
  const [taskForm, setTaskForm] = useState({ title: '', description: '', due_at: '', status: 'published', reference_url: '' })
  const [assessmentForm, setAssessmentForm] = useState({
    name: '',
    max_marks: 20,
    assessment_type: 'quiz',
    scheduled_at: '',
    end_at: '',
    published: true,
    instructions: '',
  })

  useEffect(() => {
    api.facultyHome().then(setHome).catch(() => {})
    api.facultySections().then(setSections).catch(() => {})
  }, [])

  function loadSectionData(section: any) {
    setStudents(null)
    Promise.allSettled([
      api.facultySectionStudents(section.id),
      api.sectionAssignments(section.id),
      api.examAssessments(section.id),
    ]).then(([studentsRes, tasksRes, assessmentsRes]) => {
      setStudents(studentsRes.status === 'fulfilled' ? studentsRes.value : { students: [] })
      setTasks(tasksRes.status === 'fulfilled' ? tasksRes.value : { assignments: [] })
      setAssessments(assessmentsRes.status === 'fulfilled' ? assessmentsRes.value : { assessments: [] })
    })
  }

  function openSection(section: any) {
    setSel(section)
    loadSectionData(section)
  }

  async function createTask() {
    if (!sel) return
    try {
      const response = await api.createAssignment(sel.id, taskForm)
      setDecision(response.decision)
      setShowTask(false)
      setTaskForm({ title: '', description: '', due_at: '', status: 'published', reference_url: '' })
      loadSectionData(sel)
    } catch (error: any) {
      setDecision({ outcome: 'DENY', reason: error.message })
    }
  }

  async function createAssessment() {
    if (!sel) return
    try {
      const response = await api.createAssessment({ ...assessmentForm, section_id: sel.id })
      setDecision(response.decision)
      setShowAssessment(false)
      setAssessmentForm({
        name: '',
        max_marks: 20,
        assessment_type: 'quiz',
        scheduled_at: '',
        end_at: '',
        published: true,
        instructions: '',
      })
      loadSectionData(sel)
    } catch (error: any) {
      setDecision({ outcome: 'DENY', reason: error.message })
    }
  }

  if (!home) return <Spinner />
  const profile = home.profile
  const kpis = home.kpis
  const initials = (profile.name || 'F').split(' ').map((part: string) => part[0]).slice(0, 2).join('')

  return (
    <div className="fade-in">
      <div className="profile-band">
        <div className="pb-avatar">{initials}</div>
        <div>
          <div className="pb-name">{profile.name}</div>
          <div className="pb-meta"><span className="mono">{profile.emp_id}</span> • {profile.designation} • {profile.department}</div>
        </div>
        <div className="pb-stats">
          <div className="pb-stat"><div className="pb-stat-v">{kpis.sections}</div><div className="pb-stat-l">Sections</div></div>
          <div className="pb-stat"><div className="pb-stat-v">{kpis.students}</div><div className="pb-stat-l">Students</div></div>
        </div>
      </div>

      <div className="split">
        <div className="card" style={{ flex: '0 0 340px' }}>
          <div className="card-h"><h3>My sections</h3><span className="hint">{sections?.sections.length || 0} this term</span></div>
          <div className="list">
            {(sections?.sections || []).map((section: any) => (
              <button key={section.id} className={`list-item ${sel?.id === section.id ? 'on' : ''}`} onClick={() => openSection(section)} type="button">
                <div>
                  <div className="li-title mono">{section.course_code} • {section.section}</div>
                  <div className="li-sub">{section.title}</div>
                </div>
                <div className="li-metric">{section.enrolled}</div>
              </button>
            ))}
            {(!sections || sections.sections.length === 0) && <Empty icon="Books" text="No sections assigned" />}
          </div>
        </div>

        <div className="card" style={{ flex: 1 }}>
          {!sel && <Empty icon="Class" text="Select a section to see your class roster" />}
          {sel && !students && <Spinner />}
          {sel && students && (
            <>
              <div className="card-h">
                <h3>{sel.course_code} • Section {sel.section} — {students.students.length} students</h3>
                <div className="row-actions">
                  <button className="btn btn-sm btn-out" onClick={() => go('attendance')} type="button">Mark attendance</button>
                  <button className="btn btn-sm btn-out" onClick={() => setShowTask(true)} type="button">Create task</button>
                  <button className="btn btn-sm btn-out" onClick={() => setShowAssessment(true)} type="button">Schedule quiz / test</button>
                  <button className="btn btn-sm btn-crimson" onClick={() => go('examinations')} type="button">Enter marks</button>
                </div>
              </div>

              <div className="tbl-scroll">
                <table className="tbl">
                  <thead><tr><th>Roll No</th><th>Name</th><th>CGPA</th><th>Attendance</th></tr></thead>
                  <tbody>
                    {students.students.map((student: any) => (
                      <tr key={student.roll_no}>
                        <td className="mono">{student.roll_no}</td>
                        <td><b>{student.name}</b></td>
                        <td>{student.cgpa?.toFixed(2)}</td>
                        <td>{student.attendance_pct != null ? `${student.attendance_pct}%` : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid-2" style={{ padding: 20 }}>
                <div className="card">
                  <div className="card-h"><h3>Section tasks</h3></div>
                  <div className="card-pad">
                    {(tasks.assignments || []).map((task: any) => (
                      <div className="snap" key={task.id}>
                        <span><b>{task.title}</b></span>
                        <span className="hint">{task.due_at ? new Date(task.due_at).toLocaleString() : 'No due date'}</span>
                      </div>
                    ))}
                    {(!tasks.assignments || tasks.assignments.length === 0) && <Empty text="No tasks published for this section" />}
                  </div>
                </div>

                <div className="card">
                  <div className="card-h"><h3>Quiz / test schedule</h3></div>
                  <div className="card-pad">
                    {(assessments.assessments || []).map((assessment: any) => (
                      <div className="snap" key={assessment.id}>
                        <span><b>{assessment.name}</b> - {assessment.assessment_type}</span>
                        <span className="hint">{assessment.scheduled_at ? new Date(assessment.scheduled_at).toLocaleString() : 'Schedule not set'}</span>
                      </div>
                    ))}
                    {(!assessments.assessments || assessments.assessments.length === 0) && <Empty text="No assessments scheduled yet" />}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {showTask && (
        <Modal
          title={`Create task for ${sel?.course_code || 'section'}`}
          onClose={() => setShowTask(false)}
          footer={<><button className="btn btn-out" onClick={() => setShowTask(false)} type="button">Cancel</button><button className="btn btn-brass" onClick={createTask} type="button">Publish task</button></>}
        >
          <div className="form-row"><label>Title</label><input className="inp" value={taskForm.title} onChange={e => setTaskForm({ ...taskForm, title: e.target.value })} /></div>
          <div className="form-row"><label>Description</label><textarea className="inp" value={taskForm.description} onChange={e => setTaskForm({ ...taskForm, description: e.target.value })} rows={4} /></div>
          <div className="grid-2">
            <div className="form-row"><label>Due at</label><input className="inp" type="datetime-local" value={taskForm.due_at} onChange={e => setTaskForm({ ...taskForm, due_at: e.target.value })} /></div>
            <div className="form-row"><label>Reference URL</label><input className="inp" value={taskForm.reference_url} onChange={e => setTaskForm({ ...taskForm, reference_url: e.target.value })} /></div>
          </div>
        </Modal>
      )}

      {showAssessment && (
        <Modal
          title={`Schedule assessment for ${sel?.course_code || 'section'}`}
          onClose={() => setShowAssessment(false)}
          footer={<><button className="btn btn-out" onClick={() => setShowAssessment(false)} type="button">Cancel</button><button className="btn btn-brass" onClick={createAssessment} type="button">Save schedule</button></>}
        >
          <div className="grid-2">
            <div className="form-row"><label>Name</label><input className="inp" value={assessmentForm.name} onChange={e => setAssessmentForm({ ...assessmentForm, name: e.target.value })} /></div>
            <div className="form-row"><label>Type</label>
              <select className="select" value={assessmentForm.assessment_type} onChange={e => setAssessmentForm({ ...assessmentForm, assessment_type: e.target.value })}>
                <option value="quiz">Quiz</option>
                <option value="test">Test</option>
                <option value="midterm">Midterm</option>
              </select>
            </div>
          </div>
          <div className="grid-2">
            <div className="form-row"><label>Max marks</label><input className="inp" type="number" value={assessmentForm.max_marks} onChange={e => setAssessmentForm({ ...assessmentForm, max_marks: Number(e.target.value) })} /></div>
            <div className="form-row"><label>Scheduled at</label><input className="inp" type="datetime-local" value={assessmentForm.scheduled_at} onChange={e => setAssessmentForm({ ...assessmentForm, scheduled_at: e.target.value })} /></div>
          </div>
          <div className="grid-2">
            <div className="form-row"><label>End at</label><input className="inp" type="datetime-local" value={assessmentForm.end_at} onChange={e => setAssessmentForm({ ...assessmentForm, end_at: e.target.value })} /></div>
            <div className="form-row"><label>Instructions</label><input className="inp" value={assessmentForm.instructions} onChange={e => setAssessmentForm({ ...assessmentForm, instructions: e.target.value })} /></div>
          </div>
        </Modal>
      )}

      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
    <div className="faculty-overview-grid lower"><section className="faculty-card"><CardHead title="Recent Announcements" action="View all →" onClick={() => go('workflows')}/>{announcements.length ? announcements.map((note: any) => <div className="faculty-list-row" key={note.id}><b>i</b><div><strong>{note.title}</strong><span>{note.detail}</span></div><em>{note.date}</em></div>) : <Empty icon="i" text="No recent announcements." />}</section><section className="faculty-card faculty-quick"><h2>Quick Actions</h2><div><button onClick={() => go('attendance')}>Mark Attendance</button><button onClick={() => go('examinations')}>Enter Marks</button><button onClick={() => go('workflows')}>Message Students</button><button onClick={() => go('academics')}>View Course Materials</button><button onClick={() => go('my_schedule')}>View My Schedule</button></div></section></div>
    <div className="faculty-bottom-grid"><section className="faculty-card faculty-performance"><h2>Academic Performance Overview</h2><div className="faculty-performance-metrics"><Metric title="Assessments Conducted" value={performance.assessments} note="This term" tone="mint"/><Metric title="Average Score" value={metric(performance.average_score, '%')} note="Entered marks" tone="blue"/><Metric title="Marks Entered" value={metric(performance.expected_marks ? Math.round(100 * performance.marks_entered / performance.expected_marks) : null, '%')} note={`${performance.marks_entered || 0} records entered`} tone="purple"/><Metric title="Class Average" value={metric(kpis.average_grade)} note="Out of 10" tone="teal"/></div><div className="faculty-charts"><Trend trend={trend}/><Distribution rows={distribution} total={totalMarks}/></div></section><aside className="faculty-card faculty-glance"><h2>At a Glance</h2><Glance label="Total Students" value={kpis.students}/><Glance label="Total Classes This Week" value={kpis.classes_this_week}/><Glance label="Office Hours" value={profile.office_hours || 'Not set'}/><Glance label="Email" value={profile.email || 'Not set'}/><Glance label="Phone" value={profile.phone || 'Not set'}/></aside></div>
  </div>
}
function CardHead({ title, action, onClick }: any) { return <header><h2>{title}</h2><button onClick={onClick}>{action}</button></header> }
function HeroCount({ icon, value, label }: any) { return <div className="faculty-hero-count"><i>{icon}</i><b>{value}</b><small>{label}</small></div> }
function Metric({ icon, title, value, note, tone }: any) { return <section className={`faculty-metric ${tone}`}><i>{icon}</i><div><span>{title}</span><b>{value}</b><small>{note}</small></div></section> }
function Glance({ label, value }: any) { return <div className="faculty-glance-row"><span>{label}</span><b>{value}</b></div> }
function Trend({ trend }: any) { return <section className="faculty-chart"><h3>Attendance Trend (Last 6 Weeks)</h3>{trend.some((item: any) => item.value != null) ? <div className="trend-bars">{trend.map((item: any) => <div key={item.label}><span style={{ height: `${item.value == null ? 0 : Math.max(4, item.value)}%` }} /><small>{item.label}</small></div>)}</div> : <p>No attendance records in the last six weeks.</p>}</section> }
function Distribution({ rows, total }: any) { return <section className="faculty-chart"><h3>Marks Distribution (All Assessments)</h3>{total ? <div className="faculty-distribution">{rows.map((item: any, index: number) => <div key={item.label}><i className={`dist-${index}`}/><span>{item.label}</span><b>{Math.round(item.value / total * 100)}%</b></div>)}</div> : <p>No entered marks are available.</p>}</section> }
