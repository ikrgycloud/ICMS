import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

function iso(value: Date) { return value.toISOString().slice(0, 10) }
function week(value: Date) { const next = new Date(value); next.setDate(next.getDate() - ((next.getDay() + 6) % 7)); return next }
function add(value: Date, days: number) { const next = new Date(value); next.setDate(next.getDate() + days); return next }

export default function FacultySchedule({ user, go }: { user: any; go: (view: string) => void }) {
  const [data, setData] = useState<any>(null), [anchor, setAnchor] = useState(week(new Date()))
  useEffect(() => { setData(null); api.facultySchedule(iso(anchor)).then(setData).catch(() => setData({ error: true })) }, [anchor, user?.active_role])
  const days = useMemo(() => Array.from({ length: 7 }, (_, index) => add(anchor, index)), [anchor])
  if (!data) return <Spinner />
  if (data.error) return <Empty icon="!" text="Your schedule could not be loaded." />
  const events = data.events || [], today = iso(new Date()), initials = (data.profile.name || 'P').split(' ').map((part: string) => part[0]).slice(0, 2).join('')
  const todayEvents = events.filter((event: any) => event.date === today), upcoming = events.filter((event: any) => event.date >= today).slice(0, 5)
  const detail = (event: any) => `${event.detail} · ${event.location}${event.leave_state ? ` · ${event.leave_state}` : ''}`
  return <div className="faculty-schedule fade-in">
    <section className="faculty-hero"><div className="faculty-hero-avatar">{initials}</div><div className="faculty-identity"><h1>My Schedule</h1><p>Weekly classes and authoritative academic commitments</p><span>✉ {data.profile.email || 'Email not configured'} {data.profile.phone && <> <i /> ☎ {data.profile.phone}</>}</span></div></section>
    <div className="faculty-kpis faculty-schedule-kpis"><Kpi title="Total Classes This Week" value={data.summary.classes} note={`${data.summary.sections} assigned sections`} tone="blue"/><Kpi title="Meetings" value={data.summary.meetings} note={data.summary.meetings ? 'Assigned commitments' : 'Not configured'} tone="purple"/><Kpi title="Office Hours" value={data.profile.office_hours || 'Not configured'} note="Faculty profile" tone="mint"/><Kpi title="Leave Requests" value={data.summary.leave_requests} note="Pending or approved this week" tone="orange"/></div>
    <div className="faculty-schedule-layout"><section className="faculty-card faculty-schedule-board"><header><h2>Weekly Schedule</h2><div><button type="button" onClick={() => setAnchor(add(anchor, -7))}>← Previous</button><b>{days[0].toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })} – {days[6].toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</b><button type="button" onClick={() => setAnchor(add(anchor, 7))}>Next →</button></div></header><div className="faculty-week-grid">{days.map(day => { const dayEvents = events.filter((event: any) => event.date === iso(day)); return <section key={iso(day)}><h3>{day.toLocaleDateString('en-IN', { weekday: 'short' })}<small>{day.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</small></h3>{dayEvents.map((event: any) => <button key={event.id} className={`faculty-week-event ${event.status === 'unavailable' ? 'leave' : event.type}`} onClick={() => go(event.route)} type="button"><small>{event.time}{event.end_time ? `–${event.end_time}` : ''}</small><b>{event.title}</b><span>{detail(event)}</span></button>)}{!dayEvents.length && <p>No classes scheduled.</p>}</section> })}</div></section><aside className="faculty-card faculty-schedule-agenda"><Title title="Today's Agenda" action="View current week" onClick={() => setAnchor(week(new Date()))}/>{todayEvents.length ? todayEvents.map((event: any) => <button className="faculty-list-row" key={event.id} onClick={() => go(event.route)} type="button"><b>C</b><div><strong>{event.title}</strong><span>{event.time} · {event.location}</span></div></button>) : <Empty icon="✓" text="No agenda items today." />}</aside></div>
    <div className="faculty-overview-grid lower"><section className="faculty-card"><Title title="Upcoming Commitments" action="Open calendar" onClick={() => go('calendar')}/>{upcoming.length ? upcoming.map((event: any) => <button className="faculty-list-row" key={event.id} onClick={() => go(event.route)} type="button"><b>C</b><div><strong>{event.title}</strong><span>{detail(event)}</span></div><em>{event.date} {event.time}</em></button>) : <Empty icon="—" text="No upcoming commitments." />}</section><section className="faculty-card faculty-quick"><h2>Quick Actions</h2><div><button type="button" onClick={() => go('attendance')}>Mark Attendance</button><button type="button" onClick={() => go('academics')}>View My Sections</button><button type="button" onClick={() => go('calendar')}>Academic Calendar</button><button type="button" onClick={() => go('workflows')}>My Requests</button></div></section></div>
  </div>
}

function Kpi({ title, value, note, tone }: any) { return <section className={`faculty-metric ${tone}`}><i>▣</i><div><span>{title}</span><b>{value}</b><small>{note}</small></div></section> }
function Title({ title, action, onClick }: any) { return <header><h2>{title}</h2><button type="button" onClick={onClick}>{action} →</button></header> }
