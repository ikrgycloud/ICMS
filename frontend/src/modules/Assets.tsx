import { useState, useEffect, useMemo } from 'react'
import { api } from '../api'
import { PageHead, Spinner, money } from './kit'

export default function Assets({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState('')
  useEffect(() => { api.assets().then(setData).catch(() => {}) }, [])
  const assets = data?.assets || []
  const categories = useMemo(() => [...new Set(assets.map((asset: any) => asset.category).filter(Boolean))].sort(), [assets])
  const statuses = useMemo(() => [...new Set(assets.map((asset: any) => asset.status).filter(Boolean))].sort(), [assets])
  if (!data) return <Spinner />
  const total = assets.reduce((a: number, x: any) => a + Number(x.value || 0), 0)
  const filtered = assets.filter((asset: any) => {
    const text = `${asset.tag} ${asset.name} ${asset.location}`.toLowerCase()
    return (!query || text.includes(query.toLowerCase())) && (!category || asset.category === category) && (!status || asset.status === status)
  })
  const inService = assets.filter((asset: any) => asset.status === 'in-service').length
  const attention = assets.filter((asset: any) => asset.status !== 'in-service').length
  return (
    <div className="fade-in assets-workspace">
      <PageHead title="Assets & inventory" sub="Track campus assets, locations, service status, and book value." right={<span className="assets-live"><i />Register monitored</span>} />
      <section className="assets-summary">
        <div className="assets-summary-main"><span>REGISTERED ASSETS</span><strong>{assets.length}</strong><small>Authorised campus register</small></div>
        <div><span>Book value</span><b>{money(total)}</b><small>Recorded asset value</small></div>
        <div><span>In service</span><b>{inService}</b><small>Operational assets</small></div>
        <div><span>Needs attention</span><b>{attention}</b><small>Maintenance or review</small></div>
      </section>
      <section className="assets-register card">
        <div className="assets-register-head"><div><span>ASSET REGISTER</span><h3>Campus Assets</h3><p>Search and review tracked equipment, vehicles, furniture, and facilities.</p></div><b>{filtered.length} records</b></div>
        <div className="assets-filter"><input className="inp" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search tag, asset, or location..." /><select className="select" value={category} onChange={event => setCategory(event.target.value)}><option value="">All Categories</option>{categories.map((item: string) => <option key={item}>{item}</option>)}</select><select className="select" value={status} onChange={event => setStatus(event.target.value)}><option value="">All Statuses</option>{statuses.map((item: string) => <option key={item}>{item}</option>)}</select><button className="btn btn-crimson" onClick={() => { setQuery(query.trim()); }}>Filter</button><button className="btn btn-out" onClick={() => { setQuery(''); setCategory(''); setStatus('') }}>Clear</button></div>
        <div className="tbl-scroll"><table className="tbl assets-table">
          <thead><tr><th>Asset Tag</th><th>Asset / Item</th><th>Category</th><th>Location</th><th>Status</th><th>Book Value</th></tr></thead>
          <tbody>{filtered.map((a: any) => (
                <tr key={a.id}>
                  <td className="mono"><span className="asset-tag-icon">{a.name?.charAt(0) || 'A'}</span>{a.tag}</td><td><b>{a.name}</b></td><td><span className="tag">{a.category}</span></td>
                  <td>{a.location}</td><td><span className={`pill s-${a.status.replace('-', '_')}`}>{a.status}</span></td><td>{money(a.value)}</td>
                </tr>
              ))}</tbody>
        </table>{!filtered.length && <div className="principal-empty"><b>No matching assets found.</b><p>Try changing or clearing the current filters.</p></div>}</div>
      </section>
    </div>
  )
}
