import { useEffect, useState } from 'react'
import { api, saveSession } from './api'
import './landing.css'

const LEVEL_COLORS: Record<number, string> = {
  1: '#6b4fb0', 2: '#3d5a99', 3: '#0d9488', 4: '#b98a3e',
  5: '#c07a2e', 6: '#2f9e6a', 7: '#3d6fb3', 8: '#8a1f2b',
}

const DEMO_USERNAMES: Record<number, string> = {
  1: 'chairman', 2: 'vice_chairman', 3: 'campus_head', 4: 'principal',
  5: 'vice_principal', 6: 'dean_academics', 7: 'dean_administration',
  8: 'dean_student_affairs', 9: 'dean_rd_iqac', 10: 'hod', 11: 'professor',
  12: 'associate_professor', 13: 'assistant_professor', 14: 'lecturer',
  15: 'admissions', 16: 'exam_controller', 17: 'academic_coordinator',
  18: 'placement', 19: 'librarian', 20: 'grievance', 21: 'discipline',
  22: 'finance_manager', 23: 'accounts', 24: 'hr_manager', 25: 'hr_executive',
  26: 'admin_manager', 27: 'it_manager', 28: 'system_admin', 29: 'maintenance',
  30: 'hostel_warden', 31: 'transport', 32: 'purchase', 33: 'store',
  34: 'security', 35: 'front_office', 36: 'student', 37: 'parent',
  38: 'alumni', 39: 'external_auditor', 40: 'governing_body',
}

export default function Login({ onDone, onBack }: { onDone: (u: any) => void; onBack: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [offices, setOffices] = useState<any[]>([])
  const [filter, setFilter] = useState(0)

  useEffect(() => { api.offices().then(setOffices).catch(() => {}) }, [])

  async function submit() {
    if (!username || !password) { setErr('Enter a username and password'); return }
    setBusy(true); setErr('')
    try {
      const r = await api.login(username, password)
      saveSession(r.token, r.user)
      onDone(r.user)
    } catch (e: any) {
      setErr(e.message || 'Invalid credentials')
      setBusy(false)
    }
  }

  function pick(n: number) {
    setUsername(DEMO_USERNAMES[n]); setPassword('demo123'); setErr('')
  }

  const shown = offices.filter(o => filter === 0 || o.level === filter)

  return (
    <div className="auth">
      <div className="auth-brandside">
        <button className="auth-back" onClick={onBack}>← Back to home</button>
        <div className="auth-brand">
          <div className="lp-seal">IC</div>
          <div>
            <div className="auth-brand-name">ICMS</div>
            <div className="auth-brand-sub">Management System</div>
          </div>
        </div>
        <div className="auth-hero">
          <h2>Welcome back to<br />your <em>university.</em></h2>
          <p className="lede">
            One sign-in, one workspace — built for exactly what your office does. Every
            role, from the Governing Body to the student portal, runs on a single
            authority engine that always knows who may do what.
          </p>
          <div className="auth-mini">
            <div><div className="num">40</div><div className="lbl">Offices</div></div>
            <div><div className="num">8</div><div className="lbl">Levels</div></div>
            <div><div className="num">268</div><div className="lbl">Roles</div></div>
          </div>
        </div>
      </div>

      <div className="auth-formside">
        <div className="auth-card">
          <h1>Sign in</h1>
          <p className="sub">Use any office account below, or type your credentials.</p>

          {err && <div className="auth-err">{err}</div>}

          <div className="auth-field">
            <label>Username</label>
            <input value={username} onChange={e => setUsername(e.target.value)}
              placeholder="e.g. student" onKeyDown={e => e.key === 'Enter' && submit()} />
          </div>
          <div className="auth-field">
            <label>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••" onKeyDown={e => e.key === 'Enter' && submit()} />
          </div>
          <button className="auth-submit" onClick={submit} disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in →'}
          </button>

          <div className="auth-demo-head">
            <span className="t">Demo accounts · {offices.length || 40} offices</span>
            <span className="p">password: demo123</span>
          </div>
          <div className="auth-lvlfilter">
            <button className={`auth-lvl ${filter === 0 ? 'on' : ''}`} onClick={() => setFilter(0)}>All</button>
            {[1, 2, 3, 4, 5, 6, 7, 8].map(l => (
              <button key={l} className={`auth-lvl ${filter === l ? 'on' : ''}`} onClick={() => setFilter(l)}>L{l}</button>
            ))}
          </div>
          <div className="auth-grid">
            {shown.map(o => (
              <button key={o.n} className="auth-acct" onClick={() => pick(o.n)}>
                <span className="idx" style={{ background: LEVEL_COLORS[o.level] }}>{o.n}</span>
                <div style={{ minWidth: 0 }}>
                  <div className="u">{DEMO_USERNAMES[o.n]}</div>
                  <div className="r">L{o.level} · {o.name}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
