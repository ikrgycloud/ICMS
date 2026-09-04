import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, money, Kpis } from './kit'

export default function Analytics({ user }: { user: any }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.overview().then(setData).catch(() => {}) }, [])
  if (!data) return <Spinner />
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
