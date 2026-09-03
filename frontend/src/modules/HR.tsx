import { useEffect, useState } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast } from './kit'

export default function HR({ caps = {}, principalView }: { caps?: any; principalView?: 'leave' | 'recruitment' }) {
  const [tab, setTab] = useState<'leave' | 'jobs'>(principalView === 'recruitment' ? 'jobs' : 'leave')
  const [leave, setLeave] = useState<any>(null), [jobs, setJobs] = useState<any>(null), [decision, setDecision] = useState<any>(null), [error, setError] = useState(''), [actingId, setActingId] = useState('')
  const isPrincipalView = Boolean(principalView)
  function load() { setError(''); api.leave().then(setLeave).catch(() => setError('Unable to load leave requests.')); api.jobs().then(setJobs).catch(() => setError('Unable to load recruitment vacancies.')) }
  useEffect(load, [])
  async function decide(id: string, action: string) { setActingId(id); try { const response = await api.decideLeave(id, action); setDecision({ ...response.decision, reason: `Leave request ${response.status} successfully.` }); load() } catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message || `Unable to ${action} this leave request.` }) } finally { setActingId('') } }
  const activeTab = principalView === 'recruitment' ? 'jobs' : principalView === 'leave' ? 'leave' : tab
  if (!leave && !jobs && !error) return <Spinner />
  if (!leave && !jobs) return <div className="empty-state"><h3>Unable to load human resources data.</h3><button className="btn btn-crimson" onClick={load}>Retry</button></div>
  const leaveRows = leave?.leave || [], jobRows = jobs?.jobs || []
  const title = activeTab === 'leave' ? (isPrincipalView ? 'Leave' : 'Human Resources') : 'Recruitment & Vacancies'
  const subtitle = activeTab === 'leave' ? 'Review staff leave requests and record workflow decisions.' : 'Review current academic and operational vacancies.'
  return <div className={`fade-in principal-operations principal-hr ${isPrincipalView ? 'principal-hr-focused' : ''}`}>
    <PageHead title={title} sub={subtitle} right={isPrincipalView ? <span className="hr-status"><i />{activeTab === 'leave' ? `${leaveRows.length} requests` : `${jobRows.length} vacancies`}</span> : undefined} />
    {!isPrincipalView && <div className="hr-tabs"><button className={activeTab === 'leave' ? 'active' : ''} onClick={() => setTab('leave')}>Leave requests</button><button className={activeTab === 'jobs' ? 'active' : ''} onClick={() => setTab('jobs')}>Recruitment & vacancies</button></div>}
    {error && <div className="hr-error">{error}<button className="btn btn-out" onClick={load}>Retry</button></div>}
    {activeTab === 'leave' && <section className="card hr-card"><div className="hr-card-head"><div><span>Leave register</span><h3>Staff leave requests</h3></div><b>{leaveRows.length} records</b></div><div className="tbl-scroll"><table className="tbl hr-table"><thead><tr><th>Staff</th><th>Leave type</th><th>Dates</th><th>Days</th><th>Reason</th><th>Status</th><th>Decision</th></tr></thead><tbody>{leaveRows.map((row: any) => <tr key={row.id}><td><b>{row.staff}</b></td><td><span className="hr-kind">{row.kind}</span></td><td>{row.from} → {row.to}</td><td>{row.days}</td><td className="hr-reason">{row.reason}</td><td><span className={`pill s-${row.status}`}>{row.status}</span></td><td>{row.status === 'pending' ? <div className="row-actions"><button className="btn btn-sm btn-crimson" disabled={!leave?.can_approve || actingId === row.id} onClick={() => decide(row.id, 'approve')}>{actingId === row.id ? 'Approving...' : 'Approve'}</button><button className="btn btn-sm btn-out" disabled={!leave?.can_approve || actingId === row.id} onClick={() => decide(row.id, 'reject')}>{actingId === row.id ? 'Rejecting...' : 'Reject'}</button></div> : <span className="hint">Closed</span>}</td></tr>)}</tbody></table>{!leaveRows.length && <div className="principal-empty"><b>No leave requests found.</b><p>New staff requests will appear here.</p></div>}</div></section>}
    {activeTab === 'jobs' && <section className="card hr-card"><div className="hr-card-head"><div><span>Recruitment register</span><h3>Open vacancies</h3></div><b>{jobRows.length} records</b></div><div className="tbl-scroll"><table className="tbl hr-table"><thead><tr><th>Role / Vacancy</th><th>Department</th><th>Employment type</th><th>Openings</th><th>Status</th></tr></thead><tbody>{jobRows.map((row: any) => <tr key={row.id}><td><b>{row.title}</b></td><td>{row.dept}</td><td><span className="hr-kind">{row.kind}</span></td><td>{row.openings}</td><td><span className={`pill s-${row.status}`}>{row.status}</span></td></tr>)}</tbody></table>{!jobRows.length && <div className="principal-empty"><b>No recruitment vacancies found.</b><p>Open positions will appear here when available.</p></div>}</div></section>}
    {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
  </div>
}
