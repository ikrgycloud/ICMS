import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast, Modal, GatedBtn } from './kit'

export default function Grievance({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  const [decision, setDecision] = useState<any>(null)
  const [show, setShow] = useState(false)
  const [form, setForm] = useState({ kind: 'Grievance', subject: '', detail: '' })

  function load() { api.grievance().then(setData).catch(() => {}) }
  useEffect(() => { load() }, [])

  async function raise() {
    try { const r = await api.raiseComplaint(form); setDecision(r.decision); setShow(false); setForm({ kind: 'Grievance', subject: '', detail: '' }); load() }
    catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }); setShow(false) }
  }
  async function resolve(id: string, status: string) {
    try { const r = await api.resolveComplaint(id, status); setDecision(r.decision); load() }
    catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }) }
  }

  if (!data) return <Spinner />
  return (
    <div className="fade-in">
      <PageHead title="Grievance & discipline" sub="Complaints intake, investigation and resolution"
        right={<GatedBtn can={!!caps.raise} onClick={() => setShow(true)}>+ Raise complaint</GatedBtn>} />
      <div className="card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Type</th><th>Raised by</th><th>Subject</th><th>Severity</th><th>Status</th><th style={{ textAlign: 'right' }}></th></tr></thead>
            <tbody>
              {data.complaints.map((c: any) => (
                <tr key={c.id}>
                  <td><span className={`tag ${c.kind === 'Ragging' ? 'tag-rose' : ''}`}>{c.kind}</span></td>
                  <td className="mono">{c.raised_by}</td><td><b>{c.subject}</b></td>
                  <td><span className={`pill s-${c.severity}`}>{c.severity}</span></td>
                  <td><span className={`pill s-${c.status}`}>{c.status}</span></td>
                  <td style={{ textAlign: 'right' }}>
                    {c.status !== 'resolved' && (
                      <div className="row-actions">
                        <button className="btn btn-sm btn-out" disabled={!caps.resolve} onClick={() => resolve(c.id, 'investigating')}>Investigate</button>
                        <button className="btn btn-sm btn-teal" disabled={!caps.resolve} onClick={() => resolve(c.id, 'resolved')}>Resolve</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {show && (
        <Modal title="Raise a complaint" onClose={() => setShow(false)}
          footer={<><button className="btn btn-out" onClick={() => setShow(false)}>Cancel</button>
            <button className="btn btn-brass" onClick={raise} disabled={!form.subject}>Submit</button></>}>
          <div className="form-row"><label>Type</label>
            <select className="select" value={form.kind} onChange={e => setForm({ ...form, kind: e.target.value })}>
              <option>Grievance</option><option>Ragging</option><option>Discipline</option>
            </select></div>
          <div className="form-row"><label>Subject</label>
            <input className="inp" value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })} /></div>
          <div className="form-row"><label>Details</label>
            <textarea className="inp" rows={3} value={form.detail} onChange={e => setForm({ ...form, detail: e.target.value })} /></div>
        </Modal>
      )}
      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
