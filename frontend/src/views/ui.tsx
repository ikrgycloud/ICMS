export const LEVEL_COLORS: Record<number, string> = {
  1: '#8b6fc9', 2: '#4a86c9', 3: '#2fa98c', 4: '#c9a24a',
  5: '#e0b74a', 6: '#3aa06a', 7: '#4a86c9', 8: '#6f7fd4',
}

const AUTH_CLASS: Record<string, string> = {
  'Full': 'a-Full', 'Limited': 'a-Limited', 'View Only': 'a-View',
  'Recommend': 'a-Recommend', 'Delegated': 'a-Delegated',
  'Conditional': 'a-Conditional', 'Not Allowed': 'a-None',
}
const AUTH_SHORT: Record<string, string> = {
  'Full': 'Full', 'Limited': 'Limited', 'View Only': 'View',
  'Recommend': 'Recommend', 'Delegated': 'Delegated',
  'Conditional': 'Conditional', 'Not Allowed': '—',
}

export function AuthChip({ v }: { v: string }) {
  return <span className={`auth-chip ${AUTH_CLASS[v] || 'a-None'}`}>{AUTH_SHORT[v] || v}</span>
}

export function StatePill({ s }: { s: string }) {
  return <span className={`pill s-${s}`}>{s.replace(/_/g, ' ')}</span>
}

export function Spinner() {
  return <div className="center-load"><div className="spinner" /></div>
}

export function Empty({ icon = '◇', text }: { icon?: string; text: string }) {
  return <div className="empty"><div className="ei">{icon}</div>{text}</div>
}

export function money(n?: number | null) {
  if (n == null) return '—'
  return '₹' + n.toLocaleString('en-IN')
}
