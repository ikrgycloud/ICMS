import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast, Modal, money, GatedBtn } from './kit'

export default function Finance({ caps, readOnly = false }: { caps: any; readOnly?: boolean }) {
  const [tab, setTab] = useState<'fees' | 'budget'>('fees')
  const [data, setData] = useState<any>(null)
  const [budget, setBudget] = useState<any>(null)
  const [decision, setDecision] = useState<any>(null)
  const [modal, setModal] = useState<{ kind: string; inv: any } | null>(null)
  const [amount, setAmount] = useState('')

  function load() {
    api.invoices().then(setData).catch(() => {})
    api.budget().then(setBudget).catch(() => {})
  }
  useEffect(() => { load() }, [])

  async function act() {
    if (!modal) return
    try {
      const amt = Number(amount)
      const r = modal.kind === 'pay'
        ? await api.recordPayment(modal.inv.id, amt)
        : await api.waiveFee({ invoice_id: modal.inv.id, amount: amt, reason: 'Approved waiver' })
      setDecision(r.decision); setModal(null); setAmount(''); load()
    } catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }); setModal(null) }
  }

  if (!data) return <Spinner />
  const sm = data.summary
  const feesUnavailable = data.data_status === 'unavailable'

  return (
    <div className="fade-in">
      <PageHead title="Finance" sub="Fee collection, waivers (with limit-based escalation), and budget oversight" />

      {feesUnavailable ? <div className="empty">{data.reason || 'Campus-scoped invoice data is unavailable.'}</div> : <div className="kpi-row" style={{ marginBottom: 20 }}>
        <div className="kpi"><div className="kpi-v">{money(sm.total_billed)}</div><div className="kpi-l">Total billed</div></div>
        <div className="kpi"><div className="kpi-v" style={{ color: 'var(--teal)' }}>{money(sm.total_collected)}</div><div className="kpi-l">Collected</div></div>
        <div className="kpi"><div className="kpi-v" style={{ color: 'var(--rose)' }}>{money(sm.outstanding)}</div><div className="kpi-l">Outstanding</div></div>
        <div className="kpi"><div className="kpi-v">{Math.round(100 * sm.total_collected / (sm.total_billed || 1))}%</div><div className="kpi-l">Collection rate</div></div>
      </div>}

      <div className="tabs">
        <button className={`tab ${tab === 'fees' ? 'on' : ''}`} onClick={() => setTab('fees')}>Fee invoices</button>
        <button className={`tab ${tab === 'budget' ? 'on' : ''}`} onClick={() => setTab('budget')}>Budget</button>
      </div>

      {tab === 'fees' && !feesUnavailable && (
        <div className="card">
          <div className="tbl-scroll">
            <table className="tbl">
                <thead><tr><th>Roll No</th><th>Name</th><th>Billed</th><th>Paid</th><th>Balance</th><th>Status</th>{!readOnly && <th style={{ textAlign: 'right' }}>Actions</th>}</tr></thead>
              <tbody>
                {data.invoices.slice(0, 80).map((r: any) => (
                  <tr key={r.id}>
                    <td className="mono">{r.roll_no}</td>
                    <td>{r.name}</td>
                    <td>{money(r.amount)}</td>
                    <td>{money(r.paid)}</td>
                    <td><b style={{ color: r.balance > 0 ? 'var(--rose)' : 'var(--teal)' }}>{money(r.balance)}</b></td>
                    <td><span className={`pill s-${r.status}`}>{r.status}</span></td>
                    {!readOnly && <td style={{ textAlign: 'right' }}>
                      <div className="row-actions">
                        <button className="btn btn-sm btn-out" disabled={!caps.record_payment || r.balance <= 0} onClick={() => { setModal({ kind: 'pay', inv: r }); setAmount(String(r.balance)) }}>Payment</button>
                        <button className="btn btn-sm btn-brass" disabled={!caps.waive || r.balance <= 0} onClick={() => { setModal({ kind: 'waive', inv: r }); setAmount(String(r.balance)) }}>Waive</button>
                      </div>
                    </td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'budget' && budget && (
        <div className="card">
          <div className="card-pad">
            {budget.budget.map((b: any) => {
              const pct = Math.round(100 * b.spent / (b.allocated || 1))
              return (
                <div className="budget-row" key={b.category}>
                  <div className="budget-head"><b>{b.category}</b><span>{money(b.spent)} / {money(b.allocated)}</span></div>
                  <div className="bar-track"><div className="bar-fill" style={{ width: `${pct}%`, background: pct > 85 ? 'var(--rose)' : 'var(--brass)' }} /></div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {modal && (
        <Modal title={modal.kind === 'pay' ? 'Record fee payment' : 'Approve fee waiver'} onClose={() => setModal(null)}
          footer={<><button className="btn btn-out" onClick={() => setModal(null)}>Cancel</button>
            <button className="btn btn-brass" onClick={act}>{modal.kind === 'pay' ? 'Record' : 'Approve waiver'}</button></>}>
          <div className="form-row"><label>Student</label><div className="mono">{modal.inv.roll_no} · {modal.inv.name}</div></div>
          <div className="form-row"><label>Amount (₹)</label>
            <input className="inp" type="number" value={amount} onChange={e => setAmount(e.target.value)} /></div>
          {modal.kind === 'waive' && <p className="hint">Waivers above your scope’s approval limit auto-escalate to the Vice-Chancellor per the approval matrix.</p>}
        </Modal>
      )}
      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
