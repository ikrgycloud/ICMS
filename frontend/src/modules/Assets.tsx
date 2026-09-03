import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { PageHead, Spinner, money } from './kit'

export default function Assets() {
  const [data, setData] = useState<any>(null)
  const [q, setQ] = useState(''), [category, setCategory] = useState(''), [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const load = (filters = { q, category, status }) => { setError(''); api.assets(filters).then(setData).catch(() => setError('Unable to load asset inventory. Please try again.')) }
  useEffect(() => { load({ q: '', category: '', status: '' }) }, [])
  const rows = useMemo(() => data?.assets || [], [data])
  if (!data) return <Spinner />
  const summary = data.summary
  return <div className="fade-in principal-operations">
    <PageHead title="Assets & Inventory" sub="Campus asset register, book value and service attention." />
    <div className="operations-kpis"><Metric label="Total tracked assets" value={summary.total}/><Metric label="Book value" value={money(summary.book_value)}/><Metric label="In service" value={summary.in_service}/><Metric label="Needs attention" value={summary.maintenance}/></div>
    <div className="operations-filter"><input className="inp" value={q} onChange={e => setQ(e.target.value)} placeholder="Search asset, tag or location" onKeyDown={e => e.key === 'Enter' && load()}/><select className="select" value={category} onChange={e => setCategory(e.target.value)}><option value="">All Categories</option>{data.categories.map((x: string) => <option key={x}>{x}</option>)}</select><select className="select" value={status} onChange={e => setStatus(e.target.value)}><option value="">All Statuses</option>{data.statuses.map((x: string) => <option key={x}>{x}</option>)}</select><button className="btn btn-crimson" onClick={() => load()}>Filter</button><button className="btn btn-out" onClick={() => { setQ(''); setCategory(''); setStatus(''); load({ q: '', category: '', status: '' }) }}>Clear</button></div>
    {error && <p className="principal-empty">{error}</p>}
    <section className="card" style={{ marginBottom: 16 }}><div className="card-h"><h3>Portfolio Mix</h3><span className="hint">All tracked campus assets</span></div><div className="card-pad"><div className="grid-3">{data.category_summary.map((item: any) => <div className="snap" key={item.category}><span>{item.category}</span><b>{item.count} · {summary.total ? Math.round((item.count / summary.total) * 100) : 0}%</b><small>{money(item.book_value)}</small></div>)}</div></div></section>
    <section className="card"><div className="card-h"><h3>Campus Assets</h3><span className="hint">{rows.length} matching records</span></div><AssetTable rows={rows}/></section>
  </div>
}

export function AssetTable({ rows }: { rows: any[] }) { return <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Asset / Tag</th><th>Asset name</th><th>Category</th><th>Location</th><th>Status</th><th>Book value</th></tr></thead><tbody>{rows.map(a => <tr key={a.id}><td className="mono">{a.tag}</td><td><b>{a.name || a.item}</b></td><td><span className="tag">{a.category}</span></td><td>{a.location}</td><td><span className={`pill s-${String(a.status).replace('-', '_')}`}>{a.status}</span></td><td>{money(a.value)}</td></tr>)}</tbody></table>{!rows.length && <p className="principal-empty">No assets match these filters.</p>}</div> }
function Metric({ label, value }: any) { return <div><span>{label}</span><b>{value}</b></div> }
