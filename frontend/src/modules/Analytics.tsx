import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, money, Kpis } from './kit'

export default function Analytics({ user }: { user: any }) {
  const [data, setData] = useState<any>(null)
  const [year, setYear] = useState(''), [semester, setSemester] = useState('')
  useEffect(() => { (user.office_n === 4 ? api.principalOverview(year, semester) : api.overview()).then(setData).catch(() => {}) }, [user.office_n, year, semester])
  if (!data) return <Spinner />
  if (user.office_n === 4) {
    const p = data.performance, k = data.kpis
    return <div className="fade-in principal-operations"><PageHead title="Reports & Analytics" sub="Campus-scoped academic and operational reporting." />
      <div className="operations-filter"><label>Academic Year<select className="select" value={year || data.filters.selected_year} onChange={e => setYear(e.target.value)}>{data.filters.academic_years.map((x: string) => <option key={x}>{x}</option>)}</select></label><label>Semester<select className="select" value={semester} onChange={e => setSemester(e.target.value)}><option value="">All Semesters</option>{data.filters.student_semesters.map((x: number) => <option key={x} value={x}>Semester {x}</option>)}</select></label></div>
      <div className="operations-kpis"><Metric label="Students" value={k.students}/><Metric label="Average CGPA" value={p.average_cgpa}/><Metric label="Pass rate" value={p.pass_rate == null ? '—' : `${p.pass_rate}%`}/><Metric label="At risk" value={k.risk_students}/></div>
      <section className="card card-pad"><div className="card-h"><h3>Academic performance</h3><span className="hint">Selected academic year and semester</span></div><div className="grid-3"><Metric label="Distinction" value={p.bands.distinction}/><Metric label="First class" value={p.bands.first}/><Metric label="Second class" value={p.bands.second}/></div></section>
    </div>
  }
  const s = data.stats
  const dept = data.dept_distribution || {}
  const max = Math.max(1, ...Object.values(dept).map(Number))

  return (
    <div className="fade-in">
      <PageHead title="Analytics" sub="Cross-institution metrics" />
      <Kpis items={[
        { label: 'Students', value: s.students }, { label: 'Faculty', value: s.faculty },
        { label: 'Sections', value: s.sections }, { label: 'Offers', value: s.placement_offers },
        { label: 'Fees due', value: money(s.fees_due), tone: 'var(--rose)' },
      ]} />
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-h"><h3>Enrolment by department</h3></div>
        <div className="card-pad">
          {Object.entries(dept).sort((a, b) => Number(b[1]) - Number(a[1])).map(([d, n]) => (
            <div className="bar-row" key={d}>
              <div className="bar-label">{d}</div>
              <div className="bar-track"><div className="bar-fill" style={{ width: `${(Number(n) / max) * 100}%` }} /></div>
              <div className="bar-val">{String(n)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value }: any) { return <div><span>{label}</span><b>{value}</b></div> }
