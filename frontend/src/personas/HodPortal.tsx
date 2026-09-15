import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner } from '../modules/kit'

function LegacyHodDashboard({ go }: { go: (view: string) => void }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.hodDashboard().then(setData).catch((error: any) => setData({ error: error.message || true })) }, [])
  if (!data) return <Spinner />
  if (data.error) return <Empty icon="!" text={data.error} />
  const department = data.department || {}, faculty = data.faculty || {}, teaching = data.teaching || {}
  const students = data.students || {}, reviews = data.reviews || {}, alerts = data.alerts || {}
  const cards = [
    ['Faculty', faculty.active_count], ['Active Courses', teaching.active_courses], ['Running Sections', teaching.active_sections],
    ['Department Students', students.total_students], ['Faculty Overloaded', faculty.overloaded_count == null ? 'Not configured' : faculty.overloaded_count],
    ['At-Risk Students', students.at_risk_count],
    ['Pending Reviews', reviews.total_pending], ['Attendance Pending', teaching.attendance_pending_count],
  ]
  return <main className="prof-overview fade-in">
    <div className="prof-heading"><div><h1>Head of Department</h1><p>{department.name} {department.code ? `(${department.code})` : ''}{department.campus ? ` · ${department.campus}` : ''}</p></div></div>
    <section className="prof-stat-grid">{cards.map(([label, value]) => <article className="prof-stat" key={String(label)}><span>H</span><div><b>{value ?? '—'}</b><small>{label}</small></div></article>)}</section>
    <section className="prof-layout"><div className="prof-left">
      <article className="prof-card"><header><h2>Faculty Workload Summary</h2></header><div className="prof-card-body"><p><b>{faculty.allocated_count || 0}</b> allocated · <b>{faculty.unallocated_count || 0}</b> unallocated · <b>{faculty.total_active_teaching_allocations || 0}</b> active allocations</p></div></article>
      <article className="prof-card"><header><h2>Teaching Delivery</h2></header><div className="prof-card-body"><p>Sessions today: <b>{teaching.sessions_today || 0}</b> · Attendance finalized: <b>{teaching.attendance_finalized_count || 0}</b> · Pending: <b>{teaching.attendance_pending_count || 0}</b></p></div></article>
      <article className="prof-card"><header><h2>Student Risk Snapshot</h2></header><div className="prof-card-body"><p>Attendance: <b>{students.attendance_risk_count || 0}</b> · Academic: <b>{students.academic_risk_count || 0}</b> · Backlog: <b>{students.backlog_risk_count || 0}</b> · Referrals: <b>{students.mentoring_referral_count || 0}</b></p></div></article>
    </div><div className="prof-right">
      <article className="prof-card"><header><h2>My Reviews</h2><button onClick={() => go('hod_reviews')} type="button">Open inbox</button></header><div className="prof-table-wrap"><table className="prof-table"><tbody>{[['Marks', reviews.marks_pending, 'marks'], ['Attendance Corrections', reviews.attendance_corrections_pending, 'attendance_corrections'], ['Faculty Leave', reviews.leave_pending, 'faculty_leave'], ['Mentoring Referrals', reviews.mentoring_referrals_pending, 'mentoring_referrals']].map(([label, value, kind]) => <tr key={String(kind)}><td>{label}</td><td><button onClick={() => go(`hod_reviews_${kind}`)} type="button">{value || 0}</button></td></tr>)}</tbody></table></div></article>
      <article className="prof-card"><header><h2>Academic Alerts</h2></header><div className="prof-card-body"><p>Faculty overload: <b>{alerts.faculty_overload_count == null ? 'Not configured' : alerts.faculty_overload_count}</b></p><p>No timetable conflicts detected or available.</p></div></article>
    </div></section>
  </main>
}

export function HodDashboard({ go }: { go: (view: string) => void }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.hodDashboard().then(setData).catch((error: any) => setData({ error: error.message || true })) }, [])
  if (!data) return <Spinner />
  if (data.error) return <Empty icon="!" text={data.error} />
  const department = data.department || {}, faculty = data.faculty || {}, teaching = data.teaching || {}
  const students = data.students || {}, reviews = data.reviews || {}, exams = data.exams || {}
  const readiness = data.readiness || {}, allocations = data.allocations || {}
  const primaryKpis = [
    { label: 'Active Faculty', value: faculty.active_count || 0, view: 'hod_faculty' },
    { label: 'Department Students', value: students.total_students || 0, view: 'hod_students' },
    { label: 'Active Sections', value: teaching.active_sections || 0, view: 'hod_sections' },
    { label: 'At-Risk Students', value: students.at_risk_count || 0, view: 'hod_risk' },
  ]
  const operationalKpis = [
    { label: 'Pending Reviews', value: reviews.total_pending || 0, view: 'hod_reviews' },
    { label: 'Attendance Pending', value: teaching.attendance_pending_count || 0, view: 'hod_attendance' },
    { label: 'Sections Without Faculty', value: readiness.sections_without_faculty || 0, view: 'hod_allocations' },
    { label: 'Upcoming Exams', value: exams.upcoming_exam_count || 0, view: 'hod_exams' },
  ]
  const reviewRows = [['Marks', reviews.marks_pending || 0, 'marks'], ['Attendance Corrections', reviews.attendance_corrections_pending || 0, 'attendance_corrections'], ['Faculty Leave', reviews.leave_pending || 0, 'faculty_leave'], ['Mentoring Referrals', reviews.mentoring_referrals_pending || 0, 'mentoring_referrals']]
  const attention = [
    ...(data.attention || []),
    ...(teaching.attendance_pending_count ? [{ label: `${teaching.attendance_pending_count} attendance record${teaching.attendance_pending_count === 1 ? '' : 's'} awaiting finalization`, view: 'hod_attendance' }] : []),
    ...(students.at_risk_count ? [{ label: `${students.at_risk_count} student${students.at_risk_count === 1 ? '' : 's'} currently at risk`, view: 'hod_risk' }] : []),
    ...(reviews.marks_pending ? [{ label: `${reviews.marks_pending} marks review${reviews.marks_pending === 1 ? '' : 's'} awaiting HOD`, view: 'hod_reviews_marks' }] : []),
  ]
  const readinessRows = [
    { label: 'Faculty Allocation Coverage', numerator: readiness.sections_with_faculty || 0, denominator: readiness.sections || 0, view: 'hod_allocations' },
    { label: 'Timetable Coverage', numerator: readiness.sections_with_timetable || 0, denominator: readiness.sections || 0, view: 'hod_sections' },
    { label: 'Attendance Finalization', numerator: teaching.attendance_finalized_count || 0, denominator: teaching.sessions_today || 0, view: 'hod_attendance' },
    { label: 'Course Coverage', numerator: readiness.courses_with_sections || 0, denominator: readiness.courses || 0, view: 'hod_courses' },
  ]
  const Kpi = ({ item, tone }: { item: any, tone: string }) => item.view
    ? <button className={`hod-kpi ${tone} hod-kpi-action`} onClick={() => go(item.view)} type="button"><b>{item.value}</b><span>{item.label}</span><i>View details</i></button>
    : <article className={`hod-kpi ${tone}`}><b>{item.value}</b><span>{item.label}</span></article>
  return <main className="hod-dashboard fade-in">
    <header className="hod-dashboard-heading"><div><p>Department command center</p><h1>Department Overview</h1><span>{department.name}{department.code ? ` (${department.code})` : ''}{department.campus ? ` · ${department.campus}` : ''}</span></div></header>
    <section className="hod-kpi-grid hod-kpi-primary">{primaryKpis.map(item => <Kpi item={item} tone="primary" key={item.label} />)}</section>
    <section className="hod-kpi-grid hod-kpi-secondary">{operationalKpis.map(item => <Kpi item={item} tone="secondary" key={item.label} />)}</section>
    <section className="hod-command-grid">
      <article className="hod-card hod-readiness"><header><h2>Department Readiness</h2><button onClick={() => go('hod_planning')} type="button">Open planning</button></header><div>{readinessRows.map(row => <button key={row.label} onClick={() => go(row.view)} type="button"><span>{row.label}</span><b>{row.denominator ? `${row.numerator} / ${row.denominator}` : '—'}</b><i><em style={{ width: `${row.denominator ? Math.min(100, row.numerator * 100 / row.denominator) : 0}%` }} /></i></button>)}</div></article>
      <article className="hod-card"><header><h2>Today’s Department Classes</h2><button onClick={() => go('hod_sections')} type="button">View timetable</button></header><div className="hod-today-summary"><b>{teaching.sessions_today || 0}</b><span>{teaching.sessions_today ? 'classes scheduled today' : 'No department classes scheduled today.'}</span><div><Metric label="Attendance Pending" value={teaching.attendance_pending_count || 0} /><Metric label="Attendance Finalized" value={teaching.attendance_finalized_count || 0} /></div></div></article>
      <article className="hod-card"><header><h2>My Reviews</h2><button onClick={() => go('hod_reviews')} type="button">Open inbox</button></header><div className="hod-review-list">{reviewRows.map(([label, value, kind]) => <button key={String(kind)} onClick={() => go(`hod_reviews_${kind}`)} type="button"><span>{label}</span><b>{value}</b></button>)}</div></article>
      <article className="hod-card"><header><h2>Academic Operations</h2><button onClick={() => go('hod_allocations')} type="button">Open allocations</button></header><div className="hod-mini-grid hod-three-metrics"><Metric label="Active Allocations" value={allocations.active_count || 0} /><Metric label="Pending Allocations" value={allocations.pending_count || 0} /><Metric label="Attendance Pending" value={teaching.attendance_pending_count || 0} /><Metric label="Attendance Finalized" value={teaching.attendance_finalized_count || 0} /><Metric label="Upcoming Exams" value={exams.upcoming_exam_count || 0} /><Metric label="Marks Awaiting HOD" value={exams.marks_awaiting_hod || 0} /></div></article>
      <article className="hod-card"><header><h2>Student Health</h2><button onClick={() => go('hod_risk')} type="button">View at-risk students</button></header><div className="hod-mini-grid hod-three-metrics"><Metric label="At Risk" value={students.at_risk_count || 0} /><Metric label="Attendance Risk" value={students.attendance_risk_count || 0} /><Metric label="Academic Risk" value={students.academic_risk_count || 0} /><Metric label="Backlog Risk" value={students.backlog_risk_count || 0} /><Metric label="Multiple Risk Reasons" value={students.multi_risk_count || 0} /></div></article>
      <article className="hod-card"><header><h2>Needs Attention</h2><button onClick={() => go('hod_planning')} type="button">Open planning</button></header><div className="hod-alerts"><div>{attention.length ? attention.slice(0, 5).map((item: any, index: number) => <button key={`${item.kind || item.view}-${index}`} onClick={() => go(item.view)} type="button"><span>•</span>{item.label}</button>) : <p>No current department attention items.</p>}</div></div></article>
    </section>
    <section className="hod-bottom-grid">
      <article className="hod-card"><header><h2>My Requests</h2><button onClick={() => go('hod_requests')} type="button">View requests</button></header><div className="hod-request-list">{(data.my_requests || []).map((request: any) => <button key={request.id} onClick={() => go('hod_requests')} type="button"><span>{request.label}</span><small>{request.stage || request.status || 'Recorded'}</small></button>)}{!(data.my_requests || []).length && <p>No HOD-initiated requests to track.</p>}</div></article>
      <article className="hod-card"><header><h2>Recent Activity</h2><button onClick={() => go('hod_department_audit')} type="button">Open audit</button></header><div className="hod-request-list">{(data.recent_activity || []).map((event: any) => <button key={event.id} onClick={() => go('hod_department_audit')} type="button"><span>{event.resource} · {event.action.replaceAll('.', ' ')}</span><small>{event.timestamp ? new Date(event.timestamp).toLocaleDateString() : 'Recorded'}</small></button>)}{!(data.recent_activity || []).length && <p>No safe department activity is available.</p>}</div></article>
    </section>
  </main>
}

function Metric({ label, value }: { label: string, value: number }) {
  return <div className="hod-mini-metric"><b>{value}</b><span>{label}</span></div>
}

const tabLabels: Record<string, string> = { all: 'All', marks: 'Marks', attendance_corrections: 'Attendance Corrections', faculty_leave: 'Faculty Leave', mentoring_referrals: 'Mentoring Referrals' }

export function HodReviews({ initialKind = 'all' }: { initialKind?: string }) {
  const [kind, setKind] = useState(initialKind), [data, setData] = useState<any>(null), [error, setError] = useState(''), [notice, setNotice] = useState(''), [saving, setSaving] = useState(false)
  const load = () => { setData(null); setError(''); api.hodReviews(kind).then(setData).catch((err: any) => setError(err.message || 'Could not load reviews')) }
  useEffect(() => setKind(initialKind), [initialKind])
  useEffect(load, [kind])
  const rows = useMemo(() => data?.reviews || [], [data])
  const decide = async (row: any, action: string) => {
    if (action === 'approve' && !window.confirm('Approve this item using the existing workflow route?')) return
    const comment = action === 'approve' ? '' : window.prompt(`Reason for ${action}:`) || ''
    if (action !== 'approve' && !comment.trim()) return
    setSaving(true); setError(''); setNotice('')
    try {
      if (row.kind === 'marks') await api.decideMarksSubmission(row.id, { action, comment })
      if (row.kind === 'attendance_correction') await api.decideAttendanceCorrection(row.id, { action, comment })
      if (row.kind === 'faculty_leave') await api.decideFacultyLeave(row.id, { action, comment })
      setNotice('Review decision submitted. Pending counts have been refreshed.'); load()
    } catch (err: any) { setError(err.message || 'Could not submit the review decision. The item may have changed; refresh and try again.') } finally { setSaving(false) }
  }
  if (error) return <Empty icon="!" text={error} />
  return <main className="prof-overview fade-in"><div className="prof-heading"><div><h1>My Reviews</h1><p>Only items currently routed to you are listed. Completed, returned, and other reviewers’ stages are excluded.</p></div></div>
    <div className="faculty-tabs">{Object.entries(tabLabels).map(([key, label]) => <button className={kind === key ? 'active' : ''} onClick={() => setKind(key)} key={key} type="button">{label}{data?.counts && key !== 'all' ? ` (${data.counts[`${key === 'faculty_leave' ? 'leave' : key}_pending`] ?? data.counts[key] ?? 0})` : ''}</button>)}</div>{notice && <p className="hod-allocation-message">{notice}</p>}
    {!data ? <Spinner /> : <section className="prof-card"><div className="prof-table-wrap"><table className="prof-table"><thead><tr><th>Type</th><th>Item</th><th>Current stage</th><th>Status</th><th>Action</th></tr></thead><tbody>{rows.map((row: any) => <ReviewRow key={`${row.kind}:${row.id}`} row={row} onDecide={decide} saving={saving} />)}{!rows.length && <tr><td colSpan={5}>No reviews currently need your action.</td></tr>}</tbody></table></div></section>}
  </main>
}

export function HodFacultyWorkload({ go }: { go: (view: string) => void }) {
  const [data, setData] = useState<any>(null), [allocations, setAllocations] = useState<any[]>([]), [error, setError] = useState('')
  const [query, setQuery] = useState(''), [designation, setDesignation] = useState(''), [allocationStatus, setAllocationStatus] = useState('all'), [course, setCourse] = useState(''), [section, setSection] = useState(''), [selected, setSelected] = useState<any>(null)
  const load = () => {
    setError('')
    Promise.all([api.hodFacultyWorkload(), api.teachingAllocations()]).then(([workload, allocationData]) => { setData(workload); setAllocations(allocationData.allocations || []) }).catch((err: any) => setError(err.message || 'Faculty workload could not be loaded.'))
  }
  useEffect(load, [])
  if (error) return <Empty icon="!" text={error} />
  if (!data) return <Spinner />
  const faculty = data.faculty || []
  const today = new Date().toISOString().slice(0, 10)
  const activeAllocations = allocations.filter(row => row.status === 'active' && (!row.effective_from || row.effective_from <= today) && (!row.effective_to || row.effective_to >= today))
  const designations = [...new Set(faculty.map((row: any) => row.designation).filter(Boolean))].sort()
  const courses = [...new Map(activeAllocations.map(row => [row.course_id, `${row.course_code}${row.course_title ? ` — ${row.course_title}` : ''}`])).entries()]
  const sections = [...new Map(activeAllocations.map(row => [row.section_id, `${row.course_code} · ${row.section}`])).entries()]
  const activeFor = (facultyId: string) => activeAllocations.filter(row => row.faculty_id === facultyId)
  const rows = faculty.filter((row: any) => {
    const search = `${row.name} ${row.employee_id}`.toLowerCase().includes(query.trim().toLowerCase())
    const assigned = activeFor(row.id)
    return search && (!designation || row.designation === designation) && (allocationStatus === 'all' || (allocationStatus === 'allocated' ? row.active_allocations > 0 : row.active_allocations === 0)) && (!course || assigned.some(item => item.course_id === course)) && (!section || assigned.some(item => item.section_id === section))
  })
  const highestWorkload = Math.max(1, ...rows.map((row: any) => Number(row.workload_units) || 0))
  const activeFaculty = faculty.filter((row: any) => row.active_allocations > 0).length
  const hasFilters = Boolean(query || designation || allocationStatus !== 'all' || course || section)
  const assignments = selected ? allocations.filter(row => row.faculty_id === selected.id) : []
  const clearFilters = () => { setQuery(''); setDesignation(''); setAllocationStatus('all'); setCourse(''); setSection('') }
  return <main className="hod-faculty-page fade-in">
    <header className="hod-faculty-heading"><div><p>Department academic workload</p><h1>Faculty &amp; Workload</h1><span>{data.department?.name || 'Department'} · Workload Units reflect active teaching allocations.</span></div><button className="btn btn-crimson" onClick={() => go('hod_allocations')} type="button">Manage Teaching Allocations</button></header>
    <section className="hod-faculty-summary"><SummaryCard label="Total Faculty" value={faculty.length} /><SummaryCard label="Allocated Faculty" value={activeFaculty} /><SummaryCard label="Unallocated Faculty" value={Math.max(0, faculty.length - activeFaculty)} /><SummaryCard label="Active Teaching Allocations" value={faculty.reduce((total: number, row: any) => total + (row.active_allocations || 0), 0)} /></section>
    <p className="hod-faculty-summary-note">Department totals · filters apply to the faculty table below.</p>
    <section className="hod-faculty-filters">
      <label>Search faculty or employee ID<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Name or employee ID" /></label>
      <label>Designation<select value={designation} onChange={event => setDesignation(event.target.value)}><option value="">All designations</option>{designations.map(value => <option value={value} key={value}>{value}</option>)}</select></label>
      <label>Allocation status<select value={allocationStatus} onChange={event => setAllocationStatus(event.target.value)}><option value="all">All faculty</option><option value="allocated">Allocated</option><option value="unallocated">Unallocated</option></select></label>
      <label>Course<select value={course} onChange={event => setCourse(event.target.value)}><option value="">All active courses</option>{courses.map(([id, label]) => <option value={id} key={id}>{label}</option>)}</select></label>
      <label>Section<select value={section} onChange={event => setSection(event.target.value)}><option value="">All active sections</option>{sections.map(([id, label]) => <option value={id} key={id}>{label}</option>)}</select></label>
      {hasFilters && <button className="btn btn-out" onClick={clearFilters} type="button">Clear filters</button>}
    </section>
    <article className="hod-faculty-table-card"><header><div><h2>Faculty Workload</h2><p>{hasFilters ? `${rows.length} faculty match the selected filters.` : `${faculty.length} faculty in this department.`}</p></div><span>Comparative workload display</span></header><div className="hod-faculty-table-wrap"><table><thead><tr><th>Faculty</th><th>Designation</th><th>Active Courses</th><th>Active Sections</th><th>Active Allocations</th><th>Workload Units</th><th>Mentoring Load</th><th>Actions</th></tr></thead><tbody>{rows.map((row: any) => <tr key={row.id}><td><b>{row.name}</b><small>{row.employee_id || '—'}</small></td><td>{row.designation || '—'}</td><td>{row.active_courses || 0}</td><td>{row.active_sections || 0}</td><td>{row.active_allocations || 0}</td><td><div className="hod-workload-cell"><b>{row.workload_units ?? '—'}</b><i><span style={{ width: `${Math.min(100, 100 * (Number(row.workload_units) || 0) / highestWorkload)}%` }} /></i></div></td><td>{row.mentoring_load || 0}</td><td><div className="hod-faculty-actions"><button onClick={() => setSelected(row)} type="button">View details</button><button onClick={() => go('hod_allocations')} type="button">Allocate</button></div></td></tr>)}{!rows.length && <tr><td colSpan={8}>{faculty.length ? 'No faculty match the selected filters.' : 'No faculty found in this department.'}</td></tr>}</tbody></table></div></article>
    {selected && <Modal className="modal-wide" title={`Faculty Workload — ${selected.name}`} onClose={() => setSelected(null)} footer={<button className="btn btn-out" onClick={() => setSelected(null)} type="button">Close</button>}><section className="hod-faculty-detail"><div className="hod-faculty-detail-identity"><span>{selected.employee_id || '—'}</span><h3>{selected.name}</h3><p>{selected.designation || '—'}</p></div><div className="hod-faculty-detail-metrics"><SummaryCard label="Active Courses" value={selected.active_courses || 0} /><SummaryCard label="Active Sections" value={selected.active_sections || 0} /><SummaryCard label="Active Allocations" value={selected.active_allocations || 0} /><SummaryCard label="Workload Units" value={selected.workload_units ?? '—'} /><SummaryCard label="Mentoring Load" value={selected.mentoring_load || 0} /></div><h3>Teaching Allocations</h3>{assignments.length ? <div className="hod-assignment-list">{assignments.map((row: any) => <div key={row.id}><b>{row.course_code} · {row.course_title || 'Course'}</b><span>Section {row.section || '—'} · {row.status || '—'}</span><small>{row.effective_from || '—'} to {row.effective_to || 'Ongoing'}</small></div>)}</div> : <p className="hod-detail-empty">No teaching allocations are recorded for this faculty member.</p>}{selected.functional_assignments?.length ? <><h3>Functional Assignments</h3><p className="hod-functional-list">{selected.functional_assignments.join(' · ')}</p></> : null}</section></Modal>}
  </main>
}

function SummaryCard({ label, value }: { label: string, value: string | number }) {
  return <article className="hod-faculty-summary-card"><b>{value}</b><span>{label}</span></article>
}

export function HodOperations({ kind }: { kind: 'faculty' | 'courses' | 'sections' | 'students' | 'attendance' | 'risk' | 'exams' | 'reports' | 'profile' | 'digital_id' }) {
  const [data, setData] = useState<any>(null), [query, setQuery] = useState(''), [error, setError] = useState('')
  const titles: any = { faculty: 'Faculty & Workload', courses: 'Programs & Courses', sections: 'Sections & Timetable', students: 'Department Students', attendance: 'Attendance Monitoring', risk: 'At-Risk Students', exams: 'Examination Coordination', reports: 'Department Reports', profile: 'My Profile', digital_id: 'Digital ID' }
  const load = () => {
    setData(null); setError('')
    const request = kind === 'faculty' ? api.hodFacultyWorkload(query) : kind === 'courses' ? api.hodProgramsCourses(query) : kind === 'students' ? api.hodStudents(query) : kind === 'risk' ? api.hodAtRiskStudents(query) : kind === 'sections' ? api.hodSections() : kind === 'attendance' ? api.hodAttendanceMonitoring() : kind === 'exams' ? api.hodExaminations() : kind === 'reports' ? api.hodReports() : kind === 'profile' ? api.hodProfile() : api.hodDigitalId()
    request.then(setData).catch((err: any) => setError(err.message || 'Could not load department operations'))
  }
  useEffect(load, [kind])
  if (error) return <Empty icon="!" text={error} />
  if (!data) return <Spinner />
  const rawRows = data.faculty || data.allocations || data.courses || data.students || data.sections || data.exams || (data.profile ? [data.profile] : data.digital_id ? [data.digital_id] : [])
  const rows = Array.isArray(rawRows) ? rawRows : kind === 'reports' ? [{ ...data.faculty, ...data.teaching, ...data.students, pending_reviews: data.reviews?.total_pending, upcoming_exams: data.exams?.upcoming_exam_count }] : []
  const columns = rows.length ? Object.keys(rows[0]).filter(key => !['id', 'course_id', 'program_id', 'section_id', 'functional_assignments', 'risk_indicators'].includes(key)) : []
  return <main className="prof-overview fade-in"><div className="prof-heading"><div><h1>{titles[kind]}</h1><p>{data.department?.name || 'Department'} · department-scoped monitoring only.</p></div></div>
    {(kind === 'faculty' || kind === 'courses' || kind === 'students' || kind === 'risk') && <div className="faculty-tabs"><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search within department" /><button className="btn btn-out" onClick={load} type="button">Search</button></div>}
    {kind === 'faculty' && <p className="hint">{data.workload_status_deferred}</p>}
    <section className="prof-card"><div className="prof-table-wrap"><table className="prof-table"><thead><tr>{columns.map(column => <th key={column}>{column.replace(/_/g, ' ')}</th>)}</tr></thead><tbody>{rows.map((row: any) => <tr key={row.id || row.section_id}>{columns.map(column => <td key={column}>{Array.isArray(row[column]) ? row[column].join(', ') || 'Not available' : row[column] == null || row[column] === '' ? 'Not available' : String(row[column])}</td>)}</tr>)}{!rows.length && <tr><td colSpan={Math.max(columns.length, 1)}>No department records match this view.</td></tr>}</tbody></table></div></section>
  </main>
}

function ReviewRow({ row, onDecide, saving }: { row: any, onDecide: (row: any, action: string) => void, saving: boolean }) {
  const item = row.payload || {}
  const label = row.kind === 'marks' ? `${item.course_code || ''} · ${item.assessment || 'Assessment'}`
    : row.kind === 'attendance_correction' ? `${item.student || 'Student'} · ${item.course_code || ''}`
    : row.kind === 'faculty_leave' ? `${item.staff || 'Faculty'} · ${item.kind || 'Leave'}`
    : `${item.student?.name || 'Student'} · ${item.category || 'Mentoring referral'}`
  const stage = item.current_stage ? `Stage ${item.current_stage}` : 'Referral review'
  const actionable = ['marks', 'attendance_correction', 'faculty_leave'].includes(row.kind)
  return <tr><td>{tabLabels[row.kind] || row.kind}</td><td><b>{label}</b></td><td>{stage}</td><td>{item.status || 'referred'}</td><td>{actionable ? <><button className="btn btn-out" disabled={saving} onClick={() => onDecide(row, 'approve')} type="button">Approve</button> <button className="btn btn-out" disabled={saving} onClick={() => onDecide(row, 'return')} type="button">Return</button> <button className="btn btn-out" disabled={saving} onClick={() => onDecide(row, 'reject')} type="button">Reject</button></> : 'View only'}</td></tr>
}

export function HodDeferredPage({ label }: { label: string }) {
  const reasons: Record<string, string> = {
    schedule: 'Timetable creation remains owned by the Academic Coordinator; this HOD portal will not use an institution-wide timetable substitute.',
    messages: 'No department-scoped recipient and message workflow has been approved yet.',
    marks: 'Use My Reviews for marks that are currently routed to this HOD; a separate duplicate review page is intentionally unavailable.',
    corrections: 'Use My Reviews for attendance corrections that are currently routed to this HOD; a separate duplicate review page is intentionally unavailable.',
    leave: 'Use My Reviews for faculty leave currently routed to this HOD; HOD self-leave is not available without an approved requester workflow.',
    curriculum: 'No department-scoped curriculum-request workflow is configured.',
    requirements: 'No approved department requirements workflow is configured.',
    research: 'Research ownership and approval routing have not been defined for an HOD overview.',
    audit: 'Department ownership cannot yet be resolved safely for every audit entity, so the global audit view remains blocked.',
    announcements: 'Department-scoped announcement delivery has not been enabled in this HOD portal.',
    self_leave: 'HOD self-leave is unavailable because no valid requester workflow has been configured.',
    payroll: 'Payroll is a protected HR function and is not available to HOD.',
    directory: 'A department-scoped directory endpoint has not been approved for this portal.',
  }
  return <Empty icon="…" text={reasons[label] || `${label} is unavailable. This portal does not route to an institution-wide substitute.`} />
}
