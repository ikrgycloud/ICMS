import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast } from './kit'

export default function Admissions({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  const [decision, setDecision] = useState<any>(null)

  function load() { api.applications().then(setData).catch(() => {}) }
  useEffect(() => { load() }, [])

  async function decide(id: string, action: string) {
    try {
      const r = await api.decideApplication(id, action)
      setDecision(r.decision); load()
    } catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }) }
  }

  if (!data) return <Spinner />
  const counts = data.applications.reduce((a: any, x: any) => { a[x.status] = (a[x.status] || 0) + 1; return a }, {})

  return (
    <div className="fade-in">
      <PageHead title="Admissions" sub="Applicant pipeline · verify, offer, and reject per the approval chain" />
      <div className="kpi-row" style={{ marginBottom: 20 }}>
        {['submitted', 'verified', 'offered', 'admitted', 'rejected'].map(st => (
          <div className="kpi" key={st}><div className="kpi-v">{counts[st] || 0}</div><div className="kpi-l">{st}</div></div>
        ))}
      </div>
      <div className="card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Applicant</th><th>Program</th><th>Score</th><th>Status</th><th style={{ textAlign: 'right' }}>Decision</th></tr></thead>
            <tbody>
              {data.applications.map((a: any) => (
                <tr key={a.id}>
                  <td><b>{a.name}</b><div className="hint">{a.email}</div></td>
                  <td>{a.program}</td>
                  <td><b>{a.score}</b></td>
                  <td><span className={`pill s-${a.status}`}>{a.status}</span></td>
                  <td style={{ textAlign: 'right' }}>
                    <div className="row-actions">
                      {a.status === 'submitted' && <button className="btn btn-sm btn-out" disabled={!caps.verify} onClick={() => decide(a.id, 'verify')}>Verify</button>}
                      {(a.status === 'verified' || a.status === 'submitted') && <button className="btn btn-sm btn-teal" disabled={!caps.offer} onClick={() => decide(a.id, 'offer')}>Offer</button>}
                      {a.status !== 'rejected' && a.status !== 'admitted' && <button className="btn btn-sm btn-rose" disabled={!caps.reject} onClick={() => decide(a.id, 'reject')}>Reject</button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
