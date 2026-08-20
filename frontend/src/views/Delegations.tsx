import { useEffect, useState } from 'react'
import { api } from '../api'
<<<<<<< HEAD
import { Empty, Modal, Spinner, money } from '../modules/kit'
=======
import { Spinner, Empty } from './ui'
>>>>>>> 22ee34d (updated code to branch)

export default function Delegations({ user }: { user: any }) {
  const [rows, setRows] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [show, setShow] = useState(false)
<<<<<<< HEAD
  const [selected, setSelected] = useState<any>(null)

  function load() {
    api.delegations()
      .then(r => {
        setRows(r.delegations || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  useEffect(load, [])

  async function revoke(id: string) {
    await api.revokeDelegation(id)
    load()
=======

  function load() { api.delegations().then(r => { setRows(r.delegations); setLoading(false) }).catch(() => setLoading(false)) }
  useEffect(load, [])

  async function revoke(id: string) {
    await api.revokeDelegation(id); load()
>>>>>>> 22ee34d (updated code to branch)
  }

  return (
    <div className="fade-in">
      <div className="page-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1>Delegation</h1>
<<<<<<< HEAD
          <p>Authority you grant is time-bound, scoped, revocable and audited. Delegations assigned to your login also appear here for review.</p>
=======
          <p>Authority you grant is time-bound, scoped, revocable and audited. Revoked grants stop immediately; expired grants simply lapse.</p>
>>>>>>> 22ee34d (updated code to branch)
        </div>
        <button className="btn btn-brass" onClick={() => setShow(true)}>+ Delegate authority</button>
      </div>

      {loading ? <Spinner /> : (
        <div className="card">
          <div className="tbl-scroll">
<<<<<<< HEAD
            {rows.length === 0 ? <Empty icon="[]" text="No delegations yet. Grant a colleague time-bound authority to cover for you." /> : (
              <table className="tbl">
                <thead><tr><th>From</th><th>To</th><th>Delegated Access</th><th>Limit</th><th>Window</th><th>Status</th><th></th></tr></thead>
                <tbody>
                  {rows.map(d => (
                    <tr key={d.id}>
                      <td>{d.from_name || d.from}</td>
                      <td style={{ fontWeight: 600 }}>{d.to_name || d.to}</td>
                      <td><span className="tag" style={{ background: '#f3ecfa', color: '#7a4bb0' }}>{humanizeAccess(d.authority_label || d.authority)}</span></td>
                      <td className="mono">{money(d.limit)}</td>
                      <td className="mono" style={{ fontSize: 8 }}>{formatDate(d.start)} to {formatDate(d.end)}</td>
=======
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
>>>>>>> 22ee34d (updated code to branch)
                      <td>
                        <span className="pill" style={d.active ? { background: '#e3f4ef', color: '#16785f' } : { background: '#f4f2ef', color: '#a29a89' }}>
                          {d.active ? 'active' : d.status}
                        </span>
                      </td>
<<<<<<< HEAD
                      <td style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                        <button className="btn btn-out" onClick={() => setSelected(d)}>View</button>
                        {d.from === user.username && d.active && <button className="btn btn-rose" onClick={() => revoke(d.id)}>Revoke</button>}
                      </td>
=======
                      <td>{d.from === user.username && d.active && <button className="btn btn-rose" onClick={() => revoke(d.id)}>Revoke</button>}</td>
>>>>>>> 22ee34d (updated code to branch)
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {show && <DelegateModal onClose={() => setShow(false)} onDone={() => { setShow(false); load() }} />}
<<<<<<< HEAD
      {selected && <DelegationViewModal row={selected} user={user} onClose={() => setSelected(null)} />}
=======
>>>>>>> 22ee34d (updated code to branch)
    </div>
  )
}

<<<<<<< HEAD
function DelegationViewModal({ row, user, onClose }: { row: any; user: any; onClose: () => void }) {
  const attachmentHref = row?.attachment?.data_b64
    ? `data:${row.attachment.mime_type || 'application/octet-stream'};base64,${row.attachment.data_b64}`
    : ''

  return (
    <Modal
      title="Delegation Details"
      onClose={onClose}
      footer={<button className="btn btn-out" onClick={onClose} type="button">Close</button>}
    >
      <div style={{ display: 'grid', gap: 16 }}>
        <div className="chair-delegation-detail-grid">
          <Meta label="Reference">{row.reference_code || '-'}</Meta>
          <Meta label="Policy Type">{row.policy_type || 'General'}</Meta>
          <Meta label="Delegated Access">{humanizeAccess(row.authority_label || row.authority)}</Meta>
          <Meta label="Limit">{money(row.limit)}</Meta>
        </div>

        <div className="chair-delegation-note">
          <strong>{row.subject || 'Delegated authority'}</strong>
          <span>{row.description || row.reason || 'No additional note was captured for this delegation.'}</span>
        </div>

        <div className="chair-delegation-detail-grid">
          <Meta label="Granted By">{row.from_name || row.from}</Meta>
          <Meta label="Assigned To">{row.to_name || row.to}</Meta>
          <Meta label="Role / Office">{row.to_office || row.to_role || '-'}</Meta>
          <Meta label="Status">{row.status_meta?.label || row.status}</Meta>
        </div>

        <div className="chair-delegation-preview">
          <div className="chair-delegation-preview-body">
            <small>Delegation scope</small>
            <span>{row.resource_scope_label || row.resource_scope || '*'}</span>
          </div>
          <div className="chair-delegation-preview-body">
            <small>Validity</small>
            <span>{formatDate(row.start)} to {formatDate(row.end)}</span>
          </div>
          <div className="chair-delegation-preview-body">
            <small>Delegated to type</small>
            <span>{row.delegated_to_type || '-'}</span>
          </div>
          <div className="chair-delegation-preview-body">
            <small>Review frequency</small>
            <span>{row.review_frequency_label || 'None'}</span>
          </div>
          {!!row.notes && (
            <div className="chair-delegation-preview-body">
              <small>Notes / Conditions</small>
              <span>{row.notes}</span>
            </div>
          )}
          {!!attachmentHref && (
            <div className="chair-delegation-preview-body">
              <small>Attachment</small>
              <a className="chair-delegation-link" href={attachmentHref} download={row.attachment.name}>{row.attachment.name}</a>
            </div>
          )}
          {row.to === user.username && (
            <div className="chair-delegation-preview-body">
              <small>Recipient visibility</small>
              <span>This delegation is active in your login and can be used where the delegated scope matches.</span>
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}

=======
>>>>>>> 22ee34d (updated code to branch)
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
<<<<<<< HEAD

  useEffect(() => { api.offices().then(setOffices).catch(() => {}) }, [])
  const options = offices.filter(o => DEMO[o.n]).map(o => ({ u: DEMO[o.n], label: `${DEMO[o.n]} - ${o.name}` }))

  async function submit() {
    if (!to) {
      setErr('Choose a recipient')
      return
    }
    setBusy(true)
    setErr('')
    try {
      await api.createDelegation({ to_username: to, authority, days: parseInt(days), limit: limit ? parseFloat(limit) : null, reason })
      onDone()
    } catch (e: any) {
      setErr(e.message)
      setBusy(false)
    }
=======
  useEffect(() => { api.offices().then(setOffices).catch(() => {}) }, [])
  const options = offices.filter(o => DEMO[o.n]).map(o => ({ u: DEMO[o.n], label: `${DEMO[o.n]} · ${o.name}` }))

  async function submit() {
    if (!to) { setErr('Choose a recipient'); return }
    setBusy(true); setErr('')
    try {
      await api.createDelegation({ to_username: to, authority, days: parseInt(days), limit: limit ? parseFloat(limit) : null, reason })
      onDone()
    } catch (e: any) { setErr(e.message); setBusy(false) }
>>>>>>> 22ee34d (updated code to branch)
  }

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
<<<<<<< HEAD
        <div className="modal-h"><h3>Delegate authority</h3><button className="close-x" onClick={onClose}>x</button></div>
=======
        <div className="modal-h"><h3>Delegate authority</h3><button className="close-x" onClick={onClose}>×</button></div>
>>>>>>> 22ee34d (updated code to branch)
        <div className="modal-b">
          {err && <div className="err-box">{err}</div>}
          <div className="form-row">
            <label>Delegate to</label>
            <select className="select" value={to} onChange={e => setTo(e.target.value)}>
<<<<<<< HEAD
              <option value="">Choose recipient...</option>
=======
              <option value="">Choose recipient…</option>
>>>>>>> 22ee34d (updated code to branch)
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
<<<<<<< HEAD
              <label>Amount limit (optional)</label>
=======
              <label>Amount limit (₹, optional)</label>
>>>>>>> 22ee34d (updated code to branch)
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
<<<<<<< HEAD
          <button className="btn btn-brass" onClick={submit} disabled={busy}>{busy ? 'Granting...' : 'Grant delegation'}</button>
=======
          <button className="btn btn-brass" onClick={submit} disabled={busy}>{busy ? 'Granting…' : 'Grant delegation'}</button>
>>>>>>> 22ee34d (updated code to branch)
        </div>
      </div>
    </div>
  )
}
<<<<<<< HEAD

function Meta({ label, children }: any) {
  return (
    <div className="chair-delegation-meta">
      <small>{label}</small>
      <strong>{children}</strong>
    </div>
  )
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function humanizeAccess(value: string) {
  const raw = String(value || '').trim()
  if (!raw) return '-'
  return raw
    .split(':')
    .map(part => part.replace(/_/g, ' '))
    .map(part => part.replace(/\b\w/g, char => char.toUpperCase()))
    .join(' / ')
}
=======
>>>>>>> 22ee34d (updated code to branch)
