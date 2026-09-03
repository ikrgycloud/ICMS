import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, AuthChip } from './ui'

export default function Permissions({ user }: { user: any }) {
  const [perms, setPerms] = useState<any>(null), [verb, setVerb] = useState('approve'), [scope, setScope] = useState('department'), [amount, setAmount] = useState(''), [result, setResult] = useState<any>(null)
  const [checking, setChecking] = useState(false), [error, setError] = useState(''), [q, setQ] = useState(''), [filter, setFilter] = useState('')
  const load = () => { setError(''); api.myPermissions().then(setPerms).catch(() => setError('Unable to load Authority & Permissions.')) }
  useEffect(load, [])
  if (!perms && !error) return <Spinner />
  if (error) return <div className="empty-state"><h3>Unable to load Authority &amp; Permissions.</h3><p>Authority and permission information is currently unavailable.</p><button className="btn btn-crimson" onClick={load}>Retry</button></div>

  const authority = new Map(perms.permissions.map((permission: any) => [permission.verb, permission.authority]))
  const allVerbs = perms.all_verbs || []
  const verbs = allVerbs.filter((name: string) => (!q || `${name} ${authority.get(name) || ''}`.toLowerCase().includes(q.toLowerCase())) && (!filter || name.toLowerCase() === filter))
  const availableFilters = [...new Set(allVerbs.map((name: string) => name.toLowerCase()))].sort()
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
    <section className="authority-summary"><Summary label="Effective authority" value={`Level ${perms.level ?? '—'}`} detail={perms.scope_level ? 'Campus / Branch scope' : 'Not configured'} /><Summary label="Permission count" value={perms.permissions.length} detail="Granted permissions" /><Summary label="Scope" value={scopeValue} detail={perms.scope_ref || 'Not configured'} /><Summary label="Approval authority" value={perms.approval_limit != null ? `₹${perms.approval_limit.toLocaleString('en-IN')}` : 'Not configured'} detail="Configured approval limit" /></section>
    <div className="authority-grid">
      <section className="card authority-permissions"><div className="authority-card-head"><div><span>Permissions</span><h3>Granted permissions</h3></div><b>{perms.permissions.length} permissions</b></div><div className="authority-filter"><input className="inp" value={q} onChange={e => setQ(e.target.value)} placeholder="Search permissions..."/><select className="select" value={filter} onChange={e => setFilter(e.target.value)}><option value="">All permissions</option>{availableFilters.map((name: string) => <option value={name} key={name}>{name}</option>)}</select></div><div className="permission-chips">{verbs.map((name: string) => <div className="permission-chip" key={name}><span>{name}</span><AuthChip v={authority.get(name) || 'Not Allowed'} /></div>)}{!verbs.length && <div className="principal-empty"><b>No matching permissions.</b><p>Try a different search or filter.</p></div>}</div><div className="authority-context"><Context label="Campus" value={perms.scope_ref || 'Not configured'} /><Context label="Tenant" value={perms.tenant_id || 'Not configured'} /><Context label="Authority level" value={`L${perms.level ?? '—'} · Campus / Branch`} /></div></section>
      <section className="card authority-check"><div className="authority-card-head"><div><span>Authority engine</span><h3>Live authority check</h3><p>Simulate a decision using the same authority engine used by the application.</p></div></div><div className="authority-check-form"><label>Action<select className="select" value={verb} onChange={e => setVerb(e.target.value)}>{allVerbs.map((name: string) => <option key={name}>{name}</option>)}</select></label><label>Target scope<select className="select" value={scope} onChange={e => setScope(e.target.value)}>{['global', 'university', 'campus', 'faculty', 'department', 'program', 'section', 'individual'].map(name => <option key={name}>{name}</option>)}</select></label><label>Amount (₹, optional)<input className="inp mono" value={amount} onChange={e => setAmount(e.target.value)} placeholder="e.g. 300000" /></label><button className="btn btn-crimson" onClick={check} disabled={checking}>{checking ? 'Evaluating…' : 'Run authority check'}</button></div>{result && <AuthorityResult data={result} tone={resultTone} />}</section>
    </div>
  </div>
}

function Summary({ label, value, detail }: any) { return <div><span>{label}</span><b>{value}</b><small>{detail}</small></div> }
function Context({ label, value }: any) { return <div><span>{label}</span><b>{value}</b></div> }
function AuthorityResult({ data, tone }: any) { const fields = [['Authority', data.authority], ['Scope', data.scope], ['Required permission', data.required_permission], ['Approval limit', data.approval_limit], ['Workflow state', data.workflow_state], ['Delegation', data.delegation], ['Validity', data.validity], ['Escalates to', data.escalate_to]].filter(([, value]) => value != null && value !== ''); return <div className={`authority-result ${tone}`}><div className="authority-result-title"><span>Decision</span><b>{data.outcome === 'ALLOW' ? 'Allowed' : data.outcome === 'DENY' ? 'Not allowed' : data.outcome}</b>{data.authority && <AuthChip v={data.authority} />}</div>{data.reason && <p>{data.reason}</p>}{fields.length > 0 && <div className="authority-result-fields">{fields.map(([label, value]) => <div key={label as string}><span>{label}</span><b>{String(value)}</b></div>)}</div>}</div> }
