import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Spinner } from './kit'

function iso(d: Date) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
function monday(d: Date) { const x = new Date(d); x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); x.setHours(0, 0, 0, 0); return x }
function time(value: string) { const d = new Date(value); return Number.isNaN(d.getTime()) ? 'All day' : d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }) }
function viewDays(anchor: Date, mode: 'day' | 'week' | 'month') {
  if (mode === 'day') return [new Date(anchor)]
  if (mode === 'week') return Array.from({ length: 7 }, (_, i) => { const d = monday(anchor); d.setDate(d.getDate() + i); return d })
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1)
  const start = monday(first); const last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0)
  const count = Math.ceil((last.getDate() + ((first.getDay() + 6) % 7)) / 7) * 7
  return Array.from({ length: count }, (_, i) => { const d = new Date(start); d.setDate(d.getDate() + i); return d })
}
function monthKey(d: Date) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01` }

export default function MySchedule({ user, go }: { user: any; go: (view: string) => void }) {
  const [anchor, setAnchor] = useState(monday(new Date()))
  const [data, setData] = useState<any>(null)
  const [mode, setMode] = useState<'day' | 'week' | 'month'>('week')
  const [category, setCategory] = useState('all')
  const days = useMemo(() => viewDays(anchor, mode), [anchor, mode])
  useEffect(() => {
    const keys = [...new Set(days.map(monthKey))]
    Promise.all(keys.map(key => api.calendar(key))).then(results => {
      const unique = new Map<string, any>()
      results.flatMap(result => result.events || []).forEach((event: any) => unique.set(event.id, event))
      setData({ events: [...unique.values()], range: { label: anchor.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' }) } })
    }).catch(() => setData({ events: [] }))
  }, [anchor, days])
  const events = useMemo(() => (data?.events || []).filter((event: any) => event.source_type !== 'academic' && (event.source_type === 'manual' || event.source_type === 'workflow' || event.audience?.includes('leadership'))), [data])
  const categories = useMemo<string[]>(() => [...new Set<string>(events.map((event: any) => String(event.category || 'Other')))].sort(), [events])
  const visibleEvents = useMemo(() => category === 'all' ? events : events.filter((event: any) => (event.category || 'Other') === category), [events, category])
  const today = iso(new Date()); const todayEvents = events.filter((e: any) => e.start?.slice(0, 10) === today)
  const weekEnd = new Date(anchor); weekEnd.setDate(weekEnd.getDate() + 7)
  const weekEvents = events.filter((e: any) => { const d = new Date(e.start); return d >= anchor && d < weekEnd })
  const deadlines = events.filter((e: any) => e.source_type === 'workflow' || e.status === 'action').slice(0, 4)
  const meetings = events.filter((e: any) => /meeting|review|hearing/i.test(e.title)).slice(0, 4)
  const tasks = events.filter((e: any) => e.status === 'action' && e.start?.slice(0, 10) === today)
  if (!data) return <Spinner />
  return <div className="schedule-page fade-in">
    <header className="schedule-head"><div><h1>My Schedule</h1><p>Your personal schedule of meetings, deadlines, reviews, hearings, and events.</p><small>⌖ {user.scope || 'Campus'} <i /> {data.range?.label || 'Current month'} <i /> Acting as {user.active_role}</small></div><button className="schedule-add" onClick={() => go('calendar')}>＋ Add Event</button></header>
    <div className="schedule-summary"><ScheduleStat icon="calendar" label="Today" value={todayEvents.length} link="View today" onClick={() => { setAnchor(new Date()); setMode('day') }} /><ScheduleStat icon="calendar" label="This Week" value={weekEvents.length} link="View week" onClick={() => { setAnchor(new Date()); setMode('week') }} /><ScheduleStat icon="deadline" label="Deadlines" value={deadlines.length} link="View deadlines" onClick={() => go('approvals')} /><ScheduleStat icon="meeting" label="Upcoming Meetings" value={meetings.length} link="View meetings" onClick={() => setCategory('Meetings')} /><ScheduleStat icon="task" label="Tasks for Today" value={tasks.length} link="View tasks" onClick={() => { setAnchor(new Date()); setMode('day'); setCategory('Approvals') }} /><Agenda title="Today's Agenda" events={todayEvents} empty="No agenda items for today." go={go} /></div>
    <div className="schedule-main"><section className="schedule-board"><div className="schedule-tools"><div className="schedule-tabs">{(['day', 'week', 'month'] as const).map(item => <button key={item} className={mode === item ? 'on' : ''} onClick={() => setMode(item)}>{item}</button>)}</div><div className="schedule-nav"><button onClick={() => setAnchor(d => shift(d, mode, -1))}>‹</button><b>{days[0].toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })} – {days[days.length - 1].toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</b><button onClick={() => setAnchor(d => shift(d, mode, 1))}>›</button></div><select className="schedule-category" value={category} onChange={e => setCategory(e.target.value)}><option value="all">All Categories</option>{categories.map(item => <option key={item}>{item}</option>)}</select></div><div className={`schedule-grid ${mode}`}>{days.map(day => <div className={`schedule-day ${day.getMonth() !== anchor.getMonth() && mode === 'month' ? 'outside' : ''}`} key={iso(day)}><header><b>{day.toLocaleDateString('en-IN', { weekday: 'short' })}</b><span>{day.getDate()}</span></header>{visibleEvents.filter((e: any) => e.start?.slice(0, 10) === iso(day)).map((event: any) => <button className="schedule-event" style={{ borderLeftColor: event.color || '#1478ff' }} onClick={() => go(event.module_key || 'calendar')} key={event.id}><small>{event.all_day ? 'All day' : time(event.start)}</small><b>{event.title}</b><span>{event.location || event.category}</span></button>)}</div>)}</div></section><aside className="schedule-side"><Agenda title="Upcoming Deadlines" events={deadlines} empty="No approval deadlines." go={go}/><Agenda title="Upcoming Meetings" events={meetings} empty="No upcoming meetings." go={go}/></aside></div>
  </div>
}
function ScheduleStat({ icon, label, value, link, onClick }: any) { return <button className="schedule-stat" onClick={onClick}><span className={`schedule-stat-icon ${icon}`}>{icon === 'calendar' ? '▣' : icon === 'deadline' ? '◷' : icon === 'task' ? '✓' : '♧'}</span><div><small>{label}</small><b>{value}</b><em>{link} →</em></div></button> }
function Agenda({ title, events, empty, go }: any) { return <section className="schedule-agenda"><header><h2>{title}</h2><button onClick={() => go('calendar')}>View all</button></header>{events.length ? events.map((event: any) => <button onClick={() => go(event.module_key || 'calendar')} key={event.id}><span style={{ background: event.color || '#1478ff' }}/><div><b>{event.title}</b><small>{time(event.start)} · {event.location || event.category}</small></div></button>) : <p>{empty}</p>}</section> }
function shift(anchor: Date, mode: 'day' | 'week' | 'month', direction: number) { const next = new Date(anchor); if (mode === 'month') next.setMonth(next.getMonth() + direction); else next.setDate(next.getDate() + direction * (mode === 'week' ? 7 : 1)); return next }
