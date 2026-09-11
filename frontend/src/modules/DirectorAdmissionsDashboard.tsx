import { api } from '../api'
import { PageHead, Spinner, useLoad } from './kit'

const stage = (apps: any[], states: string[]) => apps.filter(x => states.includes(x.current_status)).length

export default function DirectorAdmissionsDashboard({ user, go }: { user: any; go: (view: string) => void }) {
  const [data, loading] = useLoad<any>(() => Promise.all([api.applications(), api.admissionDirectorMonitoring(), api.admissionPhase5Status()]).then(([applications, monitoring, phase5]) => ({ applications: applications.applications || [], monitoring, phase5: phase5.applications || [] })))
  if (loading || !data) return <Spinner />
  const apps = data.applications as any[]
  const monitoring = data.monitoring || { seat_pools: [], offers: [] }
  const activeSeats = (monitoring.seat_pools || []).reduce((n: number, row: any) => n + Number(row.active || 0), 0)
  const availableSeats = (monitoring.seat_pools || []).reduce((n: number, row: any) => n + Number(row.available || 0), 0)
  const offered = stage(apps, ['OFFERED']), accepted = stage(apps, ['OFFER_ACCEPTED'])
  const offerPending = stage(apps, ['OFFER_RECOMMENDATION_PENDING', 'OFFER_APPROVAL_PENDING'])
  const rows = [
    ['Applications received', stage(apps, ['SUBMITTED', 'RESUBMITTED', 'REVIEW_IN_PROGRESS']), 'director_review'],
    ['Document & eligibility', stage(apps, ['DOCUMENT_VERIFIED', 'ELIGIBILITY_PENDING', 'ELIGIBLE']), 'director_eligibility'],
    ['Assessment & counselling', stage(apps, ['ASSESSMENT_PENDING', 'ASSESSMENT_QUALIFIED', 'COUNSELLING_PENDING']), 'director_assessments'],
    ['Allocation & waitlist', stage(apps, ['ALLOCATION_PENDING', 'ALLOCATED', 'WAITLISTED']), 'director_allocation'],
    ['Offers accepted', accepted, 'director_offers'],
    ['Finance cleared', stage(apps, ['FINANCE_CLEARED', 'FINAL_APPROVAL_PENDING', 'READY_TO_ADMIT', 'ENROLLED']), 'director_finance'],
    ['Ready / enrolled', stage(apps, ['READY_TO_ADMIT', 'ENROLLED']), 'director_ready'],
  ] as const
  const max = Math.max(1, ...rows.map(x => x[1]))
  return <div className="fade-in director-dashboard">
    <PageHead title="Admissions Command Center" sub="One workspace for the complete applicant-to-enrollment journey" />
    <section className="director-hero">
      <div><span className="eyebrow">LIVE ADMISSIONS OPERATIONS</span><h2>Move every applicant forward with confidence.</h2><p>From review and eligibility to offers, finance, and enrollment—every stage is linked, governed, and visible here.</p></div>
      <div className="hero-actions"><button className="btn btn-brass" onClick={() => go('director_review')}>Open Review Queue</button><button className="btn btn-out" onClick={() => go('director_final_approval')}>Approval Inbox</button></div>
    </section>
    <div className="director-kpis">
      <Metric label="In active pipeline" value={apps.filter(x => !['ENROLLED', 'INELIGIBLE', 'OFFER_DECLINED', 'OFFER_EXPIRED'].includes(x.current_status)).length} note="Across all active admissions stages" />
      <Metric label="Awaiting review" value={stage(apps, ['SUBMITTED', 'RESUBMITTED', 'REVIEW_IN_PROGRESS', 'CORRECTION_REQUIRED'])} note="Review, correction and documents" tone="#c7902d" />
      <Metric label="Seats committed" value={activeSeats} note={`${availableSeats} seats currently available`} tone="#167d70" />
      <Metric label="Offers awaiting response" value={offered} note={`${offerPending} recommendation / approval actions pending`} tone="#6b4ea8" />
      <Metric label="Offers accepted" value={accepted} note="Applicants who accepted their allocated seat" tone="#6b4ea8" />
      <Metric label="Ready to enroll" value={stage(apps, ['READY_TO_ADMIT'])} note={`${stage(apps, ['ENROLLED'])} already enrolled`} tone="#9d2330" />
    </div>
    <div className="grid-2" style={{ marginTop: 20 }}>
      <section className="card"><div className="card-h"><h3>Admission journey</h3><span className="hint">live workflow health</span></div><div className="card-pad">{rows.map(([label, value, target]) => <button className="journey-row" key={label} onClick={() => go(target)}><span>{label}</span><div className="journey-track"><i style={{ width: `${(Number(value) / max) * 100}%` }} /></div><b>{value}</b><em>›</em></button>)}</div></section>
      <section className="card"><div className="card-h"><h3>Control room</h3><span className="hint">priority workspaces</span></div><div className="card-pad control-grid"><Action title="Document verification" text="Verify documents and resolve corrections" go={() => go('director_document_verification')} /><Action title="Merit & allocation" text="Assess, rank, allocate and manage waitlist" go={() => go('director_merit')} /><Action title="Offers & approvals" text="Recommend, approve, issue and monitor offers" go={() => go('director_recommendations')} /><Action title="Final admission" text="Review readiness and complete enrollment handoff" go={() => go('director_ready')} /></div></section>
    </div>
    <section className="card" style={{ marginTop: 20 }}><div className="card-h"><h3>Seat capacity at a glance</h3><button className="linkish" onClick={() => go('director_seat_pools')}>Open seat management</button></div><div className="card-pad"><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Programme / Campus</th><th>Quota</th><th>Capacity</th><th>Committed</th><th>Available</th><th>Waitlist</th></tr></thead><tbody>{(monitoring.seat_pools || []).map((pool: any) => <tr key={pool.id}><td>{pool.program}<div className="hint">{pool.campus}</div></td><td>{pool.quota}</td><td>{pool.capacity}</td><td>{pool.active}</td><td><b>{pool.available}</b></td><td>{pool.waitlisted}</td></tr>)}</tbody></table></div></div></section>
  </div>
}

function Metric({ label, value, note, tone = '#a51f32' }: any) { return <div className="director-metric" style={{ borderTopColor: tone }}><span>{label}</span><b>{value}</b><small>{note}</small></div> }
function Action({ title, text, go }: any) { return <button className="director-action" onClick={go}><b>{title}</b><span>{text}</span><i>Open →</i></button> }
