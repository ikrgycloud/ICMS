import { Modal } from './kit'

export default function EligibilityDetailView({ detail, onClose }: { detail: any; onClose: () => void }) {
  const app = detail.application || {}
  const latest = detail.runs?.[0]
  const checks = (detail.checks || []).filter((item: any) => item.run_id === latest?.id)
  const mandatory = checks.filter((item: any) => !item.quota_id)
  const quotaChecks = checks.filter((item: any) => item.quota_id)
  const passed = checks.filter((item: any) => item.outcome === 'PASS').length
  const failed = checks.filter((item: any) => item.outcome === 'FAIL').length
  const eligible = latest?.outcome === 'ELIGIBLE'
  const pending = !latest || latest.outcome === 'pending'
  const next = detail.next_step || { title: 'Review eligibility', description: 'Check the recorded requirements and continue according to admission policy.', destination: 'Eligibility & Quotas' }
  const formatValue = (value: any) => {
    if (value == null || value === '') return 'Not supplied'
    if (typeof value !== 'object') return String(value)
    return Object.entries(value).map(([key, item]) => `${key.replaceAll('_', ' ')}: ${String(item)}`).join(' | ')
  }
  const checkTable = (rows: any[]) => <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Requirement</th><th>Applicant value</th><th>Decision</th><th>Explanation</th></tr></thead><tbody>{rows.length ? rows.map((item: any, index: number) => <tr key={`${item.rule_id}-${index}`}><td><b>{item.rule?.replaceAll('_', ' ')}</b><br /><span className="hint">Required: {formatValue(item.values?.expected)}</span></td><td>{formatValue(item.values?.observed)}</td><td><b style={{ color: item.outcome === 'PASS' ? 'var(--teal)' : '#b42318' }}>{item.outcome === 'PASS' ? 'Pass' : 'Fail'}</b></td><td>{item.reason || 'No additional explanation recorded.'}</td></tr>) : <tr><td colSpan={4} className="hint">No checks were recorded for this evaluation.</td></tr>}</tbody></table></div>

  return <Modal title={`Eligibility Decision: ${app.application_no || 'Application'}`} onClose={onClose} footer={<button className="btn btn-out" onClick={onClose}>Close</button>}>
    <section style={{ padding: 18, borderRadius: 10, border: `1px solid ${eligible ? 'var(--teal)' : pending ? 'var(--brass)' : '#f0b5ad'}`, background: eligible ? '#edf9f4' : pending ? '#fff8e6' : '#fff1f0', marginBottom: 18 }}>
      <span className="hint">Eligibility decision</span>
      <h2 style={{ margin: '4px 0', color: eligible ? 'var(--teal)' : pending ? '#8a5a00' : '#b42318' }}>{eligible ? 'Eligible for admission' : pending ? 'Evaluation pending' : 'Not eligible'}</h2>
      <p style={{ margin: 0 }}>{eligible ? 'The applicant meets the mandatory rules and at least one applicable quota path.' : pending ? 'No completed eligibility decision is available yet.' : 'One or more mandatory or quota requirements were not met. Review the failed checks below.'}</p>
    </section>

    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10, marginBottom: 18 }}>
      <div className="card-pad" style={{ border: '1px solid var(--line)' }}><span className="hint">Checks passed</span><h3 style={{ margin: '4px 0' }}>{passed}</h3></div>
      <div className="card-pad" style={{ border: '1px solid var(--line)' }}><span className="hint">Checks failed</span><h3 style={{ margin: '4px 0' }}>{failed}</h3></div>
      <div className="card-pad" style={{ border: '1px solid var(--line)' }}><span className="hint">Application status</span><h3 style={{ margin: '4px 0', fontSize: 15 }}>{app.status?.replaceAll('_', ' ') || 'Pending'}</h3></div>
    </div>

    <section className="card-pad" style={{ border: '1px solid var(--brass)', borderLeftWidth: 4, marginBottom: 18 }}>
      <span className="hint">What to do next</span>
      <h3 style={{ margin: '5px 0' }}>{next.title}</h3>
      <p style={{ margin: 0 }}>{next.description}</p>
      <p className="hint" style={{ marginBottom: 0 }}>Continue in: <b>{next.destination}</b></p>
    </section>

    <h4>Applicant summary</h4>
    <p><b>{app.applicant_name}</b> · {app.program || 'Programme not set'} · {app.campus || 'Campus not set'}</p>
    <p className="hint">Latest evaluation: {latest?.completed_at ? latest.completed_at.slice(0, 16) : 'Not completed'}</p>
    <h4>Mandatory requirements</h4>{checkTable(mandatory)}
    <h4>Quota requirements</h4>{checkTable(quotaChecks)}
  </Modal>
}

function LegacyEligibilityDetailView({ detail, onClose }: { detail: any; onClose: () => void }) {
  const app = detail.application || {}
  const latest = detail.runs?.[0]
  const latestChecks = (detail.checks || []).filter((item: any) => item.run_id === latest?.id)
  const mandatory = latestChecks.filter((item: any) => !item.quota_id)
  const quotaGroups = latestChecks.filter((item: any) => item.quota_id).reduce((groups: Record<string, any[]>, item: any) => {
    ;(groups[item.quota_id] = groups[item.quota_id] || []).push(item)
    return groups
  }, {})
  const resultTable = (rows: any[]) => <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Rule</th><th>Configured requirement</th><th>Applicant value</th><th>Result</th><th>Decision reason</th></tr></thead><tbody>{rows.length ? rows.map((item: any, index: number) => <tr key={`${item.rule_id}-${index}`}><td>{item.rule} <span className="hint">v{item.rule_version}</span></td><td>{JSON.stringify(item.values?.expected || {})}</td><td>{item.values?.observed == null || item.values?.observed === '' ? 'Not supplied' : String(item.values.observed)}</td><td><b>{item.outcome}</b></td><td>{item.reason}</td></tr>) : <tr><td colSpan={5} className="hint">No checks are available yet. Run eligibility evaluation first.</td></tr>}</tbody></table></div>

  return <Modal title={`Eligibility Detail: ${app.application_no || 'Application'}`} onClose={onClose} footer={<button className="btn btn-out" onClick={onClose}>Close</button>}>
    <h4>Applicant and Application</h4>
    <p><b>{app.applicant_name}</b> · {app.program} · {app.cycle} · {app.campus}</p>
    <p>Status: <b>{app.status}</b> · Version {app.status_version}</p>

    <h4>Profile and Preferences</h4>
    <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Profile field</th><th>Value</th></tr></thead><tbody>{Object.entries(app.profile || {}).length ? Object.entries(app.profile || {}).map(([key, value]) => <tr key={key}><td>{key.replaceAll('_', ' ')}</td><td>{String(value)}</td></tr>) : <tr><td colSpan={2} className="hint">No profile data supplied.</td></tr>}</tbody></table></div>
    <p className="hint">Preferences: {(app.preferences || []).map((item: any) => `#${item.rank} ${item.program}`).join(' · ') || 'None'}</p>

    <h4>Document Verification</h4>
    <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Document</th><th>File</th><th>Verification status</th></tr></thead><tbody>{(app.documents || []).length ? app.documents.map((item: any) => <tr key={`${item.type}-${item.file_name}`}><td>{item.type}</td><td>{item.file_name}</td><td><b>{item.status || 'PENDING'}</b></td></tr>) : <tr><td colSpan={3} className="hint">No documents uploaded.</td></tr>}</tbody></table></div>

    <h4>Latest Evaluation</h4>
    <p><b>{latest?.outcome || 'PENDING'}</b>{latest?.completed_at ? ` · completed ${latest.completed_at.slice(0, 16)}` : ''}</p>
    <h4>Mandatory Eligibility Checks</h4>{resultTable(mandatory)}
    <h4>Quota Eligibility Checks</h4>{Object.values(quotaGroups).length ? Object.values(quotaGroups).map((rows: any) => <div key={rows[0].quota_id}><p><b>{rows[0].quota?.name || 'Quota'} ({rows[0].quota?.code || rows[0].quota_id})</b></p>{resultTable(rows)}</div>) : <p className="hint">No quota-specific checks were run.</p>}

    <h4>Evaluation History</h4>
    <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Result</th><th>Started</th><th>Completed</th><th>Officer</th></tr></thead><tbody>{(detail.runs || []).length ? detail.runs.map((run: any) => <tr key={run.id}><td><b>{run.outcome}</b></td><td>{run.started_at?.slice(0, 16)}</td><td>{run.completed_at?.slice(0, 16) || 'In progress'}</td><td>{run.actor_id || 'System'}</td></tr>) : <tr><td colSpan={4} className="hint">No eligibility evaluation has been run.</td></tr>}</tbody></table></div>
  </Modal>
}
