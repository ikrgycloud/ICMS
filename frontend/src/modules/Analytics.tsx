import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, money, Kpis } from './kit'

export default function Analytics({ user, go }: { user: any; go?: (view: string) => void }) {
  return user?.office_n === 6 ? <DeanPerformanceResults go={go} /> : <GenericAnalytics />
}

function GenericAnalytics() {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.overview().then(setData).catch(() => {}) }, [])
  if (!data) return <Spinner />
  const s = data.stats
  const dept = data.dept_distribution || {}
  const max = Math.max(1, ...Object.values(dept).map(Number))

  return (
    <div className="fade-in">
      <PageHead title="Analytics" sub="Cross-institution metrics" />
      <Kpis items={[
        { label: 'Students', value: s.students }, { label: 'Faculty', value: s.faculty },
        { label: 'Sections', value: s.sections }, { label: 'Offers', value: s.placement_offers },
        { label: 'Fees due', value: money(s.fees_due), tone: 'var(--rose)' },
      ]} />
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-h"><h3>Enrolment by department</h3></div>
        <div className="card-pad">
          {Object.entries(dept).sort((a, b) => Number(b[1]) - Number(a[1])).map(([d, n]) => (
            <div className="bar-row" key={d}>
              <div className="bar-label">{d}</div>
              <div className="bar-track"><div className="bar-fill" style={{ width: `${(Number(n) / max) * 100}%` }} /></div>
              <div className="bar-val">{String(n)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function DeanPerformanceResults({ go }: { go?: (view: string) => void }) {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.deanDashboard().then(setData).catch((e: any) => setError(e.message || 'Unable to load performance data'))
  }, [])

  if (!data) return error ? <div className="card card-pad calendar-banner warn">{error}</div> : <Spinner />

  const health = data.health || {}
  const departments = [...(data.department_performance || [])].sort((a: any, b: any) => Number(a.pass_rate || 0) - Number(b.pass_rate || 0))
  const trends = data.result_trends || []
  const risks = Number(health.at_risk_students || 0)
  const conflicts = Number(data.kpis?.timetable_conflicts || 0)
  const targetPassRate = 75
  return <div className="fade-in dean-performance-page">
    <PageHead title="Performance & Results" sub="Compare academic outcomes, identify intervention areas, and track results across your scope." right={<button className="btn btn-out" onClick={() => window.location.reload()} type="button">Refresh</button>} />
    <div className="dean-performance-kpis">
      <PerformanceMetric label="Pass rate" value={formatPerformancePercent(health.pass_rate)} note={`Target ${targetPassRate}%`} tone={Number(health.pass_rate || 0) >= targetPassRate ? 'good' : 'warning'} />
      <PerformanceMetric label="Attendance" value={formatPerformancePercent(health.attendance)} note="Institution average" tone="good" />
      <PerformanceMetric label="Average CGPA" value={health.avg_cgpa == null ? '—' : Number(health.avg_cgpa).toFixed(2)} note="Current academic scope" tone="neutral" />
      <PerformanceMetric label="At-risk students" value={Number(health.at_risk_students || 0).toLocaleString()} note="Requires intervention" tone={risks ? 'danger' : 'good'} />
    </div>
    <div className="dean-performance-grid">
      <section className="card dean-performance-panel dean-performance-departments">
        <div className="card-h"><div><h3>Department performance</h3><p className="hint">Lowest pass rates appear first for faster intervention.</p></div><span className="dean-performance-target">Target {targetPassRate}%</span></div>
        <div className="dean-performance-bars">
          {departments.length ? departments.map((row: any) => {
            const passRate = Number(row.pass_rate || 0)
            return <button className="dean-performance-bar-row" key={row.id} onClick={() => go?.('dean_risk')} type="button" title={`${row.name}: ${passRate}% pass rate`}>
              <span className="dean-performance-bar-name">{row.name}</span><span className="dean-performance-bar-track"><i className={passRate < targetPassRate ? 'below-target' : ''} style={{ width: `${Math.max(6, passRate)}%` }} /></span><b>{passRate}%</b>
            </button>
          }) : <div className="dean-empty">No department result data for this scope.</div>}
        </div>
      </section>
      <section className="card dean-performance-panel dean-performance-trends">
        <div className="card-h"><div><h3>Result trend</h3><p className="hint">Pass rate across academic years.</p></div></div>
        {trends.length ? <div className="dean-performance-trend-list">{trends.map((row: any) => <div className="dean-performance-trend-row" key={row.academic_year}><span>{row.academic_year}</span><div className="dean-performance-bar-track"><i style={{ width: `${Math.max(6, Number(row.pass_rate || 0))}%` }} /></div><b>{Number(row.pass_rate || 0)}%</b></div>)}</div> : <div className="dean-empty">No result trend data available.</div>}
      </section>
    </div>
    <section className="dean-performance-actions" aria-label="Performance actions">
      <div><span className="dean-performance-action-kicker">Decision queue</span><h3>Performance signals needing attention</h3><p>Use department-level results to guide quality reviews and timetable interventions.</p></div>
      <div className="dean-performance-action-items"><button className="dean-performance-action danger" onClick={() => go?.('dean_risk')} type="button"><b>{risks}</b><span>At-risk students</span></button><button className="dean-performance-action warning" onClick={() => go?.('dean_timetable')} type="button"><b>{conflicts}</b><span>Timetable conflicts</span></button><button className="dean-performance-action neutral" onClick={() => go?.('dean_reports')} type="button"><b>{Number(data.kpis?.academic_actions || 0)}</b><span>Academic actions</span></button></div>
    </section>
  </div>
}

function PerformanceMetric({ label, value, note, tone }: { label: string; value: string; note: string; tone: string }) {
  return <div className={`dean-performance-metric ${tone}`}><span>{label}</span><b>{value}</b><small>{note}</small></div>
}

function formatPerformancePercent(value: number | null | undefined) {
  return value == null ? '—' : `${Math.round(Number(value))}%`
}
