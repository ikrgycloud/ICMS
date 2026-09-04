import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Spinner } from './kit'

const icon = (value: string) => <span className={`principal-icon ${value}`}>{value === 'students' ? '♟' : value === 'staff' ? '♙' : value === 'attendance' ? '▣' : value === 'decision' ? '☑' : value === 'risk' ? '⚑' : value === 'alert' ? '!' : value === 'exam' ? '▤' : value === 'welfare' ? '♡' : '◈'}</span>

export default function PrincipalOverview({ user, go }: { user: any; go: (view: string) => void }) {
  const [data, setData] = useState<any>(null)
  const [workflows, setWorkflows] = useState<any[]>([])
  const [notifs, setNotifs] = useState<any[]>([])
  const [academicYear, setAcademicYear] = useState('—')

  useEffect(() => {
    let active = true
    Promise.all([api.overview(), api.workflows('inbox'), api.notifications(), api.academicCalendar()]).then(([overview, inbox, notifications, calendar]) => {
      if (!active) return
      setData(overview)
      setWorkflows(inbox.workflows || [])
      setNotifs(notifications.notifications || [])
      setAcademicYear(yearFromTerm(calendar.selected_term))
    }).catch(() => active && setData({ stats: {}, dept_distribution: {} }))
    return () => { active = false }
  }, [])

  const pending = workflows.filter(item => !['approved', 'executed', 'rejected'].includes(item.state))
  const departmentRows = useMemo(() => Object.entries(data?.dept_distribution || {}).slice(0, 5), [data])
  if (!data) return <Spinner />
  const s = data.stats || {}
  const studentRisk = Number(s.open_complaints || 0) + Number(s.pending_leave || 0)
  const cards = [
    ['Total Students', number(s.students), 'students', 'Live SIS total'],
    ['Faculty & Staff', number(s.faculty), 'staff', 'Live HR total'],
    ["Today's Attendance", '—', 'attendance', 'Attendance feed unavailable'],
    ['Needs My Decision', pending.length, 'decision', `${pending.filter(x => x.state === 'escalated').length} escalated`],
    ['At Risk Students', studentRisk, 'risk', 'Derived from open cases'],
    ['Critical Alerts', notifs.filter(x => x.severity === 'critical').length, 'alert', 'From your notifications'],
  ]

  return <div className="principal-dashboard fade-in">
    <section className="principal-welcome">
      <div>
        <h1>Good morning, Principal <span>👋</span></h1>
        <p>{user.scope || 'Campus'} <b>•</b> {user.office}</p>
        <small>▣ Academic Year: {academicYear} <i /> Last updated: {new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</small>
      </div>
      <div className="principal-context"><label>SEMESTER</label><strong>Even Semester⌄</strong></div>
    </section>

    <div className="principal-kpis">{cards.map(([label, value, kind, note]) => <button key={String(label)} className="principal-kpi" onClick={() => kind === 'decision' ? go('approvals') : kind === 'alert' ? go('workflows') : undefined} type="button">
      {icon(String(kind))}<div><span>{label}</span><b>{value}</b><small>{note}</small></div>
    </button>)}</div>

    <div className="principal-grid principal-top-grid">
      <Panel title="Needs My Decision" action="View all" onAction={() => go('approvals')}>
        <div className="principal-decision-list">{pending.slice(0, 5).map((item, index) => <button key={item.id} onClick={() => go('approvals')} className="principal-decision">
          <span className={`decision-mark d${index % 4}`}>●</span><span><b>{item.title || item.label}</b><small>{item.initiator || 'Workflow request'} · {item.label}</small></span><em>{item.state.replace('_', ' ')}</em>
        </button>)}{!pending.length && <EmptyLine text="No decisions are waiting for your office." />}</div>
        <div className="principal-statuses"><span>● Awaiting Approval ({pending.length})</span><span>● Escalated ({pending.filter(x => x.state === 'escalated').length})</span></div>
      </Panel>
      <Panel title="Attendance Trend" action="Open Details" onAction={() => go('analytics')}>
        <div className="principal-chart empty-chart"><div className="chart-grid" /><div className="chart-empty">Attendance trend data is not supplied by the current API.</div><div className="chart-legend"><span>● Student Attendance</span><span>● Faculty Attendance</span></div></div>
      </Panel>
      <Panel title="Academic Performance (Overall)" action="Open Analytics" onAction={() => go('analytics')}>
        <div className="principal-performance"><div className="performance-ring"><b>—</b><span>Performance</span></div><div className="performance-copy"><p><i className="blue" />CGPA and classification feed unavailable</p><p><i className="green" />Use Analytics for live enrolment</p><div className="performance-minis"><Mini value="—" label="Avg. CGPA" /><Mini value={studentRisk} label="Open cases" /><Mini value={number(s.sections)} label="Live sections" /></div></div></div>
      </Panel>
    </div>

    <div className="principal-grid principal-middle-grid">
      <Panel title="Examination Overview" action="Open Exams" onAction={() => go('examinations')}><MetricGrid items={[[number(s.sections), 'Live Sections'], ['—', 'Marks Submitted'], ['—', 'Pending Moderation'], [number(s.courses), 'Courses']]}/></Panel>
      <Panel title="Student Welfare" action="Open Students" onAction={() => go('students')}><MetricGrid items={[[studentRisk, 'Open Cases'], [number(s.open_complaints), 'Open Grievances'], [number(s.pending_leave), 'Leave Requests'], ['—', 'Disciplinary Cases']]}/></Panel>
      <Panel title="Campus Operations" action="Open Finance" onAction={() => go('finance')}><MetricGrid items={[[number(s.applications), 'Applications'], [number(s.projects), 'Research Projects'], [number(s.fees_due) ? '!' : '0', 'Fee Dues'], ['—', 'Facilities Alerts']]}/></Panel>
    </div>

    <div className="principal-grid principal-bottom-grid">
      <Panel title="Department Snapshot" action="Open Analytics" onAction={() => go('analytics')}><div className="department-list">{departmentRows.map(([dept, count]) => <div key={String(dept)}><span>{String(dept)}</span><b>{number(count)}</b><i style={{ width: `${Math.min(100, Number(count) / Math.max(1, ...departmentRows.map(x => Number(x[1]))) * 100)}%` }} /></div>)}{!departmentRows.length && <EmptyLine text="No department data available." />}</div></Panel>
      <Panel title="Recent Notifications" action="View all" onAction={() => go('workflows')}><div className="notification-list">{notifs.slice(0, 5).map(n => <div key={n.id}><i className={n.severity} /> <span>{n.title}</span><small>{timeAgo(n.created_at)}</small></div>)}{!notifs.length && <EmptyLine text="No recent notifications." />}</div></Panel>
      <Panel title="Quick Access"><div className="principal-quick">{[['My Approvals', 'approvals'], ['Delegations', 'delegation'], ['Reports', 'analytics'], ['Campus Directory', 'directory'], ['Communication', 'calendar'], ['Audit', 'audit']].map(([label, target]) => <button key={label} onClick={() => go(target)}><b>◈</b>{label}</button>)}</div></Panel>
    </div>
  </div>
}

function Panel({ title, action, onAction, children }: any) { return <section className="principal-panel"><header><h2>{title}</h2>{action && <button onClick={onAction}>{action}</button>}</header>{children}</section> }
function Mini({ value, label }: any) { return <div><b>{value}</b><small>{label}</small></div> }
function MetricGrid({ items }: { items: any[][] }) { return <div className="principal-metric-grid">{items.map(([value, label]) => <div key={label}><b>{value}</b><span>{label}</span></div>)}</div> }
function EmptyLine({ text }: { text: string }) { return <p className="principal-empty">{text}</p> }
function number(value: any) { return Number(value || 0).toLocaleString('en-IN') }
function timeAgo(value: string) { if (!value) return 'now'; const h = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 3600000)); return h ? `${h}h ago` : 'now' }
function yearFromTerm(term: string) {
  const termText = String(term || '')
  const termYear = Number(termText.match(/\d{4}/)?.[0])
  if (!Number.isFinite(termYear)) return '—'
  // The calendar seeds an odd term as 2026-Odd and its paired even term as
  // 2027-Even; both belong to the same 2026-27 academic year.
  const startYear = /-Even$/i.test(termText) ? termYear - 1 : termYear
  return `${startYear}-${String(startYear + 1).slice(-2)}`
}
