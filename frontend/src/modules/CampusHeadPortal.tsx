import { useEffect, useState } from 'react'
import { api } from '../api'
import { PrincipalApprovals } from '../views/PrincipalWorkflowViews'

/**
 * A deliberately small, read-only reference for the authenticated Campus / Branch
 * Head. Office configuration remains governed by the directory service; this
 * screen never exposes configuration controls or substitutes tenant-wide data.
 */
export function CampusProfile() {
  const [office, setOffice] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    api.office(3)
      .then((response: any) => {
        // A successful but structurally empty response is not a profile.
        const usable = response && typeof response === 'object' &&
          ['name', 'level', 'scope', 'purpose', 'reports_to', 'modules'].some((field) => response[field] !== undefined && response[field] !== null)
        if (active) setOffice(usable ? response : null)
      })
      .catch(() => { if (active) setOffice(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const modules = Array.isArray(office?.modules)
    ? office.modules.filter(Boolean).join(', ')
    : typeof office?.modules === 'string' && office.modules.trim()
      ? office.modules
      : 'Not available yet'
  const rows: Array<[string, string | number]> = office ? [
    ['Office', office.name || 'Campus Head Office'],
    ['Level', office.level ?? '3'],
    ['Scope', office.scope || 'Campus scope'],
    ['Purpose', office.purpose || 'Campus leadership oversight'],
    ['Reports to', office.reports_to || 'Vice Chairman'],
    ['Modules', modules],
  ] : []

  return <div className="fade-in campus-head-page">
    <div className="page-head">
      <h1>Campus Profile</h1>
      <p>Assigned campus and branch information for executive oversight.</p>
    </div>
    <section className="campus-head-panel campus-profile-panel">
      {loading ? <div className="empty">Loading campus profile…</div> : office ? (
        <div className="campus-head-plan campus-profile-plan">
          {rows.map(([label, value]) => <div className="plan-row" key={label}>
            <label>{label}</label><strong>{value}</strong>
          </div>)}
        </div>
      ) : <CampusProfileEmptyState text="No campus profile data available yet" />}
    </section>
  </div>
}

/** Campus-scoped, read-only department and programme register. */
export function DepartmentsPrograms() {
  const [overview, setOverview] = useState<any>(null)

  useEffect(() => {
    let active = true
    api.overview().then((response: any) => { if (active) setOverview(response) })
      .catch(() => { if (active) setOverview(null) })
    return () => { active = false }
  }, [])

  const rows = Array.isArray(overview?.department_programs) ? overview.department_programs : []
  const numeric = (value: any) => Number.isFinite(Number(value)) ? Number(value).toLocaleString('en-IN') : '0'
  return <div className="fade-in campus-head-page campus-directory-page">
    <div className="page-head"><h1>Departments &amp; Programs</h1><p>Department-level structure and current enrollment mix.</p></div>
    <section className="campus-directory-table">
      {rows.length ? <div className="campus-head-table-wrap"><table className="campus-head-table"><thead><tr><th>Department</th><th className="numeric">Students</th><th className="numeric">Programs</th><th>Status</th></tr></thead><tbody>{rows.map((department: any) => <tr key={department.id}><td>{department.code}{department.name ? ` — ${department.name}` : ''}</td><td className="numeric">{numeric(department.students)}</td><td className="numeric">{numeric(department.programs)}</td><td><span className="status-chip status-monitoring">Monitoring</span></td></tr>)}</tbody></table></div> : <CampusProfileEmptyState text="No department and program data available yet" />}
    </section>
  </div>
}

export function LeadershipTeam() {
  const [leadership, setLeadership] = useState<any>({ members: [] })
  const [selected, setSelected] = useState<any>(null)
  useEffect(() => { api.campusLeadership().then(setLeadership).catch(() => setLeadership({ members: [] })) }, [])
  const rows = Array.isArray(leadership?.members) ? leadership.members : []
  return <div className="fade-in campus-head-page leadership-page">
    <div className="page-head"><h1>Leadership Team</h1><p>Read-only view of senior administrative and academic leadership information.</p></div>
    <section className="leadership-directory">{rows.length ? <div className="campus-head-list">{rows.map((member: any) => <div key={member.id || member.name} className="list-item"><div><strong>{member.name || 'Leadership member'}</strong><small>{member.designation || member.role || 'Leadership role'} · {member.department || member.office || 'Office'}</small></div><button className="btn btn-out btn-sm" type="button" onClick={() => setSelected(member)}>View details</button></div>)}</div> : <CampusProfileEmptyState text="No leadership team data available yet" />}</section>
    {selected && <LeadershipDetail member={selected} onClose={() => setSelected(null)} />}
  </div>
}

type CampusOverviewTab = 'academic' | 'students' | 'workforce'
const CAMPUS_OVERVIEW_TABS: Array<{ key: CampusOverviewTab, label: string }> = [{ key: 'academic', label: 'Academic' }, { key: 'students', label: 'Students' }, { key: 'workforce', label: 'Workforce' }]
function campusOverviewTabFromLocation(): CampusOverviewTab { const tab = new URLSearchParams(window.location.search).get('tab'); return CAMPUS_OVERVIEW_TABS.some((item) => item.key === tab) ? tab as CampusOverviewTab : 'academic' }
export function CampusOverview() {
  const [tab, setTab] = useState<CampusOverviewTab>(campusOverviewTabFromLocation)
  useEffect(() => { const update = () => setTab(campusOverviewTabFromLocation()); window.addEventListener('popstate', update); return () => window.removeEventListener('popstate', update) }, [])
  const select = (next: CampusOverviewTab) => { const url = new URL(window.location.href); url.searchParams.set('tab', next); window.history.pushState({ tab: next }, '', url); setTab(next) }
  const current = CAMPUS_OVERVIEW_TABS.find((item) => item.key === tab)?.label || 'Academic'
  return <div className="fade-in campus-head-page campus-overview-page"><header className="campus-overview-header"><h1>Campus Overview</h1><p>Academic, student and workforce performance for the campus.</p></header><div className="campus-overview-tabs" role="tablist" aria-label="Campus overview sections">{CAMPUS_OVERVIEW_TABS.map((item) => <button key={item.key} type="button" role="tab" aria-selected={tab === item.key} className={`campus-overview-tab ${tab === item.key ? 'active' : ''}`} onClick={() => select(item.key)}>{item.label}</button>)}</div><section className="campus-overview-section" role="tabpanel"><h2>{current} overview</h2>{tab === 'academic' ? <AcademicSnapshot /> : tab === 'students' ? <StudentSnapshot /> : <WorkforceOverview />}</section></div>
}
function CampusRegister({ title, subtitle, rows, children }: any) { return <div className="campus-overview-content"><section className="campus-overview-register"><header className="campus-register-heading"><span>{title}</span><small>{subtitle}</small></header><div className="campus-register-grid">{rows.map(([label, value]: any) => <div className="campus-register-row" key={label}><span>{label}</span><strong>{value === null || value === undefined || value === '' ? 'Not available yet' : String(value)}</strong></div>)}</div>{children}</section></div> }
function AcademicSnapshot() { const [overview, setOverview] = useState<any>(null), [calendar, setCalendar] = useState<any>(null); useEffect(() => { Promise.all([api.overview().catch(() => null), api.academicCalendar().catch(() => null)]).then(([o,c]) => { setOverview(o); setCalendar(c) }) }, []); const stats=overview?.stats || {}; return <CampusRegister title="Academic performance" subtitle="Current available records" rows={[["Students",stats.students],["Faculty",stats.faculty],["Courses",stats.courses],["Sections",stats.sections],["Academic term",calendar?.selected_term || 'Not recorded'],["Placement offers",stats.placement_offers]]} /> }
function StudentSnapshot() { const [data,setData]=useState<any>({summary:{},departments:[]}); useEffect(()=>{api.students('', '', 1, 25, {}).then(setData).catch(()=>setData({summary:{},departments:[]}))},[]); const summary=data.summary||{}, departments=Array.isArray(data.departments)?data.departments:[]; return <CampusRegister title="Student performance" subtitle="Population and current standing" rows={[["All students",summary.all_students],["At risk",summary.at_risk],["Departments",departments.length],["Open grievances",summary.open_grievances]]}>{departments.length>0&&<CampusRegisterTable headers={['Department','Students']} rows={departments.map((d:any)=>[d.name||d.code||'Not available yet',d.count ?? 'Not available yet'])}/>}</CampusRegister> }
function WorkforceOverview() { const [data,setData]=useState<any>({summary:{},staff:[]}); useEffect(()=>{api.facultyStaff('', '', '', 1, {}).then(setData).catch(()=>setData({summary:{},staff:[]}))},[]); const summary=data.summary||{}, staff=Array.isArray(data.staff)?data.staff:[]; return <CampusRegister title="Workforce directory" subtitle="Read-only campus workforce summary" rows={[["Total staff",summary.total],["Faculty",summary.faculty],["Administrative",summary.administrative],["Support",summary.support]]}>{staff.length>0&&<CampusRegisterTable headers={['Employee','Department','Designation','Status']} rows={staff.map((m:any)=>[m.name||'Not available yet',m.department||'Not available yet',m.designation||m.role||'Not available yet',m.status||'Not available yet'])}/>}</CampusRegister> }
function CampusRegisterTable({headers,rows}:any){return <div className="campus-register-table-wrap"><table className="campus-register-table"><thead><tr>{headers.map((header:string)=><th key={header}>{header}</th>)}</tr></thead><tbody>{rows.map((row:any,index:number)=><tr key={index}>{row.map((value:any,cell:number)=><td key={cell}>{value}</td>)}</tr>)}</tbody></table></div>}

function LeadershipDetail({ member, onClose }: any) {
  const optional = [['Employee ID', member.employee_id || member.employeeId || member.id], ['Email', member.email], ['Phone', member.phone], ['Role', member.role], ['Office', member.office], ['Joined', member.joining_date || member.joined_at]].filter(([, value]) => value !== null && value !== undefined && value !== '')
  return <div className="modal-bg leadership-modal-bg" onClick={onClose}><section className="modal leadership-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="Leadership staff profile"><header className="modal-h"><div><span>Leadership / Staff Profile</span><h3>{member.name || 'Staff member'}</h3></div><button className="modal-x" onClick={onClose} aria-label="Close profile">×</button></header><div className="modal-b leadership-modal-body"><LeadershipProfileField label="Department" value={member.department} /><LeadershipProfileField label="Designation" value={member.designation || member.role} /><LeadershipProfileField label="Status" value={member.status} />{optional.map(([label, value]: any) => <LeadershipProfileField key={label} label={label} value={value} />)}</div><footer className="modal-f"><button className="btn btn-out" onClick={onClose}>Close</button></footer></section></div>
}
function LeadershipProfileField({ label, value }: { label: string, value: any }) { return <div className="leadership-profile-field"><span>{label}</span><b>{String(value || 'Not available yet')}</b></div> }

function CampusProfileEmptyState({ text }: { text: string }) {
  return <div className="campus-head-empty-metric"><span>{text}</span></div>
}

/** Campus Head landing page.  All figures are fetched from the target tenant;
 * no reference/demo values are rendered as operational data. */
export function CampusHeadDashboard({ user, go }: { user: any, go: (view: string) => void }) {
  const [data, setData] = useState<any>({ inbox: [], notifications: [], escalations: [], risks: {}, students: {}, faculty: {}, budget: [], invoices: {}, assets: {}, grievance: {}, reports: [], bop: null, overview: {} })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let live = true
    Promise.all([
      api.overview().catch(() => ({})), api.workflows('inbox').catch(() => ({ workflows: [] })),
      api.escalations().catch(() => ({ escalations: [] })), api.grievance().catch(() => ({})),
      api.riskSummary().catch(() => ({ summary: {} })), api.students('', '', 1, 25, {}).catch(() => ({})),
      api.facultyStaff('', '', '', 1, {}).catch(() => ({})), api.budget().catch(() => ({})),
      api.invoices().catch(() => ({})), api.assets().catch(() => ({})), api.academicCalendar().catch(() => ({})),
      api.notifications().catch(() => ({ notifications: [] })), api.bop().catch(() => ({})), api.campusReports().catch(() => ({ reports: [] })),
    ])
      .then(([overview, inbox, escalations, grievance, risks, students, faculty, budget, invoices, assets, calendar, notifications, bop, reports]) => {
        if (live) setData({
          overview: overview || {}, calendar: calendar || {}, grievance: grievance || {}, risks: risks?.summary || {}, students: students || {}, faculty: faculty || {}, budget: Array.isArray(budget?.budget) ? budget.budget : [], invoices: invoices || {}, assets: assets || {}, bop: Array.isArray(bop?.plans) ? (bop.plans[0] || null) : (bop?.plan || null), reports: Array.isArray(reports?.reports) ? reports.reports : [],
          inbox: Array.isArray(inbox?.workflows) ? inbox.workflows : [],
          notifications: Array.isArray(notifications?.notifications) ? notifications.notifications : [],
          escalations: Array.isArray(escalations?.escalations) ? escalations.escalations : [],
        })
      })
      .catch(() => { if (live) setData((current: any) => ({ ...current, unavailable: true })) })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [])

  const inbox = Array.isArray(data?.inbox) ? data.inbox : []
  const notifications = Array.isArray(data?.notifications) ? data.notifications : []
  const escalations = Array.isArray(data?.escalations) ? data.escalations : []
  const pending = inbox.filter((row: any) => !['approved', 'executed', 'rejected', 'completed'].includes(String(row?.state || '').toLowerCase()))
  const budget = Array.isArray(data.budget) ? data.budget : []
  const totalBudget = budget.reduce((sum: number, row: any) => sum + Number(row.allocated || 0), 0)
  const totalSpent = budget.reduce((sum: number, row: any) => sum + Number(row.spent || 0), 0)
  const money = (n: any) => Number.isFinite(Number(n)) ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Number(n)) : 'Not available yet'
  const value = (n: any) => n === null || n === undefined || n === '' ? 'Not available yet' : String(n)
  const campus = user?.campus || user?.branch || user?.scope_ref || 'Campus not assigned'
  const risk = data.risks || {}, reports = Array.isArray(data.reports) ? data.reports : [], summary = data.students?.summary || {}, faculty = data.faculty?.summary || {}
  return <div className="fade-in campus-head-dashboard">
    <header className="campus-head-header"><div><span className="eyebrow">CAMPUS / BRANCH HEAD</span><h1>{campus}</h1></div><div className="campus-head-header-meta"><div><label>ACADEMIC YEAR</label><strong>{data.calendar?.selected_term || 'Not available yet'}</strong></div></div></header>
    {loading ? <div className="card"><div className="empty">Loading campus operational data…</div></div> : data.unavailable ? <div className="err-box">Campus data could not be loaded. Refresh to retry.</div> : <>
      <section className="campus-head-kpis">{[['Campus KPI Snapshot', (risk.open || risk.high_critical) ? (risk.open || 0) + (risk.high_critical || 0) : 'Not available yet', 'Live campus indicators', 'green'],['Budget Utilization', totalBudget ? `${((totalSpent / totalBudget) * 100).toFixed(1)}%` : 'Not available yet', totalBudget ? `${money(totalSpent)} used of ${money(totalBudget)}` : 'No budget data available', 'amber'],['Pending Approvals', pending.length, pending.length ? 'Items currently awaiting review' : 'No pending approvals', 'red'],['Risks & Issues', value(risk.open), 'Open campus risk records', 'violet'],['Escalations', escalations.filter((x:any) => !['RESOLVED','CLOSED'].includes(String(x.status || '').toUpperCase())).length, 'Open campus escalations', 'crimson']].map(([title, item, detail, tone]) => <button type="button" className={`campus-head-kpi campus-head-kpi-${tone}`} key={title as string} onClick={() => go(title === 'Pending Approvals' ? 'campus_head_approvals' : title === 'Escalations' ? 'escalations' : 'risk_issues')}><div className="campus-head-kpi-top"><span>{title}</span><small>{detail}</small></div><strong>{String(item)}</strong></button>)}</section>
      <div className="campus-head-grid campus-head-top-grid">
        <Panel title="Vice Chairman Strategic Targets"><Empty text="No strategic targets available" /></Panel><Panel title="Branch Operational Plan"><Plan rows={[['Plan name', data.bop?.name],['Academic year', data.bop?.academic_year || data.calendar?.selected_term],['Status', data.bop?.status],['Progress', data.bop?.progress],['Last updated', data.bop?.updated_at],['VC review', data.bop?.vc_feedback]]} /></Panel>
      </div>
      <Panel title="Department Performance"><div className="campus-head-table-wrap"><table className="campus-head-table"><thead><tr><th>Department</th><th>KPI / Performance</th><th>Status</th><th>Trend</th></tr></thead><tbody>{(data.overview?.dept_distribution ? Object.entries(data.overview.dept_distribution) : []).map(([name, count]: any) => <tr key={name}><td>{name}</td><td>{value(count)}</td><td><span className="status-chip status-monitoring">Monitoring</span></td><td>—</td></tr>)}{!data.overview?.dept_distribution && <tr><td colSpan={4}><Empty text="No department performance data available yet" /></td></tr>}</tbody></table></div></Panel>
      <div className="campus-head-grid campus-head-mid-grid"><Panel title="Campus Performance"><Metrics values={[['Academic', data.overview?.stats?.courses],['Student', summary.all_students],['Finance', data.invoices?.summary?.outstanding ? money(data.invoices.summary.outstanding) : null],['Workforce', faculty.total],['Infrastructure', data.assets?.summary?.total],['Placements', data.overview?.stats?.placement_offers]]} /></Panel><Panel title="Resource Utilization"><div className="campus-head-resource-list">{budget.length ? budget.slice(0,5).map((row:any) => <Resource key={row.category} row={row} money={money} />) : <Empty text="No resource utilization data available yet" />}</div></Panel></div>
      <div className="campus-head-grid campus-head-mid-grid"><Panel title="My Approvals"><div className="campus-head-list">{pending.length ? pending.slice(0,5).map((row:any) => <div className="list-item" key={row.id}><div><strong>{row.title}</strong><small>{row.label} · {row.state}</small></div><span className="status-chip">{row.state}</span></div>) : <Empty text="No approvals are currently available to this office" />}</div></Panel><Panel title="Risks & Issues"><RiskMetrics values={[['Open',risk.open],['High / Critical',risk.high_critical],['Overdue actions',risk.overdue_actions],['Escalated',risk.escalated],['Resolved',risk.resolved]]} /></Panel></div>
      <div className="campus-head-grid campus-head-bottom-grid"><Panel title="Reporting to Vice Chairman"><Metrics values={[['Last report',reports[0]?.title],['Status',reports[0]?.status],['Reports awaiting VC',reports.filter((x:any)=>x.status==='VC_REVIEW').length],['VC feedback',reports.find((x:any)=>x.vc_feedback)?.vc_feedback]]} /></Panel><Panel title="Escalations"><RiskMetrics values={[['Pending',escalations.filter((x:any)=>['SUBMITTED','RECEIVED','FOLLOW_UP'].includes(x.status)).length],['Overdue',escalations.filter((x:any)=>x.overdue).length],['Resolved',escalations.filter((x:any)=>['RESOLVED','CLOSED'].includes(x.status)).length]]} /></Panel></div>
      <Panel title="Campus Operational Snapshot"><div className="campus-head-operational-grid">{[['Students',summary.all_students],['Faculty',faculty.total],['Courses',data.overview?.stats?.courses],['Live Sections',data.overview?.stats?.sections],['Fees Outstanding',data.invoices?.summary?.outstanding ? money(data.invoices.summary.outstanding) : null],['Open Grievances',Array.isArray(data.grievance?.complaints) ? data.grievance.complaints.filter((x:any)=>String(x.status).toLowerCase() !== 'resolved').length : null]].map(([label,item]) => <div className="ops-card" key={label as string}><label>{label}</label><strong>{value(item)}</strong></div>)}</div></Panel>
      {notifications.length > 0 && <Panel title="Recent Notifications"><div className="campus-head-list">{notifications.slice(0,6).map((item:any)=><div className="list-item" key={item.id}><div><strong>{item.title}</strong><small>{item.severity || 'Info'} · {item.at ? new Date(item.at).toLocaleDateString('en-IN') : 'Recent'}</small></div></div>)}</div></Panel>}
    </>}
  </div>
}

function Panel({ title, children }: any) { return <section className="campus-head-panel"><header className="campus-head-panel-header"><h2>{title}</h2></header>{children}</section> }
function Empty({ text }: { text: string }) { return <div className="campus-head-empty-metric"><span>{text}</span></div> }
function Plan({ rows }: any) { return <div className="campus-head-plan">{rows.map(([label, value]: any) => <div className="plan-row" key={label}><label>{label}</label><strong>{value || 'Not available yet'}</strong></div>)}</div> }
function Metrics({ values }: any) { return <div className="campus-head-metrics">{values.map(([label,value]:any)=><div className="campus-head-metric" key={label}><label>{label}</label><strong>{value ?? 'Not available yet'}</strong></div>)}</div> }
function RiskMetrics({ values }: any) { return <div className="campus-head-risk-grid">{values.map(([label,value]:any)=><div className="risk-item" key={label}><label>{label}</label><strong>{value ?? 'Not available yet'}</strong></div>)}</div> }
function Resource({ row, money }: any) { const allocated=Number(row.allocated || 0), spent=Number(row.spent || 0), pct=allocated ? Math.min(100,(spent/allocated)*100) : 0; return <div className="resource-row"><div className="resource-head"><span>{row.category || 'Budget'}</span><strong>{money(spent)}</strong></div><div className="resource-bar"><i style={{width:`${pct}%`}} /></div><small>{allocated ? `${pct.toFixed(1)}% of ${money(allocated)}` : 'Not available yet'}</small></div> }

export function CampusHeadApprovals({ user, onChange }: { user: any, onChange: () => void }) {
  return <PrincipalApprovals user={user} onChange={onChange} />
}

/** Campus-scoped escalation register. Escalations are governance records,
 * not generic workflow requests, so the Campus Head gets a dedicated view. */
export function CampusHeadEscalations() {
  const [data, setData] = useState<any>(null)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [riskCreating, setRiskCreating] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [followUp, setFollowUp] = useState<any>(null)
  const [followUpNote, setFollowUpNote] = useState('')
  const blank = { risk_id: '', reason: '' }
  const [form, setForm] = useState<any>(blank)
  const [risks, setRisks] = useState<any[]>([])

  const load = () => {
    setError('')
    api.escalations({ q: query.trim(), state: status })
      .then((response: any) => setData({ escalations: Array.isArray(response?.escalations) ? response.escalations : [] }))
      .catch((requestError: any) => {
        setData({ escalations: [] })
        setError(requestError?.message || 'Campus escalation records could not be loaded.')
      })
  }

  useEffect(() => { load() }, [])
  const rows = Array.isArray(data?.escalations) ? data.escalations : []
  const unresolved = rows.filter((row: any) => !['RESOLVED', 'CLOSED'].includes(String(row?.status || '').toUpperCase()))
  const overdue = unresolved.filter((row: any) => {
    const due = row?.due_at || row?.due_date
    return due && !Number.isNaN(Date.parse(due)) && Date.parse(due) < Date.now()
  })
  const create = async () => {
    setSubmitting(true); setError('')
    try { await api.createCampusEscalation(form); setCreating(false); setForm(blank); load() }
    catch (requestError: any) { setError(requestError?.message || 'Escalation could not be submitted to the Principal.') }
    finally { setSubmitting(false) }
  }
  const resubmit = async () => {
    if (!followUp) return
    setSubmitting(true); setError('')
    try { await api.resubmitCampusEscalation(followUp.id, followUpNote); setFollowUp(null); setFollowUpNote(''); load() }
    catch (requestError: any) { setError(requestError?.message || 'Escalation follow-up could not be submitted.') }
    finally { setSubmitting(false) }
  }

  return <div className="fade-in campus-head-page campus-escalations">
    <header className="campus-workspace-header"><div><span className="eyebrow">CAMPUS / BRANCH HEAD</span><h1>Escalations</h1><p>Escalate an existing campus risk to the scoped Principal for a governed decision.</p></div><button className="btn btn-crimson" onClick={() => { setForm(blank); setRiskCreating(true); api.risks().then((response:any) => setRisks(Array.isArray(response?.risks) ? response.risks.filter((risk:any) => !['RESOLVED', 'CLOSED'].includes(String(risk.status || '').toUpperCase())) : [])).catch(() => setRisks([])) }}>Create escalation</button></header>
    <div className="campus-head-risk-grid risk-summary-strip">
      {[["Pending", unresolved.length], ["Overdue", overdue.length], ["Resolved", rows.filter((row: any) => String(row?.status || '').toUpperCase() === 'RESOLVED').length]].map(([label, value]) => <div className="risk-item" key={label as string}><label>{label}</label><strong>{value}</strong></div>)}
    </div>
    <section className="workspace-filter-bar"><div className="risk-filters"><input className="inp" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search escalation or risk" aria-label="Search escalations" /><select className="select" value={status} onChange={event => setStatus(event.target.value)} aria-label="Filter escalation status"><option value="">All statuses</option>{['DRAFT', 'SUBMITTED', 'RECEIVED', 'FOLLOW_UP', 'RESOLVED', 'CLOSED'].map(value => <option value={value} key={value}>{value.replace('_', ' ')}</option>)}</select><button type="button" className="btn btn-out" onClick={load}>Apply filters</button></div></section>
    <section className="campus-head-panel">
      {data === null ? <div className="empty">Loading campus escalations…</div> : error ? <div className="err-box">{error}</div> : <div className="campus-head-table-wrap"><table className="campus-head-table"><thead><tr><th>Escalation</th><th>Source</th><th>Priority</th><th>Destination</th><th>Status</th><th>Created</th></tr></thead><tbody>{rows.map((row: any) => <tr key={row?.id || row?.reference}><td><b>{row?.title || 'Untitled escalation'}</b><small>{row?.reference || row?.id || 'Reference unavailable'}</small></td><td>{row?.module || row?.source_type || 'Not available yet'}</td><td>{row?.priority || 'Not available yet'}</td><td>{row?.destination || row?.to || 'Policy routed'}</td><td><span className="status-chip">{row?.status || 'Not available yet'}</span></td><td>{row?.created_at && !Number.isNaN(Date.parse(row.created_at)) ? new Date(row.created_at).toLocaleDateString('en-IN') : 'Not available yet'}</td></tr>)}{!rows.length && <tr><td colSpan={6}><CampusProfileEmptyState text="No campus escalations match the selected filters." /></td></tr>}</tbody></table></div>}
    </section>
    {rows.filter((row: any) => row?.status === 'FOLLOW_UP' && row?.workflow_id).map((row: any) => <section className="campus-head-panel" key={`follow-up-${row.id}`}><div className="page-head"><div><span className="eyebrow">PRINCIPAL FOLLOW-UP REQUIRED</span><h3>{row.title}</h3><p>Address the returned decision brief and resubmit the same escalation record for a new Principal review version.</p></div><button className="btn btn-crimson" onClick={() => { setFollowUp(row); setFollowUpNote('') }}>Prepare follow-up</button></div></section>)}
    {riskCreating && <div className="modal-bg" role="dialog" aria-modal="true" aria-label="Create risk escalation"><div className="modal risk-modal"><div className="modal-h"><div><h3>Escalate a campus risk</h3><p>Select an open Risk &amp; Issues record. Its identity, category and priority are retained without duplication.</p></div><button className="modal-x" onClick={() => !submitting && setRiskCreating(false)}>×</button></div><div className="modal-b risk-form-grid"><label className="risk-form-wide">Related risk<select autoFocus className="select" value={form.risk_id} onChange={event => setForm({ ...form, risk_id: event.target.value })}><option value="">Select an open risk…</option>{risks.map((risk:any) => <option value={risk.id} key={risk.id} disabled={Boolean(risk.escalated_at)}>{risk.title} · {risk.category} · {risk.severity}{risk.escalated_at ? ' — already submitted to Principal' : ''}</option>)}</select></label>{risks.length === 0 ? <div className="risk-description risk-form-wide"><b>No open risks are available</b><br />Create a risk in Risk &amp; Issues before opening an escalation.</div> : <p className="hint risk-form-wide">Risks already submitted to the Principal remain visible but are locked to prevent duplicate decisions. Review their status in this Escalations register.</p>}{form.risk_id && (() => { const risk = risks.find((item:any) => item.id === form.risk_id); return risk ? <div className="risk-description risk-form-wide"><b>{risk.title}</b><br />{risk.category} · {risk.severity} · {risk.status}{risk.description ? <><br />{risk.description}</> : null}</div> : null })()}<label className="risk-form-wide">Decision brief<textarea className="inp" value={form.reason} onChange={event => setForm({ ...form, reason: event.target.value })} placeholder="Describe the impact, action already taken, decision required from the Principal, and time sensitivity." /></label><p className="hint risk-form-wide">The Principal receives the linked risk and decision brief in My Approvals. A risk can have only one active escalation.</p></div><div className="modal-f"><button className="btn btn-out" disabled={submitting} onClick={() => setRiskCreating(false)}>Cancel</button><button className="btn btn-crimson" disabled={submitting || !form.risk_id || form.reason.trim().length < 10} onClick={() => void create()}>{submitting ? 'Submitting...' : 'Submit to Principal'}</button></div></div></div>}
    {followUp && <div className="modal-bg" role="dialog" aria-modal="true" aria-label="Resubmit campus escalation"><div className="modal risk-modal"><div className="modal-h"><div><h3>Prepare Principal follow-up</h3><p>{followUp.title} · {followUp.reference}</p></div><button className="modal-x" onClick={() => !submitting && setFollowUp(null)}>×</button></div><div className="modal-b"><label className="workflow-field workflow-reason">Updated response<textarea autoFocus className="inp" rows={5} value={followUpNote} onChange={event => setFollowUpNote(event.target.value)} placeholder="State what changed, the evidence considered, and the decision requested from the Principal." /></label><p className="hint">Resubmission preserves the escalation and advances its workflow version. Prior Principal feedback remains in the approval audit history.</p></div><div className="modal-f"><button className="btn btn-out" disabled={submitting} onClick={() => setFollowUp(null)}>Cancel</button><button className="btn btn-crimson" disabled={submitting || followUpNote.trim().length < 10} onClick={() => void resubmit()}>{submitting ? 'Submitting...' : 'Resubmit to Principal'}</button></div></div></div>}
  </div>
}

export function CampusHeadReports() {
  const [reports, setReports] = useState<any[]>([]), [open, setOpen] = useState(false), [selected, setSelected] = useState<any>(null), [error, setError] = useState('')
  const blank = { report_type: 'MONTHLY_CAMPUS_REPORT', period_start: '', period_end: '', title: '' }
  const [form, setForm] = useState<any>(blank)
  const load = () => api.campusReports().then((r:any) => setReports(Array.isArray(r?.reports) ? r.reports : [])).catch((e:any) => setError(e.message || 'Unable to load campus reports.'))
  // Do not pass an async loader directly to useEffect. Its Promise would be
  // treated as a cleanup callback when this screen unmounts, which causes the
  // production-only "n is not a function" React error after navigation.
  useEffect(() => { void load() }, [])
  async function save() { try { const result = selected?.id ? await api.updateCampusReport(selected.id, { ...form, expected_version: selected.version }) : await api.createCampusReport(form); setSelected(result.report); setOpen(false); load() } catch(e:any) { setError(e.message || 'Unable to save report.') } }
  async function submit() { try { const result=await api.submitCampusReport(selected.id); setSelected(result.report); load() } catch(e:any) { setError(e.message || 'Unable to submit report.') } }
  const editable = selected && ['DRAFT','RETURNED'].includes(selected.status)
  return <div className="fade-in campus-head-page"><div className="page-head"><div><h1>Reports &amp; Analytics</h1><p>Campus reports submitted to the Vice Chairman.</p></div><button className="btn btn-crimson" onClick={()=>{setSelected(null);setForm(blank);setOpen(true)}}>Create report</button></div>{error && <div className="err-box">{error}</div>}<section className="campus-head-panel"><div className="campus-head-table-wrap"><table className="campus-head-table"><thead><tr><th>Report type</th><th>Period</th><th>Title</th><th>Status</th><th>Version</th><th>Updated</th><th /></tr></thead><tbody>{reports.map((r:any)=><tr key={r.id}><td>{r.report_type}</td><td>{r.period_start} to {r.period_end}</td><td><b>{r.title}</b></td><td><span className="status-chip">{r.status}</span></td><td>{r.version}</td><td>{r.updated_at ? new Date(r.updated_at).toLocaleDateString('en-IN') : 'Not available yet'}</td><td><button className="btn btn-out" onClick={()=>{setSelected(r);setForm(r)}}>Open</button></td></tr>)}{!reports.length&&<tr><td colSpan={7}><Empty text="No campus reports available." /></td></tr>}</tbody></table></div></section>{open&&<ReportForm form={form} setForm={setForm} onClose={()=>setOpen(false)} onSave={save}/>} {selected&&!open&&<div className="modal-bg"><div className="modal risk-modal"><div className="modal-h"><div><h3>{selected.title}</h3><p>{selected.report_type} · version {selected.version}</p></div><button className="modal-x" onClick={()=>setSelected(null)}>×</button></div><div className="modal-b"><Metrics values={[['Status',selected.status],['Period',`${selected.period_start} to ${selected.period_end}`],['VC feedback',selected.vc_feedback || 'Not available yet']]}/><p className="hint">Submitted reports retain an immutable, verified campus-data snapshot.</p></div><div className="modal-f">{editable&&<button className="btn btn-out" onClick={()=>setOpen(true)}>Edit</button>}{editable&&<button className="btn btn-crimson" onClick={submit}>{selected.status==='RETURNED'?'Resubmit':'Submit to VC'}</button>}</div></div></div>}</div>
}
function ReportForm({form,setForm,onClose,onSave}:any){return <div className="modal-bg"><div className="modal risk-modal"><div className="modal-h"><h3>Campus report draft</h3><button className="modal-x" onClick={onClose}>×</button></div><div className="modal-b risk-form-grid"><label>Report type<select className="select" value={form.report_type} onChange={e=>setForm({...form,report_type:e.target.value})}><option>MONTHLY_CAMPUS_REPORT</option><option>IMMEDIATE_RISK_EXCEPTION_REPORT</option></select></label><label>Period start<input required className="inp" type="date" value={form.period_start||''} onChange={e=>setForm({...form,period_start:e.target.value})}/></label><label>Period end<input required className="inp" type="date" value={form.period_end||''} onChange={e=>setForm({...form,period_end:e.target.value})}/></label><label className="risk-form-wide">Title<input required className="inp" value={form.title||''} onChange={e=>setForm({...form,title:e.target.value})}/></label></div><div className="modal-f"><button className="btn btn-out" onClick={onClose}>Cancel</button><button className="btn btn-crimson" onClick={onSave}>Save draft</button></div></div></div>}

export function CampusHeadOperationalPlan({ user, onChange }: { user: any, onChange: () => void }) {
  const [plans, setPlans] = useState<any[]>([]), [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true), [editor, setEditor] = useState<any>(null), [viewingPlan, setViewingPlan] = useState<any>(null), [error, setError] = useState('')
  const selected = plans.find((plan) => plan.id === selectedId) || plans[0] || null
  const load = async (preferredId = '') => {
    setLoading(true); setError('')
    try {
      const response: any = await api.bop()
      const next = Array.isArray(response?.plans) ? response.plans : []
      setPlans(next); setSelectedId(preferredId && next.some((plan) => plan.id === preferredId) ? preferredId : (next[0]?.id || ''))
    } catch (e: any) { setPlans([]); setSelectedId(''); setError(e.message || 'Unable to load Branch Operational Plans.') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])
  const save = async (form: any) => {
    setError('')
    try {
      const response: any = editor?.id
        ? await api.updateBop(editor.id, { ...form, expected_version: editor.version })
        : await api.createBop(form)
      const plan = response?.plan
      setEditor(null); await load(plan?.id); onChange()
    } catch (e: any) { setError(e.message || 'Unable to save the plan.') }
  }
  const submit = async (resubmit = false) => {
    if (!selected) return
    setError('')
    try { const response: any = resubmit ? await api.resubmitBop(selected.id) : await api.submitBop(selected.id); await load(response?.plan?.id || selected.id); onChange() }
    catch (e: any) { setError(e.message || 'Unable to submit the plan.') }
  }
  const submittedPlans = plans.filter((plan) => ['submitted', 'reviewed', 'approved'].includes(String(plan.status).toLowerCase()))
  const formatDate = (value: any) => value ? new Date(value).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : 'Not submitted'
  return <div className="fade-in campus-head-page bop-page">
    <header className="bop-page-head"><div><span className="eyebrow">CAMPUS PLANNING WORKSPACE</span><h1>Branch Operational Plan</h1><p>Shape priorities, resource needs, delivery commitments, and executive review in one place.</p></div><div className="bop-head-actions"><div className="bop-portfolio"><label>PLAN PORTFOLIO</label><strong>{plans.length}</strong><small>{plans.length === 1 ? 'plan on record' : 'plans on record'}</small></div><button className="btn btn-crimson" onClick={() => setEditor({})}>Create plan</button></div></header>
    {error && <div className="err-box">{error}</div>}
    {loading ? <section className="campus-head-panel bop-loading"><span className="bop-loading-mark" /><div><strong>Loading plan data...</strong><small>Retrieving your campus planning portfolio.</small></div></section> : <>
      {!selected ? <section className="campus-head-panel bop-empty"><div className="bop-empty-mark">BOP</div><div><h2>No Branch Operational Plan has been created for this campus yet</h2><p>Start a draft when this campus is ready to record its delivery commitments and executive review requirements.</p></div></section> : <>
        <section id="bop-current-plan" className="bop-hero" tabIndex={-1}><div className="bop-hero-main"><span className="eyebrow">{selected.campus || user?.scope_ref || 'Campus scope'}</span><h2>{selected.title}</h2><p>{selected.strategic_alignment || 'Strategic alignment not recorded'}</p></div><div className="bop-hero-side"><div className="bop-status-line"><span className="status-chip">{selected.status}</span><small>Current plan status</small></div><div className="bop-hero-meta"><div><small>Planning period</small><strong>{selected.planning_period || 'Not recorded'}</strong></div><div><small>Plan owner</small><strong>{selected.created_by || 'Not available yet'}</strong></div><div><small>Last submission</small><strong>{selected.submission ? formatDate(selected.submission.submitted_at) : 'Not submitted'}</strong></div></div>{['draft', 'returned'].includes(String(selected.status).toLowerCase()) && <div className="bop-actions"><button className="btn btn-out" onClick={() => setEditor(selected)}>Edit plan</button><button className="btn btn-crimson" onClick={() => submit(selected.status === 'returned')}>{selected.status === 'returned' ? 'Resubmit to VC' : 'Submit for review'}</button></div>}</div></section>
        {selected.vc_review?.feedback && <section className="bop-feedback"><label>VICE CHAIRMAN FEEDBACK</label><p>{selected.vc_review.feedback}</p></section>}
        <section className="campus-head-panel bop-details"><div className="bop-details-head"><div><label>PLAN DETAILS</label><h3>Delivery and governance record</h3></div><small>Read-only after submission</small></div><div className="bop-detail-list">{[
          ['Strategic alignment', selected.strategic_alignment], ['Timeline', selected.timeline], ['Initiatives', selected.initiatives], ['Activities', selected.activities], ['Responsible areas', selected.responsible_areas], ['Required resources', selected.resources], ['KPI references', selected.kpi_references], ['Risks and dependencies', selected.risks], ['Notes', selected.notes],
        ].map(([heading, content]: any) => <div className="bop-detail-row" key={heading}><label>{heading}</label><div>{Array.isArray(content) ? content.length ? <ul>{content.map((item: string, index: number) => <li key={`${index}-${item}`}>{item}</li>)}</ul> : <span>Not recorded</span> : <span>{content || 'Not recorded'}</span>}</div></div>)}</div></section>
      </>}
      {submittedPlans.length > 0 && <section className="campus-head-panel bop-submitted"><div className="bop-details-head"><div><label>SUBMITTED PLANS</label><h3>Plans under executive review or completed</h3></div><small>{submittedPlans.length} {submittedPlans.length === 1 ? 'plan' : 'plans'}</small></div><div className="bop-submitted-list">{submittedPlans.map((plan) => <article key={plan.id} className={`bop-submitted-row ${selected?.id === plan.id ? 'is-current' : ''}`}><div><b>{plan.title}</b><span>{plan.planning_period || 'Period not recorded'} · submitted {plan.submission ? formatDate(plan.submission.submitted_at) : 'date not recorded'}</span></div><span className="status-chip">{plan.status}</span><button className="btn btn-out" onClick={() => setViewingPlan(plan)}>View plan</button></article>)}</div></section>}
    </>}
    {editor && <BopEditor plan={editor} onCancel={() => setEditor(null)} onSave={save} />}
    {viewingPlan && <BopPlanPreview plan={viewingPlan} onClose={() => setViewingPlan(null)} onOpen={() => { setSelectedId(viewingPlan.id); setViewingPlan(null); window.setTimeout(() => document.getElementById('bop-current-plan')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 40) }} />}
  </div>
}

const BOP_FIELDS = ['initiatives', 'activities', 'responsible_areas', 'resources', 'kpi_references', 'risks']
const BOP_EXAMPLES: Record<string, string> = {
  title: 'e.g. Campus Delivery Plan 2026–27',
  planning_period: 'e.g. July 2026 – June 2027',
  strategic_alignment: 'e.g. Improve learner outcomes, retention, and service delivery',
  timeline: 'e.g. Q1 planning · Q2 implementation · Q3 review · Q4 closure',
  initiatives: 'e.g. Student success programme\nDigital attendance improvement',
  activities: 'e.g. Hold monthly delivery review\nPublish action tracker',
  responsible_areas: 'e.g. Academic Office\nCampus Operations',
  resources: 'e.g. Faculty development allocation\nStudent support coordinator',
  kpi_references: 'e.g. Student retention ≥ 90%\nAttendance ≥ 85%',
  risks: 'e.g. Delayed resource approval\nFaculty capacity constraints',
  notes: 'e.g. Dependencies, assumptions, and review notes for the Vice Chairman',
}
function BopEditor({ plan, onCancel, onSave }: any) {
  const isEdit = Boolean(plan?.id)
  const initial = (key: string) => Array.isArray(plan?.[key]) ? plan[key].join('\n') : (plan?.[key] || '')
  const [form, setForm] = useState<any>(() => ({ title: initial('title'), planning_period: initial('planning_period'), strategic_alignment: initial('strategic_alignment'), initiatives: initial('initiatives'), activities: initial('activities'), responsible_areas: initial('responsible_areas'), resources: initial('resources'), timeline: initial('timeline'), kpi_references: initial('kpi_references'), risks: initial('risks'), notes: initial('notes') }))
  const update = (key: string, value: string) => setForm((current: any) => ({ ...current, [key]: value }))
  const save = () => onSave({ ...form, ...Object.fromEntries(BOP_FIELDS.map((field) => [field, String(form[field] || '').split('\n').map((item) => item.trim()).filter(Boolean)])) })
  const text = (label: string, field: string, list = false) => <label className={list ? 'bop-field bop-wide' : 'bop-field'}>{label}{list ? <textarea className="inp" value={form[field]} onChange={(event) => update(field, event.target.value)} placeholder={BOP_EXAMPLES[field] || 'One item per line'} /> : <input className="inp" value={form[field]} onChange={(event) => update(field, event.target.value)} placeholder={BOP_EXAMPLES[field]} />}</label>
  return <div className="bop-editor-overlay" role="dialog" aria-modal="true" aria-label={isEdit ? 'Edit Branch Operational Plan' : 'Create Branch Operational Plan'}><section className="campus-head-panel bop-editor"><header><div><span className="eyebrow">DRAFT WORKSPACE</span><h2>{isEdit ? 'Edit Branch Operational Plan' : 'Create Branch Operational Plan'}</h2><p>Use one line per item for lists. You can save and return before submitting for review.</p></div><button className="modal-x" aria-label="Close plan editor" onClick={onCancel}>×</button></header><div className="bop-form-grid">{text('Plan title', 'title')}{text('Planning period', 'planning_period')}{text('Strategic alignment', 'strategic_alignment')}{text('Timeline', 'timeline')}{text('Initiatives', 'initiatives', true)}{text('Activities', 'activities', true)}{text('Responsible areas', 'responsible_areas', true)}{text('Resources', 'resources', true)}{text('KPI references', 'kpi_references', true)}{text('Risks', 'risks', true)}{text('Notes', 'notes', true)}</div><footer><button className="btn btn-out" onClick={onCancel}>Cancel</button><button className="btn btn-crimson" disabled={!form.title.trim()} onClick={save}>Save Draft</button></footer></section></div>
}

function BopPlanPreview({ plan, onClose, onOpen }: any) {
  const detailRows = [
    ['Strategic alignment', plan.strategic_alignment], ['Timeline', plan.timeline], ['Initiatives', plan.initiatives], ['Activities', plan.activities], ['Responsible areas', plan.responsible_areas], ['Required resources', plan.resources], ['KPI references', plan.kpi_references], ['Risks and dependencies', plan.risks], ['Notes', plan.notes],
  ]
  return <div className="bop-editor-overlay bop-preview-overlay" role="dialog" aria-modal="true" aria-label={`Plan details: ${plan.title}`}>
    <section className="campus-head-panel bop-preview">
      <header><div><span className="eyebrow">SUBMITTED PLAN</span><h2>{plan.title}</h2><p>{plan.campus || 'Campus scope'} · {plan.planning_period || 'Planning period not recorded'}</p></div><button className="modal-x" aria-label="Close plan details" onClick={onClose}>×</button></header>
      <div className="bop-preview-status"><span className="status-chip">{plan.status}</span><span>Submitted {plan.submission?.submitted_at ? new Date(plan.submission.submitted_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : 'date not recorded'}</span></div>
      {plan.vc_review?.feedback && <div className="bop-feedback"><label>VICE CHAIRMAN FEEDBACK</label><p>{plan.vc_review.feedback}</p></div>}
      <div className="bop-detail-list bop-preview-list">{detailRows.map(([heading, content]: any) => <div className="bop-detail-row" key={heading}><label>{heading}</label><div>{Array.isArray(content) ? content.length ? <ul>{content.map((item: string, index: number) => <li key={`${index}-${item}`}>{item}</li>)}</ul> : <span>Not recorded</span> : <span>{content || 'Not recorded'}</span>}</div></div>)}</div>
      <footer><button className="btn btn-out" onClick={onClose}>Close</button><button className="btn btn-crimson" onClick={onOpen}>Show in workspace</button></footer>
    </section>
  </div>
}

/** Campus-scoped risk register backed by the target quality-risk service. */
export function CampusHeadRiskIssues() {
  const [risks, setRisks] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    api.campusHeadRisks().then((result: any) => setRisks(Array.isArray(result?.risks) ? result.risks : []))
      .catch((err: any) => setError(err?.message || 'Campus risk register is unavailable.'))
      .finally(() => setLoading(false))
  }, [])
  return <div className="fade-in campus-head-page risk-workspace">
    <div className="page-head"><div><h1>Risk &amp; Issues</h1><p>Campus-scoped academic and operational risk indicators.</p></div></div>
    <section className="campus-head-panel">{loading ? <div className="empty">Loading campus risks…</div> : error ? <div className="err-box">{error}</div> : !risks.length ? <div className="empty">No active campus risks match your authorized scope.</div> : <div className="campus-head-table-wrap"><table className="campus-head-table"><thead><tr><th>Risk</th><th>Department</th><th>Metric</th><th>Value</th><th>Threshold</th><th>Status</th></tr></thead><tbody>{risks.map((risk: any) => <tr key={risk.source_key || risk.id}><td><b>{risk.title || risk.source_key || 'Campus risk'}</b></td><td>{risk.department || 'Campus'}</td><td>{risk.metric_key || '—'}</td><td>{risk.metric_value ?? '—'}</td><td>{risk.threshold ?? '—'}</td><td>{risk.status || 'Open'}</td></tr>)}</tbody></table></div>}</section>
  </div>
}

/** Read-only asset oversight.  The API only returns canonical campus assets. */
export function InfrastructureOverview() {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.assets().then(setData).catch(() => setData({ data_status: 'unavailable', reason: 'Campus-scoped infrastructure data is unavailable.' })) }, [])
  const money = (v:any) => new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(Number(v || 0))
  if (!data) return <div className="fade-in campus-head-page infrastructure-overview"><div className="infrastructure-loading"><i/><span>Loading verified campus infrastructure…</span></div></div>
  const summary=data.summary||{}
  return <div className="fade-in campus-head-page infrastructure-overview"><div className="page-head"><div><span className="eyebrow">CAMPUS PERFORMANCE</span><h1>Infrastructure</h1><p>Campus asset and infrastructure status based on currently available asset inventory.</p></div></div><section className="campus-head-panel infrastructure-panel"><div className="campus-head-metrics">{[['Total tracked assets',summary.total],['Book value',data.data_status==='unavailable'?'Not available yet':money(summary.book_value)],['In service',summary.in_service],['Needs attention',summary.maintenance]].map(([label,value])=><div className="campus-head-metric" key={label as string}><label>{label}</label><strong>{value ?? 'Not available yet'}</strong></div>)}</div>{data.data_status==='unavailable'?<div className="campus-data-unavailable"><div className="campus-data-unavailable-mark">!</div><div><b>Campus asset register is awaiting ownership verification</b><p>{data.reason||'Campus-scoped infrastructure data is unavailable.'} Existing unassigned records remain intentionally hidden until an authorised inventory owner assigns them to this campus.</p></div></div>:data.assets?.length?<div className="tbl-scroll infrastructure-table"><table className="tbl"><thead><tr><th>Asset</th><th>Category</th><th>Location</th><th>Status</th><th>Value</th></tr></thead><tbody>{data.assets.map((a:any)=><tr key={a.id}><td><b>{a.name}</b><br/><small className="mono">{a.tag}</small></td><td>{a.category}</td><td>{a.location}</td><td><span className={`pill s-${a.status}`}>{a.status}</span></td><td>{money(a.value)}</td></tr>)}</tbody></table></div>:<CampusProfileEmptyState text="No campus-owned asset records are available."/>}</section></div>
}

const CAMPUS_RISK_CATEGORIES=['Academic','Student','Faculty/Workforce','Finance','Infrastructure','Operations','Compliance','Safety','Administration']
const CAMPUS_RISK_LEVELS=['LOW','MEDIUM','HIGH','CRITICAL']
const blankCampusRisk={title:'',description:'',category:'Operations',severity:'MEDIUM',likelihood:'MEDIUM',impact:'MEDIUM',priority:'MEDIUM',owner_id:'',due_at:''}
export function CampusRiskWorkspace() {
  const [risks,setRisks]=useState<any[]>([]),[owners,setOwners]=useState<any[]>([]),[summary,setSummary]=useState<any>({}),[filters,setFilters]=useState<any>({status:'',severity:'',category:'',owner_id:''}),[selected,setSelected]=useState<any>(null),[form,setForm]=useState<any>(blankCampusRisk),[editor,setEditor]=useState(false),[error,setError]=useState(''),[reason,setReason]=useState(''),[action,setAction]=useState<any>({description:'',owner_id:'',due_at:''})
  const load=()=>Promise.all([api.risks(filters),api.riskOwners(),api.riskSummary()]).then(([r,o,s]:any)=>{setRisks(r.risks||[]);setOwners(o.owners||[]);setSummary(s.summary||{})}).catch((e:any)=>setError(e.message||'Campus risk register is unavailable.'))
  useEffect(()=>{load()},[filters.status,filters.severity,filters.category,filters.owner_id])
  const open=(id:string)=>api.risk(id).then((r:any)=>{setSelected(r.risk);setReason('');setAction({description:'',owner_id:'',due_at:''})}).catch((e:any)=>setError(e.message))
  const save=async()=>{try{const body={...form,due_at:form.due_at?new Date(form.due_at).toISOString():null,expected_version:selected?.version_no};const r:any=editor&&selected?await api.updateRisk(selected.id,body):await api.createRisk(body);setEditor(false);setSelected(r.risk);load()}catch(e:any){setError(e.message||'Unable to save risk.')}}
  const transition=async(kind:string)=>{if(!selected||!reason.trim()){setError('A lifecycle reason is required.');return}try{const r:any=kind==='resolve'?await api.resolveRisk(selected.id,reason,reason):kind==='close'?await api.closeRisk(selected.id,reason):await api.escalateRisk(selected.id,reason);setSelected(r.risk);setReason('');load()}catch(e:any){setError(e.message||`Unable to ${kind} risk.`)}}
  const addAction=async()=>{if(!action.description.trim()||!selected)return;try{const r:any=await api.createRiskAction(selected.id,{...action,due_at:action.due_at?new Date(action.due_at).toISOString():null});setSelected(r.risk);setAction({description:'',owner_id:'',due_at:''});load()}catch(e:any){setError(e.message||'Unable to add corrective action.')}}
  const owner=(id:string)=>owners.find((x:any)=>x.id===id)?.name||'Unassigned'
  return <div className="fade-in campus-head-page risk-workspace"><header className="campus-workspace-header"><div><span className="eyebrow">CAMPUS / BRANCH HEAD</span><h1>Risk &amp; Issues</h1><p>Campus-scoped risks, corrective actions, and escalation status.</p></div><button className="btn btn-crimson" onClick={()=>{setForm(blankCampusRisk);setSelected(null);setEditor(true)}}>Create Risk / Issue</button></header>{error&&<div className="err-box">{error}</div>}<div className="campus-head-risk-grid risk-summary-strip">{[['Open Risks',summary.open],['High / Critical',summary.high_critical],['Overdue Actions',summary.overdue_actions],['Escalated',summary.escalated],['Resolved',summary.resolved]].map(([l,v])=><div className="risk-item" key={l as string}><label>{l}</label><strong>{v??'Not available yet'}</strong></div>)}</div><section className="workspace-filter-bar"><div className="risk-filters"><select className="select" value={filters.status} onChange={e=>setFilters({...filters,status:e.target.value})}><option value="">All statuses</option>{['OPEN','IN_PROGRESS','RESOLVED','CLOSED'].map(x=><option key={x}>{x}</option>)}</select><select className="select" value={filters.severity} onChange={e=>setFilters({...filters,severity:e.target.value})}><option value="">All severities</option>{CAMPUS_RISK_LEVELS.map(x=><option key={x}>{x}</option>)}</select><select className="select" value={filters.category} onChange={e=>setFilters({...filters,category:e.target.value})}><option value="">All categories</option>{CAMPUS_RISK_CATEGORIES.map(x=><option key={x}>{x}</option>)}</select><select className="select" value={filters.owner_id} onChange={e=>setFilters({...filters,owner_id:e.target.value})}><option value="">All owners</option>{owners.map((x:any)=><option value={x.id} key={x.id}>{x.name}</option>)}</select></div></section><section className="campus-head-panel"><div className="campus-head-table-wrap"><table className="campus-head-table"><thead><tr><th>Risk / Issue</th><th>Category</th><th>Severity</th><th>Priority</th><th>Owner</th><th>Status</th><th>Due</th></tr></thead><tbody>{risks.map((r:any)=><tr className="risk-row" onClick={()=>open(r.id)} key={r.id}><td><b>{r.title}</b><small>{r.description}</small></td><td>{r.category}</td><td>{r.severity}</td><td>{r.priority}</td><td>{owner(r.owner_id)}</td><td><span className="status-chip">{r.status}</span></td><td>{r.due_at?new Date(r.due_at).toLocaleDateString('en-IN'):'—'}</td></tr>)}{!risks.length&&<tr><td colSpan={7}><CampusProfileEmptyState text="No campus risks match the selected filters."/></td></tr>}</tbody></table></div></section>{editor&&<CampusRiskEditor form={form} setForm={setForm} owners={owners} onClose={()=>setEditor(false)} onSave={save}/>} {selected&&!editor&&<div className="modal-bg"><section className="modal risk-modal"><div className="modal-h"><div><h3>{selected.title}</h3><p>{selected.category} · {selected.campus_scope_id}</p></div><button className="modal-x" onClick={()=>setSelected(null)}>×</button></div><div className="modal-b"><div className="risk-detail-grid">{[['Status',selected.status],['Severity',selected.severity],['Likelihood / Impact',`${selected.likelihood} / ${selected.impact}`],['Due date',selected.due_at?new Date(selected.due_at).toLocaleDateString('en-IN'):'Not set']].map(([l,v])=><div className="campus-head-metric" key={l as string}><label>{l}</label><strong>{v}</strong></div>)}</div><p className="risk-description">{selected.description||'No description recorded.'}</p><h4>Corrective actions</h4>{selected.actions.map((a:any)=><div className="risk-action" key={a.id}><div><b>{a.description}</b><small>{owner(a.owner_id)} · {a.status}{a.overdue?' · Overdue':''}</small></div>{['OPEN','IN_PROGRESS'].includes(a.status)?<button className="btn btn-out btn-sm" onClick={async()=>{const r:any=await api.completeRiskAction(selected.id,a.id,'Completed');setSelected(r.risk);load()}}>Complete</button>:a.status==='COMPLETED'?<button className="btn btn-out btn-sm" onClick={async()=>{const r:any=await api.verifyRiskAction(selected.id,a.id);setSelected(r.risk);load()}}>Verify</button>:<span className="status-chip">Verified</span>}</div>)}{selected.allowed_actions.edit&&<div className="risk-form-grid"><label className="risk-form-wide">Action description<input className="inp" value={action.description} onChange={e=>setAction({...action,description:e.target.value})}/></label><label>Owner<select className="select" value={action.owner_id} onChange={e=>setAction({...action,owner_id:e.target.value})}><option value="">Unassigned</option>{owners.map((x:any)=><option value={x.id} key={x.id}>{x.name}</option>)}</select></label><label>Due date<input className="inp" type="datetime-local" value={action.due_at} onChange={e=>setAction({...action,due_at:e.target.value})}/></label><button className="btn btn-out" onClick={addAction}>Add action</button></div>}<label className="risk-form-wide">Lifecycle reason<textarea className="inp" value={reason} onChange={e=>setReason(e.target.value)} placeholder="Required for resolve, close, or escalate"/></label></div><div className="modal-f"><button className="btn btn-out" onClick={()=>{setForm({...selected,due_at:selected.due_at?.slice(0,16)||''});setEditor(true)}}>Edit</button>{selected.allowed_actions.resolve&&<button className="btn btn-out" onClick={()=>transition('resolve')}>Resolve</button>}{selected.allowed_actions.close&&<button className="btn btn-out" onClick={()=>transition('close')}>Close</button>}{selected.allowed_actions.escalate&&<button className="btn btn-crimson" onClick={()=>transition('escalate')}>Escalate</button>}</div></section></div>}</div>
}
function CampusRiskEditor({form,setForm,owners,onClose,onSave}:any){const select=(label:string,key:string,items:string[])=><label>{label}<select className="select" value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}>{items.map(x=><option key={x}>{x}</option>)}</select></label>;return <div className="modal-bg"><section className="modal risk-modal"><div className="modal-h"><h3>{form.id?'Edit Risk / Issue':'Create Risk / Issue'}</h3><button className="modal-x" onClick={onClose}>×</button></div><div className="modal-b risk-form-grid"><label>Title<input className="inp" value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label>{select('Category','category',CAMPUS_RISK_CATEGORIES)}<label className="risk-form-wide">Description<textarea className="inp" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label>{select('Severity','severity',CAMPUS_RISK_LEVELS)}{select('Likelihood','likelihood',CAMPUS_RISK_LEVELS)}{select('Impact','impact',CAMPUS_RISK_LEVELS)}{select('Priority','priority',CAMPUS_RISK_LEVELS)}<label>Owner<select className="select" value={form.owner_id} onChange={e=>setForm({...form,owner_id:e.target.value})}><option value="">Unassigned</option>{owners.map((x:any)=><option value={x.id} key={x.id}>{x.name}</option>)}</select></label><label>Due date<input className="inp" type="datetime-local" value={form.due_at||''} onChange={e=>setForm({...form,due_at:e.target.value})}/></label></div><div className="modal-f"><button className="btn btn-out" onClick={onClose}>Cancel</button><button className="btn btn-crimson" disabled={!form.title.trim()} onClick={onSave}>{form.id?'Save changes':'Create Risk / Issue'}</button></div></section></div>}
