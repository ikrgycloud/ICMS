import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Spinner, money } from './kit'

const pretty = (value: string) => value.replace(/[_-]/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase())
const normalized = (value: unknown) => String(value || 'active').toLowerCase()

function projectProgress(status: string) {
  if (status.includes('complete')) return 100
  if (status.includes('active') || status.includes('approved')) return 72
  if (status.includes('review')) return 52
  if (status.includes('pending') || status.includes('proposal')) return 32
  return 45
}

function statusClass(status: string) {
  if (status.includes('complete') || status.includes('active') || status.includes('approved')) return 'is-active'
  if (status.includes('review') || status.includes('pending') || status.includes('proposal')) return 'is-review'
  return 'is-risk'
}

export default function Research({ caps: _caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  const [status, setStatus] = useState('all')
  const [department, setDepartment] = useState('all')
  const [agency, setAgency] = useState('all')
  const [query, setQuery] = useState('')

  useEffect(() => { api.research().then(setData).catch((error: Error) => setData({ error: error.message })) }, [])

  const projects = data?.projects || []
  const statuses = useMemo(() => Array.from(new Set(projects.map((project: any) => normalized(project.status)))), [projects]) as string[]
  const departments = useMemo(() => Array.from(new Set(projects.map((project: any) => project.dept).filter(Boolean))), [projects]) as string[]
  const agencies = useMemo(() => Array.from(new Set(projects.map((project: any) => project.agency).filter(Boolean))), [projects]) as string[]
  const filtered = useMemo(() => {
    const search = query.trim().toLowerCase()
    return projects.filter((project: any) => {
      const projectStatus = normalized(project.status)
      const matchesStatus = status === 'all' || projectStatus === status
      const matchesDepartment = department === 'all' || project.dept === department
      const matchesAgency = agency === 'all' || project.agency === agency
      const haystack = [project.title, project.pi, project.dept, project.agency, project.status].join(' ').toLowerCase()
      return matchesStatus && matchesDepartment && matchesAgency && (!search || haystack.includes(search))
    })
  }, [projects, status, department, agency, query])

  if (!data) return <Spinner />
  if (data.error) return <div className="empty">Research &amp; Guidance is available only when you have an active research responsibility.</div>

  const activeProjects = projects.filter((project: any) => {
    const value = normalized(project.status)
    return value.includes('active') || value.includes('approved')
  }).length
  const reviewProjects = projects.filter((project: any) => {
    const value = normalized(project.status)
    return value.includes('review') || value.includes('pending') || value.includes('proposal')
  }).length
  const completedProjects = projects.filter((project: any) => normalized(project.status).includes('complete')).length
  const attentionProjects = Math.max(0, projects.length - activeProjects - completedProjects)
  const reviewQueue = filtered.filter((project: any) => !normalized(project.status).includes('complete')).slice(0, 4)

  const metrics = [
    ['▣', 'Total Projects', projects.length, 'Active & completed', 'violet'],
    ['◉', 'Total Funding', money(data.total_grants || 0), 'Sanctioned grants', 'green'],
    ['✓', 'Ongoing Projects', activeProjects, 'In progress', 'purple'],
    ['⚑', 'Proposed Projects', reviewProjects, 'Awaiting approval', 'orange'],
    ['!', 'Completed Projects', completedProjects, 'Successfully completed', 'red'],
  ]

  return <div className="research-guidance fade-in">
    <div className="rg-breadcrumb">Professor Office <span>/</span> Research <span>/</span> <strong>Research &amp; Grants</strong></div>
    <div className="rg-heading">
      <div>
        <h1>Research &amp; Grants</h1>
        <p>Track your associated research projects, grants, funding, and compliance in one place.</p>
      </div>
      <div className="rg-context">Research workspace</div>
    </div>

    <section className="rg-metrics" aria-label="Research summary">
      {metrics.map(([icon, label, value, caption, tone]) => <article className="rg-metric" key={String(label)}>
        <span className={`rg-metric-icon ${tone}`}>{icon}</span>
        <div><small>{label}</small><strong>{value}</strong><em>{caption}</em></div>
      </article>)}
    </section>

    <div className="rg-main">
        <section className="rg-filters card">
          <label>Project status<select value={status} onChange={event => setStatus(event.target.value)}><option value="all">All statuses</option>{statuses.map(value => <option key={value} value={value}>{pretty(value)}</option>)}</select></label>
          <label>Department<select value={department} onChange={event => setDepartment(event.target.value)}><option value="all">All departments</option>{departments.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
          <label>Funding agency<select value={agency} onChange={event => setAgency(event.target.value)}><option value="all">All agencies</option>{agencies.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
          <label className="rg-search">Search projects<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search project, PI, agency..." /></label>
          <div className="rg-result-count">{filtered.length} project{filtered.length === 1 ? '' : 's'}</div>
        </section>

        <section className="card rg-table-card">
          <div className="rg-section-title"><div><h2>Projects Overview</h2><p>Projects associated with your active research responsibilities</p></div></div>
          <div className="tbl-scroll"><table className="tbl rg-table">
            <colgroup><col className="rg-col-project" /><col className="rg-col-pi" /><col className="rg-col-dept" /><col className="rg-col-agency" /><col className="rg-col-grant" /><col className="rg-col-progress" /><col className="rg-col-status" /></colgroup>
            <thead><tr><th>Project / topic</th><th>Principal investigator</th><th>Department</th><th>Funding agency</th><th>Grant</th><th>Progress</th><th>Status</th></tr></thead>
            <tbody>{filtered.map((project: any) => {
              const currentStatus = normalized(project.status)
              const progress = projectProgress(currentStatus)
              return <tr key={project.id}>
                <td><strong>{project.title}</strong><span className="rg-id">Project #{project.id}</span></td>
                <td>{project.pi || '—'}</td><td>{project.dept || '—'}</td><td>{project.agency || '—'}</td>
                <td><strong>{money(project.grant || 0)}</strong></td>
                <td><div className="rg-progress"><span>{progress}%</span><i><b style={{ width: `${progress}%` }} /></i></div></td>
                <td><span className={`rg-status ${statusClass(currentStatus)}`}>{pretty(currentStatus)}</span></td>
              </tr>
            })}</tbody>
          </table></div>
          {!filtered.length && <div className="rg-empty">No projects match these filters.</div>}
        </section>
        <div className="rg-note"><b>ⓘ</b><span>This section lists research projects associated with your active responsibilities, including funded, ongoing, proposed, and completed projects.</span></div>
      </div>
  </div>
}
