import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, Kpis, PageHead, Pill, Spinner } from './kit'

type Vacancy = {
  id: string
  title: string
  dept?: string
  kind?: string
  openings?: number
  status?: string
}

/**
 * Principal-facing recruitment oversight.  This intentionally does not reuse
 * the HR workspace: HR owns operational leave/payroll actions while the
 * Principal needs a read-only, vacancy-specific governance view.
 */
export default function PrincipalRecruitment() {
  const [data, setData] = useState<{ jobs?: Vacancy[] } | null>(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')

  async function load() {
    setError('')
    try {
      setData(await api.jobs())
    } catch (e: any) {
      setError(e?.message || 'Recruitment data could not be loaded. Please try again.')
      setData({ jobs: [] })
    }
  }

  useEffect(() => { void load() }, [])

  const jobs = data?.jobs || []
  const statuses = useMemo(() => Array.from(new Set(jobs.map(job => String(job.status || 'open')))).sort(), [jobs])
  const visible = useMemo(() => jobs.filter(job => {
    const needle = query.trim().toLowerCase()
    const matchesQuery = !needle || [job.title, job.dept, job.kind].some(value => String(value || '').toLowerCase().includes(needle))
    return matchesQuery && (status === 'all' || String(job.status || 'open') === status)
  }), [jobs, query, status])
  const open = jobs.filter(job => String(job.status || 'open').toLowerCase() === 'open')
  const vacancies = open.reduce((sum, job) => sum + Number(job.openings || 0), 0)
  const departments = new Set(open.map(job => job.dept).filter(Boolean)).size

  if (!data) return <Spinner />

  return (
    <main className="principal-recruitment fade-in">
      <PageHead
        title="Recruitment & Vacancies"
        sub="Institutional vacancy oversight. Recruitment operations remain with Human Resources; approval tasks appear in My Approvals."
        right={<button className="btn btn-secondary" onClick={() => void load()}>Refresh</button>}
      />

      <Kpis items={[
        { label: 'Open positions', value: open.length, tone: '#8f1736' },
        { label: 'Approved vacancies', value: vacancies, tone: '#1765cb' },
        { label: 'Departments hiring', value: departments, tone: '#087b5f' },
        { label: 'All postings', value: jobs.length },
      ]} />

      {error && <div className="principal-recruitment-error" role="alert">
        <span>{error}</span><button className="btn btn-sm btn-secondary" onClick={() => void load()}>Try again</button>
      </div>}

      <section className="card principal-recruitment-card">
        <header className="principal-recruitment-head">
          <div><span>VACANCY REGISTER</span><h2>Current recruitment positions</h2><p>Review active staffing demand and recruitment progress without exposing HR leave or payroll records.</p></div>
          <b>{visible.length} shown</b>
        </header>
        <div className="principal-recruitment-filters">
          <label><span>Search position</span><input className="inp" value={query} onChange={event => setQuery(event.target.value)} placeholder="Title, department, or type" /></label>
          <label><span>Posting status</span><select className="select" value={status} onChange={event => setStatus(event.target.value)}><option value="all">All statuses</option>{statuses.map(value => <option key={value} value={value}>{value.replace(/_/g, ' ')}</option>)}</select></label>
          {(query || status !== 'all') && <button className="btn btn-secondary" onClick={() => { setQuery(''); setStatus('all') }}>Clear filters</button>}
        </div>
        {visible.length === 0 ? <Empty icon="◌" text={jobs.length ? 'No vacancies match the selected filters.' : 'No recruitment vacancies are currently recorded.'} /> : (
          <div className="tbl-scroll"><table className="tbl principal-recruitment-table"><thead><tr><th>Position</th><th>Department</th><th>Employment type</th><th>Vacancies</th><th>Posting status</th></tr></thead><tbody>
            {visible.map(job => <tr key={job.id}><td><b>{job.title || 'Untitled position'}</b><small>Posting #{job.id}</small></td><td>{job.dept || 'Not specified'}</td><td><span className="tag">{job.kind || 'Not specified'}</span></td><td><b>{Number(job.openings || 0)}</b></td><td><Pill s={job.status || 'open'} /></td></tr>)}
          </tbody></table></div>
        )}
      </section>
    </main>
  )
}
