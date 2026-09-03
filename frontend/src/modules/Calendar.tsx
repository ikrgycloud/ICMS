import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, Kpis, Modal, PageHead, Pill, Spinner } from './kit'

const AUDIENCES = [
  { value: 'all', label: 'All roles' },
  { value: 'leadership', label: 'Leadership only' },
  { value: 'staff', label: 'Staff only' },
  { value: 'students', label: 'Students only' },
  { value: 'parents', label: 'Parents only' },
  { value: 'operations', label: 'Operations teams' },
  { value: 'students,parents', label: 'Students and parents' },
  { value: 'staff,leadership', label: 'Staff and leadership' },
]

const CATEGORIES = [
  'Institution',
  'Governance',
  'Academics',
  'Students',
  'Finance',
  'Research',
  'Placements',
  'Operations',
  'Library',
  'Engagement',
]

const MONTH_OPTIONS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]

function monthStartIso(base = new Date()) {
  const d = new Date(base)
  d.setDate(1)
  return d.toISOString().slice(0, 10)
}

function localDateTime(offsetDays = 0, hour = 9, minute = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  d.setHours(hour, minute, 0, 0)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function blankForm() {
  return {
    id: '',
    title: '',
    category: 'Institution',
    audience: 'all',
    start_at: localDateTime(0, 9, 0),
    end_at: localDateTime(0, 10, 0),
    all_day: true,
    location: '',
    description: '',
    color: '#8a1f2b',
    status: 'published',
  }
}

export default function Calendar({ user, caps, readOnly = false }: { user: any; caps: any; readOnly?: boolean }) {
  const [month, setMonth] = useState(monthStartIso())
  const [selectedDate, setSelectedDate] = useState(dateInputValue(new Date()))
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [detail, setDetail] = useState<any>(null)
  const [form, setForm] = useState<any>(blankForm())

  async function load(targetMonth = month) {
    setLoading(true)
    setError('')
    try {
      const next = await api.calendar(targetMonth)
      setData(next)
    } catch (err: any) {
      setError(err?.message || 'We could not load the calendar right now.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(month)
  }, [month])

  const monthDays = useMemo(() => buildMonthGrid(data?.range?.start || month), [data?.range?.start, month])
  const eventsByDay = useMemo(() => {
    const map: Record<string, any[]> = {}
    ;(data?.events || []).forEach((event: any) => {
      const start = new Date(event.start)
      const end = new Date(event.end || event.start)
      const cursor = new Date(start)
      cursor.setHours(0, 0, 0, 0)
      const endDay = new Date(end)
      endDay.setHours(0, 0, 0, 0)
      while (cursor <= endDay) {
        const key = cursor.toISOString().slice(0, 10)
        ;(map[key] = map[key] || []).push(event)
        cursor.setDate(cursor.getDate() + 1)
      }
    })
    Object.values(map).forEach(bucket => bucket.sort((a, b) => +new Date(a.start) - +new Date(b.start)))
    return map
  }, [data])

  const canCreate = !readOnly && Boolean(data?.permissions?.create && caps?.create)
  const canEdit = !readOnly && Boolean(data?.permissions?.edit && caps?.edit)
  const canDelete = !readOnly && Boolean(data?.permissions?.delete && caps?.delete)
  const selected = parseLocalDate(selectedDate)
  const yearOptions = useMemo(() => buildYearOptions(selected.getFullYear()), [selectedDate])

  function commitCalendarSelection(next: Date) {
    setSelectedDate(dateInputValue(next))
    setMonth(monthStartIso(next))
  }

  function shiftMonth(direction: number) {
    const base = parseLocalDate(selectedDate || `${data?.range?.start || month}`)
    const next = new Date(base.getFullYear(), base.getMonth() + direction, 1)
    next.setDate(Math.min(base.getDate(), daysInMonth(next.getFullYear(), next.getMonth())))
    commitCalendarSelection(next)
  }

  function applyDate(raw: string) {
    if (!raw) return
    commitCalendarSelection(parseLocalDate(raw))
  }

  function applyMonth(monthIndex: number) {
    const base = parseLocalDate(selectedDate)
    const next = new Date(base.getFullYear(), monthIndex, 1)
    next.setDate(Math.min(base.getDate(), daysInMonth(next.getFullYear(), monthIndex)))
    commitCalendarSelection(next)
  }

  function applyYear(year: number) {
    const base = parseLocalDate(selectedDate)
    const next = new Date(year, base.getMonth(), 1)
    next.setDate(Math.min(base.getDate(), daysInMonth(year, base.getMonth())))
    commitCalendarSelection(next)
  }

  function openCreate() {
    const next = blankForm()
    setForm(next)
    setDetail(null)
    setShowModal(true)
  }

  function openEvent(event: any) {
    if (event.editable && canEdit && event.source_type === 'manual') {
      setForm({
        id: event.id,
        title: event.title,
        category: event.category,
        audience: event.audience,
        start_at: toDateTimeLocal(event.start),
        end_at: toDateTimeLocal(event.end || event.start),
        all_day: event.all_day,
        location: event.location || '',
        description: event.description || '',
        color: event.color || '#8a1f2b',
        status: event.status || 'published',
      })
      setDetail(null)
    } else {
      setDetail(event)
    }
    setShowModal(true)
  }

  async function saveEvent() {
    setSaving(true)
    try {
      if (form.id) await api.updateCalendarEvent(form.id, form)
      else await api.createCalendarEvent(form)
      setShowModal(false)
      setForm(blankForm())
      await load()
    } catch (err: any) {
      setError(err?.message || 'We could not save the calendar event.')
    } finally {
      setSaving(false)
    }
  }

  async function removeEvent() {
    if (!form.id) return
    setSaving(true)
    try {
      await api.deleteCalendarEvent(form.id)
      setShowModal(false)
      setForm(blankForm())
      await load()
    } catch (err: any) {
      setError(err?.message || 'We could not delete the calendar event.')
    } finally {
      setSaving(false)
    }
  }

  if (loading && !data) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead
        title="Institution Calendar"
        sub={`Live calendar for ${user.active_role}. This board blends shared events, academic milestones, and workflow-linked dates straight from the database.`}
        right={
          <div className="calendar-head-actions">
            <label className="calendar-jump-control">
              <span>Date</span>
              <input
                className="calendar-jump-input"
                type="date"
                value={selectedDate}
                onChange={e => applyDate(e.target.value)}
              />
            </label>
            <label className="calendar-jump-control">
              <span>Month</span>
              <select
                className="select calendar-jump-select"
                value={String(selected.getMonth())}
                onChange={e => applyMonth(Number(e.target.value))}
              >
                {MONTH_OPTIONS.map((label, index) => (
                  <option key={label} value={index}>{label}</option>
                ))}
              </select>
            </label>
            <label className="calendar-jump-control">
              <span>Year</span>
              <select
                className="select calendar-jump-select"
                value={String(selected.getFullYear())}
                onChange={e => applyYear(Number(e.target.value))}
              >
                {yearOptions.map(year => (
                  <option key={year} value={year}>{year}</option>
                ))}
              </select>
            </label>
            <button className="btn btn-out" onClick={() => commitCalendarSelection(new Date())} type="button">Today</button>
            <button className="btn btn-out" onClick={() => shiftMonth(-1)} type="button">Prev</button>
            <button className="btn btn-out" onClick={() => shiftMonth(1)} type="button">Next</button>
            {canCreate && <button className="btn btn-crimson" onClick={openCreate} type="button">Add event</button>}
          </div>
        }
      />

      {error && <div className="calendar-banner warn">{error}</div>}

      {data && (
        <>
          <Kpis items={[
            { label: 'Month', value: data.range.label },
            { label: 'Visible events', value: data.summary.events },
            { label: 'Today', value: data.summary.today },
            { label: 'Upcoming', value: data.summary.upcoming },
          ]} />

          <div className="calendar-layout" style={{ marginTop: 22 }}>
            <section className="card calendar-board-card">
              <div className="card-h">
                <h3>{data.range.label}</h3>
                <div className="calendar-legend">
                  <span><i className="legend-dot manual" /> Manual</span>
                  <span><i className="legend-dot academic" /> Academic</span>
                  <span><i className="legend-dot linked" /> Linked feeds</span>
                </div>
              </div>

              <div className="calendar-board">
                {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(label => (
                  <div className="calendar-weekday" key={label}>{label}</div>
                ))}
                {monthDays.map(day => {
                  const dayEvents = eventsByDay[day.key] || []
                  return (
                    <div
                      key={day.key}
                      className={`calendar-cell ${day.currentMonth ? '' : 'muted'} ${day.today ? 'today' : ''}`}
                    >
                      <div className="calendar-cell-top">
                        <span>{day.date.getDate()}</span>
                        {day.today && <em>Today</em>}
                      </div>
                      <div className="calendar-cell-events">
                        {dayEvents.slice(0, 3).map((event: any) => (
                          <button
                            key={`${day.key}-${event.id}`}
                            className={`calendar-pill ${eventTone(event.source_type)}`}
                            onClick={() => openEvent(event)}
                            type="button"
                            title={event.title}
                          >
                            {event.title}
                          </button>
                        ))}
                        {dayEvents.length > 3 && <div className="calendar-more">+{dayEvents.length - 3} more</div>}
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>

            <div className="calendar-side">
              <section className="card">
                <div className="card-h">
                  <h3>Upcoming</h3>
                  <span className="hint">next items</span>
                </div>
                <div className="calendar-agenda">
                  {data.upcoming?.length ? data.upcoming.map((event: any) => (
                    <button className="calendar-agenda-item" key={event.id} onClick={() => openEvent(event)} type="button">
                      <div className={`calendar-source-bar ${eventTone(event.source_type)}`} />
                      <div className="calendar-agenda-copy">
                        <div className="calendar-agenda-title">{event.title}</div>
                        <div className="calendar-agenda-meta">{prettyDate(event.start)} · {event.location || audienceLabel(event.audience)}</div>
                        <div className="calendar-agenda-body">{event.description || sourceLabel(event.source_type)}</div>
                      </div>
                    </button>
                  )) : <Empty icon="📆" text="No upcoming events in this month" />}
                </div>
              </section>

              <section className="card">
                <div className="card-h">
                  <h3>Source mix</h3>
                  <span className="hint">live DB feed</span>
                </div>
                <div className="card-pad">
                  <div className="snap"><span>Manual events</span><b>{data.summary.source_counts.manual}</b></div>
                  <div className="snap"><span>Academic milestones</span><b>{data.summary.source_counts.academic}</b></div>
                  <div className="snap"><span>Workflow-linked items</span><b>{data.summary.source_counts.linked}</b></div>
                  <div className="snap"><span>Your role</span><b>{user.active_role}</b></div>
                </div>
              </section>
            </div>
          </div>
        </>
      )}

      {showModal && !detail && (
        <Modal
          title={form.id ? 'Edit Calendar Event' : 'Add Calendar Event'}
          onClose={() => {
            setShowModal(false)
            setForm(blankForm())
          }}
          footer={
            <>
              {form.id && canDelete && <button className="btn btn-rose" onClick={removeEvent} disabled={saving}>Delete</button>}
              <button className="btn btn-out" onClick={() => setShowModal(false)} disabled={saving}>Cancel</button>
              <button className="btn btn-crimson" onClick={saveEvent} disabled={saving}>{saving ? 'Saving...' : 'Save event'}</button>
            </>
          }
        >
          <div className="form-row">
            <label>Title</label>
            <input className="inp" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
          </div>
          <div className="grid-2">
            <div className="form-row">
              <label>Category</label>
              <select className="select" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                {CATEGORIES.map(option => <option key={option} value={option}>{option}</option>)}
              </select>
            </div>
            <div className="form-row">
              <label>Audience</label>
              <select className="select" value={form.audience} onChange={e => setForm({ ...form, audience: e.target.value })}>
                {AUDIENCES.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
          </div>
          <div className="grid-2">
            <div className="form-row">
              <label>Start</label>
              <input className="inp" type="datetime-local" value={form.start_at} onChange={e => setForm({ ...form, start_at: e.target.value })} />
            </div>
            <div className="form-row">
              <label>End</label>
              <input className="inp" type="datetime-local" value={form.end_at} onChange={e => setForm({ ...form, end_at: e.target.value })} />
            </div>
          </div>
          <div className="grid-2">
            <div className="form-row">
              <label>Location</label>
              <input className="inp" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} />
            </div>
            <div className="form-row">
              <label>Accent</label>
              <input className="inp" type="color" value={form.color} onChange={e => setForm({ ...form, color: e.target.value })} />
            </div>
          </div>
          <div className="form-row">
            <label>Description</label>
            <textarea className="inp" rows={4} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          </div>
          <label className="calendar-check">
            <input type="checkbox" checked={form.all_day} onChange={e => setForm({ ...form, all_day: e.target.checked })} />
            <span>Render this as an all-day event in the month board</span>
          </label>
        </Modal>
      )}

      {showModal && detail && (
        <Modal title="Event details" onClose={() => { setShowModal(false); setDetail(null) }}>
          <div className="calendar-detail">
            <div className="calendar-detail-top">
              <Pill s={detail.status || 'scheduled'} />
              <span className={`calendar-source-chip ${eventTone(detail.source_type)}`}>{sourceLabel(detail.source_type)}</span>
            </div>
            <h3>{detail.title}</h3>
            <p>{detail.description || 'No additional notes were provided for this event.'}</p>
            <div className="snap"><span>When</span><b>{prettyDate(detail.start)}</b></div>
            <div className="snap"><span>Audience</span><b>{audienceLabel(detail.audience)}</b></div>
            <div className="snap"><span>Location</span><b>{detail.location || 'TBA'}</b></div>
            <div className="snap"><span>Linked module</span><b>{detail.module_key?.replace(/_/g, ' ') || 'calendar'}</b></div>
          </div>
        </Modal>
      )}
    </div>
  )
}

function buildMonthGrid(rawStart: string) {
  const start = new Date(`${rawStart}T00:00:00`)
  const gridStart = new Date(start)
  gridStart.setDate(gridStart.getDate() - gridStart.getDay())
  const out = []
  for (let i = 0; i < 42; i += 1) {
    const d = new Date(gridStart)
    d.setDate(gridStart.getDate() + i)
    const key = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
    out.push({
      key,
      date: d,
      currentMonth: d.getMonth() === start.getMonth(),
      today: key === new Date().toISOString().slice(0, 10),
    })
  }
  return out
}

function toDateTimeLocal(raw: string) {
  const d = new Date(raw)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function parseLocalDate(raw: string) {
  const [year, month, day] = String(raw || '').slice(0, 10).split('-').map(Number)
  return new Date(year || 2026, (month || 1) - 1, day || 1)
}

function dateInputValue(base: Date) {
  return `${base.getFullYear()}-${pad(base.getMonth() + 1)}-${pad(base.getDate())}`
}

function daysInMonth(year: number, monthIndex: number) {
  return new Date(year, monthIndex + 1, 0).getDate()
}

function buildYearOptions(selectedYear: number) {
  const start = Math.min(2020, selectedYear - 5)
  const end = Math.max(2032, selectedYear + 5)
  const out = []
  for (let year = start; year <= end; year += 1) out.push(year)
  return out
}

function prettyDate(raw: string) {
  const d = new Date(raw)
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function sourceLabel(source: string) {
  if (source === 'manual') return 'Manual event'
  if (source === 'academic') return 'Academic calendar'
  if (source === 'workflow') return 'Workflow feed'
  if (source === 'finance') return 'Finance feed'
  if (source === 'library') return 'Library feed'
  if (source === 'placement') return 'Placement feed'
  return 'Linked feed'
}

function audienceLabel(audience: string) {
  return audience.replace(/,/g, ', ').replace(/\b\w/g, ch => ch.toUpperCase())
}

function eventTone(source: string) {
  if (source === 'manual') return 'manual'
  if (source === 'academic') return 'academic'
  return 'linked'
}
