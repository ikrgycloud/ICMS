import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, PageHead, Spinner, money } from '../modules/kit'

export function StudentCalendarView({ user, go }: { user: any; go: (v: string) => void }) {
  const [month, setMonth] = useState(studentMonthStart())
  const [selectedDate, setSelectedDate] = useState(todayDateKey())
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [savingPersonal, setSavingPersonal] = useState(false)
  const [showPersonalModal, setShowPersonalModal] = useState(false)
  const [personalForm, setPersonalForm] = useState(() => blankPersonalEvent(todayDateKey()))

  useEffect(() => {
    let active = true

    async function load() {
      setLoading(true)
      setError('')
      try {
        const next = await api.studentCalendar(month)
        if (active) setData(next)
      } catch (err: any) {
        if (active) {
          setError(err?.message || 'We could not load your calendar right now.')
          setData(null)
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [month])

  const selected = parseIsoDate(selectedDate)
  const yearOptions = useMemo(() => buildStudentYearOptions(selected.getFullYear()), [selectedDate])
  const monthDays = useMemo(
    () => buildStudentMonthGrid(data?.range?.start || month),
    [data?.range?.start, month],
  )
  const eventsByDay = useMemo(
    () => groupStudentCalendarEvents(data?.events || []),
    [data?.events],
  )
  const visibleEventCount = data?.summary?.month_events ?? 0

  function syncSelection(nextDate: string) {
    setSelectedDate(nextDate)
    setMonth(studentMonthStart(parseIsoDate(nextDate)))
  }

  function jumpToday() {
    syncSelection(todayDateKey())
  }

  function shiftSelection(delta: number) {
    syncSelection(shiftStudentReferenceDate(selectedDate, delta))
  }

  function applyMonthIndex(monthIndex: number) {
    syncSelection(buildDateWithMonth(selectedDate, monthIndex))
  }

  function applyYearValue(year: number) {
    syncSelection(buildDateWithYear(selectedDate, year))
  }

  function openCreatePersonalEvent() {
    setError('')
    setPersonalForm(blankPersonalEvent(selectedDate))
    setShowPersonalModal(true)
  }

  function closePersonalModal() {
    setError('')
    setShowPersonalModal(false)
    setPersonalForm(blankPersonalEvent(selectedDate))
  }

  async function savePersonalEvent() {
    const title = String(personalForm.title || '').trim()
    if (!title) {
      setError('Event title is required.')
      return
    }
    const payload = buildPersonalEventPayload(personalForm)
    const fromDate = new Date(payload.start_at)
    const toDate = new Date(payload.end_at)
    if (Number.isNaN(+fromDate) || Number.isNaN(+toDate)) {
      setError('From and to date/time are required.')
      return
    }
    if (toDate < fromDate) {
      setError('To date and time must be after the from date and time.')
      return
    }

    try {
      setSavingPersonal(true)
      setError('')
      if (personalForm.id) await api.updateStudentCalendarPersonalEvent(personalForm.id, payload)
      else await api.createStudentCalendarPersonalEvent(payload)

      const targetDate = personalForm.startDate || selectedDate
      const targetMonth = studentMonthStart(parseIsoDate(targetDate))
      setSelectedDate(targetDate)
      setShowPersonalModal(false)
      setPersonalForm(blankPersonalEvent(targetDate))

      if (targetMonth === month) {
        const next = await api.studentCalendar(targetMonth)
        setData(next)
      } else {
        setMonth(targetMonth)
      }
    } catch (err: any) {
      setError(err?.message || 'We could not save your personal event.')
    } finally {
      setSavingPersonal(false)
    }
  }

  async function deletePersonalEvent() {
    if (!personalForm.id) return
    try {
      setSavingPersonal(true)
      setError('')
      await api.deleteStudentCalendarPersonalEvent(personalForm.id)

      const targetDate = personalForm.startDate || selectedDate
      const targetMonth = studentMonthStart(parseIsoDate(targetDate))
      setShowPersonalModal(false)
      setPersonalForm(blankPersonalEvent(targetDate))

      if (targetMonth === month) {
        const next = await api.studentCalendar(targetMonth)
        setData(next)
      } else {
        setMonth(targetMonth)
      }
    } catch (err: any) {
      setError(err?.message || 'We could not delete your personal event.')
    } finally {
      setSavingPersonal(false)
    }
  }

  function openCalendarEvent(event: any) {
    if (event.kind === 'personal') {
      setError('')
      setPersonalForm({
        id: event.personal_event_id || event.personalEventId,
        title: event.title,
        startDate: event.rawStartDate || event.rawDate || selectedDate,
        startTime: event.rawStartTime || event.rawTime || '09:00',
        endDate: event.rawEndDate || event.rawStartDate || event.rawDate || selectedDate,
        endTime: event.rawEndTime || event.rawTime || '10:00',
        note: event.note || '',
      })
      setShowPersonalModal(true)
      return
    }
    go(event.module || 'calendar')
  }

  if (loading && !data) return <Spinner />

  return (
    <div className="student-calendar-page fade-in">
      <PageHead
        title="My Calendar"
        sub="Track classes, academic milestones, assignments, quizzes, and important due dates in one place."
      />

      {error && <div className="calendar-banner warn">{error}</div>}

      {data && (
        <div className="student-calendar-shell">
          <div className="student-calendar-main">
            <div className="student-calendar-kpis">
              <StudentCalendarStat
                kind="month"
                label="This Month"
                value={visibleEventCount}
                sub="Events in view"
              />
              <StudentCalendarStat
                kind="class"
                label="Classes Today"
                value={data.summary?.classes_today ?? 0}
                sub="Scheduled sessions"
              />
              <StudentCalendarStat
                kind="assignment"
                label="Assignments Due"
                value={data.summary?.due_assignments ?? 0}
                sub="Due this month"
              />
              <StudentCalendarStat
                kind="assessment"
                label="Upcoming Quiz / Test"
                value={data.summary?.upcoming_assessments ?? 0}
                sub="Scheduled this month"
              />
            </div>

            <section className="student-calendar-board-card student-calendar-surface">
              <div className="student-calendar-toolbar">
                <div className="student-calendar-command-bar">
                  <div className="student-calendar-month-chip">
                    <span className="student-calendar-month-icon">
                      <StudentCalendarGlyph kind="month" />
                    </span>
                    <div className="student-calendar-month-copy">
                      <b>{data.range?.label || formatMonthLabel(month)}</b>
                      <small>{formatLongDate(selected)}</small>
                    </div>
                  </div>

                  <div className="student-calendar-selector-cluster">
                    <label className="student-calendar-selector-segment">
                      <span>Month</span>
                      <select
                        className="student-calendar-select"
                        value={String(selected.getMonth())}
                        onChange={event => applyMonthIndex(Number(event.target.value))}
                      >
                        {studentMonthOptions().map((label, index) => (
                          <option key={label} value={index}>{label}</option>
                        ))}
                      </select>
                    </label>

                    <label className="student-calendar-selector-segment">
                      <span>Year</span>
                      <select
                        className="student-calendar-select"
                        value={String(selected.getFullYear())}
                        onChange={event => applyYearValue(Number(event.target.value))}
                      >
                        {yearOptions.map(year => (
                          <option key={year} value={year}>{year}</option>
                        ))}
                      </select>
                    </label>

                    <label className="student-calendar-selector-segment date">
                      <span>Date</span>
                      <input
                        className="student-calendar-picker-input"
                        type="date"
                        value={selectedDate}
                        onChange={event => syncSelection(event.target.value)}
                      />
                    </label>
                  </div>

                  <div className="student-calendar-action-strip">
                    <button className="student-calendar-ghost-btn" onClick={jumpToday} type="button">Today</button>

                    <div className="student-calendar-nav">
                      <button onClick={() => shiftSelection(-1)} type="button" aria-label="Previous month">‹</button>
                      <button onClick={() => shiftSelection(1)} type="button" aria-label="Next month">›</button>
                    </div>

                    <button className="student-calendar-add-btn" onClick={openCreatePersonalEvent} type="button">
                      <span>+</span>
                      Add Event
                    </button>
                  </div>
                </div>

                <div className="student-calendar-legend">
                  <span><i className="class" /> Classes</span>
                  <span><i className="academic" /> Academic Events</span>
                  <span><i className="assignment" /> Assignments</span>
                  <span><i className="assessment" /> Quiz / Test</span>
                  <span><i className="finance" /> Fee Due</span>
                  <span><i className="library" /> Library</span>
                  <span><i className="personal" /> My Events</span>
                </div>
              </div>

              <div className="student-calendar-board-wrap">
                <div className="student-calendar-board">
                  {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(label => (
                    <div className="student-calendar-weekday" key={label}>{label}</div>
                  ))}

                  {monthDays.map(day => {
                    const dayEvents = eventsByDay[day.key] || []
                    return (
                      <div
                        key={day.key}
                        className={`student-calendar-cell ${day.currentMonth ? '' : 'muted'} ${day.today ? 'today' : ''}`}
                      >
                        <div className="student-calendar-cell-top">
                          <span>{day.date.getDate()}</span>
                          {day.today && <em>Today</em>}
                        </div>

                        <div className="student-calendar-cell-events">
                          {dayEvents.slice(0, 3).map((event: any) => (
                            <button
                              key={`${day.key}-${event.id}`}
                              className={`student-calendar-pill ${event.kind}`}
                              onClick={() => openCalendarEvent(event)}
                              title={[event.title, event.time_label, event.source_label].filter(Boolean).join(' · ')}
                              type="button"
                            >
                              <strong>{event.title}</strong>
                              <span>{event.time_label || event.subtitle || event.category}</span>
                            </button>
                          ))}
                          {dayEvents.length > 3 && <div className="student-calendar-more">+{dayEvents.length - 3} more</div>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </section>
          </div>

          <aside className="student-calendar-side">
            <StudentCalendarPanel
              title="Today's Schedule"
              meta={formatLongDate(new Date())}
              actionLabel="View full timetable"
              onAction={() => go('academics')}
            >
              {data.today_schedule?.length ? (
                <div className="student-calendar-schedule-list">
                  {data.today_schedule.map((item: any) => (
                    <button className="student-calendar-schedule-row" key={item.timetable_entry_id} onClick={() => go('academics')} type="button">
                      <div className="student-calendar-schedule-time">
                        <strong>{formatClockLabel(item.start_time)}</strong>
                        <span>{formatClockLabel(item.end_time)}</span>
                      </div>
                      <i className="student-calendar-schedule-dot" />
                      <div className="student-calendar-schedule-copy">
                        <div className="student-calendar-row-title">{item.course_title || item.course_code}</div>
                        <div className="student-calendar-row-sub">{item.faculty} · {item.room || 'Room TBA'}</div>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <Empty icon="Calendar" text="No classes scheduled for today." />
              )}
            </StudentCalendarPanel>

            <StudentCalendarPanel title="Upcoming Deadlines">
              {data.deadlines?.length ? (
                <div className="student-calendar-side-list">
                  {data.deadlines.map((item: any) => (
                    <button className="student-calendar-side-row" key={item.id} onClick={() => go(item.module || 'calendar')} type="button">
                      <span className={`student-calendar-side-icon ${item.kind}`}>
                        <StudentCalendarGlyph kind={item.kind} />
                      </span>
                      <div className="student-calendar-side-copy">
                        <div className="student-calendar-row-title">{item.title}</div>
                        <div className="student-calendar-row-sub">
                          {item.course_code ? `${item.course_code} · ` : ''}{item.subtitle}
                        </div>
                      </div>
                      <span className={`student-calendar-side-badge ${item.kind}`}>
                        {formatDeadlineBadge(item)}
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <Empty icon="Tasks" text="No due assignments, quizzes, or payment dates are coming up." />
              )}
            </StudentCalendarPanel>

            <StudentCalendarPanel
              title="Academic Milestones"
              actionLabel="View term calendar"
              onAction={() => go('academic_calendar')}
            >
              {data.upcoming_events?.length ? (
                <div className="student-calendar-side-list">
                  {data.upcoming_events.map((item: any) => (
                    <button className="student-calendar-side-row academic" key={item.id} onClick={() => go('academic_calendar')} type="button">
                      <span className="student-calendar-side-icon academic">
                        <StudentCalendarGlyph kind="academic" />
                      </span>
                      <div className="student-calendar-side-copy">
                        <div className="student-calendar-row-title">{item.title}</div>
                        <div className="student-calendar-row-sub">{formatAcademicRange(item.start_date, item.end_date)}</div>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <Empty icon="Calendar" text="No academic milestones are available right now." />
              )}
            </StudentCalendarPanel>
          </aside>
        </div>
      )}

      {showPersonalModal && (
        <Modal
          title={personalForm.id ? 'Edit My Event' : 'Add My Event'}
          onClose={closePersonalModal}
          footer={(
            <>
              {personalForm.id && (
                <button className="btn btn-rose" disabled={savingPersonal} onClick={deletePersonalEvent} type="button">Delete</button>
              )}
              <button className="btn btn-out" disabled={savingPersonal} onClick={closePersonalModal} type="button">Cancel</button>
              <button className="btn btn-brass" disabled={savingPersonal} onClick={savePersonalEvent} type="button">
                {savingPersonal ? 'Saving...' : 'Save Event'}
              </button>
            </>
          )}
        >
          <div className="form-row">
            <label>Event title</label>
            <input
              className="inp"
              value={personalForm.title}
              onChange={event => setPersonalForm({ ...personalForm, title: event.target.value })}
              placeholder="Add a reminder, plan, or personal note"
            />
          </div>

          <div className="grid-2">
            <div className="form-row">
              <label>From date</label>
              <input
                className="inp"
                type="date"
                value={personalForm.startDate}
                onChange={event => setPersonalForm({ ...personalForm, startDate: event.target.value })}
              />
            </div>

            <div className="form-row">
              <label>From time</label>
              <input
                className="inp"
                type="time"
                value={personalForm.startTime}
                onChange={event => setPersonalForm({ ...personalForm, startTime: event.target.value })}
              />
            </div>
          </div>

          <div className="grid-2">
            <div className="form-row">
              <label>To date</label>
              <input
                className="inp"
                type="date"
                value={personalForm.endDate}
                onChange={event => setPersonalForm({ ...personalForm, endDate: event.target.value })}
              />
            </div>

            <div className="form-row">
              <label>To time</label>
              <input
                className="inp"
                type="time"
                value={personalForm.endTime}
                onChange={event => setPersonalForm({ ...personalForm, endTime: event.target.value })}
              />
            </div>
          </div>

          <div className="form-row">
            <label>Notes</label>
            <textarea
              className="inp"
              rows={4}
              value={personalForm.note}
              onChange={event => setPersonalForm({ ...personalForm, note: event.target.value })}
              placeholder="Visible only on your own student calendar."
            />
          </div>

          <p className="student-calendar-modal-note">
            Personal events are stored only for this student calendar and do not change any academic, timetable,
            examination, finance, or library workflow.
          </p>
        </Modal>
      )}
    </div>
  )
}

export function StudentCoursesView() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'current' | 'catalog'>('current')
  const [semester, setSemester] = useState('all')
  const [catalogSemester, setCatalogSemester] = useState('')
  const [showEdit, setShowEdit] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editingCourse, setEditingCourse] = useState<any>(null)
  const [editForm, setEditForm] = useState({ faculty: '', schedule: '' })

  async function load() {
    setLoading(true)
    setError('')
    try {
      const next = await api.studentCourses()
      setData(next)
      const currentSemester = String(next?.filters?.current_semester || '')
      const nextCatalogSemesters = Array.from(
        new Set((next?.catalog || []).map((course: any) => Number(course.semester || 0)).filter(Boolean)),
      ).sort((left, right) => left - right)
      const hasCurrentSemesterCourses = Boolean(
        currentSemester && (next?.courses || []).some((course: any) => String(course.semester || '') === currentSemester),
      )
      const defaultCatalogSemester = nextCatalogSemesters.includes(Number(currentSemester || 0))
        ? currentSemester
        : (nextCatalogSemesters.length ? String(nextCatalogSemesters[0]) : '')
      setSemester(hasCurrentSemesterCourses ? currentSemester : 'all')
      setCatalogSemester(defaultCatalogSemester)
    } catch (err: any) {
      setError(err?.message || 'We could not load the student academics view right now.')
      setData({ student: {}, summary: {}, filters: { available_semesters: [] }, courses: [], catalog: [], pending_tasks: [], upcoming_assessments: [] })
      setSemester('all')
      setCatalogSemester('')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const semesterOptions = useMemo(
    () => [...new Set((data?.filters?.available_semesters || []).map((value: number) => Number(value)))].sort((left, right) => left - right),
    [data],
  )
  const catalogSemesters = useMemo(
    () => [...new Set((data?.catalog || []).map((course: any) => Number(course.semester || 0)).filter(Boolean))].sort((left, right) => left - right),
    [data],
  )
  const catalogYearGroups = useMemo(
    () => buildCatalogYearGroups(catalogSemesters),
    [catalogSemesters],
  )
  const activeCatalogYear = useMemo(() => {
    const selected = Number(catalogSemester || 0)
    if (selected > 0) return Math.ceil(selected / 2)
    return catalogYearGroups[0]?.year || null
  }, [catalogSemester, catalogYearGroups])
  const activeCatalogGroup = useMemo(
    () => catalogYearGroups.find(group => group.year === activeCatalogYear) || null,
    [catalogYearGroups, activeCatalogYear],
  )
  const filteredCourses = useMemo(
    () => (data?.courses || []).filter((course: any) => matchesStudentSemester(course.semester, semester)),
    [data, semester],
  )
  const filteredCatalog = useMemo(
    () => [...(data?.catalog || [])]
      .filter((course: any) => !catalogSemester || matchesStudentSemester(course.semester, catalogSemester))
      .sort((left: any, right: any) => {
        const semesterGap = Number(left?.semester || 0) - Number(right?.semester || 0)
        if (semesterGap) return semesterGap
        return String(left?.code || '').localeCompare(String(right?.code || ''))
      }),
    [data, catalogSemester],
  )
  const filteredTasks = useMemo(
    () => (data?.pending_tasks || []).filter((item: any) => matchesStudentSemester(item.semester, semester)),
    [data, semester],
  )
  const filteredAssessments = useMemo(
    () => (data?.upcoming_assessments || []).filter((item: any) => matchesStudentSemester(item.semester, semester)),
    [data, semester],
  )

  useEffect(() => {
    if (!catalogSemesters.length) {
      if (catalogSemester) setCatalogSemester('')
      return
    }
    if (!catalogSemesters.includes(Number(catalogSemester || 0))) {
      setCatalogSemester(String(catalogSemesters[0]))
    }
  }, [catalogSemesters, catalogSemester])

  const credits = filteredCourses.reduce((sum: number, course: any) => sum + Number(course.credits || 0), 0)
  const attendanceRows = filteredCourses.filter((course: any) => course.attendance_pct != null)
  const overallAttendance = attendanceRows.length
    ? Math.round(attendanceRows.reduce((sum: number, course: any) => sum + Number(course.attendance_pct || 0), 0) / attendanceRows.length)
    : data?.summary?.attendance_pct ?? null
  const attendanceLabel = overallAttendance != null
    ? (overallAttendance >= 85 ? 'Excellent attendance' : overallAttendance >= 75 ? 'Good standing' : 'Needs attention')
    : 'Attendance pending'
  const semesterLabel = semester === 'all' ? 'Current Load' : `Semester ${semester}`
  const student = data?.student || {}
  const selectedCatalogSemesterNumber = Number(catalogSemester || 0)
  const isOddCatalogSemester = selectedCatalogSemesterNumber > 0 && selectedCatalogSemesterNumber % 2 === 1
  const isEvenCatalogSemester = selectedCatalogSemesterNumber > 0 && selectedCatalogSemesterNumber % 2 === 0

  function openEdit(course: any) {
    setEditingCourse(course)
    setEditForm({ faculty: course.faculty || '', schedule: course.schedule || '' })
    setShowEdit(true)
  }

  function selectCatalogYear(year: number) {
    const target = catalogYearGroups.find(group => group.year === year)
    if (!target) return
    const prefersEven = Number(catalogSemester || 0) > 0 && Number(catalogSemester) % 2 === 0
    const nextSemester = prefersEven
      ? target.evenSemester ?? target.oddSemester
      : target.oddSemester ?? target.evenSemester
    setCatalogSemester(nextSemester ? String(nextSemester) : '')
  }

  async function saveEdit() {
    if (!editingCourse) return
    try {
      setSaving(true)
      setError('')
      await api.updateStudentCourseView(editingCourse.section_id, editForm)
      setShowEdit(false)
      setEditingCourse(null)
      await load()
    } catch (err: any) {
      setError(err?.message || 'We could not save the course view update.')
    } finally {
      setSaving(false)
    }
  }

  async function resetEdit() {
    if (!editingCourse) return
    try {
      setSaving(true)
      setError('')
      await api.updateStudentCourseView(editingCourse.section_id, { faculty: '', schedule: '' })
      setShowEdit(false)
      setEditingCourse(null)
      await load()
    } catch (err: any) {
      setError(err?.message || 'We could not reset the course view.')
    } finally {
      setSaving(false)
    }
  }

  if (loading && !data) return <Spinner />

  return (
    <div className="student-academics-page fade-in">
      <PageHead
        title="Academics Overview"
        sub="Track your courses, performance, attendance, and academic activities in one place."
        right={(
          <div className="student-academics-head-actions">
            {tab === 'current' && (
              <label className="student-academics-select">
                <span>View</span>
                <select value={semester} onChange={event => setSemester(event.target.value)}>
                  <option value="all">Current Load</option>
                  {semesterOptions.map((value: number) => (
                    <option key={value} value={String(value)}>{`Semester ${value}`}</option>
                  ))}
                </select>
              </label>
            )}
            <button className="student-academics-refresh" onClick={load} type="button">Refresh</button>
          </div>
        )}
      />

      <div className="student-academics-context">
        <span className="mono">{student.roll_no || '--'}</span>
        <span>{student.program || student.department || 'Student academics'}</span>
        <span>{student.semester ? `Semester ${student.semester}` : 'Semester -'}</span>
        <span>{student.section ? `Section ${student.section}` : 'Section -'}</span>
        <span>{student.batch ? `Batch ${student.batch}` : 'Batch -'}</span>
      </div>

      {error && <div className="student-academics-banner">{error}</div>}

      <div className="student-academics-kpis">
        <StudentAcademicMetric
          kind="courses"
          label="Enrolled Courses"
          value={String(filteredCourses.length)}
          sub={`${credits} Credits`}
          tone="green"
        />
        <StudentAcademicMetric
          kind="results"
          label="CGPA"
          value={data?.summary?.cgpa != null ? `${Number(data.summary.cgpa).toFixed(2)} / 10` : '-'}
          sub={data?.summary?.cgpa_label || 'Current standing'}
          tone="violet"
        />
        <StudentAcademicMetric
          kind="attendance"
          label="Overall Attendance"
          value={overallAttendance != null ? `${overallAttendance}%` : '-'}
          sub={attendanceLabel}
          tone="blue"
        />
        <StudentAcademicMetric
          kind="assessment"
          label="Assessments"
          value={String(filteredAssessments.length)}
          sub={filteredAssessments.length ? 'Upcoming' : 'No upcoming items'}
          tone="amber"
        />
        <StudentAcademicMetric
          kind="tasks"
          label="Pending Tasks"
          value={String(filteredTasks.length)}
          sub={filteredTasks.length ? 'Due soon' : 'Nothing pending'}
          tone="slate"
        />
      </div>

      <section className="student-academics-board">
        <div className="student-academics-tabs">
          <button className={`student-academics-tab ${tab === 'current' ? 'active' : ''}`} onClick={() => setTab('current')} type="button">
            {semesterLabel} Courses
          </button>
          <button className={`student-academics-tab ${tab === 'catalog' ? 'active' : ''}`} onClick={() => setTab('catalog')} type="button">
            Course Catalogue
          </button>
        </div>

        {tab === 'current' ? (
          <>
            <div className="student-academics-board-head">
              <div>
                <h3>{semesterLabel} Courses</h3>
                <p>
                  Courses shown here are pulled from your student-specific department and section load.
                  Edits on this page are saved only for your own academics view.
                </p>
              </div>
              <span className="student-academics-board-pill">{filteredCourses.length} courses</span>
            </div>

            <div className="tbl-scroll student-academics-table-wrap">
              <table className="tbl student-academics-table">
                <thead>
                  <tr>
                    <th>Course Code</th>
                    <th>Course Name</th>
                    <th>Credits</th>
                    <th>Professor Name</th>
                    <th>Schedule</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCourses.map((course: any) => (
                    <tr key={course.section_id}>
                      <td className="mono"><b>{course.course_code}</b></td>
                      <td>
                        <div className="student-academics-course-title">{course.title}</div>
                        <div className="student-academics-course-sub">{joinParts([
                          course.semester ? `Semester ${course.semester}` : '',
                          course.section ? `Section ${course.section}` : '',
                          course.room,
                        ])}</div>
                      </td>
                      <td>{course.credits}</td>
                      <td>
                        <button className="student-academics-edit-pill" onClick={() => openEdit(course)} type="button">
                          <span>{course.faculty || '-'}</span>
                          <StudentAcademicGlyph kind="edit" />
                        </button>
                      </td>
                      <td>
                        <button className="student-academics-edit-pill" onClick={() => openEdit(course)} type="button">
                          <span>{course.schedule || '-'}</span>
                          <StudentAcademicGlyph kind="edit" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!filteredCourses.length && (
                    <tr>
                      <td colSpan={5}><div className="empty">No courses match this student view yet</div></td>
                    </tr>
                  )}
                </tbody>
                {filteredCourses.length > 0 && (
                  <tfoot>
                    <tr>
                      <td colSpan={2}><b>Total Credits</b></td>
                      <td><b>{credits}</b></td>
                      <td colSpan={2} />
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </>
        ) : (
          <>
            <div className="student-academics-board-head">
              <div>
                <h3>Course Catalogue</h3>
                <p>
                  Catalogue entries combine your department offerings and your published result history so every scored semester stays connected here.
                </p>
              </div>
              <span className="student-academics-board-pill">{filteredCatalog.length} entries</span>
            </div>

            {catalogYearGroups.length > 0 && (
              <div className="student-academics-catalog-filter">
                <div className="student-academics-catalog-filter-head">
                  <div className="student-academics-catalog-filter-copy">
                    <span>Browse by year</span>
                    <p>Select an academic year first, then choose its odd or even semester.</p>
                  </div>

                  {activeCatalogGroup && (
                    <div className="student-academics-catalog-filter-active">
                      <strong>{`Year ${activeCatalogGroup.year}`}</strong>
                      <small>
                        {catalogSemester
                          ? `${isEvenCatalogSemester ? 'Even Semester' : 'Odd Semester'} / Semester ${catalogSemester}`
                          : 'Choose a semester'}
                      </small>
                    </div>
                  )}
                </div>

                <div className="student-academics-catalog-years">
                  {catalogYearGroups.map(group => (
                    <button
                      key={group.year}
                      className={`student-academics-catalog-year ${activeCatalogYear === group.year ? 'active' : ''}`}
                      aria-pressed={activeCatalogYear === group.year}
                      onClick={() => selectCatalogYear(group.year)}
                      type="button"
                    >
                      <strong>{`Year ${group.year}`}</strong>
                      <small>{joinParts([
                        group.oddSemester ? `Sem ${group.oddSemester}` : '',
                        group.evenSemester ? `Sem ${group.evenSemester}` : '',
                      ]) || 'No semesters'}</small>
                    </button>
                  ))}
                </div>

                {activeCatalogGroup && (
                  <div className="student-academics-catalog-terms">
                    <span className="student-academics-catalog-terms-label">{`Year ${activeCatalogGroup.year} semesters`}</span>

                    <div className="student-academics-catalog-term-grid">
                      <button
                        className={`student-academics-catalog-term ${isOddCatalogSemester ? 'active' : ''}`}
                        aria-pressed={isOddCatalogSemester}
                        disabled={!activeCatalogGroup.oddSemester}
                        onClick={() => activeCatalogGroup.oddSemester && setCatalogSemester(String(activeCatalogGroup.oddSemester))}
                        type="button"
                      >
                        <strong>Odd Semester</strong>
                        <small>{activeCatalogGroup.oddSemester ? `Semester ${activeCatalogGroup.oddSemester}` : 'Not available'}</small>
                      </button>

                      <button
                        className={`student-academics-catalog-term ${isEvenCatalogSemester ? 'active' : ''}`}
                        aria-pressed={isEvenCatalogSemester}
                        disabled={!activeCatalogGroup.evenSemester}
                        onClick={() => activeCatalogGroup.evenSemester && setCatalogSemester(String(activeCatalogGroup.evenSemester))}
                        type="button"
                      >
                        <strong>Even Semester</strong>
                        <small>{activeCatalogGroup.evenSemester ? `Semester ${activeCatalogGroup.evenSemester}` : 'Not available'}</small>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="tbl-scroll student-academics-table-wrap">
              <table className="tbl student-academics-table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Course</th>
                    <th>Semester</th>
                    <th>Credits</th>
                    <th>Current Section</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCatalog.map((course: any) => (
                    <tr key={course.course_id}>
                      <td className="mono"><b>{course.code}</b></td>
                      <td>
                        <div className="student-academics-course-title">{course.title}</div>
                        <div className="student-academics-course-sub">{course.source_label || 'Catalogue record'}</div>
                      </td>
                      <td>{course.semester ? `Semester ${course.semester}` : '-'}</td>
                      <td>{course.credits}</td>
                      <td>{course.current_sections?.length ? course.current_sections.map((section: string) => `Section ${section}`).join(', ') : '-'}</td>
                    </tr>
                  ))}
                  {!filteredCatalog.length && (
                    <tr>
                      <td colSpan={5}><div className="empty">No catalogue entries match this filter</div></td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <div className="student-academics-sync">
        <div>
          All data is synced with your student academics view. Last refreshed:
          {' '}
          <b>{formatDate(data?.refreshed_at, true)}</b>
        </div>
        <button className="student-academics-refresh ghost" onClick={load} type="button">Refresh</button>
      </div>

      {showEdit && editingCourse && (
        <Modal
          title={`Edit course view - ${editingCourse.course_code}`}
          onClose={() => {
            setShowEdit(false)
            setEditingCourse(null)
          }}
          footer={(
            <>
              {editingCourse.has_preference && (
                <button className="btn btn-out" disabled={saving} onClick={resetEdit} type="button">Reset</button>
              )}
              <button
                className="btn btn-out"
                disabled={saving}
                onClick={() => {
                  setShowEdit(false)
                  setEditingCourse(null)
                }}
                type="button"
              >
                Cancel
              </button>
              <button className="btn btn-brass" disabled={saving} onClick={saveEdit} type="button">
                {saving ? 'Saving...' : 'Save'}
              </button>
            </>
          )}
        >
          <div className="form-row">
            <label>Professor name</label>
            <input
              className="inp"
              value={editForm.faculty}
              onChange={event => setEditForm({ ...editForm, faculty: event.target.value })}
              placeholder={editingCourse.base_faculty || 'Professor name'}
            />
          </div>
          <div className="form-row">
            <label>Schedule</label>
            <input
              className="inp"
              value={editForm.schedule}
              onChange={event => setEditForm({ ...editForm, schedule: event.target.value })}
              placeholder={editingCourse.base_schedule || 'Mon 09:00 - 10:00'}
            />
          </div>
          <p className="student-academics-edit-note">
            These edits are saved to the database only for this student academics page and do not
            alter the academic office, faculty timetable, or any other workflow.
          </p>
        </Modal>
      )}
    </div>
  )
}

function StudentAcademicMetric({
  kind,
  label,
  value,
  sub,
  tone,
}: {
  kind: string
  label: string
  value: string
  sub: string
  tone: string
}) {
  return (
    <article className="student-academics-metric">
      <span className={`student-academics-metric-icon ${tone}`}>
        <StudentAcademicGlyph kind={kind} />
      </span>
      <div className="student-academics-metric-copy">
        <div className="student-academics-metric-label">{label}</div>
        <div className="student-academics-metric-value">{value}</div>
        <div className="student-academics-metric-sub">{sub}</div>
      </div>
    </article>
  )
}

function StudentAcademicGlyph({ kind }: { kind: string }) {
  switch (kind) {
    case 'courses':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 0 4 23V5.5Z" /><path d="M12 3v18" /></svg>
    case 'results':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 4h10l3 3v13H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" /><path d="M15 4v3h3M9 13h6M9 17h4" /></svg>
    case 'attendance':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m5 12 4 4 10-10" /></svg>
    case 'assessment':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 4h10l3 3v13H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" /><path d="M15 4v3h3M9 13h6M9 17h4" /></svg>
    case 'tasks':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="6" y="4" width="12" height="16" rx="2" /><path d="M9 4.5h6M9 9h6M9 13h6M9 17h4" /></svg>
    case 'edit':
      return <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="m13.5 3.5 3 3L7 16H4v-3l9.5-9.5Z" /><path d="M11.5 5.5l3 3" /></svg>
    default:
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8" /></svg>
  }
}

function matchesStudentSemester(value: number | string | null | undefined, filter: string) {
  return filter === 'all' || String(value || '') === filter
}

function buildCatalogYearGroups(semesters: number[]) {
  const groups = new Map<number, { year: number; oddSemester: number | null; evenSemester: number | null }>()

  semesters.forEach(semester => {
    const year = Math.ceil(semester / 2)
    const current = groups.get(year) || { year, oddSemester: null, evenSemester: null }
    if (semester % 2 === 0) current.evenSemester = semester
    else current.oddSemester = semester
    groups.set(year, current)
  })

  return Array.from(groups.values()).sort((left, right) => left.year - right.year)
}

function formatDate(value?: string, withTime = false) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('en-IN', withTime
    ? { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { day: '2-digit', month: 'short', year: 'numeric' },
  ).format(parsed)
}

function urgencyTone(value: string) {
  const key = String(value || '').toLowerCase()
  if (key.includes('overdue') || key.includes('today')) return 'danger'
  if (key.includes('tomorrow')) return 'warn'
  return 'ok'
}

function joinParts(parts: Array<string | undefined | null>) {
  return parts.map(part => String(part || '').trim()).filter(Boolean).join(' / ')
}

function timeRange(start?: string, end?: string) {
  if (!start) return '-'
  const first = new Date(start)
  if (Number.isNaN(first.getTime())) return start
  const startText = new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit' }).format(first)
  if (!end) return startText
  const second = new Date(end)
  if (Number.isNaN(second.getTime())) return startText
  return `${startText} - ${new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit' }).format(second)}`
}

function formatTimeLabel(value?: string) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit' }).format(parsed)
}

function formatWeekday(value?: string) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('en-IN', { weekday: 'long' }).format(parsed)
}

function formatDuration(start?: string, end?: string) {
  if (!start || !end) return '-'
  const first = new Date(start)
  const second = new Date(end)
  if (Number.isNaN(first.getTime()) || Number.isNaN(second.getTime())) return '-'
  const totalMinutes = Math.max(0, Math.round((second.getTime() - first.getTime()) / 60000))
  if (!totalMinutes) return '-'
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return joinParts([
    hours ? `${hours} hr${hours === 1 ? '' : 's'}` : '',
    minutes ? `${minutes} min` : '',
  ]) || '-'
}

function examSeatSummary(item: any) {
  if (!item?.seat_label) return 'Seat allocation will appear after office release.'
  return joinParts([`Seat ${item.seat_label}`, item?.seat_zone])
}

function scoreTermKey(academicYear?: string, semester?: number | string) {
  return `${academicYear || '--'}_${semester || '--'}`
}

export function StudentAttendanceView() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [semester, setSemester] = useState('all')
  const [course, setCourse] = useState('all')
  const [month, setMonth] = useState('')
  const [status, setStatus] = useState('all')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const next = await api.studentAttendance()
      setData(next)
      const nextSemester = String(next?.filters?.current_semester || next?.filters?.available_semesters?.[0] || 'all')
      const nextMonth = String(next?.filters?.available_months?.[0] || '')
      setSemester(nextSemester || 'all')
      setCourse('all')
      setMonth(nextMonth)
      setStatus('all')
    } catch (err: any) {
      setError(err?.message || 'We could not load the attendance dashboard right now.')
      setData({
        student: {},
        policy: { minimum_attendance_pct: 75, low_attendance_pct: 80 },
        filters: { current_semester: '', available_semesters: [], available_months: [] },
        courses: [],
        records: [],
        today: { date: '', label: '', items: [] },
        refreshed_at: '',
        last_synced_at: '',
      })
      setSemester('all')
      setCourse('all')
      setMonth('')
      setStatus('all')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const minimumAttendance = Number(data?.policy?.minimum_attendance_pct || 75)
  const lowAttendanceCutoff = Number(data?.policy?.low_attendance_pct || 80)
  const student = data?.student || {}
  const semesterOptions = useMemo(
    () => [...new Set((data?.filters?.available_semesters || []).map((value: number) => Number(value)).filter(Boolean))].sort((left, right) => right - left),
    [data],
  )
  const semesterScopedCourses = useMemo(
    () => (data?.courses || []).filter((item: any) => matchesStudentSemester(item.semester, semester)),
    [data, semester],
  )
  const courseOptions = useMemo(
    () => [...semesterScopedCourses].sort((left: any, right: any) => String(left.course_code || '').localeCompare(String(right.course_code || ''))),
    [semesterScopedCourses],
  )
  const filteredCourses = useMemo(
    () => semesterScopedCourses.filter((item: any) => {
      if (course !== 'all' && item.section_id !== course) return false
      if (status !== 'all' && String(item?.status?.key || '') !== status) return false
      return true
    }),
    [semesterScopedCourses, course, status],
  )
  const visibleSectionIds = useMemo(
    () => new Set(filteredCourses.map((item: any) => item.section_id)),
    [filteredCourses],
  )
  const activeMonth = month || String(data?.filters?.available_months?.[0] || '')
  const filteredRecords = useMemo(
    () => (data?.records || []).filter((row: any) => {
      if (!visibleSectionIds.has(row.section_id)) return false
      if (activeMonth && !String(row.on_date || '').startsWith(activeMonth)) return false
      return true
    }),
    [data, visibleSectionIds, activeMonth],
  )
  const todayItems = useMemo(
    () => (data?.today?.items || []).filter((item: any) => visibleSectionIds.has(item.section_id)),
    [data, visibleSectionIds],
  )
  const recentUpdates = useMemo(
    () => [...filteredRecords]
      .sort((left: any, right: any) => String(right.updated_at || '').localeCompare(String(left.updated_at || '')))
      .slice(0, 5),
    [filteredRecords],
  )
  const totalAttended = filteredCourses.reduce((sum: number, item: any) => sum + Number(item.attended || 0), 0)
  const totalSessions = filteredCourses.reduce((sum: number, item: any) => sum + Number(item.total || 0), 0)
  const overallAttendance = totalSessions ? Math.round((100 * totalAttended) / totalSessions) : null
  const presentThisMonth = filteredRecords.filter((row: any) => row.present).length
  const absenceCount = filteredRecords.filter((row: any) => String(row?.status?.key || '') === 'absent').length
  const leaveOrOdCount = filteredRecords.filter((row: any) => ['leave', 'od'].includes(String(row?.status?.key || ''))).length
  const lowAttendanceCourses = filteredCourses.filter(
    (item: any) => item.attendance_pct != null && Number(item.attendance_pct) < lowAttendanceCutoff,
  )
  const weeklyTrend = useMemo(
    () => buildStudentAttendanceTrend(filteredRecords, activeMonth),
    [filteredRecords, activeMonth],
  )
  const currentMonthLabel = formatAttendanceMonth(activeMonth)
  const overallAttendanceLabel = attendanceStandingLabel(overallAttendance, minimumAttendance)

  if (loading && !data) return <Spinner />

  return (
    <div className="student-attendance-page fade-in">
      <PageHead
        title="Attendance"
        sub="Daily attendance updated from department office and marked sessions for your enrolled courses only."
      />

      <div className="student-attendance-context">
        <span className="mono">{student.roll_no || '--'}</span>
        <span>{student.name || 'Logged-in student'}</span>
        <span>{student.program || student.department || 'Student Portal'}</span>
        <span>{student.semester ? `Semester ${student.semester}` : 'Semester -'}</span>
        <span>{student.section ? `Section ${student.section}` : 'Section -'}</span>
      </div>

      {error && <div className="student-attendance-banner">{error}</div>}

      <section className="student-attendance-toolbar">
        <div className="student-attendance-filters">
          <label className="student-attendance-filter">
            <span>Semester</span>
            <select value={semester} onChange={event => setSemester(event.target.value)}>
              <option value="all">All Semesters</option>
              {semesterOptions.map((value: number) => (
                <option key={value} value={String(value)}>{`Semester ${value}`}</option>
              ))}
            </select>
          </label>

          <label className="student-attendance-filter">
            <span>Course</span>
            <select value={course} onChange={event => setCourse(event.target.value)}>
              <option value="all">All Courses</option>
              {courseOptions.map((item: any) => (
                <option key={item.section_id} value={item.section_id}>{`${item.course_code} ${item.course_title}`}</option>
              ))}
            </select>
          </label>

          <label className="student-attendance-filter">
            <span>Month</span>
            <select value={month} onChange={event => setMonth(event.target.value)}>
              {(data?.filters?.available_months || []).map((value: string) => (
                <option key={value} value={value}>{formatAttendanceMonth(value)}</option>
              ))}
            </select>
          </label>

          <label className="student-attendance-filter">
            <span>Status</span>
            <select value={status} onChange={event => setStatus(event.target.value)}>
              <option value="all">All</option>
              <option value="good">Good</option>
              <option value="warning">Warning</option>
              <option value="critical">Critical</option>
              <option value="pending">Pending</option>
            </select>
          </label>
        </div>

        <div className="student-attendance-toolbar-side">
          <div className="student-attendance-sync-label">
            <span className="student-attendance-sync-dot" />
            <span>
              Last synced
              {' '}
              <b>{formatDate(data?.last_synced_at, true)}</b>
            </span>
          </div>
          <button className="student-attendance-refresh" disabled={loading} onClick={load} type="button">
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </section>

      <div className="student-attendance-kpis">
        <StudentAttendanceMetric
          kind="overall"
          tone="green"
          label="Overall Attendance"
          value={overallAttendance != null ? `${overallAttendance}%` : '-'}
          sub={overallAttendanceLabel}
        />
        <StudentAttendanceMetric
          kind="month"
          tone="blue"
          label="Present This Month"
          value={`${presentThisMonth} day${presentThisMonth === 1 ? '' : 's'}`}
          sub={filteredRecords.length ? `Out of ${filteredRecords.length} marked sessions` : `No marked sessions in ${currentMonthLabel}`}
        />
        <StudentAttendanceMetric
          kind="absence"
          tone="amber"
          label="Absent / Leave"
          value={`${absenceCount} absence${absenceCount === 1 ? '' : 's'}`}
          sub={leaveOrOdCount ? `${leaveOrOdCount} OD or leave update${leaveOrOdCount === 1 ? '' : 's'}` : 'No leave or OD updates'}
        />
        <StudentAttendanceMetric
          kind="risk"
          tone="violet"
          label="Low Attendance Courses"
          value={`${lowAttendanceCourses.length} subject${lowAttendanceCourses.length === 1 ? '' : 's'}`}
          sub={lowAttendanceCourses.length ? `At risk below ${lowAttendanceCutoff}%` : `All courses at or above ${lowAttendanceCutoff}%`}
        />
      </div>

      <div className="student-attendance-shell">
        <div className="student-attendance-main">
          <section className="student-attendance-card student-attendance-summary-card">
            <div className="student-attendance-card-head">
              <div>
                <h3>Attendance Summary</h3>
                <p>Attendance is updated after daily department verification and scoped only to your active enrollments.</p>
              </div>
              <span className="student-attendance-card-meta">{`${filteredCourses.length} course${filteredCourses.length === 1 ? '' : 's'}`}</span>
            </div>

            <div className="tbl-scroll student-attendance-table-wrap">
              <table className="tbl student-attendance-table">
                <thead>
                  <tr>
                    <th>Course Code</th>
                    <th>Course Name</th>
                    <th>Faculty</th>
                    <th>Attended / Total</th>
                    <th>Percentage</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCourses.map((item: any) => (
                    <tr key={item.section_id}>
                      <td className="mono"><b>{item.course_code}</b></td>
                      <td>
                        <div className="student-attendance-course-title">{item.course_title}</div>
                        <div className="student-attendance-course-sub">{joinParts([
                          item.semester ? `Semester ${item.semester}` : '',
                          item.section ? `Section ${item.section}` : '',
                          item.room,
                          item.schedule,
                        ])}</div>
                      </td>
                      <td>{item.faculty || '-'}</td>
                      <td><b>{`${item.attended || 0} / ${item.total || 0}`}</b></td>
                      <td>
                        <div className="student-attendance-progress-cell">
                          <div className="student-attendance-progress-track">
                            <div
                              className={`student-attendance-progress-fill ${item?.status?.tone || 'pending'}`}
                              style={{ width: `${Math.max(0, Math.min(100, Number(item.attendance_pct || 0)))}%` }}
                            />
                          </div>
                          <span>{item.attendance_pct != null ? `${item.attendance_pct}%` : '-'}</span>
                        </div>
                      </td>
                      <td>
                        <span className={`student-attendance-pill ${item?.status?.tone || 'pending'}`}>{item?.status?.label || 'Pending'}</span>
                      </td>
                    </tr>
                  ))}
                  {!filteredCourses.length && (
                    <tr>
                      <td colSpan={6}><div className="empty">No attendance courses match this filter</div></td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="student-attendance-card student-attendance-trend-card">
            <div className="student-attendance-card-head">
              <div>
                <h3>Monthly Attendance Trend</h3>
                <p>{`Weekly attendance trend for ${currentMonthLabel}. Minimum requirement line stays at ${minimumAttendance}%.`}</p>
              </div>
              <span className="student-attendance-card-meta">Weekly view</span>
            </div>

            <StudentAttendanceTrend weeks={weeklyTrend} minimumAttendance={minimumAttendance} />
          </section>
        </div>

        <div className="student-attendance-side">
          <section className="student-attendance-card">
            <div className="student-attendance-card-head">
              <div>
                <h3>Today's Marking Status</h3>
                <p>{data?.today?.label || 'Today'}</p>
              </div>
            </div>

            <div className="student-attendance-side-list">
              {todayItems.length ? todayItems.map((item: any) => (
                <div className="student-attendance-today-row" key={item.timetable_entry_id}>
                  <div className="student-attendance-time">
                    <strong>{formatAttendanceTime(item.start_time)}</strong>
                    <span>{item.course_code}</span>
                  </div>
                  <div className="student-attendance-side-copy">
                    <div className="student-attendance-row-title">{item.course_title}</div>
                    <div className="student-attendance-row-sub">{joinParts([item.faculty, item.room, item.note || item.source_label])}</div>
                  </div>
                  <span className={`student-attendance-pill ${item?.status?.tone || 'pending'}`}>{item?.status?.label || 'Pending'}</span>
                </div>
              )) : <Empty text="No active classes scheduled for this filter today" />}
            </div>
          </section>

          <section className="student-attendance-card">
            <div className="student-attendance-card-head">
              <div>
                <h3>Recent Attendance Updates</h3>
                <p>{`${currentMonthLabel} office-updated sessions`}</p>
              </div>
            </div>

            <div className="student-attendance-side-list">
              {recentUpdates.length ? recentUpdates.map((item: any) => (
                <div className="student-attendance-update-row" key={item.id}>
                  <div className="student-attendance-update-date">{formatDate(item.on_date)}</div>
                  <div className="student-attendance-side-copy">
                    <div className="student-attendance-row-title">{`${item.course_code} ${item.course_title}`}</div>
                    <div className="student-attendance-row-sub">{joinParts([item.source_label, item.note])}</div>
                  </div>
                  <span className={`student-attendance-pill ${item?.status?.tone || 'pending'}`}>{item?.status?.label || 'Pending'}</span>
                </div>
              )) : <Empty text="No recent attendance updates for this filter" />}
            </div>
          </section>

          <section className="student-attendance-card">
            <div className="student-attendance-card-head">
              <div>
                <h3>Attendance Alerts</h3>
                <p>{`Courses below ${lowAttendanceCutoff}% stay highlighted until the office-updated record improves.`}</p>
              </div>
            </div>

            <div className="student-attendance-alert-list">
              {lowAttendanceCourses.length ? lowAttendanceCourses.map((item: any) => {
                const sessionsNeeded = sessionsNeededForAttendanceTarget(
                  Number(item.attended || 0),
                  Number(item.total || 0),
                  lowAttendanceCutoff,
                )
                return (
                  <article className="student-attendance-alert" key={item.section_id}>
                    <div className="student-attendance-alert-title">{`${item.course_title} below ${lowAttendanceCutoff}%`}</div>
                    <div className="student-attendance-alert-copy">
                      {`Attendance is ${item.attendance_pct}%. Attend the next ${sessionsNeeded} session${sessionsNeeded === 1 ? '' : 's'} to move back toward ${lowAttendanceCutoff}%.`}
                    </div>
                  </article>
                )
              }) : (
                <article className="student-attendance-alert ok">
                  <div className="student-attendance-alert-title">No active attendance alerts</div>
                  <div className="student-attendance-alert-copy">{`All displayed courses are at or above ${lowAttendanceCutoff}%.`}</div>
                </article>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function StudentAttendanceMetric({
  kind,
  tone,
  label,
  value,
  sub,
}: {
  kind: string
  tone: string
  label: string
  value: string
  sub: string
}) {
  return (
    <article className="student-attendance-metric">
      <span className={`student-attendance-metric-icon ${tone}`}>
        <StudentAttendanceGlyph kind={kind} />
      </span>
      <div className="student-attendance-metric-copy">
        <div className="student-attendance-metric-label">{label}</div>
        <div className="student-attendance-metric-value">{value}</div>
        <div className="student-attendance-metric-sub">{sub}</div>
      </div>
    </article>
  )
}

function StudentAttendanceTrend({ weeks, minimumAttendance }: { weeks: any[]; minimumAttendance: number }) {
  if (!weeks.length) return <Empty text="No verified attendance trend is available yet" />

  const width = 640
  const height = 220
  const paddingLeft = 44
  const paddingRight = 18
  const paddingTop = 20
  const paddingBottom = 44
  const chartWidth = width - paddingLeft - paddingRight
  const chartHeight = height - paddingTop - paddingBottom
  const step = weeks.length > 1 ? chartWidth / (weeks.length - 1) : 0
  const points = weeks.map((week, index) => {
    const value = week.pct == null ? minimumAttendance : Number(week.pct)
    const x = paddingLeft + (step * index)
    const y = paddingTop + ((100 - value) / 100) * chartHeight
    return { ...week, value, x, y }
  })
  const polyline = points.map(point => `${point.x},${point.y}`).join(' ')
  const areaPath = points.length
    ? `M ${points[0].x} ${paddingTop + chartHeight} L ${points.map(point => `${point.x} ${point.y}`).join(' L ')} L ${points[points.length - 1].x} ${paddingTop + chartHeight} Z`
    : ''
  const minimumY = paddingTop + ((100 - minimumAttendance) / 100) * chartHeight
  const tickValues = [0, 25, 50, 75, 100]

  return (
    <div className="student-attendance-chart">
      <svg className="student-attendance-chart-svg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        {tickValues.map(value => {
          const y = paddingTop + ((100 - value) / 100) * chartHeight
          return (
            <g key={value}>
              <line className="student-attendance-grid-line" x1={paddingLeft} x2={width - paddingRight} y1={y} y2={y} />
              <text className="student-attendance-grid-label" x={10} y={y + 4}>{value}</text>
            </g>
          )
        })}

        <line className="student-attendance-minimum-line" x1={paddingLeft} x2={width - paddingRight} y1={minimumY} y2={minimumY} />
        {areaPath && <path className="student-attendance-area-path" d={areaPath} />}
        {polyline && <polyline className="student-attendance-line-path" points={polyline} />}

        {points.map(point => (
          <g key={point.label}>
            <circle className="student-attendance-line-point" cx={point.x} cy={point.y} r={5} />
            <text className="student-attendance-point-label" x={point.x} y={point.y - 12} textAnchor="middle">
              {point.pct == null ? '-' : `${point.pct}%`}
            </text>
          </g>
        ))}
      </svg>

      <div className="student-attendance-chart-labels">
        {weeks.map((week: any) => (
          <div className="student-attendance-chart-label" key={week.label}>
            <strong>{week.label}</strong>
            <span>{week.range}</span>
          </div>
        ))}
      </div>

      <div className="student-attendance-chart-legend">
        <span><i className="line" /> Attendance Percentage</span>
        <span><i className="minimum" /> Minimum Requirement</span>
      </div>
    </div>
  )
}

function StudentAttendanceGlyph({ kind }: { kind: string }) {
  switch (kind) {
    case 'overall':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 17 9 12l3 3 8-9" /><path d="M4 5v12h16" /></svg>
    case 'month':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 3v4M16 3v4M3 10h18" /></svg>
    case 'absence':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="9" cy="8" r="3" /><circle cx="17" cy="10" r="3" /><path d="M4 20c0-3 2.2-5 5-5s5 2 5 5" /><path d="M14 20c0-2.2 1.7-4 4-4 1.1 0 2.1.4 2.9 1.1" /></svg>
    case 'risk':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m12 3 7 4v5c0 4.5-2.7 7.8-7 9-4.3-1.2-7-4.5-7-9V7l7-4Z" /><path d="M12 8v5" /><path d="M12 16h.01" /></svg>
    default:
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8" /></svg>
  }
}

function buildStudentAttendanceTrend(records: any[], month: string) {
  const match = /^(\d{4})-(\d{2})$/.exec(String(month || ''))
  if (!match) return []

  const year = Number(match[1])
  const monthIndex = Number(match[2]) - 1
  if (Number.isNaN(year) || Number.isNaN(monthIndex) || monthIndex < 0 || monthIndex > 11) return []

  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate()
  const monthShort = new Intl.DateTimeFormat('en-IN', { month: 'short' }).format(new Date(year, monthIndex, 1))
  const weeks = []

  for (let start = 1, weekNumber = 1; start <= daysInMonth; start += 7, weekNumber += 1) {
    const end = Math.min(start + 6, daysInMonth)
    const startKey = `${match[1]}-${match[2]}-${pad(start)}`
    const endKey = `${match[1]}-${match[2]}-${pad(end)}`
    const bucket = records.filter((row: any) => {
      const value = String(row?.on_date || '')
      return value >= startKey && value <= endKey
    })
    const total = bucket.length
    const present = bucket.filter((row: any) => row.present).length
    weeks.push({
      label: `Week ${weekNumber}`,
      range: `${start} - ${end} ${monthShort}`,
      pct: total ? Math.round((100 * present) / total) : null,
    })
  }

  return weeks
}

function sessionsNeededForAttendanceTarget(attended: number, total: number, targetPct: number) {
  if (!total || (100 * attended) / total >= targetPct) return 0
  let needed = 0
  while (needed < 100) {
    needed += 1
    if ((100 * (attended + needed)) / (total + needed) >= targetPct) return needed
  }
  return 100
}

function attendanceStandingLabel(value: number | null, minimumAttendance: number) {
  if (value == null) return 'Attendance appears after office verification'
  if (value >= 85) return `Good - Above minimum ${minimumAttendance}%`
  if (value >= minimumAttendance) return `On track - Above minimum ${minimumAttendance}%`
  return `Below minimum ${minimumAttendance}%`
}

function formatAttendanceMonth(value: string) {
  const match = /^(\d{4})-(\d{2})$/.exec(String(value || ''))
  if (!match) return 'All Months'
  const year = Number(match[1])
  const monthIndex = Number(match[2]) - 1
  return new Intl.DateTimeFormat('en-IN', { month: 'long', year: 'numeric' }).format(new Date(year, monthIndex, 1))
}

function formatAttendanceTime(value?: string) {
  if (!value) return '-'
  const [hourText, minuteText] = String(value).split(':')
  const hour = Number(hourText)
  const minute = Number(minuteText)
  if (Number.isNaN(hour) || Number.isNaN(minute)) return value
  return new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit' }).format(
    new Date(2026, 7, 25, hour, minute),
  )
}

const DEFAULT_STUDENT_EXAM_FILTERS = {
  academic_year: '',
  semester: '',
  course_id: '',
  assessment_type: '',
  status: 'all',
}

function formatAssessmentTypeLabel(value?: string) {
  return String(value || 'assessment')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, char => char.toUpperCase())
}

function formatMetricValue(value: any, digits = 2) {
  if (value == null || value === '') return '--'
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return String(value)
  return numeric.toFixed(digits)
}

function formatScoreValue(value: any) {
  if (value == null || value === '') return '--'
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return String(value)
  return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1)
}

function shortMonth(value?: string) {
  if (!value) return '---'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value).slice(0, 3).toUpperCase()
  return new Intl.DateTimeFormat('en-IN', { month: 'short' }).format(parsed).toUpperCase()
}

function shortDay(value?: string) {
  if (!value) return '--'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '--'
  return new Intl.DateTimeFormat('en-IN', { day: '2-digit' }).format(parsed)
}

function formatSemesterLabel(academicYear?: string, semester?: number | string) {
  if (!academicYear && !semester) return 'Semester'
  return joinParts([academicYear || '', semester ? `Semester ${semester}` : ''])
}

function studentExamPillTone(status: any) {
  return String(status?.tone || 'muted').toLowerCase()
}

function studentScoreBacklogTone(value: string) {
  if (value === 'active') return 'danger'
  if (value === 'cleared') return 'success'
  return 'muted'
}

function normalizeStudentExamFilters(next: any) {
  return {
    academic_year: String(next?.academic_year || ''),
    semester: String(next?.semester || ''),
    course_id: String(next?.course_id || ''),
    assessment_type: String(next?.assessment_type || ''),
    status: String(next?.status || 'all'),
  }
}

function StudentExamMetric({
  label,
  value,
  sub,
  tone,
  kind,
}: {
  label: string
  value: string
  sub: string
  tone: string
  kind: string
}) {
  return (
    <article className="student-exams-metric">
      <span className={`student-exams-metric-icon ${tone}`}>
        <StudentExamGlyph kind={kind} />
      </span>
      <div className="student-exams-metric-copy">
        <div className="student-exams-metric-label">{label}</div>
        <div className="student-exams-metric-value">{value}</div>
        <div className="student-exams-metric-sub">{sub}</div>
      </div>
    </article>
  )
}

function StudentExamGlyph({ kind }: { kind: string }) {
  switch (kind) {
    case 'upcoming':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 3v4M16 3v4M3 10h18" /></svg>
    case 'completed':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m5 12 4 4 10-10" /></svg>
    case 'average':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 19h16" /><path d="M7 15V9M12 15V5M17 15v-3" /></svg>
    case 'cgpa':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3 5 6v6c0 4.3 2.7 7.6 7 9 4.3-1.4 7-4.7 7-9V6l-7-3Z" /><path d="M9.5 12.5 11.2 14 14.8 10" /></svg>
    default:
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8" /></svg>
  }
}

export function StudentExaminationsView({ go }: { go?: (v: string) => void } = {}) {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState(DEFAULT_STUDENT_EXAM_FILTERS)
  const [selectedAssessment, setSelectedAssessment] = useState<any>(null)
  const [selectedUpdate, setSelectedUpdate] = useState<any>(null)

  async function load(nextFilters = filters) {
    setLoading(true)
    setError('')
    try {
      const next = await api.studentExaminations(nextFilters)
      setData(next)
      setFilters(normalizeStudentExamFilters(next.filters?.applied || nextFilters))
    } catch (err: any) {
      setError(err?.message || 'We could not load your examinations right now.')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(DEFAULT_STUDENT_EXAM_FILTERS)
  }, [])

  if (loading && !data) return <Spinner />

  const summary = data?.summary || {}
  const upcoming = data?.upcoming_assessments || []
  const updates = data?.recent_updates || []
  const filterMeta = data?.filters || {}

  return (
    <div className="student-exams-page fade-in">
      <PageHead
        title="Examinations"
        sub="Your upcoming assessments and published scores for enrolled sections only."
      />

      {error && <div className="student-attendance-banner">{error}</div>}

      <section className="student-exams-toolbar">
        <div className="student-exams-filters">
          <label className="student-exams-filter">
            <span>Academic Year</span>
            <select value={filters.academic_year} onChange={event => setFilters(current => ({ ...current, academic_year: event.target.value }))}>
              <option value="">All Academic Years</option>
              {(filterMeta.academic_years || []).map((item: string) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="student-exams-filter">
            <span>Semester</span>
            <select value={filters.semester} onChange={event => setFilters(current => ({ ...current, semester: event.target.value }))}>
              <option value="">All Semesters</option>
              {(filterMeta.semesters || []).map((item: number) => <option key={item} value={String(item)}>{`Semester ${item}`}</option>)}
            </select>
          </label>
          <label className="student-exams-filter">
            <span>Course</span>
            <select value={filters.course_id} onChange={event => setFilters(current => ({ ...current, course_id: event.target.value }))}>
              <option value="">All Courses</option>
              {(filterMeta.courses || []).map((item: any) => <option key={item.id} value={item.id}>{`${item.code} ${item.title}`}</option>)}
            </select>
          </label>
          <label className="student-exams-filter">
            <span>Assessment Type</span>
            <select value={filters.assessment_type} onChange={event => setFilters(current => ({ ...current, assessment_type: event.target.value }))}>
              <option value="">All Assessment Types</option>
              {(filterMeta.assessment_types || []).map((item: string) => <option key={item} value={item}>{formatAssessmentTypeLabel(item)}</option>)}
            </select>
          </label>
          <label className="student-exams-filter">
            <span>Status</span>
            <select value={filters.status} onChange={event => setFilters(current => ({ ...current, status: event.target.value }))}>
              {(filterMeta.statuses || ['all']).map((item: string) => <option key={item} value={item}>{formatAssessmentTypeLabel(item)}</option>)}
            </select>
          </label>
        </div>
        <div className="student-exams-toolbar-side">
          <div className="student-exams-sync-label">
            <span className="student-attendance-sync-dot" />
            Last synced <b>{formatDate(data?.refreshed_at, true)}</b>
          </div>
          <button className="student-exams-reset" disabled={loading} onClick={() => {
            const next = { ...DEFAULT_STUDENT_EXAM_FILTERS }
            setFilters(next)
            load(next)
          }} type="button">
            Reset
          </button>
          <button className="student-exams-apply" disabled={loading} onClick={() => load(filters)} type="button">
            {loading ? 'Applying...' : 'Apply Filters'}
          </button>
        </div>
      </section>

      <div className="student-exams-kpis">
        <StudentExamMetric label="Upcoming" value={String(summary.upcoming_count ?? 0)} sub="Published timetable items ahead" tone="blue" kind="upcoming" />
        <StudentExamMetric label="Completed" value={String(summary.completed_count ?? 0)} sub="Published scores already available" tone="green" kind="completed" />
        <StudentExamMetric label="Average Score" value={summary.average_score_pct != null ? `${formatMetricValue(summary.average_score_pct)}%` : '--'} sub={summary.average_score_label || 'Published marks only'} tone="amber" kind="average" />
        <StudentExamMetric label="CGPA / Backlogs" value={`${summary.cgpa != null ? formatMetricValue(summary.cgpa) : '--'} / ${summary.backlogs ?? 0}`} sub={summary.cgpa_label || 'Official result standing'} tone="violet" kind="cgpa" />
      </div>

      <div className="student-exams-shell">
        <section className="student-exams-card">
          <div className="student-exams-card-head">
            <div>
              <h3>Upcoming Assessments</h3>
              <p>Only published timetable entries from your enrolled courses are shown here.</p>
            </div>
            <span className="student-exams-card-meta">{`${upcoming.length} scheduled`}</span>
          </div>
          <div className="student-exams-upcoming-list">
            {upcoming.map((item: any) => (
              <button
                className="student-exams-upcoming-row student-exams-row-button"
                key={item.id}
                onClick={() => setSelectedAssessment(item)}
                type="button"
              >
                <div className="student-exams-date-tile">
                  <span>{shortMonth(item.scheduled_at)}</span>
                  <strong>{shortDay(item.scheduled_at)}</strong>
                </div>
                <div className="student-exams-upcoming-copy">
                  <div className="student-exams-row-title">{item.assessment_name}</div>
                  <div className="student-exams-row-sub">
                    {joinParts([
                      item.course_code,
                      formatAssessmentTypeLabel(item.assessment_type),
                      timeRange(item.scheduled_at, item.end_at),
                      item.venue,
                      item.seat_label ? `Seat ${item.seat_label}` : '',
                    ])}
                  </div>
                  <div className="student-exams-row-link">Open timetable details</div>
                </div>
                <span className={`student-exams-pill ${studentExamPillTone(item.status)}`}>{item.status?.label || 'Scheduled'}</span>
              </button>
            ))}
            {upcoming.length === 0 && <Empty text="No upcoming published assessments match the current filters." />}
          </div>
        </section>

        <section className="student-exams-card student-exams-standing-card">
          <div className="student-exams-card-head">
            <div>
              <h3>Current Standing</h3>
              <p>CGPA and backlog counts come from official published results only.</p>
            </div>
            {go && <button className="linkish" onClick={() => go('scores')} type="button">Open Scores</button>}
          </div>
          <div className="student-exams-standing-main">
            <div className="student-exams-standing-value">
              <strong>{summary.cgpa != null ? formatMetricValue(summary.cgpa) : '--'}</strong>
              <span>/ 10</span>
            </div>
            <div className="student-exams-standing-label">CGPA</div>
            <div className="student-exams-standing-pill">{summary.cgpa_label || 'Current standing'}</div>
          </div>
          <div className="student-exams-standing-grid">
            <div className="student-exams-standing-stat">
              <b>{summary.courses_enrolled ?? 0}</b>
              <span>Courses Enrolled</span>
            </div>
            <div className="student-exams-standing-stat">
              <b>{summary.completed_count ?? 0}</b>
              <span>Assessments Completed</span>
            </div>
            <div className="student-exams-standing-stat">
              <b>{summary.scores_published ?? 0}</b>
              <span>Scores Published</span>
            </div>
            <div className="student-exams-standing-stat">
              <b>{summary.backlogs ?? 0}</b>
              <span>Active Backlogs</span>
            </div>
          </div>
        </section>
      </div>

      <section className="student-exams-card">
        <div className="student-exams-card-head">
          <div>
            <h3>Recent Exam Updates</h3>
            <p>Changes are limited to your own enrolled courses and section timetable.</p>
          </div>
          <span className="student-exams-card-meta">{`${updates.length} updates`}</span>
        </div>
        <div className="student-exams-update-list">
          {updates.map((item: any) => (
            <button
              className="student-exams-update-row student-exams-row-button"
              key={item.id}
              onClick={() => setSelectedUpdate(item)}
              type="button"
            >
              <div className="student-exams-update-date">{formatDate(item.updated_at)}</div>
              <div className="student-exams-upcoming-copy">
                <div className="student-exams-row-title">{item.message}</div>
                <div className="student-exams-row-sub">{joinParts([item.course_code, item.course_title, item.assessment_name, item.seat_label ? `Seat ${item.seat_label}` : ''])}</div>
                <div className="student-exams-row-link">Open update details</div>
              </div>
              <span className={`student-exams-pill ${studentExamPillTone(item.status)}`}>{item.status?.label || 'Updated'}</span>
            </button>
          ))}
          {updates.length === 0 && <Empty text="No recent exam updates for your current enrolments." />}
        </div>
      </section>

      {selectedAssessment && (
        <Modal
          className="modal-wide student-exams-detail-modal"
          onClose={() => setSelectedAssessment(null)}
          title={`${selectedAssessment.course_code} Timetable`}
        >
          <div className="student-exams-popup">
            <div className="student-exams-popup-hero">
              <div>
                <div className="student-exams-popup-kicker">Student Assessment Timetable</div>
                <div className="student-exams-detail-title">{selectedAssessment.assessment_name}</div>
                <div className="student-exams-detail-sub">
                  {joinParts([
                    selectedAssessment.course_code,
                    selectedAssessment.course_title,
                    formatAssessmentTypeLabel(selectedAssessment.assessment_type),
                    selectedAssessment.section ? `Section ${selectedAssessment.section}` : '',
                  ])}
                </div>
              </div>
              <div className="student-exams-popup-chip-stack">
                <span className={`student-exams-pill ${studentExamPillTone(selectedAssessment.status)}`}>{selectedAssessment.status?.label || 'Scheduled'}</span>
                <span className="student-scores-term-chip subtle">{formatSemesterLabel(selectedAssessment.academic_year, selectedAssessment.semester)}</span>
              </div>
            </div>
            <div className="student-exams-popup-grid">
              <div className="student-exams-popup-tile">
                <span>Exam Date</span>
                <b>{formatDate(selectedAssessment.scheduled_at)}</b>
                <small>{formatWeekday(selectedAssessment.scheduled_at)}</small>
              </div>
              <div className="student-exams-popup-tile">
                <span>Time Slot</span>
                <b>{timeRange(selectedAssessment.scheduled_at, selectedAssessment.end_at)}</b>
                <small>{`${formatTimeLabel(selectedAssessment.scheduled_at)} reporting as per section notice`}</small>
              </div>
              <div className="student-exams-popup-tile">
                <span>Duration</span>
                <b>{formatDuration(selectedAssessment.scheduled_at, selectedAssessment.end_at)}</b>
                <small>{selectedAssessment.mode || 'Offline'}</small>
              </div>
              <div className="student-exams-popup-tile">
                <span>Venue</span>
                <b>{selectedAssessment.venue || '--'}</b>
                <small>{selectedAssessment.source_office || 'Examination workflow'}</small>
              </div>
              <div className="student-exams-popup-tile highlight">
                <span>Seat Allocation</span>
                <b>{selectedAssessment.seat_label ? `Seat ${selectedAssessment.seat_label}` : 'Awaiting allocation'}</b>
                <small>{selectedAssessment.seat_zone || 'Specific student seat will appear here after office release.'}</small>
              </div>
              <div className="student-exams-popup-tile">
                <span>Faculty In Charge</span>
                <b>{selectedAssessment.faculty || '--'}</b>
                <small>{selectedAssessment.source_label || selectedAssessment.source_office || '--'}</small>
              </div>
            </div>
            <div className="student-exams-popup-grid student-exams-popup-grid-compact">
              <div className="student-exams-popup-tile compact">
                <span>Published By</span>
                <b>{selectedAssessment.source_label || selectedAssessment.source_office || '--'}</b>
              </div>
              <div className="student-exams-popup-tile compact">
                <span>Schedule Version</span>
                <b>{`v${selectedAssessment.schedule_version || 1}`}</b>
              </div>
              <div className="student-exams-popup-tile compact">
                <span>Mode</span>
                <b>{selectedAssessment.mode || '--'}</b>
              </div>
              <div className="student-exams-popup-tile compact">
                <span>Student Seat Note</span>
                <b>{selectedAssessment.seat_note || examSeatSummary(selectedAssessment)}</b>
              </div>
            </div>
            <div className="student-exams-detail-panel student-exams-popup-note">
              <span>Department Note</span>
              <p>{selectedAssessment.note || 'No additional timetable note was provided for this assessment.'}</p>
            </div>
          </div>
        </Modal>
      )}

      {selectedUpdate && (
        <Modal
          className="modal-wide student-exams-detail-modal"
          onClose={() => setSelectedUpdate(null)}
          title="Exam Update Details"
        >
          <div className="student-exams-popup">
            <div className="student-exams-popup-hero">
              <div>
                <div className="student-exams-popup-kicker">Student Exam Update</div>
                <div className="student-exams-detail-title">{selectedUpdate.message}</div>
                <div className="student-exams-detail-sub">
                  {joinParts([
                    selectedUpdate.course_code,
                    selectedUpdate.course_title,
                    selectedUpdate.assessment_name,
                    selectedUpdate.section ? `Section ${selectedUpdate.section}` : '',
                  ])}
                </div>
              </div>
              <div className="student-exams-popup-chip-stack">
                <span className={`student-exams-pill ${studentExamPillTone(selectedUpdate.status)}`}>{selectedUpdate.status?.label || 'Updated'}</span>
                <span className="student-scores-term-chip subtle">{formatSemesterLabel(selectedUpdate.academic_year, selectedUpdate.semester)}</span>
              </div>
            </div>
            <div className="student-exams-popup-grid">
              <div className="student-exams-popup-tile">
                <span>Updated On</span>
                <b>{formatDate(selectedUpdate.updated_at, true)}</b>
                <small>{selectedUpdate.source_office || 'Examination workflow'}</small>
              </div>
              <div className="student-exams-popup-tile">
                <span>Source</span>
                <b>{selectedUpdate.source_label || '--'}</b>
                <small>{selectedUpdate.faculty || '--'}</small>
              </div>
              <div className="student-exams-popup-tile">
                <span>Current Slot</span>
                <b>{timeRange(selectedUpdate.scheduled_at, selectedUpdate.end_at)}</b>
                <small>{formatDate(selectedUpdate.scheduled_at)}</small>
              </div>
              <div className="student-exams-popup-tile">
                <span>Venue</span>
                <b>{selectedUpdate.venue || '--'}</b>
                <small>{selectedUpdate.mode || '--'}</small>
              </div>
              <div className="student-exams-popup-tile highlight">
                <span>Seat Allocation</span>
                <b>{selectedUpdate.seat_label ? `Seat ${selectedUpdate.seat_label}` : 'Awaiting allocation'}</b>
                <small>{selectedUpdate.seat_zone || 'Specific student seat will appear here after office release.'}</small>
              </div>
              <div className="student-exams-popup-tile">
                <span>Faculty In Charge</span>
                <b>{selectedUpdate.faculty || '--'}</b>
                <small>{selectedUpdate.assessment_name || '--'}</small>
              </div>
              {selectedUpdate.score != null && (
                <div className="student-exams-popup-tile compact">
                  <span>Published Score</span>
                  <b>{`${formatScoreValue(selectedUpdate.score)} / ${formatScoreValue(selectedUpdate.max_marks)}`}</b>
                  <small>{selectedUpdate.grade || 'Published result'}</small>
                </div>
              )}
              {selectedUpdate.percentage != null && (
                <div className="student-exams-popup-tile compact">
                  <span>Percentage</span>
                  <b>{`${formatMetricValue(selectedUpdate.percentage)}%`}</b>
                  <small>Visible only after publication</small>
                </div>
              )}
            </div>
            {(selectedUpdate.previous_start_at || selectedUpdate.previous_venue || selectedUpdate.previous_status || selectedUpdate.new_start_at || selectedUpdate.new_venue || selectedUpdate.new_status) && (
              <div className="student-exams-popup-compare">
                <div className="student-exams-detail-panel">
                  <span>Previous Schedule</span>
                  <p>{joinParts([
                    selectedUpdate.previous_start_at ? formatDate(selectedUpdate.previous_start_at, true) : '',
                    selectedUpdate.previous_end_at ? timeRange(selectedUpdate.previous_start_at, selectedUpdate.previous_end_at) : '',
                    selectedUpdate.previous_venue,
                    selectedUpdate.previous_status ? formatAssessmentTypeLabel(selectedUpdate.previous_status) : '',
                  ]) || 'No previous slot recorded.'}</p>
                </div>
                <div className="student-exams-detail-panel">
                  <span>Current Schedule</span>
                  <p>{joinParts([
                    selectedUpdate.new_start_at ? formatDate(selectedUpdate.new_start_at, true) : '',
                    selectedUpdate.new_end_at ? timeRange(selectedUpdate.new_start_at, selectedUpdate.new_end_at) : '',
                    selectedUpdate.new_venue,
                    selectedUpdate.new_status ? formatAssessmentTypeLabel(selectedUpdate.new_status) : '',
                  ]) || 'Current published state.'}</p>
                </div>
              </div>
            )}
            <div className="student-exams-detail-panel student-exams-popup-note">
              <span>Office Note</span>
              <p>{selectedUpdate.note || selectedUpdate.seat_note || 'No additional note was shared for this update.'}</p>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

export function StudentScoresView() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState(DEFAULT_STUDENT_EXAM_FILTERS)
  const [focusTerm, setFocusTerm] = useState('all')

  async function load(nextFilters = filters) {
    setLoading(true)
    setError('')
    try {
      const next = await api.studentScores(nextFilters)
      setData(next)
      setFilters(current => ({ ...current, ...normalizeStudentExamFilters(next.filters?.applied || nextFilters), status: 'published' }))
    } catch (err: any) {
      setError(err?.message || 'We could not load your scores right now.')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load({ ...DEFAULT_STUDENT_EXAM_FILTERS, status: 'published' })
  }, [])

  useEffect(() => {
    const visibleGroups = data?.semester_groups || []
    if (focusTerm === 'all') return
    if (!visibleGroups.some((group: any) => scoreTermKey(group.academic_year, group.semester) === focusTerm)) {
      setFocusTerm('all')
    }
  }, [focusTerm, data?.semester_groups])

  if (loading && !data) return <Spinner />

  const summary = data?.summary || {}
  const semesterGroups = data?.semester_groups || []
  const comingSoon = data?.coming_soon || []
  const backlogs = data?.backlogs || { current: 0, cleared: 0, subjects: [] }
  const filterMeta = data?.filters || {}
  const displayedSemesterGroups = focusTerm === 'all'
    ? semesterGroups
    : semesterGroups.filter((group: any) => scoreTermKey(group.academic_year, group.semester) === focusTerm)

  return (
    <div className="student-exams-page student-scores-page fade-in">
      <PageHead
        title="Scores"
        sub="Published marks and official semester results for your login only."
      />

      {error && <div className="student-attendance-banner">{error}</div>}

      <section className="student-exams-toolbar">
        <div className="student-exams-filters">
          <label className="student-exams-filter">
            <span>Academic Year</span>
            <select value={filters.academic_year} onChange={event => setFilters(current => ({ ...current, academic_year: event.target.value }))}>
              <option value="">All Academic Years</option>
              {(filterMeta.academic_years || []).map((item: string) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="student-exams-filter">
            <span>Semester</span>
            <select value={filters.semester} onChange={event => setFilters(current => ({ ...current, semester: event.target.value }))}>
              <option value="">All Semesters</option>
              {(filterMeta.semesters || []).map((item: number) => <option key={item} value={String(item)}>{`Semester ${item}`}</option>)}
            </select>
          </label>
          <label className="student-exams-filter">
            <span>Course</span>
            <select value={filters.course_id} onChange={event => setFilters(current => ({ ...current, course_id: event.target.value }))}>
              <option value="">All Courses</option>
              {(filterMeta.courses || []).map((item: any) => <option key={item.id} value={item.id}>{`${item.code} ${item.title}`}</option>)}
            </select>
          </label>
          <label className="student-exams-filter">
            <span>Assessment Type</span>
            <select value={filters.assessment_type} onChange={event => setFilters(current => ({ ...current, assessment_type: event.target.value }))}>
              <option value="">All Assessment Types</option>
              {(filterMeta.assessment_types || []).map((item: string) => <option key={item} value={item}>{formatAssessmentTypeLabel(item)}</option>)}
            </select>
          </label>
        </div>
        <div className="student-exams-toolbar-side">
          <div className="student-exams-sync-label">
            <span className="student-attendance-sync-dot" />
            Updated <b>{formatDate(data?.refreshed_at, true)}</b>
          </div>
          <button className="student-exams-reset" disabled={loading} onClick={() => {
            const next = { ...DEFAULT_STUDENT_EXAM_FILTERS, status: 'published' }
            setFocusTerm('all')
            setFilters(next)
            load(next)
          }} type="button">
            Reset
          </button>
          <button className="student-exams-apply" disabled={loading} onClick={() => load({ ...filters, status: 'published' })} type="button">
            {loading ? 'Applying...' : 'Apply Filters'}
          </button>
        </div>
      </section>

      <div className="student-scores-summary-grid">
        <section className="student-exams-card student-scores-summary-card">
          <div className="student-exams-card-head">
            <div>
              <h3>Official Standing</h3>
              <p>CGPA and backlog counts are read-only values from the official result pipeline.</p>
            </div>
          </div>
          <div className="student-scores-standing">
            <div className="student-scores-standing-value">{summary.cgpa != null ? formatMetricValue(summary.cgpa) : '--'}</div>
            <div className="student-scores-standing-label">{summary.cgpa_label || 'Current standing'}</div>
            <div className="student-scores-standing-meta">{`${summary.backlogs ?? 0} active backlog${summary.backlogs === 1 ? '' : 's'} / ${summary.cleared_backlogs ?? 0} cleared / ${summary.visible_semesters ?? 0} semesters in view`}</div>
          </div>
        </section>

        <section className="student-exams-card student-scores-summary-card">
          <div className="student-exams-card-head">
            <div>
              <h3>Semester GPA</h3>
              <p>Displayed semester GPAs are official credit-weighted results only.</p>
            </div>
          </div>
          <div className="student-scores-sgpa-list">
            {(summary.sgpa_rows || []).map((item: any) => (
              <div className="student-scores-sgpa-chip" key={`${item.academic_year}_${item.semester}`}>
                <b>{item.sgpa != null ? formatMetricValue(item.sgpa) : '--'}</b>
                <span>{`${item.academic_year} / Semester ${item.semester}`}</span>
              </div>
            ))}
            {(!summary.sgpa_rows || summary.sgpa_rows.length === 0) && <Empty text="Official SGPA will appear after published semester results." />}
          </div>
        </section>
      </div>

      <section className="student-exams-card student-scores-nav-card">
        <div className="student-exams-card-head">
          <div>
            <h3>Semester Navigation</h3>
            <p>Use filters for the official dataset, then use these chips to focus on one published semester at a time.</p>
          </div>
          <span className="student-exams-card-meta">{`${displayedSemesterGroups.length} shown / ${semesterGroups.length} available`}</span>
        </div>
        <div className="student-scores-nav-strip">
          <button
            className={`student-scores-nav-chip ${focusTerm === 'all' ? 'active' : ''}`}
            onClick={() => setFocusTerm('all')}
            type="button"
          >
            <b>All Semesters</b>
            <span>{`${summary.visible_semesters ?? semesterGroups.length} visible`}</span>
          </button>
          {semesterGroups.map((group: any) => {
            const key = scoreTermKey(group.academic_year, group.semester)
            return (
              <button
                className={`student-scores-nav-chip ${focusTerm === key ? 'active' : ''}`}
                key={key}
                onClick={() => setFocusTerm(key)}
                type="button"
              >
                <b>{`Semester ${group.semester}`}</b>
                <span>{group.academic_year}</span>
              </button>
            )
          })}
        </div>
        <div className="student-scores-highlights">
          <div className="student-scores-highlight">
            <span>Published Scores</span>
            <b>{summary.published_marks ?? 0}</b>
          </div>
          <div className="student-scores-highlight">
            <span>Coming Soon</span>
            <b>{summary.coming_soon ?? 0}</b>
          </div>
          <div className="student-scores-highlight">
            <span>Active Backlogs</span>
            <b>{summary.backlogs ?? 0}</b>
          </div>
          <div className="student-scores-highlight">
            <span>Cleared Backlogs</span>
            <b>{summary.cleared_backlogs ?? 0}</b>
          </div>
        </div>
      </section>

      <section className="student-exams-card student-scores-coming-card">
        <div className="student-exams-card-head">
          <div>
            <h3>Results Publishing Soon</h3>
            <p>These completed assessments are awaiting faculty or examination office publication.</p>
          </div>
          <span className="student-exams-card-meta">{`${summary.coming_soon ?? 0} pending`}</span>
        </div>
        <div className="student-scores-coming-grid">
          {comingSoon.map((item: any) => (
            <article className="student-scores-coming-item" key={item.assessment_id}>
              <div className="student-scores-coming-head">
                <div>
                  <b>{item.assessment_name}</b>
                  <span>{joinParts([item.course_code, item.course_title, formatSemesterLabel(item.academic_year, item.semester)])}</span>
                </div>
                <span className={`student-exams-pill ${studentExamPillTone(item.status)}`}>{item.status?.label || 'Publishing Soon'}</span>
              </div>
              <div className="student-scores-coming-meta">
                {joinParts([
                  item.completed_at ? `Completed ${formatDate(item.completed_at, true)}` : '',
                  item.venue,
                  item.mode,
                ])}
              </div>
              <p>{item.note || 'Publication is in progress for this assessment.'}</p>
            </article>
          ))}
          {comingSoon.length === 0 && <Empty text="No completed assessments are currently awaiting publication." />}
        </div>
      </section>

      <div className="student-scores-term-list">
        {displayedSemesterGroups.map((group: any) => (
          <section className="student-exams-card student-scores-term-card" key={`${group.academic_year}_${group.semester}`}>
            <div className="student-scores-term-head">
              <div>
                <h3>{group.label}</h3>
                <p>{joinParts([
                  group.sgpa_label || 'Official SGPA pending',
                  `${group.summary?.official_results ?? 0} official subjects`,
                  `${group.summary?.published_scores ?? 0} published assessment scores`,
                ])}</p>
              </div>
              <div className="student-scores-term-chip-row">
                <span className="student-scores-term-chip">
                  <b>{group.sgpa != null ? formatMetricValue(group.sgpa) : '--'}</b>
                  <span>SGPA</span>
                </span>
                <span className="student-scores-term-chip">
                  <b>{group.summary?.active_backlogs ?? 0}</b>
                  <span>Backlogs</span>
                </span>
                <span className="student-scores-term-chip">
                  <b>{group.summary?.published_scores ?? 0}</b>
                  <span>Scores</span>
                </span>
                <span className="student-scores-term-chip">
                  <b>{group.summary?.pending_publications ?? 0}</b>
                  <span>Coming Soon</span>
                </span>
              </div>
            </div>

            <div className="student-scores-term-stats">
              <div className="student-scores-term-stat">
                <span>Average Score</span>
                <b>{group.summary?.average_score_pct != null ? `${formatMetricValue(group.summary.average_score_pct)}%` : '--'}</b>
              </div>
              <div className="student-scores-term-stat">
                <span>Official Results</span>
                <b>{group.summary?.official_results ?? 0}</b>
              </div>
              <div className="student-scores-term-stat">
                <span>Credits Counted</span>
                <b>{formatScoreValue(group.summary?.credits)}</b>
              </div>
              <div className="student-scores-term-stat">
                <span>Cleared Backlogs</span>
                <b>{group.summary?.cleared_backlogs ?? 0}</b>
              </div>
            </div>

            <div className="student-scores-term-grid">
              <section className="student-scores-mini-card">
                <div className="student-scores-mini-head">
                  <h4>Assessment Scores</h4>
                  <span>{`${group.published_marks?.length ?? 0} published`}</span>
                </div>
                <div className="tbl-scroll student-exams-table-wrap">
                  <table className="tbl student-exams-table">
                    <thead>
                      <tr>
                        <th>Assessment</th>
                        <th>Course</th>
                        <th>Type</th>
                        <th>Score</th>
                        <th>Percentage</th>
                        <th>Published On</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(group.published_marks || []).map((item: any) => (
                        <tr key={`${item.assessment_id}_${item.published_at}`}>
                          <td>{item.assessment_name}</td>
                          <td>
                            <div className="student-exams-course-title">{item.course_code}</div>
                            <div className="student-exams-course-sub">{item.course_title}</div>
                          </td>
                          <td>{formatAssessmentTypeLabel(item.assessment_type)}</td>
                          <td><b>{`${formatScoreValue(item.score)} / ${formatScoreValue(item.max_marks)}`}</b></td>
                          <td>{item.percentage != null ? `${formatMetricValue(item.percentage)}%` : '--'}</td>
                          <td>{formatDate(item.published_at)}</td>
                        </tr>
                      ))}
                      {(!group.published_marks || group.published_marks.length === 0) && (
                        <tr><td colSpan={6}><div className="empty">No published assessment scores are available for this semester yet.</div></td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="student-scores-mini-card">
                <div className="student-scores-mini-head">
                  <h4>Official Subject Results</h4>
                  <span>{`${group.official_results?.length ?? 0} subjects`}</span>
                </div>
                <div className="tbl-scroll student-exams-table-wrap">
                  <table className="tbl student-exams-table">
                    <thead>
                      <tr>
                        <th>Subject</th>
                        <th>Grade</th>
                        <th>Credits</th>
                        <th>Percentage</th>
                        <th>Outcome</th>
                        <th>Published On</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(group.official_results || []).map((item: any) => (
                        <tr key={item.id}>
                          <td>
                            <div className="student-exams-course-title">{item.subject_code}</div>
                            <div className="student-exams-course-sub">{item.subject_title}</div>
                          </td>
                          <td>{item.grade || '--'}</td>
                          <td>{formatScoreValue(item.credits)}</td>
                          <td>{item.percentage != null ? `${formatMetricValue(item.percentage)}%` : '--'}</td>
                          <td>
                            <span className={`student-exams-pill ${studentScoreBacklogTone(item.backlog_status)}`}>
                              {item.backlog_status === 'active'
                                ? 'Backlog'
                                : item.backlog_status === 'cleared'
                                  ? 'Cleared'
                                  : formatAssessmentTypeLabel(item.outcome || 'published')}
                            </span>
                          </td>
                          <td>{formatDate(item.published_at)}</td>
                        </tr>
                      ))}
                      {(!group.official_results || group.official_results.length === 0) && (
                        <tr><td colSpan={6}><div className="empty">Official semester results are not published for this semester yet.</div></td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </section>
        ))}
        {displayedSemesterGroups.length === 0 && <Empty text="No semester score history matches the selected filters." />}
      </div>

      <section className="student-exams-card">
        <div className="student-exams-card-head">
          <div>
            <h3>Backlog Status</h3>
            <p>Backlogs reflect the latest published subject result only. Later passes automatically clear them.</p>
          </div>
        </div>
        <div className="student-exams-update-list">
          {(backlogs.subjects || []).map((item: any) => (
            <div className="student-exams-update-row" key={`${item.subject_code}_${item.semester}`}>
              <div className="student-exams-update-date">{item.academic_year || '--'}</div>
              <div className="student-exams-upcoming-copy">
                <div className="student-exams-row-title">{`${item.subject_code} ${item.subject_title}`}</div>
                <div className="student-exams-row-sub">{`Semester ${item.semester || '--'} / Attempt ${item.attempt || '--'}`}</div>
              </div>
              <span className="student-exams-pill danger">Failed</span>
            </div>
          ))}
          {(!backlogs.subjects || backlogs.subjects.length === 0) && <Empty text="No active backlogs in the latest published subject results." />}
        </div>
      </section>
    </div>
  )
}

export function StudentFeesView() {
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    api.studentFees().then(setData).catch(() => setData({ invoices: [], payments: [], summary: { balance: 0 } }))
  }, [])

  if (!data) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead title="Fees" sub="Your invoices, balance, and recorded payments" />
      <div className="grid-2">
        <div className="card">
          <div className="card-h"><h3>Fee invoices</h3><span className="hint">Balance {money(data.summary?.balance)}</span></div>
          <div className="tbl-scroll">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Term</th>
                  <th>Amount</th>
                  <th>Paid</th>
                  <th>Balance</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.invoices.map((invoice: any, index: number) => (
                  <tr key={`${invoice.term}-${index}`}>
                    <td>{invoice.term}</td>
                    <td>{money(invoice.amount)}</td>
                    <td>{money(invoice.paid)}</td>
                    <td><b style={{ color: invoice.balance > 0 ? 'var(--red)' : 'var(--teal-dk)' }}>{money(invoice.balance)}</b></td>
                    <td><span className={`pill s-${invoice.status}`}>{invoice.status}</span></td>
                  </tr>
                ))}
                {data.invoices.length === 0 && (
                  <tr><td colSpan={5}><div className="empty">No fee invoices found</div></td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-h"><h3>Payment history</h3></div>
          <div className="card-pad">
            {data.payments.map((payment: any, index: number) => (
              <div className="snap" key={`${payment.reference}-${index}`}>
                <span className="mono">{payment.reference}</span>
                <span><b>{money(payment.amount)}</b> - {payment.method}</span>
              </div>
            ))}
            {data.payments.length === 0 && <Empty text="No payments yet" />}
          </div>
        </div>
      </div>
    </div>
  )
}

export function StudentLibraryView() {
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    api.studentLibraryLoans().then(setData).catch(() => setData({ loans: [] }))
  }, [])

  if (!data) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead title="Library" sub="Your active book loans linked to the student account" />
      <div className="card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Book</th>
                <th>Issued On</th>
                <th>Due On</th>
                <th>Fine</th>
              </tr>
            </thead>
            <tbody>
              {data.loans.map((loan: any) => (
                <tr key={loan.id}>
                  <td>{loan.book}</td>
                  <td>{loan.issued_on || '-'}</td>
                  <td>{loan.due_on || '-'}</td>
                  <td>{money(loan.fine || 0)}</td>
                </tr>
              ))}
              {data.loans.length === 0 && (
                <tr><td colSpan={4}><div className="empty">0 active loans</div></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function StudentCalendarStat({ kind, label, value, sub }: { kind: string; label: string; value: number; sub: string }) {
  return (
    <div className="student-calendar-kpi-card">
      <span className={`student-calendar-kpi-icon ${kind}`}>
        <StudentCalendarGlyph kind={kind} />
      </span>
      <div className="student-calendar-kpi-copy">
        <div className="student-calendar-kpi-label">{label}</div>
        <div className="student-calendar-kpi-value">{value}</div>
        <div className="student-calendar-kpi-sub">{sub}</div>
      </div>
    </div>
  )
}

function StudentCalendarPanel(
  { title, meta, actionLabel, onAction, children }:
  { title: string; meta?: string; actionLabel?: string; onAction?: () => void; children: any },
) {
  return (
    <section className="student-calendar-panel">
      <div className="student-calendar-panel-head">
        <div>
          <h3>{title}</h3>
          {meta && <span>{meta}</span>}
        </div>
        {actionLabel && onAction && (
          <button className="student-calendar-panel-link" onClick={onAction} type="button">
            {actionLabel}
          </button>
        )}
      </div>
      <div className="student-calendar-panel-body">{children}</div>
    </section>
  )
}

function StudentCalendarGlyph({ kind }: { kind: string }) {
  switch (kind) {
    case 'month':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 3v4M16 3v4M3 10h18M8 14h3M13 14h3M8 18h5" /></svg>
    case 'class':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 0 4 23V5.5Z" /><path d="M12 3v18" /></svg>
    case 'assignment':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="6" y="4" width="12" height="16" rx="2" /><path d="M9 4.5h6M9 9h6M9 13h6M9 17h4" /></svg>
    case 'assessment':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 4h10l3 3v13H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" /><path d="M15 4v3h3M9 13h6M9 17h4" /></svg>
    case 'academic':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M7 2v4M17 2v4M3 9h18M7 13h10M7 17h6" /></svg>
    case 'finance':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 5h9M7 9h7M9 5c0 6 5 4 5 9 0 2-2 4-5 4" /></svg>
    case 'library':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M6 4h12v16H6z" /><path d="M9 4v16" /></svg>
    default:
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8" /></svg>
  }
}

function studentMonthStart(base = new Date()) {
  return `${base.getFullYear()}-${pad(base.getMonth() + 1)}-01`
}

function todayDateKey() {
  return toDayKey(new Date())
}

function shiftCalendarSelection(
  rawDate: string,
  delta: number,
  setSelectedDate: (value: string) => void,
  setMonth: (value: string) => void,
) {
  const nextDate = shiftStudentReferenceDate(rawDate, delta)
  setSelectedDate(nextDate)
  setMonth(studentMonthStart(parseIsoDate(nextDate)))
}

function updateCalendarDate(
  rawDate: string,
  setSelectedDate: (value: string) => void,
  setMonth: (value: string) => void,
) {
  if (!rawDate) return
  setSelectedDate(rawDate)
  setMonth(studentMonthStart(parseIsoDate(rawDate)))
}

function updateCalendarMonth(
  rawMonth: string,
  rawDate: string,
  setSelectedDate: (value: string) => void,
  setMonth: (value: string) => void,
) {
  if (!rawMonth) return
  const nextDate = buildDateFromMonth(rawMonth, rawDate)
  setSelectedDate(nextDate)
  setMonth(studentMonthStart(parseIsoDate(nextDate)))
}

function shiftStudentReferenceDate(rawDate: string, delta: number) {
  const base = parseIsoDate(rawDate)
  const next = new Date(base.getFullYear(), base.getMonth() + delta, 1)
  const maxDay = new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate()
  next.setDate(Math.min(base.getDate(), maxDay))
  return toDayKey(next)
}

function buildDateFromMonth(rawMonth: string, rawDate: string) {
  const [year, month] = rawMonth.split('-').map(Number)
  const current = parseIsoDate(rawDate)
  const next = new Date(year || current.getFullYear(), (month || current.getMonth() + 1) - 1, 1)
  const maxDay = new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate()
  next.setDate(Math.min(current.getDate(), maxDay))
  return toDayKey(next)
}

function buildStudentMonthGrid(rawStart: string) {
  const start = parseIsoDate(rawStart)
  const gridStart = new Date(start)
  gridStart.setDate(gridStart.getDate() - gridStart.getDay())
  const out = []
  for (let i = 0; i < 42; i += 1) {
    const day = new Date(gridStart)
    day.setDate(gridStart.getDate() + i)
    out.push({
      key: toDayKey(day),
      date: day,
      currentMonth: day.getMonth() === start.getMonth(),
      today: toDayKey(day) === toDayKey(new Date()),
    })
  }
  return out
}

function groupStudentCalendarEvents(events: any[]) {
  const map: Record<string, any[]> = {}
  events.forEach(event => {
    const start = new Date(event.start)
    const end = new Date(event.end || event.start)
    const cursor = new Date(start)
    cursor.setHours(0, 0, 0, 0)
    const endDay = new Date(end)
    endDay.setHours(0, 0, 0, 0)
    while (cursor <= endDay) {
      const key = toDayKey(cursor)
      ;(map[key] = map[key] || []).push(event)
      cursor.setDate(cursor.getDate() + 1)
    }
  })
  Object.values(map).forEach(bucket => bucket.sort((left, right) => +new Date(left.start) - +new Date(right.start)))
  return map
}

function parseIsoDate(raw: string) {
  const [year, month, day] = (raw || '').slice(0, 10).split('-').map(Number)
  return new Date(year || 2026, (month || 1) - 1, day || 1)
}

function toDayKey(value: Date) {
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`
}

function formatMonthLabel(rawStart: string) {
  return parseIsoDate(rawStart).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
}

function formatLongDate(value: Date) {
  return value.toLocaleDateString('en-IN', { weekday: 'long', day: '2-digit', month: 'short', year: 'numeric' })
}

function formatAcademicRange(startDate: string, endDate: string) {
  const start = parseIsoDate(startDate)
  const end = parseIsoDate(endDate || startDate)
  const startLabel = start.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
  const endLabel = end.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
  return startDate === endDate ? endLabel : `${startLabel} - ${endLabel}`
}

function formatDeadlineBadge(item: any) {
  if (item.kind === 'assignment' && item.badge) return item.badge
  const target = new Date(item.date)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  target.setHours(0, 0, 0, 0)
  const diff = Math.round((target.getTime() - today.getTime()) / 86400000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  return target.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function formatClockLabel(raw: string) {
  if (!raw) return '--'
  const [hour, minute] = raw.split(':').map(Number)
  const base = new Date(2026, 7, 24, hour || 0, minute || 0)
  return base.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })
}

function studentMonthOptions() {
  return Array.from({ length: 12 }, (_, index) =>
    new Date(2026, index, 1).toLocaleDateString('en-IN', { month: 'long' }),
  )
}

function buildStudentYearOptions(selectedYear: number) {
  const currentYear = new Date().getFullYear()
  const start = Math.min(currentYear - 4, selectedYear - 4)
  const end = Math.max(currentYear + 6, selectedYear + 6)
  const years = []
  for (let year = start; year <= end; year += 1) years.push(year)
  return years
}

function buildDateWithMonth(rawDate: string, monthIndex: number) {
  const current = parseIsoDate(rawDate)
  const next = new Date(current.getFullYear(), monthIndex, 1)
  const maxDay = new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate()
  next.setDate(Math.min(current.getDate(), maxDay))
  return toDayKey(next)
}

function buildDateWithYear(rawDate: string, year: number) {
  const current = parseIsoDate(rawDate)
  const next = new Date(year, current.getMonth(), 1)
  const maxDay = new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate()
  next.setDate(Math.min(current.getDate(), maxDay))
  return toDayKey(next)
}

function blankPersonalEvent(date: string) {
  return {
    id: '',
    title: '',
    startDate: date,
    startTime: '09:00',
    endDate: date,
    endTime: '10:00',
    note: '',
  }
}

function buildPersonalEventPayload(form: any) {
  const startAt = combineDateAndTime(form.startDate, form.startTime)
  const endAt = combineDateAndTime(form.endDate, form.endTime)
  return {
    title: String(form.title || '').trim() || 'Personal Event',
    note: String(form.note || '').trim(),
    start_at: startAt,
    end_at: endAt,
  }
}

function combineDateAndTime(rawDate: string, rawTime: string) {
  const dateKey = rawDate || todayDateKey()
  const timeKey = rawTime || '09:00'
  return `${dateKey}T${timeKey}:00`
}

function pad(value: number) {
  return String(value).padStart(2, '0')
}
