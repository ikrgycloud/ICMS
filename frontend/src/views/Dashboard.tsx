import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, StatePill, LEVEL_COLORS } from './ui'

export default function Dashboard({ user, go }: { user: any; go: (v: string) => void }) {
  const [data, setData] = useState<any>(null)

  useEffect(() => { api.dashboard().then(setData).catch(() => {}) }, [])
  if (!data) return <Spinner />

  const k = data.kpis
  const kpis = [
    { n: k.inbox, l: 'Awaiting my office', c: 'var(--brass)', v: 'workflows' },
    { n: k.my_requests, l: 'My requests', c: 'var(--teal)', v: 'workflows' },
    { n: k.approved, l: 'Approved', c: 'var(--teal-dk)', v: 'workflows' },
    { n: k.escalated, l: 'Escalated', c: 'var(--rose)', v: 'workflows' },
    { n: k.unread, l: 'Unread alerts', c: 'var(--amber)', v: 'workflows' },
  ]
  const states = data.workflows_by_state || {}
  const stateOrder = ['submitted', 'under_review', 'reviewed', 'approved', 'executed', 'escalated', 'rejected']
  const total = Object.values(states).reduce((a: any, b: any) => a + b, 0) as number

  return (
    <div className="fade-in">
      <div className="page-head">
        <h1>Good day, {user.name.split(' ')[0] || user.username}</h1>
        <p>{user.purpose}</p>
      </div>

      <div className="kpi-row">
        {kpis.map((x, i) => (
          <div className="kpi" key={i} style={{ ['--kc' as any]: x.c, cursor: 'pointer' }} onClick={() => go(x.v)}>
            <div className="kn">{x.n}</div>
            <div className="kl">{x.l}</div>
          </div>
        ))}
      </div>

      <div className="grid-2">
        {/* owned processes */}
        <div className="card">
          <div className="card-h">
            <h3>Processes this office owns</h3>
            <span className="hint">§10 approval matrix</span>
          </div>
          <div className="card-pad">
            {data.owned_processes.length === 0 && (
              <p style={{ color: 'var(--txt-mute)', fontSize: 14 }}>
                This office participates in workflows but does not own a reserved process.
                Open Workflows to initiate a request that routes to the owning office.
              </p>
            )}
            {data.owned_processes.map((p: any) => (
              <div key={p.key} style={{ padding: '13px 0', borderBottom: '1px solid #f2efe8' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontWeight: 600, fontSize: 14.5, color: 'var(--txt)' }}>{p.label}</div>
                  {p.amount && <span className="tag" style={{ background: '#fdf3dc', color: '#96701b' }}>monetary</span>}
                </div>
                <div style={{ fontFamily: 'var(--ff-mono)', fontSize: 11.5, color: 'var(--txt-mute)', marginTop: 5 }}>
                  {p.chain.join('  →  ')}  ⇡ {p.escalation}
                </div>
              </div>
            ))}
            <button className="btn btn-brass" style={{ marginTop: 16 }} onClick={() => go('workflows')}>
              Go to workflows →
            </button>
          </div>
        </div>

        {/* workflow states */}
        <div className="card">
          <div className="card-h">
            <h3>Workflow states · all tenants</h3>
            <span className="hint">{total} total</span>
          </div>
          <div className="card-pad">
            {total === 0 && <p style={{ color: 'var(--txt-mute)', fontSize: 14 }}>No workflows have run yet. Start one from the Workflows page to see the engine route it through the approval chain.</p>}
            {stateOrder.filter(s => states[s]).map(s => {
              const pct = Math.round((states[s] / total) * 100)
              return (
                <div key={s} style={{ marginBottom: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <StatePill s={s} />
                    <span style={{ fontFamily: 'var(--ff-mono)', fontSize: 12, color: 'var(--txt-soft)' }}>{states[s]}</span>
                  </div>
                  <div style={{ height: 8, background: '#f0ede5', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ width: `${pct}%`, height: '100%', background: 'var(--brass)', borderRadius: 4, transition: 'width .6s' }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* office snapshot */}
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-h">
          <h3>Your office at a glance</h3>
          <span className="hint">reports to {user.reports_to}</span>
        </div>
        <div className="card-pad grid-3">
          <div>
            <div className="side-sec" style={{ padding: 0, color: 'var(--txt-mute)' }}>Modules</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
              {user.modules.map((m: string) => <span className="tag" key={m}>{m}</span>)}
            </div>
          </div>
          <div>
            <div className="side-sec" style={{ padding: 0, color: 'var(--txt-mute)' }}>Key workflows</div>
            <ul style={{ marginTop: 10, paddingLeft: 16, fontSize: 13.5, color: 'var(--txt-soft)', lineHeight: 1.9 }}>
              {user.workflows.map((w: string) => <li key={w}>{w}</li>)}
            </ul>
          </div>
          <div>
            <div className="side-sec" style={{ padding: 0, color: 'var(--txt-mute)' }}>Internal roles ({user.internal_roles.length})</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
              {user.internal_roles.map((r: string, i: number) => (
                <span className="tag" key={r} style={i === 0 ? { background: '#fdf3dc', color: '#96701b', fontWeight: 600 } : {}}>{r}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
