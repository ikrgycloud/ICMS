import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, money } from './kit'

export default function Research({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.research().then(setData).catch(() => {}) }, [])
  if (!data) return <Spinner />
  return (
    <div className="fade-in">
      <PageHead title="Research & grants" sub={`${data.projects.length} projects · ${money(data.total_grants)} in sanctioned grants`} />
      <div className="card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Project</th><th>Principal Investigator</th><th>Dept</th><th>Agency</th><th>Grant</th><th>Status</th></tr></thead>
            <tbody>
              {data.projects.map((p: any) => (
                <tr key={p.id}>
                  <td><b>{p.title}</b></td><td>{p.pi}</td><td>{p.dept}</td>
                  <td><span className="tag">{p.agency}</span></td><td>{money(p.grant)}</td>
                  <td><span className={`pill s-${p.status}`}>{p.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
