import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Modal, Spinner } from './kit'

const RUPEE = '\u20B9'
const PERFORMANCE_STATUS_OPTIONS = ['Achieved', 'On Track', 'Attention']
const PERFORMANCE_DIRECTION_OPTIONS = [
  { value: 'up', label: 'Up' },
  { value: 'down', label: 'Down' },
]
const DEFAULT_COMPLIANCE_OPTIONS = [
  { value: 'regulatory', label: 'Regulatory' },
  { value: 'quality', label: 'Quality' },
  { value: 'policy', label: 'Policy' },
  { value: 'risk', label: 'Risk' },
]
type PeriodMode = 'none' | 'preset' | 'custom'
type SemesterMode = 'whole' | 'odd' | 'even'
type RangeMeta = {
  key: string
  semester_label: string
  start: string
  end: string
  label: string
  year: string
  semester: 'odd' | 'even'
} & Record<string, any>

export default function Governance({ user: _user }: { user: any }) {
  const [selectedStart, setSelectedStart] = useState('')
  const [selectedYear, setSelectedYear] = useState('')
  const [selectedSemesterMode, setSelectedSemesterMode] = useState<SemesterMode>('whole')
  const [periodMode, setPeriodMode] = useState<PeriodMode>('preset')
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  const [complianceFilter, setComplianceFilter] = useState('all')
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [editorOpen, setEditorOpen] = useState(false)
  const [draft, setDraft] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const availableRanges = useMemo<RangeMeta[]>(() => {
    if (!data?.range) return []
    const ranges = data.range.available_ranges?.length ? data.range.available_ranges : [data.range]
    return ranges.map(buildRangeMeta)
  }, [data])

  const yearOptions = useMemo(
    () => Array.from(new Set(availableRanges.map(range => range.year))).sort((left, right) => Number(right) - Number(left)),
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

  const serverSelectedRange = useMemo(
    () => availableRanges.find(range => range.key === data?.selected_semester?.key) || null,
    [availableRanges, data?.selected_semester?.key],
  )

  const activeRange = useMemo(
    () =>
      availableRanges.find(range => range.start === selectedStart) ||
      serverSelectedRange ||
      filteredRanges[0] ||
      availableRanges[0] ||
      null,
    [availableRanges, filteredRanges, selectedStart, serverSelectedRange],
  )

  const resolvedYear = selectedYear || serverSelectedRange?.year || availableRanges[0]?.year || String(new Date().getFullYear())
  const scopedRange = useMemo(
    () => buildScopeRange(resolvedYear, selectedSemesterMode),
    [resolvedYear, selectedSemesterMode],
  )

  const queryRange = useMemo(() => {
    if (periodMode === 'none') {
      return {
        start: scopedRange.start,
        end: scopedRange.end,
        label: formatDateRangeLabel(scopedRange.start, scopedRange.end),
      }
    }

    if (periodMode === 'custom') {
      const next = clampRangeToScope(
        customStart || data?.range?.start || scopedRange.start,
        customEnd || data?.range?.end || scopedRange.end,
        scopedRange,
      )
      return {
        ...next,
        label: formatDateRangeLabel(next.start, next.end),
      }
    }

    const presetRange =
      filteredRanges.find(range => range.start === selectedStart) ||
      serverSelectedRange ||
      filteredRanges[0] ||
      availableRanges[0] ||
      null

    if (!presetRange) return { start: '', end: '', label: '' }
    return {
      start: presetRange.start,
      end: presetRange.end,
      label: presetRange.label,
    }
  }, [
    availableRanges,
    customEnd,
    customStart,
    data?.range?.end,
    data?.range?.start,
    filteredRanges,
    periodMode,
    scopedRange,
    selectedStart,
    serverSelectedRange,
  ])

  const rangeLabel = queryRange.label || data?.range?.label || activeRange?.label || formatDateRangeLabel(scopedRange.start, scopedRange.end)

  useEffect(() => {
    if (!availableRanges.length) return
    if (!selectedYear || !yearOptions.includes(selectedYear)) {
      setSelectedYear(serverSelectedRange?.year || availableRanges[0].year)
    }
  }, [availableRanges, selectedYear, serverSelectedRange, yearOptions])

  useEffect(() => {
    if (selectedSemesterMode === 'whole' || !yearScopedRanges.length) return
    if (!yearScopedRanges.some(range => range.semester === selectedSemesterMode)) {
      setSelectedSemesterMode('whole')
    }
  }, [selectedSemesterMode, yearScopedRanges])

  useEffect(() => {
    if (periodMode !== 'preset' || !filteredRanges.length) return
    const currentStart = selectedStart || serverSelectedRange?.start
    if (!filteredRanges.some(range => range.start === currentStart)) {
      setSelectedStart(filteredRanges[0].start)
    }
  }, [filteredRanges, periodMode, selectedStart, serverSelectedRange?.start])

  useEffect(() => {
    if (periodMode !== 'custom') return
    const next = clampRangeToScope(
      customStart || data?.range?.start || scopedRange.start,
      customEnd || data?.range?.end || scopedRange.end,
      scopedRange,
    )
    if (next.start !== customStart) setCustomStart(next.start)
    if (next.end !== customEnd) setCustomEnd(next.end)
  }, [customEnd, customStart, data?.range?.end, data?.range?.start, periodMode, scopedRange])

  useEffect(() => {
    let active = true

    async function load() {
      setLoading(true)
      setError('')

      try {
        const response = await api.governance('', queryRange.start, queryRange.end)
        if (!active) return
        setData(response)
      } catch (err: any) {
        if (!active) return
        setError(err?.message || 'We could not load the governance dashboard.')
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [periodMode, queryRange.end, queryRange.start, reloadKey])

  useEffect(() => {
    setComplianceFilter('all')
  }, [data?.selected_semester?.key])

  useEffect(() => {
    setEditorOpen(false)
    setDraft(null)
    setSaveError('')
  }, [data?.selected_semester?.key, periodMode, queryRange.end, queryRange.start])

  const filteredCompliance = useMemo(() => {
    const items = data?.compliance?.items || []
    if (complianceFilter === 'all') return items
    return items.filter((item: any) => item.category === complianceFilter)
  }, [data, complianceFilter])

  const complianceOptions = useMemo(() => {
    const items = (data?.compliance?.filters || []).filter((option: any) => option.value !== 'all')
    return items.length ? items : DEFAULT_COMPLIANCE_OPTIONS
  }, [data])

  const draftRatio = useMemo(() => {
    if (!draft) return 0
    return calculateRatio(coerceNumber(draft.kpis.students), coerceNumber(draft.kpis.faculty))
  }, [draft])

  const draftUtilization = useMemo(() => {
    if (!draft) return 0
    return calculatePercent(coerceNumber(draft.budget.utilized_crore), coerceNumber(draft.budget.total_crore))
  }, [draft])

  const draftComplianceScore = useMemo(() => {
    if (!draft) return 0
    return calculateComplianceAverage(draft.compliance.items)
  }, [draft])

  const draftComplianceLabel = useMemo(
    () => governanceRating(draftComplianceScore),
    [draftComplianceScore],
  )

  if (loading) return <Spinner />

  if (error || !data) {
    return (
      <div className="chair-panel fade-in">
        <div className="chair-panel-head"><h3>Governance dashboard unavailable</h3></div>
        <div className="card-pad">
          <p style={{ color: 'var(--txt-soft)', lineHeight: 1.7, marginBottom: 16 }}>
            {error || 'The governance dashboard could not be loaded right now.'}
          </p>
          <button className="btn btn-crimson" onClick={() => setReloadKey(key => key + 1)} type="button">
            Try again
          </button>
        </div>
      </div>
    )
  }

  const kpiCards = [
    { key: 'students', label: 'Students', value: formatNumber(data.kpis.students), icon: 'students', tone: 'lavender' },
    { key: 'faculty', label: 'Faculty', value: formatNumber(data.kpis.faculty), icon: 'faculty', tone: 'blue' },
    { key: 'student_faculty_ratio', label: 'Student : Faculty', value: `${trimNumber(data.kpis.student_faculty_ratio)} : 1`, icon: 'ratio', tone: 'green' },
    { key: 'fee_collection_pct', label: 'Fee Collection', value: `${trimNumber(data.kpis.fee_collection_pct)}%`, icon: 'fees', tone: 'mint' },
    { key: 'research_grants', label: 'Research Grants', value: formatCrore(data.kpis.research_grants), icon: 'research', tone: 'gold' },
    { key: 'placement_offers', label: 'Placement Offers', value: formatNumber(data.kpis.placement_offers), icon: 'placements', tone: 'orange' },
    { key: 'average_cgpa', label: 'Average CGPA', value: trimNumber(data.kpis.average_cgpa), icon: 'cgpa', tone: 'rose' },
  ]

  function openEditor() {
    setDraft(createDraft(data))
    setSaveError('')
    setEditorOpen(true)
  }

  function closeEditor() {
    if (saving) return
    setEditorOpen(false)
    setDraft(null)
    setSaveError('')
  }

  function updateDraftField(section: string, key: string, value: string) {
    setDraft((current: any) => ({
      ...current,
      [section]: {
        ...current[section],
        [key]: value,
      },
    }))
  }

  function updateComplianceItem(index: number, key: string, value: string) {
    setDraft((current: any) => ({
      ...current,
      compliance: {
        ...current.compliance,
        items: current.compliance.items.map((item: any, itemIndex: number) =>
          itemIndex === index ? { ...item, [key]: value } : item,
        ),
      },
    }))
  }

  function updatePerformanceItem(index: number, key: string, value: string) {
    setDraft((current: any) => ({
      ...current,
      performance_summary: current.performance_summary.map((item: any, itemIndex: number) =>
        itemIndex === index ? { ...item, [key]: value } : item,
      ),
    }))
  }

  async function saveDraft() {
    if (!draft) return
    setSaving(true)
    setSaveError('')
    try {
      const semesterKey = data.selected_semester.key
      await api.updateGovernance(semesterKey, buildGovernancePayload(draft))
      const refreshed = await api.governance('', queryRange.start, queryRange.end)
      setData(refreshed)
      setComplianceFilter('all')
      setEditorOpen(false)
      setDraft(null)
    } catch (err: any) {
      setSaveError(err?.message || 'We could not save the governance dashboard changes.')
    } finally {
      setSaving(false)
    }
  }

  function handlePeriodModeChange(nextMode: PeriodMode) {
    setPeriodMode(nextMode)
    if (nextMode === 'custom') {
      const next = clampRangeToScope(queryRange.start || scopedRange.start, queryRange.end || scopedRange.end, scopedRange)
      setCustomStart(next.start)
      setCustomEnd(next.end)
      return
    }
    if (!filteredRanges.length) return
    if (!filteredRanges.some(range => range.start === selectedStart)) {
      setSelectedStart(filteredRanges[0].start)
    }
  }

  function handleCustomStartChange(value: string) {
    const nextStart = clampDate(value || scopedRange.start, scopedRange.start, scopedRange.end)
    const nextEnd = customEnd && customEnd >= nextStart ? customEnd : nextStart
    setCustomStart(nextStart)
    setCustomEnd(clampDate(nextEnd, scopedRange.start, scopedRange.end))
  }

  function handleCustomEndChange(value: string) {
    const nextEnd = clampDate(value || customStart || scopedRange.end, scopedRange.start, scopedRange.end)
    const nextStart = customStart && customStart <= nextEnd ? customStart : nextEnd
    setCustomStart(clampDate(nextStart, scopedRange.start, scopedRange.end))
    setCustomEnd(nextEnd)
  }

  return (
    <div className="governance-view fade-in">
      <section className="chair-head-shell gov-head-shell">
        <div className="chair-head-top gov-head-top">
          <div className="chair-topline gov-topline">
            <h1>{data.title}</h1>
            <p>{data.subtitle}</p>
          </div>

          <button
            className={`gov-edit-chip gov-edit-btn ${data.can_edit ? '' : 'disabled'}`}
            disabled={!data.can_edit}
            onClick={openEditor}
            title={data.can_edit ? 'Edit and save this governance dashboard to the database' : 'Your role cannot edit this dashboard'}
            type="button"
          >
            <span className="gov-edit-ico"><GovGlyph kind="edit" /></span>
            <span>Edit Dashboard</span>
          </button>
        </div>

        <div className="chair-toolbar gov-toolbar-chair">
          <label className="chair-filter">
            <span className="chair-filter-label">Year</span>
            <span className="chair-filter-control">
              <GovGlyph kind="calendar" />
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
              <GovGlyph kind="semester" />
              <select value={selectedSemesterMode} onChange={event => setSelectedSemesterMode(event.target.value as SemesterMode)}>
                <option value="whole">Whole</option>
                <option value="odd">Odd semester</option>
                <option value="even">Even semester</option>
              </select>
            </span>
          </label>

          <label className="chair-filter">
            <span className="chair-filter-label">Period</span>
            <span className="chair-filter-control">
              <GovGlyph kind="clock" />
              <select value={periodMode} onChange={event => handlePeriodModeChange(event.target.value as PeriodMode)}>
                <option value="preset">Semester snapshot</option>
                <option value="custom">Custom date range</option>
                <option value="none">None</option>
              </select>
            </span>
          </label>

          {periodMode === 'preset' && (
            <label className="chair-filter chair-filter-span">
              <span className="chair-filter-label">Snapshot</span>
              <span className="chair-filter-control chair-filter-control-wide">
                <GovGlyph kind="calendar" />
                <select value={selectedStart || activeRange?.start || data.range.start} onChange={event => setSelectedStart(event.target.value)}>
                  {filteredRanges.map(range => (
                    <option key={range.key} value={range.start}>{range.label}</option>
                  ))}
                </select>
              </span>
            </label>
          )}

          {periodMode === 'custom' && (
            <div className="chair-date-range-panel">
              <div className="chair-date-range-head">
                <div>
                  <span className="chair-filter-label">Custom range</span>
                  <strong>{rangeLabel}</strong>
                </div>
                <span className="chair-range-badge">Selecting the matching governance snapshot in this year and semester</span>
              </div>

              <div className="chair-date-range-grid">
                <label className="chair-filter">
                  <span className="chair-filter-label">Start date</span>
                  <span className="chair-filter-control">
                    <GovGlyph kind="calendar" />
                    <input
                      type="date"
                      value={customStart}
                      min={scopedRange.start}
                      max={customEnd || scopedRange.end}
                      onChange={event => handleCustomStartChange(event.target.value)}
                    />
                  </span>
                </label>

                <label className="chair-filter">
                  <span className="chair-filter-label">End date</span>
                  <span className="chair-filter-control">
                    <GovGlyph kind="calendar" />
                    <input
                      type="date"
                      value={customEnd}
                      min={customStart || scopedRange.start}
                      max={scopedRange.end}
                      onChange={event => handleCustomEndChange(event.target.value)}
                    />
                  </span>
                </label>
              </div>
            </div>
          )}

          {periodMode === 'none' && (
            <div className="chair-filter-note">
              <span className="chair-filter-note-icon"><GovGlyph kind="info" /></span>
              <div>
                <strong>{rangeLabel}</strong>
                <span>Using only the selected year and semester without an extra period filter.</span>
              </div>
            </div>
          )}
        </div>
      </section>

      <div className="gov-kpi-grid">
        {kpiCards.map(card => (
          <div className="gov-kpi-card" key={card.key}>
            <div className={`gov-kpi-icon ${card.tone}`}>
              <GovGlyph kind={card.icon} />
            </div>
            <div className="gov-kpi-copy">
              <div className="gov-kpi-value">{card.value}</div>
              <div className="gov-kpi-label">{card.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="gov-panel-grid">
        <section className="gov-panel">
          <div className="gov-panel-head">
            <h3>Budget Utilisation</h3>
            <div className="gov-panel-select">{data.selected_semester.label}</div>
          </div>

          <div className="gov-budget-stats">
            <div className="gov-budget-stat">
              <span>Total Budget</span>
              <strong>{formatCrore(data.budget.total)}</strong>
            </div>
            <div className="gov-budget-stat">
              <span>Utilisation</span>
              <strong>{formatCrore(data.budget.utilized)} <em>({trimNumber(data.budget.utilization_pct)}%)</em></strong>
            </div>
          </div>

          <div className="gov-budget-track">
            <div className="gov-budget-fill" style={{ width: `${Math.min(100, Number(data.budget.utilization_pct) || 0)}%` }} />
          </div>
        </section>

        <section className="gov-panel">
          <div className="gov-panel-head">
            <h3>Institutional Compliance</h3>
            <label className="gov-filter-select">
              <select value={complianceFilter} onChange={event => setComplianceFilter(event.target.value)}>
                {(data.compliance.filters || []).map((option: any) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="gov-compliance-body">
            <div className="gov-compliance-score">
              <div className="gov-compliance-ring">
                <div className="gov-compliance-core">
                  <GovGlyph kind="shield" />
                </div>
              </div>
              <div>
                <div className="gov-compliance-label">Compliance Score</div>
                <div className="gov-compliance-value">{trimNumber(data.compliance.score)}%</div>
                <div className="gov-compliance-grade">{data.compliance.label}</div>
              </div>
            </div>

            <div className="gov-compliance-list">
              {filteredCompliance.map((item: any) => (
                <div className="gov-compliance-item" key={item.id}>
                  <div className="gov-compliance-name">
                    <span className="gov-check"><GovGlyph kind="check" /></span>
                    <span>{item.label}</span>
                  </div>
                  <strong>{item.score}%</strong>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      <section className="gov-panel gov-performance-panel">
        <div className="gov-panel-head">
          <h3>Performance Summary</h3>
        </div>

        <div className="gov-table-wrap">
          <table className="gov-table">
            <thead>
              <tr>
                <th>Area</th>
                <th>Metric</th>
                <th>Current Value</th>
                <th>Target</th>
                <th>Status</th>
                <th>Trend</th>
              </tr>
            </thead>
            <tbody>
              {(data.performance_summary || []).map((row: any) => (
                <tr key={row.id}>
                  <td data-label="Area">
                    <div className="gov-area-cell">
                      <span className={`gov-area-icon ${row.icon || 'academics'}`}><GovGlyph kind={row.icon || 'academics'} /></span>
                      <span>{row.area}</span>
                    </div>
                  </td>
                  <td data-label="Metric">{row.metric}</td>
                  <td data-label="Current Value">{row.current_value}</td>
                  <td data-label="Target">{row.target_value}</td>
                  <td data-label="Status">
                    <span className={`gov-status ${statusClass(row.status)}`}>{row.status}</span>
                  </td>
                  <td data-label="Trend">
                    <span className={`gov-trend ${row.trend_direction === 'down' ? 'down' : 'up'}`}>
                      {row.trend_direction === 'down' ? '\u2193' : '\u2191'} {Math.abs(Number(row.trend_pct) || 0)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="gov-table-foot">
          <span className="gov-foot-icon"><GovGlyph kind="info" /></span>
          <span>Data as on {data.last_updated_label}</span>
        </div>
      </section>

      {editorOpen && draft && (
        <Modal
          title={`Edit Dashboard · ${data.selected_semester.label}`}
          className="modal-governance-editor"
          onClose={closeEditor}
          footer={
            <>
              <button className="btn btn-out" disabled={saving} onClick={closeEditor} type="button">Cancel</button>
              <button className="btn btn-crimson" disabled={saving} onClick={saveDraft} type="button">
                {saving ? 'Saving...' : 'Save changes'}
              </button>
            </>
          }
        >
          <div className="gov-editor-shell">
            <div className="gov-editor-note">
              <strong>Changes save directly into the selected semester dashboard in the database.</strong>
              <span>The page refreshes from the backend response after save, so the existing workflow stays intact.</span>
            </div>

            {saveError && <div className="gov-editor-error">{saveError}</div>}

            <section className="gov-editor-section">
              <div className="gov-editor-head">
                <h4>Core Metrics</h4>
                <span>{data.selected_semester.label}</span>
              </div>

              <div className="gov-editor-grid gov-editor-grid-3">
                <Field label="Students">
                  <input className="inp" type="number" min="0" value={draft.kpis.students} onChange={event => updateDraftField('kpis', 'students', event.target.value)} />
                </Field>
                <Field label="Faculty">
                  <input className="inp" type="number" min="0" value={draft.kpis.faculty} onChange={event => updateDraftField('kpis', 'faculty', event.target.value)} />
                </Field>
                <Field label="Fee Collection %">
                  <input className="inp" type="number" min="0" max="100" step="0.1" value={draft.kpis.fee_collection_pct} onChange={event => updateDraftField('kpis', 'fee_collection_pct', event.target.value)} />
                </Field>
                <Field label="Research Grants (Cr)">
                  <input className="inp" type="number" min="0" step="0.01" value={draft.kpis.research_grants_crore} onChange={event => updateDraftField('kpis', 'research_grants_crore', event.target.value)} />
                </Field>
                <Field label="Placement Offers">
                  <input className="inp" type="number" min="0" value={draft.kpis.placement_offers} onChange={event => updateDraftField('kpis', 'placement_offers', event.target.value)} />
                </Field>
                <Field label="Average CGPA">
                  <input className="inp" type="number" min="0" max="10" step="0.01" value={draft.kpis.average_cgpa} onChange={event => updateDraftField('kpis', 'average_cgpa', event.target.value)} />
                </Field>
                <Field label="Total Budget (Cr)">
                  <input className="inp" type="number" min="0" step="0.01" value={draft.budget.total_crore} onChange={event => updateDraftField('budget', 'total_crore', event.target.value)} />
                </Field>
                <Field label="Utilised Budget (Cr)">
                  <input className="inp" type="number" min="0" step="0.01" value={draft.budget.utilized_crore} onChange={event => updateDraftField('budget', 'utilized_crore', event.target.value)} />
                </Field>
                <Field label="As On Date">
                  <input className="inp" type="date" value={draft.last_updated} onChange={event => setDraft((current: any) => ({ ...current, last_updated: event.target.value }))} />
                </Field>
              </div>

              <div className="gov-editor-preview-strip">
                <PreviewStat label="Student : Faculty" value={`${trimNumber(draftRatio)} : 1`} tone="green" />
                <PreviewStat label="Budget Utilisation" value={`${trimNumber(draftUtilization)}%`} tone="gold" />
                <PreviewStat label="Compliance Score" value={`${trimNumber(draftComplianceScore)}% · ${draftComplianceLabel}`} tone="teal" />
              </div>
            </section>

            <section className="gov-editor-section">
              <div className="gov-editor-head">
                <h4>Compliance Metrics</h4>
                <span>These scores drive the compliance summary card.</span>
              </div>

              <div className="gov-edit-list">
                {draft.compliance.items.map((item: any, index: number) => (
                  <div className="gov-edit-row" key={item.id}>
                    <Field label="Metric">
                      <input className="inp" value={item.label} onChange={event => updateComplianceItem(index, 'label', event.target.value)} />
                    </Field>
                    <Field label="Category">
                      <select className="select" value={item.category} onChange={event => updateComplianceItem(index, 'category', event.target.value)}>
                        {complianceOptions.map((option: any) => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Score %">
                      <input className="inp" type="number" min="0" max="100" step="0.1" value={item.score} onChange={event => updateComplianceItem(index, 'score', event.target.value)} />
                    </Field>
                  </div>
                ))}
              </div>
            </section>

            <section className="gov-editor-section">
              <div className="gov-editor-head">
                <h4>Performance Summary</h4>
                <span>Update the values shown in the bottom table.</span>
              </div>

              <div className="gov-perf-edit-list">
                {draft.performance_summary.map((item: any, index: number) => (
                  <div className="gov-perf-editor-card" key={item.id}>
                    <div className="gov-perf-editor-grid">
                      <Field label="Area">
                        <input className="inp" value={item.area} onChange={event => updatePerformanceItem(index, 'area', event.target.value)} />
                      </Field>
                      <Field label="Metric">
                        <input className="inp" value={item.metric} onChange={event => updatePerformanceItem(index, 'metric', event.target.value)} />
                      </Field>
                      <Field label="Current Value">
                        <input className="inp" value={item.current_value} onChange={event => updatePerformanceItem(index, 'current_value', event.target.value)} />
                      </Field>
                      <Field label="Target">
                        <input className="inp" value={item.target_value} onChange={event => updatePerformanceItem(index, 'target_value', event.target.value)} />
                      </Field>
                      <Field label="Status">
                        <select className="select" value={item.status} onChange={event => updatePerformanceItem(index, 'status', event.target.value)}>
                          {PERFORMANCE_STATUS_OPTIONS.map(option => (
                            <option key={option} value={option}>{option}</option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Trend %">
                        <input className="inp" type="number" min="0" step="0.1" value={item.trend_pct} onChange={event => updatePerformanceItem(index, 'trend_pct', event.target.value)} />
                      </Field>
                      <Field label="Direction">
                        <select className="select" value={item.trend_direction} onChange={event => updatePerformanceItem(index, 'trend_direction', event.target.value)}>
                          {PERFORMANCE_DIRECTION_OPTIONS.map(option => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                          ))}
                        </select>
                      </Field>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </Modal>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: any }) {
  return (
    <div className="form-row">
      <label>{label}</label>
      {children}
    </div>
  )
}

function PreviewStat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className={`gov-editor-preview ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function buildRangeMeta(range: any): RangeMeta {
  const [yearPart = '', monthPart = '1'] = String(range?.start || '').split('-')
  const year = String(Number(yearPart) || new Date().getFullYear())
  const month = Number(monthPart) || 1
  return {
    ...range,
    year,
    semester: month >= 7 ? 'odd' : 'even',
  }
}

function buildScopeRange(year: string, semester: SemesterMode) {
  const safeYear = Number(year) || new Date().getFullYear()
  if (semester === 'odd') {
    return {
      start: `${safeYear}-07-01`,
      end: `${safeYear}-12-31`,
    }
  }
  if (semester === 'even') {
    return {
      start: `${safeYear}-01-01`,
      end: `${safeYear}-06-30`,
    }
  }
  return {
    start: `${safeYear}-01-01`,
    end: `${safeYear}-12-31`,
  }
}

function clampDate(value: string, min: string, max: string) {
  if (!value) return min
  if (value < min) return min
  if (value > max) return max
  return value
}

function clampRangeToScope(start: string, end: string, scope: { start: string; end: string }) {
  const safeStart = clampDate(start || scope.start, scope.start, scope.end)
  const safeEnd = clampDate(end || scope.end, scope.start, scope.end)
  if (safeStart <= safeEnd) {
    return { start: safeStart, end: safeEnd }
  }
  return { start: safeEnd, end: safeEnd }
}

function formatDateRangeLabel(start: string, end: string) {
  if (!start || !end) return ''
  const from = new Date(`${start}T00:00:00`)
  const to = new Date(`${end}T00:00:00`)
  const sameYear = from.getFullYear() === to.getFullYear()
  if (start === end) {
    return from.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
  }
  if (sameYear) {
    return `${from.toLocaleString('en-IN', { day: '2-digit', month: 'short' })} - ${to.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}`
  }
  return `${from.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })} - ${to.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}`
}

function GovGlyph({ kind }: { kind: string }) {
  switch (kind) {
    case 'calendar':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="5" width="18" height="16" rx="2" />
          <path d="M8 3v4M16 3v4M3 10h18" />
        </svg>
      )
    case 'students':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      )
    case 'faculty':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="4" width="18" height="14" rx="2" />
          <path d="M7 8h4" />
          <path d="M7 12h4" />
          <path d="M15 7l2 2-4 4-2 .5.5-2z" />
          <path d="M8 20h8" />
        </svg>
      )
    case 'ratio':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="8" cy="8" r="3" />
          <circle cx="16" cy="8" r="3" />
          <path d="M3 20a5 5 0 0 1 10 0" />
          <path d="M11 20a5 5 0 0 1 10 0" />
        </svg>
      )
    case 'fees':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3v18" />
          <path d="M16.5 7.5c0-1.93-2.01-3.5-4.5-3.5s-4.5 1.57-4.5 3.5S9.51 11 12 11s4.5 1.57 4.5 3.5S14.49 18 12 18s-4.5-1.57-4.5-3.5" />
        </svg>
      )
    case 'research':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 2v6l-5.5 9.5A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-3.5L14 8V2" />
          <path d="M8 2h8" />
          <path d="M8 14h8" />
        </svg>
      )
    case 'placements':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="7" width="18" height="12" rx="2" />
          <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          <path d="M3 12h18" />
        </svg>
      )
    case 'academics':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2 8l10-5 10 5-10 5-10-5z" />
          <path d="M6 10.5V15c0 1.7 2.7 3.5 6 3.5s6-1.8 6-3.5v-4.5" />
        </svg>
      )
    case 'finance':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3v18" />
          <path d="M16.5 7.5c0-1.93-2.01-3.5-4.5-3.5s-4.5 1.57-4.5 3.5S9.51 11 12 11s4.5 1.57 4.5 3.5S14.49 18 12 18s-4.5-1.57-4.5-3.5" />
        </svg>
      )
    case 'cgpa':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <path d="M5 19V9" />
          <path d="M12 19V5" />
          <path d="M19 19v-8" />
          <path d="M3 19h18" />
        </svg>
      )
    case 'semester':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 7l8-4 8 4-8 4-8-4z" />
          <path d="M6 10v4c0 1.2 2.7 3 6 3s6-1.8 6-3v-4" />
        </svg>
      )
    case 'clock':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="8.5" />
          <path d="M12 7.5v5l3.5 2" />
        </svg>
      )
    case 'edit':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
        </svg>
      )
    case 'shield':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3l7 4v5c0 4.5-3 7.9-7 9-4-1.1-7-4.5-7-9V7l7-4z" />
          <path d="M9 12l2 2 4-4" />
        </svg>
      )
    case 'check':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
      )
    case 'info':
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 10v6" />
          <path d="M12 7h.01" />
        </svg>
      )
    default:
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="8" />
        </svg>
      )
  }
}

function createDraft(source: any) {
  return {
    kpis: {
      students: String(source.kpis.students ?? ''),
      faculty: String(source.kpis.faculty ?? ''),
      fee_collection_pct: trimNumber(source.kpis.fee_collection_pct ?? 0),
      research_grants_crore: toCroreInput(source.kpis.research_grants),
      placement_offers: String(source.kpis.placement_offers ?? ''),
      average_cgpa: trimNumber(source.kpis.average_cgpa ?? 0),
    },
    budget: {
      total_crore: toCroreInput(source.budget.total),
      utilized_crore: toCroreInput(source.budget.utilized),
    },
    compliance: {
      items: (source.compliance.items || []).map((item: any) => ({
        id: item.id,
        label: item.label,
        category: item.category || 'all',
        score: trimNumber(item.score ?? 0),
      })),
    },
    performance_summary: (source.performance_summary || []).map((row: any) => ({
      id: row.id,
      area: row.area,
      metric: row.metric,
      current_value: row.current_value,
      target_value: row.target_value,
      status: row.status,
      trend_pct: trimNumber(row.trend_pct ?? 0),
      trend_direction: row.trend_direction || 'up',
      icon: row.icon || derivePerformanceIcon(row.area),
    })),
    last_updated: source.last_updated || '',
  }
}

function buildGovernancePayload(draft: any) {
  const students = coerceNumber(draft.kpis.students)
  const faculty = coerceNumber(draft.kpis.faculty)
  const complianceItems = draft.compliance.items.map((item: any) => {
    const score = clamp(coerceNumber(item.score), 0, 100)
    return {
      id: item.id,
      category: item.category || 'all',
      label: (item.label || '').trim() || 'Compliance Metric',
      score,
      status: complianceStatus(score),
    }
  })
  const complianceScore = calculateComplianceAverage(complianceItems)

  return {
    kpis: {
      students: Math.round(students),
      faculty: Math.round(faculty),
      student_faculty_ratio: calculateRatio(students, faculty),
      fee_collection_pct: clamp(coerceNumber(draft.kpis.fee_collection_pct), 0, 100),
      research_grants: coerceNumber(draft.kpis.research_grants_crore) * 1e7,
      placement_offers: Math.round(coerceNumber(draft.kpis.placement_offers)),
      average_cgpa: coerceNumber(draft.kpis.average_cgpa),
    },
    budget: {
      total: coerceNumber(draft.budget.total_crore) * 1e7,
      utilized: coerceNumber(draft.budget.utilized_crore) * 1e7,
    },
    compliance: {
      score: complianceScore,
      label: governanceRating(complianceScore),
      items: complianceItems,
    },
    performance_summary: draft.performance_summary.map((item: any) => ({
      id: item.id,
      area: (item.area || '').trim() || 'Area',
      metric: (item.metric || '').trim() || 'Metric',
      current_value: (item.current_value || '').trim() || '0',
      target_value: (item.target_value || '').trim() || '0',
      status: item.status || 'On Track',
      trend_pct: Math.abs(coerceNumber(item.trend_pct)),
      trend_direction: item.trend_direction === 'down' ? 'down' : 'up',
      icon: derivePerformanceIcon(item.area, item.icon),
    })),
    last_updated: draft.last_updated || null,
  }
}

function derivePerformanceIcon(area: string, fallback = '') {
  const key = (area || '').trim().toLowerCase()
  if (key.includes('finance')) return 'finance'
  if (key.includes('placement')) return 'placements'
  if (key.includes('research')) return 'research'
  if (key.includes('student')) return 'students'
  if (key.includes('faculty')) return 'faculty'
  return fallback || 'academics'
}

function governanceRating(score: number) {
  if (score >= 90) return 'Excellent'
  if (score >= 80) return 'Strong'
  if (score >= 70) return 'On Track'
  return 'Needs Attention'
}

function complianceStatus(score: number) {
  if (score >= 80) return 'healthy'
  if (score >= 60) return 'normal'
  return 'degraded'
}

function calculateRatio(students: number, faculty: number) {
  if (!faculty) return 0
  return roundTo(students / faculty, 1)
}

function calculatePercent(part: number, total: number) {
  if (!total) return 0
  return roundTo((part / total) * 100, 1)
}

function calculateComplianceAverage(items: any[]) {
  if (!items.length) return 0
  const total = items.reduce((sum, item) => sum + coerceNumber(item.score), 0)
  return roundTo(total / items.length, 1)
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function coerceNumber(value: any) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function roundTo(value: number, places = 1) {
  const factor = 10 ** places
  return Math.round(value * factor) / factor
}

function toCroreInput(value: number) {
  return trimNumber((Number(value || 0) / 1e7))
}

function formatCrore(value: number) {
  return `${RUPEE}${(Number(value || 0) / 1e7).toFixed(2)} Cr`
}

function formatNumber(value: number) {
  return Number(value || 0).toLocaleString('en-IN')
}

function trimNumber(value: number) {
  return Number(value || 0).toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1')
}

function statusClass(status: string) {
  const key = status.toLowerCase().replace(/[^a-z0-9]+/g, '-')
  if (key.includes('achieved')) return 'achieved'
  if (key.includes('track')) return 'track'
  return 'attention'
}
