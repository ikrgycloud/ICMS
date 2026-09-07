import { useEffect, useMemo, useState } from 'react'
import {
  HiOutlineAcademicCap,
  HiOutlineArrowPath,
  HiOutlineBuildingLibrary,
  HiOutlineCalendarDays,
  HiOutlineChartBarSquare,
  HiOutlineClipboardDocumentList,
  HiOutlineDocumentText,
  HiOutlineExclamationTriangle,
  HiOutlineFolderOpen,
  HiOutlineUserGroup,
  HiOutlineUsers,
} from 'react-icons/hi2'
import { api } from '../api'
import { Empty, Spinner } from './kit'

type Filters = { academic_year: string; semester: string; school_id: string; dept_id: string; program_id: string }
// Start on the complete current scope.  The API owns the available academic
// periods; an arbitrary historical period can otherwise render an empty
// dashboard even though live records exist.
const initialFilters: Filters = { academic_year: '', semester: '', school_id: '', dept_id: '', program_id: '' }

const colorMap: Record<string, string> = {
  Approved: '#3cb179',
  'In Review': '#4687d7',
  Returned: '#f0b649',
  Overdue: '#e85757',
  Completed: '#3cb179',
  'In Progress': '#f0b649',
  Pending: '#8aa8d1',
}

export default function DeanAcademicsDashboard({ go }: { go: (view: string) => void }) {
  const [filters, setFilters] = useState<Filters>(initialFilters)
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  async function load(next = filters) {
    setLoading(true)
    setError('')
    try {
      const result = await api.deanDashboard(next)
      setData(result)
      setLastUpdated(new Date())
    } catch (e: any) {
      setError(e.message || 'Unable to load academic dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(initialFilters) }, [])

  const kpis = useMemo(() => [
    ['Programs', data?.kpis?.programs ?? 0, 'curriculum'],
    ['Departments', data?.kpis?.departments ?? 0, 'analytics'],
    ['Courses', data?.kpis?.courses ?? 0, 'courses_subjects'],
    ['Faculty', data?.kpis?.faculty ?? 0, 'academics'],
    ['Curriculum Reviews', data?.kpis?.curriculum_reviews ?? 0, 'curriculum'],
    ['Timetable Conflicts', data?.kpis?.timetable_conflicts ?? 0, 'academics'],
    ['Academic Actions', data?.kpis?.academic_actions ?? 0, 'dean_risk'],
    ['Needs My Decision', data?.kpis?.needs_my_decision ?? 0, 'decision_inbox'],
  ], [data])

  const update = (key: keyof Filters, value: string) => {
    const next = { ...filters, [key]: value, ...(key === 'dept_id' ? { program_id: '' } : {}) }
    setFilters(next)
    load(next)
  }

  const departmentPerformance = data?.department_performance || []
  const maxDepartmentPass = Math.max(1, ...departmentPerformance.map((row: any) => Number(row.pass_rate || 0)))
  const trendData = data?.result_trends || []
  const curriculumEntries = Object.entries(data?.curriculum_status || {})
  const curriculumTotal = curriculumEntries.reduce((sum: number, [, count]) => sum + Number(count || 0), 0)
  const readiness = data?.timetable_readiness || { completed: 0, in_progress: 0, pending: 0, conflicts: 0 }
  const avgWorkload = data?.faculty_workload?.avg_load ?? 0
  const exceptionItems = [
    { label: 'Pending decisions', count: Number(data?.kpis?.needs_my_decision || 0), target: 'decision_inbox', tone: 'warning' },
    { label: 'Timetable conflicts', count: Number(data?.kpis?.timetable_conflicts || 0), target: 'dean_timetable', tone: 'danger' },
    { label: 'At-risk students', count: Number(data?.health?.at_risk_students || 0), target: 'analytics', tone: 'danger' },
    { label: 'Overloaded faculty', count: Number(data?.faculty_workload?.overloaded || 0), target: 'dean_allocation', tone: 'warning' },
  ]

  if (!data && loading) return <Spinner />
  if (!data) return <div className="card card-pad calendar-banner warn">{error || 'Unable to load academic dashboard'}</div>

  return <div className="fade-in dean-dashboard">
    <div className="dean-overview-head">
      <div>
        <span className="dean-overview-eyebrow">Dean Academics</span>
        <h1>Academic Overview</h1>
        <p>Monitor performance, workload, readiness, and decisions across your academic scope.</p>
      </div>
      <div className="dean-live-status" aria-live="polite">
        <span className={`dean-live-dot ${loading ? 'is-loading' : ''}`} />
        <span>{loading ? 'Updating data' : lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Live data'}</span>
      </div>
    </div>
    <div className="dean-filters">
      <div className="dean-filter"><label>Academic Year</label><select value={filters.academic_year} onChange={e => update('academic_year', e.target.value)}><option value="">All years</option>{(data.options?.academic_years || []).map((year: string) => <option key={year} value={year}>{year}</option>)}</select></div>
      <div className="dean-filter"><label>Semester</label><select value={filters.semester} onChange={e => update('semester', e.target.value)}><option value="">All semesters</option>{(data.options?.semesters || []).map((semester: number) => <option key={semester} value={semester}>Semester {semester}</option>)}</select></div>
      <div className="dean-filter"><label>School / Faculty</label><select value={filters.school_id} onChange={e => update('school_id', e.target.value)}><option value="">All</option>{(data.options?.schools || []).map((row: any) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></div>
      <div className="dean-filter"><label>Department</label><select value={filters.dept_id} onChange={e => update('dept_id', e.target.value)}><option value="">All</option>{(data.options?.departments || []).map((row: any) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></div>
      <div className="dean-filter"><label>Program</label><select value={filters.program_id} onChange={e => update('program_id', e.target.value)}><option value="">All</option>{(data.options?.programs || []).map((row: any) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></div>
      <button className={`dean-refresh ${loading ? 'is-loading' : ''}`} onClick={() => load()} type="button" aria-label="Refresh dashboard" title="Refresh dashboard"><HiOutlineArrowPath /></button>
    </div>

    {error && <div className="calendar-banner warn" style={{ marginTop: 14 }}>{error}</div>}

    <div className="dean-kpi-grid">
      {kpis.map(([label, value, target], index) => (
        <button key={label} className={`dean-kpi ${index === kpis.length - 1 ? 'needs-decision' : ''}`} onClick={() => go(String(target))} type="button" aria-label={`${label}: ${value}`}>
          <div className="dean-kpi-icon"><DeanKpiIcon label={label} /></div>
          <div className="dean-kpi-label">{label}</div>
          <div className="dean-kpi-value">{value}</div>
        </button>
      ))}
    </div>

    <div className="dean-exception-strip" aria-label="Academic exceptions requiring attention">
      <div className="dean-exception-intro"><span>Attention required</span><small>Priority items in your scope</small></div>
      {exceptionItems.map((item) => (
        <button key={item.label} className={`dean-exception-item ${item.tone}`} onClick={() => go(item.target)} type="button" aria-label={`${item.label}: ${item.count}`}>
          <span>{item.label}</span><strong>{item.count}</strong>
        </button>
      ))}
    </div>

    <div className="dean-main-grid">
      <section className="dean-panel">
        <div className="dean-panel-head"><h3>Academic Health (Overall)</h3></div>
        <div className="dean-health-grid">
          <MetricTile label="Avg CGPA" value={Number(data.health.avg_cgpa || 0).toFixed(2)} trend="up" />
          <MetricTile label="Pass Rate" value={formatPercent(data.health.pass_rate)} trend="up" />
          <MetricTile label="Attendance" value={formatPercent(data.health.attendance)} trend="up" />
          <MetricTile label="Active Backlogs" value={formatNumber(data.health.active_backlogs)} trend="down" />
          <MetricTile label="At-Risk Students" value={formatNumber(data.health.at_risk_students)} trend="down" />
        </div>
      </section>

      <section className="dean-panel">
        <div className="dean-panel-head"><h3>Department Performance (Pass Rate %)</h3></div>
        <div className="dean-bar-list">
          {departmentPerformance.length ? departmentPerformance.map((row: any) => (
            <button className="dean-bar-item" key={row.id} onClick={() => go('analytics')} type="button" title={`${row.name}: ${Number(row.pass_rate || 0)}% pass rate`}>
              <span className="dean-bar-label">{row.name}</span>
              <span className="dean-bar-track"><i style={{ width: `${Math.max(8, Number(row.pass_rate || 0))}%` }} /></span>
              <span className="dean-bar-value">{Number(row.pass_rate || 0)}%</span>
            </button>
          )) : <Empty text="No result data for this scope" />}
        </div>
      </section>

      <section className="dean-panel">
        <div className="dean-panel-head"><h3>Curriculum Status</h3></div>
        <div className="dean-donut-wrap dean-curriculum-chart">
          <DonutChart segments={curriculumEntries.map(([label, value]) => ({ label: niceLabel(label), value: Number(value || 0), color: colorMap[niceLabel(label)] || '#8ab7f5' }))} />
          <div className="dean-donut-legend">
            {curriculumEntries.map(([label, value]) => (
              <button key={label} className="dean-legend-item" onClick={() => go('curriculum')} type="button" aria-label={`${niceLabel(label)}: ${value}`}>
                <span className="dot" style={{ background: colorMap[niceLabel(label)] || '#8ab7f5' }} />
                <span>{niceLabel(label)}</span>
                <b>{curriculumTotal ? Math.round((Number(value || 0) / curriculumTotal) * 100) : 0}%</b>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="dean-panel">
        <div className="dean-panel-head"><h3>Timetable Readiness</h3><button className="dean-panel-link" type="button" onClick={() => go('dean_timetable')}>Resolve exceptions</button></div>
        <div className="dean-donut-wrap dean-curriculum-chart dean-readiness-chart">
          <DonutChart segments={[
            { label: 'Completed', value: Number(readiness.completed || 0), color: colorMap.Completed },
            { label: 'In Progress', value: Number(readiness.in_progress || 0), color: colorMap['In Progress'] },
            { label: 'Pending', value: Number(readiness.pending || 0), color: colorMap.Pending },
          ]} />
          <div className="dean-donut-legend">
            {[
              ['Completed', Number(readiness.completed || 0), colorMap.Completed],
              ['In Progress', Number(readiness.in_progress || 0), colorMap['In Progress']],
              ['Pending', Number(readiness.pending || 0), colorMap.Pending],
            ].map(([label, value, color]: any) => <button key={label} className="dean-legend-item" onClick={() => go('dean_timetable')} type="button"><span className="dot" style={{ background: color }} /><span>{label}</span><b>{(Number(readiness.completed || 0) + Number(readiness.in_progress || 0) + Number(readiness.pending || 0)) ? Math.round((value / (Number(readiness.completed || 0) + Number(readiness.in_progress || 0) + Number(readiness.pending || 0))) * 100) : 0}%</b></button>)}
          </div>
          <div className="dean-conflict-stat">Critical conflicts <strong>{Number(readiness.conflicts || 0)}</strong></div>
        </div>
      </section>

      <section className="dean-panel">
        <div className="dean-panel-head"><h3>Faculty Workload</h3><button className="dean-panel-link" type="button" onClick={() => go('dean_allocation')}>Manage allocation</button></div>
        <div className="dean-workload-wrap">
          <WorkloadGauge value={Number(avgWorkload || 0)} status={data.faculty_workload?.status} units={data.faculty_workload?.avg_units} />
          <div className="dean-workload-summary"><span><b>{Number(data.faculty_workload?.assigned || 0)}</b> assigned</span><span><b>{Number(data.faculty_workload?.unassigned || 0)}</b> unassigned</span><span><b>{Number(data.faculty_workload?.overloaded || 0)}</b> overloaded</span></div>
        </div>
      </section>

      <section className="dean-panel">
        <div className="dean-panel-head"><h3>Result Trends (Overall Pass Rate %)</h3></div>
        <div className="dean-trend-wrap">
          <TrendChart data={trendData} />
        </div>
      </section>

      <section className="dean-panel">
        <div className="dean-panel-head"><h3>Upcoming Academic Milestones</h3></div>
        <div className="dean-milestones">
          {(data.milestones || []).map((row: any) => (
            <button className="dean-milestone" key={row.id} onClick={() => go('academic_calendar')} type="button" aria-label={`${row.title}, ${formatDate(row.start_date)}`}>
              <div className="dean-milestone-icon"><HiOutlineCalendarDays /></div>
              <div className="dean-milestone-main">
                <strong>{row.title}</strong>
                <span>{formatDate(row.start_date)}{row.end_date ? ` - ${formatDate(row.end_date)}` : ''}</span>
              </div>
            </button>
          ))}
          {!data.milestones?.length && <Empty text="No upcoming academic milestones." />}
        </div>
      </section>

      <section className="dean-panel">
        <div className="dean-panel-head"><h3>My Approvals (Needs My Decision)</h3></div>
        <div className="dean-approval-list">
          <ApprovalRow label="Curriculum Proposals" count={Number(data.kpis?.curriculum_reviews || 0)} onClick={() => go('curriculum')} />
          <ApprovalRow label="Program Change Requests" count={Number(data.approvals?.program || 0)} onClick={() => go('dean_programs')} />
          <ApprovalRow label="Timetable Exceptions" count={Number(data.kpis?.timetable_conflicts || 0)} onClick={() => go('dean_timetable')} />
          <ApprovalRow label="Faculty Allocation Exceptions" count={Number(data.approvals?.allocation || 0)} onClick={() => go('dean_allocation')} />
        </div>
        <button className="dean-view-all" onClick={() => go('decision_inbox')} type="button">View All</button>
      </section>
    </div>
  </div>
}

function DeanKpiIcon({ label }: { label: string }) {
  const iconMap: Record<string, any> = {
    Programs: HiOutlineAcademicCap,
    Departments: HiOutlineBuildingLibrary,
    Courses: HiOutlineFolderOpen,
    Faculty: HiOutlineUsers,
    'Curriculum Reviews': HiOutlineDocumentText,
    'Timetable Conflicts': HiOutlineCalendarDays,
    'Academic Actions': HiOutlineClipboardDocumentList,
    'Needs My Decision': HiOutlineExclamationTriangle,
  }
  const Icon = iconMap[label] || HiOutlineChartBarSquare
  return <Icon />
}

function MetricTile({ label, value, trend }: { label: string; value: string; trend: 'up' | 'down' }) {
  return <div className="dean-metric">
    <div className="dean-metric-label">{label}</div>
    <div className="dean-metric-value">{value}</div>
    <span className={`dean-metric-trend-note ${trend}`}>{trend === 'up' ? 'Higher is better' : 'Lower is better'}</span>
  </div>
}

function WorkloadGauge({ value, status, units }: { value: number; status?: string | null; units?: number | null }) {
  const clamped = Math.min(100, Math.max(0, value))
  const angle = 180 + clamped * 1.8
  const radians = angle * Math.PI / 180
  const x = 100 + 76 * Math.cos(radians)
  const y = 100 + 76 * Math.sin(radians)
  const label = status || 'No allocation data'
  return <div className="dean-workload-gauge" role="img" aria-label={`Average faculty workload ${Math.round(clamped)} percent, ${label}`}>
    <svg viewBox="0 0 200 120" aria-hidden="true">
      <path className="gauge-track" pathLength="100" d="M24 100 A76 76 0 0 1 176 100" />
      <path className="gauge-green" pathLength="100" strokeDasharray="25 75" strokeDashoffset="0" d="M24 100 A76 76 0 0 1 176 100" />
      <path className="gauge-yellow" pathLength="100" strokeDasharray="25 75" strokeDashoffset="-25" d="M24 100 A76 76 0 0 1 176 100" />
      <path className="gauge-orange" pathLength="100" strokeDasharray="25 75" strokeDashoffset="-50" d="M24 100 A76 76 0 0 1 176 100" />
      <path className="gauge-red" pathLength="100" strokeDasharray="25 75" strokeDashoffset="-75" d="M24 100 A76 76 0 0 1 176 100" />
      <line className="gauge-needle" x1="100" y1="100" x2={x} y2={y} />
      <circle className="gauge-pin" cx="100" cy="100" r="5" />
    </svg>
    <div className="dean-workload-inner"><strong>{clamped < 10 ? clamped.toFixed(1) : Math.round(clamped)}%</strong><span>{label}</span>{units != null && <small>{Number(units).toFixed(2)} units / 4</small>}</div>
    <div className="dean-workload-footer"><span>0%</span><span>100%</span></div>
  </div>
}

function DonutChart({ segments }: { segments: Array<{ label: string; value: number; color: string }> }) {
  const total = segments.reduce((sum, item) => sum + (Number(item.value) || 0), 0) || 1
  let offset = 0
  const gradient = segments.map((segment) => {
    const start = offset
    const end = offset + (Number(segment.value || 0) / total) * 100
    offset = end
    return `${segment.color} ${start}% ${end}%`
  }).join(', ')

  return <div className="dean-donut-chart" style={{ background: `conic-gradient(${gradient})` }}>
    <div className="dean-donut-hole" />
  </div>
}

function TrendChart({ data }: { data: any[] }) {
  if (!data.length) {
    return <div className="dean-empty">No result trend data</div>
  }
  const values = data.map((row) => Number(row.pass_rate || 0))
  const min = Math.min(...values, 0)
  const max = Math.max(...values, 100)
  const points = data.map((row, index) => {
    const x = 12 + (index * 70) / Math.max(1, data.length - 1)
    const y = 110 - ((Number(row.pass_rate || 0) - min) / Math.max(1, max - min)) * 78
    return { x, y, label: row.academic_year || `Term ${index + 1}`, value: Number(row.pass_rate || 0) }
  })
  const path = points.map((p, index) => `${index === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
  return <div className="dean-trend-card">
    <svg viewBox="0 0 260 150" preserveAspectRatio="none">
      <path d={path} fill="none" stroke="#2d6cdf" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {points.map((point) => <circle key={`${point.label}-${point.value}`} cx={point.x} cy={point.y} r="4" fill="#2d6cdf" />)}
    </svg>
    <div className="dean-trend-labels">
      {points.map((point) => <span key={`${point.label}-${point.value}`}>{point.label}</span>)}
    </div>
  </div>
}

function ApprovalRow({ label, count, onClick }: { label: string; count: number; onClick: () => void }) {
  return <button className="dean-approval-row" onClick={onClick} type="button"><span>{label}</span><b>{count}</b></button>
}

function niceLabel(label: string) {
  const map: Record<string, string> = {
    Approved: 'Approved',
    'In Review': 'In Review',
    Returned: 'Returned',
    Overdue: 'Overdue',
    SUBMITTED: 'In Review',
    DRAFT: 'Draft',
    REJECTED: 'Rejected',
    RETURNED: 'Returned',
  }
  return map[label] || label.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatPercent(value: number | null) {
  return value == null ? '—' : `${Math.round(value)}%`
}

function formatNumber(value: number | null) {
  if (value == null) return '—'
  return value.toLocaleString()
}

function formatDate(value: string | null | undefined) {
  if (!value) return 'TBD'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
