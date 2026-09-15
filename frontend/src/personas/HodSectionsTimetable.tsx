import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner } from '../modules/kit'

const today = () => new Date().toISOString().slice(0, 10)
const current = (row: any) => row.status === 'active' && (!row.effective_from || row.effective_from <= today()) && (!row.effective_to || row.effective_to >= today())
const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const pct = (part: number, total: number) => total ? Math.round((part / total) * 100) : 0

export default function HodSectionsTimetable({ go }: { go: (view: string) => void }) {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<any>(null)
  const [filters, setFilters] = useState({ q: '', program: '', semester: '', term: '', faculty: '', coverage: 'all', timetable: 'all' })

  const load = async () => {
    setError('')
    try {
      const [sectionData, catalog, allocationData] = await Promise.all([api.hodSections(), api.hodProgramsCourses(), api.teachingAllocations()])
      setData({ department: sectionData.department || null, sections: sectionData.sections || [], catalog, allocations: allocationData.allocations || [] })
    } catch (err: any) { setError(err.message || 'Sections and timetable could not be loaded.') }
  }

  useEffect(() => { load() }, [])
  if (error && !data) return <Empty icon="!" text={error} />
  if (!data) return <Spinner />

  const programs = data.catalog.programs || []
  const courses = data.catalog.courses || []
  const courseMap = new Map(courses.map((row: any) => [row.id, row]))
  const programMap = new Map(programs.map((row: any) => [row.id, row]))
  const ownership = new Map(data.allocations.filter(current).map((row: any) => [row.section_id, row]))
  const rows = data.sections.map((section: any) => {
    const course = courseMap.get(section.course_id)
    return { ...section, course, program: programMap.get(course?.program_id), allocation: ownership.get(section.id), entries: section.timetable || [] }
  })
  const faculty = [...new Map(rows.filter((row: any) => row.allocation).map((row: any) => [row.allocation.faculty_id, row.allocation.faculty])).entries()]
  const terms = [...new Set(rows.map((row: any) => row.term).filter(Boolean))].sort()
  const semesters = [...new Set(courses.map((row: any) => row.semester).filter(Boolean))].sort((a: any, b: any) => Number(a) - Number(b))
  const visible = rows.filter((row: any) =>
    `${row.course_code} ${row.course_title} ${row.section}`.toLowerCase().includes(filters.q.toLowerCase()) &&
    (!filters.program || row.program?.id === filters.program) &&
    (!filters.semester || String(row.course?.semester) === filters.semester) &&
    (!filters.term || row.term === filters.term) &&
    (!filters.faculty || row.allocation?.faculty_id === filters.faculty) &&
    (filters.coverage === 'all' || (filters.coverage === 'assigned' ? Boolean(row.allocation) : !row.allocation)) &&
    (filters.timetable === 'all' || (filters.timetable === 'scheduled' ? row.entries.length > 0 : !row.entries.length))
  )
  const withFaculty = rows.filter((row: any) => row.allocation).length
  const withTimetable = rows.filter((row: any) => row.entries.length).length
  const ready = rows.filter((row: any) => row.allocation && row.entries.length).length
  const needsAttention = rows.filter((row: any) => !row.allocation || !row.entries.length)
  const timetableRows = visible.flatMap((row: any) => row.entries.map((entry: any) => ({ ...entry, section: row }))).sort((a: any, b: any) => a.day_of_week - b.day_of_week || String(a.start_time).localeCompare(String(b.start_time)))
  const clear = () => setFilters({ q: '', program: '', semester: '', term: '', faculty: '', coverage: 'all', timetable: 'all' })

  return <main className="hod-sections-page fade-in">
    <header className="hod-sections-heading"><div><p>Department delivery monitoring</p><h1>Sections &amp; Timetable</h1><span>{data.department?.name || 'Your department'}{data.department?.code ? ` · ${data.department.code}` : ''} · Shared academic records, shown read-only.</span></div><button className="btn btn-out" onClick={load} type="button">Refresh data</button></header>
    {error && <p className="hod-sections-message" role="alert">{error}</p>}
    <section className="hod-sections-summary" aria-label="Section summary"><Stat value={rows.length} label="Department Sections" helper="Shared section records" /><Stat value={withFaculty} label="Sections With Faculty" helper="Active teaching allocations" /><Stat value={withTimetable} label="Sections With Timetable" helper="Current timetable entries" /><Stat value={ready} label="Delivery Ready" helper="Faculty and timetable present" /><Stat value={needsAttention.length} label="Needs Attention" helper="Allocation or timetable gap" tone="attention" /></section>
    <section className="hod-sections-readiness" aria-label="Delivery readiness"><Readiness label="Faculty allocation coverage" value={pct(withFaculty, rows.length)} detail={`${withFaculty} of ${rows.length} sections have an active allocation`} /><Readiness label="Timetable coverage" value={pct(withTimetable, rows.length)} detail={`${withTimetable} of ${rows.length} sections have a current timetable`} /><Readiness label="Delivery readiness" value={pct(ready, rows.length)} detail={`${ready} of ${rows.length} sections have both requirements`} /></section>
    {needsAttention.length > 0 && <section className="hod-sections-attention" aria-label="Sections needing attention"><div><p>Needs attention</p><h2>Resolve shared academic delivery gaps</h2><span>Use the authoritative allocation or timetable workspace to make changes.</span></div><div className="hod-sections-attention-list">{needsAttention.slice(0, 4).map((row: any) => <article key={row.id}><b>{row.course_code} · Section {row.section}</b><span>{!row.allocation && !row.entries.length ? 'Faculty allocation and timetable missing' : !row.allocation ? 'Faculty allocation missing' : 'Timetable missing'}</span><button type="button" onClick={() => !row.allocation ? go('hod_allocations') : setSelected(row)}>{!row.allocation ? 'Teaching allocations' : 'View section'}</button></article>)}</div></section>}
    <section className="hod-sections-filters" aria-label="Section filters"><label>Search<input value={filters.q} onChange={e => setFilters({ ...filters, q: e.target.value })} placeholder="Course or section" /></label><label>Program<select value={filters.program} onChange={e => setFilters({ ...filters, program: e.target.value })}><option value="">All programs</option>{programs.map((x: any) => <option value={x.id} key={x.id}>{x.code}</option>)}</select></label><label>Semester<select value={filters.semester} onChange={e => setFilters({ ...filters, semester: e.target.value })}><option value="">All semesters</option>{semesters.map(x => <option value={String(x)} key={String(x)}>Semester {x}</option>)}</select></label><label>Term<select value={filters.term} onChange={e => setFilters({ ...filters, term: e.target.value })}><option value="">All recorded terms</option>{terms.map(x => <option value={x} key={x}>{x}</option>)}</select></label><label>Faculty<select value={filters.faculty} onChange={e => setFilters({ ...filters, faculty: e.target.value })}><option value="">All faculty</option>{faculty.map(([id, name]: any) => <option value={id} key={id}>{name}</option>)}</select></label><label>Faculty coverage<select value={filters.coverage} onChange={e => setFilters({ ...filters, coverage: e.target.value })}><option value="all">All</option><option value="assigned">Assigned</option><option value="unassigned">Unassigned</option></select></label><label>Timetable<select value={filters.timetable} onChange={e => setFilters({ ...filters, timetable: e.target.value })}><option value="all">All</option><option value="scheduled">Scheduled</option><option value="missing">Missing</option></select></label><button className="btn btn-out" onClick={clear} type="button">Clear filters</button></section>
    <section className="hod-sections-register" aria-label="Section register"><div className="hod-sections-register-head"><div><p>Section register</p><h2>{visible.length} visible section{visible.length === 1 ? '' : 's'}</h2></div><span>Faculty is derived from active TeachingAllocation records.</span></div><div className="hod-sections-list">{visible.map((row: any) => <article className="hod-section-card" key={row.id}><button className="hod-section-main" onClick={() => setSelected(row)} type="button"><div className="hod-section-ident"><b>{row.course_code}</b><h3>{row.course_title}</h3><span>Section {row.section} · {row.term || 'Term not recorded'}</span></div><div><span>Faculty</span><b>{row.allocation?.faculty || 'Needs faculty'}</b></div><div><span>Students</span><b>{row.student_count}</b></div><div><span>Timetable</span><b>{row.entries.length ? `${row.entries.length} current entr${row.entries.length === 1 ? 'y' : 'ies'}` : 'Missing timetable'}</b></div><em className={row.allocation && row.entries.length ? 'ready' : 'attention'}>{row.allocation && row.entries.length ? 'Ready' : row.allocation ? 'Timetable gap' : row.entries.length ? 'Allocation gap' : 'Delivery gaps'}</em></button><div className="hod-section-actions"><button onClick={() => setSelected(row)} type="button">View details</button><button onClick={() => go('hod_allocations')} type="button">Teaching allocations</button></div></article>)}{!visible.length && <Empty icon="○" text={rows.length ? 'No sections match the selected filters.' : 'No sections are available for this department.'} />}</div></section>
    <section className="hod-timetable-register" aria-label="Current timetable"><div className="hod-sections-register-head"><div><p>Current timetable</p><h2>{timetableRows.length} active entries</h2></div><span>Only active, in-effect timetable entries are shown.</span></div>{timetableRows.length ? <div className="hod-timetable-table" role="table"><div className="hod-timetable-row hod-timetable-labels" role="row"><span>Day &amp; time</span><span>Course / section</span><span>Faculty</span><span>Room</span></div>{timetableRows.map((entry: any) => <div className="hod-timetable-row" role="row" key={entry.id}><span><b>{days[entry.day_of_week] || `Day ${entry.day_of_week}`}</b><small>{entry.start_time} – {entry.end_time}</small></span><span><b>{entry.section.course_code}</b><small>Section {entry.section.section}</small></span><span>{entry.section.allocation?.faculty || 'Needs faculty'}</span><span>{[entry.building, entry.room].filter(Boolean).join(' · ') || 'Not recorded'}</span></div>)}</div> : <p className="hod-sections-empty">No current timetable entries match the selected filters.</p>}</section>
    {selected && <SectionDetail row={selected} onClose={() => setSelected(null)} onAllocation={() => go('hod_allocations')} />}
  </main>
}

function Stat({ value, label, helper, tone = '' }: any) { return <article className={tone}><b>{value}</b><span>{label}</span><small>{helper}</small></article> }
function Readiness({ label, value, detail }: any) { return <article><div><span>{label}</span><b>{value}%</b></div><i><span style={{ width: `${value}%` }} /></i><small>{detail}</small></article> }
function SectionDetail({ row, onClose, onAllocation }: any) { return <Modal className="modal-wide" title={`${row.course_code} · Section ${row.section}`} onClose={onClose} footer={<><button className="btn btn-out" onClick={onClose} type="button">Close</button><button className="btn btn-crimson" onClick={onAllocation} type="button">Teaching allocations</button></>}><section className="hod-section-detail"><div className="hod-section-detail-info"><span>Course</span><b>{row.course_title}</b><span>Program</span><b>{row.program ? `${row.program.code} · ${row.program.name}` : 'No program relation recorded'}</b><span>Semester</span><b>{row.course?.semester || '—'}</b><span>Term</span><b>{row.term || 'Not recorded'}</b><span>Active students</span><b>{row.student_count}</b><span>Faculty ownership</span><b>{row.allocation ? `${row.allocation.faculty} · active${row.allocation.effective_from ? ` from ${row.allocation.effective_from}` : ''}` : 'No active teaching allocation.'}</b></div><h3>Current timetable entries</h3>{row.entries.length ? <div className="hod-section-entry-list">{row.entries.map((entry: any) => <article key={entry.id}><div><b>{days[entry.day_of_week] || `Day ${entry.day_of_week}`}</b><span>{entry.start_time} – {entry.end_time}</span></div><div><span>Room</span><b>{[entry.building, entry.room].filter(Boolean).join(' · ') || 'Not recorded'}</b></div><div><span>Status</span><b>{entry.status}</b></div></article>)}</div> : <p className="hod-sections-empty">No current timetable entries are configured for this section.</p>}</section></Modal> }
