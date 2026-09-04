import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner } from './kit'

export default function AdminPanel({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.adminUsers().then(setData).catch(() => {}) }, [])
  if (!data) return <Spinner />
  return (
    <div className="fade-in">
      <PageHead title="System administration" sub="Identity & access — reserved to IT / System Admin per the RBAC invariants" />
      <div className="sod-banner">
        <span className="sod-i">⚙</span>
        <div><b>Least privilege.</b> Only IT and System Administrator offices receive system-configuration authority, and every configuration change is itself audited.</div>
      </div>
      <div className="card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Username</th><th>Office</th><th>Role</th><th>Scope</th><th>MFA</th><th>Status</th></tr></thead>
            <tbody>
              {data.users.map((u: any) => (
                <tr key={u.username}>
                  <td className="mono">{u.username}</td><td>#{u.office_n}</td><td>{u.role}</td>
                  <td><span className="tag">{u.scope_level}</span></td>
                  <td>{u.mfa ? <span className="pill s-active">on</span> : <span className="pill s-due">off</span>}</td>
                  <td><span className={`pill s-${u.status}`}>{u.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
