/**
 * Campus Head page components.
 * Phase 2 keeps all functionality view-only and uses existing APIs/data only.
 */

import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { StatePill, money } from '../views/ui'

export function CampusProfile() {
  const [office, setOffice] = useState<any>(null)

  useEffect(() => {
    api.office(3).then(setOffice).catch(() => setOffice(null))
  }, [])

  return (
    <div className="fade-in campus-head-page">
      <div className="page-head">
        <h1>Campus Profile</h1>
        <p>Assigned campus and branch information for executive oversight.</p>
      </div>

      <div className="campus-head-panel">
        {office ? (
          <div className="campus-head-plan">
            <div className="plan-row"><label>Office</label><strong>{office.name || 'Campus Head Office'}</strong></div>
            <div className="plan-row"><label>Level</label><strong>{office.level || '3'}</strong></div>
            <div className="plan-row"><label>Scope</label><strong>{office.scope || 'Campus scope'}</strong></div>
            <div className="plan-row"><label>Purpose</label><strong>{office.purpose || 'Campus leadership oversight'}</strong></div>
            <div className="plan-row"><label>Reports to</label><strong>{office.reports_to || 'Vice Chairman'}</strong></div>
            <div className="plan-row"><label>Modules</label><strong>{(office.modules || []).join(', ') || 'Not available yet'}</strong></div>
          </div>
        ) : (
          <EmptyState text="No campus profile data available yet" />
        )}
      </div>
    </div>
  )
}

export function BranchOperationalPlan() {
  const [plan, setPlan] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')

  function load() {
    setLoading(true)
    api.bop().then((response: any) => setPlan(response.plan || null)).catch((err: any) => setError(err?.message || 'Unable to load the Branch Operational Plan.')).finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function submitPlan() {
    if (!plan?.id) return
    try {
      const response = plan.status === 'returned' ? await api.resubmitBop(plan.id) : await api.submitBop(plan.id)
      setPlan(response)
    } catch (err: any) {
      setError(err?.message || 'Unable to submit the Branch Operational Plan.')
    }
  }

  if (loading) return <div className="fade-in campus-head-page"><div className="page-head"><h1>Branch Operational Plan</h1></div><div className="campus-head-panel"><EmptyState text="Loading plan data..." /></div></div>

  return (
    <div className="fade-in campus-head-page">
      <div className="page-head">
        <h1>Branch Operational Plan</h1>
        <p>Campus-scoped plan submission and Vice Chairman review status.</p>
      </div>
      {error && <div className="campus-head-panel"><EmptyState text={error} /></div>}
      {!plan && !editing && <div className="campus-head-panel">
        <EmptyState text="No Branch Operational Plan has been created for this campus yet" />
        <button className="btn btn-crimson" onClick={() => setEditing(true)} type="button">Create BOP</button>
      </div>}
      {plan && !editing && <BOPSummary plan={plan} onEdit={() => setEditing(true)} onSubmit={submitPlan} />}
      {editing && <BOPEditor initial={plan} onCancel={() => setEditing(false)} onSaved={(next: any) => { setPlan(next); setEditing(false) }} />}
    </div>
  )
}

function BOPSummary({ plan, onEdit, onSubmit }: { plan: any; onEdit: () => void; onSubmit: () => void }) {
  const editable = plan.status === 'draft' || plan.status === 'returned'
  const submittable = plan.status === 'draft' || plan.status === 'returned'
  return <>
      <div className="campus-head-panel">
        <div className="campus-head-plan">
          <div className="plan-row"><label>Plan title</label><strong>{plan.title}</strong></div>
          <div className="plan-row"><label>Campus</label><strong>{plan.campus || 'Not available yet'}</strong></div>
          <div className="plan-row"><label>Planning period</label><strong>{plan.planning_period || 'Not available yet'}</strong></div>
          <div className="plan-row"><label>Status</label><strong>{plan.status}</strong></div>
          <div className="plan-row"><label>Created by</label><strong>{plan.created_by}</strong></div>
          <div className="plan-row"><label>VC feedback</label><strong>{plan.vc_review?.feedback || 'Not available yet'}</strong></div>
        </div>
        {plan.submission?.submitted_at && <p className="campus-head-caption">Submitted {new Date(plan.submission.submitted_at).toLocaleString()}</p>}
        <div className="row-actions">
          {editable && <button className="btn btn-out" onClick={onEdit} type="button">Edit</button>}
          {submittable && <button className="btn btn-crimson" onClick={onSubmit} type="button">{plan.status === 'returned' ? 'Resubmit' : 'Submit for review'}</button>}
        </div>
      </div>
      <div className="campus-head-grid campus-head-mid-grid">
        <BOPSection title="Strategic alignment" value={plan.strategic_alignment} />
        <BOPSection title="Timeline" value={plan.timeline} />
        <BOPSection title="Initiatives" items={plan.initiatives} />
        <BOPSection title="Activities" items={plan.activities} />
        <BOPSection title="Responsible areas" items={plan.responsible_areas} />
        <BOPSection title="Required resources" items={plan.resources} />
        <BOPSection title="KPI references" items={plan.kpi_references} />
        <BOPSection title="Risks and dependencies" items={plan.risks} />
        <BOPSection title="Notes" value={plan.notes} />
      </div>
    </>
}

function BOPSection({ title, value, items = [] }: { title: string; value?: string; items?: string[] }) {
  const available = value || items.length
  return <section className="campus-head-panel"><header className="campus-head-panel-header"><h2>{title}</h2></header><div className="card-pad">{available ? value || <ul className="bullet-list">{items.map(item => <li key={item}>{item}</li>)}</ul> : <EmptyState text="Not available yet" />}</div></section>
}

const EMPTY_BOP = {
  title: '', planning_period: '', strategic_alignment: '', initiatives: [], activities: [],
  responsible_areas: [], resources: [], timeline: '', kpi_references: [], risks: [], notes: '',
}

function BOPEditor({ initial, onCancel, onSaved }: { initial: any; onCancel: () => void; onSaved: (plan: any) => void }) {
  const [form, setForm] = useState<any>({ ...EMPTY_BOP, ...(initial || {}) })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (key: string, value: any) => setForm((current: any) => ({ ...current, [key]: value }))
  const setList = (key: string, value: string) => set(key, value.split('\n'))
  async function save() {
    setBusy(true); setError('')
    try {
      const body = { ...form, initiatives: form.initiatives, activities: form.activities, responsible_areas: form.responsible_areas, resources: form.resources, kpi_references: form.kpi_references, risks: form.risks }
      const next = initial?.id ? await api.updateBop(initial.id, body) : await api.createBop(body)
      onSaved(next)
    } catch (err: any) { setError(err?.message || 'Unable to save the draft.') }
    finally { setBusy(false) }
  }
  return <div className="campus-head-panel">
    <header className="campus-head-panel-header"><h2>{initial?.id ? 'Edit Branch Operational Plan' : 'Create Branch Operational Plan'}</h2></header>
    {error && <EmptyState text={error} />}
    <div className="card-pad" style={{ display: 'grid', gap: 14 }}>
      <label className="form-row"><span>Plan title</span><input className="inp" value={form.title} onChange={e => set('title', e.target.value)} /></label>
      <label className="form-row"><span>Planning period</span><input className="inp" value={form.planning_period} onChange={e => set('planning_period', e.target.value)} placeholder="Academic year or period" /></label>
      <label className="form-row"><span>Strategic alignment</span><textarea className="inp" rows={3} value={form.strategic_alignment} onChange={e => set('strategic_alignment', e.target.value)} /></label>
      {(['initiatives', 'activities', 'responsible_areas', 'resources', 'kpi_references', 'risks'] as const).map(key => <label className="form-row" key={key}><span>{key.replace('_', ' ')}</span><textarea className="inp" rows={3} value={(form[key] || []).join('\n')} onChange={e => setList(key, e.target.value)} placeholder="One item per line" /></label>)}
      <label className="form-row"><span>Timeline</span><textarea className="inp" rows={3} value={form.timeline} onChange={e => set('timeline', e.target.value)} /></label>
      <label className="form-row"><span>Notes</span><textarea className="inp" rows={3} value={form.notes} onChange={e => set('notes', e.target.value)} /></label>
      <div className="row-actions"><button className="btn btn-out" onClick={onCancel} type="button">Cancel</button><button className="btn btn-crimson" onClick={save} disabled={busy} type="button">{busy ? 'Saving...' : 'Save Draft'}</button></div>
    </div>
  </div>
}

export function DepartmentsPrograms() {
  const [overview, setOverview] = useState<any>(null)
  useEffect(() => {
    api.overview().then(setOverview).catch(() => setOverview(null))
  }, [])

  const rows = Object.entries(overview?.dept_distribution || {})
  return (
    <div className="fade-in campus-head-page">
      <div className="page-head">
        <h1>Departments & Programs</h1>
        <p>Department-level structure and current enrollment mix.</p>
      </div>
      <div className="campus-head-panel">
        {rows.length ? (
          <div className="campus-head-table-wrap">
            <table className="campus-head-table">
              <thead>
                <tr><th>Department</th><th>Students</th><th>Program mix</th><th>Status</th></tr>
              </thead>
              <tbody>
                {rows.map(([department, count]) => (
                  <tr key={department}>
                    <td>{department}</td>
                    <td>{String(count)}</td>
                    <td>Not available yet</td>
                    <td><span className="status-chip status-monitoring">Monitoring</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState text="No department and program data available yet" />
        )}
      </div>
    </div>
  )
}

export function LeadershipTeam() {
  const [staff, setStaff] = useState<any>({ staff: [] })
  useEffect(() => {
    api.facultyStaff('', '', '', 1, {}).then(setStaff).catch(() => setStaff({ staff: [] }))
  }, [])

  const rows = staff.staff || []
  return (
    <div className="fade-in campus-head-page">
      <div className="page-head">
        <h1>Leadership Team</h1>
        <p>Read-only view of senior administrative and academic leadership information.</p>
      </div>
      <div className="campus-head-panel">
        {rows.length ? (
          <div className="campus-head-list">
            {rows.slice(0, 12).map((member: any) => (
              <div key={member.id || member.name} className="list-item">
                <div>
                  <strong>{member.name || 'Leadership member'}</strong>
                  <small>{member.designation || member.role || 'Leadership role'} · {member.department || 'Office'}</small>
                </div>
                <span className="status-chip status-approved">Visible</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState text="No leadership team data available yet" />
        )}
      </div>
    </div>
  )
}

export function AcademicSnapshot() {
  const [overview, setOverview] = useState<any>(null)
  const [calendar, setCalendar] = useState<any>(null)

  useEffect(() => {
    Promise.all([
      api.overview().catch(() => null),
      api.academicCalendar().catch(() => null),
    ]).then(([overviewData, calendarData]) => {
      setOverview(overviewData)
      setCalendar(calendarData)
    })
  }, [])

  const stats = overview?.stats || {}
  return (
    <div className="fade-in campus-head-page">
      <div className="page-head">
        <h1>Academic Snapshot</h1>
        <p>Campus academic summary based on existing available records.</p>
      </div>
      <div className="campus-head-panel">
        <div className="campus-head-metrics">
          <div className="campus-head-metric"><label>Students</label><strong>{n(stats.students, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>Faculty</label><strong>{n(stats.faculty, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>Courses</label><strong>{n(stats.courses, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>Sections</label><strong>{n(stats.sections, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>Academic term</label><strong>{n(calendar?.selected_term, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>Placement offers</label><strong>{n(stats.placement_offers, 'Not available yet')}</strong></div>
        </div>
      </div>
    </div>
  )
}

export function StudentSnapshot() {
  const [students, setStudents] = useState<any>({ summary: {}, departments: [], students: [] })
  useEffect(() => {
    api.students('', '', 1, 25, {}).then(setStudents).catch(() => setStudents({ summary: {}, departments: [], students: [] }))
  }, [])

  const summary = students.summary || {}
  return (
    <div className="fade-in campus-head-page">
      <div className="page-head">
        <h1>Student Snapshot</h1>
        <p>Student population and status summary using existing records.</p>
      </div>
      <div className="campus-head-panel">
        <div className="campus-head-metrics">
          <div className="campus-head-metric"><label>All students</label><strong>{n(summary.all_students, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>At risk</label><strong>{n(summary.at_risk, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>Departments</label><strong>{(students.departments || []).length || 'Not available yet'}</strong></div>
          <div className="campus-head-metric"><label>Open grievances</label><strong>{n(summary.open_grievances, 'Not available yet')}</strong></div>
        </div>
      </div>
    </div>
  )
}

export function WorkforceOverview() {
  const [faculty, setFaculty] = useState<any>({ summary: {}, staff: [] })
  useEffect(() => {
    api.facultyStaff('', '', '', 1, {}).then(setFaculty).catch(() => setFaculty({ summary: {}, staff: [] }))
  }, [])

  const summary = faculty.summary || {}
  return (
    <div className="fade-in campus-head-page">
      <div className="page-head">
        <h1>Workforce</h1>
        <p>Read-only workforce summary for the campus.</p>
      </div>
      <div className="campus-head-panel">
        <div className="campus-head-metrics">
          <div className="campus-head-metric"><label>Total staff</label><strong>{n(summary.total, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>Faculty</label><strong>{n(summary.faculty, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>Administrative</label><strong>{n(summary.administrative, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>Support</label><strong>{n(summary.support, 'Not available yet')}</strong></div>
        </div>
      </div>
    </div>
  )
}

export function InfrastructureOverview() {
  const [assets, setAssets] = useState<any>({ summary: {}, assets: [], category_summary: [] })
  useEffect(() => {
    api.assets().then(setAssets).catch(() => setAssets({ summary: {}, assets: [], category_summary: [] }))
  }, [])

  const summary = assets.summary || {}
  const unavailable = assets.data_status === 'unavailable'
  return (
    <div className="fade-in campus-head-page">
      <div className="page-head">
        <h1>Infrastructure</h1>
        <p>Campus asset and infrastructure status based on currently available asset inventory.</p>
      </div>
      <div className="campus-head-panel">
        {unavailable ? <EmptyState text={assets.reason || 'Campus-scoped infrastructure data is unavailable.'} /> : <div className="campus-head-metrics">
          <div className="campus-head-metric"><label>Total tracked assets</label><strong>{n(summary.total, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>Book value</label><strong>{currency(summary.book_value)}</strong></div>
          <div className="campus-head-metric"><label>In service</label><strong>{n(summary.in_service, 'Not available yet')}</strong></div>
          <div className="campus-head-metric"><label>Needs attention</label><strong>{n(summary.maintenance, 'Not available yet')}</strong></div>
        </div>}
        {!unavailable && assets.assets?.length ? <div className="tbl-scroll" style={{ marginTop: 18 }}><table className="tbl"><thead><tr><th>Asset</th><th>Category</th><th>Location</th><th>Status</th><th>Value</th></tr></thead><tbody>{assets.assets.map((asset: any) => <tr key={asset.id}><td><b>{asset.name}</b><br /><small className="mono">{asset.tag}</small></td><td>{asset.category}</td><td>{asset.location}</td><td>{asset.status}</td><td>{currency(asset.value)}</td></tr>)}</tbody></table></div> : null}
      </div>
    </div>
  )
}

export function CampusHeadApprovals() {
  const [workflows, setWorkflows] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState('')

  function load() {
    setLoading(true)
    api.workflows('inbox').then((response: any) => setWorkflows(response.workflows || [])).catch((err: any) => setError(err?.message || 'Unable to load approvals.')).finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function decide(workflowId: string, action: string) {
    setBusy(`${workflowId}:${action}`); setError('')
    try { await api.decideWorkflow(workflowId, action, reason); setReason(''); load() }
    catch (err: any) { setError(err?.message || `Unable to ${action} this request.`) }
    finally { setBusy('') }
  }

  return <div className="fade-in campus-head-page">
    <div className="page-head"><h1>My Approvals</h1><p>Campus-scoped requests awaiting an authorized Campus Head action.</p></div>
    {error && <div className="campus-head-panel"><EmptyState text={error} /></div>}
    {loading ? <div className="campus-head-panel"><EmptyState text="Loading approval requests..." /></div> : workflows.length ? <div className="campus-head-approval-list">{workflows.map((workflow: any) => {
      let profile: any = {}
      try { profile = JSON.parse(workflow.profile?.notes || '{}') } catch { profile = {} }
      return <article className="campus-head-panel campus-head-approval-card" key={workflow.id}>
        <div className="campus-head-approval-heading"><div><h2>{workflow.label || 'Workflow request'}</h2><strong>{workflow.title || 'Request details unavailable'}</strong></div><StatePill s={workflow.state} /></div>
        <div className="campus-head-approval-meta">
          <div><label>Requester</label><strong>{workflow.initiator || 'Requester unavailable'}</strong></div>
          <div><label>Amount</label><strong>{money(workflow.amount)}</strong></div>
          <div><label>Campus</label><strong>{profile.campus || 'Campus unavailable'}</strong></div>
          <div><label>Workflow stage</label><strong>{workflow.current_stage ?? 0} / {workflow.chain?.length || 0}</strong></div>
          <div><label>Submitted</label><strong>{workflow.created_at ? new Date(workflow.created_at).toLocaleString() : 'Date unavailable'}</strong></div>
          <div><label>Authority result</label><strong>{workflow.action_message || 'No authorized action available'}</strong></div>
        </div>
        {workflow.available_actions?.length ? <><label className="workflow-field campus-head-approval-reason">Reason / remarks<textarea className="inp" value={reason} onChange={e => setReason(e.target.value)} placeholder="Optional remarks" /></label><div className="row-actions">{workflow.available_actions.map((action: string) => <button className={`btn ${action === 'reject' ? 'btn-out' : 'btn-crimson'}`} key={action} disabled={!!busy} onClick={() => decide(workflow.id, action)}>{busy === `${workflow.id}:${action}` ? 'Working...' : action[0].toUpperCase() + action.slice(1)}</button>)}</div></> : null}
      </article>
    })}</div> : <div className="campus-head-panel"><EmptyState text="No requests are awaiting an authorized Campus Head action." /></div>}
  </div>
}

export function MyRequests() {
  return (
    <div className="fade-in campus-head-page">
      <div className="page-head">
        <h1>My Requests</h1>
        <p>Campus Head request tracking is read-only in this phase.</p>
      </div>
      <div className="campus-head-panel">
        <EmptyState text="No request data available yet" />
      </div>
    </div>
  )
}

export function PolicyRepository() {
  const [catalog, setCatalog] = useState<any>(null)
  useEffect(() => {
    api.catalog().then(setCatalog).catch(() => setCatalog(null))
  }, [])

  const items = catalog?.policies || [{ title: 'Institutional policy registry', description: 'Not available yet' }]
  return (
    <div className="fade-in campus-head-page">
      <div className="page-head">
        <h1>Policy Repository</h1>
        <p>Institutional policy and reference documents currently available to this office.</p>
      </div>
      <div className="campus-head-panel">
        <div className="campus-head-list">
          {items.map((item: any, index: number) => (
            <div key={item.title || index} className="list-item">
              <div>
                <strong>{item.title || 'Policy reference'}</strong>
                <small>{item.description || 'No data available'}</small>
              </div>
              <span className="status-chip status-monitoring">Read-only</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function n(value: any, empty = 'Not available yet') {
  if (value === null || value === undefined || value === '' || value === '—') return empty
  return value
}

function currency(value: any) {
  if (value === null || value === undefined || value === '') return 'Not available yet'
  const number = Number(value)
  if (!Number.isFinite(number)) return 'Not available yet'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(number)
}

function percent(value: any) {
  if (value === null || value === undefined || value === '') return 'Not available yet'
  const number = Number(value)
  if (!Number.isFinite(number)) return 'Not available yet'
  return `${number.toFixed(1)}%`
}

function academicYearFromTerm(term: string) {
  const match = String(term || '').match(/(\d{4})/)
  if (!match) return 'Not available yet'
  const start = Number(match[1])
  return `${start}-${String(start + 1).slice(-2)}`
}

export function CampusHeadDashboard({ user, go, pageTitle }: { user: any; go: (view: string) => void; pageTitle?: string }) {
  const [overview, setOverview] = useState<any>(null)
  const [riskSummary, setRiskSummary] = useState<any>({})
  const [inbox, setInbox] = useState<any>({ workflows: [] })
  const [escalations, setEscalations] = useState<any>({ incoming: [], outgoing: [] })
  const [grievance, setGrievance] = useState<any>({ complaints: [] })
  const [students, setStudents] = useState<any>({ summary: {}, departments: [], students: [] })
  const [faculty, setFaculty] = useState<any>({ summary: {}, staff: [] })
  const [budget, setBudget] = useState<any>({ budget: [] })
  const [invoices, setInvoices] = useState<any>({ invoices: [], summary: {} })
  const [assets, setAssets] = useState<any>({ assets: [], summary: {}, category_summary: [] })
  const [calendar, setCalendar] = useState<any>({})
  const [notifications, setNotifications] = useState<any[]>([])
  const [bop, setBop] = useState<any>({ plan: null })
  const [reports, setReports] = useState<any[]>([])

  useEffect(() => {
    let active = true
    Promise.all([
      api.overview(),
      api.workflows('inbox'),
      api.escalations(),
      api.grievance(),
      api.riskSummary(),
      api.students('', '', 1, 25, {}),
      api.facultyStaff('', '', '', 1, {}),
      api.budget(),
      api.invoices(),
      api.assets(),
      api.academicCalendar(),
      api.notifications(),
      api.bop(),
    ]).then(([overviewRes, inboxRes, escalationsRes, grievanceRes, riskSummaryRes, studentsRes, facultyRes, budgetRes, invoicesRes, assetsRes, calendarRes, notificationsRes, bopRes]) => {
      if (!active) return
      setOverview(overviewRes)
      setInbox(inboxRes || { workflows: [] })
      setEscalations(escalationsRes || { incoming: [], outgoing: [] })
      setGrievance(grievanceRes || { complaints: [] })
      setRiskSummary(riskSummaryRes?.summary || {})
      setStudents(studentsRes || { summary: {}, departments: [], students: [] })
      setFaculty(facultyRes || { summary: {}, staff: [] })
      setBudget(budgetRes || { budget: [] })
      setInvoices(invoicesRes || { invoices: [], summary: {} })
      setAssets(assetsRes || { assets: [], summary: {}, category_summary: [] })
      setCalendar(calendarRes || {})
      setNotifications((notificationsRes?.notifications || []).slice(0, 6))
      setBop(bopRes || { plan: null })
    }).catch(() => {
      if (active) {
        setOverview({ stats: {}, dept_distribution: {} })
        setInbox({ workflows: [] })
        setEscalations({ incoming: [], outgoing: [] })
        setGrievance({ complaints: [] })
        setRiskSummary({})
        setStudents({ summary: {}, departments: [], students: [] })
        setFaculty({ summary: {}, staff: [] })
        setBudget({ budget: [] })
        setInvoices({ invoices: [], summary: {} })
        setAssets({ assets: [], summary: {}, category_summary: [] })
        setCalendar({})
        setNotifications([])
        setBop({ plan: null })
      }
    })
    return () => { active = false }
  }, [user?.office_n])

  useEffect(() => {
    api.campusReports().then((response: any) => setReports(response.reports || [])).catch(() => setReports([]))
  }, [user?.office_n])

  const deptRows = useMemo(() => {
    const fromOverview = Object.entries(overview?.dept_distribution || {})
    if (fromOverview.length) {
      return fromOverview.map(([department, count]) => ({ department: String(department), value: Number(count) || 0, status: 'Monitoring', trend: '—' }))
    }
    return (students?.departments || []).map((item: any) => ({
      department: item.name || item.code || 'Department',
      value: Number(item.count) || 0,
      status: 'Monitoring',
      trend: '—',
    }))
  }, [overview, students])

  const pendingApprovals = useMemo(() => {
    const rows = inbox?.workflows || []
    return rows.filter((item: any) => !['approved', 'executed', 'rejected', 'completed'].includes(String(item.state || '').toLowerCase()))
  }, [inbox])

  const complaintCounts = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0, resolved: 0, escalated: 0 }
    for (const item of grievance?.complaints || []) {
      const level = String(item.severity || '').toLowerCase()
      const status = String(item.status || '').toLowerCase()
      if (level === 'critical') counts.critical += 1
      if (level === 'high') counts.high += 1
      if (level === 'medium') counts.medium += 1
      if (level === 'low') counts.low += 1
      if (status === 'resolved') counts.resolved += 1
      if (status === 'escalated' || status === 'escalation') counts.escalated += 1
    }
    return counts
  }, [grievance])

  const campusName = user?.scope || user?.campus || 'Main Campus'
  const academicYear = academicYearFromTerm(calendar?.selected_term || '')
  const budgetTotal = (budget?.budget || []).reduce((sum: number, row: any) => sum + Number(row.allocated || 0), 0)
  const spentTotal = (budget?.budget || []).reduce((sum: number, row: any) => sum + Number(row.spent || 0), 0)
  const outstandingFees = Number(invoices?.summary?.outstanding || 0)
  const riskCounts = riskSummary || {}
  const summaryCards = [
    { title: 'Campus KPI Snapshot', value: String((riskCounts.open || 0) + (riskCounts.high_critical || 0)), detail: (riskCounts.open || riskCounts.high_critical) ? 'Live risk indicators for this campus' : 'No active campus KPI snapshot yet', tone: 'green' },
    { title: 'Budget Utilization', value: budget?.budget?.length ? `${percent((spentTotal / (budgetTotal || 1)) * 100)}` : '0', detail: budget?.budget?.length ? `${currency(spentTotal)} used of ${currency(budgetTotal)}` : 'No budget data available', tone: 'amber' },
    { title: 'Pending Approvals', value: String(pendingApprovals.length), detail: pendingApprovals.length ? 'Items currently awaiting review' : 'No pending approvals available to this office', tone: 'red' },
    { title: 'Risks & Issues', value: String(riskCounts.open || 0), detail: riskCounts.open ? 'Open campus risk records' : 'No open campus risks', tone: 'violet' },
    { title: 'Escalations', value: String((escalations?.escalations || []).filter((item: any) => !['RESOLVED', 'CLOSED'].includes(item.status)).length), detail: 'Open campus escalations', tone: 'crimson' },
  ]

  return (
    <div className="fade-in campus-head-dashboard">
      <section className="campus-head-header">
        <div>
          <span className="eyebrow">Campus / Branch Head</span>
            <h1>{pageTitle || campusName}</h1>
        </div>
        <div className="campus-head-header-meta">
          <div><label>Academic Year</label><strong>{academicYear}</strong></div>
        </div>
      </section>

      <section className="campus-head-kpis">
        {summaryCards.map((card) => (
          <div key={card.title} className={`campus-head-kpi campus-head-kpi-${card.tone}`}>
            <div className="campus-head-kpi-top"><span>{card.title}</span><small>{card.detail}</small></div>
            <strong>{card.value}</strong>
          </div>
        ))}
      </section>

      <div className="campus-head-grid campus-head-top-grid">
        <Panel title="Vice Chairman Strategic Targets">
          <div className="campus-head-empty-metric"><strong>0</strong><span>No strategic targets available</span></div>
        </Panel>

        <Panel title="Branch Operational Plan">
          <div className="campus-head-plan">
            <div className="plan-row"><label>Plan name</label><strong>Not available yet</strong></div>
            <div className="plan-row"><label>Academic year</label><strong>{academicYear}</strong></div>
            <div className="plan-row"><label>Status</label><strong>Not available yet</strong></div>
            <div className="plan-row"><label>Progress</label><strong>Not available yet</strong></div>
            <div className="plan-row"><label>Last updated</label><strong>Not available yet</strong></div>
            <div className="plan-row"><label>VC review</label><strong>Not available yet</strong></div>
          </div>
          <p className="campus-head-caption">Campus operational plan is tracked under the Vice Chairman review workflow.</p>
        </Panel>
      </div>

      <Panel title="Department Performance">
        <div className="campus-head-table-wrap">
          <table className="campus-head-table">
            <thead>
              <tr>
                <th>Department</th>
                <th>KPI / Performance</th>
                <th>Status</th>
                <th>Trend</th>
              </tr>
            </thead>
            <tbody>
              {deptRows.length ? deptRows.map((row) => (
                <tr key={row.department}>
                  <td>{row.department}</td>
                  <td>{Number(row.value) ? Number(row.value).toLocaleString('en-IN') : 'Not available yet'}</td>
                  <td><span className="status-chip status-monitoring">{row.status}</span></td>
                  <td>{row.trend}</td>
                </tr>
              )) : <tr><td colSpan={4}><EmptyState text="No department performance data available yet" /></td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="campus-head-grid campus-head-mid-grid">
        <Panel title="Campus Performance">
          <div className="campus-head-metrics">
            {[['Academic', overview?.stats?.courses ? String(overview.stats.courses) : 'Not available yet'], ['Student', students?.summary?.all_students ? String(students.summary.all_students) : 'Not available yet'], ['Finance', outstandingFees ? currency(outstandingFees) : 'Not available yet'], ['Workforce', faculty?.summary?.total ? String(faculty.summary.total) : 'Not available yet'], ['Infrastructure', assets?.summary?.total ? String(assets.summary.total) : 'Not available yet'], ['Placements', overview?.stats?.placement_offers ? String(overview.stats.placement_offers) : 'Not available yet']].map(([label, value]) => (
              <div key={label} className="campus-head-metric">
                <label>{label}</label>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Resource Utilization">
          <div className="campus-head-resource-list">
            {(budget?.budget || []).slice(0, 5).map((row: any) => {
              const allocated = Number(row.allocated || 0)
              const spent = Number(row.spent || 0)
              const percentUsed = allocated ? Math.min(100, (spent / allocated) * 100) : 0
              return (
                <div key={row.category} className="resource-row">
                  <div className="resource-head"><span>{row.category || 'Budget'}</span><strong>{currency(spent || 0)}</strong></div>
                  <div className="resource-bar"><i style={{ width: `${percentUsed}%` }} /></div>
                  <small>{allocated ? `${percent(percentUsed)} of ${currency(allocated)}` : 'Not available yet'}</small>
                </div>
              )
            })}
            {!budget?.budget?.length && <EmptyState text="No resource utilization data available yet" />}
          </div>
        </Panel>
      </div>

      <div className="campus-head-grid campus-head-mid-grid">
        <Panel title="My Approvals">
          <div className="campus-head-list">
            {pendingApprovals.length ? pendingApprovals.slice(0, 5).map((item: any) => (
              <div key={item.id || item.title} className="list-item">
                <div>
                  <strong>{item.title || item.label || 'Workflow request'}</strong>
                  <small>{item.label || 'Request'} · {n(item.state, 'Pending')}</small>
                </div>
                <span className={`status-chip status-${String(item.state || '').toLowerCase() || 'pending'}`}>{n(item.state, 'Pending')}</span>
              </div>
            )) : <EmptyState text="No approvals are currently available to this office" />}
          </div>
        </Panel>

        <Panel title="Risks & Issues">
          <div className="campus-head-risk-grid">
            {[
              ['Open', riskCounts.open || 0],
              ['High / Critical', riskCounts.high_critical || 0],
              ['Overdue actions', riskCounts.overdue_actions || 0],
              ['Escalated', riskCounts.escalated || 0],
              ['Resolved', riskCounts.resolved || 0],
            ].map(([label, value]) => (
              <div key={label} className="risk-item">
                <label>{label}</label>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          {!riskCounts.open && !riskCounts.high_critical && !riskCounts.escalated && <EmptyState text="No campus risk data available yet" />}
        </Panel>
      </div>

      <div className="campus-head-grid campus-head-bottom-grid">
        <Panel title="Reporting to Vice Chairman">
          <div className="reporting-box">
            <div><label>Last report</label><strong>{reports.length ? reports[0].title : 'No reports available yet'}</strong></div>
            <div><label>Status</label><strong>{reports.length ? reports[0].status : 'Not available yet'}</strong></div>
            <div><label>Reports awaiting VC</label><strong>{reports.filter((item: any) => item.status === 'VC_REVIEW').length}</strong></div>
            <div><label>VC feedback</label><strong>{reports.find((item: any) => item.vc_feedback)?.vc_feedback || 'No feedback available yet'}</strong></div>
          </div>
        </Panel>

        <Panel title="Escalations">
          <div className="campus-head-risk-grid">
            {[
              ['Pending', (escalations?.escalations || []).filter((item: any) => ['SUBMITTED', 'RECEIVED', 'FOLLOW_UP'].includes(item.status)).length],
              ['Overdue', (escalations?.escalations || []).filter((item: any) => item.overdue).length],
              ['Resolved', (escalations?.escalations || []).filter((item: any) => item.status === 'RESOLVED' || item.status === 'CLOSED').length],
            ].map(([label, value]) => (
              <div key={label} className="risk-item">
                <label>{label}</label>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          {!escalations?.escalations?.length && <EmptyState text="No escalation data available yet" />}
        </Panel>
      </div>

      <Panel title="Campus Operational Snapshot">
        <div className="campus-head-operational-grid">
          {[
            ['Students', students?.summary?.all_students || overview?.stats?.students || 'Not available yet'],
            ['Faculty', faculty?.summary?.total || overview?.stats?.faculty || 'Not available yet'],
            ['Courses', overview?.stats?.courses || 'Not available yet'],
            ['Live Sections', overview?.stats?.sections || 'Not available yet'],
            ['Fees Outstanding', outstandingFees ? currency(outstandingFees) : 'Not available yet'],
            ['Open Grievances', grievance?.complaints?.length ? String(grievance.complaints.filter((item: any) => String(item.status || '').toLowerCase() !== 'resolved').length) : 'Not available yet'],
          ].map(([label, value]) => (
            <div key={label} className="ops-card">
              <label>{label}</label>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </Panel>

      {notifications.length > 0 && (
        <Panel title="Recent Notifications">
          <div className="campus-head-list">
            {notifications.map((item: any) => (
              <div key={item.id} className="list-item">
                <div>
                  <strong>{item.title || 'Notification'}</strong>
                  <small>{item.severity || 'Info'} · {item.created_at ? new Date(item.created_at).toLocaleDateString('en-IN') : 'Recent'}</small>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="campus-head-panel">
      <header className="campus-head-panel-header"><h2>{title}</h2></header>
      {children}
    </section>
  )
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>
}
