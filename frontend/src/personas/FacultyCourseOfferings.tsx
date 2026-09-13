import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

export default function FacultyCourseOfferings() {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.courseOfferings().then(setData).catch(() => setData({ offerings: [] })) }, [])
  if (!data) return <Spinner />
  const rows = data.offerings || []
  return <main className="assess-workspace fade-in">
    <section className="assess-heading"><h1>My Course Offerings</h1><p>Only course offerings linked to your active teaching assignments are shown.</p></section>
    {!rows.length ? <Empty text="You do not have any active course offering assignments." /> : <article className="assess-register"><header><h2>Assigned Offerings</h2></header><div className="assess-table-wrap"><table className="assess-table"><thead><tr><th>Course</th><th>Program</th><th>Academic year</th><th>Semester / Term</th><th>Dates</th><th>Faculty</th></tr></thead><tbody>{rows.map((row: any) => <tr key={row.id}><td><b>{row.course_code}</b><span>{row.course_title}</span></td><td>{row.program_code || row.program}</td><td>{row.academic_year}</td><td>{row.semester}<span>{row.term}</span></td><td>{row.course_start_date || 'Not set'}<span>{row.expected_completion_date || 'No end date'}</span></td><td>{(row.faculty_allocations || []).map((item: any) => item.faculty).filter(Boolean).join(', ') || 'Assigned teaching section'}</td></tr>)}</tbody></table></div></article>}
  </main>
}
