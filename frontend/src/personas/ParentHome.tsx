import { useState, useEffect } from 'react'
import { api } from '../api'
import { Spinner, money } from '../modules/kit'

export default function ParentHome({ user }: { user: any }) {
  const [home, setHome] = useState<any>(null)
  useEffect(() => { api.parentHome().then(setHome).catch(() => {}) }, [])
  if (!home) return <Spinner />
  const w = home.ward
  const initials = (w.name || 'W').split(' ').map((x: string) => x[0]).slice(0, 2).join('')

  return (
    <div className="fade-in">
      <div className="profile-band">
        <div className="pb-avatar">{initials}</div>
        <div>
          <div className="pb-name">{w.name}</div>
          <div className="pb-meta"><span className="mono">{w.roll_no}</span> · {w.department} · Semester {w.semester}</div>
        </div>
        <div className="pb-stats">
          <div className="pb-stat"><div className="pb-stat-v">{w.cgpa?.toFixed(2)}</div><div className="pb-stat-l">CGPA</div></div>
          <div className="pb-stat"><div className="pb-stat-v">{w.attendance_pct ?? '—'}%</div><div className="pb-stat-l">Attendance</div></div>
        </div>
      </div>

      <div className="sod-banner">
        <span className="sod-i">👪</span>
        <div><b>Guardian view.</b> You are viewing the academic and financial summary for your ward only. This scope is enforced by the authority engine — you cannot see other students' records.</div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-h"><h3>Academic standing</h3></div>
          <div className="card-pad">
            <div className="snap"><span>CGPA</span><b>{w.cgpa?.toFixed(2)}</b></div>
            <div className="snap"><span>Attendance</span><b>{w.attendance_pct ?? '—'}%</b></div>
            <div className="snap"><span>Semester</span><b>{w.semester}</b></div>
            <div className="snap"><span>Department</span><b>{w.department}</b></div>
          </div>
        </div>
        <div className="card">
          <div className="card-h"><h3>Fee status</h3></div>
          <div className="card-pad">
            {home.fee ? (
              <>
                <div className="snap"><span>Total</span><b>{money(home.fee.amount)}</b></div>
                <div className="snap"><span>Paid</span><b style={{ color: 'var(--teal-dk)' }}>{money(home.fee.paid)}</b></div>
                <div className="snap"><span>Balance</span><b style={{ color: home.fee.balance > 0 ? 'var(--red)' : 'var(--teal-dk)' }}>{money(home.fee.balance)}</b></div>
                <div className="snap"><span>Status</span><span className={`pill s-${home.fee.status}`}>{home.fee.status}</span></div>
              </>
            ) : <div className="empty">No fee record</div>}
          </div>
        </div>
      </div>
    </div>
  )
}
