import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, Kpis } from './kit'

export default function Placements({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.placements().then(setData).catch(() => {}) }, [])
  if (!data) return <Spinner />
  const s = data.summary
  return (
    <div className="fade-in">
      <PageHead title="Placements" sub="Recruiter drives and offers" />
      <Kpis items={[
        { label: 'Total offers', value: s.offers, tone: 'var(--teal)' },
        { label: 'Highest CTC', value: `${s.top_ctc} LPA` },
        { label: 'Drives', value: s.drives },
      ]} />
      <div className="card" style={{ marginTop: 20 }}>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Company</th><th>Role</th><th>CTC (LPA)</th><th>Eligible CGPA</th><th>Date</th><th>Status</th><th>Offers</th></tr></thead>
            <tbody>
              {data.drives.map((d: any) => (
                <tr key={d.id}>
                  <td><b>{d.company}</b></td><td>{d.role}</td><td><b>{d.ctc}</b></td>
                  <td>{d.eligible_cgpa}</td><td>{d.date}</td>
                  <td><span className={`pill s-${d.status}`}>{d.status}</span></td><td>{d.offers}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
