import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Spinner, StatePill, Empty, money } from './ui'

export default function Workflows({ user, onChange, initialTab = 'inbox' }: { user: any; onChange: () => void; initialTab?: 'inbox' | 'mine' | 'all' }) {
  const [tab, setTab] = useState<'inbox' | 'mine' | 'all'>(initialTab)
  const [wfs, setWfs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showStart, setShowStart] = useState(false)
  const [selected, setSelected] = useState<any>(null)
  const [timetablePlans, setTimetablePlans] = useState<any[]>([])
  const requestVersion = useRef(0)

  function load() {
    const version = ++requestVersion.current
    setLoading(true)
    api.workflows(tab).then(r => {
      if (version !== requestVersion.current) return
      setWfs(Array.isArray(r?.workflows) ? r.workflows : [])
      setLoading(false)
    }).catch(() => {
      if (version === requestVersion.current) setLoading(false)
    })
  }
  useEffect(() => { load() }, [tab])
  useEffect(() => { if ([5, 10, 17].includes(user.office_n)) { Promise.all([api.timetablePlans(), api.sections(), api.courseOfferings(), api.academicConflicts()]).then(async ([p, s, o, c]) => { const entries = (await Promise.all((s.sections || []).map(async (x: any) => ({ x, t: (await api.sectionTimetable(x.id)).entries || [] })))).flatMap((z: any) => z.t.map((t: any) => ({ ...t, section: z.x }))); setTimetablePlans((p.plans || []).map((plan: any) => { const e = entries.find((x: any) => x.id === plan.timetable_entry_id), off = (o.offerings || []).find((x: any) => x.id === plan.offering_id); return { ...plan, entry: e, offering: off, conflict: (c.conflicts || []).some((x: any) => x.left.entry_id === plan.timetable_entry_id || x.right.entry_id === plan.timetable_entry_id) } })) }).catch(() => {}) } }, [user.office_n])

  async function timetableDecision(plan: any, action: string) {
    const reason = action === 'return' ? window.prompt('Return reason (required)') || '' : ''
    if (action === 'return' && !reason.trim()) return
    try {
      if (user.office_n === 10) await api.timetableHodDecision(plan.id, action === 'approve' ? 'approve' : 'return', reason)
      else if (user.office_n === 5) await api.timetableVpDecision(plan.id, action === 'approve' ? 'approve' : 'return', reason)
      const next = await api.timetablePlans(); setTimetablePlans(next.plans || [])
    } catch (e: any) { window.alert(e.message || 'Unable to update timetable workflow') }
  }

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

      {[5, 10].includes(user.office_n) && tab === 'inbox' && <TimetablePlans plans={timetablePlans} office={user.office_n} onDecision={timetableDecision} />}

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

function TimetablePlans({ plans, office, onDecision }: any) {
  const [detail, setDetail] = useState<any>(null)
  const visible = plans.filter((p: any) => office === 10 ? p.status === 'HOD Review' : office === 5 ? p.status === 'VP Review' : Boolean(p.submitted_by))
  return <><section className="card" style={{ marginBottom: 18 }}><div className="card-h"><h3>{office === 17 ? 'My Timetable Requests' : 'Timetable Reviews'}</h3></div>{!visible.length ? <Empty text={office === 17 ? 'No timetable submissions yet.' : 'No timetable plans are awaiting your review.'} /> : <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Course</th><th>Offering / Section</th><th>Faculty</th><th>Room / Schedule</th><th>Conflict</th><th>Status</th><th>Submitted / Updated</th><th /></tr></thead><tbody>{visible.map((p: any) => { const e=p.entry, s=e?.section, o=p.offering; return <tr key={p.id}><td><b>{s?.course_code || '—'}</b><small>{s?.course_title || '—'}</small></td><td>{o?.program_code || p.offering_id || '—'}<br />{s?.section || p.section_id}</td><td>{s?.faculty || '—'}</td><td>{e?.room || s?.room || '—'}<br />{e ? `${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][e.day_of_week]} ${e.start_time}–${e.end_time}` : '—'}</td><td><StatePill s={p.conflict ? 'Conflict' : 'Clear'} /></td><td><StatePill s={p.status} /></td><td>{p.submitted_by || '—'}<br />{p.updated_at ? new Date(p.updated_at).toLocaleString() : '—'}</td><td><button className="btn btn-out" onClick={() => setDetail(p)}>Details</button>{office === 10 && p.status === 'HOD Review' && <><button className="btn btn-out" onClick={() => onDecision(p, 'approve')}>Forward to VP</button><button className="btn btn-out" onClick={() => onDecision(p, 'return')}>Return</button></>}{office === 5 && p.status === 'VP Review' && <><button className="btn btn-out" onClick={() => onDecision(p, 'approve')}>Approve</button><button className="btn btn-out" onClick={() => onDecision(p, 'return')}>Return</button></>}</td></tr>})}</tbody></table></div>}</section>{detail && <div className="modal-bg" onClick={() => setDetail(null)}><div className="modal" onClick={e => e.stopPropagation()}><div className="modal-h"><h3>Timetable Details</h3><button className="close-x" onClick={() => setDetail(null)}>×</button></div><div className="modal-b"><p><b>{detail.entry?.section?.course_code}</b> · {detail.entry?.section?.course_title}</p><p>Offering: {detail.offering?.program_code || detail.offering_id} · Section: {detail.entry?.section?.section || detail.section_id}</p><p>Faculty: {detail.entry?.section?.faculty || '—'} · Room: {detail.entry?.room || '—'}</p><p>Schedule: {detail.entry ? `${['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][detail.entry.day_of_week]} ${detail.entry.start_time}–${detail.entry.end_time}` : '—'}</p><p>Conflict: {detail.conflict ? 'Conflict' : 'Clear'} · Status: {detail.status}</p><p>Submitted by: {detail.submitted_by || '—'} · Updated: {detail.updated_at ? new Date(detail.updated_at).toLocaleString() : '—'}</p><p>Reason: {detail.reason || '—'}</p></div></div></div>}</>
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
            {data.escalation && <Meta label="Escalates to"><span className="mono">{data.escalation}</span></Meta>}
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
                {data.process_key !== 'attendance_correction' && <button className="btn btn-teal" disabled={busy} onClick={() => decide('review')}>Review</button>}
                <button className="btn btn-brass" disabled={busy} onClick={() => decide('approve')}>Approve</button>
                {data.state === 'approved' && data.process_key !== 'attendance_correction' && <button className="btn btn-solid" disabled={busy} onClick={() => decide('execute')}>Execute</button>}
                <button className="btn btn-rose" disabled={busy} onClick={() => decide('reject')}>Reject</button>
                {data.process_key !== 'attendance_correction' && <button className="btn btn-out" disabled={busy} onClick={() => decide('escalate')}>Escalate</button>}
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
