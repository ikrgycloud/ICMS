import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner } from './kit'

export default function Transport({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.transport().then(setData).catch(() => {}) }, [])
  if (!data) return <Spinner />
  return (
    <div className="fade-in">
      <PageHead title="Transport" sub="Routes, vehicles and seat occupancy" />
      <div className="card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Route</th><th>Stops</th><th>Vehicle</th><th>Seats</th></tr></thead>
            <tbody>
              {data.routes.map((r: any) => (
                <tr key={r.id}>
                  <td><b>{r.name}</b></td><td className="hint">{r.stops}</td><td className="mono">{r.vehicle}</td>
                  <td><span className="fill-bar"><span style={{ width: `${(r.taken / r.seats) * 100}%` }} /></span> {r.taken}/{r.seats}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-h"><h3>Pending transport requests</h3></div>
        <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Student</th><th>Preferred pickup point</th><th>Status</th></tr></thead><tbody>
          {(data.requests || []).map((request: any) => <tr key={request.id}><td><b>{request.student}</b></td><td>{request.pickup_point || 'Not provided'}</td><td><span className={`pill s-${request.status}`}>{request.status}</span></td></tr>)}
          {!(data.requests || []).length && <tr><td colSpan={3}><div className="empty">No pending transport requests</div></td></tr>}
        </tbody></table></div>
      </div>
    </div>
  )
}
