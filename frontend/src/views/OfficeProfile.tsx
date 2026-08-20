import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, LEVEL_COLORS } from './ui'

export default function OfficeProfile({ user }: { user: any }) {
  const [o, setO] = useState<any>(null)
  useEffect(() => { api.office(user.office_n).then(setO).catch(() => {}) }, [user.office_n])
  if (!o) return <Spinner />

  return (
    <div className="fade-in">
      <div className="page-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
<<<<<<< HEAD
          <span className="lvl-badge" style={{ background: LEVEL_COLORS[o.level], width: 40, height: 40, fontSize: 11 }}>L{o.level}</span>
=======
          <span className="lvl-badge" style={{ background: LEVEL_COLORS[o.level], width: 40, height: 40, fontSize: 15 }}>L{o.level}</span>
>>>>>>> 22ee34d (updated code to branch)
          <div>
            <h1 style={{ marginBottom: 2 }}>{o.name}</h1>
            <p style={{ margin: 0 }}>{o.purpose}</p>
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-h"><h3>Internal roles</h3><span className="hint">{o.internal_roles.length} roles · you hold the head role</span></div>
          <div className="card-pad">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
              {o.internal_roles.map((r: string, i: number) => (
<<<<<<< HEAD
                <span className="tag" key={r} style={i === 0 ? { background: '#fdf3dc', color: '#96701b', fontWeight: 600, fontSize: 9 } : { fontSize: 9 }}>{r}{i === 0 ? ' ★' : ''}</span>
=======
                <span className="tag" key={r} style={i === 0 ? { background: '#fdf3dc', color: '#96701b', fontWeight: 600, fontSize: 13 } : { fontSize: 13 }}>{r}{i === 0 ? ' ★' : ''}</span>
>>>>>>> 22ee34d (updated code to branch)
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-h"><h3>Reporting line</h3><span className="hint">org chart</span></div>
          <div className="card-pad">
            <div className="report-line">
              <div className="rl-node up">{o.reports_to}</div>
              <div className="rl-conn">▲ reports to</div>
              <div className="rl-node self" style={{ borderColor: LEVEL_COLORS[o.level] }}>{o.name} <span style={{ opacity: .6 }}>· you</span></div>
            </div>
            <div style={{ marginTop: 18, display: 'flex', gap: 26 }}>
              <div><div className="mini-lbl">Scope</div><span className="mono">{o.scope}</span></div>
              <div><div className="mini-lbl">Office no.</div><span className="mono">{o.n} / 40</span></div>
              <div><div className="mini-lbl">Level</div><span className="mono">L{o.level} / 8</span></div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 20 }}>
        <div className="card">
          <div className="card-h"><h3>Functionalities</h3></div>
          <div className="card-pad"><ul className="bullet-list">{o.functionalities.map((f: string) => <li key={f}>{f}</li>)}</ul></div>
        </div>
        <div className="card">
          <div className="card-h"><h3>Workflows owned or touched</h3></div>
          <div className="card-pad"><ul className="bullet-list">{o.workflows.map((w: string) => <li key={w}>{w}</li>)}</ul></div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-h"><h3>Modules</h3></div>
        <div className="card-pad"><div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>{o.modules.map((m: string) => <span className="tag" key={m}>{m}</span>)}</div></div>
      </div>
    </div>
  )
}
