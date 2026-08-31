import { useState, useEffect } from 'react'
import { api } from '../api'
import { Spinner, money } from '../modules/kit'

export default function ParentHome({ user }: { user: any }) {
  const [home, setHome] = useState<any>(null)
  const [paying, setPaying] = useState('')
  useEffect(() => { api.parentHome().then(setHome).catch(() => {}) }, [])
  if (!home) return <Spinner />
  const w = home.ward
  const initials = (w.name || 'W').split(' ').map((x: string) => x[0]).slice(0, 2).join('')
  async function pay(invoice: any) { try { setPaying(invoice.id); const order = await api.createParentRazorpayOrder(invoice.id); if (!(window as any).Razorpay) await new Promise<void>((resolve, reject) => { const script=document.createElement('script'); script.src='https://checkout.razorpay.com/v1/checkout.js'; script.onload=()=>resolve(); script.onerror=()=>reject(new Error('Could not load Razorpay checkout')); document.body.appendChild(script) }); new (window as any).Razorpay({ key:order.key_id, amount:order.amount, currency:order.currency, name:'ICMS', description:order.description, order_id:order.order_id, prefill:order.student, handler:async (response:any)=>{ await api.verifyParentRazorpayPayment({invoice_id:invoice.id,...response}); setHome(await api.parentHome()) }}).open() } catch (error:any) { alert(error.message || 'Unable to start payment') } finally { setPaying('') } }

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
                <div className="snap"><span>Balance</span><b style={{ color: home.fee.balance > 0 ? 'var(--red)' : 'var(--teal-dk)' }}>{money(home.fee.balance)}</b></div>
                {(home.fee.invoices || []).map((invoice: any) => <div className="snap" key={invoice.id}><span>{invoice.term}<small>Base {money(invoice.base_amount)} + GST {money(invoice.gst_amount)} ({invoice.gst_rate}%) · Total {money(invoice.amount)}</small><small>{money(invoice.paid)} paid · {money(invoice.balance)} balance</small></span><div className="row-actions">{invoice.balance > 0 && <button className="btn btn-sm btn-brass" disabled={paying === invoice.id} onClick={() => pay(invoice)}>{paying === invoice.id ? 'Starting...' : 'Pay online'}</button>}{invoice.paid > 0 && <button className="btn btn-sm btn-out" onClick={() => api.downloadParentReceipt(invoice.id)}>PDF receipt</button>}</div></div>)}
              </>
            ) : <div className="empty">No fee record</div>}
          </div>
        </div>
      </div>
    </div>
  )
}
