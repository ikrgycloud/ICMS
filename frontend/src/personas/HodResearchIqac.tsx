import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Spinner } from '../modules/kit'

const pretty = (value?: string) => String(value || '—').replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase())
const date = (value?: string) => value ? new Date(value).toLocaleDateString() : '—'

export default function HodResearchIqac() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [search, setSearch] = useState('')
  const [projectStatus, setProjectStatus] = useState('all')
  const [faculty, setFaculty] = useState('all')
  const [category, setCategory] = useState('all')
  const [publicationType, setPublicationType] = useState('all')

  const load = async () => {
    setRefreshing(true); setError('')
    try { setData(await api.hodResearchIqac()) }
    catch (caught: any) { setError(caught.message || 'Research monitoring could not be loaded.') }
    finally { setRefreshing(false) }
  }
  useEffect(() => { void load() }, [])

  const projects = data?.research?.projects || []
  const publications = data?.research?.publications || []
  const facultyNames = useMemo(() => [...new Set([...projects, ...publications].map((item: any) => item.faculty_name).filter(Boolean))].sort(), [projects, publications])
  const projectStatuses = useMemo(() => [...new Set(projects.map((item: any) => item.status).filter(Boolean))].sort(), [projects])
  const categories = useMemo(() => [...new Set(projects.map((item: any) => item.category).filter(Boolean))].sort(), [projects])
  const publicationTypes = useMemo(() => [...new Set(publications.map((item: any) => item.publication_type).filter(Boolean))].sort(), [publications])
  const normalizedSearch = search.trim().toLowerCase()
  const filteredProjects = projects.filter((item: any) =>
    (projectStatus === 'all' || item.status === projectStatus) &&
    (faculty === 'all' || item.faculty_name === faculty) &&
    (category === 'all' || item.category === category) &&
    (!normalizedSearch || `${item.title || ''} ${item.faculty_name || ''}`.toLowerCase().includes(normalizedSearch)))
  const filteredPublications = publications.filter((item: any) =>
    (publicationType === 'all' || item.publication_type === publicationType) &&
    (faculty === 'all' || item.faculty_name === faculty) &&
    (!normalizedSearch || `${item.title || ''} ${item.faculty_name || ''}`.toLowerCase().includes(normalizedSearch)))

  if (!data && !error) return <main className="hod-research-page"><Spinner /></main>
  return <main className="hod-research-page fade-in">
    <header className="hod-research-head">
      <div><p>{data?.department?.name || 'Department research scope'}{data?.department?.campus ? ` · ${data.department.campus}` : ''}</p><h1>Research / IQAC</h1><span>Department Research is available as read-only monitoring. IQAC / Quality remains a separately unconfigured capability.</span></div>
      <button className="btn btn-out" type="button" onClick={() => void load()} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh'}</button>
    </header>
    {error && <section className="hod-research-error" role="alert"><b>Research monitoring is unavailable.</b><span>{error}</span><button className="btn btn-out" type="button" onClick={() => void load()}>Try again</button></section>}
    {data && <>
      <section className="hod-research-kpis" aria-label="Department research summary">
        <Metric label="Visible Research Projects" value={data.research?.summary?.projects ?? 0} hint="Authorized department records" />
        <Metric label="Active / Ongoing" value={data.research?.summary?.active_projects ?? 0} hint="Current project states" tone="active" />
        <Metric label="Completed / Closed" value={projects.filter((item: any) => ['completed', 'closed'].includes(item.status)).length} hint="Visible final project states" tone="complete" />
        <Metric label="Published Publications" value={data.research?.summary?.published_publications ?? 0} hint="Published records only" tone="published" />
        <Metric label="Participating Faculty" value={data.research?.summary?.participating_faculty ?? 0} hint="Across visible records" />
      </section>

      <section className="hod-research-register">
        <header><div><p>Department Research · read-only</p><h2>Research Projects</h2></div><small>{filteredProjects.length} of {projects.length} visible</small></header>
        <div className="hod-research-filters">
          <label>Search projects / faculty<input value={search} onChange={event => setSearch(event.target.value)} placeholder="Project title or faculty" /></label>
          <label>Project status<select value={projectStatus} onChange={event => setProjectStatus(event.target.value)}><option value="all">All statuses</option>{projectStatuses.map(item => <option key={item} value={item}>{pretty(item)}</option>)}</select></label>
          <label>Faculty<select value={faculty} onChange={event => setFaculty(event.target.value)}><option value="all">All faculty</option>{facultyNames.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
          <label>Project category<select value={category} onChange={event => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map(item => <option key={item} value={item}>{pretty(item)}</option>)}</select></label>
          <button type="button" className="hod-research-clear" onClick={() => { setSearch(''); setProjectStatus('all'); setFaculty('all'); setCategory('all'); setPublicationType('all') }}>Clear filters</button>
        </div>
        <div className="hod-research-table-wrap"><table><thead><tr><th>Project Title</th><th>Category</th><th>Faculty</th><th>Status</th><th>Start Date</th><th>End Date</th></tr></thead><tbody>
          {filteredProjects.map((item: any) => <tr key={item.id}><td><strong>{item.title || 'Untitled project'}</strong></td><td>{item.category ? pretty(item.category) : '—'}</td><td>{item.faculty_name || '—'}</td><td><span className={`hod-research-status is-${item.status}`}>{pretty(item.status)}</span></td><td>{date(item.start_date)}</td><td>{date(item.expected_end_date)}</td></tr>)}
          {!filteredProjects.length && <tr><td colSpan={6}><div className="hod-research-empty"><strong>{projects.length ? 'No visible projects match these filters.' : 'No department research records available.'}</strong><span>{projects.length ? 'Adjust or clear a filter to see the authorized project register.' : 'Draft, proposed, private, and unowned research records are not included.'}</span></div></td></tr>}
        </tbody></table></div>
      </section>

      <section className="hod-research-register hod-research-publications">
        <header><div><p>Published records only</p><h2>Publications</h2></div><small>{filteredPublications.length} of {publications.length} visible</small></header>
        <div className="hod-research-publication-filter"><label>Publication type<select value={publicationType} onChange={event => setPublicationType(event.target.value)}><option value="all">All publication types</option>{publicationTypes.map(item => <option key={item} value={item}>{pretty(item)}</option>)}</select></label></div>
        <div className="hod-research-table-wrap"><table><thead><tr><th>Publication Title</th><th>Type</th><th>Venue</th><th>Publication Date</th><th>Faculty</th></tr></thead><tbody>
          {filteredPublications.map((item: any) => <tr key={item.id}><td><strong>{item.title || 'Untitled publication'}</strong></td><td>{item.publication_type ? pretty(item.publication_type) : '—'}</td><td>{item.venue || '—'}</td><td>{date(item.publication_date)}</td><td>{item.faculty_name || '—'}</td></tr>)}
          {!filteredPublications.length && <tr><td colSpan={5}><div className="hod-research-empty"><strong>{publications.length ? 'No published records match these filters.' : 'No published department publications are available.'}</strong><span>Unpublished manuscripts and private publication metadata are excluded.</span></div></td></tr>}
        </tbody></table></div>
      </section>

      <section className="hod-iqac-unavailable" aria-label="IQAC and Quality status"><div className="hod-iqac-symbol">IQ</div><div><span>IQAC / Quality</span><h2>Not Configured</h2><p>{data.iqac?.message || 'A department-level IQAC submission and reviewer workflow has not been configured in the authoritative system.'}</p><small>Evidence submission and storage, reviewer routing, return/resubmit, approval history, and a department compliance lifecycle are not available.</small></div></section>
    </>}
  </main>
}

function Metric({ label, value, hint, tone = '' }: { label: string; value: number; hint: string; tone?: string }) {
  return <article className={`hod-research-kpi ${tone}`}><span>{label}</span><strong>{value}</strong><small>{hint}</small></article>
}
