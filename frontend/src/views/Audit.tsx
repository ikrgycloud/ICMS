import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, Empty } from './ui'

export default function AuditView() {
  const [rows, setRows] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [verify, setVerify] = useState<any>(null)
  const [verifying, setVerifying] = useState(false)

  function load() { api.audit().then(r => { setRows(r.entries); setLoading(false) }).catch(() => setLoading(false)) }
  useEffect(load, [])

  async function runVerify() {
    setVerifying(true)
    const r = await api.verifyAudit()
    setVerify(r); setVerifying(false)
  }

  const outColor = (o: string) => o === 'ALLOW' ? 'var(--teal)' : o === 'DENY' ? 'var(--rose)' : o === 'ESCALATE' ? 'var(--amber)' : '#6f7fd4'

  return (
    <div className="fade-in">
      <div className="page-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1>Audit log</h1>
          <p>Every authority decision is appended to a hash-chained ledger. Each entry seals the previous entry's hash, so any tampering breaks the chain.</p>
        </div>
        <button className="btn btn-brass" onClick={runVerify} disabled={verifying}>{verifying ? 'Verifying…' : '⛓ Verify chain integrity'}</button>
      </div>

      {verify && (
        <div style={{ borderRadius: 12, padding: '14px 18px', marginBottom: 18, background: verify.intact ? '#e8f6f1' : '#fbe9e4', border: `1.5px solid ${verify.intact ? 'var(--teal)' : 'var(--rose)'}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
<<<<<<< HEAD
            <span style={{ fontSize: 16 }}>{verify.intact ? '✓' : '✕'}</span>
=======
            <span style={{ fontSize: 20 }}>{verify.intact ? '✓' : '✕'}</span>
>>>>>>> 22ee34d (updated code to branch)
            <div>
              <div style={{ fontWeight: 600, color: verify.intact ? 'var(--teal-dk)' : 'var(--rose)' }}>
                {verify.intact ? 'Chain intact' : 'Chain broken'}
              </div>
<<<<<<< HEAD
              <div style={{ fontSize: 9, color: 'var(--txt-soft)' }}>
=======
              <div style={{ fontSize: 13, color: 'var(--txt-soft)' }}>
>>>>>>> 22ee34d (updated code to branch)
                {verify.count} entries verified{verify.intact ? ' — no tampering detected.' : ` — break at entry ${verify.broken_at}.`}
              </div>
            </div>
          </div>
        </div>
      )}

      {loading ? <Spinner /> : (
        <div className="card">
          <div className="tbl-scroll">
            {rows.length === 0 ? <Empty icon="⛓" text="No audit entries yet. Decisions will be recorded here as workflows run." /> : (
              <table className="tbl">
                <thead><tr><th>#</th><th>When</th><th>Actor</th><th>Action</th><th>Outcome</th><th>Reason</th><th>Hash</th></tr></thead>
                <tbody>
                  {rows.map((e, i) => (
                    <tr key={e.id}>
                      <td className="mono" style={{ color: 'var(--txt-mute)' }}>{rows.length - i}</td>
<<<<<<< HEAD
                      <td className="mono" style={{ fontSize: 8 }}>{new Date(e.at).toLocaleString()}</td>
                      <td>{e.actor}</td>
                      <td><span className="mono" style={{ fontSize: 8 }}>{e.action}</span></td>
                      <td><span className="mono" style={{ fontWeight: 700, fontSize: 8, color: outColor(e.outcome) }}>{e.outcome}</span></td>
                      <td style={{ color: 'var(--txt-soft)', fontSize: 8.5, maxWidth: 260 }}>{e.reason}</td>
                      <td className="mono" style={{ fontSize: 8, color: 'var(--txt-mute)' }} title={e.hash}>{e.hash?.slice(0, 10)}…</td>
=======
                      <td className="mono" style={{ fontSize: 11.5 }}>{new Date(e.at).toLocaleString()}</td>
                      <td>{e.actor}</td>
                      <td><span className="mono" style={{ fontSize: 12 }}>{e.action}</span></td>
                      <td><span className="mono" style={{ fontWeight: 700, fontSize: 12, color: outColor(e.outcome) }}>{e.outcome}</span></td>
                      <td style={{ color: 'var(--txt-soft)', fontSize: 12.5, maxWidth: 260 }}>{e.reason}</td>
                      <td className="mono" style={{ fontSize: 10.5, color: 'var(--txt-mute)' }} title={e.hash}>{e.hash?.slice(0, 10)}…</td>
>>>>>>> 22ee34d (updated code to branch)
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
