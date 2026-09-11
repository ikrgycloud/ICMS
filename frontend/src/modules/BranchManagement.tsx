import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { PageHead, Spinner } from './kit'

const blank = { name: '', code: '', location: '', principal: { name: '', email: '', username: '' }, campus_head: { name: '', email: '', username: '' }, provision_all_offices: true, initial_password: '', confirm_password: '' }

export default function BranchManagement() {
  const [branches, setBranches] = useState<any[]>([]), [form, setForm] = useState<any>(blank)
  const [accounts, setAccounts] = useState<any[]>([]), [accountBranch, setAccountBranch] = useState('')
  const [developmentLink, setDevelopmentLink] = useState(''), [inviteMessage, setInviteMessage] = useState(''), [resendingId, setResendingId] = useState('')
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle'), [demoCopyId, setDemoCopyId] = useState(''), [demoCopyError, setDemoCopyError] = useState('')
  const [activatingId, setActivatingId] = useState('')
  const [lifecycleBranch, setLifecycleBranch] = useState<any>(null), [lifecycleStatus, setLifecycleStatus] = useState<'discontinued' | 'deactivated' | null>(null), [changingLifecycle, setChangingLifecycle] = useState(false)
  const resetCopyTimer = useRef<number | undefined>(undefined)
  const [open, setOpen] = useState(false), [loading, setLoading] = useState(true), [saving, setSaving] = useState(false)
  const [error, setError] = useState(''), [result, setResult] = useState<any>(null)
  const load = () => { setLoading(true); api.branches().then((r: any) => setBranches(r.branches || [])).catch((e: any) => setError(e.message || 'Unable to load branches.')).finally(() => setLoading(false)) }
  useEffect(load, [])
  const refreshAccounts = useCallback(async () => {
    try { const response = await api.branchUsers(accountBranch ? { branch: accountBranch } : {}); setAccounts(response.users || []) }
    catch { setAccounts([]) }
  }, [accountBranch])
  useEffect(() => { refreshAccounts() }, [refreshAccounts, result])
  const leader = (key: string, field: string, value: string) => setForm((f: any) => ({ ...f, [key]: { ...f[key], [field]: value } }))
  async function submit(event: any) {
    event.preventDefault(); setSaving(true); setError(''); setResult(null)
    try {
      const response = await api.provisionBranch(form)
      setResult({ ...response, created_users: (response.created_users || []).map(({ initial_password, ...user }: any) => user) })
      setOpen(false); setForm(blank); load()
    } catch (e: any) { setError(e.message || 'Branch provisioning failed.') }
    finally { setSaving(false) }
  }
  async function resend(account: any) {
    setError(''); setInviteMessage(''); setCopyState('idle'); setResendingId(account.id)
    try { const response = await api.resendBranchOnboarding(account.id); setDevelopmentLink(response.onboarding_url || ''); setInviteMessage('Onboarding invitation created.'); await refreshAccounts() }
    catch (e: any) { setError(e.message || 'Onboarding invitation could not be sent.') }
    finally { setResendingId('') }
  }
  async function copyDevelopmentLink() {
    if (!developmentLink || !navigator.clipboard?.writeText) { setCopyState('failed'); return }
    try { await navigator.clipboard.writeText(developmentLink); setCopyState('copied'); if (resetCopyTimer.current) window.clearTimeout(resetCopyTimer.current); resetCopyTimer.current = window.setTimeout(() => setCopyState('idle'), 2000) }
    catch { setCopyState('failed') }
  }
  async function copyDemoPassword(accountId: string) {
    setDemoCopyError('')
    if (!navigator.clipboard?.writeText) { setDemoCopyError('Unable to copy password. Please copy it manually.'); return }
    try { const response = await api.copyDevelopmentBranchPassword(accountId); await navigator.clipboard.writeText(response.password); setDemoCopyId(accountId); window.setTimeout(() => setDemoCopyId(''), 2000) }
    catch { setDemoCopyError('Unable to copy. Please copy the password manually.') }
  }
  async function copyLegacyPassword(accountId: string) {
    setDemoCopyError('')
    if (!navigator.clipboard?.writeText) { setDemoCopyError('Unable to copy. Please copy the password manually.'); return }
    try {
      const response = await api.copyLegacyBranchPassword(accountId)
      await navigator.clipboard.writeText(response.password)
      setDemoCopyId(accountId)
      window.setTimeout(() => setDemoCopyId(''), 2000)
    } catch (e: any) { setDemoCopyError(e.message || 'Unable to copy. Please copy the password manually.') }
  }
  async function createPassword(account: any) {
    setError(''); setInviteMessage(''); setCopyState('idle'); setResendingId(account.id)
    try { const response = await api.createBranchAccountPassword(account.id); setDevelopmentLink(response.onboarding_url || ''); setInviteMessage(response.message || 'Onboarding link created.'); await refreshAccounts() }
    catch (e: any) { setError(e.message || 'Onboarding invitation could not be created.') }
    finally { setResendingId('') }
  }
  async function activate(account: any) {
    setError(''); setActivatingId(account.id)
    try { await api.activateBranchUser(account.id); await refreshAccounts() }
    catch (e: any) { setError(e.message || 'Account could not be activated.') }
    finally { setActivatingId('') }
  }
  async function changeLifecycle() {
    if (!lifecycleBranch || !lifecycleStatus) return
    setChangingLifecycle(true); setError('')
    try {
      await api.setBranchLifecycle(lifecycleBranch.id, lifecycleStatus)
      setLifecycleBranch(null); setLifecycleStatus(null); load()
    } catch (e: any) { setError(e.message || 'Institute lifecycle could not be updated.') }
    finally { setChangingLifecycle(false) }
  }
  const statusLabel = (status: string) => ({ active: 'Active', discontinued: 'Discontinued', deactivated: 'Deactivated' }[String(status || '').toLowerCase()] || status || '-')
  const statusClass = (status: string) => String(status || '').toLowerCase() === 'active' ? 's-active' : String(status || '').toLowerCase() === 'discontinued' ? 's-pending' : 's-rejected'
  const lifecycleActions = (branch: any) => {
    const status = String(branch.status || '').toLowerCase()
    if (status === 'active') return <><button className="btn btn-out" type="button" onClick={() => { setLifecycleBranch(branch); setLifecycleStatus('discontinued') }}>Discontinue</button><button className="btn btn-out" type="button" onClick={() => { setLifecycleBranch(branch); setLifecycleStatus('deactivated') }}>Deactivate</button></>
    if (status === 'discontinued') return <button className="btn btn-out" type="button" onClick={() => { setLifecycleBranch(branch); setLifecycleStatus('deactivated') }}>Deactivate</button>
    return <span className="muted">No actions available</span>
  }
  const accountAction = (account: any) => {
    // Account status is the canonical activation lifecycle. Credential and
    // invitation fields describe setup history only and must never make an
    // already active account appear to need activation again.
    if (String(account.status || '').toLowerCase() === 'active') {
      return account.legacy_copy_password_available
        ? <button className="btn btn-out" type="button" onClick={() => copyLegacyPassword(account.id)}>{demoCopyId === account.id ? 'Copied' : 'Copy Password'}</button>
        : <button className="btn btn-out" type="button" onClick={() => copyDemoPassword(account.id)}>{demoCopyId === account.id ? 'Copied' : 'Copy Password'}</button>
    }
    if (account.credential_state === 'password_created') {
      return <button className="btn btn-out" type="button" disabled={activatingId === account.id} onClick={() => activate(account)}>{activatingId === account.id ? 'Activating...' : 'Activate'}</button>
    }
    if (account.credential_state === 'invitation_pending') {
      return <button className="btn btn-out" type="button" disabled={resendingId === account.id} onClick={() => resend(account)}>{resendingId === account.id ? 'Sending...' : 'Resend Onboarding'}</button>
    }
    if (account.credential_state === 'password_not_created') {
      return <button className="btn btn-out" type="button" disabled={resendingId === account.id} onClick={() => createPassword(account)}>{resendingId === account.id ? 'Creating...' : 'Create Password'}</button>
    }
    return <span className="muted">Password unavailable</span>
  }
  if (loading) return <Spinner />
  return <div className="fade-in principal-operations">
    <PageHead title="Branch Management" sub="Provision independently isolated branches using the institution's existing authority, workflow, and office definitions." right={<button className="btn btn-crimson" onClick={() => setOpen(true)}>Create New Branch</button>} />
    {error && <div className="hr-error">{error}<button className="btn btn-out" onClick={() => setError('')}>Dismiss</button></div>}
    {result && <section className="card hr-card"><div className="hr-card-head"><div><span>Provisioning complete</span><h3>{result.branch.name} is ready</h3></div><b>{result.created_user_count} users</b></div><p>Tenant <code>{result.branch.tenant_id}</code> and its canonical campus scope were created. Audit reference: <code>{result.audit_reference}</code>.</p></section>}
    <section className="card hr-card"><div className="hr-card-head"><div><span>Institution branches</span><h3>Provisioned branches</h3></div><b>{branches.length}</b></div>{!branches.length ? <div className="principal-empty"><b>No additional branches provisioned.</b><p>Main Campus remains unchanged and is not recreated here.</p></div> : <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Branch</th><th>Code</th><th>Location</th><th>Status</th><th>Campus scope</th><th>Actions</th></tr></thead><tbody>{branches.map(branch => <tr key={branch.id}><td><b>{branch.name}</b></td><td>{branch.code}</td><td>{branch.location || '-'}</td><td><span className={`pill ${statusClass(branch.status)}`}>{statusLabel(branch.status)}</span></td><td><code>{branch.campus_scope_id}</code></td><td><div className="branch-lifecycle-actions">{lifecycleActions(branch)}</div></td></tr>)}</tbody></table></div>}</section>
    <section className="card hr-card"><div className="hr-card-head"><div><span>User &amp; Office Accounts</span><h3>{accountBranch ? 'Branch accounts' : 'All branch accounts'}</h3></div><select className="select" value={accountBranch} onChange={e => setAccountBranch(e.target.value)}><option value="">All branches</option>{branches.map(b => <option value={b.tenant_id} key={b.id}>{b.name}</option>)}</select></div>
      {inviteMessage && <div className="branch-invite-success" aria-live="polite">{inviteMessage}</div>}{developmentLink && <div className="branch-onboarding-link"><div><b>Onboarding link created</b><p>The user sets their own password using this one-time link. The account remains invited until you activate it.</p></div><div className="branch-onboarding-link-row"><input className="inp" value={developmentLink} readOnly aria-label="Onboarding link" /><a className="btn btn-out" href={developmentLink} target="_blank" rel="noreferrer">Open Onboarding</a><button className="btn btn-out" type="button" onClick={copyDevelopmentLink}>{copyState === 'copied' ? 'Copied' : 'Copy Link'}</button></div><div className="branch-copy-status" aria-live="polite">{copyState === 'copied' ? 'Onboarding link copied.' : copyState === 'failed' ? 'Unable to copy onboarding link. Please copy it manually.' : ''}</div></div>}{demoCopyError && <div className="branch-copy-status" aria-live="polite">{demoCopyError}</div>}
      {!accounts.length ? <div className="principal-empty"><b>No branch accounts to show.</b><p>Provisioned users remain invited until secure onboarding is completed.</p></div> : <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Branch</th><th>Status</th><th>Last login</th><th></th></tr></thead><tbody>{accounts.map(a => <tr key={a.id}><td>{a.name}</td><td><code>{a.username}</code></td><td>{a.role}</td><td>{a.branch}</td><td><span className="pill">{a.status}</span></td><td>{a.last_login_at ? new Date(a.last_login_at).toLocaleString() : 'Never'}</td><td>{accountAction(a)}</td></tr>)}</tbody></table></div>}
    </section>
    {lifecycleBranch && lifecycleStatus && <div className="modal-bg branch-provision-bg"><div className="modal branch-provision-modal" role="dialog" aria-modal="true" aria-labelledby="branch-lifecycle-title"><div className="modal-h"><div><h3 id="branch-lifecycle-title">{lifecycleStatus === 'discontinued' ? 'Discontinue Institute' : 'Deactivate Institute'}</h3></div><button className="modal-x" type="button" aria-label="Close lifecycle confirmation" disabled={changingLifecycle} onClick={() => { setLifecycleBranch(null); setLifecycleStatus(null) }}>x</button></div><div className="modal-b branch-provision-body"><p>{lifecycleStatus === 'discontinued' ? 'Are you sure you want to discontinue this institute?' : 'This will deactivate the institute. Existing data will be preserved.'}</p><p><b>{lifecycleBranch.name}</b> will be marked as {statusLabel(lifecycleStatus)}. No users, academic records, workflows, notifications, or audit records will be deleted.</p></div><div className="modal-f"><button className="btn btn-out" type="button" disabled={changingLifecycle} onClick={() => { setLifecycleBranch(null); setLifecycleStatus(null) }}>Cancel</button><button className="btn btn-crimson" type="button" disabled={changingLifecycle} onClick={changeLifecycle}>{changingLifecycle ? 'Updating...' : lifecycleStatus === 'discontinued' ? 'Discontinue' : 'Deactivate'}</button></div></div></div>}
    {open && <div className="modal-bg branch-provision-bg"><form className="modal branch-provision-modal" onSubmit={submit} role="dialog" aria-modal="true" aria-labelledby="branch-provision-title"><div className="modal-h"><div><h3 id="branch-provision-title">Create New Branch</h3><p>Set up branch details and configure its leadership.</p></div><button className="modal-x" type="button" aria-label="Close branch creation form" onClick={() => setOpen(false)}>x</button></div><div className="modal-b branch-provision-body"><section className="branch-form-section"><div className="branch-form-section-head"><h4>Branch Details</h4><p>Basic information about the branch.</p></div><div className="branch-form-grid"><label className="form-row"><span>Branch name</span><input required className="inp" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label><label className="form-row"><span>Branch code</span><input required className="inp" placeholder="north-campus" value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} /></label><label className="form-row branch-form-full"><span>Location / details</span><input className="inp" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} /></label></div></section><section className="branch-form-section"><div className="branch-form-section-head"><h4>Initial Password</h4><p>Optional for this new branch only. In development, leaving it empty uses the demo fallback.</p></div><div className="branch-form-grid"><label className="form-row"><span>Initial password</span><input type="password" className="inp" value={form.initial_password} onChange={e => setForm({ ...form, initial_password: e.target.value })} /></label><label className="form-row"><span>Confirm password</span><input type="password" className="inp" value={form.confirm_password} onChange={e => setForm({ ...form, confirm_password: e.target.value })} /></label></div></section>{[["principal", "Principal", "Assign the principal responsible for this branch."], ["campus_head", "Campus Head", "Assign the campus head responsible for this branch."]].map(([key, label, description]) => <section className="branch-form-section" key={key}><div className="branch-form-section-head"><h4>{label}</h4><p>{description}</p></div><div className="branch-form-grid"><label className="form-row"><span>Name</span><input required className="inp" value={form[key].name} onChange={e => leader(key, 'name', e.target.value)} /></label><label className="form-row"><span>Username</span><input required className="inp" value={form[key].username} onChange={e => leader(key, 'username', e.target.value)} /></label><label className="form-row branch-form-full"><span>Email</span><input type="email" className="inp" value={form[key].email} onChange={e => leader(key, 'email', e.target.value)} /></label></div></section>)}<section className="branch-form-section"><div className="branch-form-section-head"><h4>Office Setup</h4><p>Choose the initial branch office configuration.</p></div><label className="form-row"><span>Office setup</span><select className="select" value={form.provision_all_offices ? 'all' : 'leadership'} onChange={e => setForm({ ...form, provision_all_offices: e.target.value === 'all' })}><option value="all">Provision all branch office users</option><option value="leadership">Provision Principal and Campus Head only</option></select></label></section></div><div className="modal-f"><button className="btn btn-out" type="button" onClick={() => setOpen(false)}>Cancel</button><button className="btn btn-crimson" disabled={saving}>{saving ? 'Provisioning...' : 'Create Branch'}</button></div></form></div>}
  </div>
}
