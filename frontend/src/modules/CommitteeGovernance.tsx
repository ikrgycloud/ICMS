import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, PageHead, Pill, Spinner } from './kit'

const emptyCommittee = { name: '', committee_type: 'Academic', chair_id: '', permissions: ['view', 'record', 'assign', 'verify'] }

export default function CommitteeGovernance() {
  const [committees, setCommittees] = useState<any[]>([])
  const [selected, setSelected] = useState<any>(null)
  const [detail, setDetail] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [showMember, setShowMember] = useState(false)
  const [showMeeting, setShowMeeting] = useState(false)
  const [committeeForm, setCommitteeForm] = useState(emptyCommittee)
  const [memberForm, setMemberForm] = useState({ user_id: '', role: 'member' })
  const [meetingForm, setMeetingForm] = useState({ meeting_at: '', agenda: '' })

  async function load() {
    setLoading(true); setError('')
    try { const data = await api.committees(); const rows = data.committees || []; setCommittees(rows); setSelected(current => rows.find((item: any) => item.id === current?.id) || rows[0] || null) }
    catch (e: any) { setError(e.message || 'Unable to load committees') } finally { setLoading(false) }
  }
  async function loadDetail(committee: any) {
    if (!committee) { setDetail(null); return }
    try { const [members, meetings, resolutions, actions] = await Promise.all([api.committeeMembers(committee.id), api.committeeMeetings(committee.id), api.committeeResolutions(committee.id), api.committeeActionItems()]); setDetail({ members: members.members || [], meetings: meetings.meetings || [], resolutions: resolutions.resolutions || [], actions: actions.actions || [] }) }
    catch (e: any) { setError(e.message || 'Unable to load committee details') }
  }
  useEffect(() => { load() }, [])
  useEffect(() => { loadDetail(selected) }, [selected])
  async function saveCommittee() { setSaving(true); try { if (committeeForm.name.trim()) { await api.createCommittee(committeeForm); setShowEdit(false); await load() } } catch (e: any) { setError(e.message || 'Unable to save committee') } finally { setSaving(false) } }
  async function updateCommittee() { if (!selected) return; setSaving(true); try { await api.updateCommittee(selected.id, committeeForm); setShowEdit(false); await load() } catch (e: any) { setError(e.message || 'Unable to update committee') } finally { setSaving(false) } }
  async function addMember() { if (!selected) return; setSaving(true); try { await api.addCommitteeMember(selected.id, memberForm); setShowMember(false); setMemberForm({ user_id: '', role: 'member' }); await loadDetail(selected) } catch (e: any) { setError(e.message || 'Unable to add committee member') } finally { setSaving(false) } }
  async function removeMember(id: string) { if (!selected) return; setSaving(true); try { await api.removeCommitteeMember(selected.id, id); await loadDetail(selected) } catch (e: any) { setError(e.message || 'Unable to remove committee member') } finally { setSaving(false) } }
  async function createMeeting() { if (!selected) return; setSaving(true); try { await api.createCommitteeMeeting({ committee_id: selected.id, ...meetingForm }); setShowMeeting(false); setMeetingForm({ meeting_at: '', agenda: '' }); await loadDetail(selected) } catch (e: any) { setError(e.message || 'Unable to schedule committee meeting') } finally { setSaving(false) } }
  if (loading) return <Spinner />

  return <div className="fade-in">
    <PageHead title="Committee Governance" sub="Record decisions, preserve minutes, and follow verified actions." right={<><button className="btn btn-crimson" onClick={() => { setCommitteeForm(emptyCommittee); setShowEdit(true) }}>New committee</button><button className="btn btn-out" onClick={load}>Refresh</button></>} />
    {error && <div className="calendar-banner warn">{error}</div>}
    <div className="academic-layout"><aside className="card card-pad"><div className="card-h"><h3>Committees</h3></div>{committees.map(c => <button className={`academic-side-item ${selected?.id === c.id ? 'active' : ''}`} key={c.id} onClick={() => setSelected(c)}><strong>{c.name}</strong><span>{c.type} · {c.status}</span></button>)}{!committees.length && <Empty text="No committees configured" />}</aside>
      <main className="card card-pad">{selected && detail ? <><div className="card-h"><div><h3>{selected.name}</h3><span className="hint">{selected.type} · Chair {selected.chair_id || 'Unassigned'}</span></div><span className="row-actions"><Pill s={selected.status} /><button className="btn btn-sm btn-out" onClick={() => { setCommitteeForm({ name: selected.name, committee_type: selected.type, chair_id: selected.chair_id || '', permissions: selected.permissions || emptyCommittee.permissions }); setShowEdit(true) }}>Edit</button></span></div>
        <div className="kpi-grid"><Metric label="Members" value={detail.members.length} /><Metric label="Meetings" value={detail.meetings.length} /><Metric label="Resolutions" value={detail.resolutions.length} /><Metric label="Open actions" value={detail.actions.filter((a: any) => a.status !== 'VERIFIED').length} /></div>
        <section><div className="card-h"><h4>Members</h4><button className="btn btn-sm btn-out" onClick={() => setShowMember(true)}>Add member</button></div>{detail.members.map((m: any) => <div className="snap" key={m.id}><span>{m.user_id}</span><span className="row-actions"><Pill s={m.role} /><button className="btn btn-sm btn-out" disabled={saving} onClick={() => removeMember(m.id)}>Remove</button></span></div>)}{!detail.members.length && <Empty text="No members assigned" />}</section>
        <section><div className="card-h"><h4>Meetings and minutes</h4><button className="btn btn-sm btn-out" onClick={() => setShowMeeting(true)}>Schedule meeting</button></div>{detail.meetings.map((m: any) => <div className="snap" key={m.id}><span>{new Date(m.meeting_at).toLocaleString()}<br /><small>{m.agenda || 'No agenda'}</small></span><Pill s={m.status} /></div>)}{!detail.meetings.length && <Empty text="No meetings recorded" />}</section>
        <section><h4>Resolutions and actions</h4>{detail.resolutions.map((r: any) => <div className="snap" key={r.id}><span><b>{r.title}</b><br /><small>{r.decision}</small></span><Pill s={r.status} /></div>)}{detail.actions.map((a: any) => <div className="snap" key={a.id}><span>{a.title}<br /><small>Owner: {a.owner_id}</small></span><Pill s={a.status} /></div>)}{!detail.resolutions.length && !detail.actions.length && <Empty text="No resolutions or actions" />}</section>
      </> : <Empty text="Select a committee" />}</main></div>
    {showEdit && <Modal title={committeeForm.name ? 'Edit committee' : 'New committee'} onClose={() => setShowEdit(false)} footer={<><button className="btn btn-out" onClick={() => setShowEdit(false)}>Cancel</button><button className="btn btn-crimson" disabled={saving} onClick={committeeForm.name && selected?.name === committeeForm.name ? updateCommittee : saveCommittee}>{saving ? 'Saving...' : 'Save'}</button></>}><Field label="Name"><input className="inp" value={committeeForm.name} onChange={e => setCommitteeForm({ ...committeeForm, name: e.target.value })} /></Field><Field label="Type"><input className="inp" value={committeeForm.committee_type} onChange={e => setCommitteeForm({ ...committeeForm, committee_type: e.target.value })} /></Field><Field label="Chair user ID"><input className="inp" value={committeeForm.chair_id} onChange={e => setCommitteeForm({ ...committeeForm, chair_id: e.target.value })} /></Field></Modal>}
    {showMember && <Modal title="Add committee member" onClose={() => setShowMember(false)} footer={<><button className="btn btn-out" onClick={() => setShowMember(false)}>Cancel</button><button className="btn btn-crimson" disabled={saving} onClick={addMember}>Add member</button></>}><Field label="User ID"><input className="inp" value={memberForm.user_id} onChange={e => setMemberForm({ ...memberForm, user_id: e.target.value })} /></Field><Field label="Role"><input className="inp" value={memberForm.role} onChange={e => setMemberForm({ ...memberForm, role: e.target.value })} /></Field></Modal>}
    {showMeeting && <Modal title="Schedule committee meeting" onClose={() => setShowMeeting(false)} footer={<><button className="btn btn-out" onClick={() => setShowMeeting(false)}>Cancel</button><button className="btn btn-crimson" disabled={saving} onClick={createMeeting}>Schedule</button></>}><Field label="Meeting date and time"><input className="inp" type="datetime-local" value={meetingForm.meeting_at} onChange={e => setMeetingForm({ ...meetingForm, meeting_at: e.target.value })} /></Field><Field label="Agenda"><textarea className="inp" value={meetingForm.agenda} onChange={e => setMeetingForm({ ...meetingForm, agenda: e.target.value })} /></Field></Modal>}
  </div>
}
function Metric({ label, value }: any) { return <div className="kpi"><div className="kpi-val">{value}</div><div className="kpi-label">{label}</div></div> }
function Field({ label, children }: any) { return <div className="form-row"><label>{label}</label>{children}</div> }