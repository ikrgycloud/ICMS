import { useEffect, useState } from 'react'
import { api } from '../api'
import { Barcode, buildQrMatrix, QrCode } from './StudentHome'
import './FacultyDigitalId.css'

function dateLabel(value: string) {
  return value ? new Date(`${value}T00:00:00`).toLocaleDateString() : 'Not specified'
}

export default function FacultyDigitalId() {
  const [card, setCard] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.facultyDigitalId()
      .then((data: any) => setCard(data.digital_id || null))
      .catch((reason: any) => setError(reason?.message || 'Faculty Digital ID could not be loaded.'))
  }, [])

  if (error) return <main className="faculty-id-page"><div className="faculty-id-state">{error}</div></main>
  if (!card) return <main className="faculty-id-page"><div className="faculty-id-state"><div className="spinner" />Loading Digital ID...</div></main>

  return (
    <main className="faculty-id-page fade-in">
      <header className="faculty-id-heading">
        <h1>Digital ID</h1>
        <p>Your authenticated ICMS faculty identity card.</p>
      </header>

      <section className="faculty-id-card" aria-label="Faculty identity card">
        <div className="faculty-id-topline">
          <div><strong>ICMS</strong><span>Faculty Identity Card</span></div>
          <span className="faculty-id-campus">{card.campus || 'ICMS'}</span>
        </div>

        <div className="faculty-id-main">
          <div className="faculty-id-avatar" aria-label="Faculty avatar">{card.avatar_initials || 'F'}</div>
          <div className="faculty-id-person">
            <h2>{card.full_name || 'Faculty member'}</h2>
            <p className="faculty-id-employee">{card.employee_id || 'Employee ID unavailable'}</p>
            <p>{card.designation || 'Faculty'}{card.department ? ` | ${card.department}` : ''}</p>
          </div>
          <QrCode matrix={buildQrMatrix(String(card.verification_payload || 'ICMS:FAC'))} />
        </div>

        <div className="faculty-id-details">
          <div><span>Designation</span><b>{card.designation || '-'}</b></div>
          <div><span>Department</span><b>{card.department || card.department_code || '-'}</b></div>
          <div><span>Campus</span><b>{card.campus || '-'}</b></div>
          <div><span>Valid Until</span><b>{dateLabel(card.valid_until)}</b></div>
        </div>

        <div className="faculty-id-barcode">
          <Barcode value={String(card.barcode_value || '')} />
          <span>{card.employee_id || 'ICMS Faculty'}</span>
        </div>
      </section>

      {!card.valid_until && <p className="faculty-id-note">Card validity is not defined in the current staff identity policy.</p>}
    </main>
  )
}


