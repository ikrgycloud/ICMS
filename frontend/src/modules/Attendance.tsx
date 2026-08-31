import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast, Empty } from './kit'

export default function Attendance({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  const [sel, setSel] = useState<any>(null)
  const [roster, setRoster] = useState<any>(null)
  const [present, setPresent] = useState<Record<string, boolean>>({})
  const [decision, setDecision] = useState<any>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => { api.attendanceSections().then(setData).catch(() => {}) }, [])

  function openSection(s: any) {
    setSel(s); setRoster(null)
    api.attendanceRoster(s.id).then(r => {
      setRoster(r)
      const init: Record<string, boolean> = {}
      r.roster.forEach((x: any) => { init[x.student_id] = true })
      setPresent(init)
    })
  }

  async function save() {
    setSaving(true)
    const present_ids = Object.keys(present).filter(k => present[k])
    const absent_ids = Object.keys(present).filter(k => !present[k])
    try {
      const r = await api.markAttendance({ section_id: sel.id, present_ids, absent_ids })
      setDecision(r.decision)
      api.attendanceSections().then(setData)
      openSection(sel)
    } catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }) }
    setSaving(false)
  }

  if (!data) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead title="Attendance" sub={caps.mark ? 'Select a section to mark today’s attendance' : 'View attendance across sections'} />

      <div className="split">
        <div className="card" style={{ flex: '0 0 340px' }}>
          <div className="card-h"><h3>Sections</h3></div>
          <div className="list">
            {data.sections.map((s: any) => (
              <button key={s.id} className={`list-item ${sel?.id === s.id ? 'on' : ''}`} onClick={() => openSection(s)}>
                <div>
                  <div className="li-title mono">{s.course_code} · {s.section}</div>
                  <div className="li-sub">{s.course_title}</div>
                </div>
                <div className="li-metric">{s.attendance_pct != null ? `${s.attendance_pct}%` : '—'}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="card" style={{ flex: 1 }}>
          {!sel && <Empty icon="✔" text="Select a section to view its roster" />}
          {sel && !roster && <Spinner />}
          {sel && roster && (
            <>
              <div className="card-h">
                <h3>{sel.course_code} · Section {sel.section}</h3>
                {caps.mark && <button className="btn btn-teal" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save attendance'}</button>}
              </div>
              <div className="card-pad">
                {caps.mark && (
                  <div className="mark-actions">
                    <button className="linkish" onClick={() => { const a: any = {}; roster.roster.forEach((x: any) => a[x.student_id] = true); setPresent(a) }}>All present</button>
                    <button className="linkish" onClick={() => { const a: any = {}; roster.roster.forEach((x: any) => a[x.student_id] = false); setPresent(a) }}>All absent</button>
                  </div>
                )}
                <div className="tbl-scroll">
                  <table className="tbl">
                    <thead><tr><th>Roll No</th><th>Name</th><th>Cumulative</th>{caps.mark && <th>Today</th>}</tr></thead>
                    <tbody>
                      {roster.roster.map((x: any) => (
                        <tr key={x.student_id}>
                          <td className="mono">{x.roll_no}</td>
                          <td>{x.name}</td>
                          <td>{x.pct != null ? `${x.pct}% (${x.present}/${x.total})` : 'no records'}</td>
                          {caps.mark && (
                            <td>
                              <label className="switch">
                                <input type="checkbox" checked={!!present[x.student_id]}
                                  onChange={e => setPresent({ ...present, [x.student_id]: e.target.checked })} />
                                <span className={present[x.student_id] ? 'sw-p' : 'sw-a'}>{present[x.student_id] ? 'Present' : 'Absent'}</span>
                              </label>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
