import { useEffect, useState } from 'react'
import { api } from '../api'
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
  )
}
