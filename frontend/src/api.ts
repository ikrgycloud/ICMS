const BASE = import.meta.env.VITE_API_URL || '/api'

function tok() { return localStorage.getItem('icms_token') || '' }

async function req(path: string, opts: RequestInit = {}) {
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
  const data = txt ? JSON.parse(txt) : {}
  if (!res.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item: any) => item.msg || item.message || JSON.stringify(item)).join(', ')
      : data.detail
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return data
}

async function download(path: string) {
  const headers: Record<string, string> = {}
  const t = tok()
  if (t) headers.Authorization = `Bearer ${t}`
  const res = await fetch(`${BASE}${path}`, { headers })
  if (!res.ok) throw new Error('Could not download the receipt')

  const url = URL.createObjectURL(await res.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = 'ICMS-payment-receipt.pdf'
  link.click()
  URL.revokeObjectURL(url)
}

export const api = {
  login: (username: string, password: string) =>
    req('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  me: () => req('/me'),
  stats: () => req('/stats'),
  catalog: () => req('/catalog'),
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
  examTimetable: (sectionId: string) => req(`/exams/timetable/${sectionId}`),
  createAssessment: (b: any) => req('/exams/assessments', { method: 'POST', body: JSON.stringify(b) }),
  updateAssessment: (assessmentId: string, b: any) =>
    req(`/exams/assessments/${assessmentId}`, { method: 'PUT', body: JSON.stringify(b) }),
  createExamTimetable: (b: any) => req('/exams/timetable', { method: 'POST', body: JSON.stringify(b) }),
  updateExamTimetable: (scheduleId: string, b: any) =>
    req(`/exams/timetable/${scheduleId}`, { method: 'PUT', body: JSON.stringify(b) }),
  enterMarks: (b: any) => req('/exams/marks', { method: 'POST', body: JSON.stringify(b) }),
  publishMarks: (assessment_id: string) => req('/exams/marks/publish', { method: 'POST', body: JSON.stringify({ assessment_id }) }),
  publishResult: (section_id: string) => req('/exams/publish', { method: 'POST', body: JSON.stringify({ section_id }) }),

  // ---- admissions ----
  applications: () => req('/admissions'),
  decideApplication: (application_id: string, action: string) =>
    req('/admissions/decide', { method: 'POST', body: JSON.stringify({ application_id, action }) }),

  // ---- finance ----
  invoices: () => req('/finance/invoices'),
  academicRollovers: () => req('/academic-rollover'),
  academicRolloverPolicy: () => req('/academic-rollover/policy'),
  updateAcademicRolloverPolicy: (body: any) => req('/academic-rollover/policy', { method: 'PUT', body: JSON.stringify(body) }),
  startAcademicRollover: (body: any) => req('/academic-rollover', { method: 'POST', body: JSON.stringify(body) }),
  decideAcademicRollover: (id: string, body: any) => req(`/academic-rollover/${id}/decision`, { method: 'POST', body: JSON.stringify(body) }),
  submitAcademicRollover: (id: string) => req(`/academic-rollover/${id}/submit`, { method: 'POST' }),
  approveAcademicRollover: (id: string) => req(`/academic-rollover/${id}/approve`, { method: 'POST' }),
  executeAcademicRollover: (id: string) => req(`/academic-rollover/${id}/execute`, { method: 'POST' }),
  budget: () => req('/finance/budget'),
  recordPayment: (invoice_id: string, amount: number, method = 'cash', reference = '') =>
    req('/finance/payment', { method: 'POST', body: JSON.stringify({ invoice_id, amount, method, reference }) }),
  clearOfflinePayment: (payment_id: string, action: 'cleared' | 'bounced') =>
    req(`/finance/payments/${payment_id}/clear`, { method: 'POST', body: JSON.stringify({ action }) }),
  downloadFinanceReceipt: (invoice_id: string, payment_id = '') => download(`/finance/invoices/${invoice_id}/receipt.pdf${payment_id ? `?payment_id=${encodeURIComponent(payment_id)}` : ''}`),
  waiveFee: (b: any) => req('/finance/waive', { method: 'POST', body: JSON.stringify(b) }),
  feeReferenceData: () => req('/fees/reference-data'),
  feeHeads: (includeInactive = false) => req(`/fees/heads?include_inactive=${includeInactive}`),
  createFeeHead: (b: any) => req('/fees/heads', { method: 'POST', body: JSON.stringify(b) }),
  updateFeeHead: (id: string, b: any) => req(`/fees/heads/${id}`, { method: 'PUT', body: JSON.stringify(b) }),
  setFeeHeadStatus: (id: string, is_active: boolean) => req(`/fees/heads/${id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  feeStructures: (filters: Record<string, string> = {}) => {
    const qs = new URLSearchParams(Object.entries(filters).filter(([, value]) => value))
    return req(`/fee-structures${qs.size ? `?${qs}` : ''}`)
  },
  feeStructure: (id: string) => req(`/fee-structures/${id}`),
  feeStructureAffectedStudents: (id: string) => req(`/fee-structures/${id}/affected-students`),
  createFeeStructure: (b: any) => req('/fee-structures', { method: 'POST', body: JSON.stringify(b) }),
  updateFeeStructure: (id: string, b: any) => req(`/fee-structures/${id}`, { method: 'PUT', body: JSON.stringify(b) }),
  publishFeeStructure: (id: string) => req(`/fee-structures/${id}/publish`, { method: 'POST' }),
  submitFeeStructure: (id: string) => req(`/fee-structures/${id}/submit`, { method: 'POST' }),

  // ---- library ----
  books: (q = '') => req(`/library/books?q=${encodeURIComponent(q)}`),
  loans: () => req('/library/loans'),
  issueBook: (b: any) => req('/library/issue', { method: 'POST', body: JSON.stringify(b) }),
  returnBook: (loan_id: string) => req(`/library/return/${loan_id}`, { method: 'POST' }),

  // ---- hr ----
  leave: () => req('/hr/leave'),
  jobs: () => req('/hr/jobs'),
  decideLeave: (leave_id: string, action: string) =>
    req('/hr/leave/decide', { method: 'POST', body: JSON.stringify({ leave_id, action }) }),

  // ---- ops ----
  assets: () => req('/assets'),
  hostel: () => req('/hostel'),
  allocateHostel: (id: string) => req(`/hostel/allocate/${id}`, { method: 'POST' }),
  transport: () => req('/transport'),
  research: () => req('/research'),
  placements: () => req('/placements'),

  // ---- grievance ----
  grievance: () => req('/grievance'),
  raiseComplaint: (b: any) => req('/grievance', { method: 'POST', body: JSON.stringify(b) }),
  resolveComplaint: (complaint_id: string, status = 'resolved') =>
    req('/grievance/resolve', { method: 'POST', body: JSON.stringify({ complaint_id, status }) }),

  // ---- governance / admin ----
  governance: (semester = '') => {
    const params = new URLSearchParams()
    if (semester) params.set('semester', semester)
    const qs = params.toString()
    return req(`/governance${qs ? `?${qs}` : ''}`)
  },
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
  studentChallans: () => req('/portal/student/fees/challans'),
  createStudentChallan: (invoice_id: string, amount?: number) => req('/portal/student/fees/challans', { method: 'POST', body: JSON.stringify({ invoice_id, ...(amount !== undefined ? { amount } : {}) }) }),
  downloadStudentChallan: (challan_id: string) => download(`/portal/student/fees/challans/${challan_id}/pdf`),
  submitOfflineProof: (body: any) => req('/portal/student/fees/offline-proofs', { method: 'POST', body: JSON.stringify(body) }),
  createRazorpayOrder: (invoice_id: string, amount?: number) => req('/portal/student/fees/razorpay/order', { method: 'POST', body: JSON.stringify({ invoice_id, ...(amount !== undefined ? { amount } : {}) }) }),
  verifyRazorpayPayment: (body: any) => req('/portal/student/fees/razorpay/verify', { method: 'POST', body: JSON.stringify(body) }),
  downloadStudentReceipt: (invoice_id: string, payment_id = '') => download(`/portal/student/fees/invoices/${invoice_id}/receipt.pdf${payment_id ? `?payment_id=${encodeURIComponent(payment_id)}` : ''}`),
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
  createParentRazorpayOrder: (invoice_id: string, amount?: number) => req('/portal/parent/fees/razorpay/order', { method: 'POST', body: JSON.stringify({ invoice_id, ...(amount !== undefined ? { amount } : {}) }) }),
  verifyParentRazorpayPayment: (body: any) => req('/portal/parent/fees/razorpay/verify', { method: 'POST', body: JSON.stringify(body) }),
  downloadParentReceipt: (invoice_id: string) => download(`/portal/parent/fees/invoices/${invoice_id}/receipt.pdf`),
  pendingPayments: () => req('/finance/payments/pending'),
  verifyOfflinePayment: (payment_id: string, action: string, remarks = '') => req(`/finance/payments/${payment_id}/clear`, { method: 'POST', body: JSON.stringify({ action, remarks }) }),

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
