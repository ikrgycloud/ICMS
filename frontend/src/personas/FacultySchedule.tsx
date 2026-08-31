import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

function iso(value: Date) { return value.toISOString().slice(0, 10) }
function week(date: Date) { const next = new Date(date); next.setDate(next.getDate() - ((next.getDay() + 6) % 7)); return next }
function add(date: Date, days: number) { const next = new Date(date); next.setDate(next.getDate() + days); return next }

export default function FacultySchedule({ user, go }: { user: any; go: (view: string) => void }) {
  const [data, setData] = useState<any>(null)
  const [anchor, setAnchor] = useState(week(new Date()))
  useEffect(() => { api.facultySchedule().then(setData).catch(() => setData({ error: true })) }, [user?.active_role])
  const days = useMemo(() => Array.from({ length: 6 }, (_, index) => add(anchor, index)), [anchor])
  if (!data) return <Spinner />
  if (data.error) return <Empty icon="!" text="Your schedule could not be loaded." />
  const events = data.events || []; const today = iso(new Date()); const initials = (data.profile.name || 'P').split(' ').map((part: string) => part[0]).slice(0, 2).join('')
  const shown = events.filter((event: any) => days.some(day => iso(day) === event.date))
  const todayEvents = events.filter((event: any) => event.date === today)
  return <div className="faculty-schedule fade-in">
    <section className="faculty-hero"><div className="faculty-hero-avatar">{initials}</div><div className="faculty-identity"><h1>My Schedule</h1><p>Weekly classes, academic commitments, and office hours</p><span>✉ {data.profile.email || 'Email not set'} {data.profile.phone && <> <i /> ☎ {data.profile.phone}</>}</span></div></section>
    <div className="faculty-kpis faculty-schedule-kpis"><ScheduleKpi title="Total Classes This Week" value={data.summary.classes} note={`${data.summary.sections} assigned sections`} tone="blue"/><ScheduleKpi title="Meetings" value={data.summary.meetings} note="Staff commitments" tone="purple"/><ScheduleKpi title="Office Hours" value={data.profile.office_hours || 'Not set'} note="From your faculty profile" tone="mint"/><ScheduleKpi title="Leave Requests" value={data.summary.leave_requests} note="Pending or approved" tone="orange"/></div>
    <div className="faculty-schedule-layout"><section className="faculty-card faculty-schedule-board"><header><h2>Weekly Schedule</h2><div><button onClick={() => setAnchor(add(anchor, -7))}>← Previous</button><b>{days[0].toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })} – {days[days.length - 1].toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</b><button onClick={() => setAnchor(add(anchor, 7))}>Next →</button></div></header><div className="faculty-week-grid">{days.map(day => <section key={iso(day)}><h3>{day.toLocaleDateString('en-IN', { weekday: 'short' })}<small>{day.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</small></h3>{shown.filter((event: any) => event.date === iso(day)).map((event: any) => <button key={event.id} className={`faculty-week-event ${event.type}`} onClick={() => go(event.route)}><small>{event.time}</small><b>{event.title}</b><span>{event.detail} · {event.location}</span></button>) || null}{!shown.some((event: any) => event.date === iso(day)) && <p>No commitments</p>}</section>)}</div></section><aside className="faculty-card faculty-schedule-agenda"><CardTitle title="Today's Agenda" action="View full schedule" onClick={() => setAnchor(week(new Date()))}/>{todayEvents.length ? todayEvents.map((event: any) => <button className="faculty-list-row" key={event.id} onClick={() => go(event.route)}><b>{event.type === 'class' ? 'C' : 'M'}</b><div><strong>{event.title}</strong><span>{event.time} · {event.location}</span></div></button>) : <Empty icon="✓" text="No agenda items today." />}</aside></div>
    <div className="faculty-overview-grid lower"><section className="faculty-card"><CardTitle title="Upcoming Commitments" action="Open calendar" onClick={() => go('calendar')}/>{events.filter((event: any) => event.date >= today).slice(0, 5).map((event: any) => <button className="faculty-list-row" key={event.id} onClick={() => go(event.route)}><b>{event.type === 'class' ? 'C' : 'M'}</b><div><strong>{event.title}</strong><span>{event.detail} · {event.location}</span></div><em>{event.date} {event.time}</em></button>)}</section><section className="faculty-card faculty-quick"><h2>Quick Actions</h2><div><button onClick={() => go('attendance')}>Mark Attendance</button><button onClick={() => go('academics')}>View My Sections</button><button onClick={() => go('calendar')}>Academic Calendar</button><button onClick={() => go('workflows')}>My Requests</button></div></section></div>
  </div>
}
function ScheduleKpi({ title, value, note, tone }: any) { return <section className={`faculty-metric ${tone}`}><i>▣</i><div><span>{title}</span><b>{value}</b><small>{note}</small></div></section> }
function CardTitle({ title, action, onClick }: any) { return <header><h2>{title}</h2><button onClick={onClick}>{action} →</button></header> }
