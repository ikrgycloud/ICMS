import { useEffect, useMemo, useState } from 'react'
import { HiOutlineAcademicCap, HiOutlineBanknotes, HiOutlineBookOpen, HiOutlineCalendarDays, HiOutlineChartBarSquare, HiOutlineCheckBadge, HiOutlineClipboardDocumentList, HiOutlineClock, HiOutlineCreditCard, HiOutlineDocumentCheck, HiOutlineDocumentCurrencyRupee, HiOutlineDocumentText, HiOutlineExclamationTriangle, HiOutlineFolder, HiOutlineGift, HiOutlineHome, HiOutlineLifebuoy, HiOutlineQueueList, HiOutlineScale, HiOutlineShieldCheck, HiOutlineSquares2X2, HiOutlineUserGroup, HiOutlineUserPlus, HiOutlineUsers } from 'react-icons/hi2'
import { api, getUser, logout, saveSession } from './api'
import Workflows from './views/Workflows'
import Delegations from './views/Delegations'
import Directory from './views/Directory'
import Matrices from './views/Matrices'
import AuditView from './views/Audit'
import Permissions from './views/Permissions'
import OfficeProfile from './views/OfficeProfile'
import Overview from './modules/Overview'
import DirectorAdmissionsDashboard from './modules/DirectorAdmissionsDashboard'
import Calendar from './modules/Calendar'
import MySchedule from './modules/MySchedule'
import AcademicCalendar from './modules/AcademicCalendar'
import AcademicRollover from './modules/AcademicRollover'
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
import Hostel from './modules/Hostel'
import Transport from './modules/Transport'
import Research from './modules/Research'
import Placements from './modules/Placements'
import Grievance from './modules/Grievance'
import Governance from './modules/Governance'
import DeanAcademicsDashboard from './modules/DeanAcademicsDashboard'
import DeanAcademicWorkspaces from './modules/DeanAcademicWorkspaces'
import DeanPrograms from './modules/DeanPrograms'
import DecisionInbox from './modules/DecisionInbox'
import MyRequests from './modules/MyRequests'
import ChairmanApprovals from './modules/ChairmanApprovals'
import ChairmanDelegation from './modules/ChairmanDelegation'
import AdminPanel from './modules/AdminPanel'
import Analytics from './modules/Analytics'
import Procurement from './modules/Procurement'
import Integrations from './modules/Integrations'
import StudentHome from './personas/StudentHome'
import { StudentAttendanceView, StudentCalendarView, StudentCoursesView, StudentExaminationsView, StudentFeesView, StudentLibraryView, StudentScoresView } from './personas/StudentViews'
import FacultyHome from './personas/FacultyHome'
import AssociateProfessorHome from './personas/AssociateProfessorHome'
import FacultySchedule from './personas/FacultySchedule'
import ParentHome from './personas/ParentHome'
import FrontDeskWorkspace from './frontdesk/FrontDeskWorkspace'

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
const DEAN_ACADEMICS_NAV = [
  ['Workspace', 'Overview', 'overview'],
  ['Academic Planning', 'Programs', 'dean_programs'], ['Academic Planning', 'Curriculum', 'curriculum'], ['Academic Planning', 'Courses', 'courses_subjects'],
  ['Academic Operations', 'Academic Calendar', 'academic_calendar'], ['Academic Operations', 'Timetable', 'dean_timetable'], ['Academic Operations', 'Faculty Allocation', 'dean_allocation'],
  ['Academic Quality', 'Performance & Results', 'analytics'], ['Academic Quality', 'Academic Risk', 'dean_risk'],
  ['Authority', 'My Approvals', 'decision_inbox'], ['Authority', 'My Requests', 'workflows'],
  ['Reports', 'Reports & Analytics', 'dean_reports'], ['Reports', 'Audit', 'audit'],
  ['Reference', 'Directory', 'directory'],
] as const
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
  ['Workspace', 'Dashboard', 'overview'], ['Workspace', 'My Schedule', 'my_schedule'],
  ['Academics', 'Academic Calendar', 'academic_calendar'], ['Academics', 'Curriculum', 'curriculum'],
  ['Academics', 'Courses & Subjects', 'courses_subjects'], ['Academics', 'Timetable', 'calendar'],
  ['Academics', 'Academic Performance', 'analytics'],
  ['Students', 'Students', 'students'], ['Students', 'Admissions', 'admissions'], ['Students', 'Attendance', 'attendance'],
  ['Students', 'Performance', 'analytics'], ['Students', 'Student Welfare', 'grievance'], ['Students', 'Discipline & Grievances', 'grievance'],
  ['Examination', 'Exams', 'examinations'],
  ['People & Workforce', 'Faculty & Staff', 'faculty_staff'], ['People & Workforce', 'Leave', 'leave'], ['People & Workforce', 'Recruitment / Vacancies', 'recruitment'],
  ['Finance & Operations', 'Finance', 'finance'], ['Finance & Operations', 'Procurement', 'procurement'], ['Finance & Operations', 'Facilities & Maintenance', 'assets'],
  ['Finance & Operations', 'Assets', 'assets'], ['Finance & Operations', 'Hostel', 'hostel'], ['Finance & Operations', 'Transport', 'transport'],
  ['Approvals & Workflow', 'My Approvals', 'approvals'], ['Approvals & Workflow', 'Escalations', 'workflows'], ['Approvals & Workflow', 'Workflows', 'workflows'], ['Approvals & Workflow', 'Delegation', 'delegation'],
  ['Audit & Reporting', 'Audit', 'audit'], ['Audit & Reporting', 'Reports', 'analytics'],
  ['Reference', 'Directory', 'directory'], ['Reference', 'Authority & Permissions', 'matrices'],
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

const DIRECTOR_ADMISSIONS_NAV = [
  ['Overview', 'Overview', 'overview'],
  ['Admissions Planning', 'Admission Cycles', 'director_cycles'], ['Admissions Planning', 'Programs & Intake', 'director_programs'], ['Admissions Planning', 'Quotas', 'director_quotas'],
  ['Applications', 'All Applications', 'director_applications'], ['Applications', 'Corrections', 'director_corrections'], ['Applications', 'Document Verification', 'director_document_verification'], ['Applications', 'Document Status', 'director_documents'],
  ['Eligibility & Selection', 'Eligibility Queue', 'director_eligibility'], ['Eligibility & Selection', 'Eligibility Rules', 'director_rules'], ['Eligibility & Selection', 'Merit & Rankings', 'director_merit'], ['Eligibility & Selection', 'Counselling', 'director_counselling'],
  ['Seat Management', 'Seat Pools', 'director_seat_pools'], ['Seat Management', 'Seat Allocation', 'director_allocation'], ['Seat Management', 'Waitlist', 'director_waitlist'],
  ['Offers', 'Offer Recommendations', 'director_recommendations'], ['Offers', 'Approval Inbox', 'approvals'], ['Offers', 'Issued Offers', 'director_offers'], ['Offers', 'Offer Status', 'director_offer_status'],
  ['Applicant Finance', 'Finance Status', 'director_finance'], ['Applicant Finance', 'Invoices & Challans', 'director_invoices'], ['Applicant Finance', 'Payment Status', 'director_payment_status'], ['Applicant Finance', 'Accounts Verification', 'director_accounts'], ['Applicant Finance', 'Finance Clearance', 'director_clearance'],
  ['Final Admission', 'Final Approval', 'director_final_approval'], ['Final Admission', 'Ready to Admit', 'director_ready'], ['Final Admission', 'Enrollment Queue', 'director_enrollment_queue'], ['Final Admission', 'Student Conversion', 'director_conversion'], ['Final Admission', 'Enrollment Status', 'director_enrollment'],
  ['Special Admissions', 'Scholarship Admissions', 'director_scholarship'], ['Special Admissions', 'International Admissions', 'director_international'],
  ['Applicant Support', 'Application Status', 'director_applications'], ['Applicant Support', 'Helpdesk / Support', 'workflows'],
  ['Reports', 'Reports', 'director_reports'], ['Calendar', 'Calendar', 'calendar'],
] as const

const DIRECTOR_TAB: Record<string, string> = {
  director_cycles: 'cycles', director_programs: 'program_intake', director_quotas: 'quotas',
  director_applications: 'applications', director_review: 'review', director_corrections: 'corrections', director_document_verification: 'review', director_documents: 'document_status',
  director_eligibility: 'eligibility', director_rules: 'rules', director_assessments: 'decisions', director_merit: 'decisions', director_counselling: 'counselling', director_seat_pools: 'seatpools', director_allocation: 'decisions', director_waitlist: 'waitlist', director_recommendations: 'offers', director_offers: 'issued_offers',
  director_ready: 'ready_to_admit', director_enrollment_queue: 'enrollment_queue', director_conversion: 'student_conversion', director_enrollment: 'enrollment_status', director_finance: 'finance_status', director_invoices: 'invoices_challans', director_payment_status: 'payment_status', director_accounts: 'accounts_verification', director_clearance: 'clearance_status',
  director_final_approval: 'final_approval',
  director_offer_status: 'offers', director_scholarship: 'eligibility', director_international: 'applications', director_reports: 'reports',
}

const ADMISSION_MANAGER_NAV = [
  ['Overview', 'Overview', 'overview'],
  ['Admissions Planning', 'Admission Cycles', 'manager_cycles'], ['Admissions Planning', 'Programs & Intake', 'manager_programs'], ['Admissions Planning', 'Quotas', 'manager_quotas'],
  ['Applications', 'All Applications', 'manager_applications'], ['Applications', 'Corrections', 'manager_corrections'], ['Applications', 'Document Status', 'manager_documents'],
  ['Eligibility & Selection', 'Eligibility Queue', 'manager_eligibility'], ['Eligibility & Selection', 'Eligibility Rules', 'manager_rules'], ['Eligibility & Selection', 'Assessments & Merit', 'manager_assessments'], ['Eligibility & Selection', 'Counselling', 'manager_counselling'],
  ['Seat Management', 'Seat Pools', 'manager_seat_pools'], ['Seat Management', 'Allocation', 'manager_allocation'], ['Seat Management', 'Waitlist', 'manager_waitlist'],
  ['Offers', 'Offer Recommendations', 'manager_recommendations'], ['Offers', 'Offer Status', 'manager_offers'],
  ['Applicant Finance', 'Finance Status', 'manager_finance'], ['Applicant Finance', 'Invoices & Challans', 'manager_invoices'], ['Applicant Finance', 'Clearance Status', 'manager_clearance'],
  ['Final Admission', 'Ready to Admit', 'manager_ready'], ['Final Admission', 'Enrollment Status', 'manager_enrollment'],
  ['Reports', 'Reports', 'manager_reports'], ['Calendar', 'Calendar', 'calendar'],
] as const

const ADMISSION_MANAGER_TAB: Record<string, string> = {
  manager_cycles: 'cycles', manager_programs: 'program_intake', manager_quotas: 'quotas',
  manager_applications: 'applications', manager_review: 'review', manager_corrections: 'corrections', manager_documents: 'document_status',
  manager_eligibility: 'eligibility', manager_rules: 'rules', manager_assessments: 'decisions', manager_counselling: 'counselling',
  manager_seat_pools: 'seatpools', manager_allocation: 'decisions', manager_waitlist: 'waitlist',
  manager_recommendations: 'recommendations', manager_offers: 'issued_offers',
  manager_finance: 'finance_status', manager_invoices: 'invoices_challans', manager_clearance: 'clearance_status',
  manager_ready: 'ready_to_admit', manager_enrollment: 'enrollment_status', manager_reports: 'reports',
}

export default function App({ onLogout }: { onLogout: () => void }) {
  const [user, setUser] = useState<any>(getUser())
  const [ws, setWs] = useState<any>(null)
  const [view, setView] = useState('overview')
  const [sideOpen, setSideOpen] = useState(false)
  const [notifs, setNotifs] = useState<any>({ notifications: [], unread: 0 })
  const [approvalCount, setApprovalCount] = useState(0)
  const [showNotif, setShowNotif] = useState(false)
  const [showRoles, setShowRoles] = useState(false)
  const [switching, setSwitching] = useState(false)
  const [collapsedDirectorGroups, setCollapsedDirectorGroups] = useState<Record<string, boolean>>({})
  const [collapsedDeanGroups, setCollapsedDeanGroups] = useState<Record<string, boolean>>({})

  function loadWs() {
    api.workspace().then(setWs).catch(() => {})
  }

  function loadNotifs() {
    api.notifications().then(setNotifs).catch(() => {})
  }

  function loadApprovalCount() {
    if (user?.office_n === 6) api.governanceInbox().then((result: any) => setApprovalCount(Number(result.summary?.pending ?? result.count ?? 0))).catch(() => {})
  }

  useEffect(() => {
    api.me().then(r => setUser(r.user)).catch(() => {})
    loadWs()
    loadNotifs()
    loadApprovalCount()
    const timer = setInterval(loadNotifs, 20000)
    const approvalTimer = setInterval(loadApprovalCount, 20000)
    const approvalUpdated = () => loadApprovalCount()
    window.addEventListener('icms:approval-updated', approvalUpdated)
    return () => { clearInterval(timer); clearInterval(approvalTimer); window.removeEventListener('icms:approval-updated', approvalUpdated) }
  }, [])

  useEffect(() => {
    const hashView = window.location.hash.replace(/^#/, '')
    if (hashView && hashView !== view) {
      setView(hashView)
    }
  }, [])

  useEffect(() => {
    const hashView = window.location.hash.replace(/^#/, '')
    if (hashView !== view) {
      window.location.hash = view || 'overview'
    }
  }, [view])

  useEffect(() => {
    if (!ws?.modules?.length) return
    // Faculty & Staff is a Principal-specific presentation of the authorised
    // HR module.  It has its own route so that the list/profile experience is
    // retained when opened from the dashboard KPI or the Principal sidebar.
    const virtualModule = (user?.office_n === 4 && ['faculty_staff', 'curriculum', 'courses_subjects'].includes(view)) || (user?.office_n === 6 && ['courses_subjects', 'decision_inbox', 'dean_programs', 'dean_timetable', 'dean_allocation', 'dean_risk', 'dean_reports', 'analytics'].includes(view)) || view.startsWith('director_') || view.startsWith('manager_')
    // Finance is a student self-service destination even though students do
    // not receive the staff Finance workspace capability from the backend.
    if (!virtualModule && !(user?.persona === 'student' && view === 'finance') && !ws.modules.some((module: any) => module.key === view)) {
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
    () => {
      const modules = rawModules
      .filter((module: any) => !(user?.persona === 'student' && module.key === 'students'))
      // Finance Manager works only with fee operations and fee-approval tasks.
      // Governance matrices and generic administration screens are not part of this portal.
      .filter((module: any) => user?.office_n !== 22 || ['overview', 'finance', 'rollover', 'approvals', 'audit'].includes(module.key))
      .filter((module: any) => module && module.key)
      .map((module: any) => ({ ...module, actions: module.actions || {}, ...displayMeta(user, module) }))
      if (user?.persona === 'student' && !modules.some((module: any) => module.key === 'finance')) {
        modules.push({ key: 'finance', label: 'Fees & Payments', group: 'Student Services', enabled: true })
      }
      return modules
    },
    [rawModules, user],
  )

  if (!user || !ws) {
    return <div className="center-load"><div className="spinner" /></div>
  }

  const color = LEVEL_COLORS[user.level] || '#c9a24a'
  const chairmanShell = user.office_n === 1
  const principalShell = user.office_n === 4
  const deanAcademicsShell = user.office_n === 6
  const facultyShell = user.persona === 'faculty'
  const directorAdmissionsShell = user.office_n === 15 && user.active_role === 'Director of Admissions'
  // The seeded office role is named “Admissions Manager”; accept the singular
  // wording from requirements too so both authorised role labels share this shell.
  const admissionManagerShell = ['Admission Manager', 'Admissions Manager'].includes(user.active_role)
  const admissionsOperationsShell = directorAdmissionsShell || admissionManagerShell
  const admissionOfficeSingleRole = user.office_n === 15
  const groups: Record<string, any[]> = {}
  displayModules.forEach((module: any) => {
    ;(groups[module.group] = groups[module.group] || []).push(module)
  })
  const order = chairmanShell ? CHAIRMAN_GROUP_ORDER : GROUP_ORDER
  const groupKeys = [...order.filter(key => groups[key]), ...Object.keys(groups).filter(key => !order.includes(key))]
  const principalGroups = PRINCIPAL_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const source = displayModules.find((module: any) => module.key === key)
      || (key === 'courses_subjects' ? displayModules.find((module: any) => module.key === 'academics') : undefined)
      || (key === 'faculty_staff' ? { key, label, group, enabled: true } : undefined)
    ;(out[group] = out[group] || []).push({ key, label, group, source, enabled: Boolean(source) })
    return out
  }, {})
  const deanGroups = DEAN_ACADEMICS_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const source = displayModules.find((module: any) => module.key === key) || { key, actions: {} }
    ;(out[group] = out[group] || []).push({ key, label, group, source, enabled: true })
    return out
  }, {})
  const deanGroupKeys = [...new Set(DEAN_ACADEMICS_NAV.map(([group]) => group))]
  const facultyGroups = FACULTY_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const source = displayModules.find((module: any) => module.key === key)
    ;(out[group] = out[group] || []).push({ key, label, group, source, enabled: Boolean(source) })
    return out
  }, {})
  const directorGroups = DIRECTOR_ADMISSIONS_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const backingKey = DIRECTOR_TAB[key] ? 'admissions' : key
    const source = displayModules.find((module: any) => module.key === backingKey)
    ;(out[group] = out[group] || []).push({ key, label, group, source, actions: source?.actions || {}, enabled: Boolean(source), backingKey })
    return out
  }, {})
  const directorGroupKeys = [...new Set(DIRECTOR_ADMISSIONS_NAV.map(([group]) => group))]
  const managerGroups = ADMISSION_MANAGER_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const backingKey = ADMISSION_MANAGER_TAB[key] ? 'admissions' : key
    const source = displayModules.find((module: any) => module.key === backingKey)
    ;(out[group] = out[group] || []).push({ key, label, group, source, actions: source?.actions || {}, enabled: Boolean(source), backingKey })
    return out
  }, {})
  const managerGroupKeys = [...new Set(ADMISSION_MANAGER_NAV.map(([group]) => group))]
  const activeAdmissionsGroups = directorAdmissionsShell ? directorGroups : managerGroups
  const activeAdmissionsGroupKeys = directorAdmissionsShell ? directorGroupKeys : managerGroupKeys
  const current = (deanAcademicsShell
    ? Object.values(deanGroups).flat().find((module: any) => module.key === view)
    : admissionsOperationsShell
    ? Object.values(activeAdmissionsGroups).flat().find((module: any) => module.key === view)
    : undefined) || displayModules.find((module: any) => module.key === view) || displayModules[0]

  return (
    <div className={`app ${chairmanShell ? 'chairman-shell' : ''} ${principalShell ? 'principal-shell' : ''} ${facultyShell ? 'faculty-shell' : ''} ${deanAcademicsShell ? 'dean-academics-shell' : ''} ${directorAdmissionsShell ? 'director-admissions-shell' : ''} ${admissionManagerShell ? 'admission-manager-shell' : ''}`}>
      <aside className={`sidebar ${sideOpen ? 'open' : ''}`}>
        <div className="brand">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="seal">IC</div>
            <div>
              <div className="brand-name">ICMS</div>
              <div className="brand-sub">{principalShell ? 'Principal Portal' : directorAdmissionsShell ? 'Admissions Directorate' : admissionManagerShell ? 'Admissions Operations' : facultyShell ? 'University Group' : 'University Group'}</div>
            </div>
          </div>
        </div>

        <div className="office-tag" style={{ ['--oc' as any]: color }}>
          <div className="ot-badge icon"><OfficeBadgeIcon /></div>
          <div style={{ minWidth: 0 }}>
            <div className="ot-office">{user.office}</div>
            <div className="ot-level">Level {user.level} - {toTitleCase(user.scope_level)} scope</div>
          </div>
        </div>

        <nav className="side-nav">
          {(deanAcademicsShell ? deanGroupKeys : principalShell ? Object.keys(principalGroups) : facultyShell ? Object.keys(facultyGroups) : admissionsOperationsShell ? activeAdmissionsGroupKeys : groupKeys).map(group => (
            <div key={group}>
              {deanAcademicsShell || admissionsOperationsShell ? <button className="side-sec director-nav-group" onClick={() => deanAcademicsShell ? setCollapsedDeanGroups(current => ({ ...current, [group]: !current[group] })) : setCollapsedDirectorGroups(current => ({ ...current, [group]: !current[group] }))} type="button">{group}<span>{(deanAcademicsShell ? collapsedDeanGroups[group] : collapsedDirectorGroups[group]) ? '+' : '−'}</span></button> : <div className="side-sec">{group}</div>}
              {((!deanAcademicsShell && !admissionsOperationsShell) || (deanAcademicsShell ? !collapsedDeanGroups[group] : !collapsedDirectorGroups[group])) && (deanAcademicsShell ? deanGroups[group] : principalShell ? principalGroups[group] : facultyShell ? facultyGroups[group] : admissionsOperationsShell ? activeAdmissionsGroups[group] : groups[group]).map((module: any) => (
                <button
                  key={(deanAcademicsShell || principalShell || facultyShell || admissionsOperationsShell) ? `${group}-${module.label}` : module.key}
                  className={`nav-item ${(facultyShell ? FACULTY_ACTIVE_LABEL[view] === module.label : view === module.key) && (!(deanAcademicsShell || principalShell || facultyShell || admissionsOperationsShell) || module.enabled) ? 'on' : ''}`}
                  onClick={() => {
                    setView(module.key)
                    setSideOpen(false)
                  }}
                  title={module.label}
                  type="button"
                >
                  <span className="ico">
                    <NavGlyph moduleKey={module.backingKey || module.key} label={admissionsOperationsShell ? module.label : undefined} />
                  </span>
                  <span className="nav-label">{module.label}</span>
                  {module.key === 'decision_inbox' && deanAcademicsShell && approvalCount > 0 && (
                    <span className="badge">{approvalCount}</span>
                  )}
                  {module.key === 'workflows' && !deanAcademicsShell && notifs.unread > 0 && (
                    <span className="badge">{notifs.unread}</span>
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
              <button className="role-btn" onClick={() => !admissionOfficeSingleRole && setShowRoles(open => !open)} type="button">
                <span className="role-dot" style={{ background: color }} />
                <span className="role-label">{user.active_role}</span>
                {!admissionOfficeSingleRole && <span className="role-caret"><ChevronDownIcon /></span>}
              </button>
              {!admissionOfficeSingleRole && showRoles && (
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
          <ModuleView view={view} module={current} user={user} onChange={loadNotifs} go={setView} />
        </div>
      </div>
    </div>
  )
}

function ModuleView({ view, module, user, onChange, go }: any) {
  const caps = module?.actions || {}
  if (user.office_n === 35) return <FrontDeskWorkspace view={view} />
  if (view.startsWith('director_')) {
    if (DIRECTOR_TAB[view]) return <Admissions caps={caps} initialTab={DIRECTOR_TAB[view]} sidebarNavigation />
  }
  if (view.startsWith('manager_')) {
    if (ADMISSION_MANAGER_TAB[view]) return <Admissions caps={caps} initialTab={ADMISSION_MANAGER_TAB[view]} sidebarNavigation />
  }
  switch (view) {
    case 'decision_inbox':
      return <DecisionInbox />
    case 'dean_programs':
      return <DeanPrograms />
    case 'overview':
      if (user.office_n === 6) return <DeanAcademicsDashboard go={go} />
      if (user.office_n === 15 && user.active_role === 'Director of Admissions') return <DirectorAdmissionsDashboard user={user} go={go} />
      if (user.persona === 'student') return <StudentHome user={user} go={go} />
      if (user.office_n === 12) return <AssociateProfessorHome go={go} />
      if (user.persona === 'faculty') return <FacultyHome user={user} go={go} />
      if (user.persona === 'parent') return <ParentHome user={user} />
      return <Overview user={user} go={go} />
    case 'calendar':
      if (user.persona === 'student') return <StudentCalendarView user={user} go={go} />
      return <Calendar user={user} caps={caps} />
    case 'my_schedule':
      if (user.persona === 'faculty') return <FacultySchedule user={user} go={go} />
      return <MySchedule user={user} go={go} />
    case 'academic_calendar':
      return <AcademicCalendar user={user} caps={caps} />
    case 'rollover':
      return <AcademicRollover user={user} />
    case 'integrations':
      return <Integrations caps={caps} />
    case 'analytics':
      return <Analytics user={user} go={go} />
    case 'students':
      if (user.persona === 'student') return <StudentHome user={user} go={go} />
      return <Students caps={caps} />
    case 'academics':
      if (user.office_n === 6) return <DeanAcademicWorkspaces />
      if (user.persona === 'student') return <StudentCoursesView />
      return <Academics caps={caps} />
    case 'dean_timetable':
      return <DeanAcademicWorkspaces initialTab="readiness" />
    case 'dean_allocation':
      return <DeanAcademicWorkspaces initialTab="allocation" />
    case 'dean_risk':
      return <DeanAcademicWorkspaces initialTab="risk" />
    case 'dean_reports':
      return <DeanAcademicWorkspaces initialTab="reports" />
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
      if (user.persona === 'parent') return <ParentHome user={user} />
      return <Finance caps={caps} user={user} onOpenApprovals={() => go('approvals')} />
    case 'library':
      if (user.persona === 'student') return <StudentLibraryView />
      return <Library caps={caps} />
    case 'hr':
      return <HR caps={caps} />
    case 'faculty_staff':
      return <FacultyStaff />
    case 'leave':
      return <HR caps={caps} />
    case 'recruitment':
      return <HR caps={caps} />
    case 'procurement':
      return <Procurement caps={caps} />
    case 'assets':
      return <Assets caps={caps} />
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
    case 'admin':
      return <AdminPanel caps={caps} />
    case 'approvals':
      return user.office_n === 1
        ? <ChairmanApprovals user={user} onChange={onChange} />
        : <Workflows user={user} onChange={onChange} />
    case 'workflows':
      return user.office_n === 6 ? <MyRequests go={go} /> : <Workflows user={user} onChange={onChange} />
    case 'delegation':
      return user.office_n === 1 ? <ChairmanDelegation user={user} /> : <Delegations user={user} />
    case 'audit':
      return <AuditView />
    case 'directory':
      return <Directory />
    case 'matrices':
      return <Matrices />
    case 'permissions':
      return <Permissions user={user} />
    case 'office_profile':
      return <OfficeProfile user={user} />
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

function NavGlyph({ moduleKey, label }: { moduleKey: string, label?: string }) {
  const admissionIcons: Record<string, any> = {
    'Overview': HiOutlineSquares2X2,
    'Admission Cycles': HiOutlineCalendarDays,
    'Programs & Intake': HiOutlineAcademicCap,
    'Quotas': HiOutlineUsers,
    'All Applications': HiOutlineClipboardDocumentList,
    'Corrections': HiOutlineDocumentCheck,
    'Document Verification': HiOutlineDocumentCheck,
    'Document Status': HiOutlineClipboardDocumentList,
    'Eligibility Queue': HiOutlineScale,
    'Eligibility Rules': HiOutlineScale,
    'Merit & Rankings': HiOutlineChartBarSquare,
    'Assessments & Merit': HiOutlineChartBarSquare,
    'Counselling': HiOutlineUserGroup,
    'Seat Pools': HiOutlineQueueList,
    'Seat Allocation': HiOutlineQueueList,
    'Allocation': HiOutlineQueueList,
    'Waitlist': HiOutlineUsers,
    'Offer Recommendations': HiOutlineGift,
    'Approval Inbox': HiOutlineCheckBadge,
    'Issued Offers': HiOutlineGift,
    'Offer Status': HiOutlineGift,
    'Finance Status': HiOutlineBanknotes,
    'Invoices & Challans': HiOutlineDocumentCurrencyRupee,
    'Payment Status': HiOutlineCreditCard,
    'Accounts Verification': HiOutlineDocumentCheck,
    'Finance Clearance': HiOutlineCheckBadge,
    'Clearance Status': HiOutlineCheckBadge,
    'Final Approval': HiOutlineCheckBadge,
    'Ready to Admit': HiOutlineUserPlus,
    'Enrollment Queue': HiOutlineQueueList,
    'Student Conversion': HiOutlineUserPlus,
    'Enrollment Status': HiOutlineAcademicCap,
    'Scholarship Admissions': HiOutlineGift,
    'International Admissions': HiOutlineUsers,
    'Application Status': HiOutlineClipboardDocumentList,
    'Helpdesk / Support': HiOutlineLifebuoy,
    'Reports': HiOutlineChartBarSquare,
    'Calendar': HiOutlineCalendarDays,
  }
  const AdmissionIcon = label ? admissionIcons[label] : null
  if (AdmissionIcon) return <AdmissionIcon />
  switch (moduleKey) {
    case 'frontdesk_dashboard':
    case 'frontdesk_visitors':
    case 'frontdesk_verify':
    case 'frontdesk_appointments':
    case 'frontdesk_helpdesk':
    case 'frontdesk_calls':
    case 'frontdesk_directory':
    case 'frontdesk_delegations':
      return <HiOutlineUserGroup />
    case 'overview':
      return <HiOutlineHome />
    case 'calendar':
      return <HiOutlineCalendarDays />
    case 'academic_calendar':
      return <HiOutlineCalendarDays />
    case 'governance':
      return <HiOutlineShieldCheck />
    case 'approvals':
      return <HiOutlineCheckBadge />
    case 'delegation':
      return <HiOutlineUsers />
    case 'audit':
      return <HiOutlineShieldCheck />
    case 'directory':
      return <HiOutlineUserGroup />
    case 'finance':
      return <HiOutlineBanknotes />
    case 'analytics':
      return <HiOutlineChartBarSquare />
    case 'hr':
      return <HiOutlineUsers />
    case 'integrations':
      return <HiOutlineSquares2X2 />
    case 'workflows':
      return <HiOutlineDocumentText />
    case 'matrices':
      return <HiOutlineClipboardDocumentList />
    case 'students':
      return <HiOutlineAcademicCap />
    case 'academics':
    case 'curriculum':
    case 'courses_subjects':
      return <HiOutlineBookOpen />
    case 'attendance':
      return <HiOutlineClipboardDocumentList />
    case 'examinations':
      return <HiOutlineDocumentCheck />
    case 'scores':
      return <HiOutlineChartBarSquare />
    case 'admissions':
      return <HiOutlineUserPlus />
    case 'library':
      return <HiOutlineFolder />
    case 'hostel':
      return <HiOutlineAcademicCap />
    case 'transport':
      return <HiOutlineClock />
    case 'decision_inbox':
      return <HiOutlineCheckBadge />
    case 'dean_programs':
      return <HiOutlineAcademicCap />
    case 'dean_timetable':
      return <HiOutlineCalendarDays />
    case 'dean_allocation':
      return <HiOutlineUsers />
    case 'dean_risk':
      return <HiOutlineExclamationTriangle />
    case 'dean_reports':
      return <HiOutlineChartBarSquare />
    case 'grievance':
      return <HiOutlineExclamationTriangle />
    case 'research':
      return <HiOutlineBookOpen />
    case 'placements':
      return <HiOutlineUserGroup />
    case 'procurement':
      return <HiOutlineDocumentCurrencyRupee />
    case 'assets':
      return <HiOutlineFolder />
    case 'admin':
      return <HiOutlineShieldCheck />
    default:
      return <HiOutlineSquares2X2 />
  }
}
