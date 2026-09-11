import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, LEVEL_COLORS } from './ui'

const LEVEL_NAMES: Record<number, string> = { 1: 'Governance & Apex', 2: 'Executive Leadership', 3: 'Campus Leadership', 4: 'Institution Heads', 5: 'Deputy / Associate', 6: 'Academic Units', 7: 'Administrative Units', 8: 'Support & Operations' }

export default function Directory({ user }: { user?: any }) {
  const [offices, setOffices] = useState<any[]>([]), [q, setQ] = useState(''), [sel, setSel] = useState<any>(null)
  useEffect(() => { api.offices().then(setOffices).catch(() => {}) }, [])
  if (!offices.length) return <Spinner />
  const principal = user?.office_n === 4
  const filtered = offices.filter(office => office.name.toLowerCase().includes(q.toLowerCase()) || (office.purpose || '').toLowerCase().includes(q.toLowerCase()))
  const byLevel: Record<number, any[]> = {}
  filtered.forEach(office => { (byLevel[office.level] = byLevel[office.level] || []).push(office) })
  return <div className={`fade-in directory-page ${principal ? 'principal-directory' : ''}`}>
    <div className="page-head"><h1>Office Directory</h1><p>All 40 offices across 8 authority levels, {offices.reduce((total, office) => total + office.roles, 0)} internal roles. Each office reports upward per the org chart.</p></div>
    <div className="directory-search"><span aria-hidden="true">⌕</span><input className="inp" placeholder="Search offices..." value={q} onChange={e => setQ(e.target.value)} /></div>
    <div className="directory-levels">{Object.keys(byLevel).map(Number).sort((a, b) => a - b).map(level => { const rows = byLevel[level]; const roles = rows.reduce((total, row) => total + row.roles, 0); return <section className="directory-level" key={level}><header className="directory-level-head"><span className="directory-level-badge" style={{ background: principal ? '#8f1736' : LEVEL_COLORS[level] }}>L{level}</span><div><h2>{LEVEL_NAMES[level]}</h2><p>{rows.length} {rows.length === 1 ? 'Office' : 'Offices'} · {roles} {roles === 1 ? 'Role' : 'Roles'}</p></div></header><div className="directory-office-grid">{rows.map(office => <button className="directory-office-card" type="button" key={office.n} onClick={() => setSel(office)}><div className="directory-office-top"><span className="directory-office-number" style={{ color: principal ? '#8f1736' : LEVEL_COLORS[level] }}>Office {office.n}</span><span className="directory-role-count">{office.roles} {office.roles === 1 ? 'role' : 'roles'}</span></div><strong>{office.name}</strong><p>{office.purpose}</p><span className="directory-office-level">{LEVEL_NAMES[level]}</span></button>)}</div></section>})}</div>
    {!filtered.length && <div className="principal-empty">No offices match your search.</div>}
    {sel && <OfficeModal n={sel.n} principal={principal} onClose={() => setSel(null)} />}
  </div>
}

function OfficeModal({ n, principal, onClose }: { n: number; principal: boolean; onClose: () => void }) {
  const [office, setOffice] = useState<any>(null)
  useEffect(() => { api.office(n).then(setOffice).catch(() => {}) }, [n])
  return <div className="modal-bg" onClick={onClose}><div className={`modal ${principal ? 'principal-directory-modal' : ''}`} style={{ maxWidth: 640 }} onClick={e => e.stopPropagation()}>{!office ? <div style={{ padding: 50 }}><Spinner /></div> : <><div className="modal-h"><div><div className="directory-modal-title"><span className="lvl-badge" style={{ background: principal ? '#8f1736' : LEVEL_COLORS[office.level] }}>L{office.level}</span><h3>{office.name}</h3></div><p className="directory-modal-purpose">{office.purpose}</p></div><button className={principal ? 'modal-x' : 'close-x'} onClick={onClose} aria-label="Close office details">×</button></div><div className="modal-b directory-modal-body"><Section title={`Internal roles · ${office.internal_roles.length}`}><div className="directory-role-chips">{office.internal_roles.map((role: string) => <span className="tag" key={role}>{role}</span>)}</div></Section><Section title="Functionalities"><ul className="bullet-list">{office.functionalities.map((item: string) => <li key={item}>{item}</li>)}</ul></Section><Section title="Workflows"><ul className="bullet-list">{office.workflows.map((item: string) => <li key={item}>{item}</li>)}</ul></Section><Section title="Modules"><div className="directory-module-chips">{office.modules.map((item: string) => <span className="tag" key={item}>{item}</span>)}</div></Section><div className="directory-modal-meta"><Section title="Scope"><span className="mono">{office.scope}</span></Section><Section title="Reports to"><span>{office.reports_to}</span></Section></div></div></>}</div></div>
}
function Section({ title, children }: any) { return <section className="directory-modal-section"><h4>{title}</h4>{children}</section> }
