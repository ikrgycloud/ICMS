import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

const dateLabel = (value: string) => value ? new Date(value).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) : '-'

export default function FacultyCommunication({ mode }: { mode: 'messages' | 'announcements' }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => {
    setData(null)
    const load = mode === 'messages' ? api.notifications : api.facultyAnnouncements
    load().then(setData).catch((error: any) => setData({ error: error.message || 'This information could not be loaded.' }))
  }, [mode])

  if (!data) return <Spinner />
  if (data.error) return <Empty icon="!" text={data.error} />
  const rows = mode === 'messages' ? data.notifications || [] : data.announcements || []
  const title = mode === 'messages' ? 'Messages' : 'Announcements'
  const sub = mode === 'messages'
    ? 'Notifications related to your teaching, requests, and faculty responsibilities.'
    : 'Published campus and department notices available to your faculty profile.'

  return <main className="faculty-students fade-in">
    <section className="faculty-students-heading"><div><h1>{title}</h1><p>{sub}</p></div></section>
    <article className="faculty-student-table-card">
      <header><div><h2>{title}</h2><p>{rows.length ? `${rows.length} item${rows.length === 1 ? '' : 's'}` : 'No current items.'}</p></div></header>
      <div className="faculty-student-table-wrap"><table><thead><tr><th>Title</th><th>Message</th><th>Date</th></tr></thead><tbody>
        {rows.map((row: any) => <tr key={row.id}><td><b>{row.title}</b></td><td>{mode === 'messages' ? row.body || row.detail || '-' : row.body || '-'}</td><td>{dateLabel(mode === 'messages' ? row.created_at : row.published_at)}</td></tr>)}
        {!rows.length && <tr><td colSpan={3}>No {mode === 'messages' ? 'messages' : 'announcements'} to display.</td></tr>}
      </tbody></table></div>
    </article>
  </main>
}


