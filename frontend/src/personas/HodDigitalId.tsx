import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'
import './HodDigitalId.css'

export default function HodDigitalId() {
  const [card, setCard] = useState<any>(null)
  const [error, setError] = useState('')
  const load = async () => {
    setError('')
    try { setCard((await api.hodDigitalId()).digital_id || null) }
    catch (reason: any) { setError(reason.message || 'Digital ID could not be loaded.') }
  }
  useEffect(() => { void load() }, [])
  if (error && !card) return <Empty icon="!" text={error} />
  if (!card) return <Spinner />
  const initials = card.avatar_initials || String(card.full_name || 'H').split(/\s+/).map((part: string) => part[0]).slice(0, 2).join('').toUpperCase()

  return <main className="hod-id-page fade-in">
    <header className="hod-id-heading"><div><p>Self-service identity</p><h1>Digital ID</h1><span>Your institutional identification card.</span></div><button className="btn btn-out hod-id-print" type="button" onClick={() => window.print()}>Print ID</button></header>
    {error && <p className="hod-id-message" role="alert">{error}</p>}
    <section className="hod-id-card" aria-label="HOD institutional identity card">
      <header className="hod-id-card-head"><div><strong>ICMS</strong><span>Institutional Identity Card</span></div><span>{card.campus || 'ICMS Campus'}</span></header>
      <div className="hod-id-card-main"><div className="hod-id-avatar" aria-label="Identity initials">{initials || 'H'}</div><div><p>Head of Department</p><h2>{value(card.full_name)}</h2><b>{value(card.employee_id)}</b><span>{value(card.designation)}</span></div></div>
      <dl className="hod-id-fields"><Field label="Department" value={card.department} /><Field label="Campus" value={card.campus} /><Field label="Role / Office" value={card.leadership_role} /></dl>
      <footer><span>Issued from authenticated institutional staff records</span><b>ICMS</b></footer>
    </section>
    <aside className="hod-id-note"><b>Identity-only card</b><span>This card intentionally omits contact details, authority data, authentication tokens, QR codes, and barcodes because no safe verification contract is configured.</span></aside>
  </main>
}

function Field({ label, value: fieldValue }: { label: string; value: any }) { return <div><dt>{label}</dt><dd>{value(fieldValue)}</dd></div> }
function value(fieldValue: any) { return fieldValue === null || fieldValue === undefined || fieldValue === '' ? '—' : String(fieldValue) }
