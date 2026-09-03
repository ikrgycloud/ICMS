import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast } from './kit'

export default function HR({ caps }: { caps: any }) {
  const [tab, setTab] = useState<'leave' | 'jobs'>('leave')
  const [leave, setLeave] = useState<any>(null)
  const [jobs, setJobs] = useState<any>(null)
  const [decision, setDecision] = useState<any>(null)

  function load() {
    api.leave().then(setLeave).catch(() => {})
    api.jobs().then(setJobs).catch(() => {})
  }
  useEffect(() => { load() }, [])

  async function decide(id: string, action: string) {
    try { const r = await api.decideLeave(id, action); setDecision(r.decision); load() }
    catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }) }
  }

  if (!leave) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead title="Human Resources" sub="Leave lifecycle and recruitment" />
      <div className="tabs">
        <button className={`tab ${tab === 'leave' ? 'on' : ''}`} onClick={() => setTab('leave')}>Leave requests</button>
        <button className={`tab ${tab === 'jobs' ? 'on' : ''}`} onClick={() => setTab('jobs')}>Openings</button>
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
      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
