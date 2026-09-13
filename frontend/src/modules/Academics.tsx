import { useEffect, useState } from 'react'
import { api } from '../api'
import { DecisionToast, GatedBtn, Modal, PageHead, Spinner, Pill } from './kit'

const DAY_OPTIONS = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
]

export default function Academics({ caps, go }: { caps: any, go?: (view: string) => void }) {
  const [tab, setTab] = useState<'sections' | 'courses' | 'offerings' | 'programmes'>('sections')
  const [sections, setSections] = useState<any>(null)
  const [courses, setCourses] = useState<any>(null)
  const [offerings, setOfferings] = useState<any>({ offerings: [] })
  const [programmes, setProgrammes] = useState<any>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [showProgrammeAdd, setShowProgrammeAdd] = useState(false)
  const [showTimetable, setShowTimetable] = useState(false)
  const [showAnnouncement, setShowAnnouncement] = useState(false)
  const [decision, setDecision] = useState<any>(null)
  const [selectedSection, setSelectedSection] = useState<any>(null)
  const [timetable, setTimetable] = useState<any>({ entries: [] })
  const [editingEntry, setEditingEntry] = useState<any>(null)
  const [form, setForm] = useState({ course_id: '', offering_id: '', section_code: 'A', room: 'LH-5', schedule: 'Mon/Wed 10:00', capacity: 60 })
  const [programmeForm, setProgrammeForm] = useState({ department_id: '', code: '', name: '', level: 'UG', duration_years: 4 })
  const [timetableForm, setTimetableForm] = useState({
    day_of_week: 0,
    start_time: '09:00',
    end_time: '10:00',
    room: 'LH-5',
    building: 'Academic Block',
    effective_from: '',
    effective_to: '',
  })
  const [announcementForm, setAnnouncementForm] = useState({
    title: '',
    body: '',
    audience: 'section',
    expires_at: '',
  })
  const [showHodReview, setShowHodReview] = useState(false)
  const [selectedOffering, setSelectedOffering] = useState<any>(null)
  const [hodReviewForm, setHodReviewForm] = useState({
    required_faculty_count: 0,
    required_sections: 0,
    expected_capacity: 0,
    delivery_type: 'theory',
    remarks: '',
  })
  const [savingHodReview, setSavingHodReview] = useState(false)
  const [submittingHodReview, setSubmittingHodReview] = useState(false)

  function load() {
    api.sections().then(setSections).catch(() => {})
    api.courses().then(setCourses).catch(() => {})
    api.academicProgrammes().then(setProgrammes).catch(() => {})
    api.courseOfferings().then((response) => setOfferings(response ?? { offerings: [] })).catch(() => setOfferings({ offerings: [] }))
    // Some endpoints may return an empty response while the database is still
    // starting.  Keep the view renderable until a later refresh succeeds.
    api.sections().then((response) => setSections(response ?? { sections: [] })).catch(() => setSections({ sections: [] }))
    api.courses().then((response) => setCourses(response ?? { courses: [] })).catch(() => setCourses({ courses: [] }))
  }

  useEffect(() => {
    load()
  }, [])

  async function submitSection() {
    const offering = (offerings.offerings || []).find((row: any) => row.id === form.offering_id)
    if (!offering) {
      setDecision({ outcome: 'DENY', reason: 'Choose an eligible course offering before creating a section.' })
      return
    }
    const requested = Number(offering.hod_input?.required_sections || 0)
    const created = Number(offering.sections?.length || 0)
    if (String(offering.hod_input?.status || '').toLowerCase() !== 'submitted' || requested <= created) {
      setDecision({ outcome: 'DENY', reason: 'This offering is not ready for another section. Select an offering with submitted HOD requirements and remaining section capacity.' })
      return
    }
    try {
      const response = await api.createSection(form)
      setDecision(response.decision)
      setShowAdd(false)
      load()
    } catch (error: any) {
      setDecision({ outcome: 'DENY', reason: error.message })
    }
  }

  async function submitProgramme() {
    if (!programmeForm.department_id || !programmeForm.code.trim() || !programmeForm.name.trim()) {
      setDecision({ outcome: 'DENY', reason: 'Choose a department and enter the programme code and name.' })
      return
    }
    try {
      const response = await api.createAcademicProgramme(programmeForm)
      setDecision(response.decision)
      setShowProgrammeAdd(false)
      setProgrammeForm({ department_id: '', code: '', name: '', level: 'UG', duration_years: 4 })
      load()
    } catch (error: any) {
      setDecision({ outcome: 'DENY', reason: error.message })
    }
  }

  async function openTimetable(section: any) {
    setSelectedSection(section)
    setEditingEntry(null)
    setTimetableForm({
      day_of_week: 0,
      start_time: '09:00',
      end_time: '10:00',
      room: section.room || 'LH-1',
      building: 'Academic Block',
      effective_from: '',
      effective_to: '',
    })
    try {
      const response = await api.sectionTimetable(section.id)
      setTimetable(response)
    } catch {
      setTimetable({ entries: [] })
    }
    setShowTimetable(true)
  }

  function startEditEntry(entry: any) {
    setEditingEntry(entry)
    setTimetableForm({
      day_of_week: entry.day_of_week,
      start_time: entry.start_time,
      end_time: entry.end_time,
      room: entry.room || selectedSection?.room || '',
      building: entry.building || 'Academic Block',
      effective_from: entry.effective_from || '',
      effective_to: entry.effective_to || '',
    })
  }

  async function saveTimetable() {
    if (!selectedSection) return
    if (!timetableForm.start_time || !timetableForm.end_time || timetableForm.end_time <= timetableForm.start_time) {
      setDecision({ outcome: 'DENY', reason: 'End time must be later than start time.' })
      return
    }
    if (timetableForm.effective_from && timetableForm.effective_to && timetableForm.effective_to < timetableForm.effective_from) {
      setDecision({ outcome: 'DENY', reason: 'Effective end date cannot be earlier than the start date.' })
      return
    }
    try {
      const response = editingEntry
        ? await api.updateTimetableEntry(editingEntry.id, timetableForm)
        : await api.createTimetableEntry(selectedSection.id, timetableForm)
      setDecision(response.decision)
      await openTimetable(selectedSection)
    } catch (error: any) {
      setDecision({ outcome: 'DENY', reason: error.message })
    }
  }

  async function deactivateEntry(entryId: string) {
    try {
      const response = await api.deactivateTimetableEntry(entryId)
      setDecision(response.decision)
      if (selectedSection) await openTimetable(selectedSection)
    } catch (error: any) {
      setDecision({ outcome: 'DENY', reason: error.message })
    }
  }

  async function publishAnnouncement() {
    if (!selectedSection) return
    try {
      const response = await api.publishAnnouncement({
        ...announcementForm,
        section_id: selectedSection.id,
      })
      setDecision(response.decision)
      setShowAnnouncement(false)
      setAnnouncementForm({ title: '', body: '', audience: 'section', expires_at: '' })
    } catch (error: any) {
      setDecision({ outcome: 'DENY', reason: error.message })
    }
  }

  async function openHodReview(offering: any) {
    try {
      const response = await api.hodInput(offering.id)
      const hod = response.hod_input || null
      setSelectedOffering(offering)
      setHodReviewForm({
        required_faculty_count: hod?.required_faculty_count ?? 0,
        required_sections: hod?.required_sections ?? 0,
        expected_capacity: hod?.expected_capacity ?? 0,
        delivery_type: hod?.delivery_type ?? 'theory',
        remarks: hod?.remarks ?? '',
      })
      setShowHodReview(true)
    } catch (error: any) {
      setSelectedOffering(offering)
      setHodReviewForm({
        required_faculty_count: 0,
        required_sections: 0,
        expected_capacity: 0,
        delivery_type: 'theory',
        remarks: '',
      })
      setShowHodReview(true)
    }
  }

  async function saveHodReview() {
    if (!selectedOffering) return
    setSavingHodReview(true)
    try {
      const response = await api.saveHodInput(selectedOffering.id, hodReviewForm)
      setDecision(response.decision)
      setShowHodReview(false)
      await load()
    } catch (error: any) {
      setDecision({ outcome: 'DENY', reason: error.message })
    } finally {
      setSavingHodReview(false)
    }
  }

  async function submitHodReview() {
    if (!selectedOffering) return
    setSubmittingHodReview(true)
    try {
      // Submit is the primary action in this modal. Persist the values first
      // so a newly opened offering does not fail because it has no HODInput
      // row yet (the API submit route deliberately only transitions a saved
      // input record).
      await api.saveHodInput(selectedOffering.id, hodReviewForm)
      const response = await api.submitHodInput(selectedOffering.id)
      setDecision(response.decision)
      setShowHodReview(false)
      await load()
    } catch (error: any) {
      setDecision({ outcome: 'DENY', reason: error.message })
    } finally {
      setSubmittingHodReview(false)
    }
  }

  function hodStatusText(offering: any) {
    const raw = String(offering?.hod_input?.status || '')
    const normalized = raw.toLowerCase()
    if (normalized === 'submitted') return 'Reviewed'
    if (normalized === 'reviewed' || normalized === 'completed' || normalized === 'approved') return 'Reviewed'
    return raw || 'Pending'
  }

  function workflowForOffering(offering: any) {
    if (Array.isArray(offering?.workflow) && offering.workflow.length) {
      return offering.workflow.map((step: any) => ({ label: step.label, detail: step.state === 'active' ? 'Current workflow stage' : step.completed ? 'Completed from live workflow state' : 'Waiting for the owning office', done: Boolean(step.completed), active: step.state === 'active' }))
    }
    const hodDone = String(offering?.hod_input?.status || '').toLowerCase() === 'submitted'
    return [
      { label: 'Offering', detail: 'Academic Coordinator created the offering', done: true },
      { label: 'HOD Review', detail: hodDone ? 'HOD reviewed and submitted input' : 'HOD input awaits submission', done: hodDone },
      { label: 'Faculty Allocation', detail: 'Faculty allocation can start after HOD review', done: hodDone },
      { label: 'Sections', detail: 'Sections are created from HOD requirements', done: Boolean(offering?.sections?.length) },
      { label: 'Timetable', detail: 'Timetable slots are linked to section readiness', done: Boolean(offering?.sections?.length) },
      { label: 'Dean Academics', detail: 'Dean review checks the downstream chain', done: false },
    ]
  }

  if (!sections || !courses || !programmes) return <Spinner />

  const sectionRows = Array.isArray(sections.sections) ? sections.sections : []
  const courseRows = Array.isArray(courses.courses) ? courses.courses : []
  const offeringRows = Array.isArray(offerings.offerings) ? offerings.offerings : []
  const eligibleSectionOfferings = offeringRows.filter((offering: any) => {
    const requested = Number(offering.hod_input?.required_sections || 0)
    const created = Number(offering.sections?.length || 0)
    return String(offering.hod_input?.status || '').toLowerCase() === 'submitted' && requested > created
  })
  const nextSectionCode = (offering: any) => {
    const used = new Set((offering?.sections || []).map((section: any) => String(section.section || '').trim().toUpperCase()))
    for (let index = 0; index < 26; index += 1) {
      const candidate = String.fromCharCode(65 + index)
      if (!used.has(candidate)) return candidate
    }
    return `S${used.size + 1}`
  }
  const openSectionCreate = (preferredOffering?: any) => {
    const offering = preferredOffering && eligibleSectionOfferings.some((row: any) => row.id === preferredOffering.id)
      ? preferredOffering
      : eligibleSectionOfferings[0]
    if (!offering) {
      setTab('offerings')
      setDecision({ outcome: 'DENY', reason: 'No offering is ready for a section yet. Submit HOD requirements and ensure its requested section count has not already been reached.' })
      return
    }
    setForm({ course_id: offering.course_id, offering_id: offering.id, section_code: nextSectionCode(offering), room: 'LH-5', schedule: 'Mon/Wed 10:00', capacity: 60 })
    setShowAdd(true)
  }
  const selectedSectionOffering = eligibleSectionOfferings.find((offering: any) => offering.id === form.offering_id)

  return (
    <div className="fade-in">
      <PageHead
        title="Academics"
        sub="Course catalog, sections, timetable management, and targeted student notices"
        right={tab === 'programmes' ? <GatedBtn can={!!caps.create_program} onClick={() => { setProgrammeForm({ ...programmeForm, department_id: programmes.departments[0]?.id || '' }); setShowProgrammeAdd(true) }}>+ Create programme</GatedBtn> : <GatedBtn can={!!caps.create_section} onClick={() => openSectionCreate()}>+ Create section</GatedBtn>}
      />

      <div className="tabs">
        <button className={`tab ${tab === 'programmes' ? 'on' : ''}`} onClick={() => setTab('programmes')} type="button">Programmes ({programmes.programmes.length})</button>
        <button className={`tab ${tab === 'sections' ? 'on' : ''}`} onClick={() => setTab('sections')} type="button">Sections ({sections.sections.length})</button>
        <button className={`tab ${tab === 'courses' ? 'on' : ''}`} onClick={() => setTab('courses')} type="button">Course catalog ({courses.courses.length})</button>
        <button className={`tab ${tab === 'offerings' ? 'on' : ''}`} onClick={() => setTab('offerings')} type="button">Course offerings ({offerings.offerings?.length || 0})</button>
      </div>

      {tab === 'programmes' && <div className="card"><div className="card-pad"><p className="hint">Create the programme master here, then the Admissions Office can add it to an admission cycle.</p></div><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Code</th><th>Programme</th><th>Department</th><th>Level</th><th>Duration</th></tr></thead><tbody>{programmes.programmes.map((programme: any) => <tr key={programme.id}><td className="mono"><b>{programme.code}</b></td><td>{programme.name}</td><td>{programme.department}</td><td>{programme.level}</td><td>{programme.duration_years} years</td></tr>)}</tbody></table></div></div>}

      {tab === 'sections' && (
        <div className="card">
          <div className="tbl-scroll">
            <table className="tbl">
              <thead><tr><th>Course</th><th>Sec</th><th>Faculty</th><th>Schedule</th><th>Room</th><th>Enrolled</th><th>Manage</th></tr></thead>
              <tbody>
                {sectionRows.map((section: any) => (
                  <tr key={section.id}>
                    <td><b className="mono">{section.course_code}</b> • {section.course_title}</td>
                    <td>{section.section}</td>
                    <td>{section.faculty}</td>
                    <td>{section.schedule}</td>
                    <td>{section.room}</td>
                    <td><span className="fill-bar"><span style={{ width: `${(section.enrolled / section.capacity) * 100}%` }} /></span> {section.enrolled}/{section.capacity}</td>
                    <td>
                      <div className="row-actions">
                        {caps.manage_timetable && <button className="btn btn-sm btn-out" onClick={() => openTimetable(section)} type="button">Timetable</button>}
                        {caps.publish_announcement && <button className="btn btn-sm btn-out" onClick={() => { setSelectedSection(section); setShowAnnouncement(true) }} type="button">Notice</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'courses' && (
        <div className="card">
          <div className="tbl-scroll">
            <table className="tbl">
              <thead><tr><th>Code</th><th>Title</th><th>Dept</th><th>Credits</th><th>Semester</th></tr></thead>
              <tbody>
                {courseRows.map((course: any) => (
                  <tr key={course.id}>
                    <td className="mono"><b>{course.code}</b></td>
                    <td>{course.title}</td>
                    <td>{course.dept}</td>
                    <td>{course.credits}</td>
                    <td>Sem {course.semester}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'offerings' && (
        <div className="card">
          <div className="card-pad">
            <p className="hint">Coordinator-created offerings within your department scope. Operational changes remain with the Academic Coordinator.</p>
          </div>
          <div className="tbl-scroll">
            <table className="tbl">
              <thead><tr><th>Course</th><th>Program</th><th>Academic year / term</th><th>Status</th><th>HOD input</th><th>Sections</th><th>Readiness</th></tr></thead>
              <tbody>
                {(offerings.offerings || []).map((offering: any) => (
                  <tr key={offering.id}>
                    <td><b className="mono">{offering.course_code}</b><br />{offering.course_title}</td>
                    <td>{offering.program_code || offering.program}</td>
                    <td>{offering.academic_year}<br /><span className="hint">{offering.term}</span></td>
                    <td><span className="state-pill">{offering.status}</span></td>
                    <td><span className="state-pill" onClick={() => openHodReview(offering)} style={{ cursor: 'pointer' }}>{hodStatusText(offering)}</span></td>
                    <td>{offering.sections?.length || 0} / {offering.hod_input?.required_sections || 0}</td>
                    <td>
                      <div className="row-actions">
                        <button className="btn btn-sm btn-out" onClick={() => openHodReview(offering)} type="button">Workflow</button>
                        {eligibleSectionOfferings.some((row: any) => row.id === offering.id) && caps.create_section && <button className="btn btn-sm btn-brass" onClick={() => openSectionCreate(offering)} type="button">Add section</button>}
                      </div>
                      <div className="hint">{offering.readiness?.ready ? 'Ready' : 'In preparation'}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!offerings.offerings?.length && <div className="card-pad"><p className="hint">No course offerings are currently visible in your department scope.</p></div>}
        </div>
      )}

      {showAdd && (
        <Modal
          title="Create a course section"
          onClose={() => setShowAdd(false)}
          footer={<><button className="btn btn-out" onClick={() => setShowAdd(false)} type="button">Cancel</button><button className="btn btn-brass" onClick={submitSection} disabled={!selectedSectionOffering} type="button">Create section</button></>}
        >
          <div className="card-pad" style={{ marginBottom: 14, borderRadius: 12, background: 'linear-gradient(135deg, #f8f3f5, #fff)' }}>
            <b>Section planning</b><p className="hint" style={{ margin: '5px 0 0' }}>Only offerings with submitted HOD requirements and remaining section capacity are available.</p>
          </div>
          <div className="form-row"><label>Eligible course offering</label>
            <select className="select" value={form.offering_id} onChange={e => { const offering = eligibleSectionOfferings.find((row: any) => row.id === e.target.value); if (offering) setForm({ ...form, offering_id: offering.id, course_id: offering.course_id, section_code: nextSectionCode(offering) }) }}>
              {eligibleSectionOfferings.map((offering: any) => <option key={offering.id} value={offering.id}>{offering.course_code} — {offering.course_title} · {offering.program_code || offering.program}</option>)}
            </select>
          </div>
          {selectedSectionOffering && <div className="grid-2" style={{ marginBottom: 14 }}><div className="form-row"><label>HOD-approved sections</label><div className="inp" style={{ background: '#f8f9fb' }}>{selectedSectionOffering.sections?.length || 0} created of {selectedSectionOffering.hod_input?.required_sections || 0} requested</div></div><div className="form-row"><label>Department capacity target</label><div className="inp" style={{ background: '#f8f9fb' }}>{selectedSectionOffering.hod_input?.expected_capacity || 'Not specified'} students</div></div></div>}
          <div className="grid-2">
            <div className="form-row"><label>Section code</label><input className="inp" value={form.section_code} maxLength={12} onChange={e => setForm({ ...form, section_code: e.target.value.toUpperCase() })} /></div>
            <div className="form-row"><label>Section capacity</label><input className="inp" type="number" min="1" max="1000" value={form.capacity} onChange={e => setForm({ ...form, capacity: Number(e.target.value || 1) })} /></div>
          </div>
          <div className="grid-2">
            <div className="form-row"><label>Room</label><input className="inp" value={form.room} onChange={e => setForm({ ...form, room: e.target.value })} /></div>
            <div className="form-row"><label>Schedule</label><input className="inp" value={form.schedule} onChange={e => setForm({ ...form, schedule: e.target.value })} /></div>
          </div>
        </Modal>
      )}

      {showProgrammeAdd && <Modal title="Create academic programme" onClose={() => setShowProgrammeAdd(false)} footer={<><button className="btn btn-out" onClick={() => setShowProgrammeAdd(false)} type="button">Cancel</button><button className="btn btn-brass" onClick={submitProgramme} type="button">Create programme</button></>}><div className="form-row"><label>Department</label><select className="select" value={programmeForm.department_id} onChange={e => setProgrammeForm({ ...programmeForm, department_id: e.target.value })}><option value="">Choose department</option>{programmes.departments.map((department: any) => <option key={department.id} value={department.id}>{department.code} - {department.name}</option>)}</select></div><div className="grid-2"><div className="form-row"><label>Programme code</label><input className="inp" value={programmeForm.code} onChange={e => setProgrammeForm({ ...programmeForm, code: e.target.value.toUpperCase() })} placeholder="BTECH-AI" /></div><div className="form-row"><label>Level</label><select className="select" value={programmeForm.level} onChange={e => setProgrammeForm({ ...programmeForm, level: e.target.value })}>{['UG', 'PG', 'DIPLOMA', 'PHD', 'CERTIFICATE'].map(level => <option key={level}>{level}</option>)}</select></div></div><div className="grid-2"><div className="form-row"><label>Programme name</label><input className="inp" value={programmeForm.name} onChange={e => setProgrammeForm({ ...programmeForm, name: e.target.value })} placeholder="B.Tech Artificial Intelligence" /></div><div className="form-row"><label>Duration in years</label><input className="inp" type="number" min="1" max="10" value={programmeForm.duration_years} onChange={e => setProgrammeForm({ ...programmeForm, duration_years: Number(e.target.value) })} /></div></div></Modal>}

      {showTimetable && (
        <Modal
          title={`Timetable • ${selectedSection?.course_code || ''} ${selectedSection?.section || ''}`}
          onClose={() => setShowTimetable(false)}
          className="modal-wide"
          footer={<><button className="btn btn-out" onClick={() => setShowTimetable(false)} type="button">Close</button><button className="btn btn-brass" onClick={saveTimetable} type="button">{editingEntry ? 'Update slot' : 'Add slot'}</button></>}
        >
          <div className="grid-2">
            <div>
              <div className="form-row"><label>Day</label>
                <select className="select" value={timetableForm.day_of_week} onChange={e => setTimetableForm({ ...timetableForm, day_of_week: Number(e.target.value) })}>
                  {DAY_OPTIONS.map(day => <option key={day.value} value={day.value}>{day.label}</option>)}
                </select>
              </div>
              <div className="grid-2">
                <div className="form-row"><label>Start time</label><input className="inp" type="time" value={timetableForm.start_time} onChange={e => setTimetableForm({ ...timetableForm, start_time: e.target.value })} /></div>
                <div className="form-row"><label>End time</label><input className="inp" type="time" value={timetableForm.end_time} onChange={e => setTimetableForm({ ...timetableForm, end_time: e.target.value })} /></div>
              </div>
              <div className="grid-2">
                <div className="form-row"><label>Room</label><input className="inp" value={timetableForm.room} onChange={e => setTimetableForm({ ...timetableForm, room: e.target.value })} /></div>
                <div className="form-row"><label>Building</label><input className="inp" value={timetableForm.building} onChange={e => setTimetableForm({ ...timetableForm, building: e.target.value })} /></div>
              </div>
            </div>

            <div className="card timetable-week-grid">
              <div className="card-h"><h3>Weekly timetable</h3><span className="hint">{(timetable.entries || []).length} active slots</span></div>
              <div className="card-pad">
                <div className="timetable-grid-head"><span>Day</span><span>Slots</span></div>
                {DAY_OPTIONS.map(day => {
                  const dayEntries = (timetable.entries || []).filter((entry: any) => entry.day_of_week === day.value)
                  return <div className="timetable-grid-row" key={day.value}><strong>{day.label}</strong><div>{dayEntries.length ? dayEntries.map((entry: any) => <div className="timetable-slot" key={entry.id}><span><b>{entry.slot}</b> · {entry.room || 'Room TBD'}</span><span className="row-actions"><button className="btn btn-sm btn-out" onClick={() => startEditEntry(entry)} type="button">Edit</button><button className="btn btn-sm btn-rose" onClick={() => deactivateEntry(entry.id)} type="button">Deactivate</button></span></div>) : <span className="hint">No class scheduled</span>}</div></div>
                })}
                {(!timetable.entries || timetable.entries.length === 0) && <div className="empty">No timetable entries yet</div>}
              </div>
            </div>
          </div>
        </Modal>
      )}

      {showHodReview && selectedOffering && (
        <Modal
          title={`HOD Review • ${selectedOffering.course_code || selectedOffering.course_title || 'Course offering'}`}
          className="hod-workflow-modal"
          onClose={() => setShowHodReview(false)}
          footer={<>
            <button className="btn btn-out" onClick={() => setShowHodReview(false)} type="button">Close</button>
            <button className="btn btn-out" onClick={saveHodReview} disabled={savingHodReview} type="button">{savingHodReview ? 'Saving...' : 'Save HOD input'}</button>
            <button className="btn btn-brass" onClick={submitHodReview} disabled={submittingHodReview} type="button">{submittingHodReview ? 'Submitting...' : 'Submit HOD input'}</button>
          </>}
        >
          <style>{`
            .hod-workflow { display: grid; gap: 18px; color: #24262c; }
            .hod-workflow-hero { padding: 22px; border-radius: 16px; color: #fff; background: linear-gradient(135deg,#4a1630,#812b4a 62%,#b98b42); display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }
            .hod-workflow-kicker { font-size:10px; letter-spacing:.12em; font-weight:800; opacity:.75; text-transform:uppercase; }
            .hod-workflow-hero h3 { margin:6px 0; font-size:22px; color:#fff; }.hod-workflow-hero p { margin:0; opacity:.85; font-size:13px; }
            .hod-workflow-stage { background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.25); border-radius:10px; padding:8px 11px; text-align:right; font-size:11px; }.hod-workflow-stage b{display:block;font-size:13px;margin-top:3px;}
            .hod-timeline { border:1px solid #e8e9ed; border-radius:16px; padding:18px; background:#fff; }.hod-timeline-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:14px;}.hod-timeline-head h4{margin:0;font-size:14px;}.hod-timeline-head span{font-size:12px;color:#727780;}
            .hod-timeline-steps { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }.hod-step{min-height:80px;padding:11px;border:1px solid #e8e9ed;border-radius:12px;background:#fafafb;}.hod-step-dot{width:23px;height:23px;border-radius:50%;display:grid;place-items:center;background:#d9dce1;color:#68707b;font-size:12px;font-weight:800;margin-bottom:7px;}.hod-step.done{background:#f1faf4;border-color:#cce8d5;}.hod-step.done .hod-step-dot{background:#25834d;color:#fff}.hod-step.active{background:#fff8ea;border-color:#eed69c;box-shadow:0 3px 12px rgba(154,112,24,.12)}.hod-step.active .hod-step-dot{background:#a56d14;color:#fff}.hod-step b{display:block;font-size:12px;line-height:1.3}.hod-step small{display:block;margin-top:4px;color:#767b84;font-size:10px;text-transform:uppercase;font-weight:700;letter-spacing:.04em}.hod-input-panel{border:1px solid #e8e9ed;border-radius:16px;padding:18px;background:linear-gradient(135deg,#fff,#faf9fb)}.hod-input-panel h4{margin:0 0 4px}.hod-input-panel p{margin:0 0 16px;color:#737881;font-size:12px}@media(max-width:650px){.hod-workflow-hero{flex-direction:column}.hod-timeline-steps{grid-template-columns:repeat(2,minmax(0,1fr))}}
          `}</style>
          <div className="hod-workflow">
          <section className="hod-workflow-hero">
            <div><span className="hod-workflow-kicker">HOD academic review</span><h3>{selectedOffering.course_code} · {selectedOffering.course_title}</h3><p>{selectedOffering.program_code || selectedOffering.program} · {selectedOffering.academic_year} · {selectedOffering.term}</p></div>
            <div className="hod-workflow-stage">Current offering state<b>{selectedOffering.status || 'Draft'}</b></div>
          </section>
          <section className="hod-timeline"><div className="hod-timeline-head"><h4>Live workflow timeline</h4><span>Next: {selectedOffering.next_expected_action || 'Review HOD requirements'}</span></div><div className="hod-timeline-steps">
            {workflowForOffering(selectedOffering).map((step: any, index: number) => <div key={step.label} className={`hod-step ${step.done ? 'done' : step.active ? 'active' : ''}`}><div className="hod-step-dot">{step.done ? '✓' : index + 1}</div><b>{step.label}</b><small>{step.done ? 'Completed' : step.active ? 'In progress' : 'Waiting'}</small></div>)}
          </div></section>
          <section className="hod-input-panel"><h4>Department delivery requirements</h4><p>Save a draft while planning. Submit only when the department requirements are complete.</p>
          <div className="grid-2">
            <div className="form-row">
              <label>Required faculty count</label>
              <input className="inp" type="number" min="0" value={hodReviewForm.required_faculty_count} onChange={e => setHodReviewForm({ ...hodReviewForm, required_faculty_count: Number(e.target.value || 0) })} />
            </div>
            <div className="form-row">
              <label>Required sections</label>
              <input className="inp" type="number" min="0" value={hodReviewForm.required_sections} onChange={e => setHodReviewForm({ ...hodReviewForm, required_sections: Number(e.target.value || 0) })} />
            </div>
            <div className="form-row">
              <label>Expected capacity</label>
              <input className="inp" type="number" min="0" value={hodReviewForm.expected_capacity} onChange={e => setHodReviewForm({ ...hodReviewForm, expected_capacity: Number(e.target.value || 0) })} />
            </div>
            <div className="form-row">
              <label>Delivery type</label>
              <select className="select" value={hodReviewForm.delivery_type} onChange={e => setHodReviewForm({ ...hodReviewForm, delivery_type: e.target.value })}>
                <option value="theory">Theory</option>
                <option value="lab">Lab</option>
                <option value="hybrid">Hybrid</option>
                <option value="blended">Blended</option>
              </select>
            </div>
          </div>
          <div className="form-row">
            <label>HOD remarks</label>
            <textarea className="inp" rows={5} value={hodReviewForm.remarks} onChange={e => setHodReviewForm({ ...hodReviewForm, remarks: e.target.value })} />
          </div>
          </section>
          </div>
        </Modal>
      )}

      {showAnnouncement && (
        <Modal
          title={`Publish announcement • ${selectedSection?.course_code || 'Section'}`}
          onClose={() => setShowAnnouncement(false)}
          footer={<><button className="btn btn-out" onClick={() => setShowAnnouncement(false)} type="button">Cancel</button><button className="btn btn-brass" onClick={publishAnnouncement} type="button">Publish</button></>}
        >
          <div className="form-row"><label>Title</label><input className="inp" value={announcementForm.title} onChange={e => setAnnouncementForm({ ...announcementForm, title: e.target.value })} /></div>
          <div className="form-row"><label>Message</label><textarea className="inp" rows={5} value={announcementForm.body} onChange={e => setAnnouncementForm({ ...announcementForm, body: e.target.value })} /></div>
          <div className="grid-2">
            <div className="form-row"><label>Audience</label><input className="inp" value="Selected section" disabled /></div>
            <div className="form-row"><label>Expires at</label><input className="inp" type="datetime-local" value={announcementForm.expires_at} onChange={e => setAnnouncementForm({ ...announcementForm, expires_at: e.target.value })} /></div>
          </div>
        </Modal>
      )}

      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
