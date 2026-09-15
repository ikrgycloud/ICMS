import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

const money = (value: number) => `₹${Number(value || 0).toLocaleString('en-IN')}`

export default function FacultyPayroll() {
  const [data, setData] = useState<any>(null)
  const [selectedMonth, setSelectedMonth] = useState('')

  useEffect(() => {
    api.facultyPayroll(selectedMonth || undefined).then(setData).catch(() => setData({ error: true }))
  }, [selectedMonth])

  if (!data) return <Spinner />
  if (data.error) return <Empty icon="!" text="Payroll details could not be loaded." />
  if (data.payroll_configured === false) return <Empty icon="!" text="Your payroll profile has not been configured yet. Please contact Human Resources." />

  const profile = data.profile || {}
  const entry = data.entry || {}
  const run = data.run || {}
  const payment = data.payment || {}
  const lastPaidReceipt = data.last_paid_receipt
  const earnings = data.earnings || []
  const deductions = data.deductions || []

  const gross = Number(entry.gross_salary || 0)
  const totalDeductions = Number(entry.total_deductions || 0)
  const net = Number(entry.net_salary || gross - totalDeductions)

  const paymentDate = run.payment_date || payment.posted_at || '—'
  const paymentStatus = entry.payment_status || 'pending'
  const isPaid = paymentStatus === 'paid'

  return (
    <main className="faculty-payroll fade-in">
      <section className="faculty-payroll-head">
        <div>
          <h1>Payroll</h1>
          <p>Your salary statement, earnings, deductions, and payment status.</p>
        </div>
        <div className="faculty-payroll-actions">
          <label>
            <span>Pay period</span>
            <select value={selectedMonth} onChange={event => setSelectedMonth(event.target.value)}>
              <option value="">Latest payslip</option>
              {(data.available_months || []).map((month: string) => <option key={month} value={month}>{month}</option>)}
            </select>
          </label>
          <button type="button" onClick={() => window.print()}>Print statement</button>
        </div>
      </section>

      <section className="faculty-payroll-summary">
        <article>
          <small>Net pay</small>
          <b>{money(net)}</b>
          <span>{run.payroll_month || 'Current month'} · {isPaid ? 'Credited' : paymentStatus}</span>
        </article>
        <article>
          <small>Gross earnings</small>
          <b>{money(gross)}</b>
          <span>Before deductions</span>
        </article>
        <article>
          <small>Total deductions</small>
          <b>{money(totalDeductions)}</b>
          <span>PF, tax &amp; deductions</span>
        </article>
        <article>
          <small>Payment status</small>
          <b className={isPaid ? 'payroll-success' : 'payroll-warning'}>{isPaid ? 'Credited' : paymentStatus}</b>
          <span>{paymentDate}</span>
        </article>
      </section>
      {lastPaidReceipt && (
        <section className="faculty-payroll-receipt">
          <header>
            <div>
              <small>Last paid payroll receipt</small>
              <h2>{lastPaidReceipt.payroll_month || 'Paid payroll'}</h2>
              <p>{lastPaidReceipt.run_name || 'Salary payment receipt'}</p>
            </div>
            <button type="button" onClick={() => window.print()}>Print receipt</button>
          </header>
          <div className="payroll-receipt-grid">
            <div><span>Receipt reference</span><b>{lastPaidReceipt.bank_ref_no || lastPaidReceipt.receipt_no || '—'}</b></div>
            <div><span>Payment date</span><b>{lastPaidReceipt.payment_date || '—'}</b></div>
            <div><span>Gross salary</span><b>{money(lastPaidReceipt.gross_salary)}</b></div>
            <div><span>Deductions</span><b>{money(lastPaidReceipt.total_deductions)}</b></div>
            <div><span>Net salary paid</span><b>{money(lastPaidReceipt.net_salary)}</b></div>
            <div><span>Payment method</span><b>{lastPaidReceipt.payment_method || 'Bank transfer'}</b></div>
          </div>
        </section>
      )}
<section className="faculty-payroll-grid">
        <article className="faculty-payroll-card">
          <header>
            <div>
              <h2>Salary statement</h2>
              <p>{run.run_name || 'Latest payroll run'}</p>
            </div>
            <span className="payroll-pill">{paymentStatus}</span>
          </header>

          <div className="payroll-person">
            <i>{profile.name?.split(' ').map((part: string) => part[0]).slice(0, 2).join('') || 'F'}</i>
            <div>
              <b>{profile.name || 'Faculty member'}</b>
              <span>{profile.designation || 'Faculty'} · {profile.department || 'Employee payroll account'}</span>
            </div>
          </div>

          <div className="payroll-columns">
            <section>
              <h3>Earnings</h3>
              {earnings.map((item: any) => (
                <div key={item.label}>
                  <span>{item.label}</span>
                  <b>{money(item.amount)}</b>
                </div>
              ))}
              <footer>
                <span>Gross earnings</span>
                <b>{money(gross)}</b>
              </footer>
            </section>

            <section>
              <h3>Deductions</h3>
              {deductions.map((item: any) => (
                <div key={item.label}>
                  <span>{item.label}</span>
                  <b>{money(item.amount)}</b>
                </div>
              ))}
              <footer>
                <span>Total deductions</span>
                <b>{money(totalDeductions)}</b>
              </footer>
            </section>
          </div>

          <div className="payroll-net">
            <span>Net salary credited</span>
            <b>{money(net)}</b>
          </div>
        </article>

        <aside className="faculty-payroll-side">
          <article>
            <h2>Payment details</h2>
            <div><span>Payment date</span><b>{paymentDate}</b></div>
            <div><span>Payment method</span><b>{payment.payment_method || profile.pay_mode || 'Bank transfer'}</b></div>
            <div><span>Reference</span><b>{payment.bank_ref_no || '—'}</b></div>
            <div><span>Account</span><b>{profile.bank_account_no || '—'}</b></div>
          </article>

          <article>
            <h2>Salary summary</h2>
            <div><span>Present days</span><b>{entry.present_days || 0}</b></div>
            <div><span>Paid days</span><b>{entry.paid_days || 0}</b></div>
            <div><span>Leave days</span><b>{entry.leave_days || 0}</b></div>
            <div><span>Employee code</span><b>{profile.employee_code || '—'}</b></div>
          </article>
        </aside>
      </section>
    </main>
  )
}


