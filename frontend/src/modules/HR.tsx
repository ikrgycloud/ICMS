import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast } from './kit'

export default function HR({ caps }: { caps: any }) {
  const [tab, setTab] = useState<'leave' | 'jobs' | 'payroll'>('leave')
  const [leave, setLeave] = useState<any>(null)
  const [jobs, setJobs] = useState<any>(null)
  const [payrollRuns, setPayrollRuns] = useState<any>(null)
  const [payrollDetail, setPayrollDetail] = useState<any>(null)
  const [decision, setDecision] = useState<any>(null)

  function load() {
    api.leave().then(setLeave).catch(() => {})
    api.jobs().then(setJobs).catch(() => {})
    api.payrollRuns().then(setPayrollRuns).catch(() => setPayrollRuns({ runs: [] }))
  }
  useEffect(() => { load() }, [])

  async function decide(id: string, action: string) {
    try { const r = await api.decideLeave(id, action); setDecision(r.decision); load() }
    catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }) }
  }

  async function generatePayroll() {
    try {
      const now = new Date()
      const payrollMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
      const r = await api.createPayrollRun({
        payroll_month: payrollMonth,
        run_name: `${now.toLocaleString('en-US', { month: 'long', year: 'numeric' })} Payroll Run`,
      })
      setDecision({ outcome: 'ALLOW', reason: `Payroll generated successfully (${r.run_id})` })
      load()
      setTab('payroll')
    } catch (e: any) {
      setDecision({ outcome: 'DENY', reason: e.message })
    }
  }

  async function loadPayrollDetail(runId: string) {
    try {
      const r = await api.payrollRunDetails(runId)
      setPayrollDetail(r)
    } catch (e: any) {
      setDecision({ outcome: 'DENY', reason: e.message })
    }
  }

  async function updatePayrollEntry(entryId: string, status: string) {
    try {
      const r = await api.updatePayrollEntryStatus(entryId, status)
      setDecision({ outcome: 'ALLOW', reason: `Payroll entry updated to ${r.status}` })
      if (payrollDetail) {
        const next = { ...payrollDetail, entries: (payrollDetail.entries || []).map((entry: any) => entry.id === entryId ? { ...entry, payment_status: r.status } : entry) }
        setPayrollDetail(next)
      }
      load()
    } catch (e: any) {
      setDecision({ outcome: 'DENY', reason: e.message })
    }
  }

  if (!leave) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead title="Human Resources" sub="Leave lifecycle, recruitment, and payroll" />
      <div className="tabs">
        <button className={`tab ${tab === 'leave' ? 'on' : ''}`} onClick={() => setTab('leave')}>Leave requests</button>
        <button className={`tab ${tab === 'jobs' ? 'on' : ''}`} onClick={() => setTab('jobs')}>Openings</button>
        <button className={`tab ${tab === 'payroll' ? 'on' : ''}`} onClick={() => setTab('payroll')}>Payroll</button>
      </div>

      {tab === 'leave' && (
        <div className="card">
          <div className="tbl-scroll">
            <table className="tbl">
              <thead><tr><th>Staff</th><th>Type</th><th>Dates</th><th>Days</th><th>Reason</th><th>Status</th><th style={{ textAlign: 'right' }}>Decision</th></tr></thead>
              <tbody>
                {leave.leave.map((l: any) => (
                  <tr key={l.id}>
                    <td><b>{l.staff}</b></td>
                    <td><span className="tag">{l.kind}</span></td>
                    <td>{l.from} → {l.to}</td>
                    <td>{l.days}</td>
                    <td>{l.reason}</td>
                    <td><span className={`pill s-${l.status}`}>{l.status}</span></td>
                    <td style={{ textAlign: 'right' }}>
                      {l.status === 'pending' ? (
                        <div className="row-actions">
                          <button className="btn btn-sm btn-teal" disabled={!caps.approve_leave} onClick={() => decide(l.id, 'approve')}>Approve</button>
                          <button className="btn btn-sm btn-rose" disabled={!caps.approve_leave} onClick={() => decide(l.id, 'reject')}>Reject</button>
                        </div>
                      ) : <span className="hint">closed</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'jobs' && jobs && (
        <div className="card">
          <div className="tbl-scroll">
            <table className="tbl">
              <thead><tr><th>Title</th><th>Dept</th><th>Type</th><th>Openings</th><th>Status</th></tr></thead>
              <tbody>
                {jobs.jobs.map((j: any) => (
                  <tr key={j.id}><td><b>{j.title}</b></td><td>{j.dept}</td><td><span className="tag">{j.kind}</span></td><td>{j.openings}</td><td><span className="pill s-open">{j.status}</span></td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'payroll' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <h3 style={{ margin: 0 }}>Payroll runs</h3>
            <button className="btn btn-teal" onClick={generatePayroll}>Generate current payroll</button>
          </div>

          {!payrollRuns ? <Spinner /> : (
            <div className="tbl-scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Month</th>
                    <th>Status</th>
                    <th>Payment date</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(payrollRuns.runs || []).map((run: any) => (
                    <tr key={run.id}>
                      <td><b>{run.run_name}</b></td>
                      <td>{run.payroll_month}</td>
                      <td><span className={`pill s-${run.status}`}>{run.status}</span></td>
                      <td>{run.payment_date || '—'}</td>
                      <td><button className="btn btn-sm btn-primary" onClick={() => loadPayrollDetail(run.id)}>View</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {payrollDetail && (
            <div style={{ marginTop: '24px' }}>
              <h3 style={{ marginBottom: '12px' }}>Payroll details — {payrollDetail.run.run_name}</h3>
              <div className="tbl-scroll">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th>Gross</th>
                      <th>Deductions</th>
                      <th>Net</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(payrollDetail.entries || []).map((entry: any) => (
                      <tr key={entry.id}>
                        <td>
                          <div><b>{entry.employee_name}</b></div>
                          <small>{entry.employee_code || entry.employee_id}</small>
                        </td>
                        <td>₹{Number(entry.gross_salary || 0).toLocaleString('en-IN')}</td>
                        <td>₹{Number(entry.total_deductions || 0).toLocaleString('en-IN')}</td>
                        <td>₹{Number(entry.net_salary || 0).toLocaleString('en-IN')}</td>
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'flex-start' }}>
                            <span className={`pill s-${entry.payment_status}`}>{entry.payment_status}</span>
                            {entry.payment_status !== 'paid' && <span className="hint">Accounts payment pending</span>}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
