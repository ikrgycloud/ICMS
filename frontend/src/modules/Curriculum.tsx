import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { PageHead, Spinner } from './kit'

export default function Curriculum() {
  const [courses, setCourses] = useState<any[] | null>(null)
  const [department, setDepartment] = useState('')
  const [program, setProgram] = useState('')
  const [regulation, setRegulation] = useState('')
  const [semester, setSemester] = useState('')
  const [openSemester, setOpenSemester] = useState<number | null>(null)

  useEffect(() => { api.courses().then(result => setCourses(result.courses)).catch(() => setCourses([])) }, [])
  const departments = useMemo(() => Array.from(new Set((courses || []).map(course => course.dept))).filter(Boolean).sort(), [courses])
  const semesters = useMemo(() => Array.from(new Set((courses || []).map(course => Number(course.semester)))).sort((a, b) => a - b), [courses])
  const filtered = useMemo(() => (courses || []).filter(course => (!department || course.dept === department) && (!program || course.program === program) && (!regulation || course.regulation === regulation) && (!semester || Number(course.semester) === Number(semester))), [courses, department, program, regulation, semester])
  const bySemester = useMemo(() => semesters.map(number => ({ number, courses: filtered.filter(course => Number(course.semester) === number) })).filter(group => group.courses.length), [filtered, semesters])
  const credits = filtered.reduce((sum, course) => sum + Number(course.credits || 0), 0)

  if (!courses) return <Spinner />
  return <div className="curriculum-page fade-in">
    <PageHead title="Curriculum" sub="Semester-wise course structure for the currently configured academic programs" />
    <section className="curriculum-filters card">
      <label>Department<select className="select" value={department} onChange={event => setDepartment(event.target.value)}><option value="">All departments</option>{departments.map(item => <option key={item}>{item}</option>)}</select></label><label>Program<select className="select" value={program} onChange={event => setProgram(event.target.value)}><option value="">All programs</option>{[...new Set(courses.map(course => course.program))].map(item => <option key={item}>{item}</option>)}</select></label><label>Regulation<select className="select" value={regulation} onChange={event => setRegulation(event.target.value)}><option value="">All regulations</option>{[...new Set(courses.map(course => course.regulation))].map(item => <option key={item}>{item}</option>)}</select></label>
      <label>Semester<select className="select" value={semester} onChange={event => setSemester(event.target.value)}><option value="">All semesters</option>{semesters.map(item => <option key={item} value={item}>Semester {item}</option>)}</select></label>
      <button className="btn btn-out curriculum-reset" onClick={() => { setDepartment(''); setProgram(''); setRegulation(''); setSemester(''); setOpenSemester(null) }}>Reset</button>
    </section>
    <section className="curriculum-stats">
      <Stat label="Total subjects" value={filtered.length} note="For the selected filters" />
      <Stat label="Core subjects" value={filtered.filter(course => course.course_type === 'Core').length} note="Core curriculum" />
      <Stat label="Electives" value={filtered.filter(course => course.course_type === 'Elective').length} note="Elective curriculum" />
      <Stat label="Total credits" value={credits} note="Sum of configured subject credits" />
      <Stat label="Departments" value={new Set(filtered.map(course => course.dept)).size} note="With matching subjects" />
      <Stat label="Semesters" value={bySemester.length} note="With matching subjects" />
    </section>
    {filtered.length ? <div className="curriculum-layout"><section className="curriculum-structure card"><header><div><h2>Curriculum Structure</h2><p>Click a semester to view its subjects.</p></div></header>{bySemester.map(group => {
      const groupCredits = group.courses.reduce((sum, course) => sum + Number(course.credits || 0), 0)
      const open = openSemester === group.number
      return <section className={`curriculum-semester${open ? ' open' : ''}`} key={group.number}><button className="curriculum-semester-head" onClick={() => setOpenSemester(open ? null : group.number)} aria-expanded={open}><span>Semester {group.number}</span><em>{group.courses.length} subjects · {groupCredits} credits</em><b>{open ? '−' : '+'}</b></button>{open && <div className="curriculum-table-wrap"><table className="tbl curriculum-table"><thead><tr><th>Code</th><th>Subject name</th><th>Type</th><th>Credits</th><th>L-T-P</th><th>Prerequisite</th><th>Category</th></tr></thead><tbody>{group.courses.map(course => <tr key={course.id}><td><b className="mono">{course.code}</b></td><td>{course.title}</td><td>{course.course_type}</td><td>{course.credits}</td><td>{course.ltp || '—'}</td><td>{course.prerequisite || '—'}</td><td>{course.category}</td></tr>)}</tbody></table></div>}</section>
    })}</section><aside className="curriculum-summary card"><h2>Curriculum Summary</h2><h3>Credits by semester</h3>{bySemester.map(group => { const groupCredits = group.courses.reduce((sum, course) => sum + Number(course.credits || 0), 0); const maximum = Math.max(...bySemester.map(item => item.courses.reduce((sum, course) => sum + Number(course.credits || 0), 0))); return <div className="curriculum-credit" key={group.number}><span>Semester {group.number}</span><i><b style={{ width: `${maximum ? groupCredits / maximum * 100 : 0}%` }} /></i><em>{groupCredits}</em></div> })}<div className="curriculum-note">Programme-outcome mappings are the only reference-page data not configured yet. All other curriculum fields now come from the course catalog.</div></aside></div> : <div className="card curriculum-empty">No subjects match the selected filters.</div>}
  </div>
}

function Stat({ label, value, note }: { label: string; value: number; note: string }) { return <section className="curriculum-stat"><span>{label}</span><b>{value}</b><small>{note}</small></section> }
