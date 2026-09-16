import { useEffect, useMemo, useState } from 'react'
import { HiOutlineAcademicCap, HiOutlineArchiveBox, HiOutlineArrowPathRoundedSquare, HiOutlineBanknotes, HiOutlineBookOpen, HiOutlineBriefcase, HiOutlineBuildingLibrary, HiOutlineBuildingOffice2, HiOutlineCalculator, HiOutlineCalendarDays, HiOutlineChartBarSquare, HiOutlineChatBubbleLeftRight, HiOutlineCheckBadge, HiOutlineClipboardDocumentCheck, HiOutlineClipboardDocumentList, HiOutlineCog6Tooth, HiOutlineComputerDesktop, HiOutlineCreditCard, HiOutlineDocumentChartBar, HiOutlineDocumentCheck, HiOutlineDocumentMagnifyingGlass, HiOutlineDocumentText, HiOutlineEnvelope, HiOutlineExclamationTriangle, HiOutlineFolder, HiOutlineGift, HiOutlineHome, HiOutlineIdentification, HiOutlineInbox, HiOutlineLifebuoy, HiOutlineMegaphone, HiOutlinePencilSquare, HiOutlinePresentationChartLine, HiOutlineQueueList, HiOutlineRectangleGroup, HiOutlineRocketLaunch, HiOutlineScale, HiOutlineShieldCheck, HiOutlineShoppingCart, HiOutlineSquares2X2, HiOutlineTableCells, HiOutlineTicket, HiOutlineTruck, HiOutlineUserCircle, HiOutlineUserGroup, HiOutlineUserPlus, HiOutlineUsers, HiOutlineWrenchScrewdriver } from 'react-icons/hi2'
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
import AcademicCoordinatorCenter from './modules/AcademicCoordinatorCenter'
import AcademicCoordinatorConflicts from './modules/AcademicCoordinatorConflicts'
import AcademicCoordinatorOfferings from './modules/AcademicCoordinatorOfferings'
import AcademicCoordinatorTimetable from './modules/AcademicCoordinatorTimetable'
import HodTimetableReview from './modules/HodTimetableReview'
import VicePrincipalAcademicApprovals from './modules/VicePrincipalAcademicApprovals'
import TimetableChanges from './modules/TimetableChanges'
import Curriculum from './modules/Curriculum'
import AcademicCoordinatorNotices from './modules/AcademicCoordinatorNotices'
import AcademicCoordinatorCurriculumExecution from './modules/AcademicCoordinatorCurriculumExecution'
import AcademicCoordinatorReports from './modules/AcademicCoordinatorReports'
import CoursesSubjects from './modules/CoursesSubjects'
import Attendance from './modules/Attendance'
import Examinations from './modules/Examinations'
import Admissions from './modules/Admissions'
import Finance, { PrincipalFinance } from './modules/Finance'
import Library from './modules/Library'
import HR from './modules/HR'
import PrincipalRecruitment from './modules/PrincipalRecruitment'
import FacultyStaff from './modules/FacultyStaff'
import Assets from './modules/Assets'
import Hostel from './modules/Hostel'
import Transport, { PrincipalTransport } from './modules/Transport'
import Research from './modules/Research'
import Placements from './modules/Placements'
import Grievance, { PrincipalGrievance } from './modules/Grievance'
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
import Facilities from './modules/Facilities'
import Integrations from './modules/Integrations'
import StudentHome from './personas/StudentHome'
import StudentRegistration from './personas/StudentRegistration'
import { AcademicNotices, StudentAttendanceView, StudentCalendarView, StudentCoursesView, StudentCurriculumExecution, StudentExaminationsView, StudentFeesView, StudentLibraryView, StudentScoresView } from './personas/StudentViews'
import FacultyCourseOfferings from './personas/FacultyCourseOfferings'
import FacultyHome from './personas/FacultyHome'
import AssociateProfessorHome from './personas/AssociateProfessorHome'
import FacultySchedule from './personas/FacultySchedule'
import FacultyProfile from './personas/FacultyProfile'
import FacultyExaminations from './personas/FacultyExaminations'
import { FacultyAssignments, StudentAssignments } from './personas/AssignmentViews'
import FacultyCommunication from './personas/FacultyCommunication'
import FacultyCourses from './personas/FacultyCourses'
import FacultyDigitalId from './personas/FacultyDigitalId'
import FacultyLeave from './personas/FacultyLeave'
import FacultyPayroll from './personas/FacultyPayroll'
import FacultyAssessments from './personas/FacultyAssessments'
import FacultyAttendance from './personas/FacultyAttendance'
import FacultyAttendanceCorrections from './personas/FacultyAttendanceCorrections'
import FacultyMarks from './personas/FacultyMarks'
import FacultyMentoring from './personas/FacultyMentoring'
import FacultyStudents from './personas/FacultyStudents'
import { FacultyMaterials } from './personas/CourseMaterials'
import FacultyConditionalView from './personas/FacultyConditionalViews'
import ParentHome from './personas/ParentHome'
import FrontDeskWorkspace from './frontdesk/FrontDeskWorkspace'
import ApplicantPortal from './admissions/ApplicantPortal'
import DeanAdministration from './modules/DeanAdministration'
import SpecialistQueue from './modules/SpecialistQueue'
import { PageHead } from './modules/kit'
import AccountantReport from './modules/AccountantReport'
import PrincipalDashboard from './modules/PrincipalDashboard'
import ViceChairmanCampusReports from './modules/ViceChairmanCampusReports'
import { CampusHeadApprovals, CampusHeadDashboard, CampusHeadEscalations, CampusHeadOperationalPlan, CampusHeadReports, CampusProfile, DepartmentsPrograms, LeadershipTeam, CampusOverview, InfrastructureOverview, CampusRiskWorkspace } from './modules/CampusHeadPortal'
import PrincipalAtRisk from './modules/PrincipalAtRisk'
import PrincipalCompliance from './modules/PrincipalCompliance'
import PrincipalExaminations from './modules/PrincipalExaminations'
import PrincipalExaminationOversight from './modules/PrincipalExaminationOversight'
import { ApprovalHistory, Escalations, PrincipalApprovals, PrincipalWorkflows } from './views/PrincipalWorkflowViews'

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
  ['Academic Governance', 'Programs', 'dean_programs'], ['Academic Governance', 'Curriculum', 'curriculum'], ['Academic Governance', 'Courses', 'courses_subjects'], ['Academic Governance', 'Academic Committees', 'dean_committees'],
  ['Academic Operations', 'Academic Calendar', 'academic_calendar'], ['Academic Operations', 'Faculty Allocation', 'dean_allocation'], ['Academic Operations', 'Timetable Readiness', 'dean_timetable'],
  ['Academic Operations', 'Academic Rollover', 'rollover'],
  ['Academic Operations', 'Timetable Changes', 'timetable_changes'],
  ['Quality & Monitoring', 'Performance & Results', 'analytics'], ['Quality & Monitoring', 'Academic Risk', 'dean_risk'], ['Quality & Monitoring', 'Corrective Actions', 'dean_corrective'], ['Quality & Monitoring', 'Outcomes', 'dean_outcomes'], ['Quality & Monitoring', 'Next-Semester Planning', 'dean_planning'],
  ['Authority', 'My Approvals', 'decision_inbox'], ['Authority', 'My Requests', 'workflows'],
  ['Reports', 'Reports & Analytics', 'dean_reports'], ['Reports', 'Audit', 'audit'],
  ['Reference', 'Directory', 'directory'],
] as const

// These routes are used by dashboard cards and notifications. They deliberately
// do not appear in the sidebar: each opens the relevant contextual workspace.
const DEAN_ACADEMICS_CONTEXT_ROUTES: Record<string, { label: string; key: string; actions: Record<string, never> }> = {
  dean_timetable: { label: 'Academic Operations', key: 'dean_academic_operations', actions: {} },
  dean_allocation: { label: 'Academic Operations', key: 'dean_academic_operations', actions: {} },
  dean_risk: { label: 'Academic Quality', key: 'dean_academic_quality', actions: {} },
  dean_committees: { label: 'Academic Governance', key: 'dean_committees', actions: {} },
  dean_corrective: { label: 'Quality & Monitoring', key: 'dean_corrective', actions: {} },
  dean_outcomes: { label: 'Quality & Monitoring', key: 'dean_outcomes', actions: {} },
  dean_planning: { label: 'Quality & Monitoring', key: 'dean_planning', actions: {} },
}
const DEAN_ADMINISTRATION_NAV = [
  ['Overview', 'Overview', 'administration_dashboard'],
  // Every item has its own view identity. Reusing a key here makes every
  // matching button active, and makes unrelated workspaces indistinguishable.
  ['School Administration', 'Administrative Plan', 'administration_plans'], ['School Administration', 'Resources & Facilities', 'administration_resources'], ['School Administration', 'Workforce', 'administration_workforce'], ['School Administration', 'Budget', 'administration_budget'], ['School Administration', 'Procurement & Assets', 'administration_procurement_assets'],
  ['Authority', 'My Reviews', 'administration_reviews'], ['Authority', 'My Requests', 'administration_requests'],
  ['Reports', 'Reports & Analytics', 'administration_reports'], ['Reports', 'Audit', 'audit'], ['Reference', 'Directory', 'directory'],
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
  ['Academic / People', 'Principal', 'overview'], ['Academic / People', 'At-Risk Students', 'at_risk_students'], ['Academic / People', 'Faculty & Staff', 'faculty_staff'], ['Academic / People', 'Leave', 'leave'], ['Academic / People', 'Recruitment & Vacancies', 'recruitment'],
  ['Academic / People', 'Academic Setup', 'academic_catalog'], ['Academic / People', 'Academic Calendar', 'academic_calendar'], ['Academic / People', 'Examinations', 'principal_examinations'],
  ['Finance & Operations', 'Finance', 'finance'], ['Finance & Operations', 'Procurement', 'procurement'], ['Finance & Operations', 'Facilities & Maintenance', 'facilities'],
  ['Finance & Operations', 'Assets & Inventory', 'assets'], ['Finance & Operations', 'Hostel', 'hostel'], ['Finance & Operations', 'Transport', 'transport'],
  ['Approvals & Workflow', 'My Approvals', 'approvals'], ['Approvals & Workflow', 'Approval History', 'approval_history'], ['Approvals & Workflow', 'Workflows', 'workflows'], ['Approvals & Workflow', 'Escalations', 'escalations'], ['Approvals & Workflow', 'Delegation', 'delegation'],
  ['Governance & Risk', 'Grievance & Discipline', 'grievance'], ['Governance & Risk', 'Accreditation & Compliance', 'compliance'],
  ['Audit & Reporting', 'Audit', 'audit'], ['Audit & Reporting', 'Reports', 'analytics'],
  ['Reference', 'Directory', 'directory'], ['Reference', 'Authority & Permissions', 'permissions'],
] as const

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
  ['AUTHORITY', 'My Approvals', 'campus_head_approvals'],
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
  ['Workspace', 'Overview', 'overview'], ['Workspace', 'My Schedule', 'my_schedule'], ['Workspace', 'Messages', 'messages'], ['Workspace', 'Academic Calendar', 'academic_calendar'],
  ['Teaching & Academics', 'My Sections', 'academics'], ['Teaching & Academics', 'Course Offerings', 'faculty_course_offerings'], ['Teaching & Academics', 'Attendance', 'attendance'], ['Teaching & Academics', 'Assignments', 'assignments'],
  ['Teaching & Academics', 'Assessments & Marks', 'assessments'], ['Teaching & Academics', 'Marks', 'marks_entry'], ['Teaching & Academics', 'Examinations', 'examinations'],
  ['Teaching & Academics', 'Course Materials', 'course_materials'], ['Teaching & Academics', 'Mentoring & Advisees', 'mentoring'], ['Teaching & Academics', 'Research & Guidance', 'research'],
  ['Communication', 'Announcements', 'announcements'],
  ['Self Service', 'My Profile', 'my_profile'], ['Self Service', 'Digital ID', 'digital_id'], ['Self Service', 'Leave & Requests', 'leave'], ['Self Service', 'Payroll', 'payroll'],
  ['Workflow', 'Attendance Correction Reviews', 'attendance_corrections'], ['Workflow', 'My Requests', 'workflows'],
] as const

const COORDINATOR_NAV = [
  ['Workspace', 'Overview', 'overview'],
  ['Academic planning', 'Academic Calendar', 'academic_calendar'], ['Academic planning', 'Curriculum Execution', 'curriculum'],
  ['End-of-term operations', 'Student Progression & Rollover', 'rollover'],
  ['scheduling', 'Course Offerings', 'coordinator_course_offerings'], ['scheduling', 'Sections & Timetable', 'coordinator_sections'], ['scheduling', 'Faculty Allocation', 'source_allocation'], ['scheduling', 'Conflict Center', 'coordinator_conflicts'],
  ['scheduling', 'Timetable Changes', 'timetable_changes'],
  ['coordination', 'Academic Notices', 'coordinator_notices'],
  ['authority', 'Approvals', 'coordinator_approvals'], ['authority', 'Requests', 'coordinator_requests'],
  ['reports', 'Reports', 'coordinator_reports'], ['reports', 'Audit', 'audit'],
  ['reference', 'Directory', 'directory'],
] as const

const DIRECTOR_ADMISSIONS_NAV = [
  ['Overview', 'Overview', 'overview'],
  ['1. Setup', 'Admission Cycles & Intake', 'director_cycles'],
  ['1. Setup', 'Eligibility Evaluation', 'director_eligibility'],
  ['2. Applicant Journey', 'Applications', 'director_applications'],
  ['3. Review & Verification', 'Review Queue', 'director_review'], ['3. Review & Verification', 'Corrections', 'director_corrections'], ['3. Review & Verification', 'Document Status', 'director_documents'],
  ['4. Eligibility & Quota', 'Eligibility Rules', 'director_rules'], ['4. Eligibility & Quota', 'Quotas', 'director_quotas'],
  ['5. Merit & Allocation', 'Assessment, Merit & Seats', 'director_merit'], ['5. Merit & Allocation', 'Seat Pools', 'director_seat_pools'], ['5. Merit & Allocation', 'Counselling & Waitlist', 'director_counselling'],
  ['6. Offers & Finance', 'Offer Approval & Status', 'director_offers'], ['6. Offers & Finance', 'Finance Clearance', 'director_finance'],
  ['7. Enrollment & Student Account', 'Re-submitted Corrections', 'director_resubmitted_corrections'],
  ['8. Monitoring', 'Admission Reports', 'director_reports'],
] as const

const DIRECTOR_TAB: Record<string, string> = {
  director_cycles: 'cycles', director_programs: 'program_intake', director_quotas: 'quotas',
  director_applications: 'applications', director_review: 'review', director_corrections: 'corrections', director_document_verification: 'review', director_documents: 'document_status',
  director_eligibility: 'eligibility', director_rules: 'rules', director_assessments: 'decisions', director_merit: 'decisions', director_counselling: 'counselling', director_seat_pools: 'seatpools', director_allocation: 'decisions', director_waitlist: 'waitlist', director_recommendations: 'offers', director_offers: 'offers',
  director_ready: 'ready_to_admit', director_enrollment_queue: 'enrollment_queue', director_conversion: 'student_conversion', director_enrollment: 'enrollment_status', director_finance: 'finance_status', director_invoices: 'invoices_challans', director_payment_status: 'payment_status', director_accounts: 'accounts_verification', director_clearance: 'clearance_status',
  director_final_approval: 'resubmitted_corrections', director_resubmitted_corrections: 'resubmitted_corrections',
  director_offer_status: 'offers', director_scholarship: 'eligibility', director_international: 'applications', director_reports: 'reports',
}

const ADMISSION_MANAGER_NAV = [
  ['Overview', 'Overview', 'overview'],
  ['1. Setup', 'Admission Cycles & Intake', 'manager_cycles'],
  ['1. Setup', 'Eligibility Evaluation', 'manager_eligibility'],
  ['2. Applicant Journey', 'Applications', 'manager_applications'],
  ['3. Review & Verification', 'Review Queue', 'manager_review'], ['3. Review & Verification', 'Corrections', 'manager_corrections'], ['3. Review & Verification', 'Document Status', 'manager_documents'],
  ['4. Eligibility & Quota', 'Eligibility Rules', 'manager_rules'], ['4. Eligibility & Quota', 'Quotas', 'manager_quotas'],
  ['5. Merit & Allocation', 'Assessment, Merit & Seats', 'manager_assessments'], ['5. Merit & Allocation', 'Seat Pools', 'manager_seat_pools'], ['5. Merit & Allocation', 'Counselling & Waitlist', 'manager_counselling'],
  ['6. Offers & Finance', 'Offer Approval & Status', 'manager_offers'], ['6. Offers & Finance', 'Finance Clearance', 'manager_finance'],
  ['8. Monitoring', 'Admission Reports', 'manager_reports'],
] as const

const ADMISSION_MANAGER_TAB: Record<string, string> = {
  manager_cycles: 'cycles', manager_programs: 'program_intake', manager_quotas: 'quotas',
  manager_applications: 'applications', manager_review: 'review', manager_corrections: 'corrections', manager_documents: 'document_status',
  manager_eligibility: 'eligibility', manager_rules: 'rules', manager_assessments: 'decisions', manager_counselling: 'counselling',
  manager_seat_pools: 'seatpools', manager_allocation: 'decisions', manager_waitlist: 'waitlist',
  manager_recommendations: 'offers', manager_offers: 'offers',
  manager_finance: 'finance_status', manager_invoices: 'invoices_challans', manager_clearance: 'clearance_status',
  manager_enrollment: 'enrollment_status', manager_reports: 'reports',
}

export default function App({ onLogout }: { onLogout: () => void }) {
  const [user, setUser] = useState<any>(getUser())
  const [ws, setWs] = useState<any>(null)
  const [identityReady, setIdentityReady] = useState(false)
  const [view, setView] = useState(() => {
    const currentUser = getUser()
    if (currentUser?.office_n === 31) return 'transport'
    if (currentUser?.office_n === 23) return 'overview'
    return 'overview'
  })
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
    api.me().then(r => {
      const nextUser = r.user
      setUser(nextUser)
      if (nextUser?.office_n === 31) setView('transport')
      else if (nextUser?.office_n === 23) setView('finance')
      else setView('overview')

      if ([10, 17].includes(nextUser?.office_n) && window.location.hash && window.location.hash !== '#overview') {
        window.location.hash = 'overview'
      }
    }).catch(() => {}).finally(() => setIdentityReady(true))
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
    // HR module. It has its own route so that the list/profile experience is
    // retained when opened from the dashboard KPI or the Principal sidebar.
    const virtualModule =
      (user?.office_n === 4 && ['faculty_staff', 'curriculum', 'courses_subjects'].includes(view))
      // The Dean shell has role-specific destinations that intentionally reuse
      // the governed academic workspace.  They are valid routes even though
      // they are not returned as generic workspace modules by the API.
      || (user?.office_n === 6 && ['courses_subjects', 'decision_inbox', 'dean_programs', 'dean_academic_operations', 'dean_academic_quality', 'dean_timetable', 'dean_allocation', 'dean_risk', 'dean_committees', 'dean_corrective', 'dean_outcomes', 'dean_planning', 'dean_reports', 'analytics'].includes(view))
      || ([10, 17].includes(user?.office_n) && view === 'source_allocation')
      || (user?.office_n === 10 && view === 'rollover')
      || (user?.office_n === 10 && view === 'hod_course_offerings')
      || (user?.office_n === 10 && view === 'hod_timetable_review')
      || (user?.office_n === 5 && view === 'vp_academic_approvals')
      || ([10, 17, 41].includes(user?.office_n) && view === 'program_proposals')
      || ([5, 6, 10, 17].includes(user?.office_n) && view === 'timetable_changes')
      || (user?.office_n === 7 && view.startsWith('administration_'))
      || (user?.office_n === 4 && PRINCIPAL_NAV.some(([, , key]) => key === view))
      || (user?.office_n === 3 && CAMPUS_HEAD_NAV.some(([, , key]) => key === view))
      || (user?.persona === 'faculty' && FACULTY_NAV.some(([, , key]) => key === view))
      || (user?.persona && !['student', 'parent', 'faculty'].includes(user.persona) && view === 'my_payroll')
      || (user?.office_n === 23 && ['finance_fees', 'finance_payments', 'finance_students', 'finance_payroll'].includes(view))
      || (user?.persona === 'student' && ['assignments', 'course_materials'].includes(view))
      || view.startsWith('director_') || view.startsWith('manager_') || view.startsWith('coordinator_')
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
      setView(next.user?.office_n === 31 ? 'transport' : next.user?.office_n === 23 ? 'finance' : 'overview')
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
      .filter((module: any) => !([31, 35].includes(user?.office_n) && module.key === 'my_payroll'))
      // Finance Manager works only with fee operations and fee-approval tasks.
      // Governance matrices and generic administration screens are not part of this portal.
      .filter((module: any) => user?.office_n !== 22 || ['overview', 'finance', 'rollover', 'approvals', 'audit'].includes(module.key))
      .filter((module: any) => module && module.key)
      .map((module: any) => {
        if (user?.office_n === 10 && module.key === 'workflows') {
          return { ...module, label: 'Requests', actions: module.actions || {}, ...displayMeta(user, module) }
        }
        return { ...module, actions: module.actions || {}, ...displayMeta(user, module) }
      })
      if (user?.persona === 'student' && !modules.some((module: any) => module.key === 'finance')) {
        modules.push({ key: 'finance', label: 'Fees & Payments', group: 'Student Services', enabled: true })
      }
      if (user?.persona === 'student' && !modules.some((module: any) => module.key === 'course_registrations')) {
        modules.push({ key: 'course_registrations', label: 'Course Registration', group: 'Academics', enabled: true })
      }
      if ([5, 6, 10, 17].includes(Number(user?.office_n)) && !modules.some((module: any) => module.key === 'timetable_changes')) {
        modules.push({ key: 'timetable_changes', label: user?.office_n === 17 ? 'Timetable Changes' : 'Timetable Changes Requiring Review', group: 'Academics', enabled: true })
      }
      // These are governed source workspaces, not Dean-only workspaces.  The
      // API already authorizes their respective source roles; keep the entry
      // points visible so an authorized proposer can actually create, submit,
      // and resubmit work through the production UI.
      if ([10, 17, 41].includes(Number(user?.office_n)) && !modules.some((module: any) => module.key === 'program_proposals')) {
        modules.push({ key: 'program_proposals', label: 'Programme Proposals', group: 'Academics', enabled: true })
      }
      if ([10, 17].includes(Number(user?.office_n)) && !modules.some((module: any) => module.key === 'source_allocation')) {
        modules.push({ key: 'source_allocation', label: 'Faculty Allocation', group: 'Academics', enabled: true })
      }
      // HODs own departmental requirements, while offering creation remains
      // exclusively with the Academic Coordinator.
      if (Number(user?.office_n) === 10 && !modules.some((module: any) => module.key === 'hod_course_offerings')) {
        modules.push({ key: 'hod_course_offerings', label: 'Course Offerings', group: 'Academics', enabled: true })
      }
      if (Number(user?.office_n) === 10 && !modules.some((module: any) => module.key === 'hod_timetable_review')) {
        modules.push({ key: 'hod_timetable_review', label: 'Sections & Timetable', group: 'Academics', enabled: true })
      }
      // Progression is a departmental HOD review duty.  The API has always
      // enforced the scope; provide the matching production entry point.
      if (Number(user?.office_n) === 10 && !modules.some((module: any) => module.key === 'rollover')) {
        modules.push({ key: 'rollover', label: 'Student Progression & Rollover', group: 'End-of-term operations', enabled: true })
      }
      if (Number(user?.office_n) === 5 && !modules.some((module: any) => module.key === 'vp_academic_approvals')) {
        modules.push({ key: 'vp_academic_approvals', label: 'Academic Approvals', group: 'Authority', enabled: true })
      }
      if (![31, 35].includes(user?.office_n) && user?.persona && !['student', 'parent', 'faculty'].includes(user.persona) && !modules.some((module: any) => module.key === 'my_payroll')) {
        modules.push({ key: 'my_payroll', label: 'My Payroll', group: 'Self Service', enabled: true })
      }
      return modules
    },
    [rawModules, user],
  )

  // Never render role-specific screens from cached browser state.  This is
  // particularly important after role switching: a stale Principal shell
  // would otherwise call Principal-only endpoints using a different token.
  if (!identityReady || !user || !ws) {
    return <div className="center-load"><div className="spinner" /></div>
  }

  if (user.persona === 'applicant') {
    return <ApplicantPortal authenticated onBack={doLogout} />
  }

  const color = LEVEL_COLORS[user.level] || '#c9a24a'
  const chairmanShell = user.office_n === 1
  const campusHeadShell = user.office_n === 3
  const principalShell = user.office_n === 4
  const deanAcademicsShell = user.office_n === 6
  const deanAdministrationShell = user.office_n === 7
  const transportOfficeShell = user.office_n === 31
  const facultyShell = user.persona === 'faculty'
  const directorAdmissionsShell = user.office_n === 15 && user.active_role === 'Director of Admissions'
  // The seeded office role is named “Admissions Manager”; accept the singular
  // wording from requirements too so both authorised role labels share this shell.
  const admissionManagerShell = ['Admission Manager', 'Admissions Manager'].includes(user.active_role)
  const admissionsOperationsShell = directorAdmissionsShell || admissionManagerShell
  const admissionOfficeSingleRole = user.office_n === 15
  const coordinatorShell = user.office_n === 17
  const campusHeadModules = CAMPUS_HEAD_NAV.map(([group, label, key]) => {
    const source = displayModules.find((module: any) => module.key === key)
    return { key, label, group, actions: source?.actions || {}, enabled: true }
  })
  const sidebarModules = campusHeadShell
    ? campusHeadModules
    : transportOfficeShell
    ? displayModules.filter((module: any) => !['Academics', 'Reference', 'Authority', 'Workspace'].includes(module.group))
    : displayModules
  const groups: Record<string, any[]> = {}
  sidebarModules.forEach((module: any) => {
    ;(groups[module.group] = groups[module.group] || []).push(module)
  })
  const order = chairmanShell ? CHAIRMAN_GROUP_ORDER : GROUP_ORDER
  const groupKeys = [...order.filter(key => groups[key]), ...Object.keys(groups).filter(key => !order.includes(key))]
  const coordinatorGroups = COORDINATOR_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    ;(out[group] = out[group] || []).push({ group, label, key, enabled: true })
    return out
  }, {})
  const coordinatorGroupKeys = [...new Set(COORDINATOR_NAV.map(([group]) => group))]
  const principalGroups = PRINCIPAL_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const source = displayModules.find((module: any) => module.key === key)
      || (user.office_n === 4 && key === 'faculty_staff' ? { key, label, group, enabled: true } : undefined)
    ;(out[group] = out[group] || []).push({ key, label, group, source, enabled: true })
    return out
  }, {})
  const deanGroups = DEAN_ACADEMICS_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const source = displayModules.find((module: any) => module.key === key) || { key, actions: {} }
    ;(out[group] = out[group] || []).push({ key, label, group, source, enabled: true })
    return out
  }, {})
  const deanGroupKeys = [...new Set(DEAN_ACADEMICS_NAV.map(([group]) => group))]
  const deanAdministrationGroups = DEAN_ADMINISTRATION_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const source = displayModules.find((module: any) => module.key === key) || { key, actions: {} }
    ;(out[group] = out[group] || []).push({ key, label, group, source, enabled: true })
    return out
  }, {})
  const deanAdministrationGroupKeys = [...new Set(DEAN_ADMINISTRATION_NAV.map(([group]) => group))]
  const facultyGroups = FACULTY_NAV.reduce((out: Record<string, any[]>, [group, label, key]) => {
    const source = displayModules.find((module: any) => module.key === key)
    // Professor workspace pages have their own role-specific screens.  They
    // remain available even when no generic module card is returned.
    ;(out[group] = out[group] || []).push({ key, label, group, source, enabled: true })
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
  const current = (
    deanAcademicsShell
      ? Object.values(deanGroups).flat().find((module: any) => module.key === view) || DEAN_ACADEMICS_CONTEXT_ROUTES[view]
      : deanAdministrationShell
        ? Object.values(deanAdministrationGroups).flat().find((module: any) => module.key === view)
        : coordinatorShell
          ? Object.values(coordinatorGroups).flat().find((module: any) => module.key === view)
          : facultyShell
            ? Object.values(facultyGroups).flat().find((module: any) => module.key === view)
            : admissionsOperationsShell
              ? Object.values(activeAdmissionsGroups).flat().find((module: any) => module.key === view)
              : undefined
  ) || sidebarModules.find((module: any) => module.key === view) || sidebarModules[0]
  const campusHeader = user.scope_level === 'campus' ? user.scope_ref : ''
  const isDeanNavActive = (moduleKey: string) =>
    view === moduleKey
    || (moduleKey === 'dean_academic_operations' && ['dean_timetable', 'dean_allocation'].includes(view))
    || (moduleKey === 'dean_academic_quality' && view === 'dean_risk')

  return (
    <div className={`app ${chairmanShell ? 'chairman-shell' : ''} ${principalShell ? 'principal-shell' : ''} ${campusHeadShell ? 'campus-head-shell' : ''} ${facultyShell ? 'faculty-shell' : ''} ${deanAcademicsShell ? 'dean-academics-shell' : ''} ${deanAdministrationShell ? 'dean-administration-shell' : ''} ${directorAdmissionsShell ? 'director-admissions-shell' : ''} ${admissionManagerShell ? 'admission-manager-shell' : ''}`}>
      <aside className={`sidebar ${sideOpen ? 'open' : ''}`}>
        <div className="brand">
          {campusHeadShell ? <div className="campus-head-brand">CAMPUS HEAD PORTAL</div> : <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="seal">IC</div>
            <div>
              <div className="brand-name">ICMS</div>
              <div className="brand-sub">{principalShell ? 'Principal Portal' : directorAdmissionsShell ? 'Admissions Directorate' : admissionManagerShell ? 'Admissions Operations' : facultyShell ? 'University Group' : 'University Group'}</div>
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
          {(coordinatorShell ? coordinatorGroupKeys : deanAcademicsShell ? deanGroupKeys : deanAdministrationShell ? deanAdministrationGroupKeys : principalShell ? Object.keys(principalGroups) : facultyShell ? Object.keys(facultyGroups) : admissionsOperationsShell ? activeAdmissionsGroupKeys : groupKeys).map(group => (
            <div key={group}>
              {deanAcademicsShell || deanAdministrationShell || admissionsOperationsShell ? <button className="side-sec director-nav-group" onClick={() => (deanAcademicsShell || deanAdministrationShell) ? setCollapsedDeanGroups(current => ({ ...current, [group]: !current[group] })) : setCollapsedDirectorGroups(current => ({ ...current, [group]: !current[group] }))} type="button">{group}<span>{((deanAcademicsShell || deanAdministrationShell) ? collapsedDeanGroups[group] : collapsedDirectorGroups[group]) ? '+' : '−'}</span></button> : <div className="side-sec">{group}</div>}
              {((!deanAcademicsShell && !deanAdministrationShell && !admissionsOperationsShell) || ((deanAcademicsShell || deanAdministrationShell) ? !collapsedDeanGroups[group] : !collapsedDirectorGroups[group])) && ((coordinatorShell ? coordinatorGroups[group] : deanAcademicsShell ? deanGroups[group] : deanAdministrationShell ? deanAdministrationGroups[group] : principalShell ? principalGroups[group] : facultyShell ? facultyGroups[group] : admissionsOperationsShell ? activeAdmissionsGroups[group] : groups[group]) || []).map((module: any) => (
                <button
                  key={(deanAcademicsShell || deanAdministrationShell || coordinatorShell || principalShell || facultyShell || admissionsOperationsShell) ? `${group}-${module.label}` : module.key}
                  className={`nav-item ${(coordinatorShell ? view === module.key : deanAcademicsShell ? isDeanNavActive(module.key) : view === module.key) && (!(deanAcademicsShell || deanAdministrationShell || coordinatorShell || principalShell || facultyShell || admissionsOperationsShell) || module.enabled) ? 'on' : ''} ${((principalShell || facultyShell || admissionsOperationsShell) && !module.enabled) ? 'nav-item-disabled' : ''}`}
                  onClick={() => {
                    setView(module.key)
                    setSideOpen(false)
                  }}
                  title={module.label}
                  type="button"
                >
                  <span className="ico">
                    <NavGlyph moduleKey={module.backingKey || module.key} label={module.label} />
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
            <div className="crumb">
              {user.office}
              {campusHeader && <b> / {campusHeader}</b>}
              <b> / {current?.label}</b>
            </div>
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
    case 'program_proposals':
      return <DeanPrograms />
    case 'overview':
      if (user.office_n === 3) return <CampusHeadDashboard user={user} go={go} />
      if (user.office_n === 4) return <PrincipalDashboard user={user} go={go} />
      if (user.office_n === 6) return <DeanAcademicsDashboard go={go} />
      if (user.office_n === 7) return <DeanAdministration mode="dashboard" />
      if (user.office_n === 17) return <AcademicCoordinatorCenter onNavigate={go} />
      if (user.office_n === 15 && user.active_role === 'Director of Admissions') return <DirectorAdmissionsDashboard user={user} go={go} />
      if (user.persona === 'student') return <StudentHome user={user} go={go} />
      if (user.office_n === 12) return <AssociateProfessorHome go={go} />
      if (user.persona === 'faculty') return <FacultyHome user={user} go={go} />
      if (user.persona === 'parent') return <ParentHome user={user} />
      return <Overview user={user} go={go} />
    case 'calendar':
      if (user.persona === 'student') return <StudentCalendarView user={user} go={go} />
      return <Calendar user={user} caps={caps} />
    case 'campus_profile':
      return user.office_n === 3 ? <CampusProfile /> : <div className="empty">Campus Profile is not available for this role.</div>
    case 'branch_operational_plan':
      return user.office_n === 3 ? <CampusHeadOperationalPlan user={user} onChange={onChange} /> : <div className="empty">Branch Operational Plan is not available for this role.</div>
    case 'departments_programs':
      return user.office_n === 3 ? <DepartmentsPrograms /> : <div className="empty">Departments &amp; Programs is not available for this role.</div>
    case 'leadership_team':
      return user.office_n === 3 ? <LeadershipTeam /> : <div className="empty">Leadership Team is not available for this role.</div>
    case 'campus_overview':
      return user.office_n === 3 ? <CampusOverview /> : <div className="empty">Campus Overview is not available for this role.</div>
    case 'infrastructure':
      return user.office_n === 3 ? <InfrastructureOverview /> : <div className="empty">Infrastructure is not available for this role.</div>
    case 'risk_issues':
      return user.office_n === 3 ? <CampusRiskWorkspace /> : <div className="empty">Risk &amp; Issues is not available for this role.</div>
    case 'my_schedule':
      if (user.persona === 'faculty') return <FacultySchedule user={user} go={go} />
      return <MySchedule user={user} go={go} />
    case 'messages':
      return <FacultyCommunication mode="messages" />
    case 'announcements':
      return <AcademicNotices />
    case 'academic_calendar':
      return <AcademicCalendar user={user} caps={caps} />
    case 'rollover':
      return <AcademicRollover />
    case 'integrations':
      return <Integrations caps={caps} />
    case 'analytics':
      if (user.office_n === 3) return <CampusHeadReports />
      if (user.office_n === 2) return <ViceChairmanCampusReports />
      return <Analytics user={user} go={go} />
    case 'students':
      if (user.persona === 'student') return <StudentHome user={user} go={go} />
      if (user.persona === 'faculty') return <FacultyStudents />
      return <Students caps={caps} />
    case 'principal_at_risk':
    case 'at_risk_students':
      return user.office_n === 4 ? <PrincipalAtRisk /> : <div className="empty">This Principal workspace is not available for this role.</div>
    case 'academic_catalog':
      return <CoursesSubjects />
    case 'facilities':
      return <Facilities />
    case 'mentoring':
      return user.persona === 'faculty' ? <FacultyMentoring /> : <Students caps={caps} />
    case 'academics':
      if ([6, 17].includes(user.office_n)) return <DeanAcademicWorkspaces />
      if (user.persona === 'faculty') return <FacultyCourses go={go} />
      if (user.persona === 'student') return <StudentCoursesView />
      return <Academics caps={caps} go={go} />
    case 'source_allocation':
      return <DeanAcademicWorkspaces initialTab="allocation" sourceMode={user.office_n === 17} />
    case 'dean_academic_operations':
      return <DeanAcademicWorkspaces initialTab="readiness" />
    case 'dean_academic_quality':
      return <DeanAcademicWorkspaces initialTab="risk" />
    case 'dean_timetable':
      return <DeanAcademicWorkspaces initialTab="readiness" />
    case 'dean_allocation':
      return <DeanAcademicWorkspaces initialTab="allocation" />
    case 'dean_risk':
      return <DeanAcademicWorkspaces initialTab="risk" />
    case 'dean_committees':
      return <DeanAcademicWorkspaces initialTab="committee" />
    case 'dean_corrective':
      return <DeanAcademicWorkspaces initialTab="action" />
    case 'dean_outcomes':
      return <DeanAcademicWorkspaces initialTab="outcomes" />
    case 'dean_planning':
      return <DeanAcademicWorkspaces initialTab="planning" />
    case 'dean_reports':
      return <DeanAcademicWorkspaces initialTab="reports" />
    case 'curriculum':
      if (user.persona === 'student') return <StudentCurriculumExecution />
      return user.office_n === 17 ? <AcademicCoordinatorCurriculumExecution onNavigate={go} /> : <Curriculum />
    case 'faculty_course_offerings':
      return <FacultyCourseOfferings />
    case 'courses_subjects':
      return <CoursesSubjects />
    case 'coordinator_course_offerings':
      return <AcademicCoordinatorOfferings />
    case 'hod_course_offerings':
      return user.office_n === 10
        ? <Academics caps={caps} go={go} initialTab="offerings" offeringWorkspace />
        : <div className="empty">This HOD workspace is not available for this role.</div>
    case 'hod_timetable_review':
      return user.office_n === 10
        ? <HodTimetableReview />
        : <div className="empty">This HOD timetable workspace is not available for this role.</div>
    case 'vp_academic_approvals':
      return user.office_n === 5
        ? <VicePrincipalAcademicApprovals />
        : <div className="empty">This Vice Principal workspace is not available for this role.</div>
    case 'coordinator_sections':
      return <AcademicCoordinatorTimetable />
    case 'timetable_changes':
      return <TimetableChanges />
    case 'coordinator_conflicts':
      return <AcademicCoordinatorConflicts onNavigate={go} />
    case 'coordinator_notices':
      return [6, 17].includes(Number(user.office_n)) ? <AcademicCoordinatorNotices /> : <Academics caps={caps} />
    case 'coordinator_approvals':
      return <DecisionInbox />
    case 'coordinator_requests':
      return <MyRequests go={go} />
    case 'coordinator_reports':
      return [6, 17].includes(user.office_n) ? <AcademicCoordinatorReports onNavigate={go} /> : <Analytics user={user} />
    case 'attendance':
      if (user.persona === 'faculty') return <FacultyAttendance />
      if (user.persona === 'student') return <StudentAttendanceView />
      return <Attendance caps={caps} />
    case 'attendance_corrections':
      return user.persona === 'faculty' ? <FacultyAttendanceCorrections /> : <div className="empty">Attendance correction reviews are not available for this role.</div>
    case 'examinations':
      if (user.persona === 'student') return <StudentExaminationsView go={go} />
      if (user.persona === 'faculty') return <FacultyExaminations />
      return <Examinations caps={caps} />
    case 'principal_examinations':
      return user.office_n === 4 ? <PrincipalExaminationOversight /> : <div className="empty">This Principal workspace is not available for this role.</div>
    case 'principal_compliance':
      return user.office_n === 4 ? <PrincipalCompliance go={go} /> : <div className="empty">This Principal workspace is not available for this role.</div>
    case 'assessments':
      return user.persona === 'faculty' ? <FacultyAssessments go={go} /> : <Examinations caps={caps} />
    case 'assignments':
      if (user.persona === 'faculty') return <FacultyAssignments />
      if (user.persona === 'student') return <StudentAssignments />
      return <div className="empty">Assignments are not available for this role.</div>
    case 'marks_entry':
      return user.persona === 'faculty' ? <FacultyMarks /> : <Examinations caps={caps} />
    case 'course_materials':
      return user.persona === 'faculty' ? <FacultyMaterials /> : <div className="empty">Course materials are not available for this role.</div>
    case 'scores':
      if (user.persona === 'student') return <StudentScoresView />
      return <Examinations caps={caps} />
    case 'admissions':
      return <Admissions caps={caps} />
    case 'finance_fees':
      return <Finance caps={caps} user={user} onOpenApprovals={() => go('approvals')} initialTab="fees" />
    case 'finance_payments':
      return <Finance caps={caps} user={user} onOpenApprovals={() => go('approvals')} initialTab="payments" />
    case 'finance_students':
      return <Finance caps={caps} user={user} onOpenApprovals={() => go('approvals')} initialTab="students" />
    case 'finance_payroll':
      return <Finance caps={caps} user={user} onOpenApprovals={() => go('approvals')} initialTab="payroll" />
    case 'finance':
      if (user.persona === 'student') return <StudentFeesView />
      if (user.persona === 'parent') return <ParentHome user={user} />
      if (user.office_n === 3) return <Finance caps={caps} user={user} onOpenApprovals={() => go('approvals')} readOnly />
      if (user.office_n === 4) return <PrincipalFinance onOpenApprovals={() => go('approvals')} />
      return <Finance caps={caps} user={user} onOpenApprovals={() => go('approvals')} />
    case 'accountant_report':
      return user.office_n === 23 ? <AccountantReport /> : <Analytics user={user} go={go} />
    case 'library':
      if (user.persona === 'student') return <StudentLibraryView />
      return <Library caps={caps} />
    case 'hr':
      if (user.office_n === 24) return <SpecialistQueue title="HR Staffing Requests" />
      if (user.persona === 'faculty') return <FacultyPayroll />
      return <HR caps={caps} user={user} />
    case 'payroll':
      return user.persona === 'faculty' ? <FacultyPayroll /> : <HR caps={caps} user={user} />
    case 'my_payroll':
      return <FacultyPayroll />
    case 'faculty_staff':
      return <FacultyStaff />
    case 'leave':
      return user.persona === 'faculty' ? <FacultyLeave /> : <HR caps={caps} user={user} initialTab="leave" />
    case 'digital_id':
      return user.persona === 'faculty' ? <FacultyDigitalId /> : <div className="empty">Digital ID is not available for this role.</div>
    case 'coordination':
      return <FacultyConditionalView kind="coordination" />
    case 'academic_risk':
      return <FacultyConditionalView kind="risk" />
    case 'course_registrations':
      if (user.persona === 'student') return <StudentRegistration />
      return <FacultyConditionalView kind="registrations" />
    case 'recruitment':
      return user.office_n === 4 ? <PrincipalRecruitment /> : <HR caps={caps} user={user} initialTab="jobs" />
    case 'procurement':
      if (user.office_n === 32) return <SpecialistQueue title="Procurement Requisitions" />
      return <Procurement caps={caps} />
    case 'administration_dashboard':
      return <DeanAdministration mode="dashboard" />
    case 'administration_plans':
      return <DeanAdministration mode="plans" />
    case 'administration_requirements':
      return <DeanAdministration mode="requirements" />
    case 'administration_resources':
      return <DeanAdministration mode="requirements" workspaceTitle="Resources & Facilities" categoryFilter="FACILITIES" />
    case 'administration_workforce':
      return <DeanAdministration mode="requirements" workspaceTitle="Workforce" categoryFilter="WORKFORCE" />
    case 'administration_budget':
      return <DeanAdministration mode="requirements" workspaceTitle="Budget" categoryFilter="BUDGET" />
    case 'administration_procurement_assets':
      return <DeanAdministration mode="requirements" workspaceTitle="Procurement & Assets" categoryFilter="PROCUREMENT,ASSETS" />
    case 'administration_requests':
      return <DeanAdministration mode="requests" />
    case 'administration_reviews':
      return <DeanAdministration mode="reviews" />
    case 'administration_reports':
      return <DeanAdministration mode="reports" />
    case 'assets':
      if (user.office_n === 29) return <SpecialistQueue title="Facilities Work Orders" />
      if (user.office_n === 27) return <SpecialistQueue title="IT Service Requests" />
      return <Assets caps={caps} />
    case 'hostel':
      return <Hostel caps={caps} />
    case 'transport':
      if (user.office_n === 4) return <PrincipalTransport caps={caps} />
      return <Transport caps={caps} />
    case 'research':
      return <Research caps={caps} />
    case 'placements':
      return <Placements caps={caps} />
    case 'grievance':
      return user.office_n === 4 ? <PrincipalGrievance caps={caps} /> : <Grievance caps={caps} />
    case 'governance':
      return <Governance user={user} />
    case 'admin':
      return <AdminPanel caps={caps} />
    case 'approvals':
      return user.office_n === 1
        ? <ChairmanApprovals user={user} onChange={onChange} />
        : user.office_n === 4
          ? <PrincipalApprovals user={user} onChange={onChange} />
        : <Workflows user={user} onChange={onChange} />
    case 'campus_head_approvals':
      return user.office_n === 3
        ? <CampusHeadApprovals user={user} onChange={onChange} />
        : <div className="empty">Campus Head approvals are not available for this role.</div>
    case 'workflows':
      return user.office_n === 4 ? <PrincipalWorkflows user={user} onChange={onChange} /> : user.office_n === 6 ? <MyRequests go={go} /> : <Workflows user={user} onChange={onChange} />
    case 'my_requests':
      return user.office_n === 3 ? <Workflows user={user} onChange={onChange} initialTab="mine" /> : <div className="empty">My Requests is not available for this role.</div>
    case 'principal_approval_history':
    case 'approval_history':
      return user.office_n === 4 ? <ApprovalHistory /> : <div className="empty">This Principal workspace is not available for this role.</div>
    case 'escalations':
      return user.office_n === 4 ? <Escalations /> : user.office_n === 3 ? <CampusHeadEscalations /> : <div className="empty">Escalations are not available for this role.</div>
    case 'compliance':
      return user.office_n === 4 ? <PrincipalCompliance go={go} /> : <div className="empty">This Principal workspace is not available for this role.</div>
    case 'principal_escalations':
      return user.office_n === 4 ? <Escalations /> : <div className="empty">This Principal workspace is not available for this role.</div>
    case 'delegation':
      return user.office_n === 1 ? <ChairmanDelegation user={user} /> : <Delegations user={user} />
    case 'audit':
      return <AuditView principal={user.office_n === 4} />
    case 'directory':
      return <Directory user={user} />
    case 'policy_repository':
      return user.office_n === 3 ? <Matrices /> : <div className="empty">Policy Repository is not available for this role.</div>
    case 'my_profile':
      return user.persona === 'faculty' ? <FacultyProfile /> : <div className="empty">My Profile is not available for this role.</div>
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

function CoordinatorPage({ title, sub, action }: { title: string; sub: string; action: string }) {
  return (
    <main className="page-wrap fade-in">
      <PageHead title={title} sub={sub} />
      <section className="card" style={{ marginTop: 20 }}>
        <div className="card-h"><div><h2>{title}</h2><p>This coordinator workspace has its own route, active state, and workflow.</p></div><button className="btn btn-crimson" type="button" onClick={() => window.location.reload()}>{action}</button></div>
        <div className="empty" style={{ padding: '48px 20px' }}>No {title.toLowerCase()} items are waiting for action.</div>
      </section>
    </main>
  )
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
  // Labels are deliberately the first lookup. Several role-specific routes share
  // a backing module (for example Admissions), but still need a distinct visual
  // affordance for each destination in the sidebar.
  const labelIcons: Record<string, any> = {
    'Overview': HiOutlineSquares2X2,
    'Principal': HiOutlineHome,
    'Dashboard': HiOutlineSquares2X2,
    // Campus / Branch Head portal. Keep these explicit instead of relying on
    // backing module keys: several of these screens deliberately reuse a
    // generic module but must remain visually distinguishable in the sidebar.
    'Campus Profile': HiOutlineBuildingOffice2,
    'Branch Operational Plan': HiOutlineClipboardDocumentList,
    'Departments & Programs': HiOutlineAcademicCap,
    'Leadership Team': HiOutlineUserGroup,
    'Campus Calendar': HiOutlineCalendarDays,
    'Campus Overview': HiOutlinePresentationChartLine,
    'Infrastructure': HiOutlineWrenchScrewdriver,
    'Placements': HiOutlineBriefcase,
    'Risk & Issues': HiOutlineExclamationTriangle,
    'Audit Trail': HiOutlineShieldCheck,
    'Policy Repository': HiOutlineFolder,
    'My Schedule': HiOutlineCalendarDays,
    'Messages': HiOutlineEnvelope,
    'Announcements': HiOutlineMegaphone,
    'My Sections': HiOutlineTableCells,
    'Course Offerings': HiOutlineBookOpen,
    'Attendance': HiOutlineClipboardDocumentCheck,
    'Assignments': HiOutlineClipboardDocumentList,
    'Assessments': HiOutlineCalculator,
    'Assessments & Marks': HiOutlineCalculator,
    'Marks': HiOutlinePencilSquare,
    'Marks Entry': HiOutlinePencilSquare,
    'Course Materials': HiOutlineFolder,
    'Mentoring & Advisees': HiOutlineUserCircle,
    'Research & Guidance': HiOutlineRocketLaunch,
    'My Profile': HiOutlineUserCircle,
    'Digital ID': HiOutlineIdentification,
    'Leave & Requests': HiOutlineCalendarDays,
    'Leave': HiOutlineCalendarDays,
    'Leave Requests': HiOutlineCalendarDays,
    'Payroll': HiOutlineBanknotes,
    'My Payroll': HiOutlineBanknotes,
    'Attendance Correction Reviews': HiOutlineClipboardDocumentCheck,
    'My Requests': HiOutlineInbox,
    'Requests': HiOutlineInbox,
    'Approvals': HiOutlineCheckBadge,
    'My Approvals': HiOutlineCheckBadge,
    'Academic Approvals': HiOutlineCheckBadge,
    'Approval History': HiOutlineDocumentText,
    'Workflows': HiOutlineArrowPathRoundedSquare,
    'Escalations': HiOutlineLifebuoy,
    'Delegation': HiOutlineUsers,
    'Academic Calendar': HiOutlineCalendarDays,
    'Academic Rollover': HiOutlineArrowPathRoundedSquare,
    'Curriculum': HiOutlineRectangleGroup,
    'Curriculum Execution': HiOutlineRectangleGroup,
    'Programs': HiOutlineAcademicCap,
    'Programme Proposals': HiOutlineAcademicCap,
    'Courses': HiOutlineBookOpen,
    'Academic Setup': HiOutlineAcademicCap,
    'Academic Committees': HiOutlineUserGroup,
    'Faculty Allocation': HiOutlineUsers,
    'Sections & Timetable': HiOutlineTableCells,
    'Timetable Readiness': HiOutlineTableCells,
    'Timetable Changes': HiOutlineCalendarDays,
    'Timetable Changes Requiring Review': HiOutlineCalendarDays,
    'Conflict Center': HiOutlineExclamationTriangle,
    'Academic Notices': HiOutlineMegaphone,
    'Academic Operations': HiOutlineTableCells,
    'Performance & Results': HiOutlinePresentationChartLine,
    'Academic Risk': HiOutlineExclamationTriangle,
    'Corrective Actions': HiOutlineClipboardDocumentCheck,
    'Outcomes': HiOutlineChartBarSquare,
    'Next-Semester Planning': HiOutlineRocketLaunch,
    'Reports': HiOutlineDocumentChartBar,
    'Reports & Analytics': HiOutlineDocumentChartBar,
    'Audit': HiOutlineShieldCheck,
    'Directory': HiOutlineUserGroup,
    'Authority & Permissions': HiOutlineShieldCheck,
    'Settings': HiOutlineCog6Tooth,
    'Academic Governance': HiOutlineBuildingLibrary,
    'Academic Quality': HiOutlinePresentationChartLine,
    'Administrative Plan': HiOutlineClipboardDocumentList,
    'Resources & Facilities': HiOutlineWrenchScrewdriver,
    'Workforce': HiOutlineUsers,
    'Budget': HiOutlineBanknotes,
    'Procurement & Assets': HiOutlineShoppingCart,
    'My Reviews': HiOutlineDocumentMagnifyingGlass,
    'Administration Requests': HiOutlineInbox,
    'At-Risk Students': HiOutlineExclamationTriangle,
    'Faculty & Staff': HiOutlineBuildingOffice2,
    'Recruitment & Vacancies': HiOutlineBriefcase,
    'Examinations': HiOutlineDocumentCheck,
    'Finance': HiOutlineBanknotes,
    'Finance & Resources': HiOutlineBanknotes,
    'Procurement': HiOutlineShoppingCart,
    'Facilities & Maintenance': HiOutlineWrenchScrewdriver,
    'Assets & Inventory': HiOutlineArchiveBox,
    'Hostel': HiOutlineBuildingOffice2,
    'Transport': HiOutlineTruck,
    'Grievance & Discipline': HiOutlineScale,
    'Accreditation & Compliance': HiOutlineShieldCheck,
    'Governance': HiOutlineBuildingLibrary,
    'Institution': HiOutlineBuildingOffice2,
    'Strategic Initiatives': HiOutlineRocketLaunch,
    'Communications': HiOutlineChatBubbleLeftRight,
    'Admission Cycles': HiOutlineCalendarDays,
    'Admission Cycles & Intake': HiOutlineCalendarDays,
    'Applications': HiOutlineClipboardDocumentList,
    'Review Queue': HiOutlineDocumentCheck,
    'Corrections': HiOutlinePencilSquare,
    'Document Status': HiOutlineDocumentMagnifyingGlass,
    'Eligibility Evaluation': HiOutlineScale,
    'Eligibility Rules': HiOutlineClipboardDocumentCheck,
    'Quotas': HiOutlineUserGroup,
    'Assessment, Merit & Seats': HiOutlineChartBarSquare,
    'Seat Pools': HiOutlineQueueList,
    'Counselling & Waitlist': HiOutlineChatBubbleLeftRight,
    'Offer Approval & Status': HiOutlineGift,
    'Finance Clearance': HiOutlineCreditCard,
    'Re-submitted Corrections': HiOutlineClipboardDocumentCheck,
    'Admission Reports': HiOutlineChartBarSquare,
    'Calendar': HiOutlineCalendarDays,
  }
  const keyIcons: Record<string, any> = {
    frontdesk_dashboard: HiOutlineSquares2X2, frontdesk_visitors: HiOutlineUserGroup,
    frontdesk_verify: HiOutlineTicket, frontdesk_appointments: HiOutlineCalendarDays,
    frontdesk_helpdesk: HiOutlineLifebuoy, frontdesk_calls: HiOutlineChatBubbleLeftRight,
    frontdesk_directory: HiOutlineUserGroup, frontdesk_delegations: HiOutlineUsers,
    overview: HiOutlineHome, calendar: HiOutlineCalendarDays, academic_calendar: HiOutlineCalendarDays,
    campus_profile: HiOutlineBuildingOffice2, branch_operational_plan: HiOutlineClipboardDocumentList,
    departments_programs: HiOutlineAcademicCap, leadership_team: HiOutlineUserGroup,
    campus_overview: HiOutlinePresentationChartLine, infrastructure: HiOutlineWrenchScrewdriver,
    risk_issues: HiOutlineExclamationTriangle, campus_head_approvals: HiOutlineCheckBadge,
    my_requests: HiOutlineInbox, policy_repository: HiOutlineFolder,
    governance: HiOutlineBuildingLibrary, approvals: HiOutlineCheckBadge, delegation: HiOutlineUsers,
    audit: HiOutlineShieldCheck, directory: HiOutlineUserGroup, finance: HiOutlineBanknotes,
    analytics: HiOutlinePresentationChartLine, hr: HiOutlineUsers, integrations: HiOutlineCog6Tooth,
    workflows: HiOutlineArrowPathRoundedSquare, matrices: HiOutlineTableCells, students: HiOutlineAcademicCap,
    academics: HiOutlineBookOpen, curriculum: HiOutlineRectangleGroup, courses_subjects: HiOutlineBookOpen,
    attendance: HiOutlineClipboardDocumentCheck, examinations: HiOutlineDocumentCheck, scores: HiOutlineChartBarSquare,
    admissions: HiOutlineUserPlus, library: HiOutlineBuildingLibrary, hostel: HiOutlineBuildingOffice2,
    transport: HiOutlineTruck, decision_inbox: HiOutlineInbox, dean_programs: HiOutlineAcademicCap,
    dean_timetable: HiOutlineTableCells, dean_allocation: HiOutlineUsers, dean_risk: HiOutlineExclamationTriangle,
    dean_reports: HiOutlineDocumentChartBar, grievance: HiOutlineScale, research: HiOutlineRocketLaunch,
    placements: HiOutlineBriefcase, procurement: HiOutlineShoppingCart, assets: HiOutlineComputerDesktop,
    admin: HiOutlineCog6Tooth, facilities: HiOutlineWrenchScrewdriver, compliance: HiOutlineShieldCheck,
    permissions: HiOutlineShieldCheck, faculty_staff: HiOutlineBuildingOffice2, recruitment: HiOutlineBriefcase,
    leave: HiOutlineCalendarDays, academic_catalog: HiOutlineAcademicCap, principal_examinations: HiOutlineDocumentCheck,
    approval_history: HiOutlineDocumentText, escalations: HiOutlineLifebuoy, course_registrations: HiOutlineClipboardDocumentList,
    my_schedule: HiOutlineCalendarDays, messages: HiOutlineEnvelope, announcements: HiOutlineMegaphone,
    assignments: HiOutlineClipboardDocumentList, assessments: HiOutlineCalculator, marks_entry: HiOutlinePencilSquare,
    course_materials: HiOutlineFolder, mentoring: HiOutlineUserCircle, my_profile: HiOutlineUserCircle,
    digital_id: HiOutlineIdentification, payroll: HiOutlineBanknotes, my_payroll: HiOutlineBanknotes,
    rollover: HiOutlineArrowPathRoundedSquare, timetable_changes: HiOutlineCalendarDays,
    program_proposals: HiOutlineAcademicCap, source_allocation: HiOutlineUsers,
  }
  const Icon = (label && labelIcons[label]) || keyIcons[moduleKey] || HiOutlineSquares2X2
  return <Icon />
}
