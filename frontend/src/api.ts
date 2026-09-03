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
  let data: any = {}
  if (txt) {
    try {
      data = JSON.parse(txt)
    } catch {
      // Reverse proxies and unhandled server errors can return plain text or
      // HTML. Preserve a useful message instead of leaking a JSON parse error.
      data = { detail: txt.trim() || `Request failed (${res.status})` }
    }
  }
  if (!res.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item: any) => {
          const field = Array.isArray(item.loc) ? item.loc.filter((part: any) => part !== 'body').join(' → ') : ''
          const message = item.msg || item.message || JSON.stringify(item)
          return field ? `${field}: ${message}` : message
        }).join(', ')
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
  frontdeskDashboard: () => req('/frontdesk/dashboard'),
  frontdeskVisitors: (status = '', q = '') => req(`/frontdesk/visitors?status=${encodeURIComponent(status)}&q=${encodeURIComponent(q)}`),
  createFrontdeskVisitor: (body: any) => req('/frontdesk/visitors', { method: 'POST', body: JSON.stringify(body) }),
  updateFrontdeskVisitor: (id: string, body: any) => req(`/frontdesk/visitors/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  frontdeskVisitorStatus: (id: string, status: string) => req(`/frontdesk/visitors/${id}/status`, { method: 'POST', body: JSON.stringify({ status }) }),
  deleteFrontdeskVisitor: (id: string) => req(`/frontdesk/visitors/${id}`, { method: 'DELETE' }),
  validateFrontdeskPass: (pass: string) => req(`/frontdesk/passes/${encodeURIComponent(pass)}/validate`),
  scanFrontdeskPass: (pass: string) => req(`/frontdesk/passes/${encodeURIComponent(pass)}/scan`, { method: 'POST' }),
  frontdeskAppointments: (status = '') => req(`/frontdesk/appointments?status=${encodeURIComponent(status)}`),
  createFrontdeskAppointment: (body: any) => req('/frontdesk/appointments', { method: 'POST', body: JSON.stringify(body) }),
  frontdeskTickets: (status = '') => req(`/frontdesk/tickets?status=${encodeURIComponent(status)}`),
  createFrontdeskTicket: (body: any) => req('/frontdesk/tickets', { method: 'POST', body: JSON.stringify(body) }),
  frontdeskCalls: () => req('/frontdesk/calls'),
  frontdeskDirectory: () => req('/frontdesk/directory'),
  frontdeskEmployees: () => req('/frontdesk/employees'),
  frontdeskDelegations: () => req('/frontdesk/delegations'),
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
  admissionCycles: () => req('/admissions/cycles'),
  admissionProgrammes: () => req('/admissions/programmes'),
  admissionProgramIntake: () => req('/admissions/program-intake'),
  admissionDocumentStatus: () => req('/admissions/document-status'),
  admissionPhase5Status: () => req('/admissions/phase5-status'),
  admissionFinalApprovals: () => req('/admissions/final-approvals'),
  admissionDirectorMonitoring: () => req('/admissions/director-monitoring'),
  admissionReviewQueue: (params: Record<string, string> = {}) => req(`/admissions/review-queue?${new URLSearchParams(params)}`),
  admissionDetail: (id: string) => req(`/admissions/${id}/detail`),
  createAdmissionCycle: (body: any) => req('/admissions/cycles', { method: 'POST', body: JSON.stringify(body) }),
  updateAdmissionCycle: (id: string, body: any) => req(`/admissions/cycles/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  publishAdmissionCycle: (id: string) => req(`/admissions/cycles/${id}/publish`, { method: 'POST' }),
  closeAdmissionCycle: (id: string) => req(`/admissions/cycles/${id}/close`, { method: 'POST' }),
  bindAdmissionProgram: (cycleId: string, body: any) => req(`/admissions/cycles/${cycleId}/programs`, { method: 'POST', body: JSON.stringify(body) }),
  openAdmissionPrograms: () => req('/admissions/open-programs'),
  startApplicantApplication: (body: any) => req('/admissions/applicant/start', { method: 'POST', body: JSON.stringify(body) }),
  applicantApplication: (id: string, token: string) => req(`/admissions/applicant/${id}`, { headers: { 'X-Applicant-Access-Token': token } }),
  saveApplicantProfile: (id: string, token: string, body: any) => req(`/admissions/applicant/${id}/profile`, { method: 'PUT', headers: { 'X-Applicant-Access-Token': token }, body: JSON.stringify(body) }),
  applicantRequirements: (id: string, token: string) => req(`/admissions/applicant/${id}/document-requirements`, { headers: { 'X-Applicant-Access-Token': token } }),
  addApplicantPreference: (id: string, token: string, body: any) => req(`/admissions/applicant/${id}/preferences`, { method: 'POST', headers: { 'X-Applicant-Access-Token': token }, body: JSON.stringify(body) }),
  reorderApplicantPreferences: (id: string, token: string, body: any) => req(`/admissions/applicant/${id}/preferences/order`, { method: 'PUT', headers: { 'X-Applicant-Access-Token': token }, body: JSON.stringify(body) }),
  removeApplicantPreference: (id: string, preferenceId: string, token: string, version: number) => req(`/admissions/applicant/${id}/preferences/${preferenceId}?expected_status_version=${version}`, { method: 'DELETE', headers: { 'X-Applicant-Access-Token': token } }),
  addApplicantDocument: (id: string, token: string, body: any) => req(`/admissions/applicant/${id}/documents`, { method: 'POST', headers: { 'X-Applicant-Access-Token': token }, body: JSON.stringify(body) }),
  submitApplicantApplication: (id: string, token: string, version: number) => req(`/admissions/applicant/${id}/submit`, { method: 'POST', headers: { 'X-Applicant-Access-Token': token }, body: JSON.stringify({ expected_status_version: version }) }),
  eligibilityRules: (cycle_id = '') => req(`/admissions/eligibility/rules?cycle_id=${cycle_id}`),
  eligibilityQuotas: (cycle_id = '') => req(`/admissions/eligibility/quotas?cycle_id=${cycle_id}`),
  createEligibilityRule: (body: any) => req('/admissions/eligibility/rules', { method: 'POST', body: JSON.stringify(body) }),
  updateEligibilityRule: (id: string, body: any) => req(`/admissions/eligibility/rules/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  createEligibilityQuota: (body: any) => req('/admissions/eligibility/quotas', { method: 'POST', body: JSON.stringify(body) }),
  updateEligibilityQuota: (id: string, body: any) => req(`/admissions/eligibility/quotas/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  eligibilityQueue: (params: Record<string, string> = {}) => req(`/admissions/eligibility/queue?${new URLSearchParams(params)}`),
  evaluateEligibility: (id: string, expected_status_version: number) => req(`/admissions/${id}/eligibility/evaluate`, { method: 'POST', body: JSON.stringify({ expected_status_version }) }),
  eligibilityDetail: (id: string) => req(`/admissions/${id}/eligibility`),
  applicantEligibilityStatus: (id: string, token: string) => req(`/admissions/applicant/${id}/eligibility-status`, { headers: { 'X-Applicant-Access-Token': token } }),
  applicantOffer: (id: string, token: string) => req(`/admissions/applicant/${id}/offer`, { headers: { 'X-Applicant-Access-Token': token } }),
  respondApplicantOffer: (id: string, token: string, response: 'accept' | 'decline', expected_status_version: number) => req(`/admissions/applicant/${id}/offer/${response}`, { method: 'POST', headers: { 'X-Applicant-Access-Token': token }, body: JSON.stringify({ expected_status_version }) }),
  applicantFinance: (id: string, token: string) => req(`/admissions/applicant/${id}/finance`, { headers: { 'X-Applicant-Access-Token': token } }),
  assessmentQueue: () => req('/admissions/assessments/queue'),
  advanceAdmissionPhase4: (id: string, expected_status_version: number) => req(`/admissions/${id}/phase4/advance`, { method: 'POST', body: JSON.stringify({ expected_status_version }) }),
  recordAdmissionAssessment: (id: string, body: any) => req(`/admissions/${id}/assessments`, { method: 'POST', body: JSON.stringify(body) }),
  calculateAdmissionMerit: (id: string) => req(`/admissions/${id}/merit`, { method: 'POST' }),
  admissionSeatPools: (cycle_id = '') => req(`/admissions/seat-pools?cycle_id=${cycle_id}`),
  createAdmissionSeatPool: (body: any) => req('/admissions/seat-pools', { method: 'POST', body: JSON.stringify(body) }),
  allocateAdmissionSeat: (id: string, body: any) => req(`/admissions/${id}/allocate`, { method: 'POST', body: JSON.stringify(body) }),
  recommendAdmissionOffer: (id: string, expected_status_version: number) => req(`/admissions/${id}/offer/recommend`, { method: 'POST', body: JSON.stringify({ expected_status_version }) }),
  issueAdmissionOffer: (id: string, expected_status_version: number) => req(`/admissions/${id}/offer/issue`, { method: 'POST', body: JSON.stringify({ expected_status_version }) }),
  counsellingQueue: (params: Record<string, string> = {}) => req(`/admissions/counselling/queue?${new URLSearchParams(params)}`),
  counsellingSessions: (cycle_id = '') => req(`/admissions/counselling/sessions?cycle_id=${cycle_id}`),
  createCounsellingSession: (body: any) => req('/admissions/counselling/sessions', { method: 'POST', body: JSON.stringify(body) }),
  recordCounselling: (id: string, body: any) => req(`/admissions/${id}/counselling`, { method: 'POST', body: JSON.stringify(body) }),
  admissionWaitlist: () => req('/admissions/waitlist'),
  admissionOffers: (status = '') => req(`/admissions/offers?status=${status}`),
  resolveAdmissionFees: (id: string, expected_status_version: number, fee_structure_id?: string) => req(`/admissions/${id}/fees/resolve`, { method: 'POST', body: JSON.stringify({ expected_status_version, fee_structure_id }) }),
  issueAdmissionInvoice: (id: string, expected_status_version: number) => req(`/admissions/${id}/invoice`, { method: 'POST', body: JSON.stringify({ expected_status_version }) }),
  admissionChecklist: (id: string) => req(`/admissions/${id}/ready-to-admit`),
  convertAdmission: (id: string, expected_status_version: number) => req(`/admissions/${id}/convert`, { method: 'POST', body: JSON.stringify({ expected_status_version }) }),

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
  createTransportRoute: (b: any) => req('/transport/routes', { method: 'POST', body: JSON.stringify(b) }),
  createTransportStop: (routeId: string, b: any) => req('/transport/stops', { method: 'POST', body: JSON.stringify({...b, route_id: routeId}) }),
  createTransportVehicle: (b: any) => req('/transport/vehicles', { method: 'POST', body: JSON.stringify({...b, number: b.number || b.vehicle_number, kind: b.kind || b.vehicle_type}) }),
  createTransportDriver: (b: any) => req('/transport/drivers', { method: 'POST', body: JSON.stringify({...b, license_no: b.license_no || b.license_number}) }),
  createTransportAllocation: (b: any) => req('/transport/allocations', { method: 'POST', body: JSON.stringify({...b, stop_id: b.stop_id || b.pickup_stop_id}) }),
  requestTransport: (b: any) => req('/transport/requests', { method: 'POST', body: JSON.stringify(b) }),
  approveTransportRequest: (id: string, b: any) => req(`/transport/requests/${id}/approve`, { method: 'POST', body: JSON.stringify(b) }),
  transportRoutes: () => req('/transport'),
  transportVehicles: () => req('/transport'),
  transportDrivers: () => req('/transport'),
  transportRequests: () => req('/transport'),
  transportAllocations: () => req('/transport'),
  createTransportRequest: (b: any) => req('/transport/requests', { method: 'POST', body: JSON.stringify(b) }),
  myTransportAllocation: () => req('/transport/my-allocation'),
  updateTransportVehicle: (id: string, b: any) => req(`/transport/vehicles/${id}`, { method: 'PUT', body: JSON.stringify(b) }),
  deleteTransportRoute: (id: string) => req(`/transport/routes/${id}`, { method: 'DELETE' }),
  updateTransportStop: (routeId: string, id: string, b: any) => req(`/transport/stops/${id}`, { method: 'PUT', body: JSON.stringify({...b, route_id: routeId}) }),
  deleteTransportStop: (routeId: string, id: string) => req(`/transport/stops/${id}`, { method: 'DELETE' }),
  updateTransportAllocation: (id: string, b: any) => req(`/transport/allocations/${id}`, { method: 'PUT', body: JSON.stringify(b) }),
  deleteTransportAllocation: (id: string) => req(`/transport/allocations/${id}`, { method: 'DELETE' }),
  rejectTransportRequest: (id: string) => req(`/transport/requests/${id}/reject`, { method: 'POST' }),
  transportDriverDashboard: () => req('/transport/driver-dashboard'),
  startTransportTrip: (b: any) => req('/transport/trips/start', { method: 'POST', body: JSON.stringify(b) }),
  endTransportTrip: (id: string) => req(`/transport/trips/${id}/end`, { method: 'POST' }),
  sendTransportLocation: (b: any) => req('/transport/locations', { method: 'POST', body: JSON.stringify(b) }),
  liveTransportLocation: (id: string) => req(`/transport/live-location/${id}`),
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
