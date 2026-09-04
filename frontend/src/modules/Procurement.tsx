import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, money } from './kit'

export default function Procurement({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.assets().then(setData).catch(() => {}) }, [])
  if (!data) return <Spinner />
  return (
    <div className="fade-in">
      <PageHead title="Procurement" sub="Requisitions, purchase orders and the assets they create. Approvals route by amount to the CFO." />
      <div className="card">
        <div className="card-h"><h3>Recently procured assets</h3><span className="hint">purchase → PO → asset</span></div>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Tag</th><th>Item</th><th>Category</th><th>Location</th><th>Value</th></tr></thead>
            <tbody>
              {data.assets.slice(0, 15).map((a: any) => (
                <tr key={a.id}><td className="mono">{a.tag}</td><td><b>{a.name}</b></td><td><span className="tag">{a.category}</span></td><td>{a.location}</td><td>{money(a.value)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
