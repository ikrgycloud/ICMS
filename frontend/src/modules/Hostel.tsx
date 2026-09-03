import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast, Kpis } from './kit'

export default function Hostel({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  const [decision, setDecision] = useState<any>(null)

  function load() { api.hostel().then(setData).catch(() => {}) }
  useEffect(() => { load() }, [])

  async function allocate(id: string) {
    try { const r = await api.allocateHostel(id); setDecision(r.decision); load() }
    catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }) }
  }

  if (!data) return <Spinner />
  const s = data.summary
  return (
    <div className="fade-in">
      <PageHead title="Hostel" sub="Occupancy and allocation requests" />
      <Kpis items={[
        { label: 'Rooms', value: s.rooms }, { label: 'Capacity', value: s.capacity },
        { label: 'Occupied', value: s.occupied }, { label: 'Vacant', value: s.vacant, tone: 'var(--teal)' },
      ]} />
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-h"><h3>Allocation requests</h3></div>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Student</th><th>Status</th><th style={{ textAlign: 'right' }}></th></tr></thead>
            <tbody>
              {data.requests.map((r: any) => (
                <tr key={r.id}>
                  <td><b>{r.student}</b></td>
                  <td><span className={`pill s-${r.status}`}>{r.status}</span></td>
                  <td style={{ textAlign: 'right' }}><button className="btn btn-sm btn-teal" disabled={!caps.allocate} onClick={() => allocate(r.id)}>Allocate room</button></td>
                </tr>
              ))}
              {data.requests.length === 0 && <tr><td colSpan={3}><div className="empty">No pending requests</div></td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
