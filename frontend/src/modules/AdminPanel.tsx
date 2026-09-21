import { useState, useEffect } from 'react'
import { api } from '../api'
import { Modal, PageHead, Pill, Spinner } from './kit'

export default function AdminPanel({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  const [appointments, setAppointments] = useState<any>(null)
  const [deanScopes, setDeanScopes] = useState<any>(null)
  const [form, setForm] = useState({ department_id: '', staff_id: '', rationale: '' })
  const [scopeForm, setScopeForm] = useState({ dean_user_id: '', school_id: '', dept_id: '', program_id: '', section_id: '', effective_from: '', effective_to: '' })
  const [scopeOpen, setScopeOpen] = useState(false)
  const [hodOpen, setHodOpen] = useState(false)
  const [collegeOpen, setCollegeOpen] = useState(false)
  const [outcome, setOutcome] = useState<any>(null)
  const [college, setCollege] = useState({ code: 'ACET', name: 'Aditya College Of Engineering & Technology' })
  const load = () => { api.adminUsers().then(setData).catch(() => {}); api.academicAppointments().then(setAppointments).catch(() => {}); api.deanScopeAssignments().then(setDeanScopes).catch(() => {}) }
  useEffect(load, [])
  async function submitAppointment() {
    try { await api.createHodAppointment(form); setForm({ department_id: '', staff_id: '', rationale: '' }); setHodOpen(false); setOutcome({ title: 'HOD appointment submitted', message: 'The Principal has been notified to make an independent decision.', error: false }); load() }
    catch (e: any) { setOutcome({ title: 'Appointment was not submitted', message: e.message || 'Select an eligible faculty member and provide the appointment rationale.', error: true }) }
  }
  async function submitDeanScope() {
    try {
      await api.createDeanScopeAssignment({ ...scopeForm, effective_from: scopeForm.effective_from || null, effective_to: scopeForm.effective_to || null })
      setScopeForm({ dean_user_id: '', school_id: '', dept_id: '', program_id: '', section_id: '', effective_from: '', effective_to: '' })
      setScopeOpen(false); setOutcome({ title: 'Dean scope assigned', message: 'The academic access boundary is active and has been recorded in the audit trail.', error: false }); load()
    } catch (e: any) { setOutcome({ title: 'Scope was not assigned', message: e.message || 'Review the selected Dean and academic scope.', error: true }) }
  }
  async function createCollege() {
    try { const result = await api.createAcademicUnit(college); setCollegeOpen(false); setOutcome({ title: 'College created', message: `${result.school.name} is now available in Dean scope assignments.`, error: false }); load() }
    catch (e: any) { setOutcome({ title: 'College was not created', message: e.message || 'Review the college code and name, then try again.', error: true }) }
  }
  if (!data) return <Spinner />
  return (
    <div className="fade-in admin-workspace">
      <PageHead title="System administration" sub="Identity & access — reserved to IT / System Admin per the RBAC invariants" />
      <div className="admin-head-actions"><button className="btn btn-out" onClick={() => setCollegeOpen(true)}>Create College</button><button className="btn primary" onClick={() => setScopeOpen(true)}>Assign Dean Scope</button></div>
      <div className="admin-guardrail">
        <span className="sod-i">⚙</span>
        <div><b>Least privilege.</b> Only IT and System Administrator offices receive system-configuration authority, and every configuration change is itself audited.</div>
      </div>
      <div className="admin-kpis"><div><span>Active identities</span><b>{data.users.filter((u:any) => u.status === 'active').length}</b><small>Current user accounts</small></div><div><span>Dean scopes</span><b>{(deanScopes?.assignments || []).filter((x:any) => x.active).length}</b><small>Active academic boundaries</small></div><div><span>HOD decisions</span><b>{(appointments?.appointments || []).filter((x:any) => x.status === 'SUBMITTED').length}</b><small>Awaiting Principal review</small></div></div>
      <div className="card admin-card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>Username</th><th>Office</th><th>Role</th><th>Scope</th><th>MFA</th><th>Status</th></tr></thead>
            <tbody>
              {data.users.map((u: any) => (
                <tr key={u.username}>
                  <td className="mono">{u.username}</td><td>#{u.office_n}</td><td>{u.role}</td>
                  <td><span className="tag">{u.scope_level}</span></td>
                  <td>{u.mfa ? <span className="pill s-active">on</span> : <span className="pill s-due">off</span>}</td>
                  <td><span className={`pill s-${u.status}`}>{u.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {deanScopes && <div className="card admin-card admin-governance-card" style={{ marginTop: 18 }}>
        <div className="card-head admin-card-head"><div><span className="admin-eyebrow">ACADEMIC GOVERNANCE</span><h3>Dean Academic Scope Assignments</h3><p>Principal-approved School or College authority. Whole-College access is recommended unless a documented restriction is needed.</p></div><button className="btn primary" onClick={() => setScopeOpen(true)}>Assign scope</button></div>
        <div className="form-grid" style={{ display: 'none' }}>
          <label>Dean Academics<select value={scopeForm.dean_user_id} onChange={e => setScopeForm({ ...scopeForm, dean_user_id: e.target.value })}><option value="">Select Dean</option>{(deanScopes.form_options?.deans || []).map((d:any) => <option key={d.id} value={d.id}>{d.username} — {d.role}</option>)}</select></label>
          <label>School / College<select value={scopeForm.school_id} onChange={e => setScopeForm({ ...scopeForm, school_id: e.target.value, dept_id: '', program_id: '', section_id: '' })}><option value="">Select School</option>{(deanScopes.form_options?.schools || []).map((s:any) => <option key={s.id} value={s.id}>{s.code} — {s.name}</option>)}</select></label>
          <label>Department <small>(optional restriction)</small><select disabled={!scopeForm.school_id} value={scopeForm.dept_id} onChange={e => setScopeForm({ ...scopeForm, dept_id: e.target.value, program_id: '', section_id: '' })}><option value="">Entire School</option>{(deanScopes.form_options?.departments || []).filter((d:any) => d.school_id === scopeForm.school_id).map((d:any) => <option key={d.id} value={d.id}>{d.code} — {d.name}</option>)}</select></label>
          <label>Effective from<input type="datetime-local" value={scopeForm.effective_from} onChange={e => setScopeForm({ ...scopeForm, effective_from: e.target.value })} /></label>
          <label>Effective to <small>(optional)</small><input type="datetime-local" value={scopeForm.effective_to} onChange={e => setScopeForm({ ...scopeForm, effective_to: e.target.value })} /></label>
        </div>
        <button style={{ display: 'none' }} disabled={!scopeForm.dean_user_id || !scopeForm.school_id} onClick={submitDeanScope}>Assign Dean scope</button>
        <div className="tbl-scroll" style={{ marginTop: 16 }}><table className="tbl"><thead><tr><th>Dean</th><th>School</th><th>Department restriction</th><th>Effective from</th><th>Status</th></tr></thead><tbody>{(deanScopes.assignments || []).map((a:any) => { const o=deanScopes.form_options || {}; const d=(o.deans || []).find((x:any)=>x.id===a.dean_user_id); const s=(o.schools || []).find((x:any)=>x.id===a.school_id); const dept=(o.departments || []).find((x:any)=>x.id===a.dept_id); return <tr key={a.id}><td>{d?.username || a.dean_user_id}</td><td>{s ? `${s.code} — ${s.name}` : 'Institution scope'}</td><td>{dept ? `${dept.code} — ${dept.name}` : 'Entire School'}</td><td>{a.effective_from ? new Date(a.effective_from).toLocaleString() : '—'}</td><td><span className="pill s-active">{a.active ? 'Active' : 'Ended'}</span></td></tr> })}</tbody></table></div>
      </div>}
      {appointments && <div className="card admin-card admin-governance-card" style={{ marginTop: 18 }}>
        <div className="card-head admin-card-head"><div><span className="admin-eyebrow">LEADERSHIP APPOINTMENTS</span><h3>HOD appointments</h3><p>Submit an eligible faculty appointment. The Principal independently approves, returns, or rejects it.</p></div><button className="btn primary" onClick={() => setHodOpen(true)}>Submit appointment</button></div>
        <div className="form-grid" style={{ display: 'none' }}>
          <label>Department<select value={form.department_id} onChange={e => setForm({ ...form, department_id: e.target.value })}><option value="">Select department</option>{(appointments.departments || []).filter((d:any) => !d.hod_person_id).map((d:any) => <option key={d.id} value={d.id}>{d.code} — {d.name}</option>)}</select></label>
          <label>Eligible faculty<select value={form.staff_id} onChange={e => setForm({ ...form, staff_id: e.target.value })}><option value="">Select faculty member</option>{(appointments.candidates || []).filter((f:any) => !f.department_id || f.department_id === form.department_id).map((f:any) => <option key={f.id} value={f.id}>{f.name} — {f.designation}</option>)}</select></label>
          <label>Appointment rationale<textarea value={form.rationale} onChange={e => setForm({ ...form, rationale: e.target.value })} placeholder="State the approved appointment basis and effective responsibility." /></label>
        </div>
        <button style={{ display: 'none' }} disabled={!form.department_id || !form.staff_id || form.rationale.trim().length < 10} onClick={submitAppointment}>Submit HOD appointment</button>
        <div className="tbl-scroll" style={{ marginTop: 16 }}><table className="tbl"><thead><tr><th>Department</th><th>Proposed HOD</th><th>Status</th><th>Decision note</th></tr></thead><tbody>{appointments.appointments.length ? appointments.appointments.map((a:any) => <tr key={a.id}><td>{a.department}</td><td>{a.staff}</td><td><Pill s={a.status} /></td><td>{a.decision_reason || 'Awaiting independent Principal decision'}</td></tr>) : <tr><td colSpan={4} className="admin-empty">No HOD appointments have been submitted.</td></tr>}</tbody></table></div>
      </div>}
      {collegeOpen && <Modal title="Create School / College" onClose={() => setCollegeOpen(false)} footer={<><button className="btn btn-out" onClick={() => setCollegeOpen(false)}>Cancel</button><button className="btn primary" disabled={college.code.trim().length < 2 || college.name.trim().length < 3} onClick={createCollege}>Create academic unit</button></>}><div className="admin-modal-copy"><b>Use this only for an approved top-level academic unit.</b><p>Creating it does not grant Dean access. Assign scope separately after it is recorded.</p></div><label className="form-row"><span>College code</span><input className="inp" value={college.code} onChange={e => setCollege({...college, code:e.target.value.toUpperCase()})}/></label><label className="form-row"><span>College name</span><input className="inp" value={college.name} onChange={e => setCollege({...college, name:e.target.value})}/></label></Modal>}
      {scopeOpen && <Modal title="Assign Dean Academic Scope" onClose={() => setScopeOpen(false)} footer={<><button className="btn btn-out" onClick={() => setScopeOpen(false)}>Cancel</button><button className="btn primary" disabled={!scopeForm.dean_user_id || !scopeForm.school_id} onClick={submitDeanScope}>Assign scope</button></>}><div className="admin-modal-copy"><b>Principal-approved access only.</b><p>Leave Department blank for whole-College authority. A Dean cannot grant or broaden their own scope.</p></div><label className="form-row"><span>Dean Academics</span><select className="select" value={scopeForm.dean_user_id} onChange={e=>setScopeForm({...scopeForm,dean_user_id:e.target.value})}><option value="">Select Dean</option>{(deanScopes.form_options?.deans || []).map((x:any)=><option key={x.id} value={x.id}>{x.username} — {x.role}</option>)}</select></label><label className="form-row"><span>School / College</span><select className="select" value={scopeForm.school_id} onChange={e=>setScopeForm({...scopeForm,school_id:e.target.value,dept_id:''})}><option value="">Select School / College</option>{(deanScopes.form_options?.schools || []).map((x:any)=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></label><label className="form-row"><span>Department restriction <small>(optional)</small></span><select className="select" disabled={!scopeForm.school_id} value={scopeForm.dept_id} onChange={e=>setScopeForm({...scopeForm,dept_id:e.target.value})}><option value="">Entire School / College</option>{(deanScopes.form_options?.departments || []).filter((x:any)=>x.school_id===scopeForm.school_id).map((x:any)=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></label><div className="grid-2"><label className="form-row"><span>Effective from</span><input className="inp" type="datetime-local" value={scopeForm.effective_from} onChange={e=>setScopeForm({...scopeForm,effective_from:e.target.value})}/></label><label className="form-row"><span>Effective to <small>(optional)</small></span><input className="inp" type="datetime-local" value={scopeForm.effective_to} onChange={e=>setScopeForm({...scopeForm,effective_to:e.target.value})}/></label></div></Modal>}
      {hodOpen && <Modal title="Submit HOD Appointment" onClose={() => setHodOpen(false)} footer={<><button className="btn btn-out" onClick={() => setHodOpen(false)}>Cancel</button><button className="btn primary" disabled={!form.department_id || !form.staff_id || form.rationale.trim().length < 10} onClick={submitAppointment}>Submit for Principal decision</button></>}><div className="admin-modal-copy"><b>This does not appoint the HOD immediately.</b><p>The Principal must independently approve before role and departmental scope change.</p></div><label className="form-row"><span>Department</span><select className="select" value={form.department_id} onChange={e=>setForm({...form,department_id:e.target.value,staff_id:''})}><option value="">Select department</option>{(appointments.departments || []).filter((x:any)=>!x.hod_person_id).map((x:any)=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></label><label className="form-row"><span>Eligible faculty member</span><select className="select" value={form.staff_id} onChange={e=>setForm({...form,staff_id:e.target.value})}><option value="">Select faculty</option>{(appointments.candidates || []).filter((x:any)=>!x.department_id || x.department_id===form.department_id).map((x:any)=><option key={x.id} value={x.id}>{x.name} — {x.designation}</option>)}</select></label><label className="form-row"><span>Appointment rationale</span><textarea className="inp" rows={4} value={form.rationale} onChange={e=>setForm({...form,rationale:e.target.value})} placeholder="State the approved appointment basis and responsibilities."/></label></Modal>}
      {outcome && <Modal title={outcome.title} onClose={() => setOutcome(null)} footer={<button className="btn primary" onClick={() => setOutcome(null)}>Close</button>}><div className={`admin-outcome ${outcome.error ? 'error' : 'success'}`}><b>{outcome.error ? 'Action needs attention' : 'Completed'}</b><p>{outcome.message}</p></div></Modal>}
    </div>
  )
}
