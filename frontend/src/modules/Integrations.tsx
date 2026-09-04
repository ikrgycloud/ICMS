import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast } from './kit'

const ICONS: Record<string, string> = {
  Identity: '🔐', Academics: '🎓', Finance: '₹', Communications: '✉',
  Library: '📖', Operations: '🛠', HR: '👥', Analytics: '📊', Governance: '🏛',
}

export default function Integrations({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  const [toast, setToast] = useState<any>(null)

  function load() { api.integrations().then(setData).catch(() => {}) }
  useEffect(() => { load() }, [])

  async function toggle(key: string) {
    try { await api.toggleIntegration(key); setToast({ outcome: 'ALLOW', reason: 'Connector state updated' }); load() }
    catch (e: any) { setToast({ outcome: 'DENY', reason: e.message }) }
  }
  async function sync(key: string) {
    try { await api.syncIntegration(key); setToast({ outcome: 'ALLOW', reason: 'Sync triggered' }); load() }
    catch (e: any) { setToast({ outcome: 'DENY', reason: e.message }) }
  }

  if (!data) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead title="Integrations" sub="External systems connected to ICMS — identity, LMS, payments, communications, library federation and more." />

      <div className="kpi-row" style={{ marginBottom: 24 }}>
        <div className="kpi"><div className="kpi-v">{data.summary.total}</div><div className="kpi-l">Connectors</div></div>
        <div className="kpi"><div className="kpi-v" style={{ color: 'var(--teal-dk)' }}>{data.summary.healthy}</div><div className="kpi-l">Healthy</div></div>
        <div className="kpi"><div className="kpi-v">{data.summary.categories}</div><div className="kpi-l">Categories</div></div>
      </div>

      <div className="intg-grid">
        {data.integrations.map((it: any) => (
          <div className="intg-card" key={it.key}>
            <div className="intg-top">
              <div className="intg-ico">{ICONS[it.category] || '🔌'}</div>
              <span className={`dot-health health-${it.health}`}><span className="d" />{it.health}</span>
            </div>
            <div className="intg-name">{it.name}</div>
            <div className="intg-vendor">{it.vendor} · <span className="mono">{it.protocol}</span></div>
            <div className="intg-desc">{it.desc}</div>
            <div className="intg-foot">
              <span className="hint">Owner: {it.owner_office_name?.split(' ').slice(0, 2).join(' ')}</span>
              {it.can_manage ? (
                <div className="row-actions">
                  <button className="btn btn-sm btn-out" onClick={() => sync(it.key)}>Sync</button>
                  <button className={`btn btn-sm ${it.enabled ? 'btn-rose' : 'btn-teal'}`} onClick={() => toggle(it.key)}>
                    {it.enabled ? 'Disable' : 'Enable'}
                  </button>
                </div>
              ) : <span className="tag">{it.enabled ? 'enabled' : 'disabled'}</span>}
            </div>
          </div>
        ))}
      </div>

      {toast && <DecisionToast decision={toast} onClose={() => setToast(null)} />}
    </div>
  )
}
