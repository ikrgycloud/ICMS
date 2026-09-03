import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, StatePill, Empty, money } from './ui'

export default function Workflows({ user, onChange }: { user: any; onChange: () => void }) {
  const [tab, setTab] = useState<'inbox' | 'mine' | 'all'>('inbox')
  const [wfs, setWfs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showStart, setShowStart] = useState(false)
  const [selected, setSelected] = useState<any>(null)

  function load() {
    setLoading(true)
    api.workflows(tab).then(r => { setWfs(r.workflows); setLoading(false) }).catch(() => setLoading(false))
  }
  useEffect(load, [tab])

  return (
    <div className="fade-in">
      <div className="page-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1>Workflows</h1>
          <p>Every request runs through the approval chain — permission, limit, delegation, workflow-state and segregation of duties, then audit.</p>
        </div>
        <button className="btn btn-brass" onClick={() => setShowStart(true)}>+ Initiate request</button>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
        {([['inbox', 'My office inbox'], ['mine', 'My requests'], ['all', 'All workflows']] as const).map(([id, lbl]) => (
          <button key={id} className={`btn ${tab === id ? 'btn-solid' : 'btn-out'}`} onClick={() => setTab(id)}>{lbl}</button>
        ))}
      </div>

      {loading ? <Spinner /> : (
        <div className="card">
          <div className="tbl-scroll">
            {wfs.length === 0 ? (
              <Empty icon="⇅" text={tab === 'inbox' ? 'Nothing awaiting your office. Requests routed here will appear for review and approval.' : tab === 'mine' ? 'You have not initiated any requests yet.' : 'No workflows in the system yet.'} />
            ) : (
              <table className="tbl">
                <thead>
                  <tr><th>Process</th><th>Request</th><th>Initiator</th><th>Amount</th><th>Stage</th><th>State</th><th></th></tr>
                </thead>
                <tbody>
                  {wfs.map(w => (
                    <tr key={w.id}>
                      <td style={{ fontWeight: 600 }}>{w.label}</td>
                      <td style={{ color: 'var(--txt-soft)' }}>{w.title}</td>
                      <td>{w.initiator}</td>
                      <td className="mono">{money(w.amount)}</td>
                      <td className="mono" style={{ fontSize: 8 }}>{w.current_stage}/{w.chain.length}</td>
                      <td><StatePill s={w.state} /></td>
                      <td><button className="btn btn-out" onClick={() => setSelected(w)}>Open</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {showStart && <StartModal user={user} onClose={() => setShowStart(false)} onDone={() => { setShowStart(false); load(); onChange() }} />}
      {selected && <DetailModal wf={selected} user={user} onClose={() => setSelected(null)} onDone={() => { load(); onChange() }} />}
    </div>
  )
}

function StartModal({ user, onClose, onDone }: any) {
  const [procs, setProcs] = useState<any[]>([])
  const [key, setKey] = useState('')
  const [title, setTitle] = useState('')
  const [amount, setAmount] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => { api.processes().then(r => { setProcs(r.processes); setKey(r.processes[0]?.key) }).catch(() => {}) }, [])
  const proc = procs.find(p => p.key === key)

  async function submit() {
    if (!title) { setErr('Describe the request'); return }
    setBusy(true); setErr('')
    try {
      await api.startWorkflow(key, title, proc?.amount && amount ? parseFloat(amount) : undefined)
      onDone()
    } catch (e: any) { setErr(e.message); setBusy(false) }
  }

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-h">
          <h3>Initiate a request</h3>
          <button className="close-x" onClick={onClose}>×</button>
        </div>
        <div className="modal-b">
          {err && <div className="err-box">{err}</div>}
          <div className="form-row">
            <label>Process</label>
            <select className="select" value={key} onChange={e => setKey(e.target.value)}>
              {procs.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
            </select>
          </div>
          {proc && (
            <div style={{ background: 'var(--mist)', borderRadius: 12, padding: 14, marginBottom: 16 }}>
              <div style={{ fontFamily: 'var(--ff-mono)', fontSize: 8, color: 'var(--txt-mute)', textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 8 }}>Approval chain · escalates to {proc.escalation}</div>
              <div className="chain">
                {proc.chain.map((c: string, i: number) => (
                  <>
                    <div className="chain-node" key={i} style={{ minWidth: 110, padding: 10 }}>
                      <div className="cn-stage">Stage {i}</div>
                      <div className="cn-role" style={{ fontSize: 8.5 }}>{c}</div>
                    </div>
                    {i < proc.chain.length - 1 && <span className="chain-arrow">→</span>}
                  </>
                ))}
              </div>
            </div>
          )}
          <div className="form-row">
            <label>Request description</label>
            <input className="inp" value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Fee waiver for J. Rao (roll 21CS034)" />
          </div>
          {proc?.amount && (
            <div className="form-row">
              <label>Amount (₹) — checked against your scope's approval limit</label>
              <input className="inp mono" value={amount} onChange={e => setAmount(e.target.value)} placeholder="250000" />
            </div>
          )}
        </div>
        <div className="modal-f">
          <button className="btn btn-out" onClick={onClose}>Cancel</button>
          <button className="btn btn-brass" onClick={submit} disabled={busy}>{busy ? 'Submitting…' : 'Submit request'}</button>
        </div>
      </div>
    </div>
  )
}

function DetailModal({ wf, user, onClose, onDone }: any) {
  const [data, setData] = useState<any>(wf)
  const [lastDecision, setLastDecision] = useState<any>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  function refresh() { api.workflow(wf.id).then(setData).catch(() => {}) }
  useEffect(refresh, [])

  async function decide(action: string) {
    setBusy(true); setLastDecision(null)
    try {
      const r = await api.decideWorkflow(wf.id, action, reason)
      setLastDecision(r.decision)
      setData(r.workflow)
      setReason('')
      onDone()
    } catch (e: any) { setLastDecision({ outcome: 'DENY', reason: e.message }) }
    setBusy(false)
  }

  const terminal = ['approved', 'executed', 'rejected'].includes(data.state)
  const canAct = !terminal
  const outcomeColor = (o: string) => o === 'ALLOW' ? 'var(--teal)' : o === 'DENY' ? 'var(--rose)' : o === 'ESCALATE' ? 'var(--amber)' : '#6f7fd4'

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 680 }} onClick={e => e.stopPropagation()}>
        <div className="modal-h">
          <div>
            <h3>{data.label}</h3>
            <div style={{ fontSize: 9, color: 'var(--txt-soft)', marginTop: 4 }}>{data.title}</div>
          </div>
          <button className="close-x" onClick={onClose}>×</button>
        </div>
        <div className="modal-b">
          <div style={{ display: 'flex', gap: 20, marginBottom: 18, flexWrap: 'wrap' }}>
            <Meta label="State"><StatePill s={data.state} /></Meta>
            <Meta label="Initiator">{data.initiator}</Meta>
            <Meta label="Amount"><span className="mono">{money(data.amount)}</span></Meta>
            <Meta label="Scope"><span className="mono">{data.scope_level}</span></Meta>
            <Meta label="Escalates to"><span className="mono">{data.escalation}</span></Meta>
          </div>

          <div style={{ fontFamily: 'var(--ff-mono)', fontSize: 8, color: 'var(--txt-mute)', textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 10 }}>Approval chain</div>
          <div className="chain" style={{ marginBottom: 22 }}>
            {data.chain.map((c: string, i: number) => (
              <>
                <div className={`chain-node ${i < data.current_stage ? 'done' : i === data.current_stage ? 'current' : ''}`} key={i}>
                  <div className="cn-stage">Stage {i}{i < data.current_stage ? ' ✓' : ''}</div>
                  <div className="cn-role">{c}</div>
                </div>
                {i < data.chain.length - 1 && <span className="chain-arrow">→</span>}
              </>
            ))}
          </div>

          {lastDecision && (
            <div style={{ borderRadius: 12, padding: '13px 16px', marginBottom: 18, background: '#fbf9f3', border: `1.5px solid ${outcomeColor(lastDecision.outcome)}` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="mono" style={{ fontWeight: 700, color: outcomeColor(lastDecision.outcome) }}>{lastDecision.outcome}</span>
                {lastDecision.escalate_to && <span className="tag" style={{ background: '#fdeee4', color: '#c05a1e' }}>→ {lastDecision.escalate_to}</span>}
              </div>
              <div style={{ fontSize: 9.5, color: 'var(--txt-soft)', marginTop: 6 }}>{lastDecision.reason}</div>
            </div>
          )}

          {data.history.length > 0 && (
            <>
              <div style={{ fontFamily: 'var(--ff-mono)', fontSize: 8, color: 'var(--txt-mute)', textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 10 }}>Decision history</div>
              <div style={{ marginBottom: 16 }}>
                {data.history.map((h: any, i: number) => (
                  <div key={i} style={{ display: 'flex', gap: 12, padding: '9px 0', borderBottom: '1px solid #f2efe8', fontSize: 9 }}>
                    <span className="mono" style={{ fontWeight: 700, color: outcomeColor(h.decision), minWidth: 80 }}>{h.decision}</span>
                    <div style={{ flex: 1 }}>
                      <div><b>{h.actor}</b> · <span style={{ color: 'var(--txt-soft)' }}>{h.stage_label}</span></div>
                      <div style={{ color: 'var(--txt-mute)', fontSize: 8.5 }}>{h.reason}</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {canAct && (
            <div style={{ background: 'var(--mist)', borderRadius: 12, padding: 16 }}>
              <div className="form-row" style={{ marginBottom: 12 }}>
                <label>Reason (recorded in audit)</label>
                <input className="inp" value={reason} onChange={e => setReason(e.target.value)} placeholder="Optional note for the decision" />
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button className="btn btn-teal" disabled={busy} onClick={() => decide('review')}>Review</button>
                <button className="btn btn-brass" disabled={busy} onClick={() => decide('approve')}>Approve</button>
                {data.state === 'approved' && <button className="btn btn-solid" disabled={busy} onClick={() => decide('execute')}>Execute</button>}
                <button className="btn btn-rose" disabled={busy} onClick={() => decide('reject')}>Reject</button>
                <button className="btn btn-out" disabled={busy} onClick={() => decide('escalate')}>Escalate</button>
              </div>
              <div style={{ fontSize: 8, color: 'var(--txt-mute)', marginTop: 10 }}>
                The engine runs the full authority check on each action. If you initiated this request, segregation of duties will block your own approval.
              </div>
            </div>
          )}
          {terminal && (
            <div style={{ textAlign: 'center', padding: 14, background: 'var(--mist)', borderRadius: 12, color: 'var(--txt-soft)', fontSize: 10 }}>
              This request has reached a terminal state: <b>{data.state}</b>.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Meta({ label, children }: any) {
  return (
    <div>
      <div style={{ fontFamily: 'var(--ff-mono)', fontSize: 8, color: 'var(--txt-mute)', textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 5 }}>{label}</div>
      <div style={{ fontSize: 10, fontWeight: 500 }}>{children}</div>
    </div>
  )
}
