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
    </div>
  )
}
