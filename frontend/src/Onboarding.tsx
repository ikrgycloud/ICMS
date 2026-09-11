import { useEffect, useState } from 'react'
import { api } from './api'
import './landing.css'

function EyeIcon({ shown }: { shown: boolean }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.7"/>{shown && <path d="M4 4l16 16"/>}</svg>
}

export default function Onboarding() {
  const token = new URLSearchParams(window.location.search).get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [message, setMessage] = useState('')
  const [username, setUsername] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (token) api.onboardingContext(token).then((r: any) => setUsername(r.username)).catch((e: any) => setMessage(e.message || 'This onboarding link is invalid or expired.')) }, [token])
  async function submit() {
    if (!token) return setMessage('This onboarding link is missing its security token.')
    if (password.length < 10) return setMessage('Choose a password of at least 10 characters.')
    if (password !== confirm) return setMessage('The passwords do not match.')
    setBusy(true); setMessage('')
    try { await api.completeOnboarding(token, password); setMessage('Password set successfully. Your Chairman must activate the account before you can sign in.'); setPassword(''); setConfirm('') }
    catch (e: any) { setMessage(e.message || 'This onboarding link is invalid or expired.') }
    finally { setBusy(false) }
  }
  const passwordField = (label: string, value: string, setValue: (value: string) => void, shown: boolean, setShown: (shown: boolean) => void, onKeyDown?: any) => <div className="auth-field"><label>{label}</label><div className="password-input"><input type={shown ? 'text' : 'password'} value={value} onChange={e => setValue(e.target.value)} onKeyDown={onKeyDown}/><button type="button" className="password-toggle" aria-label={shown ? 'Hide password' : 'Show password'} title={shown ? 'Hide password' : 'Show password'} onClick={() => setShown(!shown)}><EyeIcon shown={shown}/></button></div></div>
  return <div className="auth"><div className="auth-brandside"><div className="auth-brand"><div className="lp-seal">IC</div><div><div className="auth-brand-name">ICMS</div><div className="auth-brand-sub">Account setup</div></div></div></div><div className="auth-formside"><div className="auth-card"><h1>Set your password</h1><p className="sub">Use the secure link delivered to your account email. It can be used only once.</p>{message && <div className="auth-err">{message}</div>}{username && <div className="auth-field"><label>Username</label><input value={username} readOnly /></div>}{passwordField('New password', password, setPassword, showPassword, setShowPassword)}{passwordField('Confirm password', confirm, setConfirm, showConfirm, setShowConfirm, (e: any) => e.key === 'Enter' && submit())}<button className="auth-submit" onClick={submit} disabled={busy}>{busy ? 'Saving…' : 'Set password'}</button><p className="sub" style={{marginTop: 20}}><a href="/">Back to sign in</a></p></div></div></div>
}
