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
  const trendData = data?.result_trends || []
  const curriculumEntries = Object.entries(data?.curriculum_status || {})
  const curriculumTotal = curriculumEntries.reduce((sum: number, [, count]) => sum + Number(count || 0), 0)
  const readiness = data?.timetable_readiness || { completed: 0, in_progress: 0, pending: 0, conflicts: 0 }
  const curriculumSegments = valueColoredSegments(curriculumEntries.map(([label, value]) => ({ label: niceLabel(label), value: Number(value || 0) })))
  const readinessSegments = valueColoredSegments([
    { label: 'Completed', value: Number(readiness.completed || 0) },
    { label: 'In Progress', value: Number(readiness.in_progress || 0) },
    { label: 'Pending', value: Number(readiness.pending || 0) },
  ])
  const readinessTotal = readinessSegments.reduce((sum, segment) => sum + segment.value, 0)
  const healthScorecard = data?.health_scorecard || []
  const healthPriority = data?.health_priority
  const healthScope = [filters.academic_year || 'All academic years', filters.semester ? `Semester ${filters.semester}` : 'All semesters'].join(' · ')
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
          <div className="dean-kpi-icon"><DeanKpiIcon label={String(label)} /></div>
          <div className="dean-kpi-label">{label}</div>
          <div className="dean-kpi-value">{value}</div>
        </button>
      ))}
    </div>

    <div className="dean-main-grid">
      <section className="dean-panel dean-health-panel">
        <div className="dean-panel-head"><div><h3>Academic Health (Overall)</h3><span className="dean-panel-subtitle">{healthScope}</span></div><span className="hint">Live scorecard</span></div>
        <div className="dean-health-context">Thresholds and comparisons use records within the selected academic scope.</div>
        <div className="dean-health-scorecard">
          {healthScorecard.map((metric: any) => <HealthMetric key={metric.key} metric={metric} onOpen={() => go(metric.route)} />)}
        </div>
        {healthPriority && <button className={`dean-health-priority ${healthPriority.status}`} onClick={() => go(healthPriority.route)} type="button"><span><b>Priority action · {healthPriority.metric}</b><small>{healthPriority.message}</small></span><em>Open →</em></button>}
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
        <div className="dean-panel-head"><h3>Curriculum Status</h3><span className="hint">Darker shade = larger live value</span></div>
        <div className="dean-donut-wrap dean-curriculum-chart">
          <DonutChart segments={curriculumSegments} />
          <div className="dean-donut-legend">
            {curriculumSegments.map((segment) => (
              <button key={segment.label} className="dean-legend-item" onClick={() => go('curriculum')} type="button" aria-label={`${segment.label}: ${segment.value}`}>
                <span className="dot" style={{ background: segment.color }} />
                <span>{segment.label}</span>
                <b>{curriculumTotal ? Math.round((segment.value / curriculumTotal) * 100) : 0}%</b>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="dean-panel">
        <div className="dean-panel-head"><h3>Timetable Readiness</h3><span className="hint">Darker shade = larger live value</span><button className="dean-panel-link" type="button" onClick={() => go('dean_timetable')}>Resolve exceptions</button></div>
        <div className="dean-donut-wrap dean-curriculum-chart dean-readiness-chart">
          <DonutChart segments={readinessSegments} />
          <div className="dean-donut-legend">
            {readinessSegments.map((segment) => <button key={segment.label} className="dean-legend-item" onClick={() => go('dean_timetable')} type="button"><span className="dot" style={{ background: segment.color }} /><span>{segment.label}</span><b>{readinessTotal ? Math.round((segment.value / readinessTotal) * 100) : 0}%</b></button>)}
          </div>
          <div className="dean-readiness-summary" role="status" aria-label={`${Number(readiness.conflicts || 0)} critical timetable conflicts`}>
            <div><span>Critical conflicts</span><small>Unresolved timetable exceptions</small></div>
            <strong>{Number(readiness.conflicts || 0)}</strong>
          </div>
        </div>
      </section>

      <section className="dean-panel">
        <div className="dean-panel-head"><h3>Result Trends (Overall Pass Rate %)</h3></div>
        <div className="dean-trend-wrap">
          <TrendChart data={trendData} />
        </div>
      </section>

      <section className="dean-panel dean-workload-panel">
        <div className="dean-panel-head"><h3>Faculty Workload</h3><button className="dean-panel-link" type="button" onClick={() => go('dean_allocation')}>View allocation</button></div>
        <FacultyWorkload workload={data?.faculty_workload} onOpen={() => go('dean_allocation')} />
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
          <ApprovalRow label="Curriculum Proposals" count={Number(data.kpis?.curriculum_reviews || 0)} tone="curriculum" onClick={() => go('curriculum')} />
          <ApprovalRow label="Program Change Requests" count={Number(data.approvals?.program || 0)} tone="program" onClick={() => go('dean_programs')} />
          <ApprovalRow label="Timetable Exceptions" count={Number(data.kpis?.timetable_conflicts || 0)} tone="timetable" onClick={() => go('dean_timetable')} />
          <ApprovalRow label="Faculty Allocation Exceptions" count={Number(data.approvals?.allocation || 0)} tone="allocation" onClick={() => go('dean_allocation')} />
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

function HealthMetric({ metric, onOpen }: { metric: any; onOpen: () => void }) {
  const positiveMetric = ['avg_cgpa', 'pass_rate', 'attendance'].includes(metric.key)
  const comparison = metric.comparison
  const change = Number(comparison?.change || 0)
  const trend = !comparison || !change ? 'stable' : ((change > 0) === positiveMetric ? 'improving' : 'worsening')
  const displayValue = metric.value == null ? '—' : metric.key === 'avg_cgpa' ? Number(metric.value).toFixed(2) : ['pass_rate', 'attendance'].includes(metric.key) ? `${Number(metric.value)}%` : formatNumber(metric.value)
  const comparisonText = !comparison ? 'No comparison period' : `${change > 0 ? '+' : ''}${change}${comparison.unit === 'points' ? ' pp' : ''} ${comparison.label}`
  const statusLabel: Record<string, string> = { on_track: 'On track', watch: 'Watch', action: 'Action required', unavailable: 'No data' }
  return <button className={`dean-health-metric ${metric.status}`} onClick={onOpen} type="button" aria-label={`${metric.label}: ${displayValue}, ${statusLabel[metric.status] || metric.status}`}>
    <span className="dean-health-metric-label">{metric.label}</span>
    <strong>{displayValue}</strong>
    <span className={`dean-health-status ${metric.status}`}>{statusLabel[metric.status] || metric.status}</span>
    <small className={`dean-health-comparison ${trend}`}>{comparisonText}</small>
    <small className="dean-health-target">{metric.target}</small>
  </button>
}

function valueColoredSegments(segments: Array<{ label: string; value: number }>) {
  const maxValue = Math.max(1, ...segments.map((segment) => segment.value))
  return segments.map((segment, index) => ({
    ...segment,
    color: valueColor(index, segments.length, segment.value / maxValue),
  }))
}

function valueColor(index: number, total: number, relativeValue: number) {
  // Hue separates categories; saturation and lightness are derived from the
  // live value, so a larger value is visibly stronger rather than predefined.
  const hue = Math.round((index / Math.max(1, total)) * 300 + 30)
  const intensity = Math.max(0, Math.min(1, relativeValue))
  return `hsl(${hue} ${48 + intensity * 38}% ${88 - intensity * 42}%)`
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

function FacultyWorkload({ workload, onOpen }: { workload: any; onOpen: () => void }) {
  const facultyCount = Number(workload?.faculty_count || 0)
  const assigned = Number(workload?.assigned || 0)
  const load = Number(workload?.avg_load || 0)
  const capacity = Number(workload?.capacity_units || 0)
  const average = Number(workload?.avg_units || 0)
  const hasAllocationData = assigned > 0
  const status = workload?.status || 'No allocation data'
  return <button className="dean-workload-content" onClick={onOpen} type="button" aria-label={`Faculty workload: ${status}`}>
    <div className="dean-workload-gauge" style={{ '--load': `${load * 1.8}deg` } as React.CSSProperties}>
      <div className="dean-workload-gauge-hole"><strong>{hasAllocationData ? `${Math.round(load)}%` : '—'}</strong><span>{hasAllocationData ? 'average load' : 'no allocation data'}</span></div>
    </div>
    <div className="dean-workload-copy"><b>{status}</b><span>{hasAllocationData ? `${average.toFixed(1)} of ${capacity.toFixed(1)} workload units per faculty` : 'Create and approve faculty allocations to calculate workload.'}</span></div>
    <div className="dean-workload-breakdown">
      <span><i className="underloaded" />Underloaded <b>{Number(workload?.underloaded || 0)}</b></span>
      <span><i className="balanced" />Balanced <b>{Number(workload?.balanced || 0)}</b></span>
      <span><i className="overloaded" />Overloaded <b>{Number(workload?.overloaded || 0)}</b></span>
      <small>{facultyCount ? `${assigned} of ${facultyCount} faculty allocated` : 'No faculty in this scope'}</small>
    </div>
  </button>
}

function ApprovalRow({ label, count, tone, onClick }: { label: string; count: number; tone: string; onClick: () => void }) {
  return <button className={`dean-approval-row ${tone} ${count ? 'has-count' : 'is-empty'}`} onClick={onClick} type="button"><span>{label}</span><b>{count}</b></button>
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
