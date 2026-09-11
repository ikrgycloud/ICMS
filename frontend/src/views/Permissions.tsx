import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, AuthChip } from './ui'

export default function Permissions({ user }: { user: any }) {
  const [perms, setPerms] = useState<any>(null)
  const [verb, setVerb] = useState('approve')
  const [scope, setScope] = useState('department')
  const [amount, setAmount] = useState('')
  const [result, setResult] = useState<any>(null)
  const [checking, setChecking] = useState(false)

  useEffect(() => { api.myPermissions().then(setPerms).catch(() => {}) }, [])
  if (!perms) return <Spinner />

  async function check() {
    setChecking(true)
    try {
      const r = await api.authzCheck(verb, scope, amount ? parseFloat(amount) : undefined)
      setResult(r)
    } catch (e: any) { setResult({ outcome: 'DENY', reason: e.message }) }
    setChecking(false)
  }
  const outColor = (o: string) => o === 'ALLOW' ? 'var(--teal)' : o === 'DENY' ? 'var(--rose)' : o === 'ESCALATE' ? 'var(--amber)' : '#6f7fd4'

  return (
    <div className="fade-in">
      <div className="page-head">
        <h1>My authority</h1>
        <p>Your effective authority is computed from role, permission, scope, approval limit, delegation, workflow state and time validity — never a static list.</p>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-h"><h3>Granted permissions</h3><span className="hint">{perms.permissions.length} verbs</span></div>
          <div className="card-pad">
            <div className="perm-grid">
              {perms.permissions.map((p: any) => (
                <div key={p.verb} className="perm-item">
                  <span className="mono" style={{ fontSize: 13 }}>{p.verb}</span>
                  <AuthChip v={p.authority} />
                </div>
              ))}
            </div>
            <div style={{ marginTop: 18, paddingTop: 16, borderTop: '1px solid #f2efe8', display: 'flex', gap: 26, flexWrap: 'wrap' }}>
              <div><div className="mini-lbl">Scope level</div><span className="mono" style={{ fontSize: 14 }}>{perms.scope_level}</span></div>
              <div><div className="mini-lbl">Auth level</div><span className="mono" style={{ fontSize: 14 }}>L{perms.level}</span></div>
              <div><div className="mini-lbl">Approval limit</div><span className="mono" style={{ fontSize: 14 }}>{perms.approval_limit != null ? '₹' + perms.approval_limit.toLocaleString('en-IN') : 'none set'}</span></div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-h"><h3>Live authority check</h3><span className="hint">/api/authz/check</span></div>
          <div className="card-pad">
            <p style={{ fontSize: 13.5, color: 'var(--txt-soft)', marginBottom: 16 }}>Simulate a decision the way the engine evaluates it in real time.</p>
            <div className="form-row"><label>Action</label>
              <select className="select" value={verb} onChange={e => setVerb(e.target.value)}>
                {perms.all_verbs.map((v: string) => <option key={v}>{v}</option>)}
              </select>
            </div>
            <div className="form-row"><label>Target scope</label>
              <select className="select" value={scope} onChange={e => setScope(e.target.value)}>
                {['global', 'university', 'campus', 'faculty', 'department', 'program', 'section', 'individual'].map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div className="form-row"><label>Amount (₹, optional)</label>
              <input className="inp mono" value={amount} onChange={e => setAmount(e.target.value)} placeholder="e.g. 300000" />
            </div>
            <button className="btn btn-brass" style={{ width: '100%' }} onClick={check} disabled={checking}>{checking ? 'Evaluating…' : 'Run authority check'}</button>

            {result && (
              <div style={{ marginTop: 16, borderRadius: 12, padding: '14px 16px', background: '#fbf9f3', border: `1.5px solid ${outColor(result.outcome)}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className="mono" style={{ fontWeight: 700, color: outColor(result.outcome) }}>{result.outcome}</span>
                  {result.authority && <AuthChip v={result.authority} />}
                  {result.escalate_to && <span className="tag" style={{ background: '#fdeee4', color: '#c05a1e' }}>→ {result.escalate_to}</span>}
                </div>
                <div style={{ fontSize: 13.5, color: 'var(--txt-soft)', marginTop: 7 }}>{result.reason}</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
