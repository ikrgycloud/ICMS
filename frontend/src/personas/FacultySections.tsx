import { useEffect, useState } from 'react'
import { Empty, Spinner } from '../modules/kit'
import { api } from '../api'

export default function FacultySections() {
  const [home, setHome] = useState<any>(null), [term, setTerm] = useState('all'), [query, setQuery] = useState('')
  useEffect(() => { api.facultyHome().then(setHome).catch(() => setHome({ error: true })) }, [])
  if (!home) return <Spinner />
  if (home.error) return <Empty icon="!" text="Your assigned sections could not be loaded." />
  const sections = home.sections || []
  const terms = Array.from(new Set(sections.map((item: any) => String(item.term || `Semester ${item.course_semester || 'Not set'}`)))).sort()
  const filtered = sections.filter((item: any) => (term === 'all' || String(item.term || `Semester ${item.course_semester || 'Not set'}`) === term) && (!query.trim() || [item.course_code, item.title, item.section, item.room].some(value => String(value || '').toLowerCase().includes(query.trim().toLowerCase()))))
  return <main className="sections-workspace fade-in"><section className="sections-heading"><h1>My Sections</h1><p>Sections assigned to you by the Academic Office.</p></section><div className="sections-filters"><label>Academic Term<select value={term} onChange={event => setTerm(event.target.value)}><option value="all">All assigned terms</option>{terms.map(value => <option value={value} key={value}>{value}</option>)}</select></label><label className="sections-search"><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search by course, section, or room..." /></label></div><article className="sections-table-card"><h2>Assigned Sections</h2><div className="sections-table-scroll"><table className="sections-table"><thead><tr><th>Course</th><th>Term</th><th>Section</th><th>Schedule</th><th>Room</th><th>Students</th><th>Attendance Avg</th></tr></thead><tbody>{filtered.map((item: any) => <tr key={item.id}><td><b>{item.course_code}</b><span>{item.title}</span></td><td>{item.term || '—'}</td><td>{item.section}</td><td>{item.schedule || 'TBD'}</td><td>{item.room || 'TBD'}</td><td>{item.enrolled || 0}</td><td><span className="sections-progress"><i style={{ width: `${item.attendance_pct || 0}%` }} /></span>{item.attendance_pct == null ? '—' : `${Math.round(item.attendance_pct)}%`}</td></tr>)}{!filtered.length && <tr><td colSpan={7}>No assigned sections match your filters.</td></tr>}</tbody></table></div><footer>Showing {filtered.length} of {sections.length} assigned sections</footer></article></main>
}
