import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, money } from './kit'

export default function Assets({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.assets().then(setData).catch(() => {}) }, [])
  if (!data) return <Spinner />
  const total = data.assets.reduce((a: number, x: any) => a + x.value, 0)
  return (
    <div className="fade-in">
      <PageHead title="Assets & inventory" sub={`${data.assets.length} tracked assets · book value ${money(total)}`} />
      <div className="card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Tag</th><th>Asset</th><th>Category</th><th>Location</th><th>Status</th><th>Value</th></tr></thead>
            <tbody>
              {data.assets.map((a: any) => (
                <tr key={a.id}>
                  <td className="mono">{a.tag}</td><td><b>{a.name}</b></td><td><span className="tag">{a.category}</span></td>
                  <td>{a.location}</td><td><span className={`pill s-${a.status.replace('-', '_')}`}>{a.status}</span></td><td>{money(a.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
