import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner } from '../modules/kit'

type Allocation = Record<string, any>

const blank = () => ({ course_id: '', section_id: '', faculty_id: '', lecture_hours: 0, lab_hours: 0, tutorial_hours: 0, workload_units: 0, effective_from: new Date().toISOString().slice(0, 10), effective_to: '', allocation_type: 'primary', is_coordinator: false })
const title = (value: string) => value ? value[0].toUpperCase() + value.slice(1) : '—'

export default function HodTeachingAllocations() {
  const [data, setData] = useState<any>(null), [error, setError] = useState(''), [notice, setNotice] = useState('')
  const [form, setForm] = useState<any>(blank()), [filters, setFilters] = useState({ course: '', section: '', faculty: '', status: 'all' })
  const [editing, setEditing] = useState<Allocation | null>(null), [ending, setEnding] = useState<Allocation | null>(null), [saving, setSaving] = useState(false)
  const load = async () => {
    setError('')
    try {
      const [allocationData, candidates, catalog] = await Promise.all([api.teachingAllocations(), api.teachingAllocationCandidates(), api.hodProgramsCourses()])
      setData({ allocations: allocationData.allocations || [], candidates, courses: catalog.courses || [] })
    } catch (err: any) { setError(err.message || 'Teaching allocations could not be loaded.') }
  }
  useEffect(() => { load() }, [])
  if (error && !data) return <Empty icon="!" text={error} />
  if (!data) return <Spinner />

  const allocations: Allocation[] = data.allocations
  const candidateSections = data.candidates?.sections || []
  const candidateFaculty = data.candidates?.faculty || []
  const courseMap = new Map((data.courses || []).map((course: any) => [course.id, course]))
  const courses = [...new Set(candidateSections.map((row: any) => row.course_id))].map(id => courseMap.get(id) || { id, code: 'Course', title: id })
  const formSections = candidateSections.filter((row: any) => !form.course_id || row.course_id === form.course_id)
  const currentForSection = allocations.filter(row => row.section_id === form.section_id && isCurrent(row))
  const active = allocations.filter(isCurrent), pending = allocations.filter(row => row.status === 'pending'), history = allocations.filter(row => !isCurrent(row) && row.status !== 'pending')
  const visible = allocations.filter(row => (!filters.course || row.course_id === filters.course) && (!filters.section || row.section_id === filters.section) && (!filters.faculty || row.faculty_id === filters.faculty) && (filters.status === 'all' || row.status === filters.status))
  const coverage = (() => {
    const activeSections = new Set(active.map(row => row.section_id))
    const activeCourses = new Set(active.map(row => row.course_id))
    const participatingFaculty = new Set(active.map(row => row.faculty_id))
    const uncovered = candidateSections.filter((section: any) => !activeSections.has(section.id))
    const future = allocations.filter(row => row.status === 'active' && row.effective_from && row.effective_from > new Date().toISOString().slice(0, 10))
    return {
      activeSections, activeCourses, participatingFaculty, uncovered, future,
      rows: [
        { label: 'Sections covered', numerator: activeSections.size, denominator: candidateSections.length, helper: 'Current sections with an in-effect faculty allocation' },
        { label: 'Courses covered', numerator: activeCourses.size, denominator: courses.length, helper: 'Courses represented by current allocations' },
        { label: 'Faculty participating', numerator: participatingFaculty.size, denominator: candidateFaculty.length, helper: 'Eligible department faculty with a current allocation' },
      ],
    }
  })()
  const resetForm = () => setForm(blank())
  const updateForm = (key: string, value: any) => setForm((current: any) => ({ ...current, [key]: value }))
  const chooseCourse = (course_id: string) => setForm((current: any) => ({ ...current, course_id, section_id: '', faculty_id: '' }))
  const chooseSection = (section_id: string) => {
    const section = candidateSections.find((row: any) => row.id === section_id)
    setForm((current: any) => ({ ...current, section_id, course_id: section?.course_id || current.course_id, faculty_id: '' }))
  }
  const datesValid = (value: any) => !value.effective_to || value.effective_to >= (value.effective_from || new Date().toISOString().slice(0, 10))
  const existingOverlap = currentForSection.some(row => rangesOverlap(form.effective_from, form.effective_to, row.effective_from, row.effective_to))
  const overlappingAllocation = currentForSection.find(row => rangesOverlap(form.effective_from, form.effective_to, row.effective_from, row.effective_to))
  const workloadValuesValid = [form.lecture_hours, form.lab_hours, form.tutorial_hours, form.workload_units].every(value => Number.isFinite(Number(value)) && Number(value) >= 0)
  const formIssue = existingOverlap
    ? 'This section already has an active faculty allocation. Use Reassign or End from Current Allocations.'
    : !form.course_id ? 'Select a course before creating an allocation.'
    : !form.section_id ? 'Select a section before creating an allocation.'
    : !form.faculty_id ? 'Select an eligible faculty member before creating an allocation.'
    : !datesValid(form) ? 'Effective To cannot be earlier than Effective From (or today when Effective From is empty).'
    : !workloadValuesValid ? 'Hours and Workload Units must be zero or a positive number.'
    : ''
  const canCreate = !saving && !formIssue
  const create = async () => {
    if (formIssue) return setError(formIssue)
    setSaving(true); setError(''); setNotice('')
    try { await api.createTeachingAllocation(payload(form)); await load(); resetForm(); setNotice('Allocation created with status pending.') } catch (err: any) { setError(err.message || 'Allocation could not be created.') } finally { setSaving(false) }
  }
  const activate = async (row: Allocation) => {
    setSaving(true); setError(''); setNotice('')
    try { await api.activateTeachingAllocation(row.id); await load(); setNotice('Allocation activated.') } catch (err: any) { setError(err.message || 'Allocation could not be activated.') } finally { setSaving(false) }
  }
  const saveEdit = async () => {
    if (!editing || !datesValid(editing)) return setError('Effective To cannot be earlier than Effective From.')
    const reassigned = editing.status === 'active' && editing.faculty_id !== editing.original_faculty_id
    if (reassigned && !window.confirm(`Replace ${editing.current_faculty} with the selected faculty member from ${editing.effective_from || 'today'}?`)) return
    setSaving(true); setError(''); setNotice('')
    try { await api.updateTeachingAllocation(editing.id, payload(editing)); await load(); setEditing(null); setNotice(reassigned ? 'Allocation reassigned.' : 'Allocation updated.') } catch (err: any) { setError(err.message || 'Allocation could not be updated.') } finally { setSaving(false) }
  }
  const end = async () => {
    if (!ending || !window.confirm(`End the ${ending.status} allocation for ${ending.course_code} · ${ending.section}? Historical records will be kept.`)) return
    setSaving(true); setError(''); setNotice('')
    try { await api.endTeachingAllocation(ending.id); await load(); setEnding(null); setNotice('Allocation ended and retained in history.') } catch (err: any) { setError(err.message || 'Allocation could not be ended.') } finally { setSaving(false) }
  }
  const openEdit = (row: Allocation) => setEditing({ ...row, original_faculty_id: row.faculty_id, current_faculty: row.faculty })
  const showCurrentAllocation = (row: Allocation, reassign = false) => {
    setFilters({ course: row.course_id, section: row.section_id, faculty: row.faculty_id, status: 'all' })
    window.setTimeout(() => document.getElementById(`allocation-${row.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 0)
    if (reassign) openEdit(row)
  }
  const courseLabel = (course: any) => `${course.code || 'Course'}${course.title ? ` — ${course.title}` : ''}`
  return <main className="hod-allocations-page fade-in">
    <header className="hod-allocations-heading"><div><p>Department academic operations</p><h1>Teaching Allocations</h1><span>Monitor and maintain the department’s shared course, section, and faculty allocations.</span></div><button className="btn btn-out" onClick={load} disabled={saving} type="button">Refresh</button></header>
    {error && <p className="hod-allocation-message error">{error}</p>}{notice && <p className="hod-allocation-message">{notice}</p>}
    <section className="hod-allocation-summary"><Stat label="Active Allocations" value={active.length} /><Stat label="Sections Covered" value={coverage.activeSections.size} /><Stat label="Sections Uncovered" value={coverage.uncovered.length} /><Stat label="Faculty Assigned" value={coverage.participatingFaculty.size} /></section>
    <section className="hod-allocation-coverage" aria-label="Allocation coverage">
      <header><div><h2>Allocation Coverage</h2><p>Calculated from the current shared allocation register and eligible department records.</p></div></header>
      <div>{coverage.rows.map(row => <CoverageCard key={row.label} {...row} />)}</div>
    </section>
    {(coverage.uncovered.length > 0 || pending.length > 0 || coverage.future.length > 0) && <section className="hod-allocation-attention" aria-label="Allocation needs attention"><header><div><h2>Needs Attention</h2><p>Only allocation states derived from the current department register are shown.</p></div></header><div>
      {coverage.uncovered.slice(0, 4).map((section: any) => <p key={section.id}><b>Section uncovered</b><span>{section.section}{section.term ? ` · ${section.term}` : ''} has no in-effect faculty allocation.</span></p>)}
      {pending.length > 0 && <p><b>Pending allocations</b><span>{pending.length} allocation{pending.length === 1 ? '' : 's'} await activation.</span></p>}
      {coverage.future.slice(0, 4).map((row: Allocation) => <p key={row.id}><b>Future allocation</b><span>{row.course_code} · Section {row.section} starts on {row.effective_from}.</span></p>)}
    </div></section>}
    <section className="hod-allocation-create"><header><div><h2>Create / Assign Faculty</h2><p>Eligible faculty are supplied by the department-scoped allocation candidate service.</p></div><span>New allocations start as pending</span></header><div className="hod-allocation-form">
      <label>Course<select value={form.course_id} onChange={event => chooseCourse(event.target.value)}><option value="">Select course</option>{courses.map((course: any) => <option key={course.id} value={course.id}>{courseLabel(course)}</option>)}</select></label>
      <label>Section<select value={form.section_id} onChange={event => chooseSection(event.target.value)} disabled={!form.course_id}><option value="">Select section</option>{formSections.map((row: any) => <option key={row.id} value={row.id}>{row.section}{row.term ? ` · ${row.term}` : ''}</option>)}</select></label>
      <label>Effective From<input type="date" value={form.effective_from} onChange={event => updateForm('effective_from', event.target.value)} /></label>
      <label>Effective To<input type="date" value={form.effective_to} min={form.effective_from || undefined} onChange={event => updateForm('effective_to', event.target.value)} /></label>
      <label>Lecture Hours<input type="number" min="0" value={form.lecture_hours} onChange={event => updateForm('lecture_hours', Number(event.target.value))} /></label>
      <label>Lab Hours<input type="number" min="0" value={form.lab_hours} onChange={event => updateForm('lab_hours', Number(event.target.value))} /></label>
      <label>Tutorial Hours<input type="number" min="0" value={form.tutorial_hours} onChange={event => updateForm('tutorial_hours', Number(event.target.value))} /></label>
      <label>Workload Units<input type="number" min="0" value={form.workload_units} onChange={event => updateForm('workload_units', Number(event.target.value))} /></label>
    </div>
    {existingOverlap && overlappingAllocation && <div className="hod-allocation-warning" role="alert"><span>This section already has an active faculty allocation. Use Reassign or End from Current Allocations.</span><div className="hod-allocation-warning-actions"><button onClick={() => showCurrentAllocation(overlappingAllocation)} type="button">View Current Allocation</button><button onClick={() => showCurrentAllocation(overlappingAllocation, true)} type="button">Reassign Faculty</button></div></div>}
    <div className="hod-candidates"><h3>Eligible Faculty</h3>{form.section_id ? <div>{candidateFaculty.map((row: any) => <button className={form.faculty_id === row.id ? 'selected' : ''} onClick={() => updateForm('faculty_id', row.id)} key={row.id} type="button"><b>{row.name}</b><span>Workload Units: {row.workload}</span></button>)}{!candidateFaculty.length && <p>No eligible faculty are available for this section.</p>}</div> : <p>Select a course and section to view eligible faculty.</p>}</div>
    {!existingOverlap && formIssue && <p className="hod-allocation-form-hint" aria-live="polite">{formIssue}</p>}
    <footer><button className="btn btn-out" onClick={resetForm} disabled={saving} type="button">Clear</button><button className="btn btn-crimson" onClick={create} disabled={!canCreate} aria-disabled={!canCreate} title={formIssue || undefined} type="button">{saving ? 'Saving…' : 'Create Allocation'}</button></footer></section>
    <AllocationFilters filters={filters} setFilters={setFilters} courses={courses} sections={candidateSections} faculty={candidateFaculty} />
    <AllocationTable title="Current Allocations" rows={visible.filter(isCurrent)} empty="No current teaching allocations." onEdit={openEdit} onActivate={activate} onEnd={setEnding} saving={saving} />
    <AllocationTable title="Pending Allocations" rows={visible.filter(row => row.status === 'pending')} empty="No pending allocations." onEdit={openEdit} onActivate={activate} onEnd={setEnding} saving={saving} />
    <AllocationTable title="Allocation History" rows={visible.filter(row => !isCurrent(row) && row.status !== 'pending')} empty="No historical allocations." history />
    {editing && <EditModal row={editing} candidates={candidateFaculty} saving={saving} onClose={() => setEditing(null)} onChange={setEditing} onSave={saveEdit} />}
    {ending && <Modal title="End Teaching Allocation" onClose={() => setEnding(null)} footer={<><button className="btn btn-out" onClick={() => setEnding(null)} type="button">Cancel</button><button className="btn btn-crimson" onClick={end} disabled={saving} type="button">{saving ? 'Ending…' : 'End Allocation'}</button></>}><p>End the {title(ending.status)} allocation for <b>{ending.course_code} · Section {ending.section}</b>. The allocation will remain in history.</p></Modal>}
  </main>
}

function isCurrent(row: Allocation) { const today = new Date().toISOString().slice(0, 10); return row.status === 'active' && (!row.effective_from || row.effective_from <= today) && (!row.effective_to || row.effective_to >= today) }
function rangesOverlap(from: string, to: string, otherFrom: string, otherTo: string) { const start = from || '0000-01-01', end = to || '9999-12-31', existingStart = otherFrom || '0000-01-01', existingEnd = otherTo || '9999-12-31'; return start <= existingEnd && existingStart <= end }
function payload(row: any) { return { faculty_id: row.faculty_id, course_id: row.course_id, section_id: row.section_id, allocation_type: row.allocation_type || 'primary', lecture_hours: Number(row.lecture_hours) || 0, lab_hours: Number(row.lab_hours) || 0, tutorial_hours: Number(row.tutorial_hours) || 0, workload_units: Number(row.workload_units) || 0, effective_from: row.effective_from || '', effective_to: row.effective_to || '', is_coordinator: Boolean(row.is_coordinator) } }
function Stat({ label, value }: { label: string, value: number }) { return <article><b>{value}</b><span>{label}</span></article> }

function CoverageCard({ label, numerator, denominator, helper }: { label: string, numerator: number, denominator: number, helper: string }) {
  const percentage = denominator ? Math.round((numerator / denominator) * 100) : null
  return <article><div><span>{label}</span><b>{percentage === null ? '—' : `${percentage}%`}</b></div><small>{numerator} / {denominator || '—'}</small><i><em style={{ width: `${percentage || 0}%` }} /></i><p>{helper}</p></article>
}

function AllocationFilters({ filters, setFilters, courses, sections, faculty }: any) { return <section className="hod-allocation-filters"><label>Course<select value={filters.course} onChange={event => setFilters({ ...filters, course: event.target.value, section: '' })}><option value="">All courses</option>{courses.map((row: any) => <option key={row.id} value={row.id}>{row.code}</option>)}</select></label><label>Section<select value={filters.section} onChange={event => setFilters({ ...filters, section: event.target.value })}><option value="">All sections</option>{sections.filter((row: any) => !filters.course || row.course_id === filters.course).map((row: any) => <option key={row.id} value={row.id}>{row.section}</option>)}</select></label><label>Faculty<select value={filters.faculty} onChange={event => setFilters({ ...filters, faculty: event.target.value })}><option value="">All faculty</option>{faculty.map((row: any) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label><label>Status<select value={filters.status} onChange={event => setFilters({ ...filters, status: event.target.value })}><option value="all">All statuses</option><option value="pending">Pending</option><option value="active">Active</option><option value="ended">Ended</option></select></label></section> }

function AllocationTable({ title: heading, rows, empty, onEdit, onActivate, onEnd, saving, history = false }: any) { return <article className="hod-allocation-table"><header><h2>{heading}</h2><span>{rows.length}</span></header><div><table><thead><tr><th>Course</th><th>Section</th><th>Faculty</th><th>Effective Dates</th><th>Workload Units</th><th>Status</th>{!history && <th>Actions</th>}</tr></thead><tbody>{rows.map((row: Allocation) => <tr id={`allocation-${row.id}`} key={row.id}><td><b>{row.course_code}</b><small>{row.course_title}</small></td><td>{row.section}</td><td>{row.faculty}</td><td>{row.effective_from || '—'}<small>{row.effective_to || 'Ongoing'}</small></td><td>{row.workload_units}</td><td><em className={`hod-allocation-status ${row.status}`}>{title(row.status)}</em></td>{!history && <td><div className="hod-allocation-actions">{row.status === 'pending' && <button onClick={() => onActivate(row)} disabled={saving} type="button">Activate</button>}{['pending', 'active'].includes(row.status) && <button onClick={() => onEdit(row)} disabled={saving} type="button">{row.status === 'active' ? 'Edit / Reassign' : 'Edit'}</button>}{['pending', 'active'].includes(row.status) && <button onClick={() => onEnd(row)} disabled={saving} type="button">End</button>}</div></td>}</tr>)}{!rows.length && <tr><td colSpan={history ? 6 : 7}>{empty}</td></tr>}</tbody></table></div></article> }

function EditModal({ row, candidates, saving, onClose, onChange, onSave }: any) { const update = (key: string, value: any) => onChange({ ...row, [key]: value }); return <Modal className="modal-wide" title={row.status === 'active' ? 'Edit / Reassign Teaching Allocation' : 'Edit Pending Teaching Allocation'} onClose={onClose} footer={<><button className="btn btn-out" onClick={onClose} type="button">Cancel</button><button className="btn btn-crimson" onClick={onSave} disabled={saving} type="button">{saving ? 'Saving…' : 'Save Allocation'}</button></>}><div className="hod-edit-context"><span>Course</span><b>{row.course_code} · Section {row.section}</b>{row.status === 'active' && <><span>Current Faculty</span><b>{row.current_faculty}</b></>}</div><div className="hod-allocation-form"><label>New Faculty<select value={row.faculty_id} onChange={event => update('faculty_id', event.target.value)}>{candidates.map((candidate: any) => <option key={candidate.id} value={candidate.id}>{candidate.name} · Workload Units {candidate.workload}</option>)}</select></label><label>Effective From<input type="date" value={row.effective_from || ''} onChange={event => update('effective_from', event.target.value)} /></label><label>Effective To<input type="date" min={row.effective_from || undefined} value={row.effective_to || ''} onChange={event => update('effective_to', event.target.value)} /></label><label>Lecture Hours<input type="number" min="0" value={row.lecture_hours || 0} onChange={event => update('lecture_hours', Number(event.target.value))} /></label><label>Lab Hours<input type="number" min="0" value={row.lab_hours || 0} onChange={event => update('lab_hours', Number(event.target.value))} /></label><label>Tutorial Hours<input type="number" min="0" value={row.tutorial_hours || 0} onChange={event => update('tutorial_hours', Number(event.target.value))} /></label><label>Workload Units<input type="number" min="0" value={row.workload_units || 0} onChange={event => update('workload_units', Number(event.target.value))} /></label></div></Modal> }
