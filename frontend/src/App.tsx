import { useEffect, useMemo, useState } from 'react'
import { api, getUser, logout, saveSession } from './api'
import Workflows from './views/Workflows'
import { ApprovalHistory, Escalations } from './views/PrincipalWorkflowViews'
import Delegations from './views/Delegations'
import Directory from './views/Directory'
import Matrices from './views/Matrices'
import AuditView from './views/Audit'
import Permissions from './views/Permissions'
import OfficeProfile from './views/OfficeProfile'
import Overview from './modules/Overview'
import Calendar from './modules/Calendar'
import MySchedule from './modules/MySchedule'
import AcademicCalendar from './modules/AcademicCalendar'
import Students from './modules/Students'
import Academics from './modules/Academics'
import Curriculum from './modules/Curriculum'
import CoursesSubjects from './modules/CoursesSubjects'
import Attendance from './modules/Attendance'
import Examinations from './modules/Examinations'
import Admissions from './modules/Admissions'
import Finance from './modules/Finance'
import Library from './modules/Library'
import HR from './modules/HR'
import FacultyStaff from './modules/FacultyStaff'
import Assets from './modules/Assets'
import Facilities from './modules/Facilities'
import PrincipalCompliance from './modules/PrincipalCompliance'
import PrincipalAtRisk from './modules/PrincipalAtRisk'
import Hostel from './modules/Hostel'
import Transport from './modules/Transport'
import Research from './modules/Research'
import Placements from './modules/Placements'
import Grievance from './modules/Grievance'
import Governance from './modules/Governance'
import ChairmanApprovals from './modules/ChairmanApprovals'
import ChairmanDelegation from './modules/ChairmanDelegation'
import AdminPanel from './modules/AdminPanel'
import Analytics from './modules/Analytics'
import Procurement from './modules/Procurement'
import Integrations from './modules/Integrations'
import StudentHome from './personas/StudentHome'
import { StudentAttendanceView, StudentCalendarView, StudentCoursesView, StudentExaminationsView, StudentFeesView, StudentLibraryView, StudentScoresView } from './personas/StudentViews'
import FacultyHome from './personas/FacultyHome'
import FacultySchedule from './personas/FacultySchedule'
import ParentHome from './personas/ParentHome'
import {
  CampusProfile, BranchOperationalPlan, DepartmentsPrograms, LeadershipTeam,
  AcademicSnapshot, StudentSnapshot, WorkforceOverview, InfrastructureOverview,
  MyRequests, PolicyRepository, CampusHeadDashboard, CampusHeadApprovals
} from './modules/CampusHeadPlaceholder'
import RiskIssues from './modules/RiskIssues'
import CampusEscalations from './modules/CampusEscalations'
import CampusReports from './modules/CampusReports'
import CampusOverview from './modules/CampusOverview'

const LEVEL_COLORS: Record<number, string> = {
  1: '#d92d3a',
  2: '#bf2431',
  3: '#2c5fb3',
  4: '#0d9488',
  5: '#0b7a70',
  6: '#6b4ea8',
  7: '#b97e1f',
  8: '#12855b',
}

const GROUP_ORDER = ['Workspace', 'Academics', 'Services', 'Operations', 'Platform', 'Authority', 'Reference']
const CHAIRMAN_GROUP_ORDER = ['Governance', 'Institution', 'Strategy & Insights', 'Support']
const CHAIRMAN_DISPLAY: Record<string, { label: string; group: string }> = {
  overview: { label: 'Overview', group: 'Governance' },
  governance: { label: 'Governance', group: 'Governance' },
  approvals: { label: 'Approvals', group: 'Governance' },
  academic_calendar: { label: 'Academic Calendar', group: 'Institution' },
  delegation: { label: 'Delegation', group: 'Governance' },
  audit: { label: 'Audit', group: 'Governance' },
  directory: { label: 'Institution', group: 'Institution' },
  finance: { label: 'Finance & Resources', group: 'Institution' },
  calendar: { label: 'Calendar', group: 'Support' },
  hr: { label: 'Strategic Initiatives', group: 'Strategy & Insights' },
  analytics: { label: 'Reports & Analytics', group: 'Strategy & Insights' },
  integrations: { label: 'Communications', group: 'Strategy & Insights' },
  workflows: { label: 'My Approvals', group: 'Support' },
  matrices: { label: 'Settings', group: 'Support' },
}

// Principal navigation intentionally follows the reference information architecture.
// Entries without a matching capability remain visible but disabled, so the UI does
// not imply that an unavailable backend workflow can be opened.
const PRINCIPAL_NAV = [
  ['Academic / People', 'Principal', 'overview'], ['Academic / People', 'At-Risk Students', 'at_risk_students'], ['Academic / People', 'Faculty & Staff', 'faculty_staff'], ['Academic / People', 'Leave', 'leave'], ['Academic / People', 'Recruitment / Vacancies', 'recruitment'],
  ['Finance & Operations', 'Finance', 'finance'], ['Finance & Operations', 'Procurement', 'procurement'], ['Finance & Operations', 'Facilities & Maintenance', 'facilities'],
  ['Finance & Operations', 'Assets', 'assets'], ['Finance & Operations', 'Hostel', 'hostel'], ['Finance & Operations', 'Transport', 'transport'],
  ['Approvals & Workflow', 'My Approvals', 'approvals'], ['Approvals & Workflow', 'Approval History', 'approval_history'], ['Approvals & Workflow', 'Workflows', 'workflows'], ['Approvals & Workflow', 'Escalations', 'escalations'], ['Approvals & Workflow', 'Delegation', 'delegation'],
  ['Governance & Risk', 'Accreditation & Compliance', 'compliance'],
  ['Audit & Reporting', 'Audit', 'audit'], ['Audit & Reporting', 'Reports', 'analytics'],
  ['Reference', 'Directory', 'directory'], ['Reference', 'Authority & Permissions', 'permissions'],
] as const

// Campus Head navigation — executive oversight and coordination role.
const CAMPUS_HEAD_NAV = [
  ['OVERVIEW', 'Dashboard', 'overview'],
  ['CAMPUS MANAGEMENT', 'Campus Profile', 'campus_profile'],
  ['CAMPUS MANAGEMENT', 'Branch Operational Plan', 'branch_operational_plan'],
  ['CAMPUS MANAGEMENT', 'Departments & Programs', 'departments_programs'],
  ['CAMPUS MANAGEMENT', 'Leadership Team', 'leadership_team'],
  ['CAMPUS MANAGEMENT', 'Campus Calendar', 'calendar'],
  ['PERFORMANCE', 'Campus Overview', 'campus_overview'],
  ['PERFORMANCE', 'Finance', 'finance'],
  ['PERFORMANCE', 'Infrastructure', 'infrastructure'],
  ['PERFORMANCE', 'Placements', 'placements'],
  ['PERFORMANCE', 'Risk & Issues', 'risk_issues'],
  ['AUTHORITY', 'My Approvals', 'approvals'],
  ['AUTHORITY', 'Delegation', 'delegation'],
  ['AUTHORITY', 'My Requests', 'my_requests'],
  ['AUTHORITY', 'Escalations', 'escalations'],
  ['REPORTS', 'Reports & Analytics', 'analytics'],
  ['REPORTS', 'Audit Trail', 'audit'],
  ['REFERENCE', 'Directory', 'directory'],
  ['REFERENCE', 'Policy Repository', 'policy_repository'],
] as const

// Faculty offices share the same functional modules, but need the focused
// teaching workspace described by the Professor Office information layout.
// A link is only interactive when its backing module is authorised.
const FACULTY_NAV = [
  ['Workspace', 'Overview', 'overview'], ['Workspace', 'My Schedule', 'my_schedule'], ['Workspace', 'Messages', 'workflows'],
  ['Teaching & Academics', 'My Sections', 'academics'], ['Teaching & Academics', 'Attendance', 'attendance'],
  ['Teaching & Academics', 'Assessments & Marks', 'examinations'], ['Teaching & Academics', 'Examinations', 'examinations'],
  ['Teaching & Academics', 'Course Materials', 'academics'], ['Teaching & Academics', 'Research & Publications', 'research'],
  ['Teaching & Academics', 'Projects & Guidance', 'research'], ['Teaching & Academics', 'Academic Calendar', 'academic_calendar'],
  ['Administration', 'Leave Requests', 'workflows'], ['Administration', 'My Requests & Approvals', 'workflows'],
  ['Reference', 'Directory', 'directory'], ['Reference', 'Profile', 'directory'],
] as const

const FACULTY_ACTIVE_LABEL: Record<string, string> = {
  overview: 'Overview', my_schedule: 'My Schedule', workflows: 'My Requests & Approvals',
  academics: 'My Sections', attendance: 'Attendance', examinations: 'Assessments & Marks',
  research: 'Research & Publications', academic_calendar: 'Academic Calendar', directory: 'Directory',
}

export default function App({ onLogout }: { onLogout: () => void }) {
  const [user, setUser] = useState<any>(getUser())
  const [ws, setWs] = useState<any>(null)
  const [view, setView] = useState('overview')
  const [sideOpen, setSideOpen] = useState(false)
  const [notifs, setNotifs] = useState<any>({ notifications: [], unread: 0 })
  const [workflowInboxCount, setWorkflowInboxCount] = useState(0)
  const [showNotif, setShowNotif] = useState(false)
  const [showRoles, setShowRoles] = useState(false)
  const [switching, setSwitching] = useState(false)

  function loadWs() {
    api.workspace().then(setWs).catch(() => {})
  }

  function loadNotifs() {
    api.notifications().then(setNotifs).catch(() => {})
  }

  function loadWorkflowInbox() {
    if (user?.office_n !== 4) return
    api.workflows('inbox').then((response: any) => setWorkflowInboxCount(response.total ?? response.workflows?.length ?? 0)).catch(() => {})
  }

  function refreshSignals() {
    loadNotifs()
    loadWorkflowInbox()
  }

  useEffect(() => {
    api.me().then(r => setUser(r.user)).catch(() => {})
    loadWs()
    loadNotifs()
    loadWorkflowInbox()
    const timer = setInterval(loadNotifs, 20000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!ws?.modules?.length) return
    // Faculty & Staff is a Principal-specific presentation of the authorised
    // HR module.  It has its own route so that the list/profile experience is
    // retained when opened from the dashboard KPI or the Principal sidebar.
    const principalVirtualModule = user?.office_n === 4 && ['faculty_staff', 'curriculum', 'courses_subjects', 'facilities', 'at_risk_students', 'compliance', 'approval_history', 'escalations', 'leave', 'recruitment', 'permissions'].includes(view)
    const campusHeadVirtualModule = user?.office_n === 3 && CAMPUS_HEAD_NAV.some(([, , key]) => key === view)
    if (!principalVirtualModule && !campusHeadVirtualModule && !ws.modules.some((module: any) => module.key === view)) {
      setView(ws.modules[0].key)
    }
  }, [ws, view, user?.office_n])

  async function pickRole(role: string) {
    if (role === user.active_role) {
      setShowRoles(false)
      return
    }
    setSwitching(true)
    try {
      const next = await api.switchRole(role)
      saveSession(next.token, next.user)
      setUser(next.user)
      setView('overview')
      loadWs()
    } catch (error) {
      // Keep the current session if the switch fails.
    }
    setSwitching(false)
    setShowRoles(false)
  }

  function doLogout() {
    logout()
    onLogout()
  }

  async function readAll() {
    for (const notif of notifs.notifications.filter((item: any) => !item.read)) {
      await api.readNotification(notif.id)
    }
    loadNotifs()
  }

  const rawModules = ws?.modules || []
  const displayModules = useMemo(
    () => rawModules
      .filter((module: any) => !(user?.persona === 'student' && module.key === 'students'))
      .map((module: any) => ({ ...module, ...displayMeta(user, module) })),
    [rawModules, user],
  )

  if (!user || !ws) {
    return <div className="center-load"><div className="spinner" /></div>
  }

  const color = LEVEL_COLORS[user.level] || '#c9a24a'
  const chairmanShell = user.office_n === 1
  const principalShell = user.office_n === 4
  const campusHeadShell = user.office_n === 3
  const facultyShell = user.persona === 'faculty'
  const campusHeadGroups = CAMPUS_HEAD_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const enabled = true
    ;(out[group] = out[group] || []).push({ key, label, group, enabled })
    return out
  }, {})
  const groups: Record<string, any[]> = {}
  displayModules.forEach((module: any) => {
    ;(groups[module.group] = groups[module.group] || []).push(module)
  })
  const order = chairmanShell ? CHAIRMAN_GROUP_ORDER : GROUP_ORDER
  const groupKeys = [...order.filter(key => groups[key]), ...Object.keys(groups).filter(key => !order.includes(key))]
  const campusHeadCurrentItem = Object.values(campusHeadGroups).flat().find((item: any) => item.key === view)
  const current = displayModules.find((module: any) => module.key === view)
    || (principalShell && (view === 'leave' || view === 'recruitment') ? displayModules.find((module: any) => module.key === 'hr') : undefined)
    || (campusHeadShell && campusHeadCurrentItem ? { key: view, label: campusHeadCurrentItem.label } : undefined)
    || displayModules[0]
  const principalGroups = PRINCIPAL_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const source = displayModules.find((module: any) => module.key === key)
      || (key === 'courses_subjects' ? displayModules.find((module: any) => module.key === 'academics') : undefined)
      || (key === 'faculty_staff' ? { key, label, group, enabled: true } : undefined)
      || (key === 'leave' || key === 'recruitment' ? displayModules.find((module: any) => module.key === 'hr') : undefined)
      || (key === 'facilities' ? displayModules.find((module: any) => module.key === 'assets') : undefined)
      || (key === 'at_risk_students' ? displayModules.find((module: any) => module.key === 'students') : undefined)
      || (key === 'compliance' ? displayModules.find((module: any) => module.key === 'governance') : undefined)
      || (key === 'approval_history' ? displayModules.find((module: any) => module.key === 'approvals') : undefined)
      || (key === 'escalations' ? displayModules.find((module: any) => module.key === 'workflows') : undefined)
      || (key === 'permissions' ? { key, label, group, enabled: true } : undefined)
    ;(out[group] = out[group] || []).push({ key, label, group, source, enabled: Boolean(source) })
    return out
  }, {})
  const facultyGroups = FACULTY_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const source = displayModules.find((module: any) => module.key === key)
    ;(out[group] = out[group] || []).push({ key, label, group, source, enabled: Boolean(source) })
    return out
  }, {})

  return (
    <div className={`app ${chairmanShell ? 'chairman-shell' : ''} ${principalShell ? 'principal-shell' : ''} ${campusHeadShell ? 'campus-head-shell' : ''} ${facultyShell ? 'faculty-shell' : ''}`}>
      <aside className={`sidebar ${sideOpen ? 'open' : ''}`}>
        <div className="brand">
          {campusHeadShell ? <div className="campus-head-brand">CAMPUS HEAD PORTAL</div> : <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="seal">IC</div>
            <div>
              <div className="brand-name">ICMS</div>
              <div className="brand-sub">{principalShell ? 'Principal Portal' : facultyShell ? 'University Group' : 'University Group'}</div>
            </div>
          </div>}
        </div>

        <div className="office-tag" style={{ ['--oc' as any]: color }}>
          <div className="ot-badge icon"><OfficeBadgeIcon /></div>
          <div style={{ minWidth: 0 }}>
            <div className="ot-office">{user.office}</div>
            <div className="ot-level">Level {user.level} - {toTitleCase(user.scope_level)} scope</div>
          </div>
        </div>

        <nav className="side-nav">
          {(principalShell ? Object.keys(principalGroups) : campusHeadShell ? Object.keys(campusHeadGroups) : facultyShell ? Object.keys(facultyGroups) : groupKeys).map(group => (
            <div key={group}>
              <div className="side-sec">{group}</div>
              {(principalShell ? principalGroups[group] : campusHeadShell ? campusHeadGroups[group] : facultyShell ? facultyGroups[group] : groups[group]).map((module: any) => (
                <button
                  key={(principalShell || campusHeadShell || facultyShell) ? `${group}-${module.label}` : module.key}
                  className={`nav-item ${(facultyShell ? FACULTY_ACTIVE_LABEL[view] === module.label : view === module.key) && (!(principalShell || campusHeadShell || facultyShell) || module.enabled) ? 'on' : ''} ${(principalShell || campusHeadShell || facultyShell) && !module.enabled ? 'nav-item-disabled' : ''}`}
                  onClick={() => {
                    if ((principalShell || campusHeadShell || facultyShell) && !module.enabled) return
                    setView(module.key)
                    setSideOpen(false)
                  }}
                  title={(principalShell || campusHeadShell || facultyShell) && !module.enabled ? 'This module is not available for your current role' : module.label}
                  type="button"
                >
                  <span className="ico">
                    <NavGlyph moduleKey={module.key} principal={principalShell} campusHead={campusHeadShell} />
                  </span>
                  <span className="nav-label">{module.label}</span>
                  {module.key === 'workflows' && (principalShell ? workflowInboxCount : notifs.unread) > 0 && (
                    <span className="badge">{principalShell ? workflowInboxCount : notifs.unread}</span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <div className="main">
        <div className="topbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <button className="icon-btn hamburger" onClick={() => setSideOpen(open => !open)} type="button">
              <MenuIcon />
            </button>
            <div className="crumb">{user.office} <b>/ {current?.label}</b></div>
          </div>

          <div className="top-right">
            <div style={{ position: 'relative' }}>
              <button className="role-btn" onClick={() => setShowRoles(open => !open)} type="button">
                <span className="role-dot" style={{ background: color }} />
                <span className="role-label">{user.active_role}</span>
                <span className="role-caret"><ChevronDownIcon /></span>
              </button>
              {showRoles && (
                <div className="role-panel">
                  <div className="rp-head">Switch role - {user.office}</div>
                  <div className="rp-sub">
                    One account, many roles. Your office authority stays the same while the role
                    adjusts the working lens shown across the workspace.
                  </div>
                  {(user.internal_roles || []).map((role: string, index: number) => (
                    <button
                      key={role}
                      className={`rp-item ${role === user.active_role ? 'active' : ''}`}
                      onClick={() => pickRole(role)}
                      disabled={switching}
                      type="button"
                    >
                      <span className="rp-star">{index === 0 ? '*' : '-'}</span>
                      <span>{role}</span>
                      {role === user.active_role && <span className="rp-check">Active</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div style={{ position: 'relative' }}>
              <button
                className="icon-btn bell-btn"
                onClick={() => {
                  setShowNotif(open => !open)
                  if (!showNotif) loadNotifs()
                }}
                type="button"
              >
                <BellIcon />
                {notifs.unread > 0 && <span className="notif-count">{notifs.unread}</span>}
              </button>
              {showNotif && (
                <div className="notif-panel">
                  <div className="card-h" style={{ padding: '14px 18px' }}>
                    <h3 style={{ fontSize: 16 }}>Notifications</h3>
                    <button className="linkish" onClick={readAll} type="button">Mark all read</button>
                  </div>
                  <div style={{ maxHeight: 380, overflowY: 'auto' }}>
                    {notifs.notifications.length === 0 && (
                      <div className="empty" style={{ padding: 30 }}>No notifications</div>
                    )}
                    {notifs.notifications.map((notif: any) => (
                      <div className="notif-item" key={notif.id} style={{ background: notif.read ? '#fff' : '#fdfbf5' }}>
                        <span
                          className="nd"
                          style={{
                            background:
                              notif.severity === 'critical'
                                ? 'var(--rose)'
                                : notif.severity === 'action'
                                  ? 'var(--brass)'
                                  : 'var(--teal)',
                          }}
                        />
                        <div>
                          <div className="nt">{notif.title}</div>
                          <div className="nb">{notif.body}</div>
                          <div className="na">{new Date(notif.at).toLocaleString()}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="top-user">
              <div className="avatar" style={{ background: color }}>{user.name?.[0] || 'U'}</div>
              <div>
                <div className="un">{user.active_role}</div>
                <div className="rl">{user.name}</div>
              </div>
            </div>

            <button className="btn-logout" onClick={doLogout} type="button">Sign out</button>
          </div>
        </div>

        <div
          className="content"
          onClick={() => {
            if (showNotif) setShowNotif(false)
            if (showRoles) setShowRoles(false)
          }}
        >
          <ModuleView view={view} module={current} user={user} onChange={refreshSignals} go={(next: string) => {
            const riskShortcut = user.office_n === 4 && next === 'students' && sessionStorage.getItem('principal-student-risk') === 'at-risk'
            setView(riskShortcut ? 'at_risk_students' : next)
          }} />
        </div>
      </div>
    </div>
  )
}

function ModuleView({ view, module, user, onChange, go }: any) {
  const caps = module?.actions || {}
  switch (view) {
    case 'overview':
      if (user.persona === 'student') return <StudentHome user={user} go={go} />
      if (user.persona === 'faculty') return <FacultyHome user={user} go={go} />
      if (user.persona === 'parent') return <ParentHome user={user} />
      return <Overview user={user} go={go} />
    case 'calendar':
      if (user.persona === 'student') return <StudentCalendarView user={user} go={go} />
      return <Calendar user={user} caps={caps} readOnly={user.office_n === 3} />
    case 'my_schedule':
      if (user.persona === 'faculty') return <FacultySchedule user={user} go={go} />
      return <MySchedule user={user} go={go} />
    case 'academic_calendar':
      return <AcademicCalendar user={user} caps={caps} />
    case 'integrations':
      return <Integrations caps={caps} />
    case 'analytics':
      return user.office_n === 3 ? <CampusReports /> : <Analytics user={user} />
    case 'students':
      if (user.persona === 'student') return <StudentHome user={user} go={go} />
      return <Students caps={caps} />
    case 'at_risk_students':
      return <PrincipalAtRisk />
    case 'academics':
      if (user.persona === 'student') return <StudentCoursesView />
      return <Academics caps={caps} />
    case 'curriculum':
      return <Curriculum />
    case 'courses_subjects':
      return <CoursesSubjects />
    case 'attendance':
      if (user.persona === 'student') return <StudentAttendanceView />
      return <Attendance caps={caps} />
    case 'examinations':
      if (user.persona === 'student') return <StudentExaminationsView go={go} />
      return <Examinations caps={caps} />
    case 'scores':
      if (user.persona === 'student') return <StudentScoresView />
      return <Examinations caps={caps} />
    case 'admissions':
      return <Admissions caps={caps} />
    case 'finance':
      if (user.persona === 'student') return <StudentFeesView />
      return <Finance caps={caps} readOnly={user.office_n === 3} />
    case 'library':
      if (user.persona === 'student') return <StudentLibraryView />
      return <Library caps={caps} />
    case 'hr':
      return <HR caps={caps} />
    case 'faculty_staff':
      return <FacultyStaff />
    case 'leave':
      return <HR caps={caps} principalView="leave" />
    case 'recruitment':
      return <HR caps={caps} principalView="recruitment" />
    case 'procurement':
      return <Procurement caps={caps} />
    case 'assets':
      return <Assets caps={caps} />
    case 'facilities':
      return <Facilities />
    case 'hostel':
      return <Hostel caps={caps} />
    case 'transport':
      return <Transport caps={caps} />
    case 'research':
      return <Research caps={caps} />
    case 'placements':
      return <Placements caps={caps} />
    case 'grievance':
      return <Grievance caps={caps} />
    case 'governance':
      return <Governance user={user} />
    case 'compliance':
      return <PrincipalCompliance go={go} />
    case 'admin':
      return <AdminPanel caps={caps} />
    case 'approvals':
      return user.office_n === 1
        ? <ChairmanApprovals user={user} onChange={onChange} />
        : user.office_n === 3
          ? <CampusHeadApprovals />
        : <Workflows user={user} onChange={onChange} />
    case 'workflows':
      return <Workflows user={user} onChange={onChange} />
    case 'approval_history':
      return <ApprovalHistory />
    case 'escalations':
      return user.office_n === 3 ? <CampusEscalations /> : <Escalations />
    case 'delegation':
      return user.office_n === 1 ? <ChairmanDelegation user={user} /> : <Delegations user={user} />
    case 'audit':
      return <AuditView />
    case 'directory':
      return <Directory user={user} />
    case 'matrices':
      return <Matrices />
    case 'permissions':
      return <Permissions user={user} />
    case 'office_profile':
      return <OfficeProfile user={user} />
    // Campus Head pages
    case 'campus_profile':
      return <CampusProfile />
    case 'branch_operational_plan':
      return <BranchOperationalPlan />
    case 'departments_programs':
      return <DepartmentsPrograms />
    case 'leadership_team':
      return <LeadershipTeam />
    case 'campus_overview':
      return <CampusOverview />
    case 'academic_snapshot':
      return <AcademicSnapshot />
    case 'student_snapshot':
      return <StudentSnapshot />
    case 'workforce':
      return <WorkforceOverview />
    case 'infrastructure':
      return <InfrastructureOverview />
    case 'risk_issues':
      return <RiskIssues />
    case 'my_requests':
      return <MyRequests user={user} onChange={onChange} />
    case 'policy_repository':
      return <PolicyRepository />
    default:
      return <Overview user={user} go={go} />
  }
}

function displayMeta(user: any, module: any) {
  if (user.office_n !== 1) return {}
  return CHAIRMAN_DISPLAY[module.key] || {}
}

function toTitleCase(value: string) {
  return String(value || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, char => char.toUpperCase())
}

function OfficeBadgeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
      <path d="M12 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </svg>
  )
}

function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M15 18H5.5a1.5 1.5 0 0 1-1.2-2.4l1.2-1.6V10a6.5 6.5 0 1 1 13 0v4l1.2 1.6A1.5 1.5 0 0 1 18.5 18H15" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </svg>
  )
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  )
}

function ChevronDownIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="m5 7 5 5 5-5" />
    </svg>
  )
}

function NavGlyph({ moduleKey, principal = false, campusHead = false }: { moduleKey: string; principal?: boolean; campusHead?: boolean }) {
  switch (moduleKey) {
    case 'overview':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1v-8.5Z" /></svg>
    case 'campus_profile':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 20h16" /><path d="M7 20V8l5-3 5 3v12" /><path d="M9 11h.01M15 11h.01M9 15h.01M15 15h.01" /></svg>
    case 'branch_operational_plan':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M11 5h8M11 9h8M11 13h5" /><path d="M6 4H4a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h2" /><path d="m8 17 2 2 4-4" /></svg>
    case 'departments_programs':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m3 8 9-4 9 4-9 4-9-4Z" /><path d="M7 10v4c0 1.7 2.2 3 5 3s5-1.3 5-3v-4" /></svg>
    case 'leadership_team':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="9" cy="8" r="3" /><circle cx="17" cy="9" r="2.3" /><path d="M3.5 20a5.5 5.5 0 0 1 11 0M14 20a4 4 0 0 1 6.5-3.1" /></svg>
    case 'academic_snapshot':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 0 4 23V5.5Z" /><path d="M12 3v18" /></svg>
    case 'student_snapshot':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m3 8 9-4 9 4-9 4-9-4Z" /><path d="M7 10v4c0 1.7 2.2 3 5 3s5-1.3 5-3v-4" /></svg>
    case 'workforce':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="7" r="3.5" /><path d="M5 20a7 7 0 0 1 14 0" /></svg>
    case 'infrastructure':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m14 6 4-4 2 2-4 4" /><path d="m13 7-8.5 8.5a2.1 2.1 0 1 0 3 3L16 10" /><path d="m5 5 3 3M4 10l2-2" /></svg>
    case 'my_requests':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 7h11M4 12h16M4 17h9" /><circle cx="18" cy="7" r="2" /><circle cx="9" cy="17" r="2" /></svg>
    case 'policy_repository':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M6 4h12v16H6z" /><path d="M9 4v16" /></svg>
    case 'at_risk_students':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 4 3.8 19h16.4L12 4Z" /><path d="M12 10v4M12 17h.01" /></svg>
    case 'faculty_staff':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="9" cy="8" r="3" /><circle cx="17" cy="9" r="2.3" /><path d="M3.5 20a5.5 5.5 0 0 1 11 0M14 20a4 4 0 0 1 6.5-3.1" /></svg>
    case 'leave':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 3v4M16 3v4M3 10h18M8 15l2 2 5-5" /></svg>
    case 'recruitment':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="4" y="7" width="16" height="12" rx="2" /><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M4 12h16M12 12v3" /></svg>
    case 'calendar':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 3v4M16 3v4M3 10h18" /><path d="M8 14h3M13 14h3M8 18h3" /></svg>
    case 'academic_calendar':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M7 2v4M17 2v4M3 9h18" /><path d="M7 13h10M7 17h6" /></svg>
    case 'governance':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 4 5 7v5c0 4.2 2.9 7.9 7 8.9 4.1-1 7-4.7 7-8.9V7l-7-3Z" /><path d="M9.5 12 11 13.5l3.5-4" /></svg>
    case 'compliance':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3 5 6v5c0 4.7 2.9 8.5 7 10 4.1-1.5 7-5.3 7-10V6l-7-3Z" /><path d="m9 12 2 2 4-4" /></svg>
    case 'approvals':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 4h7l5 5v11a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" /><path d="M14 4v5h5M9 14l2 2 4-4" /></svg>
    case 'approval_history':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.5" /><path d="M4 4v4.5h4.5M12 8v4l3 2" /></svg>
    case 'delegation':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="8" cy="8" r="3" /><circle cx="16" cy="16" r="3" /><path d="M10.5 10.5 13.5 13.5M5 18a4 4 0 0 1 6 0M13 6a4 4 0 0 1 6 0" /></svg>
    case 'audit':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M11 5h8M11 9h8M11 13h5" /><path d="M6 4H4a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h2" /><path d="m8 17 2 2 4-4" /></svg>
    case 'directory':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 20h16" /><path d="M7 20V8l5-3 5 3v12" /><path d="M9 11h.01M15 11h.01M9 15h.01M15 15h.01" /></svg>
    case 'finance':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 5h9M7 9h7M9 5c0 6 5 4 5 9 0 2-2 4-5 4" /></svg>
    case 'analytics':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 20h16" /><path d="M7 16V9M12 16V5M17 16v-3" /></svg>
    case 'hr':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="7" r="3.5" /><path d="M5 20a7 7 0 0 1 14 0" /></svg>
    case 'integrations':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m9 12 3-3 3 3" /><path d="m9 16 3-3 3 3" /><path d="M5 7h4M15 17h4M4 12h4M16 12h4" /></svg>
    case 'workflows':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 7h11M4 12h16M4 17h9" /><circle cx="18" cy="7" r="2" /><circle cx="9" cy="17" r="2" /></svg>
    case 'escalations':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 4 3.8 19h16.4L12 4Z" /><path d="M12 10v4M12 17h.01" /></svg>
    case 'matrices':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 4h16v16H4z" /><path d="M4 10h16M10 4v16" /></svg>
    case 'students':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m3 8 9-4 9 4-9 4-9-4Z" /><path d="M7 10v4c0 1.7 2.2 3 5 3s5-1.3 5-3v-4" /></svg>
    case 'academics':
    case 'curriculum':
    case 'courses_subjects':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 0 4 23V5.5Z" /><path d="M12 3v18" /></svg>
    case 'attendance':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m5 12 4 4 10-10" /></svg>
    case 'examinations':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 4h10l3 3v13H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" /><path d="M15 4v3h3M9 13h6M9 17h4" /></svg>
    case 'scores':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 20h16" /><path d="M7 16V9M12 16V5M17 16v-3" /><path d="M6 8 9 5l3 3 4-4 2 2" /></svg>
    case 'admissions':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3v18M3 12h18" /></svg>
    case 'library':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M6 4h12v16H6z" /><path d="M9 4v16" /></svg>
    case 'hostel':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 20h16M6 20V9l6-4 6 4v11M10 13h4M10 17h4" /></svg>
    case 'transport':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="4" y="5" width="16" height="11" rx="2" /><path d="M8 16v3M16 16v3M4 11h16" /><circle cx="8" cy="19" r="1" /><circle cx="16" cy="19" r="1" /></svg>
    case 'grievance':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M8 20h8M12 17v3M6 5h12l-1 8H7L6 5Z" /><path d="M9 9h6" /></svg>
    case 'research':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="10" cy="10" r="5" /><path d="m14 14 6 6" /></svg>
    case 'placements':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 20h16" /><path d="M7 16V9M12 16V5M17 16v-3" /><path d="m6 8 3-3 3 3 4-4 2 2" /></svg>
    case 'procurement':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m4 7 8-4 8 4-8 4-8-4Z" /><path d="M4 7v10l8 4 8-4V7" /></svg>
    case 'facilities':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m14 6 4-4 2 2-4 4" /><path d="m13 7-8.5 8.5a2.1 2.1 0 1 0 3 3L16 10" /><path d="m5 5 3 3M4 10l2-2" /></svg>
    case 'assets':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="4" y="5" width="16" height="14" rx="2" /><path d="M8 9h8M8 13h5" /></svg>
    case 'permissions':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 11a5 5 0 1 1 9.2 2.8L21 18.6 18.6 21l-1.7-1.7-1.5 1.5-2.2-2.2 1.5-1.5A5 5 0 0 1 7 11Z" /><circle cx="12" cy="11" r="1" /></svg>
    case 'admin':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" /><path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 1 1-4 0v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 1 1 0-4h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a2 2 0 1 1 4 0v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6H20a2 2 0 1 1 0 4h-.2a1 1 0 0 0-.9.6Z" /></svg>
    default:
      return principal || campusHead
        ? <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></svg>
        : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8" /></svg>
  }
}
