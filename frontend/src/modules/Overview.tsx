import { api } from '../api'
import { PageHead, Kpis, Spinner, money, useLoad, Empty } from './kit'
import ChairmanOverview from './ChairmanOverview'
import PrincipalDashboard from './PrincipalDashboard'

export default function Overview({ user, go }: { user: any; go: (v: string) => void }) {
  if (user.office_n === 1) return <ChairmanOverview go={go} />
  if (user.office_n === 4) return <PrincipalDashboard user={user} go={go} />
  if (user.office_n === 22) return <FinanceManagerOverview user={user} go={go} />
  const [data, loading] = useLoad<any>(() => api.overview())
  if (loading || !data) return <Spinner />
  const s = data.stats
  const dept = data.dept_distribution || {}
  const maxDept = Math.max(1, ...Object.values(dept).map(Number))

  const quick: Record<string, { label: string; to: string }[]> = {}
  const links = (user.modules_keys || []) as string[]

  return (
    <div className="fade-in">
      <PageHead title={`Welcome, ${user.name?.split(' ')[0] || 'Officer'}`}
        sub={`${user.office} · Level ${user.level} · acting as ${user.active_role}`} />

      <Kpis items={[
        { label: 'Students', value: s.students },
        { label: 'Faculty', value: s.faculty },
        { label: 'Courses', value: s.courses },
        { label: 'Live sections', value: s.sections },
        { label: 'Fees outstanding', value: money(s.fees_due), tone: 'var(--rose)' },
        { label: 'Open grievances', value: s.open_complaints, tone: s.open_complaints ? 'var(--brass)' : undefined },
      ]} />

      <div className="grid-2" style={{ marginTop: 22 }}>
        <div className="card">
          <div className="card-h"><h3>Students by department</h3><span className="hint">live</span></div>
          <div className="card-pad">
            {Object.keys(dept).length === 0 && <div className="empty">No data</div>}
            {Object.entries(dept).sort((a, b) => Number(b[1]) - Number(a[1])).map(([d, n]) => (
              <div className="bar-row" key={d}>
                <div className="bar-label">{d}</div>
                <div className="bar-track"><div className="bar-fill" style={{ width: `${(Number(n) / maxDept) * 100}%` }} /></div>
                <div className="bar-val">{String(n)}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-h"><h3>Operational snapshot</h3></div>
          <div className="card-pad">
            <div className="snap"><span>Admission applications in pipeline</span><b>{s.applications}</b></div>
            <div className="snap"><span>Ongoing research projects</span><b>{s.projects}</b></div>
            <div className="snap"><span>Pending leave requests</span><b>{s.pending_leave}</b></div>
            <div className="snap"><span>Placement offers made</span><b>{s.placement_offers}</b></div>
            <div className="snap"><span>Library titles</span><b>{s.books}</b></div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 22 }}>
        <div className="card-h"><h3>Your workspace</h3><span className="hint">role-differentiated</span></div>
        <div className="card-pad">
          <p style={{ color: 'var(--muted)', marginBottom: 14, lineHeight: 1.6 }}>
            The modules in your sidebar and the actions you can take are computed from your office
            ({user.office}), your active role ({user.active_role}), organizational scope ({user.scope_level}),
            and the authority matrix — evaluated live on every action and written to the immutable audit log.
            Use the role switcher (top-right) to see how a different internal role changes what you can do.
          </p>
          <div className="chips">
            {(user.functionalities || []).slice(0, 8).map((f: string, i: number) => (
              <span className="chip" key={i}>{f}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function FinanceManagerOverview({ user, go }: { user: any; go: (v: string) => void }) {
  const [data, loading] = useLoad<any>(() => api.invoices())
  if (loading || !data) return <Spinner />
  const summary = data.summary || {}
  const due = (data.invoices || []).filter((invoice: any) => invoice.balance > 0)
  const latestPayments = (data.payments || []).slice(0, 6)
  const collectionRate = Math.round(100 * (summary.total_collected || 0) / (summary.total_billed || 1))

  return <div className="fade-in finance-overview">
    <PageHead title="Finance overview" sub={`Welcome, ${user.name?.split(' ')[0] || 'Finance Manager'}. Monitor fee collection and payment activity.`} />
    <section className="finance-overview-hero">
      <div><span>Collections recorded</span><strong>{money(summary.total_collected)}</strong><small>From confirmed ICMS payment records</small></div>
      <div className="finance-overview-rate"><span>Collection rate</span><b>{collectionRate}%</b><button onClick={() => go('finance')}>Open finance workspace →</button></div>
    </section>
    <div className="finance-overview-kpis">
      <div><span>Total billed</span><b>{money(summary.total_billed)}</b></div>
      <div className="due"><span>Outstanding</span><b>{money(summary.outstanding)}</b></div>
      <div><span>Open invoices</span><b>{due.length}</b></div>
      <div><span>Payments recorded</span><b>{(data.payments || []).length}</b></div>
    </div>
    <div className="finance-overview-grid">
      <section className="card finance-overview-card"><div className="card-h"><div><h3>Recent payments</h3><span className="hint">Latest database entries</span></div><button className="btn btn-sm btn-out" onClick={() => go('finance')}>View all</button></div><div className="card-pad finance-activity-list">{latestPayments.length ? latestPayments.map((payment:any) => <div className="finance-activity" key={payment.id}><div><b>{payment.name || 'Student payment'}</b><small>{payment.roll_no} · {payment.reference || 'No reference'}</small></div><span><b>{money(payment.amount)}</b><small>{payment.method}</small></span></div>) : <Empty text="No payment records yet." />}</div></section>
      <section className="card finance-overview-card"><div className="card-h"><div><h3>Collection follow-up</h3><span className="hint">Invoices with a balance</span></div><button className="btn btn-sm btn-out" onClick={() => go('finance')}>View invoices</button></div><div className="card-pad finance-activity-list">{due.slice(0, 6).map((invoice:any) => <div className="finance-activity" key={invoice.id}><div><b>{invoice.name}</b><small>{invoice.roll_no} · {invoice.term}</small></div><span className="finance-due"><b>{money(invoice.balance)}</b><small>outstanding</small></span></div>)}{!due.length && <Empty text="All invoices are settled." />}</div></section>
    </div>
  </div>
}
