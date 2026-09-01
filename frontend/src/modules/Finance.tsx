import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast, Modal, money, Empty } from './kit'

export default function Finance({ caps, user, onOpenApprovals }: { caps: any; user: any; onOpenApprovals: () => void }) {
  // Start with live financial records; fee setup is an occasional configuration task.
  const [tab, setTab] = useState<'fees' | 'payments' | 'setup' | 'students'>('fees')
  const [data, setData] = useState<any>(null)
  const [decision, setDecision] = useState<any>(null)
  const [modal, setModal] = useState<{ kind: string; inv: any; method?: string; reference?: string } | null>(null)
  const [amount, setAmount] = useState('')
  const [search, setSearch] = useState('')
  const [studentQuery, setStudentQuery] = useState('')
  const [students, setStudents] = useState<any[]>([])
  const [selectedStudent, setSelectedStudent] = useState<any>(null)
  const [selectedSemester, setSelectedSemester] = useState('')
  const [pendingPayments, setPendingPayments] = useState<any[]>([])

  function load() {
    api.invoices().then(setData).catch(() => {})
  }
  useEffect(() => { load() }, [])
  useEffect(() => { if (tab === 'payments') api.pendingPayments().then((r:any) => setPendingPayments(r.payments || [])).catch(() => setPendingPayments([])) }, [tab])
  async function decideOffline(payment:any, action:string) {
    const remarks = ['bounced', 'rejected'].includes(action) ? window.prompt('Reason (required):') || '' : ''
    try { await api.verifyOfflinePayment(payment.id, action, remarks); setPendingPayments(rows => rows.filter(row => row.id !== payment.id)); load() }
    catch (error:any) { alert(error.message || 'Could not update payment') }
  }

  async function loadStudents(q = '') {
    try {
      // The student API is paginated (maximum 100 per request). Load every
      // page so Finance can search the complete authorised student list.
      const first = await api.students(q, '', 1, 100)
      const pages = Number(first?.total_pages || 1)
      const rest = await Promise.all(Array.from({ length: Math.max(0, pages - 1) }, (_, i) => api.students(q, '', i + 2, 100)))
      setStudents([...(first?.students || []), ...rest.flatMap((page: any) => page?.students || [])])
    } catch (e) {
      setStudents([])
    }
  }

  useEffect(() => {
    if (tab === 'students') loadStudents(studentQuery)
  }, [tab])

  useEffect(() => {
    if (!selectedStudent || !selectedStudent.id) return
    api.studentProfile(selectedStudent.id).then((profile: any) => setSelectedStudent(profile.student || selectedStudent)).catch(() => {})
  }, [selectedStudent?.id])

  async function act() {
    if (!modal) return
    try {
      const amt = Number(amount)
      const method = (modal.method || 'cash').toLowerCase()
      const reference = (modal.reference || '').trim() || `${method.toUpperCase()}-${Date.now().toString().slice(-6)}`
      const r = await api.recordPayment(modal.inv.id, amt, method, reference)
      if (method === 'cash' && r.status !== 'pending_clearance') api.downloadFinanceReceipt(modal.inv.id, r.payment_id)
      setDecision(r.decision || { outcome: 'APPROVE', reason: `Recorded via ${method}` }); setModal(null); setAmount(''); load(); if (tab === 'students') loadStudents(studentQuery)
    } catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }); setModal(null) }
  }

  if (!data) return <Spinner />
  const sm = data.summary
  const selectedStudentInvoices = selectedStudent ? (data.invoices || []).filter((invoice: any) => invoice.roll_no === selectedStudent.roll_no) : []
  const availableSemesters = [...new Set(selectedStudentInvoices.map((invoice: any) => invoice.term).filter(Boolean))]
  const semesterInvoices = selectedSemester ? selectedStudentInvoices.filter((invoice: any) => invoice.term === selectedSemester) : []

  return (
    <div className="fade-in finance-workspace">
      <PageHead title="Finance Manager" sub="Fee setup, invoices, and payments recorded in ICMS." />

      <section className="finance-summary">
        <div className="finance-summary-main"><span>Fee operations dashboard</span><strong>{money(sm.total_collected)}</strong><small>Collected from recorded payments</small></div>
        <div className="finance-stat"><span>Total billed</span><b>{money(sm.total_billed)}</b></div>
        <div className="finance-stat outstanding"><span>Outstanding</span><b>{money(sm.outstanding)}</b></div>
        <div className="finance-stat"><span>Collection rate</span><b>{Math.round(100 * sm.total_collected / (sm.total_billed || 1))}%</b></div>
      </section>

      <div className="tabs finance-tabs">
        <button className={`tab ${tab === 'setup' ? 'on' : ''}`} onClick={() => setTab('setup')}>Fee setup</button>
        <button className={`tab ${tab === 'fees' ? 'on' : ''}`} onClick={() => setTab('fees')}>Student invoices</button>
        <button className={`tab ${tab === 'students' ? 'on' : ''}`} onClick={() => setTab('students')}>Students</button>
        <button className={`tab ${tab === 'payments' ? 'on' : ''}`} onClick={() => setTab('payments')}>Payment records</button>
      </div>

      {tab === 'students' && (
        <div className="card finance-card">
          <div className="card-h finance-card-head">
            <div><h3>Student collection</h3><span className="hint">Search by roll number or student name, then confirm manual payment details.</span></div>
            <label className="finance-search"><span>Search</span><input className="inp" placeholder="Roll no. or student name" value={studentQuery} onChange={e => { const value = e.target.value; setStudentQuery(value); loadStudents(value) }} /></label>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 390px) 1fr', gap: 0 }}>
            <div className="tbl-scroll" style={{ borderRight: '1px solid #edf1f7' }}>
              <table className="tbl">
                <thead><tr><th>Roll No</th><th>Name</th></tr></thead>
                <tbody>
                  {students.length ? students.map((student: any) => (
                    <tr key={student.id} style={{ cursor: 'pointer', background: selectedStudent?.id === student.id ? 'rgba(138,31,43,.04)' : undefined }} onClick={() => { setSelectedStudent(student); setSelectedSemester('') }}>
                      <td className="mono">{student.roll_no}</td>
                      <td><b>{student.name}</b></td>
                    </tr>
                  )) : <tr><td colSpan={2}><Empty text="No students match this search." /></td></tr>}
                </tbody>
              </table>
            </div>
            <div style={{ padding: 18 }}>
              {!selectedStudent ? <div className="empty">Select a student to view fee details and confirm payment.</div> : (
                <div style={{ display: 'grid', gap: 16 }}>
                  <div style={{ border: '1px solid #e7edf5', borderRadius: 14, padding: 16, background: '#fbfcfe' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                      <div>
                        <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '.08em', color: '#6b7280' }}>Student profile</div>
                        <h3 style={{ marginTop: 6, fontSize: 26 }}>{selectedStudent.name}</h3>
                      </div>
                      <div className="mono" style={{ fontWeight: 700, color: '#1f2937' }}>{selectedStudent.roll_no}</div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginTop: 14 }}>
                      <div className="stat"><small>Program</small><b>{selectedStudent.program || '—'}</b></div>
                      <div className="stat"><small>Semester</small><b>{selectedStudent.semester || '—'}</b></div>
                      <div className="stat"><small>Section</small><b>{selectedStudent.section || '—'}</b></div>
                      <div className="stat"><small>CGPA</small><b>{selectedStudent.cgpa ?? '—'}</b></div>
                    </div>
                  </div>

                  <div className="card" style={{ borderRadius: 14 }}>
                    <div className="card-h"><div><h3>Open invoices</h3><span className="hint">Select the semester, then record a cash, cheque, DD, or bank-transfer payment.</span></div><label className="finance-search"><span>Semester</span><select className="select" value={selectedSemester} onChange={e => setSelectedSemester(e.target.value)}><option value="">Select semester</option>{availableSemesters.map((term: any) => <option key={term} value={term}>{term}</option>)}</select></label></div>
                    <div className="tbl-scroll">
                      <table className="tbl">
                        <thead><tr><th>Invoice</th><th>Amount</th><th>Paid</th><th>Balance</th><th>Method</th><th>Action</th></tr></thead>
                        <tbody>
                          {!selectedSemester ? <tr><td colSpan={6}><Empty text="Select a semester to view its invoice and record payment." /></td></tr> : semesterInvoices.length ? semesterInvoices.map((invoice: any) => (
                            <tr key={invoice.id} className={invoice.balance > 0 ? 'finance-row-due' : 'finance-row-paid'}>
                              <td className="mono">{invoice.term || invoice.id.slice(0, 8)}</td>
                              <td>{money(invoice.amount)}</td>
                              <td>{money(invoice.paid)}</td>
                              <td><b style={{ color: invoice.balance > 0 ? 'var(--rose)' : 'var(--teal)' }}>{money(invoice.balance)}</b></td>
                              <td><span className="pill s-paid">{invoice.status}</span></td>
                              <td>
                                {invoice.balance > 0 ? <button className="btn btn-sm btn-crimson" onClick={() => { setModal({ kind: 'pay', inv: invoice, method: 'cash', reference: '' }); setAmount(String(invoice.balance)) }}>Confirm</button> : <span className="hint">Settled</span>}
                              </td>
                            </tr>
                          )) : <tr><td colSpan={6}><Empty text="No invoices found for this student." /></td></tr>}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'fees' && (
        <div className="card finance-card">
          <div className="card-h finance-card-head"><div><h3>Student invoices</h3><span className="hint">Live balances from the ICMS database</span></div><label className="finance-search"><span>Search</span><input className="inp" placeholder="Roll number or student name" value={search} onChange={e=>setSearch(e.target.value)} /></label></div>
          <div className="tbl-scroll">
            <table className="tbl">
              <thead><tr><th>Roll No</th><th>Name</th><th>Billed</th><th>Paid</th><th>Balance</th><th>Status</th><th style={{ textAlign: 'right' }}>Actions</th></tr></thead>
              <tbody>
                {data.invoices.filter((r:any) => !search || `${r.roll_no} ${r.name}`.toLowerCase().includes(search.toLowerCase())).slice(0, 100).map((r: any) => (
                  <tr key={r.id} className={r.balance > 0 ? 'finance-row-due' : 'finance-row-paid'}>
                    <td className="mono">{r.roll_no}</td>
                    <td>{r.name}</td>
                    <td>{money(r.amount)}</td>
                    <td>{money(r.paid)}</td>
                    <td><b style={{ color: r.balance > 0 ? 'var(--rose)' : 'var(--teal)' }}>{money(r.balance)}</b></td>
                    <td><span className={`pill s-${r.status}`}>{r.status}</span></td>
                    <td style={{ textAlign: 'right' }}>
                      <div className="row-actions">
                        <button className="btn btn-sm btn-teal" disabled={!caps.record_payment || r.balance <= 0} onClick={() => { setModal({ kind: 'pay', inv: r, method: 'cash', reference: '' }); setAmount(String(r.balance)) }}>{r.balance > 0 ? 'Record payment' : 'Settled'}</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'payments' && (
        <div className="card finance-card">
          <div className="card-h"><div><h3>Payment records</h3><span className="hint">Confirmed payments stored in the database</span></div></div>
          {pendingPayments.length > 0 && <div className="card-pad"><h4>Pending verification / clearance</h4><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Student</th><th>Challan</th><th>Amount</th><th>Mode</th><th>Reference</th><th>Action</th></tr></thead><tbody>{pendingPayments.map((p:any) => <tr key={p.id}><td><b>{p.student}</b><small>{p.roll_no}</small></td><td className="mono">{p.challan_number || '—'}</td><td>{money(p.amount)}</td><td>{p.method}</td><td className="mono">{p.reference}</td><td><div className="row-actions">{p.status === 'pending_clearance' ? <><button className="btn btn-sm btn-brass" onClick={() => decideOffline(p, 'cleared')}>Mark cleared</button><button className="btn btn-sm btn-out" onClick={() => decideOffline(p, 'bounced')}>Bounce</button></> : <><button className="btn btn-sm btn-brass" onClick={() => decideOffline(p, 'verified')}>Verify</button><button className="btn btn-sm btn-out" onClick={() => decideOffline(p, 'rejected')}>Reject</button></>}</div></td></tr>)}</tbody></table></div></div>}
          <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Date</th><th>Roll No.</th><th>Student</th><th>Amount</th><th>Method</th><th>Payment reference</th></tr></thead><tbody>{data.payments?.length ? data.payments.map((p:any) => <tr key={p.id}><td>{p.at ? new Date(p.at).toLocaleString('en-IN') : '—'}</td><td className="mono">{p.roll_no}</td><td>{p.name}</td><td><b>{money(p.amount)}</b></td><td><span className="pill s-paid">{p.method}</span></td><td className="mono">{p.reference || '—'}</td></tr>) : <tr><td colSpan={6}><Empty text="No payment records yet." /></td></tr>}</tbody></table></div>
        </div>
      )}

      {tab === 'setup' && <FeeSetup canManage={user?.office_n === 22} onOpenApprovals={onOpenApprovals} />}

      {modal && (
        <Modal title="Record fee payment" onClose={() => setModal(null)}
          footer={<><button className="btn btn-out" onClick={() => setModal(null)}>Cancel</button>
            <button className="btn btn-brass" onClick={act}>Record payment</button></>}>
          <div className="form-row"><label>Student</label><div className="mono">{modal.inv.roll_no} · {modal.inv.name}</div></div>
          <div className="form-row"><label>Semester / invoice</label><div>{modal.inv.term || 'Not specified'}</div></div>
          <div className="form-row"><label>Payment method</label>
            <select className="select" value={modal.method || 'cash'} onChange={e => setModal({ ...modal, method: e.target.value })}>
              <option value="cash">Cash</option>
              <option value="cheque">Cheque</option>
              <option value="dd">DD</option>
              <option value="bank_transfer">Bank transfer</option>
              <option value="online">Online</option>
            </select>
          </div>
          <div className="form-row"><label>Amount (₹)</label>
            <input className="inp" type="number" value={amount} onChange={e => setAmount(e.target.value)} /></div>
          <div className="form-row"><label>Reference / receipt</label>
            <input className="inp" value={modal.reference || ''} onChange={e => setModal({ ...modal, reference: e.target.value })} placeholder="Cash receipt / cheque no / transaction ID" /></div>
          {modal.kind === 'waive' && <p className="hint">Waivers above your scope’s approval limit auto-escalate to the Vice-Chancellor per the approval matrix.</p>}
        </Modal>
      )}
      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}

const blankHead = { code: '', name: '', category: 'OTHER', description: '', is_mandatory: true, display_order: 0 }
const blankLine = { fee_head_id: '', amount: '', installment_no: 1, installment_name: '', due_date: '', is_mandatory: true, description: '' }

function FeeSetup({ canManage, onOpenApprovals }: { canManage: boolean; onOpenApprovals: () => void }) {
  const [view, setView] = useState<'structures' | 'heads'>('structures')
  const [heads, setHeads] = useState<any[]>([]), [structures, setStructures] = useState<any[]>([]), [refs, setRefs] = useState<any>(null)
  const [head, setHead] = useState<any>(null), [draft, setDraft] = useState<any>(null), [error, setError] = useState(''), [saving, setSaving] = useState(false)
  const [affected, setAffected] = useState<any>(null)
  const [affectedSearch, setAffectedSearch] = useState('')
  const load = () => { api.feeHeads(true).then(r => setHeads(r.heads)).catch(e => setError(e.message)); api.feeStructures().then(r => setStructures(r.structures)).catch(e => setError(e.message)); api.feeReferenceData().then(setRefs).catch(e => setError(e.message)) }
  useEffect(() => {
    load()
    // Approval happens in the Principal workspace, often while Finance remains
    // open in another tab. Refresh on focus and periodically so APPROVED rows
    // expose Publish / Apply without requiring a manual page reload.
    window.addEventListener('focus', load)
    const refreshTimer = window.setInterval(load, 15000)
    return () => {
      window.removeEventListener('focus', load)
      window.clearInterval(refreshTimer)
    }
  }, [])
  async function saveHead() { try { setSaving(true); if (head.id) await api.updateFeeHead(head.id, head); else await api.createFeeHead(head); setHead(null); load() } catch (e:any) { setError(e.message) } finally { setSaving(false) } }
  async function toggle(h:any) { if (!confirm(`${h.is_active ? 'Deactivate' : 'Activate'} ${h.name}?`)) return; try { await api.setFeeHeadStatus(h.id, !h.is_active); load() } catch (e:any) { setError(e.message) } }
  async function saveDraft() { try { setSaving(true); const payload = {...draft, effective_from: draft.effective_from || null, effective_to: draft.effective_to || null, lines: draft.lines.map((x:any) => ({...x, amount: Number(x.amount), due_date: x.due_date || null}))}; if (draft.id) await api.updateFeeStructure(draft.id, payload); else await api.createFeeStructure(payload); setDraft(null); load() } catch (e:any) { setError(e.message) } finally { setSaving(false) } }
  async function publish(id:string) { if (!confirm('Publish and apply this fee structure to all matching students?')) return; try { setSaving(true); const result = await api.publishFeeStructure(id); const accounts = result.student_accounts_created ? ` ${result.student_accounts_created} student login account(s) created.` : ''; setError(`Published: ${result.invoices_created} invoice(s) created for ${result.matched_students} student(s).${accounts}`); load() } catch (e:any) { setError(e.message) } finally { setSaving(false) } }
  async function submit(id:string) { if (!confirm('Submit this draft for approval? It will be locked for editing.')) return; try { setSaving(true); await api.submitFeeStructure(id); setError('Fee structure submitted for approval.'); load() } catch (e:any) { setError(e.message) } finally { setSaving(false) } }
  async function showAffected(id:string) { try { setAffectedSearch(''); setAffected(await api.feeStructureAffectedStudents(id)) } catch (e:any) { setError(e.message) } }
  const gross = (draft?.lines || []).reduce((sum:number, x:any) => sum + (Number(x.amount) || 0), 0)
  const affectedStudents = (affected?.students || []).filter((student:any) => {
    const query = affectedSearch.trim().toLowerCase()
    return !query || student.roll_no.toLowerCase().includes(query) || student.name.toLowerCase().includes(query)
  })
  if (!refs) return <Spinner />
  return <div className="card fee-management-card"><div className="card-h fee-management-head"><div><span className="fee-management-eyebrow">Finance configuration</span><h3>Fee Management</h3><span className="hint">{canManage ? 'Create, approve, and publish fee structures for students.' : 'Read-only fee setup. Structures submitted for your decision appear in Approvals.'}</span></div><div className="row-actions"><button className="btn btn-out" onClick={() => setView(view === 'heads' ? 'structures' : 'heads')}>{view === 'heads' ? 'View structures' : 'View fee heads'}</button>{canManage && (view === 'heads' ? <button className="btn btn-crimson" onClick={() => setHead({...blankHead})}>+ Add fee head</button> : <button className="btn btn-crimson" onClick={() => setDraft(newDraft())}>+ Create structure</button>)}{!canManage && <button className="btn btn-brass" onClick={onOpenApprovals}>Open Approvals</button>}</div></div>
    <div className="fee-management-toolbar"><div><b>{view === 'heads' ? `${heads.length} fee heads` : `${structures.length} fee structures`}</b><span>{view === 'heads' ? 'Reusable fee components' : 'Structure status and student applicability'}</span></div><div className="fee-view-switch"><button className={view === 'structures' ? 'on' : ''} onClick={() => setView('structures')}>Structures</button><button className={view === 'heads' ? 'on' : ''} onClick={() => setView('heads')}>Fee heads</button></div></div>
    {error && <p className="hint" style={{color:'var(--rose)', padding:'0 18px'}}>{error}</p>}
    {view === 'heads' ? <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Code</th><th>Name</th><th>Category</th><th>Mandatory</th><th>Status</th>{canManage && <th/>}</tr></thead><tbody>{heads.map(h => <tr key={h.id}><td className="mono">{h.code}</td><td>{h.name}</td><td>{h.category}</td><td>{h.is_mandatory ? 'Yes' : 'No'}</td><td><span className={`pill s-${h.is_active ? 'active' : 'inactive'}`}>{h.is_active ? 'Active' : 'Inactive'}</span></td>{canManage && <td><div className="row-actions"><button className="btn btn-sm btn-out" onClick={() => setHead({...h})}>Edit</button><button className="btn btn-sm btn-out" onClick={() => toggle(h)}>{h.is_active ? 'Deactivate' : 'Activate'}</button></div></td>}</tr>)}</tbody></table></div> : <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Structure</th><th>Academic context</th><th>Version</th><th>Gross Fee</th><th>Status</th><th>Updated</th>{canManage && <th/>}</tr></thead><tbody>{structures.length ? structures.map(x => <tr key={x.id}><td><b>{x.name}</b><small className="mono">{x.code}</small></td><td>{x.academic_year} · {x.semester}<small>{x.campus} · {x.program} · Batch {x.batch} · {x.student_type}</small></td><td>V{x.version}</td><td>{money(Number(x.gross_total))}</td><td><span className={`pill s-${String(x.status).toLowerCase()}`}>{x.status}</span></td><td>{x.updated_at ? new Date(x.updated_at).toLocaleDateString('en-IN') : '—'}</td>{canManage && <td><div className="row-actions"><button className="btn btn-sm btn-out" disabled={x.status !== 'DRAFT'} onClick={() => setDraft({...x, lines:x.lines.map((l:any) => ({...l, amount:String(l.amount), due_date:l.due_date || ''}))})}>View / Edit</button>{x.status === 'DRAFT' && <button className="btn btn-sm btn-brass" disabled={saving} onClick={() => submit(x.id)}>Submit for Approval</button>}{x.status === 'APPROVED' && <button className="btn btn-sm btn-brass" disabled={saving} onClick={() => publish(x.id)}>Publish / Apply</button>}{x.status === 'PUBLISHED' && <button className="btn btn-sm btn-out" onClick={() => showAffected(x.id)}>Affected Students</button>}</div></td>}</tr>) : <tr><td colSpan={canManage ? 7 : 6}><Empty text="No fee structures yet." /></td></tr>}</tbody></table></div>}
    {head && <Modal title={head.id ? 'Edit Fee Head' : 'Add Fee Head'} onClose={() => setHead(null)} footer={<><button className="btn btn-out" onClick={() => setHead(null)}>Cancel</button><button className="btn btn-crimson" disabled={saving} onClick={saveHead}>{saving ? 'Saving...' : 'Save'}</button></>}><div className="grid-2"><Field label="Code"><input className="inp" value={head.code} onChange={e=>setHead({...head,code:e.target.value})}/></Field><Field label="Name"><input className="inp" value={head.name} onChange={e=>setHead({...head,name:e.target.value})}/></Field><Field label="Category"><input className="inp" value={head.category} onChange={e=>setHead({...head,category:e.target.value})}/></Field><Field label="Display order"><input className="inp" type="number" value={head.display_order} onChange={e=>setHead({...head,display_order:Number(e.target.value)})}/></Field></div><label><input type="checkbox" checked={head.is_mandatory} onChange={e=>setHead({...head,is_mandatory:e.target.checked})}/> Mandatory</label><Field label="Description"><textarea className="inp" value={head.description} onChange={e=>setHead({...head,description:e.target.value})}/></Field></Modal>}
    {affected && <Modal title={`Affected Students (${affected.student_count})`} onClose={() => setAffected(null)} footer={<button className="btn btn-out" onClick={() => setAffected(null)}>Close</button>}><p className="hint">{affected.structure.name} · {affected.invoice_count} invoice(s) created</p><div className="affected-students-tools"><input className="inp" value={affectedSearch} onChange={e => setAffectedSearch(e.target.value)} placeholder="Search by roll number or student name" /><span>{affectedStudents.length} of {affected.student_count} students</span></div><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Roll No.</th><th>Student</th><th>Section</th><th>Invoices</th><th>Billed</th><th>Paid</th><th>Balance</th><th>Status</th></tr></thead><tbody>{affectedStudents.length ? affectedStudents.map((student:any) => <tr key={student.student_id}><td className="mono">{student.roll_no}</td><td><b>{student.name}</b><small>{student.email || '—'}</small></td><td>{student.section}</td><td>{student.invoice_count}</td><td>{money(student.invoiced)}</td><td>{money(student.paid)}</td><td>{money(student.balance)}</td><td><span className={`pill s-${student.status}`}>{student.status}</span></td></tr>) : <tr><td colSpan={8}><Empty text="No student matches this search." /></td></tr>}</tbody></table></div></Modal>}
    {draft && <Modal className="fee-structure-modal" title={draft.id ? 'Edit Draft Fee Structure' : 'Create Fee Structure'} onClose={() => setDraft(null)} footer={<><button className="btn btn-out" onClick={() => setDraft(null)}>Cancel</button><button className="btn btn-crimson" disabled={saving} onClick={saveDraft}>{saving ? 'Saving...' : 'Save Draft'}</button></>}><div className="grid-2"><Select label="Academic Year" value={draft.academic_year_id} rows={refs.academic_years} onChange={(v:string)=>setDraft({...draft,academic_year_id:v,semester_id:''})}/><Select label="Semester" value={draft.semester_id} rows={refs.semesters.filter((x:any)=>x.academic_year_id===draft.academic_year_id)} onChange={(v:string)=>setDraft({...draft,semester_id:v})}/><Select label="Campus" value={draft.campus_id} rows={refs.campuses} onChange={(v:string)=>setDraft({...draft,campus_id:v})}/><Select label="Program" value={draft.program_id} rows={refs.programs} onChange={(v:string)=>setDraft({...draft,program_id:v})}/><Select label="Batch" value={draft.batch_id} rows={refs.batches} onChange={(v:string)=>setDraft({...draft,batch_id:v})}/><Select label="Student Type" value={draft.student_type_id} rows={refs.student_types} onChange={(v:string)=>setDraft({...draft,student_type_id:v})}/><div className="fee-auto-note"><b>Structure identity</b><span>Name and code are generated automatically from the selected academic context and student type.</span></div></div><h4>Fee Lines</h4>{draft.lines.map((line:any, i:number) => <div className="grid-2" key={line.id || i}><Select label="Fee Head" value={line.fee_head_id} rows={heads.filter(h=>h.is_active)} onChange={(v:string)=>changeLine(setDraft,draft,i,'fee_head_id',v)}/><Field label="Amount"><input className="inp" type="number" min="1" value={line.amount} onChange={e=>changeLine(setDraft,draft,i,'amount',e.target.value)}/></Field><Field label="Installment #"><input className="inp" type="number" min="1" value={line.installment_no} onChange={e=>changeLine(setDraft,draft,i,'installment_no',Number(e.target.value))}/></Field><Field label="Due Date"><input className="inp" type="date" value={line.due_date} onChange={e=>changeLine(setDraft,draft,i,'due_date',e.target.value)}/></Field><button className="btn btn-sm btn-out" onClick={()=>{if(confirm('Remove this fee line?')) setDraft({...draft,lines:draft.lines.filter((_:any,n:number)=>n!==i)})}}>Remove line</button></div>)}<button className="btn btn-out" onClick={()=>setDraft({...draft,lines:[...draft.lines,{...blankLine}]})}>+ Add Fee Line</button><div className="kpi-row" style={{marginTop:16}}><div className="kpi"><div className="kpi-v">{new Set(draft.lines.map((x:any)=>x.fee_head_id).filter(Boolean)).size}</div><div className="kpi-l">Fee Heads</div></div><div className="kpi"><div className="kpi-v">{draft.lines.length}</div><div className="kpi-l">Installments</div></div><div className="kpi"><div className="kpi-v">{money(gross)}</div><div className="kpi-l">Gross Fee</div></div></div></Modal>}
  </div>
}

function Field({label, children}:any) { return <div className="form-row"><label>{label}</label>{children}</div> }
function Select({label, value, rows, onChange}:any) { return <Field label={label}><select className="select" value={value || ''} onChange={e=>onChange(e.target.value)}><option value="">Select {label}</option>{rows.map((x:any)=><option key={x.id} value={x.id}>{x.name}{x.code ? ` (${x.code})` : ''}</option>)}</select></Field> }
function changeLine(set:any, draft:any, index:number, key:string, value:any) { const lines=draft.lines.map((x:any,i:number)=>i===index?{...x,[key]:value}:x); set({...draft,lines}) }
function newDraft() { return {name:'', code:'', academic_year_id:'', semester_id:'', campus_id:'', program_id:'', batch_id:'', student_type_id:'', version:1, effective_from:'', effective_to:'', description:'', notes:'', lines:[{...blankLine}]} }
