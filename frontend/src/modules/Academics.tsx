import { useEffect, useState } from 'react'
import { api } from '../api'
import { DecisionToast, GatedBtn, Modal, PageHead, Spinner } from './kit'

const DAY_OPTIONS = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
]

export default function Academics({ caps }: { caps: any }) {
  const [tab, setTab] = useState<'sections' | 'courses'>('sections')
  const [sections, setSections] = useState<any>(null)
  const [courses, setCourses] = useState<any>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [showTimetable, setShowTimetable] = useState(false)
  const [showAnnouncement, setShowAnnouncement] = useState(false)
  const [decision, setDecision] = useState<any>(null)
  const [selectedSection, setSelectedSection] = useState<any>(null)
  const [timetable, setTimetable] = useState<any>({ entries: [] })
  const [editingEntry, setEditingEntry] = useState<any>(null)
  const [form, setForm] = useState({ course_id: '', section_code: 'B', room: 'LH-5', schedule: 'Mon/Wed 10:00' })
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

  function load() {
    api.sections().then(setSections).catch(() => {})
    api.courses().then(setCourses).catch(() => {})
  }

  useEffect(() => {
    load()
  }, [])

  async function submitSection() {
    try {
      const response = await api.createSection(form)
      setDecision(response.decision)
      setShowAdd(false)
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

  if (!sections || !courses) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead
        title="Academics"
        sub="Course catalog, sections, timetable management, and targeted student notices"
        right={<GatedBtn can={!!caps.create_section} onClick={() => { setForm({ ...form, course_id: courses.courses[0]?.id || '' }); setShowAdd(true) }}>+ Create section</GatedBtn>}
      />

      <div className="tabs">
        <button className={`tab ${tab === 'sections' ? 'on' : ''}`} onClick={() => setTab('sections')} type="button">Sections ({sections.sections.length})</button>
        <button className={`tab ${tab === 'courses' ? 'on' : ''}`} onClick={() => setTab('courses')} type="button">Course catalog ({courses.courses.length})</button>
      </div>

      {tab === 'sections' && (
        <div className="card">
          <div className="tbl-scroll">
            <table className="tbl">
              <thead><tr><th>Course</th><th>Sec</th><th>Faculty</th><th>Schedule</th><th>Room</th><th>Enrolled</th><th>Manage</th></tr></thead>
              <tbody>
                {sections.sections.map((section: any) => (
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
                {courses.courses.map((course: any) => (
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

      {showAdd && (
        <Modal
          title="Create a new section"
          onClose={() => setShowAdd(false)}
          footer={<><button className="btn btn-out" onClick={() => setShowAdd(false)} type="button">Cancel</button><button className="btn btn-brass" onClick={submitSection} type="button">Create</button></>}
        >
          <div className="form-row"><label>Course</label>
            <select className="select" value={form.course_id} onChange={e => setForm({ ...form, course_id: e.target.value })}>
              {courses.courses.map((course: any) => <option key={course.id} value={course.id}>{course.code} — {course.title}</option>)}
            </select>
          </div>
          <div className="grid-2">
            <div className="form-row"><label>Section code</label><input className="inp" value={form.section_code} onChange={e => setForm({ ...form, section_code: e.target.value })} /></div>
            <div className="form-row"><label>Room</label><input className="inp" value={form.room} onChange={e => setForm({ ...form, room: e.target.value })} /></div>
          </div>
          <div className="form-row"><label>Schedule</label><input className="inp" value={form.schedule} onChange={e => setForm({ ...form, schedule: e.target.value })} /></div>
        </Modal>
      )}

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

            <div className="card">
              <div className="card-h"><h3>Current slots</h3></div>
              <div className="card-pad">
                {(timetable.entries || []).map((entry: any) => (
                  <div className="snap" key={entry.id}>
                    <span>{DAY_OPTIONS.find(day => day.value === entry.day_of_week)?.label || entry.day_of_week} • {entry.slot} • {entry.room}</span>
                    <span className="row-actions">
                      <button className="btn btn-sm btn-out" onClick={() => startEditEntry(entry)} type="button">Edit</button>
                      <button className="btn btn-sm btn-rose" onClick={() => deactivateEntry(entry.id)} type="button">Deactivate</button>
                    </span>
                  </div>
                ))}
                {(!timetable.entries || timetable.entries.length === 0) && <div className="empty">No timetable entries yet</div>}
              </div>
            </div>
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
