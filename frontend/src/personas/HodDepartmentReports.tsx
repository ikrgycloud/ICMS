import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'
import './HodReportsAudit.css'

type Readiness = { numerator?: number; denominator?: number; percentage?: number | null }

export default function HodDepartmentReports({ go }: { go: (view: string) => void }) {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const load = async () => {
    setError('')
    try { setData(await api.hodReports()) }
    catch (reason: any) { setError(reason.message || 'Department reports could not be loaded.') }
  }
  useEffect(() => { void load() }, [])
  if (error && !data) return <Empty icon="!" text={error} />
  if (!data) return <Spinner />

  const kpis = data.kpis || {}, readiness = data.readiness || {}, operations = data.operations || {}, health = data.student_health || {}, reviews = data.reviews || {}
  const attendance = readiness.attendance_finalization as Readiness | undefined
  const attention = Object.fromEntries((data.attention || []).map((row: any) => [row.key, row.count]))
  const cards = [
    { title: 'Faculty & Workload', metric: kpis.active_faculty, label: 'Active Faculty', readiness: readiness.faculty_allocation, detail: 'Allocation coverage', view: 'hod_faculty' },
    { title: 'Teaching Allocations', metric: operations.teaching_active, label: 'Active Allocations', readiness: readiness.faculty_allocation, detail: 'Current section coverage', view: 'hod_allocations' },
    { title: 'Student Strength', metric: kpis.department_students, label: 'Department Students', detail: 'Active enrolled students', view: 'hod_students' },
    { title: 'Attendance', metric: operations.attendance_finalized, label: 'Finalized Sessions', readiness: attendance, detail: `${operations.attendance_pending ?? 0} pending`, extra: { label: 'Below threshold', value: health.attendance_risk }, view: 'hod_attendance' },
    { title: 'At-Risk Students', metric: health.at_risk, label: 'Students At Risk', detail: 'Derived current indicators', extra: { label: 'Multiple risks', value: health.multiple_risks }, view: 'hod_risk' },
    { title: 'Examination Coordination', metric: operations.assessments, label: 'Assessments', detail: 'Current department assessments', extra: { label: 'Awaiting HOD review', value: operations.awaiting_hod_review }, view: 'hod_exams' },
    { title: 'Department Requests', metric: kpis.pending_reviews, label: 'Pending Reviews', detail: 'Current reviewer workload', view: 'hod_reviews' },
  ]

  return <main className="hod-reports-page hod-reports-workspace fade-in">
    <header className="hod-courses-heading"><div><p>Department-scoped reporting</p><h1>Department Reports</h1><span>{scopeLine(data.department)}</span></div><button className="btn btn-out" onClick={load} type="button">Refresh data</button></header>
    {error && <p className="hod-allocation-message error">{error}</p>}
    <section className="hod-reports-kpis" aria-label="Department report summary"><Stat value={kpis.active_faculty} label="Faculty" helper="Active department faculty" /><Stat value={kpis.department_students} label="Students" helper="Active department students" /><Stat value={kpis.active_sections} label="Sections" helper="Current department sections" /><Stat value={percentage(attendance)} label="Attendance Finalization" helper={coverageLabel(attendance)} /><Stat value={health.at_risk} label="At-Risk Students" helper="Derived current indicators" tone="attention" /></section>
    <section className="hod-reports-grid" aria-label="Report categories">{cards.map(card => <article className="hod-report-card" key={card.title}><header><div><h2>{card.title}</h2><span>{card.detail}</span></div><button type="button" onClick={() => go(card.view)}>Open</button></header><div className="hod-report-card-body"><Metric label={card.label} value={card.metric} />{card.readiness && <CompactCoverage label={card.readiness === attendance ? 'Finalization' : 'Readiness'} value={card.readiness} />}{card.extra && <Metric label={card.extra.label} value={card.extra.value} subtle />}</div></article>)}</section>
    <section className="hod-report-panel"><header><div><p>Readiness</p><h2>Department Coverage</h2></div></header><div className="hod-report-coverage-grid"><Coverage label="Faculty Allocation" value={readiness.faculty_allocation} /><Coverage label="Timetable" value={readiness.timetable} /><Coverage label="Attendance Finalization" value={attendance} /><Coverage label="Course Coverage" value={readiness.course_coverage} /></div></section>
    <section className="hod-report-panel hod-report-bottom-grid"><div><p>Review workload</p><h2>My Reviews</h2><div className="hod-report-review-list"><Metric label="Marks Reviews" value={reviews.marks_reviews} /><Metric label="Attendance Corrections" value={reviews.attendance_corrections} /><Metric label="Faculty Leave" value={reviews.faculty_leave} /><Metric label="Mentoring Referrals" value={reviews.mentoring_referrals} /></div><button className="btn btn-out" onClick={() => go('hod_reviews')} type="button">Open My Reviews</button></div><div><p>Needs attention</p><h2>Operational Gaps</h2><div className="hod-report-review-list"><Metric label="Sections without faculty" value={attention.sections_without_faculty} /><Metric label="Sections missing timetable" value={attention.sections_missing_timetable} /><Metric label="Attendance sessions pending" value={attention.attendance_sessions_pending} /><Metric label="Marks reviews" value={attention.marks_reviews} /></div></div></section>
  </main>
}

function scopeLine(department: any) { return [department?.name || 'Department', department?.campus, department?.term].filter(Boolean).join(' · ') }
function percentage(value?: Readiness) { return value?.percentage == null ? '—' : `${value.percentage}%` }
function coverageLabel(value?: Readiness) { return value?.denominator ? `${value.numerator ?? 0} of ${value.denominator} finalized` : 'No eligible sessions' }
function Stat({ value, label, helper, tone }: { value: any; label: string; helper: string; tone?: string }) { return <article className={tone ? `is-${tone}` : ''}><b>{value ?? '—'}</b><span>{label}</span><small>{helper}</small></article> }
function Metric({ label, value, subtle = false }: { label: string; value: any; subtle?: boolean }) { return <div className={`hod-report-metric${subtle ? ' is-subtle' : ''}`}><span>{label}</span><b>{value ?? '—'}</b></div> }
function CompactCoverage({ label, value }: { label: string; value: Readiness }) { return <div className="hod-report-inline-coverage"><span>{label}</span><b>{percentage(value)}</b><i><span style={{ width: `${Math.max(0, Math.min(100, value.percentage || 0))}%` }} /></i></div> }
function Coverage({ label, value }: { label: string; value?: Readiness }) { return <article className="hod-report-coverage"><div><span>{label}</span><b>{percentage(value)}</b></div><small>{coverageLabel(value)}</small><i><span style={{ width: `${Math.max(0, Math.min(100, value?.percentage || 0))}%` }} /></i></article> }
