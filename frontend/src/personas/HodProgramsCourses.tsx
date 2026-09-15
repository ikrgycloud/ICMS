import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner } from '../modules/kit'

const today = () => new Date().toISOString().slice(0, 10)
const activeAllocation = (row: any) => row.status === 'active' && (!row.effective_from || row.effective_from <= today()) && (!row.effective_to || row.effective_to >= today())
const activeCourse = (row: any) => String(row.status || '').toLowerCase() === 'active'

export default function HodProgramsCourses({ go }: { go: (view: string) => void }) {
  const [data, setData] = useState<any>(null), [error, setError] = useState(''), [selected, setSelected] = useState<any>(null)
  const [filters, setFilters] = useState({ query: '', program: '', semester: '', status: 'all', term: '', coverage: 'all', type: '' })
  const load = async () => {
    setError('')
    try {
      const [catalog, sectionData, allocationData] = await Promise.all([api.hodProgramsCourses(), api.hodSections(), api.teachingAllocations()])
      setData({ catalog, sections: sectionData.sections || [], allocations: allocationData.allocations || [] })
    } catch (err: any) { setError(err.message || 'Programs and courses could not be loaded.') }
  }
  useEffect(() => { load() }, [])
  if (error && !data) return <Empty icon="!" text={error} />
  if (!data) return <Spinner />

  const programs = data.catalog.programs || [], courses = data.catalog.courses || [], sections = data.sections || []
  const programById = new Map(programs.map((row: any) => [row.id, row]))
  const activeBySection = new Map(data.allocations.filter(activeAllocation).map((row: any) => [row.section_id, row]))
  const rows = courses.map((course: any) => {
    const courseSections = sections.filter((section: any) => section.course_id === course.id)
    const covered = courseSections.filter((section: any) => activeBySection.has(section.id))
    const timetabled = courseSections.filter((section: any) => Number(section.timetable_entries || 0) > 0)
    const needsAttention = (activeCourse(course) && !courseSections.length) || courseSections.some((section: any) => !activeBySection.has(section.id))
    return { ...course, program: programById.get(course.program_id), sections: courseSections, covered, timetabled, needsAttention }
  })
  const semesters = [...new Set(courses.map((row: any) => row.semester).filter((value: any) => value !== null && value !== undefined && value !== ''))].sort((a: any, b: any) => Number(a) - Number(b))
  const terms = [...new Set(sections.map((row: any) => row.term).filter(Boolean))].sort()
  const courseTypes = [...new Set(courses.map((row: any) => row.course_type).filter(Boolean))].sort()
  const filtered = rows.filter((row: any) => {
    const text = `${row.code} ${row.title}`.toLowerCase().includes(filters.query.trim().toLowerCase())
    const program = !filters.program || row.program_id === filters.program
    const semester = !filters.semester || String(row.semester) === filters.semester
    const status = filters.status === 'all' || String(row.status).toLowerCase() === filters.status
    const term = !filters.term || row.sections.some((section: any) => section.term === filters.term)
    const type = !filters.type || row.course_type === filters.type
    const coverage = filters.coverage === 'all' || (filters.coverage === 'full' ? row.sections.length > 0 && row.covered.length === row.sections.length : filters.coverage === 'partial' ? row.covered.length > 0 && row.covered.length < row.sections.length : row.sections.length > 0 && !row.covered.length)
    return text && program && semester && status && term && type && coverage
  })
  const allSections = rows.flatMap((row: any) => row.sections)
  const allocatedSections = allSections.filter((section: any) => activeBySection.has(section.id))
  const attentionCourses = rows.filter((row: any) => row.needsAttention)
  const activeCourses = courses.filter(activeCourse)
  const coursesWithoutSections = activeCourses.filter((course: any) => !rows.find((row: any) => row.id === course.id)?.sections.length)
  const coursesWithFaculty = activeCourses.filter((course: any) => { const row = rows.find((item: any) => item.id === course.id); return row?.sections.length && row.covered.length === row.sections.length })
  const programsWithDelivery = programs.map((program: any) => { const programCourses = rows.filter((row: any) => row.program_id === program.id); const programSections = programCourses.flatMap((row: any) => row.sections); return { ...program, courseCount: programCourses.length, sectionCount: programSections.length } })
  const attention = [
    ...coursesWithoutSections.map((course: any) => ({ key: `course-${course.id}`, title: 'Missing section', detail: `${course.code} has no stored section.`, view: 'hod_sections' })),
    ...allSections.filter((section: any) => !activeBySection.has(section.id)).map((section: any) => ({ key: `faculty-${section.id}`, title: 'Missing faculty allocation', detail: `${section.course_code} · Section ${section.section} has no in-effect allocation.`, view: 'hod_allocations' })),
    ...allSections.filter((section: any) => Number(section.timetable_entries || 0) === 0).map((section: any) => ({ key: `timetable-${section.id}`, title: 'Missing timetable', detail: `${section.course_code} · Section ${section.section} has no active timetable entry.`, view: 'hod_sections' })),
  ]
  const clear = () => setFilters({ query: '', program: '', semester: '', status: 'all', term: '', coverage: 'all', type: '' })
  return <main className="hod-courses-page fade-in">
    <header className="hod-courses-heading"><div><p>Department academic monitoring</p><h1>Programs &amp; Courses</h1><span>{data.catalog.department?.name || 'Department'} · live course, section, faculty, and timetable coverage.</span></div><button className="btn btn-out" onClick={load} type="button">Refresh data</button></header>
    {error && <p className="hod-allocation-message error">{error}</p>}
    <section className="hod-program-overview"><header><div><p>Shared academic structure</p><h2>Programs</h2></div><span>Select a program to filter the course register.</span></header><div>{programsWithDelivery.map((program: any) => <button className={filters.program === program.id ? 'selected' : ''} key={program.id} onClick={() => setFilters({ ...filters, program: filters.program === program.id ? '' : program.id })} type="button"><b>{program.code}</b><strong>{program.name}</strong><span>{program.level || 'Program'} · {program.duration_years ? `${program.duration_years} years` : 'Duration not recorded'}</span><small>{program.courseCount} courses · {program.sectionCount} sections</small></button>)}{!programsWithDelivery.length && <p>No programs are recorded for this department.</p>}</div></section>
    {attention.length > 0 && <section className="hod-courses-attention"><header><div><p>Delivery readiness</p><h2>Needs Attention</h2></div></header><div>{attention.slice(0, 6).map((item: any) => <button key={item.key} onClick={() => go(item.view)} type="button"><b>{item.title}</b><span>{item.detail}</span><em>Open →</em></button>)}</div></section>}
    <section className="hod-courses-summary"><Stat value={courses.length} label="Department Courses" /><Stat value={courses.filter(activeCourse).length} label="Active Courses" /><Stat value={allSections.length} label="Department Sections" /><Stat value={`${allocatedSections.length} / ${allSections.length}`} label="Sections With Faculty" /><Stat value={attentionCourses.length} label="Courses Needing Attention" /></section>
    <p className="hod-courses-summary-note">Department totals · filters narrow the course list. “Sections” uses stored department sections because no section active-status/current-term source exists.</p>
    <section className="hod-courses-filters"><label>Search<input value={filters.query} onChange={event => setFilters({ ...filters, query: event.target.value })} placeholder="Course code or title" /></label><label>Program<select value={filters.program} onChange={event => setFilters({ ...filters, program: event.target.value })}><option value="">All programs</option>{programs.map((row: any) => <option value={row.id} key={row.id}>{row.code} · {row.name}</option>)}</select></label><label>Semester<select value={filters.semester} onChange={event => setFilters({ ...filters, semester: event.target.value })}><option value="">All semesters</option>{semesters.map(value => <option value={String(value)} key={String(value)}>Semester {value}</option>)}</select></label><label>Status<select value={filters.status} onChange={event => setFilters({ ...filters, status: event.target.value })}><option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label><label>Section term<select value={filters.term} onChange={event => setFilters({ ...filters, term: event.target.value })}><option value="">All recorded terms</option>{terms.map(value => <option value={value} key={value}>{value}</option>)}</select></label><label>Course type<select value={filters.type} onChange={event => setFilters({ ...filters, type: event.target.value })}><option value="">All course types</option>{courseTypes.map(value => <option value={value} key={value}>{value}</option>)}</select></label><label>Faculty coverage<select value={filters.coverage} onChange={event => setFilters({ ...filters, coverage: event.target.value })}><option value="all">All coverage</option><option value="full">Fully allocated</option><option value="partial">Partially allocated</option><option value="none">Unallocated</option></select></label><button className="btn btn-out" onClick={clear} type="button">Clear filters</button></section>
    <section className="hod-courses-list">{filtered.map((row: any) => <CourseCard key={row.id} row={row} onDetail={() => setSelected(row)} onSections={() => go('hod_sections')} onAllocation={() => go('hod_allocations')} />)}{!filtered.length && <Empty icon="⌕" text={courses.length ? 'No courses match the selected filters.' : 'No courses are available for this department.'} />}</section>
    {selected && <CourseDetail row={selected} allocationBySection={activeBySection} onClose={() => setSelected(null)} onSections={() => go('hod_sections')} onAllocation={() => go('hod_allocations')} />}
  </main>
}

function Stat({ value, label }: { value: string | number, label: string }) { return <article><b>{value}</b><span>{label}</span></article> }

function CourseCard({ row, onDetail, onSections, onAllocation }: any) {
  const total = row.sections.length, covered = row.covered.length, timetabled = row.timetabled.length
  const facultyText = !total ? 'No sections recorded' : covered === total ? 'Fully allocated' : covered ? `${total - covered} section${total - covered === 1 ? '' : 's'} needs faculty` : 'No faculty assigned'
  return <article className="hod-course-card"><button className="hod-course-main" onClick={onDetail} type="button"><div className="hod-course-ident"><b>{row.code}</b><h2>{row.title}</h2><span>{row.program ? `${row.program.code} · ${row.program.name}` : 'No program relation recorded'}</span></div><div className="hod-course-meta"><span>Semester {row.semester || '—'}</span><span>{row.credits ?? 0} credits</span><em className={activeCourse(row) ? 'active' : 'inactive'}>{row.status || '—'}</em></div><Coverage label="Sections" value={total} total={total} /><Coverage label="Faculty coverage" value={covered} total={total} text={facultyText} /><Coverage label="Timetabled" value={timetabled} total={total} text={total ? `${timetabled} / ${total} sections` : 'No sections'} /></button><div className="hod-course-actions"><button onClick={onDetail} type="button">View details</button><button onClick={onSections} type="button">View sections</button><button onClick={onAllocation} type="button">Manage allocation</button>{row.needsAttention && <span>Needs attention</span>}</div></article>
}

function Coverage({ label, value, total, text }: any) { const percent = total ? Math.round(100 * value / total) : 0; return <div className="hod-course-coverage"><span>{label}</span><b>{text || value}</b><i><span style={{ width: `${percent}%` }} /></i></div> }

function CourseDetail({ row, allocationBySection, onClose, onSections, onAllocation }: any) { return <Modal className="modal-wide" title={`${row.code} · ${row.title}`} onClose={onClose} footer={<><button className="btn btn-out" onClick={onClose} type="button">Close</button><button className="btn btn-out" onClick={onSections} type="button">View Sections</button><button className="btn btn-crimson" onClick={onAllocation} type="button">Manage Teaching Allocation</button></>}><section className="hod-course-detail"><div className="hod-course-detail-info"><span>Program</span><b>{row.program ? `${row.program.code} · ${row.program.name}` : 'No program relation recorded'}</b><span>Semester</span><b>{row.semester || '—'}</b><span>Credits</span><b>{row.credits ?? 0}</b><span>Status</span><b>{row.status || '—'}</b>{row.course_type && <><span>Course type</span><b>{row.course_type}</b></>}{row.ltp && <><span>Lecture / Lab / Tutorial</span><b>{row.ltp}</b></>}{row.prerequisite && <><span>Prerequisite</span><b>{row.prerequisite}</b></>}</div><h3>Section Coverage</h3>{row.sections.length ? <div className="hod-course-section-list">{row.sections.map((section: any) => { const allocation = allocationBySection.get(section.id); const hasTimetable = Number(section.timetable_entries || 0) > 0; return <article key={section.id}><div><b>Section {section.section}</b><span>{section.term || 'Term not recorded'}</span></div><div><span>Faculty</span><b>{allocation?.faculty || 'Needs faculty allocation'}</b></div><div><span>Timetable</span><b>{hasTimetable ? 'Timetabled' : 'No active timetable entry'}</b></div>{section.room && section.room !== 'Not available' && <small>Room {section.room}</small>}</article> })}</div> : <p className="hod-course-empty">No sections are recorded for this course.</p>}</section></Modal> }
