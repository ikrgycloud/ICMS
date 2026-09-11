import { useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner } from '../modules/kit'

export default function FacultyConditionalView({ kind }: { kind: 'coordination' | 'risk' | 'registrations' }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => {
    const request = kind === 'coordination' ? api.facultyCourseCoordination : kind === 'risk' ? api.facultyAcademicRisk : api.facultyCourseRegistrations
    request().then(setData).catch(() => setData({ denied: true }))
  }, [kind])
  if (!data) return <Spinner />
  const meta = kind === 'coordination'
    ? { title: 'Course Coordination', sub: 'Sections assigned to you for active course coordination.', key: 'sections', columns: ['Course', 'Section', 'Term'], cells: (row: any) => [row.course_code ? `${row.course_code} · ${row.title}` : row.title, row.section, row.term] }
    : kind === 'risk'
      ? { title: 'Academic Risk', sub: 'Advisees who need academic follow-up.', key: 'students', columns: ['Student', 'Roll No.', 'Attendance', 'CGPA', 'Marks average'], cells: (row: any) => [row.name, row.roll_no, row.attendance_pct == null ? '—' : `${row.attendance_pct}%`, Number(row.cgpa || 0).toFixed(2), row.marks_average == null ? '—' : `${row.marks_average}%`] }
      : { title: 'Course Registrations', sub: 'Registration requests from advisees assigned to you.', key: 'registrations', columns: ['Student', 'Roll No.', 'Section', 'Status'], cells: (row: any) => [row.student, row.roll_no, row.section_id, row.status] }
  const rows = data[meta.key] || []
  return <main className="faculty-students fade-in"><section className="faculty-students-heading"><div><h1>{meta.title}</h1><p>{meta.sub}</p></div></section><article className="faculty-student-table-card"><header><div><h2>{meta.title}</h2><p>Access is available only while the relevant assignment is active.</p></div><span>{rows.length} records</span></header><div className="faculty-student-table-wrap"><table><thead><tr>{meta.columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row: any) => <tr key={row.id}>{meta.cells(row).map((cell: any, index: number) => <td key={index}>{cell}</td>)}</tr>)}{!rows.length && <tr><td colSpan={meta.columns.length}>{data.denied ? 'This feature is not available for your current assignment.' : 'No records require your action.'}</td></tr>}</tbody></table></div></article></main>
}
