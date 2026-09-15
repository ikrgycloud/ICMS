import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner } from '../modules/kit'

const display = (value: any) => value === null || value === undefined || value === '' ? '—' : value

export default function HodDepartmentStudents({ go }: { go: (view: string) => void }) {
  const [data, setData] = useState<any>(null)
  const [courseId, setCourseId] = useState('')
  const [sectionId, setSectionId] = useState('')
  const [filters, setFilters] = useState({ q: '', semester: '', status: '', risk: 'all' })
  const [selected, setSelected] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async (selection: { course_id?: string, section_id?: string } = {}) => {
    setLoading(true); setError('')
    try { setData(await api.hodStudents(selection)) }
    catch (err: any) { setError(err.message || 'Department student records could not be loaded.') }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])

  const chooseCourse = async (nextCourseId: string) => {
    setCourseId(nextCourseId); setSectionId(''); setSelected(null); setFilters({ q: '', semester: '', status: '', risk: 'all' })
    await load(nextCourseId ? { course_id: nextCourseId } : {})
  }
  const chooseSection = async (nextSectionId: string) => {
    setSectionId(nextSectionId); setSelected(null); setFilters({ q: '', semester: '', status: '', risk: 'all' })
    await load(nextSectionId ? { course_id: courseId, section_id: nextSectionId } : { course_id: courseId })
  }

  const rows = data?.students || []
  const semesters = useMemo(() => [...new Set(rows.map((row: any) => row.semester).filter(Boolean))].sort((a: any, b: any) => a - b), [rows])
  const statuses = useMemo(() => [...new Set(rows.map((row: any) => row.status).filter(Boolean))].sort(), [rows])
  const visible = rows.filter((row: any) =>
    `${row.name} ${row.roll_no}`.toLowerCase().includes(filters.q.toLowerCase()) &&
    (!filters.semester || String(row.semester) === filters.semester) &&
    (!filters.status || row.status === filters.status) &&
    (filters.risk === 'all' || (filters.risk === 'at_risk' ? row.risk_codes?.length : !row.risk_codes?.length))
  )
  const atRisk = rows.filter((row: any) => row.risk_codes?.length).length
  const backlogs = rows.filter((row: any) => Number(row.backlogs || 0) > 0).length
  const attendanceRisk = rows.filter((row: any) => row.risk_codes?.includes('attendance')).length

  if (!data && loading) return <Spinner />
  if (!data) return <main className="hod-students-page"><Empty icon="!" text={error || 'Department student records could not be loaded.'} /></main>

  return <main className="hod-students-page fade-in">
    <header className="hod-students-heading">
      <div><p>Department student monitoring</p><h1>Department Students</h1><span>{data.department?.name || 'Your department'}{data.department?.code ? ` · ${data.department.code}` : ''} · Select a course and section to view active enrollments.</span></div>
      <button className="btn btn-out" onClick={() => void load(sectionId ? { course_id: courseId, section_id: sectionId } : courseId ? { course_id: courseId } : {})} type="button">Refresh data</button>
    </header>
    {error && <p className="hod-students-message" role="alert">{error}</p>}

    <section className="hod-students-path" aria-label="Course, section and student selection">
      <div className="hod-students-path-step"><span>1</span><div><b>Course</b><small>Shared department course</small></div><select value={courseId} onChange={event => void chooseCourse(event.target.value)} disabled={loading}><option value="">Select a course</option>{(data.courses || []).map((course: any) => <option key={course.id} value={course.id}>{course.code} — {course.title}</option>)}</select></div>
      <i aria-hidden="true">→</i>
      <div className="hod-students-path-step"><span>2</span><div><b>Section</b><small>Course-specific section</small></div><select value={sectionId} onChange={event => void chooseSection(event.target.value)} disabled={!courseId || loading}><option value="">Select a section</option>{(data.sections || []).map((section: any) => <option key={section.id} value={section.id}>Section {section.section}{section.term ? ` · ${section.term}` : ''}</option>)}</select></div>
      <i aria-hidden="true">→</i>
      <div className="hod-students-path-result"><span>3</span><div><b>Students</b><small>{sectionId ? `${data.student_count ?? rows.length} active enrollment${(data.student_count ?? rows.length) === 1 ? '' : 's'}` : 'Select a section to load the register'}</small></div></div>
    </section>

    {!courseId && <section className="hod-students-selection-empty"><Empty icon="○" text="Select a course to view its available sections." /></section>}
    {courseId && !sectionId && <section className="hod-students-selection-empty"><Empty icon="○" text="Select a section to view students." /></section>}

    {sectionId && <>
      <section className="hod-students-summary" aria-label="Selected section summary">
        <Stat value={data.student_count ?? rows.length} label="Enrolled Students" helper="Unique active enrollments" />
        <Stat value={backlogs} label="With Backlogs" helper="Published results only" tone="attention" />
        <Stat value={atRisk} label="At Risk" helper="Current derived signals" tone="risk" />
        <Stat value={attendanceRisk} label="Attendance Risk" helper="Below 75% where available" tone="risk" />
      </section>
      <section className="hod-students-register" aria-label="Selected section student register">
        <header><div><p>Student register</p><h2>{data.selection?.course_code} · Section {data.selection?.section}</h2></div><span>Membership is derived only from active Enrollment records for this course and section.</span></header>
        <div className="hod-students-section-filters">
          <label>Search<input value={filters.q} onChange={event => setFilters({ ...filters, q: event.target.value })} placeholder="Name or roll number" /></label>
          <label>Semester<select value={filters.semester} onChange={event => setFilters({ ...filters, semester: event.target.value })}><option value="">All semesters</option>{semesters.map((semester: any) => <option key={semester} value={semester}>Semester {semester}</option>)}</select></label>
          <label>Academic status<select value={filters.status} onChange={event => setFilters({ ...filters, status: event.target.value })}><option value="">All statuses</option>{statuses.map((status: any) => <option key={status} value={status}>{status}</option>)}</select></label>
          <label>Risk status<select value={filters.risk} onChange={event => setFilters({ ...filters, risk: event.target.value })}><option value="all">All students</option><option value="at_risk">At risk</option><option value="no_risk">No current risk</option></select></label>
          <button className="btn btn-out" type="button" onClick={() => setFilters({ q: '', semester: '', status: '', risk: 'all' })}>Clear filters</button>
        </div>
        {loading ? <Spinner /> : <div className="hod-students-list">{visible.map((row: any) => <StudentRow key={row.id} row={row} onView={() => setSelected(row)} />)}{!visible.length && <Empty icon="○" text={rows.length ? 'No enrolled students match the selected filters.' : 'No enrolled students found for this section.'} />}</div>}
      </section>
    </>}
    {selected && <StudentDetail row={selected} onClose={() => setSelected(null)} go={go} />}
  </main>
}

function Stat({ value, label, helper, tone = '' }: any) { return <article className={tone}><b>{value}</b><span>{label}</span><small>{helper}</small></article> }
function StudentRow({ row, onView }: any) { return <article className="hod-student-card"><div className="hod-student-main"><div className="hod-student-ident"><b>{row.roll_no}</b><h3>{row.name}</h3><span>{row.program}</span></div><Metric label="Semester / year" value={`Semester ${display(row.semester)} · Year ${display(row.study_year)}`} /><Metric label="Cohort / section" value={display(row.section)} /><Metric label="CGPA" value={display(row.cgpa)} /><Metric label="Attendance" value={row.attendance_pct == null ? 'No data' : `${row.attendance_pct}%`} /><Metric label="Backlogs" value={row.backlogs} /><RiskBadge row={row} /></div><div className="hod-student-actions"><button onClick={onView} type="button">View</button></div></article> }
function Metric({ label, value }: any) { return <div className="hod-student-metric"><span>{label}</span><b>{display(value)}</b></div> }
function RiskBadge({ row }: any) { return row.risk_codes?.length ? <span className="hod-student-status risk">{row.risk_codes.length === 1 ? `${row.risk_codes[0]} risk` : 'Multiple risks'}</span> : <span className="hod-student-status good">No current risk</span> }
function StudentDetail({ row, onClose, go }: any) { return <Modal className="modal-wide" title={`${row.name} · ${row.roll_no}`} onClose={onClose} footer={<><button className="btn btn-out" onClick={onClose} type="button">Close</button><button className="btn btn-out" onClick={() => go('hod_attendance')} type="button">Attendance Monitoring</button>{row.risk_codes?.length ? <button className="btn btn-crimson" onClick={() => go('hod_risk')} type="button">At-Risk Students</button> : null}</>}><section className="hod-student-detail"><div className="hod-student-detail-info"><span>Program</span><b>{row.program}</b><span>Study year / semester</span><b>Year {display(row.study_year)} / Semester {display(row.semester)}</b><span>Recorded cohort section</span><b>{display(row.section)}</b><span>CGPA</span><b>{display(row.cgpa)}</b><span>Attendance</span><b>{row.attendance_pct == null ? 'No calculable attendance' : `${row.attendance_pct}%`}</b><span>Published backlogs</span><b>{row.backlogs}</b></div><h3>Active enrollments</h3><div className="hod-student-enrollments">{row.enrollments?.map((item: any) => <article key={item.id}><b>{item.course_code}</b><span>{item.course_title}</span><small>Section {item.section}{item.term ? ` · ${item.term}` : ''}</small></article>)}</div><h3>Risk signals</h3>{row.risk_indicators?.length ? <div className="hod-student-risk-list">{row.risk_indicators.map((reason: string) => <span key={reason}>{reason}</span>)}</div> : <p className="hod-students-empty">No current risk indicators from the authoritative academic sources.</p>}</section></Modal> }
