import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, PageHead, Spinner } from './kit'

const blank = { code: '', name: '', school_id: '' }

/**
 * The academic structure register is intentionally separate from programme
 * governance. A Dean can establish a department in an assigned college; HODs
 * and Academic Coordinators can subsequently operate only within it.
 */
export default function DeanDepartments() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [hodDepartment, setHodDepartment] = useState<any>(null)
  const [appointments, setAppointments] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(blank)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const load = async () => {
    try {
      setError('')
      const [departmentData, appointmentData] = await Promise.all([api.academicDepartments(), api.academicAppointments()])
      setData(departmentData)
      setAppointments(appointmentData)
    } catch (requestError: any) {
      setError(requestError?.message || 'Unable to load the department register.')
    }
  }
  useEffect(() => { void load() }, [])

  const openCreate = () => {
    setFieldErrors({})
    setForm({ ...blank, school_id: data?.schools?.[0]?.id || '' })
    setCreating(true)
  }
  const create = async () => {
    const nextErrors: Record<string, string> = {}
    if (!form.code.trim()) nextErrors.code = 'Department code is required.'
    if (!form.name.trim()) nextErrors.name = 'Department name is required.'
    if (!form.school_id) nextErrors.school_id = 'Select the owning college.'
    if (Object.keys(nextErrors).length) return setFieldErrors(nextErrors)
    try {
      setSaving(true)
      setError('')
      await api.createAcademicDepartment({ ...form, code: form.code.trim(), name: form.name.trim() })
      setCreating(false)
      setForm(blank)
      await load()
    } catch (requestError: any) {
      setError(requestError?.message || 'Department could not be created.')
    } finally {
      setSaving(false)
    }
  }

  const edit = async () => {
    if (!editing?.name?.trim()) return
    try {
      setSaving(true)
      setError('')
      await api.updateAcademicDepartment(editing.id, { name: editing.name.trim() })
      setEditing(null)
      await load()
    } catch (requestError: any) {
      setError(requestError?.message || 'Department could not be updated.')
    } finally {
      setSaving(false)
    }
  }

  const archive = async (department: any) => {
    const reason = window.prompt(`Enter the reason to archive ${department.code}:`)
    if (!reason?.trim()) return
    try {
      setSaving(true)
      setError('')
      await api.archiveAcademicDepartment(department.id, { reason: reason.trim() })
      await load()
    } catch (requestError: any) {
      setError(requestError?.message || 'Department could not be archived. Dependent records may exist.')
    } finally {
      setSaving(false)
    }
  }

  const submitHod = async (staffId: string, rationale: string) => {
    try {
      setSaving(true)
      setError('')
      await api.createHodAppointment({ department_id: hodDepartment.id, staff_id: staffId, rationale })
      setHodDepartment(null)
      await load()
    } catch (requestError: any) {
      setError(requestError?.message || 'HOD appointment could not be submitted.')
    } finally {
      setSaving(false)
    }
  }

  if (!data) return error ? <div className="card card-pad calendar-banner warn">{error}<button className="btn btn-out btn-sm" onClick={() => void load()}>Retry</button></div> : <Spinner />
  const departments = Array.isArray(data.departments) ? data.departments : []
  const schools = Array.isArray(data.schools) ? data.schools : []
  return <div className="fade-in">
    <PageHead title="Department Management" sub="Establish and review the academic department structure within your assigned colleges." right={<>{data.can_create && <button className="btn btn-crimson" onClick={openCreate}>+ Create department</button>}<button className="btn btn-out" onClick={() => void load()}>Refresh</button></>} />
    {error && <div className="calendar-banner warn">{error}</div>}
    {!schools.length && <div className="calendar-banner warn">No active college is assigned to your Dean scope, so department creation is unavailable. Assign an active college to this Dean appointment first.</div>}
    <section className="card">
      <div className="card-h"><div><h3>Department register</h3><span className="hint">Department establishment is a Dean Academics responsibility and is recorded in the audit trail.</span></div><span className="hint">{departments.length} department{departments.length === 1 ? '' : 's'}</span></div>
      {departments.length ? <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Code</th><th>Department</th><th>College</th><th>HOD assignment</th><th>Actions</th></tr></thead><tbody>{departments.map((department: any) => <tr key={department.id}><td><b>{department.code}</b></td><td>{department.name}</td><td>{department.school}</td><td>{department.hod_person_id ? 'Assigned' : 'Not assigned'}</td><td><button className="btn btn-out btn-sm" onClick={() => setEditing({ id: department.id, name: department.name })}>Edit</button>{!department.hod_person_id && <button className="btn btn-out btn-sm" onClick={() => setHodDepartment(department)}>Assign HOD</button>}<button className="btn btn-out btn-sm" onClick={() => void archive(department)} disabled={saving}>Archive</button></td></tr>)}</tbody></table></div> : <Empty text="No departments exist in your assigned academic scope." />}
    </section>
    {creating && <Modal title="Create department" onClose={() => setCreating(false)} footer={<><button className="btn btn-out" onClick={() => setCreating(false)} disabled={saving}>Cancel</button><button className="btn btn-crimson" onClick={() => void create()} disabled={saving}>{saving ? 'Creating…' : 'Create department'}</button></>}>
      <p className="hint">Use the approved organisational name and code. Department moves, renames, and closure require a separate governed change process to preserve academic records.</p>
      <Field label="Department code" error={fieldErrors.code}><input className="inp" value={form.code} maxLength={32} placeholder="Example: CSE" onChange={event => { setFieldErrors(current => ({ ...current, code: '' })); setForm({ ...form, code: event.target.value.toUpperCase() }) }} /></Field>
      <Field label="Department name" error={fieldErrors.name}><input className="inp" value={form.name} maxLength={160} placeholder="Example: Computer Science and Engineering" onChange={event => { setFieldErrors(current => ({ ...current, name: '' })); setForm({ ...form, name: event.target.value }) }} /></Field>
      <Field label="Owning college" error={fieldErrors.school_id}><select className="select" value={form.school_id} onChange={event => { setFieldErrors(current => ({ ...current, school_id: '' })); setForm({ ...form, school_id: event.target.value }) }}><option value="" disabled>Select college</option>{schools.map((school: any) => <option key={school.id} value={school.id}>{school.code} — {school.name}</option>)}</select></Field>
      {!schools.length && <div className="calendar-banner warn">No active college is assigned to your Dean scope. A system administrator must assign the scope before a department can be created.</div>}
    </Modal>}
    {editing && <Modal title="Edit department" onClose={() => setEditing(null)} footer={<><button className="btn btn-out" onClick={() => setEditing(null)} disabled={saving}>Cancel</button><button className="btn btn-crimson" onClick={() => void edit()} disabled={saving || !editing.name.trim()}>{saving ? 'Saving…' : 'Save changes'}</button></>}><p className="hint">Department codes and college ownership are immutable after creation. Rename changes are audited.</p><Field label="Department name"><input className="inp" value={editing.name} maxLength={160} onChange={event => setEditing({ ...editing, name: event.target.value })} /></Field></Modal>}
    {hodDepartment && <HodModal department={hodDepartment} appointments={appointments} saving={saving} onClose={() => setHodDepartment(null)} onSubmit={submitHod} />}
  </div>
}

function HodModal({ department, appointments, saving, onClose, onSubmit }: any) {
  const [staffId, setStaffId] = useState('')
  const [rationale, setRationale] = useState('')
  const candidates = (appointments?.candidates || []).filter((staff: any) => !staff.department_id || staff.department_id === department.id)
  return <Modal title={`Assign HOD — ${department.code}`} onClose={onClose} footer={<><button className="btn btn-out" onClick={onClose} disabled={saving}>Cancel</button><button className="btn btn-crimson" onClick={() => void onSubmit(staffId, rationale)} disabled={saving || !staffId || rationale.trim().length < 10}>{saving ? 'Submitting…' : 'Submit for Principal approval'}</button></>}><div className="hint">The Dean submits the appointment. The Principal must independently approve it before the faculty member receives HOD access.</div><Field label="Eligible faculty"><select className="select" value={staffId} onChange={event => setStaffId(event.target.value)}><option value="">Select faculty member</option>{candidates.map((staff: any) => <option key={staff.id} value={staff.id}>{staff.name} — {staff.designation}</option>)}</select></Field><Field label="Appointment rationale"><textarea className="inp" rows={4} value={rationale} onChange={event => setRationale(event.target.value)} placeholder="State the approved appointment basis and responsibilities." /></Field></Modal>
}

function Field({ label, error, children }: { label: string; error?: string; children: any }) {
  return <div className={`form-row ${error ? 'has-error' : ''}`}><label>{label}</label>{children}{error && <small className="form-field-error" role="alert">{error}</small>}</div>
}
