import { useState, useEffect, ReactNode } from 'react'

export function money(n?: number | null) {
  if (n == null) return '—'
  if (Math.abs(n) >= 1e7) return '₹' + (n / 1e7).toFixed(2) + ' Cr'
  if (Math.abs(n) >= 1e5) return '₹' + (n / 1e5).toFixed(2) + ' L'
  return '₹' + Math.round(n).toLocaleString('en-IN')
}

export function Spinner() {
  return <div className="center-load"><div className="spinner" /></div>
}

export function Empty({ icon = '◇', text }: { icon?: string; text: string }) {
  return <div className="empty"><div className="ei">{icon}</div>{text}</div>
}

export function PageHead({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) {
  return (
    <div className="page-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 20, flexWrap: 'wrap' }}>
      <div>
        <h1>{title}</h1>
        {sub && <p>{sub}</p>}
      </div>
      {right}
    </div>
  )
}

export function Kpis({ items }: { items: { label: string; value: ReactNode; tone?: string }[] }) {
  return (
    <div className="kpi-row">
      {items.map((k, i) => (
        <div className="kpi" key={i}>
          <div className="kpi-v" style={k.tone ? { color: k.tone } : {}}>{k.value}</div>
          <div className="kpi-l">{k.label}</div>
        </div>
      ))}
    </div>
  )
}

/** A capability-gated action button. Disabled (with reason) when not permitted. */
export function GatedBtn({ can, onClick, children, kind = 'brass', title }:
  { can: boolean; onClick: () => void; children: ReactNode; kind?: string; title?: string }) {
  return (
    <button className={`btn btn-${can ? kind : 'disabled'}`} disabled={!can}
      onClick={onClick} title={can ? title : 'Your role is not authorized for this action'}>
      {children}
    </button>
  )
}

/** Shows the authority engine's decision after an action. */
export function DecisionToast({ decision, onClose }: { decision: any; onClose: () => void }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4200)
    return () => clearTimeout(t)
  }, [])
  if (!decision) return null
  const oc = decision.outcome
  const tone = oc === 'ALLOW' ? 'teal' : oc === 'ESCALATE' ? 'brass' : oc === 'RECOMMEND' ? 'blue' : 'rose'
  return (
    <div className={`decision-toast dt-${tone}`}>
      <div className="dt-oc">{oc}</div>
      <div className="dt-reason">{decision.reason}</div>
      {decision.escalate_to && <div className="dt-esc">→ escalated to {decision.escalate_to}</div>}
      <button className="dt-x" onClick={onClose}>✕</button>
    </div>
  )
}

export function Pill({ s }: { s: string }) {
  return <span className={`pill s-${s.replace(/[^a-z]/gi, '_').toLowerCase()}`}>{s.replace(/_/g, ' ')}</span>
}

export function useLoad<T>(fn: () => Promise<T>, deps: any[] = []): [T | null, boolean, () => void] {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  function reload() {
    setLoading(true)
    fn().then(d => { setData(d); setLoading(false) }).catch(() => setLoading(false))
  }
  useEffect(reload, deps)
  return [data, loading, reload]
}

export function Modal({ title, children, onClose, footer, className = '' }:
  { title: string; children: ReactNode; onClose: () => void; footer?: ReactNode; className?: string }) {
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className={`modal ${className}`.trim()} onClick={e => e.stopPropagation()}>
        <div className="modal-h"><h3>{title}</h3><button className="modal-x" onClick={onClose}>✕</button></div>
        <div className="modal-b">{children}</div>
        {footer && <div className="modal-f">{footer}</div>}
      </div>
    </div>
  )
}
