import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, Empty } from './ui'

export default function AuditView() {
  const [rows, setRows] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [verify, setVerify] = useState<any>(null)
  const [verifying, setVerifying] = useState(false)
  const [query, setQuery] = useState('')
  const [outcome, setOutcome] = useState('ALL')

  function load() { setLoading(true); api.audit().then(r => { setRows(r.entries || []); setLoading(false) }).catch(() => setLoading(false)) }
  useEffect(load, [])

  async function runVerify() {
    setVerifying(true)
    try {
      const r = await api.verifyAudit()
      setVerify(r)
    } finally {
      setVerifying(false)
    }
  }

  const outColor = (o: string) => o === 'ALLOW' ? 'var(--teal)' : o === 'DENY' ? 'var(--rose)' : o === 'ESCALATE' ? 'var(--amber)' : '#6f7fd4'
  const normalizedQuery = query.trim().toLowerCase()
  const filteredRows = rows.filter(e => {
    const matchesOutcome = outcome === 'ALL' || e.outcome === outcome
    const matchesQuery = !normalizedQuery || [e.actor, e.action, e.reason, e.outcome, e.hash].join(' ').toLowerCase().includes(normalizedQuery)
    return matchesOutcome && matchesQuery
  })
  const count = (value: string) => rows.filter(e => e.outcome === value).length

  return (
    <div className="fade-in audit-page">
      <div className="page-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1>Audit & integrity</h1>
          <p>Trace authority decisions, investigate outcomes, and verify the hash-chained ledger.</p>
        </div>
        <div className="audit-head-actions"><button className="btn btn-out" onClick={load} disabled={loading}>Refresh</button><button className="btn btn-brass" onClick={runVerify} disabled={verifying}>{verifying ? 'Verifying...' : 'Verify chain integrity'}</button></div>
      </div>

      {verify && (
        <div className={`audit-integrity ${verify.intact ? 'intact' : 'broken'}`}>
          <span className="audit-integrity-mark">{verify.intact ? 'OK' : '!'}</span>
          <div><b>{verify.intact ? 'Chain intact' : 'Chain broken'}</b><span>{verify.count} entries verified{verify.intact ? ' - no tampering detected.' : ` - break at entry ${verify.broken_at}.`}</span></div>
          <small>Checked just now</small>
        </div>
      )}

      <div className="audit-summary">
        <button className={`audit-summary-card ${outcome === 'ALL' ? 'active' : ''}`} onClick={() => setOutcome('ALL')} type="button"><span>Total events</span><b>{rows.length}</b><small>Loaded from ledger</small></button>
        <button className={`audit-summary-card allow ${outcome === 'ALLOW' ? 'active' : ''}`} onClick={() => setOutcome('ALLOW')} type="button"><span>Allowed</span><b>{count('ALLOW')}</b><small>Successful decisions</small></button>
        <button className={`audit-summary-card deny ${outcome === 'DENY' ? 'active' : ''}`} onClick={() => setOutcome('DENY')} type="button"><span>Denied</span><b>{count('DENY')}</b><small>Blocked decisions</small></button>
        <button className={`audit-summary-card escalate ${outcome === 'ESCALATE' ? 'active' : ''}`} onClick={() => setOutcome('ESCALATE')} type="button"><span>Escalated</span><b>{count('ESCALATE')}</b><small>Needs higher authority</small></button>
      </div>

      {loading ? <Spinner /> : (
        <div className="card audit-ledger">
          <div className="audit-ledger-head"><div><h3>Decision ledger</h3><p>{filteredRows.length} of {rows.length} events shown</p></div><label className="audit-search"><span>Find in ledger</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Actor, action, reason, hash..." aria-label="Find in audit ledger" /></label></div>
          <div className="tbl-scroll">
            {filteredRows.length === 0 ? <Empty icon="LOG" text={rows.length ? 'No audit entries match these filters.' : 'No audit entries yet. Decisions will be recorded here as workflows run.'} /> : (
              <table className="tbl">
                <thead><tr><th>#</th><th>When</th><th>Actor</th><th>Action</th><th>Outcome</th><th>Reason</th><th>Hash</th></tr></thead>
                <tbody>
                  {filteredRows.map((e, i) => (
                    <tr key={e.id}>
                      <td className="mono" style={{ color: 'var(--txt-mute)' }}>{rows.length - i}</td>
                      <td className="mono" style={{ fontSize: 11.5 }}>{new Date(e.at).toLocaleString()}</td>
                      <td>{e.actor}</td>
                      <td><span className="mono" style={{ fontSize: 12 }}>{e.action}</span></td>
                      <td><span className="mono" style={{ fontWeight: 700, fontSize: 12, color: outColor(e.outcome) }}>{e.outcome}</span></td>
                      <td style={{ color: 'var(--txt-soft)', fontSize: 12.5, maxWidth: 260 }}>{e.reason}</td>
                      <td className="mono" style={{ fontSize: 10.5, color: 'var(--txt-mute)' }} title={e.hash}>{e.hash?.slice(0, 10)}…</td>
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
