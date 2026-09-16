import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast, Modal, money, Empty } from './kit'
import PayrollPanel from './PayrollPanel'

/**
 * Campus / Branch Head finance oversight.  The API is responsible for applying
 * canonical campus scope; this component intentionally has no mutating controls
 * or action modals.
 */
function CampusFinanceReadOnly() {
  const [tab, setTab] = useState<'fees' | 'budget'>('fees')
  const [data, setData] = useState<any>(null)
  const [budget, setBudget] = useState<any>(null)

  useEffect(() => {
    let active = true
    Promise.allSettled([api.invoices(), api.budget()]).then(([invoices, budgetResult]) => {
      if (!active) return
      setData(invoices.status === 'fulfilled' ? invoices.value : null)
      setBudget(budgetResult.status === 'fulfilled' ? budgetResult.value : null)
    })
    return () => { active = false }
  }, [])

  if (!data) return <Spinner />
  const summary = data.summary || {}
  const collectionRate = Math.round(100 * Number(summary.total_collected || 0) / (Number(summary.total_billed || 0) || 1))
  const invoices = Array.isArray(data.invoices) ? data.invoices : []
  const budgetRows = Array.isArray(budget?.budget) ? budget.budget : []

  return <div className="fade-in finance-workspace campus-finance-readonly">
    <PageHead title="Finance" sub="Fee collection, waivers (with limit-based escalation), and budget oversight" />
    <section className="kpi-row">
      <div className="kpi"><span className="kpi-l">Total billed</span><b className="kpi-v">{money(summary.total_billed || 0)}</b></div>
      <div className="kpi"><span className="kpi-l">Collected</span><b className="kpi-v campus-finance-teal">{money(summary.total_collected || 0)}</b></div>
      <div className="kpi"><span className="kpi-l">Outstanding</span><b className="kpi-v campus-finance-rose">{money(summary.outstanding || 0)}</b></div>
      <div className="kpi"><span className="kpi-l">Collection rate</span><b className="kpi-v">{collectionRate}%</b></div>
    </section>
    <div className="tabs" role="tablist" aria-label="Finance oversight sections">
      <button type="button" role="tab" aria-selected={tab === 'fees'} className={`tab ${tab === 'fees' ? 'on' : ''}`} onClick={() => setTab('fees')}>Fee invoices</button>
      <button type="button" role="tab" aria-selected={tab === 'budget'} className={`tab ${tab === 'budget' ? 'on' : ''}`} onClick={() => setTab('budget')}>Budget</button>
    </div>
    {tab === 'fees' ? <section className="card">
      <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Roll No</th><th>Name</th><th>Billed</th><th>Paid</th><th>Balance</th><th>Status</th></tr></thead><tbody>
        {invoices.slice(0, 80).map((invoice: any) => <tr key={invoice.id}><td className="mono">{invoice.roll_no || '—'}</td><td>{invoice.name || 'Not available yet'}</td><td>{money(invoice.amount || 0)}</td><td>{money(invoice.paid || 0)}</td><td><b className={Number(invoice.balance || 0) > 0 ? 'campus-finance-rose' : 'campus-finance-teal'}>{money(invoice.balance || 0)}</b></td><td><span className={`pill s-${invoice.status || 'unpaid'}`}>{invoice.status || 'unpaid'}</span></td></tr>)}
        {!invoices.length && <tr><td colSpan={6}><Empty text="No campus invoice data available yet" /></td></tr>}
      </tbody></table></div>
    </section> : <section className="card"><div className="card-pad">
      {budgetRows.length ? budgetRows.map((line: any) => {
        const pct = Math.round(100 * Number(line.spent || 0) / (Number(line.allocated || 0) || 1))
        return <div className="budget-row" key={`${line.category}-${line.fiscal_year || ''}`}><div className="budget-head"><b>{line.category || 'Budget category'}</b><span>{money(line.spent || 0)} / {money(line.allocated || 0)}</span></div><div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(100, Math.max(0, pct))}%`, background: pct > 85 ? 'var(--rose)' : 'var(--brass)' }} /></div></div>
      }) : <Empty text="No campus budget data available yet" />}
    </div></section>}
  </div>
}

function hasFeeCategory(invoice: any, category: string) {
  if (category === 'all') return true
  const categories = invoice.categories?.map((item: any) => (item.fee_category || 'Uncategorised').toUpperCase())
  const actualCats = categories?.length ? categories : [(invoice.fee_category || 'Uncategorised').toUpperCase()]
  return actualCats.includes(category.toUpperCase())
}

type FinanceProps = {
  caps: any
  user: any
  onOpenApprovals: () => void
  overviewOnly?: boolean
  onNavigate?: (view: string) => void
  initialTab?: 'fees' | 'payments' | 'setup' | 'students' | 'payroll'
  /** Campus Heads can inspect their scoped financial position, never transact. */
  readOnly?: boolean
}

export default function Finance(props: FinanceProps) {
  // Keep the leadership view inside the Finance module, rather than duplicating
  // its data contract in a role portal.  This also prevents action-oriented
  // finance workspaces and their modal state from mounting for Campus Heads.
  if (props.readOnly) return <CampusFinanceReadOnly />
  return <FinanceWorkspace {...props} />
}

function FinanceWorkspace({ caps, user, onOpenApprovals, overviewOnly = false, onNavigate, initialTab }: FinanceProps) {
  // Start with live financial records; fee setup is an occasional configuration task.
  const [tab, setTab] = useState<'overview' | 'fees' | 'payments' | 'setup' | 'students' | 'payroll'>(() => overviewOnly ? 'overview' : initialTab || (user?.office_n === 22 ? 'setup' : user?.office_n === 23 ? 'payroll' : 'fees'))
  const [data, setData] = useState<any>(null)
  const [decision, setDecision] = useState<any>(null)
  const [modal, setModal] = useState<{ kind: string; inv: any; method?: string; reference?: string } | null>(null)
  const [amount, setAmount] = useState('')
  const [search, setSearch] = useState('')
  const [studentQuery, setStudentQuery] = useState('')
  const [students, setStudents] = useState<any[]>([])
  const [selectedStudent, setSelectedStudent] = useState<any>(null)
  const [selectedSemester, setSelectedSemester] = useState('')
  const [selectedStudentCategory, setSelectedStudentCategory] = useState('all')
  const [invoiceCategory, setInvoiceCategory] = useState('all')
  const [pendingPayments, setPendingPayments] = useState<any[]>([])
  const [adjustments, setAdjustments] = useState<any[]>([])
  const [reconciliations, setReconciliations] = useState<any[]>([])
  const [refunds, setRefunds] = useState<any[]>([])
  const [waiverRequests, setWaiverRequests] = useState<any[]>([])
  const [vendorPayments, setVendorPayments] = useState<any[]>([])
  const [dayCloses, setDayCloses] = useState<any[]>([])
  const [reviewDraft, setReviewDraft] = useState<any>(null)
  const [adjustmentDraft, setAdjustmentDraft] = useState<any>(null)
  const [refundDraft, setRefundDraft] = useState<any>(null)
  const [waiverDraft, setWaiverDraft] = useState<any>(null)
  const [submittingReview, setSubmittingReview] = useState(false)
  const [submittingAdjustment, setSubmittingAdjustment] = useState(false)
  const [submittingRefund, setSubmittingRefund] = useState(false)
  const [submittingWaiver, setSubmittingWaiver] = useState(false)

  async function load() {
    const [invoicesResult, adjustmentsResult, reconciliationsResult, refundsResult, waiversResult, vendorPaymentsResult, dayClosesResult] = await Promise.allSettled([
      api.invoices(),
      api.financeAdjustments(),
      api.financeReconciliations(),
      api.financeRefunds(),
      api.feeWaiverRequests(),
      api.vendorPayments(),
      api.dayCloses(),
    ])
    if (invoicesResult.status === 'fulfilled') setData(invoicesResult.value)
    if (adjustmentsResult.status === 'fulfilled') setAdjustments(adjustmentsResult.value.adjustments || [])
    if (reconciliationsResult.status === 'fulfilled') setReconciliations(reconciliationsResult.value.reconciliations || [])
    if (refundsResult.status === 'fulfilled') setRefunds(refundsResult.value.refunds || [])
    if (waiversResult.status === 'fulfilled') setWaiverRequests(waiversResult.value.waiver_requests || [])
    if (vendorPaymentsResult.status === 'fulfilled') setVendorPayments(vendorPaymentsResult.value.vendor_payments || [])
    if (dayClosesResult.status === 'fulfilled') setDayCloses(dayClosesResult.value.day_closes || [])
  }
  useEffect(() => {
    load()
    if (user?.office_n !== 23) return
    const timer = window.setInterval(load, 30000)
    return () => window.clearInterval(timer)
  }, [user?.office_n])
  useEffect(() => { if (tab === 'payments') api.pendingPayments().then((r:any) => setPendingPayments(r.payments || [])).catch(() => setPendingPayments([])) }, [tab])
  async function decideOffline(payment:any, action:string) {
    const remarks = ['bounced', 'rejected'].includes(action) ? window.prompt('Reason (required):') || '' : ''
    try { await api.verifyOfflinePayment(payment.id, action, remarks); setPendingPayments(rows => rows.filter(row => row.id !== payment.id)); load() }
    catch (error:any) { alert(error.message || 'Could not update payment') }
  }

  function reviewInvoice(invoice:any) {
    setReviewDraft({
      invoice,
      decision: 'approved',
      remarks: '',
    })
  }

  async function submitReview() {
    if (!reviewDraft?.invoice) return
    const decision = (reviewDraft.decision || 'approved').trim().toLowerCase()
    if (!['approved', 'pending_review', 'rejected'].includes(decision)) {
      setDecision({ outcome: 'DENY', reason: 'Choose a valid review decision.' })
      return
    }
    try {
      setSubmittingReview(true)
      const result = await api.reviewInvoice(reviewDraft.invoice.id, { decision, remarks: reviewDraft.remarks || '' })
      setDecision({ outcome: decision === 'rejected' ? 'DENY' : 'APPROVE', reason: `Invoice review recorded: ${result.status || decision}` })
      setReviewDraft(null)
      load()
    } catch (error:any) {
      setDecision({ outcome: 'DENY', reason: error.message || 'Could not review invoice' })
    } finally {
      setSubmittingReview(false)
    }
  }

  function requestAdjustment(invoice:any) {
    setAdjustmentDraft({
      invoice,
      adjustment_type: 'credit',
      amount: '',
      reason: '',
    })
  }

  async function submitAdjustment() {
    if (!adjustmentDraft?.invoice) return
    const adjustmentType = (adjustmentDraft.adjustment_type || 'credit').trim().toLowerCase()
    const amount = Number(adjustmentDraft.amount)
    if (!['credit', 'debit', 'refund'].includes(adjustmentType)) {
      setDecision({ outcome: 'DENY', reason: 'Choose a valid adjustment type.' })
      return
    }
    if (!Number.isFinite(amount) || amount <= 0) {
      setDecision({ outcome: 'DENY', reason: 'Enter a valid adjustment amount greater than zero.' })
      return
    }
    if (!(adjustmentDraft.reason || '').trim()) {
      setDecision({ outcome: 'DENY', reason: 'Reason is required for the adjustment.' })
      return
    }
    try {
      setSubmittingAdjustment(true)
      const result = await api.createAdjustment({ invoice_id: adjustmentDraft.invoice.id, adjustment_type: adjustmentType, amount, reason: adjustmentDraft.reason })
      setDecision({ outcome: 'APPROVE', reason: `Adjustment requested: ${result.adjustment?.status || 'pending_review'}` })
      setAdjustmentDraft(null)
      load()
    } catch (error:any) {
      setDecision({ outcome: 'DENY', reason: error.message || 'Could not request adjustment' })
    } finally {
      setSubmittingAdjustment(false)
    }
  }

  async function createReconciliation() {
    const notes = window.prompt('Reconciliation notes:', '') || ''
    try {
      const result = await api.createReconciliation({ notes })
      setDecision({ outcome: 'APPROVE', reason: `Reconciliation closed: ${result.reconciliation?.id || 'created'}` })
      load()
    } catch (error:any) { alert(error.message || 'Could not create reconciliation') }
  }

  function requestRefund(invoice:any) {
    const paid = Number(invoice.paid || 0)
    if (!(paid > 0)) {
      setDecision({ outcome: 'DENY', reason: 'Refund is only available for invoices with a paid amount greater than zero.' })
      return
    }
    setRefundDraft({
      invoice,
      amount: String(Math.min(paid, Number(invoice.amount || paid))),
      reason: '',
    })
  }

  async function submitRefundRequest() {
    if (!refundDraft?.invoice) return
    const amount = Number(refundDraft.amount)
    if (!Number.isFinite(amount) || amount <= 0) {
      setDecision({ outcome: 'DENY', reason: 'Enter a valid refund amount greater than zero.' })
      return
    }
    const paid = Number(refundDraft.invoice.paid || 0)
    if (amount > paid) {
      setDecision({ outcome: 'DENY', reason: 'Refund amount cannot exceed the invoice paid amount.' })
      return
    }
    const reason = (refundDraft.reason || '').trim()
    if (!reason) {
      setDecision({ outcome: 'DENY', reason: 'Reason is required for a refund request.' })
      return
    }
    try {
      setSubmittingRefund(true)
      const result = await api.createRefund({ invoice_id: refundDraft.invoice.id, amount, reason })
      setDecision({ outcome: 'APPROVE', reason: `Refund requested: ${result.refund?.status || 'pending_approval'}` })
      setRefundDraft(null)
      load()
    } catch (error:any) {
      setDecision({ outcome: 'DENY', reason: error.message || 'Could not create refund request' })
    } finally {
      setSubmittingRefund(false)
    }
  }

  async function handleRefundDecision(row:any, decision:'approved'|'rejected'|'executed') {
    try {
      if (decision === 'executed') {
        const result = await api.executeRefund(row.id)
        setDecision({ outcome: 'APPROVE', reason: `Refund executed: ${result.refund?.status || 'executed'}` })
      } else {
        const remarks = decision === 'rejected' ? window.prompt('Reject reason (optional):', '') || '' : ''
        const result = await api.decideRefund(row.id, { decision, remarks })
        setDecision({ outcome: decision === 'rejected' ? 'DENY' : 'APPROVE', reason: `Refund ${result.refund?.status || decision}` })
      }
      load()
    } catch (error:any) {
      setDecision({ outcome: 'DENY', reason: error.message || 'Could not update refund request' })
    }
  }

  function requestWaiver(invoice:any) {
    const balance = Number(invoice.balance ?? (Number(invoice.amount || 0) - Number(invoice.paid || 0)))
    if (!(balance > 0)) {
      setDecision({ outcome: 'DENY', reason: 'A waiver can only be recommended against an unpaid invoice balance.' })
      return
    }
    setWaiverDraft({ invoice, amount: String(balance), reason: '' })
  }

  async function submitWaiverRequest() {
    if (!waiverDraft?.invoice) return
    const amount = Number(waiverDraft.amount)
    const balance = Number(waiverDraft.invoice.balance ?? (Number(waiverDraft.invoice.amount || 0) - Number(waiverDraft.invoice.paid || 0)))
    const reason = (waiverDraft.reason || '').trim()
    if (!Number.isFinite(amount) || amount <= 0 || amount > balance) {
      setDecision({ outcome: 'DENY', reason: 'Enter an amount within the current unpaid invoice balance.' })
      return
    }
    if (!reason) {
      setDecision({ outcome: 'DENY', reason: 'A documented reason is required for a waiver recommendation.' })
      return
    }
    try {
      setSubmittingWaiver(true)
      const result = await api.createFeeWaiverRequest({ invoice_id: waiverDraft.invoice.id, amount, reason })
      setDecision({ outcome: 'APPROVE', reason: `Waiver recommended to Principal: ${result.workflow_id}` })
      setWaiverDraft(null)
      load()
    } catch (error:any) {
      setDecision({ outcome: 'DENY', reason: error.message || 'Could not submit waiver recommendation' })
    } finally {
      setSubmittingWaiver(false)
    }
  }

  async function executeWaiver(row:any) {
    try {
      const result = await api.executeFeeWaiverRequest(row.id)
      setDecision({ outcome: 'APPROVE', reason: `Fee waiver executed: ${result.waiver_request?.status || 'executed'}` })
      load()
    } catch (error:any) {
      setDecision({ outcome: 'DENY', reason: error.message || 'Could not execute fee waiver' })
    }
  }

  async function resubmitWaiver(row:any) {
    const reason = window.prompt('Update the documented reason before resubmitting to Principal:', row.reason || '')?.trim() || ''
    if (!reason) return
    try {
      const result = await api.resubmitFeeWaiverRequest(row.id, { reason })
      setDecision({ outcome: 'APPROVE', reason: `Waiver resubmitted to Principal: ${result.workflow_id}` })
      load()
    } catch (error:any) {
      setDecision({ outcome: 'DENY', reason: error.message || 'Could not resubmit fee waiver' })
    }
  }

  async function createVendorPayment() {
    const vendorName = window.prompt('Vendor name:', '')?.trim() || ''
    if (!vendorName) {
      alert('Vendor name is required.')
      return
    }
    const invoiceRef = window.prompt('Invoice / bill reference:', '')?.trim() || ''
    const amountText = window.prompt('Payment amount (₹):', '0') || '0'
    const amount = Number(amountText)
    if (!Number.isFinite(amount) || amount <= 0) {
      alert('Enter a valid vendor payment amount greater than zero.')
      return
    }
    const notes = window.prompt('Notes:', '') || ''
    try {
      const result = await api.createVendorPayment({ vendor_name: vendorName, invoice_ref: invoiceRef, amount, notes })
      setDecision({ outcome: 'APPROVE', reason: `Vendor payment requested: ${result.vendor_payment?.status || 'pending_approval'}` })
      load()
    } catch (error:any) { alert(error.message || 'Could not create vendor payment') }
  }

  async function closeDay() {
    const notes = window.prompt('Day-close notes:', '') || ''
    try {
      const result = await api.createDayClose({ notes })
      setDecision({ outcome: 'APPROVE', reason: `Day closed: ${result.day_close?.id || 'created'}` })
      load()
    } catch (error:any) { alert(error.message || 'Could not close the day') }
  }

  async function loadStudents(q = '') {
    try {
      // The student API is paginated (maximum 100 per request). Load every
      // page so Finance can search the complete authorised student list.
      const first = await api.students(q, '', 1, 100)
      const pages = Number(first?.total_pages || 1)
      const rest = await Promise.all(Array.from({ length: Math.max(0, pages - 1) }, (_, i) => api.students(q, '', i + 2, 100)))
      setStudents([...(first?.students || []), ...rest.flatMap((page: any) => page?.students || [])])
    } catch (e) {
      setStudents([])
    }
  }

  useEffect(() => {
    if (tab === 'students') loadStudents(studentQuery)
  }, [tab])

  useEffect(() => {
    if (!selectedStudent || !selectedStudent.id) return
    api.studentProfile(selectedStudent.id).then((profile: any) => setSelectedStudent(profile.student || selectedStudent)).catch(() => {})
  }, [selectedStudent?.id])

  async function act() {
    if (!modal) return
    try {
      const amt = Number(amount)
      const method = (modal.method || 'cash').toLowerCase()
      const reference = (modal.reference || '').trim() || `${method.toUpperCase()}-${Date.now().toString().slice(-6)}`
      const r = await api.recordPayment(modal.inv.id, amt, method, reference, modal.inv.workflow_version_no)
      if (method === 'cash' && r.status !== 'pending_clearance') api.downloadFinanceReceipt(modal.inv.id, r.payment_id)
      setDecision(r.decision || { outcome: 'APPROVE', reason: `Recorded via ${method}` }); setModal(null); setAmount(''); load(); if (tab === 'students') loadStudents(studentQuery)
    } catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }); setModal(null) }
  }

  if (!data) return <Spinner />
  const sm = data.summary
  const invoiceCategories = ['TUITION', 'EXAM', 'LIBRARY', 'HOSTEL', 'TRANSPORT', 'LAB', 'DEVELOPMENT', 'ADMISSION', 'OTHER']
  const selectedStudentInvoices = selectedStudent ? (data.invoices || []).filter((invoice: any) => invoice.roll_no === selectedStudent.roll_no) : []
  const studentInvoiceCategories = ['TUITION', 'EXAM', 'LIBRARY', 'HOSTEL', 'TRANSPORT', 'LAB', 'DEVELOPMENT', 'ADMISSION', 'OTHER']
  const availableSemesters = [...new Set(selectedStudentInvoices.map((invoice: any) => invoice.term).filter(Boolean))]
  const filteredStudentInvoices = selectedStudentInvoices.filter((invoice: any) => hasFeeCategory(invoice, selectedStudentCategory))
  const semesterInvoices = selectedSemester ? filteredStudentInvoices.filter((invoice: any) => invoice.term === selectedSemester) : []
  const filteredInvoices = (data.invoices || []).filter((r: any) => {
    const matchesSearch = !search || `${r.roll_no} ${r.name}`.toLowerCase().includes(search.toLowerCase())
    const matchesCategory = hasFeeCategory(r, invoiceCategory)
    return matchesSearch && matchesCategory
  })

  const paymentRows = data.payments || []
  const totalCollected = Number(sm.total_collected || 0)
  const todayKey = new Date().toISOString().slice(0, 10)
  const todayPayments = paymentRows.filter((row: any) => String(row.at || '').slice(0, 10) === todayKey)
  const todayCollected = todayPayments.reduce((sum: number, row: any) => sum + Number(row.amount || 0), 0)
  const pendingVerification = pendingPayments.length + paymentRows.filter((row: any) => ['pending_clearance', 'pending_verification'].includes(row.status)).length
  const refundsReady = refunds.filter((row: any) => row.status === 'approved').length
  const vendorDue = vendorPayments.filter((row: any) => ['pending_approval', 'approved'].includes(row.status))
  const reconciliation = reconciliations[0]
  const paymentModes = paymentRows.reduce((out: Record<string, number>, row: any) => {
    const method = String(row.method || 'other').replace('_', ' ')
    out[method] = (out[method] || 0) + Number(row.amount || 0)
    return out
  }, {})
  const openDashboardTab = overviewOnly && onNavigate ? (next: string) => onNavigate(next === 'overview' ? 'overview' : `finance_${next}`) : setTab

  return (
    <div className="fade-in finance-workspace">
      {!overviewOnly && <PageHead title={user?.office_n === 23 ? 'Accounts Office' : 'Finance Manager'} sub="Fee setup, invoices, and payments recorded in ICMS." />}

      {!overviewOnly && <section className="finance-summary">
        <div className="finance-summary-main"><span>Fee operations dashboard</span><strong>{money(sm.total_collected)}</strong><small>Collected from recorded payments</small></div>
        <div className="finance-stat"><span>Total billed</span><b>{money(sm.total_billed)}</b></div>
        <div className="finance-stat outstanding"><span>Outstanding</span><b>{money(sm.outstanding)}</b></div>
        <div className="finance-stat"><span>Collection rate</span><b>{Math.round(100 * sm.total_collected / (sm.total_billed || 1))}%</b></div>
      </section>}

      {!overviewOnly && <div className="tabs finance-tabs">
        {user?.office_n === 22 && <button className={`tab ${tab === 'setup' ? 'on' : ''}`} onClick={() => setTab('setup')}>Fee setup & structures</button>}
        <button className={`tab ${tab === 'fees' ? 'on' : ''}`} onClick={() => setTab('fees')}>Student invoices</button>
        <button className={`tab ${tab === 'students' ? 'on' : ''}`} onClick={() => setTab('students')}>Students</button>
        <button className={`tab ${tab === 'payments' ? 'on' : ''}`} onClick={() => setTab('payments')}>Payment records</button>
        {user?.office_n === 23 && <button className={`tab ${tab === 'payroll' ? 'on' : ''}`} onClick={() => setTab('payroll')}>Payroll payments</button>}
      </div>}

      {overviewOnly && tab === 'overview' && user?.office_n === 23 && (
        <AccountsOfficeOverview
          totalCollected={totalCollected}
          todayCollected={todayCollected}
          pendingVerification={pendingVerification}
          refundsReady={refundsReady}
          vendorDue={vendorDue}
          reconciliation={reconciliation}
          paymentModes={paymentModes}
          paymentRows={paymentRows}
          todayPayments={todayPayments}
          onOpen={openDashboardTab}
        />
      )}

      {tab === 'payroll' && user?.office_n === 23 && <PayrollPanel />}

      {tab === 'students' && (
        <div className="card finance-card">
          <div className="card-h finance-card-head">
            <div><h3>Student collection</h3><span className="hint">Search by roll number or student name, then confirm manual payment details.</span></div>
            <label className="finance-search"><span>Search</span><input className="inp" placeholder="Roll no. or student name" value={studentQuery} onChange={e => { const value = e.target.value; setStudentQuery(value); loadStudents(value) }} /></label>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 390px) 1fr', gap: 0 }}>
            <div className="tbl-scroll" style={{ borderRight: '1px solid #edf1f7' }}>
              <table className="tbl">
                <thead><tr><th>Roll No</th><th>Name</th><th>Class</th></tr></thead>
                <tbody>
                  {students.length ? students.map((student: any) => (
                    <tr key={student.id} style={{ cursor: 'pointer', background: selectedStudent?.id === student.id ? 'rgba(138,31,43,.04)' : undefined }} onClick={() => { setSelectedStudent(student); setSelectedSemester(''); setSelectedStudentCategory('all') }}>
                      <td className="mono">{student.roll_no}</td>
                      <td><b>{student.name}</b></td>
                      <td>{student.section || '—'}{student.group ? ` / ${student.group}` : ''}</td>
                    </tr>
                  )) : <tr><td colSpan={3}><Empty text="No students match this search." /></td></tr>}
                </tbody>
              </table>
            </div>
            <div style={{ padding: 18 }}>
              {!selectedStudent ? <div className="empty">Select a student to view fee details and confirm payment.</div> : (
                <div style={{ display: 'grid', gap: 16 }}>
                  <div style={{ border: '1px solid #e7edf5', borderRadius: 14, padding: 16, background: '#fbfcfe' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                      <div>
                        <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '.08em', color: '#6b7280' }}>Student profile</div>
                        <h3 style={{ marginTop: 6, fontSize: 26 }}>{selectedStudent.name}</h3>
                      </div>
                      <div className="mono" style={{ fontWeight: 700, color: '#1f2937' }}>{selectedStudent.roll_no}</div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginTop: 14 }}>
                      <div className="stat"><small>Program</small><b>{selectedStudent.program || '—'}</b></div>
                      <div className="stat"><small>Semester</small><b>{selectedStudent.semester || '—'}</b></div>
                      <div className="stat"><small>Section</small><b>{selectedStudent.section || '—'}</b></div>
                      <div className="stat"><small>CGPA</small><b>{selectedStudent.cgpa ?? '—'}</b></div>
                    </div>
                  </div>

                  <div className="card" style={{ borderRadius: 14 }}>
                    <div className="card-h"><div><h3>Open invoices</h3><span className="hint">Select the semester, then record a cash, cheque, DD, or bank-transfer payment.</span></div><div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}><label className="finance-search"><span>Semester</span><select className="select" value={selectedSemester} onChange={e => setSelectedSemester(e.target.value)}><option value="">Select semester</option>{availableSemesters.map((term: any) => <option key={term} value={term}>{term}</option>)}</select></label><label className="finance-search"><span>Category</span><select className="select" value={selectedStudentCategory} onChange={e => { setSelectedStudentCategory(e.target.value); setSelectedSemester('') }}><option value="all">All categories</option>{studentInvoiceCategories.map((category: string) => <option key={category} value={category}>{category}</option>)}</select></label></div></div>
                    <div className="tbl-scroll">
                      <table className="tbl">
                        <thead><tr><th>Invoice</th><th>Amount</th><th>Paid</th><th>Balance</th><th>Method</th><th>Action</th></tr></thead>
                        <tbody>
                          {!selectedSemester ? <tr><td colSpan={6}><Empty text="Select a semester to view its invoice and record payment." /></td></tr> : semesterInvoices.length ? semesterInvoices.map((invoice: any) => (
                            <tr key={invoice.id} className={invoice.balance > 0 ? 'finance-row-due' : 'finance-row-paid'}>
                              <td className="mono">{invoice.term || invoice.id.slice(0, 8)}</td>
                              <td>{money(invoice.amount)}</td>
                              <td>{money(invoice.paid)}</td>
                              <td><b style={{ color: invoice.balance > 0 ? 'var(--rose)' : 'var(--teal)' }}>{money(invoice.balance)}</b></td>
                              <td><span className="pill s-paid">{invoice.status}</span></td>
                              <td>
                                {invoice.balance > 0 ? <button className="btn btn-sm btn-crimson" onClick={() => { setModal({ kind: 'pay', inv: invoice, method: 'cash', reference: '' }); setAmount(String(invoice.balance)) }}>Confirm</button> : <span className="hint">Settled</span>}
                              </td>
                            </tr>
                          )) : <tr><td colSpan={6}><Empty text="No invoices found for this student." /></td></tr>}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'fees' && (
        <div className="card finance-card">
          <div className="card-h finance-card-head"><div><h3>Student invoices</h3><span className="hint">Live balances from the ICMS database</span></div><div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}><label className="finance-search"><span>Search</span><input className="inp" placeholder="Roll number or student name" value={search} onChange={e=>setSearch(e.target.value)} /></label><label className="finance-search"><span>Category</span><select className="select" value={invoiceCategory} onChange={e => setInvoiceCategory(e.target.value)}><option value="all">All categories</option>{invoiceCategories.map((category: string) => <option key={category} value={category}>{category}</option>)}</select></label>{user?.office_n === 22 && <button className="btn btn-brass" onClick={() => setTab('setup')}>Manage fee structures</button>}<button className="btn btn-out" onClick={createReconciliation}>Close reconciliation</button><button className="btn btn-out" onClick={closeDay}>Day close</button></div></div>
          {(adjustments.length > 0 || reconciliations.length > 0 || refunds.length > 0 || waiverRequests.length > 0 || vendorPayments.length > 0 || dayCloses.length > 0) && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12, padding: '0 18px 18px' }}>
              {adjustments.length > 0 && (
                <div className="card" style={{ padding: 12 }}>
                  <h4 style={{ margin: '0 0 8px' }}>Pending adjustments</h4>
                  <div className="tbl-scroll">
                    <table className="tbl">
                      <thead><tr><th>Invoice</th><th>Type</th><th>Amount</th><th>Status</th></tr></thead>
                      <tbody>{adjustments.slice(0, 5).map((row:any) => (
                        <tr key={row.id}><td className="mono">{row.invoice_id.slice(0,8)}</td><td>{row.adjustment_type}</td><td>{money(row.amount)}</td><td><span className={`pill s-${row.status}`}>{row.status}</span></td></tr>
                      ))}</tbody>
                    </table>
                  </div>
                </div>
              )}
              {reconciliations.length > 0 && (
                <div className="card" style={{ padding: 12 }}>
                  <h4 style={{ margin: '0 0 8px' }}>Recent reconciliations</h4>
                  <div className="tbl-scroll">
                    <table className="tbl">
                      <thead><tr><th>ID</th><th>Collected</th><th>Closing</th><th>Status</th></tr></thead>
                      <tbody>{reconciliations.slice(0, 5).map((row:any) => (
                        <tr key={row.id}><td className="mono">{row.id.slice(0,8)}</td><td>{money(row.total_collected)}</td><td>{money(row.closing_balance)}</td><td><span className={`pill s-${row.status}`}>{row.status}</span></td></tr>
                      ))}</tbody>
                    </table>
                  </div>
                </div>
              )}
              {refunds.length > 0 && (
                <div className="card" style={{ padding: 12 }}>
                  <h4 style={{ margin: '0 0 8px' }}>Refund requests</h4>
                  <div className="tbl-scroll">
                    <table className="tbl">
                      <thead><tr><th>Invoice</th><th>Amount</th><th>Status</th></tr></thead>
                      <tbody>{refunds.slice(0, 5).map((row:any) => (
                        <tr key={row.id}>
                          <td className="mono">{row.invoice_id.slice(0,8)}</td>
                          <td>{money(row.amount)}</td>
                          <td>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-start' }}>
                              <span className={`pill s-${row.status}`}>{row.status}</span>
                              {row.status === 'pending_approval' && user?.office_n === 22 && (
                                <div className="row-actions">
                                  <button className="btn btn-sm btn-teal" onClick={() => handleRefundDecision(row, 'approved')}>Approve</button>
                                  <button className="btn btn-sm btn-out" onClick={() => handleRefundDecision(row, 'rejected')}>Reject</button>
                                </div>
                              )}
                              {row.status === 'approved' && user?.office_n === 23 && (
                                <button className="btn btn-sm btn-brass" onClick={() => handleRefundDecision(row, 'executed')}>Execute</button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                </div>
              )}
              {waiverRequests.length > 0 && (
                <div className="card" style={{ padding: 12 }}>
                  <h4 style={{ margin: '0 0 8px' }}>Fee waiver workflow</h4>
                  <div className="tbl-scroll"><table className="tbl">
                    <thead><tr><th>Invoice</th><th>Amount</th><th>Approval</th><th>Action</th></tr></thead>
                    <tbody>{waiverRequests.slice(0, 5).map((row:any) => (
                      <tr key={row.id}><td className="mono">{row.invoice_id.slice(0,8)}</td><td>{money(row.amount)}</td>
                        <td><span className={`pill s-${row.status}`}>{row.status.replaceAll('_', ' ')}</span></td>
                        <td>{row.status === 'approved_pending_accounts' && user?.office_n === 23
                          ? <button className="btn btn-sm btn-brass" onClick={() => executeWaiver(row)}>Execute</button>
                          : row.status === 'returned_to_finance' && user?.office_n === 22
                            ? <button className="btn btn-sm btn-out" onClick={() => resubmitWaiver(row)}>Revise & resubmit</button>
                            : <span className="hint">{row.status === 'pending_principal_approval' ? 'In Principal approvals' : '—'}</span>}</td></tr>
                    ))}</tbody>
                  </table></div>
                </div>
              )}
              {vendorPayments.length > 0 && (
                <div className="card" style={{ padding: 12 }}>
                  <h4 style={{ margin: '0 0 8px' }}>Vendor payments</h4>
                  <div className="tbl-scroll">
                    <table className="tbl">
                      <thead><tr><th>Vendor</th><th>Reference</th><th>Amount</th><th>Status</th></tr></thead>
                      <tbody>{vendorPayments.slice(0, 5).map((row:any) => (
                        <tr key={row.id}><td>{row.vendor_name}</td><td className="mono">{row.invoice_ref || '—'}</td><td>{money(row.amount)}</td><td><span className={`pill s-${row.status}`}>{row.status}</span></td></tr>
                      ))}</tbody>
                    </table>
                  </div>
                </div>
              )}
              {dayCloses.length > 0 && (
                <div className="card" style={{ padding: 12 }}>
                  <h4 style={{ margin: '0 0 8px' }}>Recent day closes</h4>
                  <div className="tbl-scroll">
                    <table className="tbl">
                      <thead><tr><th>Date</th><th>Collected</th><th>Closing</th></tr></thead>
                      <tbody>{dayCloses.slice(0, 5).map((row:any) => (
                        <tr key={row.id}><td className="mono">{row.close_date}</td><td>{money(row.total_collected)}</td><td>{money(row.closing_balance)}</td></tr>
                      ))}</tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
          <div className="tbl-scroll">
            <table className="tbl">
              <thead><tr><th>Roll No</th><th>Name</th><th>Category</th><th>Billed</th><th>Paid</th><th>Balance</th><th>Status</th><th style={{ textAlign: 'right' }}>Actions</th></tr></thead>
              <tbody>
                {filteredInvoices.slice(0, 100).map((r: any) => (
                  <tr key={r.id} className={r.balance > 0 ? 'finance-row-due' : 'finance-row-paid'}>
                    <td className="mono">{r.roll_no}</td>
                    <td>{r.name}</td>
                    <td><span className="pill s-active">{r.fee_category || 'Uncategorised'}</span></td>
                    <td>{money(r.amount)}</td>
                    <td>{money(r.paid)}</td>
                    <td><b style={{ color: r.balance > 0 ? 'var(--rose)' : 'var(--teal)' }}>{money(r.balance)}</b></td>
                    <td><span className={`pill s-${r.status}`}>{r.status}</span></td>
                    <td style={{ textAlign: 'right' }}>
                      <div className="row-actions">
                        <button className="btn btn-sm btn-teal" disabled={!caps.record_payment || r.balance <= 0 || (r.accounts_settlement_required && user?.office_n !== 23)} onClick={() => { setModal({ kind: 'pay', inv: r, method: 'cash', reference: '' }); setAmount(String(r.balance)) }}>{r.balance <= 0 ? 'Settled' : r.accounts_settlement_required ? (user?.office_n === 23 ? 'Settle condonation' : 'Accounts settlement') : 'Record payment'}</button>
                        <button className="btn btn-sm btn-out" onClick={() => reviewInvoice(r)}>Review</button>
                        <button className="btn btn-sm btn-out" onClick={() => requestAdjustment(r)}>Adjust</button>
                        {user?.office_n === 22 && <button className="btn btn-sm btn-out" disabled={r.balance <= 0} onClick={() => requestWaiver(r)}>Recommend waiver</button>}
                        {user?.office_n === 23 && <button className="btn btn-sm btn-out" disabled={Number(r.paid || 0) <= 0} onClick={() => requestRefund(r)}>{Number(r.paid || 0) > 0 ? 'Refund' : 'No paid balance'}</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'payments' && (
        <div className="card finance-card">
          <div className="card-h"><div><h3>Payment records</h3><span className="hint">Confirmed payments stored in the database</span></div></div>
          {pendingPayments.length > 0 && <div className="card-pad"><h4>Pending verification / clearance</h4><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Student</th><th>Challan</th><th>Amount</th><th>Mode</th><th>Reference</th><th>Action</th></tr></thead><tbody>{pendingPayments.map((p:any) => <tr key={p.id}><td><b>{p.student}</b><small>{p.roll_no}</small></td><td className="mono">{p.challan_number || '—'}</td><td>{money(p.amount)}</td><td>{p.method}</td><td className="mono">{p.reference}</td><td><div className="row-actions">{p.status === 'pending_clearance' ? <><button className="btn btn-sm btn-brass" onClick={() => decideOffline(p, 'cleared')}>Mark cleared</button><button className="btn btn-sm btn-out" onClick={() => decideOffline(p, 'bounced')}>Bounce</button></> : <><button className="btn btn-sm btn-brass" onClick={() => decideOffline(p, 'verified')}>Verify</button><button className="btn btn-sm btn-out" onClick={() => decideOffline(p, 'rejected')}>Reject</button></>}</div></td></tr>)}</tbody></table></div></div>}
          <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Date</th><th>Roll No.</th><th>Student</th><th>Amount</th><th>Method</th><th>Payment reference</th></tr></thead><tbody>{data.payments?.length ? data.payments.map((p:any) => <tr key={p.id}><td>{p.at ? new Date(p.at).toLocaleString('en-IN') : '—'}</td><td className="mono">{p.roll_no}</td><td>{p.name}</td><td><b>{money(p.amount)}</b></td><td><span className="pill s-paid">{p.method}</span></td><td className="mono">{p.reference || '—'}</td></tr>) : <tr><td colSpan={6}><Empty text="No payment records yet." /></td></tr>}</tbody></table></div>
        </div>
      )}

      {tab === 'setup' && <FeeSetup canManage={user?.office_n === 22} onOpenApprovals={onOpenApprovals} />}

      {modal && (
        <Modal title="Record fee payment" onClose={() => setModal(null)}
          footer={<><button className="btn btn-out" onClick={() => setModal(null)}>Cancel</button>
            <button className="btn btn-brass" onClick={act}>Record payment</button></>}>
          <div className="form-row"><label>Student</label><div className="mono">{modal.inv.roll_no} · {modal.inv.name}</div></div>
          <div className="form-row"><label>Semester / invoice</label><div>{modal.inv.term || 'Not specified'}</div></div>
          <div className="form-row"><label>Payment method</label>
            <select className="select" value={modal.method || 'cash'} onChange={e => setModal({ ...modal, method: e.target.value })}>
              <option value="cash">Cash</option>
              <option value="cheque">Cheque</option>
              <option value="dd">DD</option>
              <option value="bank_transfer">Bank transfer</option>
              <option value="online">Online</option>
            </select>
          </div>
          <div className="form-row"><label>Amount (₹)</label>
            <input className="inp" type="number" value={amount} onChange={e => setAmount(e.target.value)} /></div>
          <div className="form-row"><label>Reference / receipt</label>
            <input className="inp" value={modal.reference || ''} onChange={e => setModal({ ...modal, reference: e.target.value })} placeholder="Cash receipt / cheque no / transaction ID" /></div>
          {modal.kind === 'waive' && <p className="hint">Waivers above your scope’s approval limit auto-escalate to the Vice-Chancellor per the approval matrix.</p>}
        </Modal>
      )}

      {reviewDraft && (
        <Modal title="Review invoice" onClose={() => setReviewDraft(null)}
          footer={<><button className="btn btn-out" onClick={() => setReviewDraft(null)}>Cancel</button>
            <button className="btn btn-brass" disabled={submittingReview} onClick={submitReview}>{submittingReview ? 'Saving...' : 'Save review'}</button></>}>
          <div className="form-row"><label>Student</label><div className="mono">{reviewDraft.invoice.roll_no} · {reviewDraft.invoice.name}</div></div>
          <div className="form-row"><label>Invoice</label><div>{reviewDraft.invoice.term || reviewDraft.invoice.id.slice(0, 8)}</div></div>
          <div className="form-row"><label>Decision</label>
            <select className="select" value={reviewDraft.decision} onChange={e => setReviewDraft({ ...reviewDraft, decision: e.target.value })}>
              <option value="approved">Approved</option>
              <option value="pending_review">Pending review</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
          <div className="form-row"><label>Remarks</label>
            <textarea className="inp" value={reviewDraft.remarks || ''} onChange={e => setReviewDraft({ ...reviewDraft, remarks: e.target.value })} placeholder="Add review notes or comments" rows={4} /></div>
        </Modal>
      )}

      {adjustmentDraft && (
        <Modal title="Request adjustment" onClose={() => setAdjustmentDraft(null)}
          footer={<><button className="btn btn-out" onClick={() => setAdjustmentDraft(null)}>Cancel</button>
            <button className="btn btn-brass" disabled={submittingAdjustment} onClick={submitAdjustment}>{submittingAdjustment ? 'Submitting...' : 'Submit adjustment'}</button></>}>
          <div className="form-row"><label>Student</label><div className="mono">{adjustmentDraft.invoice.roll_no} · {adjustmentDraft.invoice.name}</div></div>
          <div className="form-row"><label>Invoice</label><div>{adjustmentDraft.invoice.term || adjustmentDraft.invoice.id.slice(0, 8)}</div></div>
          <div className="form-row"><label>Adjustment type</label>
            <select className="select" value={adjustmentDraft.adjustment_type} onChange={e => setAdjustmentDraft({ ...adjustmentDraft, adjustment_type: e.target.value })}>
              <option value="credit">Credit</option>
              <option value="debit">Debit</option>
              <option value="refund">Refund</option>
            </select>
          </div>
          <div className="form-row"><label>Amount (₹)</label>
            <input className="inp" type="number" value={adjustmentDraft.amount} onChange={e => setAdjustmentDraft({ ...adjustmentDraft, amount: e.target.value })} placeholder="0" /></div>
          <div className="form-row"><label>Reason</label>
            <textarea className="inp" value={adjustmentDraft.reason || ''} onChange={e => setAdjustmentDraft({ ...adjustmentDraft, reason: e.target.value })} placeholder="Explain why this adjustment is needed" rows={4} /></div>
        </Modal>
      )}

      {refundDraft && (
        <Modal title="Request refund" onClose={() => setRefundDraft(null)}
          footer={<><button className="btn btn-out" onClick={() => setRefundDraft(null)}>Cancel</button>
            <button className="btn btn-brass" disabled={submittingRefund} onClick={submitRefundRequest}>{submittingRefund ? 'Submitting...' : 'Submit refund request'}</button></>}>
          <div className="form-row"><label>Student</label><div className="mono">{refundDraft.invoice.roll_no} · {refundDraft.invoice.name}</div></div>
          <div className="form-row"><label>Invoice</label><div>{refundDraft.invoice.term || refundDraft.invoice.id.slice(0, 8)}</div></div>
          <div className="form-row"><label>Paid amount</label><div>{money(Number(refundDraft.invoice.paid || 0))}</div></div>
          <div className="form-row"><label>Refund amount (₹)</label>
            <input className="inp" type="number" value={refundDraft.amount} onChange={e => setRefundDraft({ ...refundDraft, amount: e.target.value })} /></div>
          <div className="form-row"><label>Reason</label>
            <textarea className="inp" value={refundDraft.reason} onChange={e => setRefundDraft({ ...refundDraft, reason: e.target.value })} placeholder="Enter the reason for this refund" rows={4} /></div>
          <p className="hint">Refund requests are created in pending approval state and can be approved or executed from the refund queue.</p>
        </Modal>
      )}
      {waiverDraft && (
        <Modal title="Recommend fee waiver" onClose={() => setWaiverDraft(null)}
          footer={<><button className="btn btn-out" onClick={() => setWaiverDraft(null)}>Cancel</button>
            <button className="btn btn-brass" disabled={submittingWaiver} onClick={submitWaiverRequest}>{submittingWaiver ? 'Submitting...' : 'Send to Principal'}</button></>}>
          <div className="form-row"><label>Student</label><div className="mono">{waiverDraft.invoice.roll_no} · {waiverDraft.invoice.name}</div></div>
          <div className="form-row"><label>Invoice</label><div>{waiverDraft.invoice.term || waiverDraft.invoice.id.slice(0, 8)}</div></div>
          <div className="form-row"><label>Unpaid balance</label><div>{money(Number(waiverDraft.invoice.balance ?? 0))}</div></div>
          <div className="form-row"><label>Waiver amount (₹)</label><input className="inp" type="number" value={waiverDraft.amount} onChange={e => setWaiverDraft({ ...waiverDraft, amount: e.target.value })} /></div>
          <div className="form-row"><label>Documented reason</label><textarea className="inp" value={waiverDraft.reason} onChange={e => setWaiverDraft({ ...waiverDraft, reason: e.target.value })} placeholder="Scholarship basis, approval reference, and supporting context" rows={4} /></div>
          <p className="hint">This records your recommendation, sends the decision to the Principal’s approval inbox, and lets Accounts apply the approved amount exactly once.</p>
        </Modal>
      )}
      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}

export function PrincipalFinance({ onOpenApprovals }: { onOpenApprovals: () => void }) {
  const [tab, setTab] = useState<'fees' | 'budget'>('fees')
  const [data, setData] = useState<any>(null)
  const [budget, setBudget] = useState<any>(null)

  function load() {
    api.invoices().then(setData).catch(() => {})
    api.budget().then(setBudget).catch(() => {})
  }
  useEffect(() => { load() }, [])

  if (!data) return <Spinner />
  const summary = data.summary || { total_billed: 0, total_collected: 0, outstanding: 0 }
  const feesUnavailable = data.data_status === 'unavailable'
  const collectionRate = Math.round(100 * Number(summary.total_collected || 0) / (Number(summary.total_billed || 0) || 1))

  return <div className="fade-in principal-finance">
    <PageHead title="Finance" sub="Campus financial oversight. Financial approvals are decided from the governed approval inbox; Accounts executes transactions." />
    {feesUnavailable ? <div className="empty">{data.reason || 'Campus-scoped invoice data is unavailable.'}</div> : <div className="kpi-row principal-finance-kpis">
      <div className="kpi"><div className="kpi-v">{money(summary.total_billed)}</div><div className="kpi-l">Total billed</div></div>
      <div className="kpi"><div className="kpi-v" style={{ color: 'var(--teal)' }}>{money(summary.total_collected)}</div><div className="kpi-l">Collected</div></div>
      <div className="kpi"><div className="kpi-v" style={{ color: 'var(--rose)' }}>{money(summary.outstanding)}</div><div className="kpi-l">Outstanding</div></div>
      <div className="kpi"><div className="kpi-v">{collectionRate}%</div><div className="kpi-l">Collection rate</div></div>
    </div>}
    <div className="row-actions" style={{ marginBottom: 12 }}>
      <button className="btn btn-brass" onClick={onOpenApprovals}>Open finance approvals</button>
    </div>
    <div className="tabs principal-finance-tabs">
      <button className={`tab ${tab === 'fees' ? 'on' : ''}`} onClick={() => setTab('fees')}>Fee invoices</button>
      <button className={`tab ${tab === 'budget' ? 'on' : ''}`} onClick={() => setTab('budget')}>Budget</button>
    </div>
    {tab === 'fees' && !feesUnavailable && <div className="card principal-finance-card"><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Roll No</th><th>Name</th><th>Billed</th><th>Paid</th><th>Balance</th><th>Status</th></tr></thead><tbody>{(data.invoices || []).slice(0, 80).map((invoice: any) => <tr key={invoice.id}><td className="mono">{invoice.roll_no}</td><td>{invoice.name}</td><td>{money(invoice.amount)}</td><td>{money(invoice.paid)}</td><td><b style={{ color: invoice.balance > 0 ? 'var(--rose)' : 'var(--teal)' }}>{money(invoice.balance)}</b></td><td><span className={`pill s-${invoice.status}`}>{invoice.status}</span></td></tr>)}</tbody></table></div></div>}
    {tab === 'budget' && budget && <div className="card principal-finance-card"><div className="card-pad">{(budget.budget || []).map((item: any) => { const percent = Math.round(100 * Number(item.spent || 0) / (Number(item.allocated || 0) || 1)); return <div className="budget-row" key={item.category}><div className="budget-head"><b>{item.category}</b><span>{money(item.spent)} / {money(item.allocated)}</span></div><div className="bar-track"><div className="bar-fill" style={{ width: `${percent}%`, background: percent > 85 ? 'var(--rose)' : 'var(--brass)' }} /></div></div> })}</div></div>}
  </div>
}

function AccountsOfficeOverview({ totalCollected, todayCollected, pendingVerification, refundsReady, vendorDue, reconciliation, paymentModes, paymentRows, todayPayments, onOpen }: any) {
  const modeRows = Object.entries(paymentModes).sort(([, left]: any, [, right]: any) => right - left)
  const maxMode = Math.max(1, ...modeRows.map(([, value]: any) => Number(value)))
  const recentActivity = todayPayments.slice(0, 5)
  const formatAmount = (value: number) => `₹${Number(value || 0).toLocaleString('en-IN')}`

  return (
    <section className="accounts-dashboard fade-in">
      <header className="accounts-dashboard-head">
        <div><span className="accounts-eyebrow">Accounts Office</span><h2>Dashboard</h2><p>Live collections, verification queues, reconciliation, and payment execution.</p></div>
        <span className="accounts-live"><i /> Live database data</span>
      </header>

      <div className="accounts-kpis">
        <article><span className="accounts-kpi-icon green">₹</span><div><small>Collected today</small><b>{formatAmount(todayCollected)}</b><em>{todayPayments.length} recorded payments</em></div></article>
        <article><span className="accounts-kpi-icon blue">▣</span><div><small>Total collected</small><b>{formatAmount(totalCollected)}</b><em>Confirmed fee payments</em></div></article>
        <article><span className="accounts-kpi-icon orange">◷</span><div><small>Pending verification</small><b>{pendingVerification}</b><em>Payments awaiting clearance</em></div></article>
        <article><span className="accounts-kpi-icon purple">↗</span><div><small>Unmatched entries</small><b>{reconciliation ? Math.max(0, Number(reconciliation.total_adjustments || 0)) : '—'}</b><em>From latest reconciliation</em></div></article>
        <article><span className="accounts-kpi-icon pink">↩</span><div><small>Refunds ready</small><b>{refundsReady}</b><em>Approved for execution</em></div></article>
        <article><span className="accounts-kpi-icon gold">▰</span><div><small>Vendor payments due</small><b>{vendorDue.length}</b><em>Awaiting approval or payment</em></div></article>
      </div>

      <div className="accounts-dashboard-grid accounts-dashboard-grid-top">
        <section className="accounts-panel"><header><h3>Today's collection by payment mode</h3><span>{formatAmount(todayCollected)} total</span></header><div className="accounts-mode-list">{modeRows.length ? modeRows.map(([method, value]: any) => <div className="accounts-mode-row" key={method}><span>{method}</span><div><i style={{ width: `${(Number(value) / maxMode) * 100}%` }} /></div><b>{formatAmount(value)}</b></div>) : <Empty text="No payments recorded today." />}</div></section>
        <section className="accounts-panel"><header><h3>Pending verification</h3><button onClick={() => onOpen('payments')}>View all →</button></header><div className="accounts-queue"><div><span>Bank transfers / UTR pending</span><b>{paymentRowsCount(paymentRowsByStatus(paymentRows, 'pending_verification'))}</b></div><div><span>Cheques and DDs pending</span><b>{paymentRowsCount(paymentRowsByStatus(paymentRows, 'pending_clearance'))}</b></div><div><span>All pending records</span><b>{pendingVerification}</b></div></div></section>
        <section className="accounts-panel"><header><h3>Reconciliation status</h3><button onClick={() => onOpen('fees')}>View details →</button></header><div className="accounts-recon"><strong>{reconciliation?.status || 'Not started'}</strong><span>{reconciliation ? formatAmount(reconciliation.total_collected) : formatAmount(totalCollected)} collected in latest close</span><small>{reconciliation?.period_end ? `Closed ${String(reconciliation.period_end).slice(0, 10)}` : 'No reconciliation has been closed yet'}</small></div></section>
      </div>

      <div className="accounts-dashboard-grid accounts-dashboard-grid-bottom">
        <section className="accounts-panel"><header><h3>Execution queue</h3><button onClick={() => onOpen('fees')}>Open finance →</button></header><div className="accounts-execution"><button onClick={() => onOpen('payments')}><b>{pendingVerification}</b><span>Payment verification</span></button><button onClick={() => onOpen('fees')}><b>{vendorDue.length}</b><span>Vendor payments due</span></button><button onClick={() => onOpen('fees')}><b>{refundsReady}</b><span>Refunds ready</span></button></div></section>
        <section className="accounts-panel"><header><h3>Recent activity</h3><span>Today</span></header><div className="accounts-activity">{recentActivity.length ? recentActivity.map((row: any) => <div key={row.id}><time>{String(row.at || '').slice(11, 16) || '—'}</time><span>{row.name || row.roll_no || 'Student payment'}<small>{row.method || 'payment'} · {row.reference || 'No reference'}</small></span><b>{formatAmount(row.amount)}</b></div>) : <Empty text="No activity recorded today." />}</div></section>
        <section className="accounts-panel"><header><h3>Quick actions</h3></header><div className="accounts-actions"><button onClick={() => onOpen('students')}>▣<span>Record payment</span></button><button onClick={() => onOpen('payments')}>✓<span>Verify payment</span></button><button onClick={() => onOpen('fees')}>↔<span>Reconcile</span></button><button onClick={() => onOpen('payroll')}>₹<span>Payroll</span></button></div></section>
      </div>
    </section>
  )
}

function paymentRowsByStatus(rows: any[], status: string) { return rows.filter((row: any) => row.status === status) }
function paymentRowsCount(rows: any[]) { return rows.length }

const blankHead = { code: '', name: '', category: 'OTHER', description: '', is_mandatory: true, display_order: 0 }
const blankLine = { fee_head_id: '', fee_head_category: 'all', amount: '', installment_no: 1, installment_name: '', due_date: '', is_mandatory: true, description: '' }

function FeeSetup({ canManage, onOpenApprovals }: { canManage: boolean; onOpenApprovals: () => void }) {
  const [view, setView] = useState<'structures' | 'heads'>('structures')
  const [heads, setHeads] = useState<any[]>([]), [structures, setStructures] = useState<any[]>([]), [refs, setRefs] = useState<any>(null)
  const [head, setHead] = useState<any>(null), [draft, setDraft] = useState<any>(null), [error, setError] = useState(''), [saving, setSaving] = useState(false)
  const [affected, setAffected] = useState<any>(null)
  const [impact, setImpact] = useState<any>(null)
  const [structureDetail, setStructureDetail] = useState<any>(null)
  const [submissionReview, setSubmissionReview] = useState<any>(null)
  const [publishReview, setPublishReview] = useState<any>(null)
  const [loadingStructureId, setLoadingStructureId] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [affectedSearch, setAffectedSearch] = useState('')
  const load = () => { api.feeHeads(true).then(r => setHeads(r.heads)).catch(e => setError(e.message)); api.feeStructures().then(r => setStructures(r.structures)).catch(e => setError(e.message)); api.feeReferenceData().then(setRefs).catch(e => setError(e.message)) }
  useEffect(() => {
    load()
    // Approval happens in the Principal workspace, often while Finance remains
    // open in another tab. Refresh on focus and periodically so APPROVED rows
    // expose Publish / Apply without requiring a manual page reload.
    window.addEventListener('focus', load)
    const refreshTimer = window.setInterval(load, 15000)
    return () => {
      window.removeEventListener('focus', load)
      window.clearInterval(refreshTimer)
    }
  }, [])
  async function saveHead() { try { setSaving(true); if (head.id) await api.updateFeeHead(head.id, head); else await api.createFeeHead(head); setHead(null); load() } catch (e:any) { setError(e.message) } finally { setSaving(false) } }
  async function toggle(h:any) { if (!confirm(`${h.is_active ? 'Deactivate' : 'Activate'} ${h.name}?`)) return; try { await api.setFeeHeadStatus(h.id, !h.is_active); load() } catch (e:any) { setError(e.message) } }
  async function saveDraft() {
    const required = [
      ['Academic Year', draft.academic_year_id], ['Semester', draft.semester_id],
      ['Campus', draft.campus_id], ['Program', draft.program_id],
      ['Batch', draft.batch_id], ['Student Type', draft.student_type_id],
    ]
    const missing = required.filter(([, value]) => !value).map(([label]) => label)
    if (missing.length) {
      setError(`Select: ${missing.join(', ')}.`)
      return
    }
    if (!draft.lines.length) {
      setError('Add at least one fee line.')
      return
    }
    for (let index = 0; index < draft.lines.length; index++) {
      const line = draft.lines[index]
      if (!line.fee_head_id) {
        setError(`Select a Fee Head in fee line ${index + 1}.`)
        return
      }
      if (!Number.isFinite(Number(line.amount)) || Number(line.amount) <= 0) {
        setError(`Enter an amount greater than zero in fee line ${index + 1}.`)
        return
      }
      if (!Number.isInteger(Number(line.installment_no)) || Number(line.installment_no) < 1) {
        setError(`Enter a valid installment number in fee line ${index + 1}.`)
        return
      }
    }
    const lineKeys = draft.lines.map((line:any) => `${line.fee_head_id}:${line.installment_no}`)
    if (new Set(lineKeys).size !== lineKeys.length) {
      setError('The same Fee Head and installment number cannot be added twice.')
      return
    }
    try {
      setSaving(true)
      setError('')
      const payload = {...draft, effective_from: draft.effective_from || null, effective_to: draft.effective_to || null, lines: draft.lines.map(({ fee_head_category, ...line }:any) => ({...line, amount: Number(line.amount), due_date: line.due_date || null}))}
      if (draft.id) await api.updateFeeStructure(draft.id, payload)
      else await api.createFeeStructure(payload)
      setDraft(null)
      load()
    } catch (e:any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }
  async function publish(id:string) {
    try {
      setSaving(true)
      const result = await api.publishFeeStructure(id)
      setPublishReview(null)
      const accounts = result.student_accounts_created ? ` ${result.student_accounts_created} student login account(s) created.` : ''
      setError(`Published: ${result.invoices_created} invoice(s) created for ${result.matched_students} student(s).${accounts}`)
      setAffectedSearch('')
      // Show Finance exactly which students received invoices as soon as the
      // publish operation completes; the row also retains this list afterward.
      setAffected(await api.feeStructureAffectedStudents(id))
      load()
    } catch (e:any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }
  async function submit(id:string) { try { setSaving(true); await api.submitFeeStructure(id); setSubmissionReview(null); setError('Fee structure submitted to the campus Principal for approval.'); load() } catch (e:any) { setError(e.message) } finally { setSaving(false) } }
  async function showAffected(id:string) { try { setAffectedSearch(''); setAffected(await api.feeStructureAffectedStudents(id)) } catch (e:any) { setError(e.message) } }
  async function showImpact(id:string) { try { setImpact(await api.feeStructureImpactPreview(id)) } catch (e:any) { setError(e.message) } }
  async function openPublishReview(id:string) {
    try {
      setLoadingStructureId(id)
      setError('')
      setPublishReview(await api.feeStructureImpactPreview(id))
    } catch (e:any) {
      setError(e.message || 'Could not prepare the publishing review')
    } finally {
      setLoadingStructureId('')
    }
  }
  async function openStructure(id:string) {
    try {
      setLoadingStructureId(id)
      setError('')
      const result = await api.feeStructure(id)
      const structure = result.structure
      if (['DRAFT', 'RETURNED'].includes(structure.status)) {
        setDraft({...structure, lines: (structure.lines || []).map((line:any) => ({...line, amount: String(line.amount), due_date: line.due_date || ''}))})
      } else {
        setStructureDetail(structure)
      }
    } catch (e:any) {
      setError(e.message || 'Could not open the fee structure')
    } finally {
      setLoadingStructureId('')
    }
  }
  const gross = (draft?.lines || []).reduce((sum:number, x:any) => sum + (Number(x.amount) || 0), 0)
  const feeHeadCategories = [...new Set(heads.filter(h => h.is_active).map(h => h.category || 'Uncategorised'))].sort()
  const structureCounts = structures.reduce((counts:any, row:any) => ({...counts, [row.status]: (counts[row.status] || 0) + 1}), {})
  const filteredStructures = statusFilter === 'all' ? structures : structures.filter(row => row.status === statusFilter)
  const affectedStudents = (affected?.students || []).filter((student:any) => {
    const query = affectedSearch.trim().toLowerCase()
    return !query || student.roll_no.toLowerCase().includes(query) || student.name.toLowerCase().includes(query)
  })
  if (!refs) return <Spinner />
  return <div className="card fee-management-card"><div className="card-h fee-management-head"><div><span className="fee-management-eyebrow">Finance configuration</span><h3>Fee setup & structures</h3><span className="hint">{canManage ? 'Configure fee heads, prepare a structure, obtain Principal approval, then publish student invoices.' : 'Read-only fee setup. Structures submitted for your decision appear in Approvals.'}</span></div><div className="row-actions">{canManage && (view === 'heads' ? <button className="btn btn-crimson" onClick={() => setHead({...blankHead})}>+ Add fee head</button> : <button className="btn btn-crimson" onClick={() => {setError('');setDraft(newDraft(heads.find(h=>h.is_active)?.id || ''))}}>+ Create structure</button>)}{!canManage && <button className="btn btn-brass" onClick={onOpenApprovals}>Open Approvals</button>}</div></div>
    {view === 'structures' && <div className="card-pad" style={{paddingTop:0}}><div className="kpi-row"><div className="kpi"><div className="kpi-v">{structureCounts.DRAFT || 0}</div><div className="kpi-l">Drafts</div></div><div className="kpi"><div className="kpi-v">{structureCounts.SUBMITTED || 0}</div><div className="kpi-l">With Principal</div></div><div className="kpi"><div className="kpi-v">{structureCounts.APPROVED || 0}</div><div className="kpi-l">Ready to publish</div></div><div className="kpi"><div className="kpi-v">{structureCounts.PUBLISHED || 0}</div><div className="kpi-l">Live structures</div></div></div><p className="hint" style={{margin:'8px 0 0'}}>Workflow: Fee heads → draft structure → Principal approval → Finance publish → invoices and challans.</p></div>}
    <div className="fee-management-toolbar"><div><b>{view === 'heads' ? `${heads.length} fee heads` : `${filteredStructures.length} of ${structures.length} fee structures`}</b><span>{view === 'heads' ? 'Reusable fee components' : 'Status, approval stage, and controlled publishing'}</span></div><div className="fee-view-switch"><button className={view === 'structures' ? 'on' : ''} onClick={() => setView('structures')}>Structures</button><button className={view === 'heads' ? 'on' : ''} onClick={() => setView('heads')}>Fee heads</button></div></div>
    {error && <p className="hint" style={{color:'var(--rose)', padding:'0 18px'}}>{error}</p>}
    {view === 'structures' && <div className="card-pad" style={{paddingTop:0}}><label className="finance-search"><span>Workflow status</span><select className="select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="all">All statuses</option>{['DRAFT', 'SUBMITTED', 'RETURNED', 'APPROVED', 'PUBLISHED', 'REJECTED'].map(status => <option key={status} value={status}>{status}</option>)}</select></label></div>}
    {view === 'heads' ? <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Code</th><th>Name</th><th>Category</th><th>Mandatory</th><th>Status</th>{canManage && <th/>}</tr></thead><tbody>{heads.map(h => <tr key={h.id}><td className="mono">{h.code}</td><td>{h.name}</td><td>{h.category}</td><td>{h.is_mandatory ? 'Yes' : 'No'}</td><td><span className={`pill s-${h.is_active ? 'active' : 'inactive'}`}>{h.is_active ? 'Active' : 'Inactive'}</span></td>{canManage && <td><div className="row-actions"><button className="btn btn-sm btn-out" onClick={() => setHead({...h})}>Edit</button><button className="btn btn-sm btn-out" onClick={() => toggle(h)}>{h.is_active ? 'Deactivate' : 'Activate'}</button></div></td>}</tr>)}</tbody></table></div> : <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Structure</th><th>Academic context</th><th>Version</th><th>Gross Fee</th><th>Workflow status</th><th>Updated</th>{canManage && <th/>}</tr></thead><tbody>{filteredStructures.length ? filteredStructures.map(x => <tr key={x.id}><td><b>{x.name}</b><small className="mono">{x.code}</small></td><td>{x.academic_year} · {x.semester}<small>{x.campus} · {x.program} · Batch {x.batch} · {x.student_type}</small></td><td>V{x.version}</td><td>{money(Number(x.gross_total))}</td><td><span className={`pill s-${String(x.status).toLowerCase()}`}>{x.status === 'SUBMITTED' ? 'Awaiting Principal' : x.status === 'RETURNED' ? 'Returned for revision' : x.status}</span></td><td>{x.updated_at ? new Date(x.updated_at).toLocaleDateString('en-IN') : '—'}</td>{canManage && <td><div className="row-actions"><button className="btn btn-sm btn-out" onClick={() => showImpact(x.id)}>Impact</button><button className="btn btn-sm btn-out" disabled={loadingStructureId === x.id} onClick={() => openStructure(x.id)}>{loadingStructureId === x.id ? 'Opening…' : ['DRAFT', 'RETURNED'].includes(x.status) ? (x.status === 'RETURNED' ? 'Revise' : 'View / Edit') : 'View details'}</button>{x.status === 'DRAFT' && <button className="btn btn-sm btn-brass" disabled={saving} onClick={() => setSubmissionReview(x)}>Send to Principal</button>}{x.status === 'APPROVED' && <button className="btn btn-sm btn-brass" disabled={loadingStructureId === x.id || saving} onClick={() => openPublishReview(x.id)}>{loadingStructureId === x.id ? 'Preparing…' : 'Publish / Apply'}</button>}{x.status === 'PUBLISHED' && <button className="btn btn-sm btn-out" onClick={() => showAffected(x.id)}>Affected Students</button>}</div></td>}</tr>) : <tr><td colSpan={canManage ? 7 : 6}><Empty text={structures.length ? 'No structures match this status.' : 'No fee structures yet.'} /></td></tr>}</tbody></table></div>}
    {head && <Modal title={head.id ? 'Edit Fee Head' : 'Add Fee Head'} onClose={() => setHead(null)} footer={<><button className="btn btn-out" onClick={() => setHead(null)}>Cancel</button><button className="btn btn-crimson" disabled={saving} onClick={saveHead}>{saving ? 'Saving...' : 'Save'}</button></>}><div className="grid-2"><Field label="Code"><input className="inp" value={head.code} onChange={e=>setHead({...head,code:e.target.value})}/></Field><Field label="Name"><input className="inp" value={head.name} onChange={e=>setHead({...head,name:e.target.value})}/></Field><Field label="Category"><input className="inp" value={head.category} onChange={e=>setHead({...head,category:e.target.value})}/></Field><Field label="Display order"><input className="inp" type="number" value={head.display_order} onChange={e=>setHead({...head,display_order:Number(e.target.value)})}/></Field></div><label><input type="checkbox" checked={head.is_mandatory} onChange={e=>setHead({...head,is_mandatory:e.target.checked})}/> Mandatory</label><Field label="Description"><textarea className="inp" value={head.description} onChange={e=>setHead({...head,description:e.target.value})}/></Field></Modal>}
    {submissionReview && <Modal title="Send fee structure to Principal" onClose={() => !saving && setSubmissionReview(null)} footer={<><button className="btn btn-out" disabled={saving} onClick={() => setSubmissionReview(null)}>Keep as draft</button><button className="btn btn-brass" disabled={saving} onClick={() => submit(submissionReview.id)}>{saving ? 'Sending…' : 'Confirm and send'}</button></>}><p className="hint">Review this controlled handoff before the structure is locked for Finance editing.</p><div className="grid-2"><Field label="Structure"><div><b>{submissionReview.name}</b><small className="mono">{submissionReview.code}</small></div></Field><Field label="Total fee"><div><b>{money(Number(submissionReview.gross_total))}</b></div></Field><Field label="Academic context"><div>{submissionReview.academic_year} · {submissionReview.semester}</div></Field><Field label="Applicable students"><div>{submissionReview.campus} · {submissionReview.program}<small>Batch {submissionReview.batch} · {submissionReview.student_type}</small></div></Field></div><div className="fee-auto-note"><b>Next workflow step</b><span>The selected campus Principal receives this structure in My Approvals. Finance can publish and create invoices only after approval.</span></div><p className="hint" style={{marginTop:16}}>Submitting locks the current fee lines and amounts. If the Principal returns it, you can revise and resubmit it.</p></Modal>}
    {publishReview && <Modal title="Publish and apply fee structure" onClose={() => !saving && setPublishReview(null)} footer={<><button className="btn btn-out" disabled={saving} onClick={() => setPublishReview(null)}>Cancel</button><button className="btn btn-brass" disabled={saving} onClick={() => publish(publishReview.structure.id)}>{saving ? 'Publishing…' : 'Confirm publish and apply'}</button></>}><p className="hint">This structure has Principal approval and is ready to create live student invoices.</p><div className="grid-2"><Field label="Structure"><div><b>{publishReview.structure.name}</b><small className="mono">{publishReview.structure.code}</small></div></Field><Field label="Fee per student"><div><b>{money(Number(publishReview.gross_total))}</b></div></Field><Field label="Eligible students"><div><b>{publishReview.eligible_students}</b></div></Field><Field label="Invoice impact"><div><b>{publishReview.new_invoices_if_published}</b><small>{publishReview.projected_invoices} total projected invoice(s)</small></div></Field></div><div className="fee-auto-note"><b>Release control</b><span>Publishing applies the approved fee lines only to the selected campus, programme, batch, and student type. Existing linked invoices are retained, so a retry cannot duplicate billing.</span></div><p className="hint" style={{marginTop:16}}>After publishing, Finance can review the affected students and Accounts can collect against the generated invoices.</p></Modal>}
    {structureDetail && <Modal title="Fee structure details" onClose={() => setStructureDetail(null)} footer={<button className="btn btn-out" onClick={() => setStructureDetail(null)}>Close</button>}><p className="hint">{structureDetail.name} · {structureDetail.code || 'Legacy structure'} · <b>{structureDetail.status}</b></p><div className="grid-2"><Field label="Academic context"><div>{structureDetail.academic_year || '—'} · {structureDetail.semester || '—'}</div></Field><Field label="Applicability"><div>{structureDetail.campus || '—'} · {structureDetail.program || '—'} · Batch {structureDetail.batch || '—'} · {structureDetail.student_type || '—'}</div></Field></div><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Fee head</th><th>Installment</th><th>Due date</th><th>Amount</th></tr></thead><tbody>{(structureDetail.lines || []).length ? structureDetail.lines.map((line:any) => <tr key={line.id}><td>{line.fee_head_name || line.fee_head_code || '—'}</td><td>{line.installment_no}</td><td>{line.due_date || '—'}</td><td>{money(Number(line.amount))}</td></tr>) : <tr><td colSpan={4}><Empty text="This legacy structure has no editable fee-line records." /></td></tr>}</tbody></table></div></Modal>}
    {impact && <Modal title="Fee structure impact preview" onClose={() => setImpact(null)} footer={<button className="btn btn-out" onClick={() => setImpact(null)}>Close</button>}><p className="hint">{impact.structure.name} · {impact.structure.campus} · {impact.structure.program}</p><div className="kpi-row"><div className="kpi"><div className="kpi-v">{impact.eligible_students}</div><div className="kpi-l">Eligible students</div></div><div className="kpi"><div className="kpi-v">{impact.fee_lines}</div><div className="kpi-l">Fee lines</div></div><div className="kpi"><div className="kpi-v">{impact.projected_invoices}</div><div className="kpi-l">Projected invoices</div></div><div className="kpi"><div className="kpi-v">{money(impact.gross_total)}</div><div className="kpi-l">Fee per student</div></div></div><p className="hint" style={{marginTop:16}}>Publishing will create {impact.new_invoices_if_published} new invoice(s). Existing linked invoices are retained, so retries do not duplicate billing.</p></Modal>}
    {affected && <Modal title={`Affected Students (${affected.student_count})`} onClose={() => setAffected(null)} footer={<button className="btn btn-out" onClick={() => setAffected(null)}>Close</button>}><p className="hint">{affected.structure.name} · {affected.invoice_count} invoice(s) created</p><div className="affected-students-tools"><input className="inp" value={affectedSearch} onChange={e => setAffectedSearch(e.target.value)} placeholder="Search by roll number or student name" /><span>{affectedStudents.length} of {affected.student_count} students</span></div><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Roll No.</th><th>Student</th><th>Section</th><th>Invoices</th><th>Billed</th><th>Paid</th><th>Balance</th><th>Status</th></tr></thead><tbody>{affectedStudents.length ? affectedStudents.map((student:any) => <tr key={student.student_id}><td className="mono">{student.roll_no}</td><td><b>{student.name}</b><small>{student.email || '—'}</small></td><td>{student.section}</td><td>{student.invoice_count}</td><td>{money(student.invoiced)}</td><td>{money(student.paid)}</td><td>{money(student.balance)}</td><td><span className={`pill s-${student.status}`}>{student.status}</span></td></tr>) : <tr><td colSpan={8}><Empty text="No student matches this search." /></td></tr>}</tbody></table></div></Modal>}
    {draft && <Modal className="fee-structure-modal" title={draft.id ? 'Edit Draft Fee Structure' : 'Create Fee Structure'} onClose={() => setDraft(null)} footer={<><button className="btn btn-out" onClick={() => setDraft(null)}>Cancel</button><button className="btn btn-crimson" disabled={saving} onClick={saveDraft}>{saving ? 'Saving...' : 'Save Draft'}</button></>}>{error && <p className="hint" style={{color:'var(--rose)', marginBottom:12}}>{error}</p>}<div className="grid-2"><Select label="Academic Year" value={draft.academic_year_id} rows={refs.academic_years} onChange={(v:string)=>setDraft({...draft,academic_year_id:v,semester_id:''})}/><Select label="Semester" value={draft.semester_id} rows={refs.semesters.filter((x:any)=>x.academic_year_id===draft.academic_year_id)} onChange={(v:string)=>setDraft({...draft,semester_id:v})}/><Select label="Campus" value={draft.campus_id} rows={refs.campuses} onChange={(v:string)=>setDraft({...draft,campus_id:v})}/><Select label="Program" value={draft.program_id} rows={refs.programs} onChange={(v:string)=>setDraft({...draft,program_id:v})}/><Select label="Batch" value={draft.batch_id} rows={refs.batches} onChange={(v:string)=>setDraft({...draft,batch_id:v})}/><Select label="Student Type" value={draft.student_type_id} rows={refs.student_types} onChange={(v:string)=>setDraft({...draft,student_type_id:v})}/><div className="fee-auto-note"><b>Structure identity</b><span>Name and code are generated automatically from the selected academic context and student type.</span></div></div><h4>Fee Lines</h4>{draft.lines.map((line:any, i:number) => <div className="grid-2" key={line.id || i}><Field label="Fee Head Category"><select className="select" value={line.fee_head_category || 'all'} onChange={e=>{setError('');changeFeeHeadCategory(setDraft,draft,heads,i,e.target.value)}}><option value="all">All categories</option>{feeHeadCategories.map(category => <option key={category} value={category}>{category}</option>)}</select></Field><Select label="Fee Head *" value={line.fee_head_id} rows={heads.filter(h=>h.is_active && ((line.fee_head_category || 'all') === 'all' || h.category === line.fee_head_category))} onChange={(v:string)=>{setError('');changeLine(setDraft,draft,i,'fee_head_id',v)}}/><Field label="Amount *"><input className="inp" type="number" min="1" value={line.amount} onChange={e=>{setError('');changeLine(setDraft,draft,i,'amount',e.target.value)}}/></Field><Field label="Installment #"><input className="inp" type="number" min="1" value={line.installment_no} onChange={e=>{setError('');changeLine(setDraft,draft,i,'installment_no',Number(e.target.value))}}/></Field><Field label="Due Date"><input className="inp" type="date" value={line.due_date} onChange={e=>changeLine(setDraft,draft,i,'due_date',e.target.value)}/></Field><button className="btn btn-sm btn-out" onClick={()=>{if(confirm('Remove this fee line?')) setDraft({...draft,lines:draft.lines.filter((_:any,n:number)=>n!==i)})}}>Remove line</button></div>)}<button className="btn btn-out" onClick={()=>{setError('');setDraft({...draft,lines:[...draft.lines,{...blankLine}]})}}>+ Add Fee Line</button><div className="kpi-row" style={{marginTop:16}}><div className="kpi"><div className="kpi-v">{new Set(draft.lines.map((x:any)=>x.fee_head_id).filter(Boolean)).size}</div><div className="kpi-l">Fee Heads</div></div><div className="kpi"><div className="kpi-v">{draft.lines.length}</div><div className="kpi-l">Installments</div></div><div className="kpi"><div className="kpi-v">{money(gross)}</div><div className="kpi-l">Gross Fee</div></div></div></Modal>}
  </div>
}

function Field({label, children}:any) { return <div className="form-row"><label>{label}</label>{children}</div> }
function Select({label, value, rows, onChange}:any) { return <Field label={label}><select className="select" value={value || ''} onChange={e=>onChange(e.target.value)}><option value="">Select {label}</option>{rows.map((x:any)=><option key={x.id} value={x.id}>{x.name}{x.code ? ` (${x.code})` : ''}</option>)}</select></Field> }
function changeLine(set:any, draft:any, index:number, key:string, value:any) { const lines=draft.lines.map((x:any,i:number)=>i===index?{...x,[key]:value}:x); set({...draft,lines}) }
function changeFeeHeadCategory(set:any, draft:any, heads:any[], index:number, category:string) { const lines=draft.lines.map((line:any, i:number) => { if (i !== index) return line; const selected = heads.find(head => head.id === line.fee_head_id); return {...line, fee_head_category: category, fee_head_id: category === 'all' || selected?.category === category ? line.fee_head_id : ''} }); set({...draft, lines}) }
function newDraft(defaultFeeHeadId = '') { return {name:'', code:'', academic_year_id:'', semester_id:'', campus_id:'', program_id:'', batch_id:'', student_type_id:'', version:1, effective_from:'', effective_to:'', description:'', notes:'', lines:[{...blankLine, fee_head_id:defaultFeeHeadId}]} }
