import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

const PAGE_SIZE = 12

export default function FacultyStudents() {
  const [home, setHome] = useState<any>(null), [roster, setRoster] = useState<any[]>([])
  const [term, setTerm] = useState('all'), [course, setCourse] = useState('all'), [section, setSection] = useState('all'), [query, setQuery] = useState(''), [page, setPage] = useState(1)
  useEffect(() => { api.facultyHome().then(async data => { setHome(data); const groups = await Promise.all((data.sections || []).map(async (item: any) => { try { const result = await api.facultySectionStudents(item.id); return (result.students || []).map((student: any) => ({ ...student, section: item })) } catch { return [] } })); setRoster(groups.flat()) }).catch(() => setHome({ error: true })) }, [])
  if (!home) return <Spinner />
  if (home.error) return <Empty icon="!" text="Your student roster could not be loaded." />
  const sections = home.sections || []
  const terms = Array.from(new Set(sections.map((item: any) => item.term).filter(Boolean))).sort()
  const termSections = sections.filter((item: any) => term === 'all' || item.term === term)
  const courses = Array.from(new Map(termSections.map((item: any) => [item.course_code, item.title])).entries()).sort(([a], [b]) => a.localeCompare(b))
  const courseSections = termSections.filter((item: any) => course === 'all' || item.course_code === course)
  const filtered = roster.filter(item => (term === 'all' || item.section.term === term) && (course === 'all' || item.section.course_code === course) && (section === 'all' || item.section.id === section) && (!query.trim() || `${item.name} ${item.roll_no}`.toLowerCase().includes(query.trim().toLowerCase())))
  const attendanceRows = filtered.filter(item => item.attendance_pct != null)
  const attendance = attendanceRows.length ? Math.round(attendanceRows.reduce((total, item) => total + item.attendance_pct, 0) / attendanceRows.length) : null
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)), currentPage = Math.min(page, totalPages), pageRows = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
  const from = filtered.length ? (currentPage - 1) * PAGE_SIZE + 1 : 0, to = Math.min(currentPage * PAGE_SIZE, filtered.length)
  const chooseTerm = (value: string) => { setTerm(value); setCourse('all'); setSection('all'); setPage(1) }
  const chooseCourse = (value: string) => { setCourse(value); setSection('all'); setPage(1) }
  return <main className="faculty-students fade-in"><section className="faculty-students-heading"><div><h1>My Students</h1><p>View students enrolled in your assigned sections and monitor their attendance and academic progress.</p></div><span>Faculty roster</span></section>
    <section className="faculty-student-kpis"><article><span>Students shown</span><b>{filtered.length}</b></article><article><span>Assigned sections</span><b>{courseSections.length}</b></article><article><span>Assigned courses</span><b>{new Set(courseSections.map((item: any) => item.course_code)).size}</b></article><article><span>Average attendance</span><b>{attendance == null ? '—' : `${attendance}%`}</b></article></section>
    <section className="faculty-student-filters"><label>Academic Year / Term<select value={term} onChange={event => chooseTerm(event.target.value)}><option value="all">All assigned terms</option>{terms.map(value => <option value={value} key={value}>{value}</option>)}</select></label><label>Course<select value={course} onChange={event => chooseCourse(event.target.value)}><option value="all">All assigned courses</option>{courses.map(([code, title]) => <option value={code} key={code}>{code} · {title}</option>)}</select></label><label>Section<select value={section} onChange={event => { setSection(event.target.value); setPage(1) }}><option value="all">All sections</option>{courseSections.map((item: any) => <option value={item.id} key={item.id}>{item.course_code} · Section {item.section}</option>)}</select></label><label className="faculty-student-search">Search students<input value={query} onChange={event => { setQuery(event.target.value); setPage(1) }} placeholder="Name or roll number" /></label></section>
    <article className="faculty-student-table-card"><header><div><h2>Student Roster</h2><p>Only students in sections assigned to you are shown.</p></div><span>{filtered.length} students</span></header><div className="faculty-student-table-wrap"><table><thead><tr><th>Roll No.</th><th>Student</th><th>Course</th><th>Term</th><th>Section</th><th>Attendance</th><th>CGPA</th></tr></thead><tbody>{pageRows.map((student, index) => <tr key={`${student.section.id}-${student.roll_no}-${index}`}><td>{student.roll_no}</td><td><b>{student.name}</b></td><td><b>{student.section.course_code}</b><span>{student.section.title}</span></td><td>{student.section.term || '—'}</td><td>Section {student.section.section}</td><td><em className={student.attendance_pct != null && student.attendance_pct < 75 ? 'low' : ''}>{student.attendance_pct == null ? '—' : `${student.attendance_pct}%`}</em></td><td>{student.cgpa == null ? '—' : Number(student.cgpa).toFixed(2)}</td></tr>)}{!filtered.length && <tr><td colSpan={7}>No students match the selected filters.</td></tr>}</tbody></table></div>{filtered.length > 0 && <footer className="faculty-student-pagination"><span>Showing {from}–{to} of {filtered.length} students</span><div><button disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)} type="button">Previous</button><span>Page {currentPage} of {totalPages}</span><button disabled={currentPage === totalPages} onClick={() => setPage(currentPage + 1)} type="button">Next</button></div></footer>}</article>
  </main>
}
