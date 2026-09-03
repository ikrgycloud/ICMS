import { useEffect, useState } from 'react'
import { AcademicSnapshot, StudentSnapshot, WorkforceOverview } from './CampusHeadPlaceholder'

type CampusOverviewTab = 'academic' | 'students' | 'workforce'

const TABS: { key: CampusOverviewTab; label: string }[] = [
  { key: 'academic', label: 'Academic' },
  { key: 'students', label: 'Students' },
  { key: 'workforce', label: 'Workforce' },
]

function tabFromLocation(): CampusOverviewTab {
  const tab = new URLSearchParams(window.location.search).get('tab')
  return TABS.some(item => item.key === tab) ? tab as CampusOverviewTab : 'academic'
}

export default function CampusOverview() {
  const [tab, setTab] = useState<CampusOverviewTab>(tabFromLocation)

  useEffect(() => {
    const onPopState = () => setTab(tabFromLocation())
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  function selectTab(next: CampusOverviewTab) {
    const url = new URL(window.location.href)
    url.searchParams.set('tab', next)
    window.history.pushState({ tab: next }, '', url)
    setTab(next)
  }

  return (
    <div className="fade-in campus-head-page campus-overview-page">
      <header className="campus-workspace-header">
        <div>
          <span className="eyebrow">Campus / Branch Head</span>
          <h1>Campus Overview</h1>
          <p>Academic, student and workforce performance for the campus.</p>
        </div>
        <div className="campus-context" aria-label="Campus context">
          <span>Main Campus</span><span>Office #3</span><span>Campus scope</span>
        </div>
      </header>

      <div className="campus-overview-nav-label">Performance workspace</div>
      <div className="campus-overview-tabs" role="tablist" aria-label="Campus overview sections">
        {TABS.map(item => (
          <button
            key={item.key}
            className={`campus-overview-tab ${tab === item.key ? 'active' : ''}`}
            onClick={() => selectTab(item.key)}
            role="tab"
            aria-selected={tab === item.key}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </div>

      <section className="campus-overview-section" role="tabpanel">
        <h2>{TABS.find(item => item.key === tab)?.label}</h2>
        {tab === 'academic' && <AcademicSnapshot embedded />}
        {tab === 'students' && <StudentSnapshot embedded />}
        {tab === 'workforce' && <WorkforceOverview embedded />}
      </section>
    </div>
  )
}