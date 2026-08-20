import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, Empty } from './ui'

export default function Delegations({ user }: { user: any }) {
  const [rows, setRows] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [show, setShow] = useState(false)

  function load() { api.delegations().then(r => { setRows(r.delegations); setLoading(false) }).catch(() => setLoading(false)) }
  useEffect(load, [])

  async function revoke(id: string) {
    await api.revokeDelegation(id); load()
  }

  return (
    <div className="fade-in">
      <div className="page-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1>Delegation</h1>
          <p>Authority you grant is time-bound, scoped, revocable and audited. Revoked grants stop immediately; expired grants simply lapse.</p>
        </div>
        <button className="btn btn-brass" onClick={() => setShow(true)}>+ Delegate authority</button>
      </div>

      {loading ? <Spinner /> : (
        <div className="card">
          <div className="tbl-scroll">
            {rows.length === 0 ? <Empty icon="⤳" text="No delegations yet. Grant a colleague time-bound authority to cover for you." /> : (
              <table className="tbl">
                <thead><tr><th>From</th><th>To</th><th>Authority</th><th>Limit</th><th>Window</th><th>Status</th><th></th></tr></thead>
                <tbody>
                  {rows.map(d => (
                    <tr key={d.id}>
                      <td>{d.from}</td>
                      <td style={{ fontWeight: 600 }}>{d.to}</td>
                      <td><span className="tag" style={{ background: '#f3ecfa', color: '#7a4bb0' }}>{d.authority === '*' ? 'all actions' : d.authority}</span></td>
                      <td className="mono">{d.limit ? '₹' + d.limit.toLocaleString('en-IN') : '—'}</td>
                      <td className="mono" style={{ fontSize: 11.5 }}>{new Date(d.start).toLocaleDateString()} → {new Date(d.end).toLocaleDateString()}</td>
                      <td>
                        <span className="pill" style={d.active ? { background: '#e3f4ef', color: '#16785f' } : { background: '#f4f2ef', color: '#a29a89' }}>
                          {d.active ? 'active' : d.status}
                        </span>
                      </td>
                      <td>{d.from === user.username && d.active && <button className="btn btn-rose" onClick={() => revoke(d.id)}>Revoke</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {show && <DelegateModal onClose={() => setShow(false)} onDone={() => { setShow(false); load() }} />}
    </div>
  )
}

function DelegateModal({ onClose, onDone }: any) {
  const [offices, setOffices] = useState<any[]>([])
  const [to, setTo] = useState('')
  const [authority, setAuthority] = useState('*')
  const [days, setDays] = useState('7')
  const [limit, setLimit] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const DEMO: Record<number, string> = {
    1: 'chairman', 2: 'vice_chairman', 3: 'campus_head', 4: 'principal', 5: 'vice_principal',
    6: 'dean_academics', 10: 'hod', 16: 'exam_controller', 22: 'finance_manager', 24: 'hr_manager',
    27: 'it_manager', 28: 'system_admin',
  }
  useEffect(() => { api.offices().then(setOffices).catch(() => {}) }, [])
  const options = offices.filter(o => DEMO[o.n]).map(o => ({ u: DEMO[o.n], label: `${DEMO[o.n]} · ${o.name}` }))

  async function submit() {
    if (!to) { setErr('Choose a recipient'); return }
    setBusy(true); setErr('')
    try {
      await api.createDelegation({ to_username: to, authority, days: parseInt(days), limit: limit ? parseFloat(limit) : null, reason })
      onDone()
    } catch (e: any) { setErr(e.message); setBusy(false) }
  }

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-h"><h3>Delegate authority</h3><button className="close-x" onClick={onClose}>×</button></div>
        <div className="modal-b">
          {err && <div className="err-box">{err}</div>}
          <div className="form-row">
            <label>Delegate to</label>
            <select className="select" value={to} onChange={e => setTo(e.target.value)}>
              <option value="">Choose recipient…</option>
              {options.map(o => <option key={o.u} value={o.u}>{o.label}</option>)}
            </select>
          </div>
          <div className="form-row">
            <label>Authority</label>
            <select className="select" value={authority} onChange={e => setAuthority(e.target.value)}>
              <option value="*">All actions</option>
              <option value="approve">Approve only</option>
              <option value="review">Review only</option>
            </select>
          </div>
          <div style={{ display: 'flex', gap: 14 }}>
            <div className="form-row" style={{ flex: 1 }}>
              <label>Duration (days)</label>
              <input className="inp mono" value={days} onChange={e => setDays(e.target.value)} />
            </div>
            <div className="form-row" style={{ flex: 1 }}>
              <label>Amount limit (₹, optional)</label>
              <input className="inp mono" value={limit} onChange={e => setLimit(e.target.value)} placeholder="none" />
            </div>
          </div>
          <div className="form-row">
            <label>Reason</label>
            <input className="inp" value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Covering during leave" />
          </div>
        </div>
        <div className="modal-f">
          <button className="btn btn-out" onClick={onClose}>Cancel</button>
          <button className="btn btn-brass" onClick={submit} disabled={busy}>{busy ? 'Granting…' : 'Grant delegation'}</button>
        </div>
      </div>
    </div>
  )
}
