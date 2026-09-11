import { type CSSProperties, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { PageHead, Spinner } from './kit'

export default function Facilities() {
  const [data, setData] = useState<any>(null), [q, setQ] = useState(''), [category, setCategory] = useState(''), [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const load = (filters = { q, category, status }) => { setError(''); api.assets(filters).then(setData).catch(() => setError('Unable to load facilities and maintenance data.')) }
  useEffect(() => { load({ q: '', category: '', status: '' }) }, [])

  const rows = useMemo(() => data?.assets || [], [data])
  if (!data && !error) return <Spinner />
  if (!data) return <div className="facilities-error"><h3>Unable to load facilities and maintenance data.</h3><button className="btn btn-crimson" onClick={() => load({ q: '', category: '', status: '' })}>Retry</button></div>

  const s = data.summary
  const servicePercent = s.total ? Math.round((s.in_service / s.total) * 100) : 0
  const pendingReview = rows.filter((asset: any) => String(asset.status).toLowerCase().includes('pending')).length
  return <div className="fade-in principal-operations facilities">
    <PageHead title="Facilities & Maintenance" sub="Keep campus spaces, systems and equipment safe and operational."
      right={<span className="facility-monitor"><i />Campus systems monitored</span>} />

    <section className="facility-health">
      <div className="facility-health-intro"><span>Operational Health</span><b>{servicePercent}%</b><p>{servicePercent}% of assets are in service.</p><small>{s.maintenance} items currently require maintenance attention.</small><div className="facility-progress"><div><i style={{ width: `${servicePercent}%` }} /></div><b>{servicePercent}% healthy</b></div></div>
      <div className="facility-health-stat"><small>Campus assets</small><strong>{s.total}</strong><span>Registered assets</span></div>
      <div className="facility-health-stat"><small>In service</small><strong>{s.in_service}</strong><span>Operational now</span></div>
      <div className="facility-health-stat"><small>Maintenance</small><strong>{s.maintenance}</strong><span>Needs attention</span></div>
      <div className="facility-donut" style={{ '--service-percent': `${servicePercent}%` } as CSSProperties}><div><b>{servicePercent}%</b><span>In service</span></div></div>
    </section>

    <section className="facility-kpis">
      <Kpi icon="M" label="Open Maintenance" value={s.maintenance} detail="Requires attention" />
      <Kpi icon="S" label="In Service" value={s.in_service} detail="Operational assets" />
      <Kpi icon="R" label="Pending Review" value={pendingReview} detail="Awaiting review" />
      <Kpi icon="!" label="Facility Issues" value={s.maintenance} detail="Maintenance signals" />
    </section>

    <section className="facility-register card">
      <div className="facility-register-head"><div><span>Service Register</span><h3>Maintenance & Facility Status</h3><p>Campus assets grouped by their current operational condition.</p></div><b>{rows.length} records</b></div>
      <div className="operations-filter facility-filter"><input className="inp" value={q} onChange={e => setQ(e.target.value)} placeholder="Search facility, asset or location..." onKeyDown={e => e.key === 'Enter' && load()}/><select className="select" value={category} onChange={e => setCategory(e.target.value)}><option value="">All Categories</option>{data.categories.map((x: string) => <option key={x}>{x}</option>)}</select><select className="select" value={status} onChange={e => setStatus(e.target.value)}><option value="">All Statuses</option>{data.statuses.map((x: string) => <option key={x}>{x}</option>)}</select><button className="btn btn-crimson" onClick={() => load()}>Filter</button><button className="btn btn-out" onClick={() => { setQ(''); setCategory(''); setStatus(''); load({ q: '', category: '', status: '' }) }}>Clear</button></div>
      {error && <div className="facility-inline-error">{error}<button className="btn btn-out" onClick={() => load()}>Retry</button></div>}
      <div className="tbl-scroll"><table className="tbl facility-table"><thead><tr><th>Facility / Asset</th><th>Category</th><th>Location</th><th>Status</th><th>Service Signal</th></tr></thead><tbody>{rows.map((asset: any) => <AssetRow key={asset.id} asset={asset} />)}</tbody></table>{!rows.length && <div className="principal-empty"><b>No matching facility or asset records.</b><p>Try changing or clearing the current filters.</p></div>}</div>
    </section>
  </div>
}

function Kpi({ icon, label, value, detail }: any) { return <div className="facility-kpi"><i>{icon}</i><div><span>{label}</span><b>{value}</b><small>{detail}</small></div></div> }
function AssetRow({ asset }: any) { const attention = asset.status === 'maintenance' || String(asset.status).toLowerCase().includes('pending'); return <tr><td><span className="facility-asset-icon">{asset.name?.charAt(0) || 'A'}</span><span className="facility-asset-name"><b>{asset.name}</b><small className="mono">{asset.tag}</small></span></td><td><span className="facility-category">{asset.category}</span></td><td>{asset.location}</td><td><span className={`pill s-${String(asset.status).replace('-', '_')}`}>{asset.status}</span></td><td><span className={`facility-signal ${attention ? 'attention' : ''}`}><i />{attention ? 'Attention' : 'Normal'}</span></td></tr> }
