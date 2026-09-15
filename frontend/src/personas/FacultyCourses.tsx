import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Spinner } from '../modules/kit'

const hours = (value: number | undefined) => Number(value || 0)

export default function FacultyCourses({ go }: { go: (view: string) => void }) {
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    Promise.all([api.facultySections(), api.teachingAllocations()])
      .then(([sectionsResponse, allocationsResponse]) => {
        const sections = new Map((sectionsResponse.sections || []).map((section: any) => [section.id, section]))
        const rows = (allocationsResponse.allocations || [])
          .filter((allocation: any) => allocation.status === 'active' && sections.has(allocation.section_id))
          .map((allocation: any) => ({ ...allocation, sectionData: sections.get(allocation.section_id) }))
        setData({ rows })
      })
      .catch(() => setData({ error: true }))
  }, [])

  if (!data) return <Spinner />
  if (data.error) return <Empty icon="!" text="Your assigned courses could not be loaded." />
  if (!data.rows.length) return <Empty icon="-" text="You do not have any active teaching allocations." />

  return (
    <main className="assess-workspace fade-in">
      <section className="assess-heading"><h1>My Courses &amp; Sections</h1><p>Active teaching allocations assigned to you.</p></section>
      <article className="assess-register">
        <header><h2>Assigned Sections</h2></header>
        <div className="assess-table-wrap"><table className="assess-table">
          <thead><tr><th>Course</th><th>Section</th><th>Academic Year / Term</th><th>Allocation</th><th>Hours / Workload</th><th>Schedule</th><th>Students</th><th>Status</th><th>Open</th></tr></thead>
          <tbody>{data.rows.map((row: any) => {
            const section = row.sectionData
            return <tr key={row.id}>
              <td><b>{row.course_code}</b><span>{row.course_title}</span></td>
              <td>{row.section}</td>
              <td>{row.academic_year}<span>{row.term || 'Term not set'}</span></td>
              <td>{row.allocation_type}{row.is_coordinator && <span>Course coordinator</span>}</td>
              <td>L {hours(row.lecture_hours)} / B {hours(row.lab_hours)} / T {hours(row.tutorial_hours)}<span>Total: {hours(row.workload_units)}</span></td>
              <td>{section.schedule || 'Schedule not set'}<span>{section.room || 'Room not set'}</span></td>
              <td>{section.enrolled || 0}</td>
              <td><em className="status-published">{row.status}</em></td>
              <td><div className="row-actions"><button onClick={() => go('attendance')} type="button">Attendance</button><button onClick={() => go('course_materials')} type="button">Materials</button><button onClick={() => go('assessments')} type="button">Assessments</button><button onClick={() => go('my_schedule')} type="button">Schedule</button></div></td>
            </tr>
          })}</tbody>
        </table></div>
      </article>
    </main>
  )
}


