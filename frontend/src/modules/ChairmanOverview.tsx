import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Modal, Spinner } from './kit'

const RUPEE = '\u20B9'
const SEGMENT_COLORS = ['#3b82f6', '#18b46b', '#f7b53b', '#ef233c', '#162033']

export default function ChairmanOverview({ go }: { go: (view: string) => void }) {
  const [selectedStart, setSelectedStart] = useState('')
  const [selectedYear, setSelectedYear] = useState('')
  const [selectedSemesterMode, setSelectedSemesterMode] = useState('whole')
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [feesOpen, setFeesOpen] = useState(false)
  const [feesData, setFeesData] = useState<any>(null)
  const [feesLoading, setFeesLoading] = useState(false)
  const [feesError, setFeesError] = useState('')

  useEffect(() => {
    let active = true

    async function load() {
      setLoading(true)
      setError('')

      try {
        const response = await api.chairmanOverview(selectedStart)
        if (!active) return
        setData(response)
        if (!selectedStart && response?.range?.start) {
          setSelectedStart(response.range.start)
        }
      } catch (err: any) {
        if (!active) return
        setError(err?.message || 'We could not load the chairman overview.')
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [reloadKey, selectedStart])

  useEffect(() => {
    if (!feesOpen) return
    let active = true

    async function loadFeesDetail() {
      setFeesLoading(true)
      setFeesError('')
      try {
        const response = await api.chairmanOutstandingFees(selectedStart || data?.range?.start || '')
        if (!active) return
        setFeesData(response)
      } catch (err: any) {
        if (!active) return
        setFeesError(err?.message || 'We could not load the outstanding fee details.')
      } finally {
        if (active) setFeesLoading(false)
      }
    }

    loadFeesDetail()
    return () => {
      active = false
    }
  }, [feesOpen, selectedStart, data?.range?.start])

  const donut = useMemo(() => {
    const segments = data?.financial?.segments || []
    let cursor = 0
    const stops = segments.map((segment: any, index: number) => {
      const color = SEGMENT_COLORS[index % SEGMENT_COLORS.length]
      const next = cursor + Number(segment.percent || 0)
      const stop = `${color} ${cursor}% ${next}%`
      cursor = next
      return stop
    })
    return `conic-gradient(${stops.join(', ')})`
  }, [data])

  const availableRanges = useMemo(() => {
    if (!data?.range) return []
    const ranges = data.range.available_ranges?.length ? data.range.available_ranges : [data.range]
    return ranges.map(buildRangeMeta)
  }, [data])

  const yearOptions = useMemo<string[]>(
    () => Array.from(new Set<string>(availableRanges.map((range: any) => String(range.year)))).sort((left, right) => Number(right) - Number(left)),
    [availableRanges],
  )

  const yearScopedRanges = useMemo(
    () => availableRanges.filter(range => !selectedYear || range.year === selectedYear),
    [availableRanges, selectedYear],
  )

  const filteredRanges = useMemo(
    () => yearScopedRanges.filter(range => selectedSemesterMode === 'whole' || range.semester === selectedSemesterMode),
    [yearScopedRanges, selectedSemesterMode],
  )

  const activeRange = useMemo(() => {
    const activeStart = selectedStart || data?.range?.start
    return availableRanges.find(range => range.start === activeStart) || filteredRanges[0] || availableRanges[0] || null
  }, [availableRanges, filteredRanges, selectedStart, data?.range?.start])

  useEffect(() => {
    if (!availableRanges.length) return
    if (!selectedYear || !yearOptions.includes(selectedYear)) {
      setSelectedYear(activeRange?.year || availableRanges[0].year)
    }
  }, [activeRange, availableRanges, selectedYear, yearOptions])

  useEffect(() => {
    if (selectedSemesterMode === 'whole' || !yearScopedRanges.length) return
    if (!yearScopedRanges.some(range => range.semester === selectedSemesterMode)) {
      setSelectedSemesterMode('whole')
    }
  }, [selectedSemesterMode, yearScopedRanges])

  useEffect(() => {
    if (!filteredRanges.length) return
    const activeStart = selectedStart || data?.range?.start
    if (!filteredRanges.some(range => range.start === activeStart)) {
      setSelectedStart(filteredRanges[0].start)
    }
  }, [filteredRanges, selectedStart, data?.range?.start])

  if (loading) return <Spinner />

  if (error || !data) {
    return (
      <div className="chair-panel fade-in">
        <div className="chair-panel-head"><h3>Chairman overview unavailable</h3></div>
        <div className="card-pad">
          <p style={{ color: 'var(--txt-soft)', lineHeight: 1.7, marginBottom: 16 }}>
            {error || 'The executive dashboard could not be loaded.'}
          </p>
          <button className="btn btn-crimson" onClick={() => setReloadKey(key => key + 1)} type="button">
            Try again
          </button>
        </div>
      </div>
    )
  }

  const cards = [
    {
      key: 'outstanding_fees',
      label: 'Outstanding Fees',
      value: formatCrore(data.kpis.outstanding_fees.value),
      metric: data.kpis.outstanding_fees,
      icon: 'fees',
    },
    {
      key: 'accreditations',
      label: 'Total Accreditations',
      value: formatNumber(data.kpis.accreditations.value),
      metric: data.kpis.accreditations,
      icon: 'accreditation',
    },
    {
      key: 'partners',
      label: 'Partners',
      value: formatNumber(data.kpis.partners.value),
      metric: data.kpis.partners,
      icon: 'partners',
    },
    {
      key: 'escalations',
      label: 'Escalations',
      value: formatNumber(data.kpis.escalations.value),
      metric: data.kpis.escalations,
      icon: 'alert',
    },
  ]

  const quickActions = [
    { label: 'Institution Calendar', icon: 'calendar', to: 'calendar' },
    { label: 'Academic Calendar', icon: 'document', to: 'academic_calendar' },
    { label: 'Financial Summary', icon: 'document', to: 'finance' },
    { label: 'Performance Analytics', icon: 'chart', to: 'analytics' },
  ]

  return (
    <div className="chair-overview fade-in">
      <section className="chair-head-shell">
        <div className="chair-head-top">
          <div className="chair-topline">
            <h1>{data.welcome.title} <span className="chair-wave">{'\u{1F44B}'}</span></h1>
            <p>{data.welcome.subtitle}</p>
          </div>

          <div className="chair-context-chip">
            <MetricGlyph kind="clock" />
            <span>{activeRange?.label || data.range.label}</span>
          </div>
        </div>

        <div className="chair-toolbar chair-toolbar-compact">
          <label className="chair-filter">
            <span className="chair-filter-label">Year</span>
            <span className="chair-filter-control">
              <MetricGlyph kind="calendar" />
              <select value={selectedYear || activeRange?.year || ''} onChange={event => setSelectedYear(event.target.value)}>
                {yearOptions.map(year => (
                  <option key={year} value={year}>{year}</option>
                ))}
              </select>
            </span>
          </label>

          <label className="chair-filter">
            <span className="chair-filter-label">Semester</span>
            <span className="chair-filter-control">
              <MetricGlyph kind="semester" />
              <select value={selectedSemesterMode} onChange={event => setSelectedSemesterMode(event.target.value)}>
                <option value="whole">Whole</option>
                <option value="odd">Odd semester</option>
                <option value="even">Even semester</option>
              </select>
            </span>
          </label>

          <label className="chair-filter">
            <span className="chair-filter-label">Period</span>
            <span className="chair-filter-control">
              <MetricGlyph kind="clock" />
              <select value={selectedStart || data.range.start} onChange={event => setSelectedStart(event.target.value)}>
                {filteredRanges.map((range: any) => (
                  <option key={range.start} value={range.start}>{range.label}</option>
                ))}
              </select>
            </span>
          </label>
        </div>
      </section>

      <div className="chair-kpis">
        {cards.map(card => (
          card.key === 'outstanding_fees' ? (
            <button className="chair-kpi-card is-action" key={card.key} onClick={() => setFeesOpen(true)} type="button">
              <div className="chair-kpi-icon"><MetricGlyph kind={card.icon} /></div>
              <div className="chair-kpi-copy">
                <div className="chair-kpi-label">{card.label}</div>
                <div className="chair-kpi-value">{card.value}</div>
                <div className={`chair-kpi-sub ${trendTone(card.metric)}`}>
                  <TrendArrow direction={card.metric.direction} />
                  <span>{formatDelta(card.metric, card.key === 'outstanding_fees')}</span>
                  <small>vs last month</small>
                </div>
              </div>
            </button>
          ) : (
            <div className="chair-kpi-card" key={card.key}>
              <div className="chair-kpi-icon"><MetricGlyph kind={card.icon} /></div>
              <div className="chair-kpi-copy">
                <div className="chair-kpi-label">{card.label}</div>
                <div className="chair-kpi-value">{card.value}</div>
                <div className={`chair-kpi-sub ${trendTone(card.metric)}`}>
                  <TrendArrow direction={card.metric.direction} />
                  <span>{formatDelta(card.metric, card.key === 'outstanding_fees')}</span>
                  <small>vs last month</small>
                </div>
              </div>
            </div>
          )
        ))}
      </div>

      <div className="chair-summary-grid">
        <section className="chair-panel chair-institution">
          <div className="chair-panel-head">
            <h3>Institution at a glance</h3>
          </div>

          <div className="chair-stats-grid top">
            <StatItem label="Schools" value={data.institution.schools} icon="book" />
            <StatItem label="Departments" value={data.institution.departments} icon="users" />
            <StatItem label="Programs" value={data.institution.programs} icon="box" />
            <StatItem label="Campuses" value={data.institution.campuses} icon="building" />
          </div>

          <div className="chair-divider" />

          <div className="chair-stats-grid bottom">
            <StatItem label="Total Staff" value={formatNumber(data.institution.total_staff)} />
            <StatItem label="Non-teaching Staff" value={formatNumber(data.institution.non_teaching_staff)} />
            <StatItem label="Active Users" value={formatNumber(data.institution.active_users)} />
            <StatItem label="System Uptime" value={`${Number(data.institution.system_uptime).toFixed(1)}%`} dot />
          </div>
        </section>

        <section className="chair-panel chair-financial">
          <div className="chair-panel-head">
            <h3>Financial overview (YTD)</h3>
          </div>

          <div className="chair-financial-body">
            <div className="chair-donut-shell">
              <div className="chair-donut" style={{ background: donut }}>
                <div className="chair-donut-center">
                  <div className="chair-donut-value">{formatCrore(data.financial.total_income)}</div>
                  <div className="chair-donut-label">Total Income</div>
                </div>
              </div>
            </div>

            <div className="chair-legend">
              {(data.financial.segments || []).map((segment: any, index: number) => (
                <div className="chair-legend-row" key={segment.name}>
                  <div className="chair-legend-name">
                    <span
                      className="chair-legend-dot"
                      style={{ background: SEGMENT_COLORS[index % SEGMENT_COLORS.length] }}
                    />
                    <div>
                      <div>{segment.name}</div>
                      <small>{formatCrore(segment.amount)}</small>
                    </div>
                  </div>
                  <div className="chair-legend-pct">{segment.percent}%</div>
                </div>
              ))}
            </div>
          </div>

          <div className="chair-financial-foot">
            <div>Total Expense: <strong>{formatCrore(data.financial.total_expense)}</strong></div>
            <div className="surplus">Surplus: <strong>{formatCrore(data.financial.surplus)}</strong></div>
          </div>
        </section>
      </div>

      <div className="chair-bottom-grid">
        <section className="chair-panel">
          <div className="chair-panel-head">
            <h3>Key approvals</h3>
            <button className="chair-mini-btn" onClick={() => go('approvals')} type="button">View all</button>
          </div>
          <div className="chair-list">
            {(data.key_approvals || []).map((item: any) => (
              <div className="chair-list-row" key={item.title}>
                <div className="chair-list-main">
                  <span className="chair-doc-chip"><MetricGlyph kind="document" /></span>
                  <span>{item.title}</span>
                </div>
                <div className="chair-list-side">
                  <span className="chair-count-badge">{item.count}</span>
                  <span className="chair-status">{item.status}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="chair-panel">
          <div className="chair-panel-head">
            <h3>Recent alerts</h3>
            <button className="chair-mini-btn" onClick={() => go('workflows')} type="button">View all</button>
          </div>
          <div className="chair-alert-list">
            {(data.alerts || []).map((alert: any) => (
              <div className="chair-alert-row" key={`${alert.title}-${alert.at}`}>
                <span className={`chair-alert-badge ${alert.severity}`}>
                  <MetricGlyph kind={alertGlyph(alert.severity)} />
                </span>
                <div className="chair-alert-copy">
                  <div className="chair-alert-title">{alert.title}</div>
                  <div className="chair-alert-body">{alert.body}</div>
                </div>
                <div className="chair-alert-time">{timeAgo(alert.at)}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="chair-panel">
          <div className="chair-panel-head">
            <h3>Quick actions</h3>
          </div>
          <div className="chair-action-grid">
            {quickActions.map(action => (
              <button className="chair-action-card" key={action.label} onClick={() => go(action.to)} type="button">
                <div className="chair-action-icon"><MetricGlyph kind={action.icon} /></div>
                <div>{action.label}</div>
              </button>
            ))}
          </div>
        </section>
      </div>

      {feesOpen && (
        <OutstandingFeesModal
          data={feesData}
          loading={feesLoading}
          error={feesError}
          onClose={() => setFeesOpen(false)}
          onViewDetails={() => {
            setFeesOpen(false)
            go('finance')
          }}
        />
      )}
    </div>
  )
}

function OutstandingFeesModal({
  data,
  loading,
  error,
  onClose,
  onViewDetails,
}: {
  data: any
  loading: boolean
  error: string
  onClose: () => void
  onViewDetails: () => void
}) {
  const cards = data ? [
    {
      label: 'Total Outstanding',
      value: formatCrore(data.summary.total_outstanding.value),
      delta: data.summary.total_outstanding.delta_pct,
      direction: data.summary.total_outstanding.direction,
      icon: 'fees',
      tone: 'good',
    },
    {
      label: 'Students with Dues',
      value: formatNumber(data.summary.students_with_dues.value),
      delta: data.summary.students_with_dues.delta_pct,
      direction: data.summary.students_with_dues.direction,
      icon: 'users',
      tone: 'good',
    },
    {
      label: 'Overdue (> 60 Days)',
      value: formatCrore(data.summary.overdue_over_60.value),
      delta: data.summary.overdue_over_60.delta_pct,
      direction: data.summary.overdue_over_60.direction,
      icon: 'clock',
      tone: 'danger',
    },
    {
      label: 'Notices Sent',
      value: formatNumber(data.summary.notices_sent.value),
      delta: data.summary.notices_sent.delta_pct,
      direction: data.summary.notices_sent.direction,
      icon: 'document',
      tone: 'good',
    },
  ] : []

  return (
    <Modal
      title="Outstanding Fees Overview"
      onClose={onClose}
      className="modal-wide outstanding-modal"
      footer={
        <>
          <button className="btn btn-out" onClick={onClose}>Close</button>
          <button className="btn btn-crimson" onClick={onViewDetails}>View details</button>
        </>
      }
    >
      {loading && !data && <Spinner />}
      {!loading && error && (
        <div className="outstanding-empty">
          <p>{error}</p>
        </div>
      )}
      {!loading && data && (
        <div className="outstanding-modal-body">
          <p className="outstanding-subtitle">
            Summary of outstanding fee status across the institution for {data.range.label}.
          </p>

          <div className="outstanding-card-grid">
            {cards.map(card => (
              <div className="outstanding-mini-card" key={card.label}>
                <div className="outstanding-mini-icon"><MetricGlyph kind={card.icon} /></div>
                <div className="outstanding-mini-label">{card.label}</div>
                <div className="outstanding-mini-value">{card.value}</div>
                <div className={`outstanding-mini-sub ${card.tone === 'danger' && card.direction === 'up' ? 'danger' : 'good'}`}>
                  <TrendArrow direction={card.direction} />
                  <span>{card.delta.toFixed(1)}%</span>
                  <small>vs last month</small>
                </div>
              </div>
            ))}
          </div>

          <div className="outstanding-chart-wrap">
            <div className="outstanding-chart-title">Outstanding Trend (Last 6 Months)</div>
            <OutstandingTrendChart points={data.trend || []} />
          </div>
        </div>
      )}
    </Modal>
  )
}

function OutstandingTrendChart({ points }: { points: { label: string; value: number }[] }) {
  if (!points.length) {
    return <div className="outstanding-empty">No trend data available yet.</div>
  }

  const width = 520
  const height = 180
  const padX = 30
  const padY = 22
  const max = Math.max(...points.map(point => Number(point.value || 0)), 1)
  const graphWidth = width - padX * 2
  const graphHeight = height - padY * 2
  const steps = 4

  const coords = points.map((point, index) => {
    const x = padX + (graphWidth * index) / Math.max(points.length - 1, 1)
    const y = height - padY - (graphHeight * Number(point.value || 0)) / max
    return { ...point, x, y }
  })

  const line = coords.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
  const area = `${line} L ${coords[coords.length - 1].x} ${height - padY} L ${coords[0].x} ${height - padY} Z`

  return (
    <div className="outstanding-chart">
      <svg viewBox={`0 0 ${width} ${height}`} className="outstanding-chart-svg" role="img" aria-label="Outstanding fee trend">
        <defs>
          <linearGradient id="outstandingArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(59,130,246,.24)" />
            <stop offset="100%" stopColor="rgba(59,130,246,.04)" />
          </linearGradient>
        </defs>
        {Array.from({ length: steps + 1 }).map((_, index) => {
          const y = height - padY - (graphHeight * index) / steps
          return <line key={index} x1={padX} y1={y} x2={width - padX} y2={y} className="outstanding-grid-line" />
        })}
        <path d={area} fill="url(#outstandingArea)" />
        <path d={line} fill="none" stroke="#3b82f6" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {coords.map(point => (
          <g key={point.label}>
            <circle cx={point.x} cy={point.y} r="5" fill="#3b82f6" />
            <text x={point.x} y={point.y - 12} textAnchor="middle" className="outstanding-point-label">
              {formatCrore(point.value)}
            </text>
            <text x={point.x} y={height - 6} textAnchor="middle" className="outstanding-axis-label">
              {point.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}

function StatItem({ label, value, icon, dot = false }: { label: string; value: string | number; icon?: string; dot?: boolean }) {
  return (
    <div className="chair-stat-item">
      <div className="chair-stat-label">
        {icon ? <MetricGlyph kind={icon} /> : dot ? <span className="chair-green-dot" /> : null}
        <span>{label}</span>
      </div>
      <div className="chair-stat-value">{value}</div>
    </div>
  )
}

function TrendArrow({ direction }: { direction: string }) {
  if (direction === 'down') {
    return (
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="m4 6 4 4 4-4" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="m4 10 4-4 4 4" />
    </svg>
  )
}

function formatCrore(value: number) {
  return `${RUPEE} ${(Number(value || 0) / 1e7).toFixed(2)} Cr`
}

function formatNumber(value: number) {
  return Number(value || 0).toLocaleString('en-IN')
}

function formatDelta(metric: any, isPercent = false) {
  const delta = isPercent ? Number(metric.delta || 0) : Number(metric.change || 0)
  return isPercent ? `${Math.abs(delta).toFixed(1)}%` : formatNumber(Math.abs(delta))
}

function trendTone(metric: any) {
  if (metric?.tone === 'negative') return metric?.direction === 'down' ? 'good' : 'danger'
  return 'good'
}

function buildRangeMeta(range: any) {
  const [yearPart = '', monthPart = '1'] = String(range?.start || '').split('-')
  const year = String(Number(yearPart) || new Date().getFullYear())
  const month = Number(monthPart) || 1
  return {
    ...range,
    year,
    semester: month >= 7 ? 'odd' : 'even',
  }
}

function alertGlyph(severity: string) {
  if (severity === 'critical') return 'alert'
  if (severity === 'action') return 'warning'
  return 'info'
}

function timeAgo(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const hours = Math.max(1, Math.floor(diffMs / (1000 * 60 * 60)))
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function MetricGlyph({ kind }: { kind: string }) {
  switch (kind) {
    case 'fees':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 5h9" /><path d="M7 9h7" /><path d="M9 5c0 6 5 4 5 9 0 2-2 4-5 4" /></svg>
    case 'accreditation':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="8" r="4" /><path d="m9.5 12.5-1 6L12 17l3.5 1.5-1-6" /></svg>
    case 'partners':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M8 8 5 5a2.8 2.8 0 1 0-4 4l3 3" /><path d="m16 8 3-3a2.8 2.8 0 1 1 4 4l-3 3" /><path d="m8 16-3 3a2.8 2.8 0 1 0 4 4l3-3" /><path d="m16 16 3 3a2.8 2.8 0 1 1-4 4l-3-3" /><path d="m9 9 6 6" /></svg>
    case 'alert':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 4 3 20h18L12 4Z" /><path d="M12 9v5" /><path d="M12 17h.01" /></svg>
    case 'calendar':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 3v4M16 3v4M3 10h18" /></svg>
    case 'semester':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 7 12 3l8 4-8 4-8-4Z" /><path d="M6 10v4c0 1.2 2.7 3 6 3s6-1.8 6-3v-4" /></svg>
    case 'clock':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5v5l3.5 2" /></svg>
    case 'book':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 0 4 23V5.5Z" /><path d="M12 3v18" /></svg>
    case 'users':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" /><circle cx="9.5" cy="7" r="4" /><path d="M20 8v6M23 11h-6" /></svg>
    case 'box':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m12 2 9 5-9 5-9-5 9-5Z" /><path d="M3 7v10l9 5 9-5V7" /></svg>
    case 'building':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 21h16" /><path d="M7 21V7l5-3 5 3v14" /><path d="M9 10h.01M15 10h.01M9 14h.01M15 14h.01" /></svg>
    case 'document':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7l-5-5Z" /><path d="M14 2v5h5M9 13h6M9 17h6M9 9h2" /></svg>
    case 'chart':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 20h16" /><path d="M7 16V9M12 16V5M17 16v-3" /></svg>
    case 'warning':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 9v4" /><path d="M12 17h.01" /><path d="M10 3h4l7 14a2 2 0 0 1-1.8 3H4.8A2 2 0 0 1 3 17L10 3Z" /></svg>
    case 'info':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9" /><path d="M12 10v6M12 7h.01" /></svg>
    default:
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9" /></svg>
  }
}
