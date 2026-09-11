import { useEffect, useState } from 'react'
import { api } from '../api'
import { DecisionToast, Empty, Spinner } from './kit'

export default function PayrollPanel() {
  const [runs, setRuns] = useState<any>(null)
  const [detail, setDetail] = useState<any>(null)
  const [decision, setDecision] = useState<any>(null)

  function load() {
    api.payrollRuns().then(setRuns).catch(() => setRuns({ runs: [] }))
  }

  useEffect(() => { load() }, [])

  async function openRun(runId: string) {
    try {
      setDetail(await api.payrollRunDetails(runId))
    } catch (error: any) {
      setDecision({ outcome: 'DENY', reason: error.message })
    }
  }

  async function markPaid(entryId: string) {
    try {
      const result = await api.updatePayrollEntryStatus(entryId, 'paid')
      setDecision({ outcome: 'ALLOW', reason: `Payment posted: ${result.entry_id}` })
      if (detail) {
        setDetail({
          ...detail,
          entries: (detail.entries || []).map((entry: any) =>
            entry.id === entryId ? { ...entry, payment_status: result.status } : entry,
          ),
        })
      }
      load()
    } catch (error: any) {
      setDecision({ outcome: 'DENY', reason: error.message })
    }
  }

  return (
    <div className="card">
      <div style={{ marginBottom: '16px' }}>
        <h3 style={{ margin: 0 }}>Payroll payment processing</h3>
        <span className="hint">Accounts reviews HR-generated payroll and posts bank payments.</span>
      </div>

      {!runs ? <Spinner /> : !runs.runs?.length ? <Empty text="No payroll runs are available." /> : (
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Run</th><th>Month</th><th>Status</th><th>Payment date</th><th>Action</th></tr></thead>
            <tbody>{runs.runs.map((run: any) => (
              <tr key={run.id}>
                <td><b>{run.run_name}</b></td>
                <td>{run.payroll_month}</td>
                <td><span className={`pill s-${run.status}`}>{run.status}</span></td>
                <td>{run.payment_date || '—'}</td>
                <td><button className="btn btn-sm btn-primary" onClick={() => openRun(run.id)}>View</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}

      {detail && (
        <div style={{ marginTop: '24px' }}>
          <h3 style={{ marginBottom: '12px' }}>Payroll details — {detail.run.run_name}</h3>
          <div className="tbl-scroll">
            <table className="tbl">
              <thead><tr><th>Employee</th><th>Gross</th><th>Deductions</th><th>Net</th><th>Status</th><th>Action</th></tr></thead>
              <tbody>{(detail.entries || []).map((entry: any) => (
                <tr key={entry.id}>
                  <td><div><b>{entry.employee_name}</b></div><small>{entry.employee_code || entry.employee_id}</small></td>
                  <td>₹{Number(entry.gross_salary || 0).toLocaleString('en-IN')}</td>
                  <td>₹{Number(entry.total_deductions || 0).toLocaleString('en-IN')}</td>
                  <td>₹{Number(entry.net_salary || 0).toLocaleString('en-IN')}</td>
                  <td><span className={`pill s-${entry.payment_status}`}>{entry.payment_status}</span></td>
                  <td>{entry.payment_status === 'paid' ? <span className="hint">Posted</span> : <button className="btn btn-sm btn-teal" onClick={() => markPaid(entry.id)}>Mark paid</button>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}
      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
