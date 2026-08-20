import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, AuthChip } from './ui'

export default function Matrices() {
  const [tab, setTab] = useState<'rbac' | 'approval' | 'scope'>('rbac')
  return (
    <div className="fade-in">
      <div className="page-head">
        <h1>Authority matrices</h1>
        <p>The reference tables from the developer blueprint — role-based access (§9), approval chains (§10) and organizational scope (§11). The engine reads these; nothing is hardcoded per user.</p>
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
        {([['rbac', 'RBAC · §9'], ['approval', 'Approval · §10'], ['scope', 'Scope · §11']] as const).map(([id, l]) => (
          <button key={id} className={`btn ${tab === id ? 'btn-solid' : 'btn-out'}`} onClick={() => setTab(id)}>{l}</button>
        ))}
      </div>
      {tab === 'rbac' && <RBAC />}
      {tab === 'approval' && <Approval />}
      {tab === 'scope' && <Scope />}
    </div>
  )
}

function RBAC() {
  const [d, setD] = useState<any>(null)
  useEffect(() => { api.matrix('rbac').then(setD).catch(() => {}) }, [])
  if (!d) return <Spinner />
  return (
    <div className="card">
      <div className="tbl-scroll">
        <table className="tbl matrix">
          <thead>
            <tr><th className="sticky-c">Office</th>{d.verbs.map((v: string) => <th key={v} className="rot">{v}</th>)}</tr>
          </thead>
          <tbody>
            {d.rows.map((r: any) => (
              <tr key={r.office}>
                <td className="sticky-c" style={{ fontWeight: 600 }}>{r.office}</td>
                {d.verbs.map((v: string) => <td key={v} style={{ textAlign: 'center' }}><AuthChip v={r.grants[v] || 'Not Allowed'} /></td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Approval() {
  const [d, setD] = useState<any>(null)
  useEffect(() => { api.matrix('approval').then(setD).catch(() => {}) }, [])
  if (!d) return <Spinner />
  return (
    <div className="card">
      <div className="tbl-scroll">
        <table className="tbl">
          <thead><tr><th>Process</th><th>Approval chain</th><th>Escalation</th><th>Monetary</th></tr></thead>
          <tbody>
            {d.processes.map((p: any) => (
              <tr key={p.key}>
                <td style={{ fontWeight: 600 }}>{p.label}</td>
                <td>
                  <div className="chain-inline">
                    {p.chain.map((c: string, i: number) => (
                      <>
                        <span className="chip-stage" key={i}>{c}</span>
                        {i < p.chain.length - 1 && <span className="chain-arrow" style={{ fontSize: 12 }}>→</span>}
                      </>
                    ))}
                  </div>
                </td>
                <td><span className="tag" style={{ background: '#fdeee4', color: '#c05a1e' }}>{p.escalation}</span></td>
                <td>{p.amount ? <span className="tag" style={{ background: '#fdf3dc', color: '#96701b' }}>yes</span> : <span style={{ color: 'var(--txt-mute)' }}>—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Scope() {
  const [d, setD] = useState<any>(null)
  useEffect(() => { api.matrix('scope').then(setD).catch(() => {}) }, [])
  if (!d) return <Spinner />
  const SCOPE_COLORS: Record<string, string> = {
    global: '#8b6fc9', university: '#4a86c9', campus: '#2fa98c',
    faculty: '#c9a24a', department: '#e0b74a', program: '#3aa06a',
    section: '#5a9bd4', individual: '#a29a89',
  }
  return (
    <div className="card">
      <div className="tbl-scroll">
        <table className="tbl">
          <thead><tr><th>Office</th><th>Scope level</th><th>Reach</th></tr></thead>
          <tbody>
            {d.rows.map((r: any) => (
              <tr key={r.office}>
                <td style={{ fontWeight: 600 }}>{r.office}</td>
                <td><span className="pill" style={{ background: (SCOPE_COLORS[r.scope] || '#999') + '22', color: SCOPE_COLORS[r.scope] || '#555' }}>{r.scope}</span></td>
                <td style={{ color: 'var(--txt-soft)', fontSize: 13 }}>{r.reach}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
