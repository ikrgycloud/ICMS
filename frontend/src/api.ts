const BASE = import.meta.env.VITE_API_URL || '/api'

function tok() { return localStorage.getItem('icms_token') || '' }

const GATEWAY_STATUSES = new Set([502, 503, 504])

const wait = (milliseconds: number) => new Promise(resolve => setTimeout(resolve, milliseconds))

async function req(path: string, opts: RequestInit = {}, retryAttempt = 0): Promise<any> {
  const headers: any = { 'Content-Type': 'application/json', ...(opts.headers || {}) }
  const t = tok()
  if (t) headers['Authorization'] = `Bearer ${t}`
  const res = await fetch(`${BASE}${path}`, { ...opts, headers })
  if (res.status === 401) {
    localStorage.removeItem('icms_token')
    localStorage.removeItem('icms_user')
    if (!path.includes('/auth/login')) window.location.reload()
  }
  const txt = await res.text()
  let data: any = {}
  if (txt) {
    try { data = JSON.parse(txt) }
    catch { data = {} }
  }
  if (!res.ok) {
    // A proxy can return HTML while the API is starting. Retry safe reads, but
    // never replay a mutation whose outcome may be unknown.
    if (GATEWAY_STATUSES.has(res.status) && (!opts.method || opts.method === 'GET') && retryAttempt < 2) {
      await wait(1000 * (retryAttempt + 1))
      return req(path, opts, retryAttempt + 1)
    }
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item: any) => item.msg || item.message || JSON.stringify(item)).join(', ')
      : data.detail
    const fallback = GATEWAY_STATUSES.has(res.status)
      ? 'Server is starting or temporarily unavailable. Please retry in a moment.'
      : `Request failed (${res.status})`
    throw new Error(detail || fallback)
  }
  return data
}

export const api = {
  login: (username: string, password: string) =>
    req('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  completeOnboarding: (token: string, password: string) =>
    req('/auth/onboarding/complete', { method: 'POST', body: JSON.stringify({ token, password }) }),
  onboardingContext: (token: string) => req(`/auth/onboarding/context?token=${encodeURIComponent(token)}`),
  me: () => req('/me'),
  stats: () => req('/stats'),
  catalog: () => req('/catalog'),
  setBranchLifecycle: (id: string, status: 'discontinued' | 'deactivated') =>
    req(`/branches/${encodeURIComponent(id)}/lifecycle`, { method: 'POST', body: JSON.stringify({ status }) }),
  branchUsers: (filters: Record<string, string> = {}) => req(`/branches/users?${new URLSearchParams(filters).toString()}`),
  resendBranchOnboarding: (id: string) => req(`/branches/users/${encodeURIComponent(id)}/resend-onboarding`, { method: 'POST' }),
  createBranchAccountPassword: (id: string) => req(`/branches/users/${encodeURIComponent(id)}/create-password`, { method: 'POST' }),
  activateBranchUser: (id: string) => req(`/branches/users/${encodeURIComponent(id)}/activate`, { method: 'POST' }),
  copyDevelopmentBranchPassword: (id: string) => req(`/branches/users/${encodeURIComponent(id)}/copy-development-password`, { method: 'POST' }),
  copyLegacyBranchPassword: (id: string) => req(`/branches/users/${encodeURIComponent(id)}/copy-legacy-password`, { method: 'POST' }),
  setBranchUserStatus: (id: string, active: boolean) => req(`/branches/users/${encodeURIComponent(id)}/status?active=${active}`, { method: 'POST' }),
  offices: () => req('/directory/offices').then((r: any) => r.offices || r),
  office: (n: number) => req(`/directory/office/${n}`),
  officeDetail: (n: number) => req(`/directory/office/${n}`),
  roles: () => req('/directory/roles'),
  dashboard: () => req('/dashboard'),
  myPermissions: () => req('/authz/my-permissions'),
  authzCheck: (action: string, resource = '*', amount?: number) =>
    req('/authz/check', { method: 'POST', body: JSON.stringify({ action, resource, amount }) }),
  check: (action: string, resource = '*', amount?: number) =>
    req('/authz/check', { method: 'POST', body: JSON.stringify({ action, resource, amount }) }),

  matrix: (kind: string) => req(`/matrices/${kind}`),
  rbacMatrix: () => req('/matrices/rbac'),
  approvalMatrix: () => req('/matrices/approval'),
  scopeMatrix: () => req('/matrices/scope'),

  processes: () => req('/workflows/processes'),
  startWorkflow: (process_key: string, title: string, amount?: number) =>
    req('/workflows/start', { method: 'POST', body: JSON.stringify({ process_key, title, amount }) }),
  decideWorkflow: (workflow_id: string, action: string, reason = '') =>
    req('/workflows/decide', { method: 'POST', body: JSON.stringify({ workflow_id, action, reason }) }),
  workflows: (scope = 'all') => req(`/workflows?scope=${scope}`),
  workflow: (id: string) => req(`/workflows/${id}`),
  risks: (filters: Record<string, string> = {}) => {
    const qs = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => { if (value) qs.set(key, value) })
    const suffix = qs.toString()
    return req(`/risks${suffix ? `?${suffix}` : ''}`)
  },
  risk: (id: string) => req(`/risks/${encodeURIComponent(id)}`),
  riskSummary: () => req('/risks/summary'),
  riskOwners: () => req('/risks/owners'),
  createRisk: (body: any) => req('/risks', { method: 'POST', body: JSON.stringify(body) }),
  updateRisk: (id: string, body: any) => req(`/risks/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(body) }),
  assignRisk: (id: string, owner_id: string) => req(`/risks/${encodeURIComponent(id)}/assign`, { method: 'POST', body: JSON.stringify({ owner_id }) }),
  resolveRisk: (id: string, reason = '', resolution_notes = '') => req(`/risks/${encodeURIComponent(id)}/resolve`, { method: 'POST', body: JSON.stringify({ reason, resolution_notes }) }),
  closeRisk: (id: string, reason = '') => req(`/risks/${encodeURIComponent(id)}/close`, { method: 'POST', body: JSON.stringify({ reason }) }),
  escalateRisk: (id: string, reason = '') => req(`/risks/${encodeURIComponent(id)}/escalate`, { method: 'POST', body: JSON.stringify({ reason }) }),
  riskActions: (id: string) => req(`/risks/${encodeURIComponent(id)}/actions`),
  createRiskAction: (id: string, body: any) => req(`/risks/${encodeURIComponent(id)}/actions`, { method: 'POST', body: JSON.stringify(body) }),
  updateRiskAction: (id: string, body: any) => req(`/risk-actions/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(body) }),
  completeRiskAction: (id: string, completion_notes = '') => req(`/risk-actions/${encodeURIComponent(id)}/complete`, { method: 'POST', body: JSON.stringify({ completion_notes }) }),
  verifyRiskAction: (id: string) => req(`/risk-actions/${encodeURIComponent(id)}/verify`, { method: 'POST' }),
  bop: () => req('/bop'),
  campusLeadership: () => req('/campus-leadership'),
  createBop: (body: any) => req('/bop', { method: 'POST', body: JSON.stringify(body) }),
  updateBop: (id: string, body: any) => req(`/bop/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(body) }),
  submitBop: (id: string) => req(`/bop/${encodeURIComponent(id)}/submit`, { method: 'POST' }),
  resubmitBop: (id: string) => req(`/bop/${encodeURIComponent(id)}/resubmit`, { method: 'POST' }),
  approvalHistory: (filters: Record<string, string> = {}) => req(`/approval-history?${new URLSearchParams(filters).toString()}`),
  escalations: (filters: Record<string, string> = {}) => req(`/escalations?${new URLSearchParams(filters).toString()}`),
  escalation: (id: string) => req(`/escalations/${encodeURIComponent(id)}`),
  createEscalation: (body: any) => req('/escalations', { method: 'POST', body: JSON.stringify(body) }),
  submitEscalation: (id: string, reason = '') => req(`/escalations/${encodeURIComponent(id)}/submit`, { method: 'POST', body: JSON.stringify({ reason }) }),
  followUpEscalation: (id: string, reason = '') => req(`/escalations/${encodeURIComponent(id)}/follow-up`, { method: 'POST', body: JSON.stringify({ reason }) }),
  receiveEscalation: (id: string, reason = '') => req(`/escalations/${encodeURIComponent(id)}/receive`, { method: 'POST', body: JSON.stringify({ reason }) }),
  resolveEscalation: (id: string, reason = '') => req(`/escalations/${encodeURIComponent(id)}/resolve`, { method: 'POST', body: JSON.stringify({ reason }) }),
  closeEscalation: (id: string, reason = '') => req(`/escalations/${encodeURIComponent(id)}/close`, { method: 'POST', body: JSON.stringify({ reason }) }),
  createCampusReport: (body: any) => req('/campus-reports', { method: 'POST', body: JSON.stringify(body) }),
  campusReports: () => req('/campus-reports'),
  campusReport: (id: string) => req(`/campus-reports/${encodeURIComponent(id)}`),
  updateCampusReport: (id: string, body: any) => req(`/campus-reports/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(body) }),
  submitCampusReport: (id: string) => req(`/campus-reports/${encodeURIComponent(id)}/submit`, { method: 'POST' }),
  resubmitCampusReport: (id: string) => req(`/campus-reports/${encodeURIComponent(id)}/resubmit`, { method: 'POST' }),
  vcCampusReports: () => req('/campus-reports/vc/inbox'),
  returnCampusReport: (id: string, feedback: string) => req(`/campus-reports/${encodeURIComponent(id)}/return`, { method: 'POST', body: JSON.stringify({ feedback }) }),
  approveCampusReport: (id: string) => req(`/campus-reports/${encodeURIComponent(id)}/approve`, { method: 'POST' }),
  chairmanApprovals: (params: Record<string, any> = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value == null || value === '') return
      qs.set(key, String(value))
    })
    const suffix = qs.toString()
    return req(`/approvals/chairman${suffix ? `?${suffix}` : ''}`)
  },
  chairmanInitiateRequest: (body: any) =>
    req('/approvals/chairman/initiate', { method: 'POST', body: JSON.stringify(body) }),
  chairmanDelegations: (params: Record<string, any> = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value == null || value === '') return
      qs.set(key, String(value))
    })
    const suffix = qs.toString()
    return req(`/delegations/chairman${suffix ? `?${suffix}` : ''}`)
  },
  chairmanCreateDelegation: (body: any) =>
    req('/delegations/chairman', { method: 'POST', body: JSON.stringify(body) }),
  branches: () => req('/branches'),
  provisionBranch: (body: any) => req('/branches/provision', { method: 'POST', body: JSON.stringify(body) }),

  delegations: () => req('/delegations'),
  createDelegation: (b: any) => req('/delegations', { method: 'POST', body: JSON.stringify(b) }),
  revokeDelegation: (id: string) => req(`/delegations/${id}/revoke`, { method: 'POST' }),

  notifications: () => req('/notifications'),
  readNotification: (id: string) => req(`/notifications/${id}/read`, { method: 'POST' }),

  audit: (limit = 60) => req(`/audit?limit=${limit}`),
  verifyAudit: () => req('/audit/verify'),

  // ---- role switching ----
  switchRole: (role: string) =>
    req('/auth/switch-role', { method: 'POST', body: JSON.stringify({ role }) }),

  // ---- workspace / capabilities ----
  workspace: () => req('/workspace'),
  overview: () => req('/overview'),
  principalOverview: (academic_year = '', student_semester = '') => {
    const params = new URLSearchParams({ academic_year })
    if (student_semester) params.set('student_semester', student_semester)
    return req(`/overview/principal?${params.toString()}`)
  },
  chairmanOverview: (start = '', end = '') => {
    const params = new URLSearchParams()
    if (start) params.set('start', start)
    if (end) params.set('end', end)
    const qs = params.toString()
    return req(`/overview/chairman${qs ? `?${qs}` : ''}`)
  },
  chairmanOutstandingFees: (start = '') => {
    const params = new URLSearchParams()
    if (start) params.set('start', start)
    const qs = params.toString()
    return req(`/overview/chairman/outstanding-fees${qs ? `?${qs}` : ''}`)
  },
  calendar: (start = '') => {
    const params = new URLSearchParams()
    if (start) params.set('start', start)
    const qs = params.toString()
    return req(`/calendar${qs ? `?${qs}` : ''}`)
  },
  createCalendarEvent: (body: any) => req('/calendar', { method: 'POST', body: JSON.stringify(body) }),
  updateCalendarEvent: (id: string, body: any) => req(`/calendar/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteCalendarEvent: (id: string) => req(`/calendar/${id}`, { method: 'DELETE' }),
  academicCalendar: (term = '') => {
    const params = new URLSearchParams()
    if (term) params.set('term', term)
    const qs = params.toString()
    return req(`/academic-calendar${qs ? `?${qs}` : ''}`)
  },
  createAcademicCalendarEntry: (body: any) =>
    req('/academic-calendar', { method: 'POST', body: JSON.stringify(body) }),
  updateAcademicCalendarEntry: (id: string, body: any) =>
    req(`/academic-calendar/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteAcademicCalendarEntry: (id: string) => req(`/academic-calendar/${id}`, { method: 'DELETE' }),

  // ---- students ----
  students: (q = '', dept = '', page = 1, pageSize = 25, filters: any = {}) => {
    const params = new URLSearchParams({ q, dept, page: String(page), page_size: String(pageSize) })
    if (filters.program) params.set('program', filters.program)
    if (filters.academicYear) params.set('academic_year', filters.academicYear)
    if (filters.studyYear) params.set('study_year', String(filters.studyYear))
    if (filters.semester) params.set('semester', String(filters.semester))
    if (filters.section) params.set('section', filters.section)
    if (filters.risk) params.set('risk', filters.risk)
    return req(`/students?${params.toString()}`)
  },
  studentProfile: (id: string) => req(`/students/${encodeURIComponent(id)}/profile`),
  facultyStaff: (q = '', dept = '', kind = '', page = 1, filters: any = {}) => req(`/faculty-staff?q=${encodeURIComponent(q)}&dept=${encodeURIComponent(dept)}&kind=${encodeURIComponent(kind)}&page=${page}&designation=${encodeURIComponent(filters.designation || '')}&status=${encodeURIComponent(filters.status || '')}`),
  facultyProfile: (id: string) => req(`/faculty-staff/${encodeURIComponent(id)}`),
  addStudent: (b: any) => req('/students', { method: 'POST', body: JSON.stringify(b) }),

  // ---- academics ----
  departments: () => req('/academics/departments'),
  createDepartment: (b: any) => req('/academics/departments', { method: 'POST', body: JSON.stringify(b) }),
  updateDepartment: (id: string, b: any) => req(`/academics/departments/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(b) }),
  deleteDepartment: (id: string) => req(`/academics/departments/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  programs: () => req('/academics/programs'),
  createProgram: (b: any) => req('/academics/programs', { method: 'POST', body: JSON.stringify(b) }),
  updateProgram: (id: string, b: any) => req(`/academics/programs/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(b) }),
  deleteProgram: (id: string) => req(`/academics/programs/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  courses: () => req('/academics/courses'),
  createCourse: (b: any) => req('/academics/courses', { method: 'POST', body: JSON.stringify(b) }),
  sections: () => req('/academics/sections'),
  createSection: (b: any) => req('/academics/sections', { method: 'POST', body: JSON.stringify(b) }),
  sectionTimetable: (sectionId: string) => req(`/academics/section/${sectionId}/timetable`),
  createTimetableEntry: (sectionId: string, b: any) =>
    req(`/academics/section/${sectionId}/timetable`, { method: 'POST', body: JSON.stringify(b) }),
  updateTimetableEntry: (entryId: string, b: any) =>
    req(`/academics/timetable/${entryId}`, { method: 'PUT', body: JSON.stringify(b) }),
  deactivateTimetableEntry: (entryId: string) => req(`/academics/timetable/${entryId}/deactivate`, { method: 'POST' }),
  sectionAssignments: (sectionId: string) => req(`/academics/section/${sectionId}/assignments`),
  createAssignment: (sectionId: string, b: any) =>
    req(`/academics/section/${sectionId}/assignments`, { method: 'POST', body: JSON.stringify(b) }),
  updateAssignment: (assignmentId: string, b: any) =>
    req(`/academics/assignments/${assignmentId}`, { method: 'PUT', body: JSON.stringify(b) }),
  publishAnnouncement: (b: any) => req('/academics/announcements', { method: 'POST', body: JSON.stringify(b) }),

  // ---- attendance ----
  attendanceSections: () => req('/attendance/sections'),
  attendanceRoster: (sid: string) => req(`/attendance/roster/${sid}`),
  markAttendance: (b: any) => req('/attendance/mark', { method: 'POST', body: JSON.stringify(b) }),

  // ---- exams ----
  examSections: () => req('/exams/sections'),
  examAssessments: (sid: string) => req(`/exams/assessments/${sid}`),
  examSectionOversight: (sid: string) => req(`/exams/sections/${encodeURIComponent(sid)}/oversight`),
  examTimetable: (sectionId: string) => req(`/exams/timetable/${sectionId}`),
  createAssessment: (b: any) => req('/exams/assessments', { method: 'POST', body: JSON.stringify(b) }),
  updateAssessment: (assessmentId: string, b: any) =>
    req(`/exams/assessments/${assessmentId}`, { method: 'PUT', body: JSON.stringify(b) }),
  createExamTimetable: (b: any) => req('/exams/timetable', { method: 'POST', body: JSON.stringify(b) }),
  updateExamTimetable: (scheduleId: string, b: any) =>
    req(`/exams/timetable/${scheduleId}`, { method: 'PUT', body: JSON.stringify(b) }),
  enterMarks: (b: any) => req('/exams/marks', { method: 'POST', body: JSON.stringify(b) }),
  submitMarks: (assessment_id: string) => req('/exams/marks/submit', { method: 'POST', body: JSON.stringify({ assessment_id }) }),
  publishMarks: (assessment_id: string) => req('/exams/marks/publish', { method: 'POST', body: JSON.stringify({ assessment_id }) }),
  publishResult: (section_id: string) => req('/exams/publish', { method: 'POST', body: JSON.stringify({ section_id }) }),

  // ---- admissions ----
  applications: () => req('/admissions'),
  decideApplication: (application_id: string, action: string) =>
    req('/admissions/decide', { method: 'POST', body: JSON.stringify({ application_id, action }) }),

  // ---- finance ----
  invoices: () => req('/finance/invoices'),
  budget: () => req('/finance/budget'),
  recordPayment: (invoice_id: string, amount: number) =>
    req('/finance/payment', { method: 'POST', body: JSON.stringify({ invoice_id, amount }) }),
  waiveFee: (b: any) => req('/finance/waive', { method: 'POST', body: JSON.stringify(b) }),

  // ---- library ----
  books: (q = '') => req(`/library/books?q=${encodeURIComponent(q)}`),
  loans: () => req('/library/loans'),
  issueBook: (b: any) => req('/library/issue', { method: 'POST', body: JSON.stringify(b) }),
  returnBook: (loan_id: string) => req(`/library/return/${loan_id}`, { method: 'POST' }),

  // ---- hr ----
  leave: () => req('/hr/leave'),
  jobs: () => req('/hr/jobs'),
  createJob: (b: any) => req('/hr/jobs', { method: 'POST', body: JSON.stringify(b) }),
  decideLeave: (leave_id: string, action: string) =>
    req('/hr/leave/decide', { method: 'POST', body: JSON.stringify({ leave_id, action }) }),

  // ---- ops ----
  assets: (filters: Record<string, string> = {}) => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value) })
    const qs = params.toString()
    return req(`/assets${qs ? `?${qs}` : ''}`)
  },
  procurement: () => req('/procurement'),
  hostel: () => req('/hostel'),
  availableHostelRooms: (id: string) => req(`/hostel/available-rooms/${id}`),
  allocateHostel: (id: string, room_id: string) => req(`/hostel/allocate/${id}`, { method: 'POST', body: JSON.stringify({ room_id }) }),
  transport: () => req('/transport'),
  research: () => req('/research'),
  placements: () => req('/placements'),

  // ---- grievance ----
  grievance: () => req('/grievance'),
  complaint: (id: string) => req(`/grievance/${encodeURIComponent(id)}`),
  raiseComplaint: (b: any) => req('/grievance', { method: 'POST', body: JSON.stringify(b) }),
  investigateComplaint: (complaint_id: string, notes: string) =>
    req(`/grievance/${encodeURIComponent(complaint_id)}/investigate`, { method: 'POST', body: JSON.stringify({ notes }) }),
  resolveComplaint: (complaint_id: string, notes: string) =>
    req(`/grievance/${encodeURIComponent(complaint_id)}/resolve`, { method: 'POST', body: JSON.stringify({ notes }) }),

  // ---- governance / admin ----
  governance: (semester = '') => {
    const params = new URLSearchParams()
    if (semester) params.set('semester', semester)
    const qs = params.toString()
    return req(`/governance${qs ? `?${qs}` : ''}`)
  },
  complianceRequirements: (filters: Record<string, string> = {}) => req(`/compliance-requirements?${new URLSearchParams(filters).toString()}`),
  complianceRequirement: (id: string) => req(`/compliance-requirements/${encodeURIComponent(id)}`),
  updateGovernance: (semester: string, body: any) =>
    req(`/governance/${encodeURIComponent(semester)}`, { method: 'PUT', body: JSON.stringify(body) }),
  adminUsers: () => req('/admin/users'),

  // ---- persona portals ----
  whoami: () => req('/portal/whoami'),
  studentHome: () => req('/portal/student/home'),
  studentCourses: () => req('/portal/student/courses'),
  updateStudentCourseView: (sectionId: string, body: any) =>
    req(`/portal/student/courses/${sectionId}/view`, { method: 'PUT', body: JSON.stringify(body) }),
  studentAttendance: () => req('/portal/student/attendance'),
  studentExaminations: (params: Record<string, any> = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value == null || value === '' || value === 'all') return
      qs.set(key, String(value))
    })
    if (!qs.has('status')) qs.set('status', String(params.status || 'all'))
    return req(`/portal/student/examinations?${qs.toString()}`)
  },
  studentScores: (params: Record<string, any> = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value == null || value === '') return
      qs.set(key, String(value))
    })
    const suffix = qs.toString()
    return req(`/portal/student/scores${suffix ? `?${suffix}` : ''}`)
  },
  studentResults: () => req('/portal/student/results'),
  studentFees: () => req('/portal/student/fees'),
  studentDigitalId: () => req('/portal/student/digital-id'),
  studentCalendar: (start = '') => {
    const params = new URLSearchParams()
    if (start) params.set('start', start)
    const qs = params.toString()
    return req(`/portal/student/calendar${qs ? `?${qs}` : ''}`)
  },
  createStudentCalendarPersonalEvent: (body: any) =>
    req('/portal/student/calendar/personal', { method: 'POST', body: JSON.stringify(body) }),
  updateStudentCalendarPersonalEvent: (id: string, body: any) =>
    req(`/portal/student/calendar/personal/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteStudentCalendarPersonalEvent: (id: string) =>
    req(`/portal/student/calendar/personal/${id}`, { method: 'DELETE' }),
  studentTodayClasses: () => req('/portal/student/today-classes'),
  studentTasks: () => req('/portal/student/tasks'),
  studentUpcomingAssessments: () => req('/portal/student/upcoming-assessments'),
  studentAnnouncements: () => req('/portal/student/announcements'),
  studentLibraryLoans: () => req('/portal/student/library-loans'),
  facultyHome: () => req('/portal/faculty/home'),
  facultySchedule: () => req('/portal/faculty/schedule'),
  facultySections: () => req('/portal/faculty/sections'),
  facultySectionStudents: (id: string) => req(`/portal/faculty/section/${id}/students`),
  parentHome: () => req('/portal/parent/home'),

  // ---- integrations ----
  integrations: () => req('/integrations'),
  toggleIntegration: (key: string) => req('/integrations/toggle', { method: 'POST', body: JSON.stringify({ key }) }),
  syncIntegration: (key: string) => req('/integrations/sync', { method: 'POST', body: JSON.stringify({ key }) }),
}

export function saveSession(token: string, user: any) {
  localStorage.setItem('icms_token', token)
  localStorage.setItem('icms_user', JSON.stringify(user))
}
export function getUser() {
  const u = localStorage.getItem('icms_user')
  return u ? JSON.parse(u) : null
}
export function logout() {
  localStorage.removeItem('icms_token')
  localStorage.removeItem('icms_user')
}
