import { api } from '../api'
import { PageHead, Kpis, Spinner, money, useLoad } from './kit'
import ChairmanOverview from './ChairmanOverview'
import PrincipalDashboard from './PrincipalDashboard'
import { CampusHeadDashboard } from './CampusHeadPlaceholder'

export default function Overview({ user, go }: { user: any; go: (v: string) => void }) {
  if (user.office_n === 1) return <ChairmanOverview go={go} />
  if (user.office_n === 3) return <CampusHeadDashboard user={user} go={go} />
  if (user.office_n === 4) return <PrincipalDashboard user={user} go={go} />
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
