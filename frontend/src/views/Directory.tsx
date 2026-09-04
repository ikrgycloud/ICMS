import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, LEVEL_COLORS } from './ui'

const LEVEL_NAMES: Record<number, string> = {
  1: 'Governance & apex', 2: 'Executive leadership', 3: 'Campus leadership',
  4: 'Institution heads', 5: 'Deputy / associate', 6: 'Academic units',
  7: 'Administrative units', 8: 'Support & operations',
}

export default function Directory() {
  const [offices, setOffices] = useState<any[]>([])
  const [q, setQ] = useState('')
  const [sel, setSel] = useState<any>(null)

  useEffect(() => { api.offices().then(setOffices).catch(() => {}) }, [])
  if (!offices.length) return <Spinner />

  const filtered = offices.filter(o =>
    o.name.toLowerCase().includes(q.toLowerCase()) ||
    (o.purpose || '').toLowerCase().includes(q.toLowerCase()))
  const byLevel: Record<number, any[]> = {}
  filtered.forEach(o => { (byLevel[o.level] = byLevel[o.level] || []).push(o) })

  return (
    <div className="fade-in">
      <div className="page-head">
        <h1>Office directory</h1>
        <p>All 40 offices across 8 authority levels, {offices.reduce((a, o) => a + o.roles, 0)} internal roles. Each office reports upward per the org chart.</p>
      </div>

      <input className="inp" style={{ maxWidth: 420, marginBottom: 22 }} placeholder="Search offices…" value={q} onChange={e => setQ(e.target.value)} />

      {Object.keys(byLevel).map(Number).sort((a, b) => a - b).map(lvl => (
        <div key={lvl} style={{ marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
            <span className="lvl-badge" style={{ background: LEVEL_COLORS[lvl] }}>L{lvl}</span>
            <h2 style={{ fontSize: 17, fontFamily: 'var(--ff-display)' }}>{LEVEL_NAMES[lvl]}</h2>
            <span className="hint">{byLevel[lvl].length} offices</span>
          </div>
          <div className="office-grid">
            {byLevel[lvl].map(o => (
              <div className="office-card" key={o.n} onClick={() => setSel(o)}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div className="oc-n" style={{ background: LEVEL_COLORS[lvl] }}>{o.n}</div>
                  <span className="oc-roles">{o.roles} roles</span>
                </div>
                <div className="oc-name">{o.name}</div>
                <div className="oc-purpose">{o.purpose}</div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {sel && <OfficeModal n={sel.n} onClose={() => setSel(null)} />}
    </div>
  )
}

function OfficeModal({ n, onClose }: { n: number; onClose: () => void }) {
  const [o, setO] = useState<any>(null)
  useEffect(() => { api.office(n).then(setO).catch(() => {}) }, [n])

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 640 }} onClick={e => e.stopPropagation()}>
        {!o ? <div style={{ padding: 50 }}><Spinner /></div> : (
          <>
            <div className="modal-h">
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className="lvl-badge" style={{ background: LEVEL_COLORS[o.level] }}>L{o.level}</span>
                  <h3>{o.name}</h3>
                </div>
                <div style={{ fontSize: 13, color: 'var(--txt-soft)', marginTop: 6 }}>{o.purpose}</div>
              </div>
              <button className="close-x" onClick={onClose}>×</button>
            </div>
            <div className="modal-b">
              <Section title={`Internal roles · ${o.internal_roles.length}`}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {o.internal_roles.map((r: string, i: number) => (
                    <span className="tag" key={r} style={i === 0 ? { background: '#fdf3dc', color: '#96701b', fontWeight: 600 } : {}}>{r}</span>
                  ))}
                </div>
              </Section>
              <Section title="Functionalities">
                <ul className="bullet-list">{o.functionalities.map((f: string) => <li key={f}>{f}</li>)}</ul>
              </Section>
              <Section title="Workflows">
                <ul className="bullet-list">{o.workflows.map((w: string) => <li key={w}>{w}</li>)}</ul>
              </Section>
              <div style={{ display: 'flex', gap: 30, flexWrap: 'wrap' }}>
                <Section title="Modules">
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>{o.modules.map((m: string) => <span className="tag" key={m}>{m}</span>)}</div>
                </Section>
                <Section title="Scope"><span className="mono" style={{ fontSize: 13 }}>{o.scope}</span></Section>
                <Section title="Reports to"><span style={{ fontSize: 13.5 }}>{o.reports_to}</span></Section>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function Section({ title, children }: any) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontFamily: 'var(--ff-mono)', fontSize: 11, color: 'var(--txt-mute)', textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 10 }}>{title}</div>
      {children}
    </div>
  )
}
