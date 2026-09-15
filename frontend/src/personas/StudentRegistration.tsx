import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, PageHead, Spinner } from '../modules/kit'

export default function StudentRegistration() {
  const [sections, setSections] = useState<any[] | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState('')

  const load = async () => {
    try {
      setError('')
      const result = await api.registrationSections()
      setSections(result.sections || [])
    } catch (err: any) {
      setError(err?.message || 'Unable to load registration-ready sections.')
      setSections([])
    }
  }

  useEffect(() => { load() }, [])

  const enroll = async (section: any) => {
    setBusy(section.id)
    setError('')
    setMessage('')
    try {
      const result = await api.enrollInSection(section.id)
      setMessage(`You are enrolled. Registration ID: ${result.enrollment.id}`)
      await load()
    } catch (err: any) {
      setError(err?.message || 'Enrollment could not be completed.')
    } finally {
      setBusy('')
    }
  }

  if (sections === null) return <Spinner />

  return <div className="student-registration">
    <PageHead title="Course Registration" sub="Register only for active sections in your programme. Enrollment is recorded immediately." right={<button className="btn btn-out" onClick={load}>Refresh</button>} />
    {error && <div className="form-error">{error}</div>}
    {message && <div className="form-success">{message}</div>}
    {!sections.length ? <Empty text="No registration-ready sections are available for your programme." /> : (
      <div className="table-wrap student-registration-table">
        <table>
          <thead><tr><th>Course</th><th>Section</th><th>Term</th><th>Faculty</th><th>Seats</th><th>Status</th><th /></tr></thead>
          <tbody>{sections.map((section) => {
            const available = section.status === 'Available'
            return <tr key={section.id}>
              <td><strong>{section.course_code}</strong><br /><span className="muted">{section.course}</span></td>
              <td>{section.section}</td><td>{section.term}<br /><span className="muted">{section.academic_year}</span></td>
              <td>{section.faculty || '—'}</td><td>{section.enrolled} / {section.capacity}</td>
              <td><span className={`status-tag ${available ? 'st-green' : 'st-gray'}`}>{section.status}</span></td>
              <td><button className="btn btn-crimson" disabled={!available || busy === section.id} onClick={() => enroll(section)}>{busy === section.id ? 'Enrolling…' : available ? 'Enroll' : section.status}</button></td>
            </tr>
          })}</tbody>
        </table>
      </div>
    )}
  </div>
}
