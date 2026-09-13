import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, AuthChip } from './ui'

export default function Permissions({ user }: { user: any }) {
  if (user?.office_n === 4) return <PrincipalPermissions />
  return <GenericPermissions />
}

function GenericPermissions() {
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

function PrincipalPermissions() {
  const [perms, setPerms] = useState<any>(null), [verb, setVerb] = useState('approve'), [scope, setScope] = useState('department'), [amount, setAmount] = useState(''), [result, setResult] = useState<any>(null)
  const [checking, setChecking] = useState(false), [error, setError] = useState(''), [q, setQ] = useState(''), [filter, setFilter] = useState('')
  const load = () => { setError(''); api.myPermissions().then(setPerms).catch(() => setError('Unable to load Authority & Permissions.')) }
  useEffect(load, [])
  if (!perms && !error) return <Spinner />
  if (error) return <div className="empty-state"><h3>Unable to load Authority &amp; Permissions.</h3><p>Authority and permission information is currently unavailable.</p><button className="btn btn-crimson" onClick={load}>Retry</button></div>

  const authority = new Map<string, string>((perms.permissions || []).map((permission: any): [string, string] => [String(permission.verb), String(permission.authority)]))
  const allVerbs = perms.all_verbs || []
  const verbs = allVerbs.filter((name: string) => (!q || `${name} ${authority.get(name) || ''}`.toLowerCase().includes(q.toLowerCase())) && (!filter || name.toLowerCase() === filter))
  const availableFilters: string[] = [...new Set<string>(allVerbs.map((name: string) => name.toLowerCase()))].sort()
  const scopeValue = perms.scope_level === 'campus' ? 'One Campus Only' : (perms.scope_level || 'Not configured')

  async function check() {
    setChecking(true)
    try { setResult(await api.authzCheck(verb, scope, amount ? parseFloat(amount) : undefined)) }
    catch (e: any) { setResult({ outcome: 'DENY', reason: e.message }) }
    setChecking(false)
  }
  const resultTone = result?.outcome === 'ALLOW' ? 'allow' : result?.outcome === 'DENY' ? 'deny' : 'conditional'

  return <div className="fade-in principal-operations authority-page">
    <div className="authority-head"><div><h1>Authority &amp; Permissions</h1><p>Review your effective permissions, scope and approval authority.</p></div><span className="authority-active"><i />Authority active</span></div>
    <div className="authority-summary"><div><span>Authority level</span><b>L{perms.level || '—'}</b><small>{perms.role || 'Principal authority'}</small></div><div><span>Scope</span><b>{scopeValue}</b><small>Applied to every live check</small></div><div><span>Approval limit</span><b>{perms.approval_limit != null ? `₹${Number(perms.approval_limit).toLocaleString('en-IN')}` : 'No limit set'}</b><small>Effective approval ceiling</small></div><div><span>Granted verbs</span><b>{perms.permissions?.length || 0}</b><small>Permissions available</small></div></div>
    <div className="authority-grid">
      <section className="card authority-permissions"><div className="authority-card-head"><div><span>Effective access</span><h3>Granted permissions</h3><p>Permissions resolved from your role, authority level, scope and active delegations.</p></div><b>{perms.permissions?.length || 0} verbs</b></div><div className="authority-filter"><input className="inp" value={q} onChange={event => setQ(event.target.value)} placeholder="Search permissions"/><select className="select" value={filter} onChange={event => setFilter(event.target.value)}><option value="">All permissions</option>{availableFilters.map(value => <option key={value}>{value}</option>)}</select></div><div className="permission-chips">{verbs.length ? verbs.map((name: string) => <div className="permission-chip" key={name}><span>{name.replace(/_/g, ' ')}</span><AuthChip v={authority.get(name) || 'Not granted'} /></div>) : <p className="principal-empty">No permissions match your filters.</p>}</div><div className="authority-context"><div><span>Scope level</span><b>{scopeValue}</b></div><div><span>Auth level</span><b>L{perms.level || '—'}</b></div><div><span>Approval limit</span><b>{perms.approval_limit != null ? `₹${Number(perms.approval_limit).toLocaleString('en-IN')}` : 'None set'}</b></div></div></section>
      <section className="card authority-check"><div className="authority-card-head"><div><span>Decision engine</span><h3>Live authority check</h3><p>Simulate the same authority evaluation used by protected actions.</p></div><b>Live</b></div><div className="authority-check-form"><label>Action<select className="select" value={verb} onChange={event => setVerb(event.target.value)}>{allVerbs.map((value: string) => <option key={value}>{value}</option>)}</select></label><label>Target scope<select className="select" value={scope} onChange={event => setScope(event.target.value)}>{['global', 'university', 'campus', 'faculty', 'department', 'program', 'section', 'individual'].map(value => <option key={value}>{value}</option>)}</select></label><label>Amount (₹, optional)<input className="inp mono" value={amount} onChange={event => setAmount(event.target.value)} placeholder="e.g. 300000" /></label><button className="btn btn-crimson" onClick={check} disabled={checking}>{checking ? 'Evaluating...' : 'Run authority check'}</button></div>{result && <div className={`authority-result ${resultTone}`}><div className="authority-result-title"><span>Decision</span><b>{result.outcome}</b>{result.authority && <AuthChip v={result.authority} />}</div><p>{result.reason}</p><div className="authority-result-fields"><div><span>Requested action</span><b>{verb}</b></div><div><span>Target scope</span><b>{scope}</b></div>{result.escalate_to && <div><span>Escalates to</span><b>{result.escalate_to}</b></div>}</div></div>}</section>
    </div>
  </div>
}
