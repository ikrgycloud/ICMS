import { useEffect, useState } from 'react'
import { HiOutlineAcademicCap, HiOutlineDocumentArrowUp, HiOutlineIdentification, HiOutlineMagnifyingGlass, HiOutlinePaperAirplane, HiOutlineUserPlus } from 'react-icons/hi2'
import { api } from '../api'
import './applicant.css'

const storageKey = 'icms_applicant_session'
const editableStates = ['DRAFT', 'CORRECTION_REQUIRED']

export default function ApplicantPortal({ onBack, authenticated = false }: { onBack: () => void; authenticated?: boolean }) {
  const [programmes, setProgrammes] = useState<any[]>([])
  const [session, setSession] = useState<any>(() => { try { return JSON.parse(localStorage.getItem(storageKey) || 'null') } catch { return null } })
  const [application, setApplication] = useState<any>(null)
  const [requirements, setRequirements] = useState<any[]>([])
  const [offer, setOffer] = useState<any>(null)
  const [finance, setFinance] = useState<any>(null)
  const [joining, setJoining] = useState<any>({ hostel_required: false, transport_required: false, pickup_point: '' })
  const [form, setForm] = useState<any>({ applicant_name: '', email: '', phone: '', date_of_birth: '', gender: '', qualifying_percentage: '' })
  const [programme, setProgramme] = useState('')
  const [additionalProgramme, setAdditionalProgramme] = useState('')
  const [lookup, setLookup] = useState({ application_no: '', email: '' })
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { api.openAdmissionPrograms().then((r: any) => setProgrammes(r.programmes || [])).catch(() => setNotice('Admissions are not open at the moment.')) }, [])
  useEffect(() => {
    if (!authenticated || session) return
    api.applicantSession().then(persist).catch((error: any) => setNotice(error.message || 'Applicant session could not be started.'))
  }, [authenticated, session])
  useEffect(() => { if (session) void reload() }, [session])
  const app = application?.application || application
  const status = app?.current_status || 'DRAFT'
  const version = app?.status_version ?? 0
  const editable = editableStates.includes(status)
  const joiningOpen = ['OFFER_ACCEPTED', 'FEE_RESOLUTION_PENDING', 'INVOICE_ISSUED', 'PAYMENT_PENDING', 'PAYMENT_RECORDED', 'ACCOUNTS_VERIFIED', 'FINANCE_CLEARED', 'FINAL_APPROVAL_PENDING', 'READY_TO_ADMIT'].includes(status)
  const joiningSubmitted = Boolean(joining.submitted_at)
  const update = (name: string, value: string) => setForm((current: any) => ({ ...current, [name]: value }))
  const persist = (value: any) => { localStorage.setItem(storageKey, JSON.stringify(value)); setSession(value) }

  async function reload() {
    try {
      const detail = await api.applicantApplication(session.application_id, session.access_token)
      setApplication(detail)
      setForm((current: any) => ({ ...current, applicant_name: detail.applicant_name || current.applicant_name, email: detail.email || current.email, phone: detail.phone || current.phone, date_of_birth: detail.date_of_birth || current.date_of_birth, gender: detail.gender || current.gender, qualifying_percentage: detail.profile?.qualifying_percentage || current.qualifying_percentage }))
      const [docs, offerDetail, financeDetail] = await Promise.all([
        api.applicantRequirements(session.application_id, session.access_token),
        api.applicantOffer(session.application_id, session.access_token),
        api.applicantFinance(session.application_id, session.access_token),
      ])
      setRequirements(docs.requirements || [])
      setOffer(offerDetail.offer || null)
      setFinance(financeDetail)
      setJoining(detail.profile?.joining_preferences || { hostel_required: false, transport_required: false, pickup_point: '' })
    } catch {
      localStorage.removeItem(storageKey); setSession(null); setNotice('Your applicant session is no longer available. Please create a new application.')
    }
  }
  async function start() {
    if (!programme || !form.applicant_name.trim() || !form.email.trim()) return setNotice('Enter your name, personal email, and chosen programme.')
    setBusy(true)
    try {
      const next = await api.startApplicantApplication({ cycle_program_id: programme, applicant_name: form.applicant_name, email: form.email })
      const selected = programmes.find(item => item.id === programme)
      if (selected?.program_id) await api.addApplicantPreference(next.application_id, next.access_token, { program_id: selected.program_id, expected_status_version: 0 })
      persist(next); setNotice(`Application created successfully. Save application number ${next.application_no}. ${next.email_sent ? `A confirmation was sent to ${form.email}.` : 'Keep this number with your personal email to check status later.'}`)
    } catch (e: any) { setNotice(e.message) } finally { setBusy(false) }
  }
  async function saveProfile() {
    setBusy(true)
    try { await api.saveApplicantProfile(session.application_id, session.access_token, { ...form, date_of_birth: form.date_of_birth || null, profile: { qualifying_percentage: Number(form.qualifying_percentage || 0) }, expected_status_version: version }); await reload(); setNotice('Profile saved.') } catch (e: any) { setNotice(e.message) } finally { setBusy(false) }
  }
  async function addDocument(requirement: any, file?: File) {
    if (!file) return
    setBusy(true)
    try {
      const content_base64 = await encodeFile(file)
      await api.addApplicantDocument(session.application_id, session.access_token, { requirement_id: requirement.id, document_type: requirement.document_type, storage_key: `applicant/${session.application_id}/${Date.now()}-${file.name}`, file_name: file.name, mime_type: file.type || 'application/octet-stream', content_base64, expected_status_version: version })
      await reload(); setNotice(`${requirement.document_type} submitted for verification.`)
    } catch (e: any) { setNotice(e.message) } finally { setBusy(false) }
  }
  async function submit() { if (!form.phone.trim()) return setNotice('Add your mobile number in Applicant details before submitting.'); setBusy(true); try { await api.submitApplicantApplication(session.application_id, session.access_token, version); await reload(); setNotice('Application submitted to the Admission Office.') } catch (e: any) { setNotice(e.message) } finally { setBusy(false) } }
  async function addPreference() { if (!additionalProgramme) return; setBusy(true); try { await api.addApplicantPreference(session.application_id, session.access_token, { program_id: additionalProgramme, expected_status_version: version }); setAdditionalProgramme(''); await reload(); setNotice('Programme preference added.') } catch (e: any) { setNotice(e.message) } finally { setBusy(false) } }
  async function recover() { if (!lookup.application_no || !lookup.email) return setNotice('Enter the application number and the same personal email used during application.'); setBusy(true); try { const next = await api.recoverApplicantAccess(lookup); persist(next); setNotice(`Application ${next.application_no} restored. Your latest status is now visible.`) } catch (e: any) { setNotice(e.message) } finally { setBusy(false) } }
  async function respond(response: 'accept' | 'decline') { setBusy(true); try { const result = await api.respondApplicantOffer(session.application_id, session.access_token, response, version); await reload(); setNotice(response === 'accept' ? (result.email_sent ? 'Offer accepted. Your seat reservation confirmation was sent to your personal email.' : 'Offer accepted. Your seat is reserved; continue with joining preferences and fee processing.') : 'Offer declined. The seat has been released.') } catch (e: any) { setNotice(e.message) } finally { setBusy(false) } }
  async function saveJoiningPreferences() { setBusy(true); try { await api.saveApplicantJoiningPreferences(session.application_id, session.access_token, { ...joining, expected_status_version: version }); await reload(); setNotice('Joining preferences saved. Hostel and transport teams will confirm availability after enrollment.') } catch (e: any) { setNotice(e.message) } finally { setBusy(false) } }

  return <main className="applicant-shell">
    <header className="applicant-header"><button onClick={onBack}>Back to ICMS</button><div><b>ICMS Admissions</b><span>Applicant Portal</span></div><span className="applicant-help">admissions@icms.edu</span></header>
    <section className="applicant-hero"><div><p className="eyebrow">Admissions 2026</p><h1>Your journey from application to enrollment.</h1><p>Submit your application, provide documents, accept an offer, and receive your student account at your personal email.</p></div><div className="journey-mini"><span>1. Apply</span><span>2. Verify</span><span>3. Select</span><span>4. Enroll</span></div></section>
    {notice && <div className="applicant-notice">{notice}</div>}
    {status === 'CORRECTION_REQUIRED' && <CorrectionNotice history={app?.history || []} />}
    {!session ? <section className="applicant-entry-grid"><section className="applicant-card apply-start"><div><p className="eyebrow">Start here</p><h2>Create an applicant account</h2><p>Use your personal email. We display and email your application number after creation. Keep both to check application status later.</p></div><div className="applicant-form"><label>Full legal name<input value={form.applicant_name} onChange={e => update('applicant_name', e.target.value)} /></label><label>Personal email<input type="email" value={form.email} onChange={e => update('email', e.target.value)} /></label><label>Programme<select value={programme} onChange={e => setProgramme(e.target.value)}><option value="">Choose an open programme</option>{programmes.map(item => <option key={item.id} value={item.id}>{item.program} - {item.campus} ({item.cycle})</option>)}</select></label><button className="applicant-primary" disabled={busy} onClick={start}><HiOutlineUserPlus /> {busy ? 'Creating...' : 'Create application'}</button></div></section><section className="applicant-card lookup-card"><p className="eyebrow">Returning applicant</p><h2>Check application status</h2><p>Enter the application number and personal email used when you applied.</p><div className="applicant-form"><label>Application number<input value={lookup.application_no} onChange={e => setLookup({ ...lookup, application_no: e.target.value })} placeholder="APP-2026-..." /></label><label>Personal email<input type="email" value={lookup.email} onChange={e => setLookup({ ...lookup, email: e.target.value })} /></label><button className="applicant-secondary" disabled={busy} onClick={recover}><HiOutlineMagnifyingGlass /> View application status</button></div></section></section> : <section className="applicant-workspace">
      <aside className="applicant-status"><span>Application number</span><strong>{app?.application_no}</strong><b className="status-pill">{status.replaceAll('_', ' ')}</b><p><b>{statusMessage(status)}</b></p><p>Programme: {app?.program || 'Pending selection'}<br />Campus: {app?.campus || 'Pending'}</p><button onClick={() => { localStorage.removeItem(storageKey); setSession(null); setApplication(null); setOffer(null); setFinance(null) }}>Check another application</button></aside>
      <div className="applicant-main">
        <StatusDashboard app={app} status={status} offer={offer} finance={finance} />
        {editable && <>
        <Stage title={status === 'CORRECTION_REQUIRED' ? '1. Update requested details' : '1. Applicant details'} icon={<HiOutlineIdentification />} badge={status === 'CORRECTION_REQUIRED' ? 'Correction required' : 'Editable'}><div className="applicant-grid"><label>Full legal name<input value={form.applicant_name} onChange={e => update('applicant_name', e.target.value)} /></label><label>Personal email<input value={form.email} onChange={e => update('email', e.target.value)} /></label><label>Mobile number<input value={form.phone} onChange={e => update('phone', e.target.value)} /></label><label>Date of birth<input type="date" value={form.date_of_birth} onChange={e => update('date_of_birth', e.target.value)} /></label><label>Gender<select value={form.gender} onChange={e => update('gender', e.target.value)}><option value="">Select</option><option>Female</option><option>Male</option><option>Other</option></select></label><label>Qualifying percentage<input type="number" value={form.qualifying_percentage} onChange={e => update('qualifying_percentage', e.target.value)} /></label></div><button className="applicant-secondary" disabled={busy} onClick={saveProfile}>Save updated details</button></Stage>
        <Stage title="2. Programme preferences" icon={<HiOutlineAcademicCap />} badge={`${(app?.preferences || []).length} selected`}><div className="preference-list">{(app?.preferences || []).map((item: any) => <div key={item.id}><b>Preference #{item.rank}</b><span>{item.program}</span></div>)}</div>{editable && <div className="inline-form"><select value={additionalProgramme} onChange={e => setAdditionalProgramme(e.target.value)}><option value="">Add another programme preference</option>{programmes.map(item => <option key={item.id} value={item.program_id}>{item.program} - {item.campus}</option>)}</select><button className="applicant-secondary" disabled={busy || !additionalProgramme} onClick={addPreference}>Add preference</button></div>}</Stage>
        <Stage title={status === 'CORRECTION_REQUIRED' ? '3. Replace or upload corrected documents' : '3. Document upload'} icon={<HiOutlineDocumentArrowUp />} badge={`${(app?.documents || []).length}/${requirements.length} supplied`}><div className="document-list">{requirements.map(requirement => { const document = (app?.documents || []).find((item: any) => item.requirement_id === requirement.id); return <div className="document-row" key={requirement.id}><div><b>{requirement.document_type}</b><small>{document ? `${document.file_name} - ${document.verification_status || 'Pending verification'}` : requirement.mandatory ? 'Required' : 'Optional'}</small></div>{editable ? <label className="upload-button">{document ? 'Replace file' : 'Choose file'}<input type="file" onChange={e => addDocument(requirement, e.target.files?.[0])} /></label> : <span>{document ? 'Received' : 'Not supplied'}</span>}</div> })}</div></Stage>
        <Stage title={status === 'CORRECTION_REQUIRED' ? '4. Resubmit corrections' : '4. Declaration and submission'} icon={<HiOutlinePaperAirplane />} badge={status === 'DRAFT' ? 'Action required' : status === 'CORRECTION_REQUIRED' ? 'Action required' : 'Complete'}><p className="stage-copy">{status === 'CORRECTION_REQUIRED' ? 'After updating the requested details and documents, submit the corrected application. It will return to the Admission Office for review.' : 'By submitting, you confirm that your details and documents are correct. The Admission Office will review them and may request a correction.'}</p><button className="applicant-primary" disabled={busy} onClick={submit}><HiOutlinePaperAirplane /> {status === 'CORRECTION_REQUIRED' ? 'Resubmit corrected application' : 'Submit application for review'}</button></Stage>
        </>}
        {['OFFER_RECOMMENDATION_PENDING', 'OFFER_APPROVAL_PENDING'].includes(status) && <Stage title="Admission offer" icon={<HiOutlineAcademicCap />} badge="Approval in progress"><p className="stage-copy">Your seat has been allocated and the Admission Office is completing the offer approval. Your offer number, acceptance deadline, and Accept / Decline actions will appear here as soon as the offer is issued.</p></Stage>}
        {offer && <Stage title="Admission offer" icon={<HiOutlineAcademicCap />} badge={offer.status === 'ISSUED' ? 'Offer available' : offer.status}><div className="status-details"><span><b>Offer number</b>{offer.offer_no}</span><span><b>Programme</b>{offer.programme}</span><span><b>Campus</b>{offer.campus}</span><span><b>Accept by</b>{offer.expires_at ? new Date(offer.expires_at).toLocaleString() : 'See Admission Office'}</span></div>{offer.terms?.length > 0 && <p className="stage-copy">{offer.terms.join(' ')}</p>}{status === 'OFFERED' && <div className="offer-actions"><button className="applicant-primary" disabled={busy} onClick={() => respond('accept')}>Accept offer</button><button className="applicant-secondary" disabled={busy} onClick={() => respond('decline')}>Decline offer</button></div>}</Stage>}
        {finance?.invoice && <Stage title="Admission fees" icon={<HiOutlinePaperAirplane />} badge={finance.invoice.status || 'Pending'}><div className="status-details"><span><b>Invoice amount</b>₹{Number(finance.invoice.amount || 0).toLocaleString('en-IN')}</span><span><b>Paid</b>₹{Number(finance.invoice.paid || 0).toLocaleString('en-IN')}</span><span><b>Balance</b>₹{Number(finance.invoice.balance || 0).toLocaleString('en-IN')}</span><span><b>Challan</b>{finance.challan?.number || 'Being generated'}</span></div><p className="stage-copy">Contact the Accounts Office with your application number and challan reference for payment assistance.</p></Stage>}
        {joiningOpen && !joiningSubmitted && <Stage title="Joining preferences" icon={<HiOutlineIdentification />} badge="Action requested"><p className="stage-copy">Tell us whether you need hostel accommodation or college transport. These are requests; final room and route allocation depends on availability.</p><div className="applicant-grid"><label>Hostel accommodation<select value={String(joining.hostel_required)} onChange={e => setJoining({ ...joining, hostel_required: e.target.value === 'true' })}><option value="false">Not required</option><option value="true">Required</option></select></label><label>College transport<select value={String(joining.transport_required)} onChange={e => setJoining({ ...joining, transport_required: e.target.value === 'true' })}><option value="false">Not required</option><option value="true">Required</option></select></label><label>Preferred pickup point<input value={joining.pickup_point || ''} disabled={!joining.transport_required} onChange={e => setJoining({ ...joining, pickup_point: e.target.value })} placeholder="Area, stop, or landmark" /></label></div><button className="applicant-secondary" disabled={busy} onClick={saveJoiningPreferences}>Save joining preferences</button></Stage>}
        {status === 'ENROLLED' && <Stage title="Enrollment complete" icon={<HiOutlineUserPlus />} badge="Student account created"><div className="credential-note"><b>Your student account is ready.</b><br />Student ID: {app?.enrollment?.student_id || 'Sent by email'}<br />Academic section: {app?.enrollment?.section || 'Assignment pending'}<br />Hostel: {app?.enrollment?.hostel_status || 'Not requested'}<br />Transport: {app?.enrollment?.transport_status || 'Not requested'}<br />Account activation details have been sent to {form.email}.</div></Stage>}
      </div>
    </section>}
  </main>
}

function Progress({ status }: { status: string }) {
  const order = ['DRAFT','SUBMITTED','REVIEW_IN_PROGRESS','DOCUMENT_VERIFIED','ELIGIBILITY_PENDING','ELIGIBLE','ASSESSMENT_PENDING','COUNSELLING_PENDING','ALLOCATION_PENDING','ALLOCATED','OFFER_RECOMMENDATION_PENDING','OFFER_APPROVAL_PENDING','OFFERED','OFFER_ACCEPTED','FEE_RESOLUTION_PENDING','PAYMENT_PENDING','FINANCE_CLEARED','FINAL_APPROVAL_PENDING','READY_TO_ADMIT','ENROLLED']
  const steps = [['SUBMITTED','Application'],['DOCUMENT_VERIFIED','Documents'],['ELIGIBLE','Eligibility'],['ALLOCATED','Seat'],['OFFERED','Offer'],['FINANCE_CLEARED','Finance'],['ENROLLED','Student account']]
  const rank = order.indexOf(status)
  return <div className="progress-list">{steps.map(([state, label], index) => <div key={state} className={rank >= order.indexOf(state) ? 'complete' : ''}><span>{index + 1}</span>{label}</div>)}</div>
}

function statusMessage(status: string) {
  const messages: Record<string, string> = {
    DRAFT: 'Complete your details and documents, then submit the application.', SUBMITTED: 'Your application is with the Admission Office for review.', CORRECTION_REQUIRED: 'A correction is required before review can continue.', DOCUMENT_VERIFIED: 'Documents verified. Eligibility is being evaluated.', ELIGIBILITY_PENDING: 'Eligibility evaluation is in progress.', ELIGIBLE: 'You are eligible. Assessment, merit, or counselling will proceed next.', ALLOCATION_PENDING: 'Merit and seat allocation are in progress.', ALLOCATED: 'A seat has been reserved. Your offer is being prepared.', OFFER_RECOMMENDATION_PENDING: 'Your allocated seat is being prepared for offer approval.', OFFER_APPROVAL_PENDING: 'Your seat is allocated. The Admission Office is approving your offer; no action is needed from you yet.', OFFERED: 'Review the offer details and accept or decline before it expires.', OFFER_ACCEPTED: 'Offer accepted. Complete joining preferences and wait for the fee invoice.', PAYMENT_PENDING: 'Your admission fee invoice is ready for payment.', FINAL_APPROVAL_PENDING: 'Finance is complete and final approval is in progress.', READY_TO_ADMIT: 'All checks are complete. Your student account is being created.', ENROLLED: 'Enrollment is complete. Your student account details are available below.',
  }
  return messages[status] || 'Your application is progressing through the admissions process.'
}

function StatusDashboard({ app, status, offer, finance }: any) {
  const offerStatus = offer?.status || (['OFFER_RECOMMENDATION_PENDING', 'OFFER_APPROVAL_PENDING'].includes(status) ? 'Approval in progress' : 'Not issued')
  return <section className="applicant-card status-dashboard"><div><p className="eyebrow">Live application status</p><h2>{status.replaceAll('_', ' ')}</h2><p>{statusMessage(status)}</p></div><div className="status-details"><span><b>Application</b>{app?.application_no}</span><span><b>Documents</b>{app?.document_completeness?.uploaded || 0}/{app?.document_completeness?.required || 0} uploaded</span><span><b>Offer</b>{offerStatus}</span><span><b>Fees</b>{finance?.invoice ? `Balance Rs. ${Number(finance.invoice.balance || 0).toLocaleString('en-IN')}` : 'Not invoiced'}</span></div></section>
}

function Stage({ title, icon, badge, children }: { title: string; icon: any; badge: string; children: any }) {
  return <section className="applicant-card stage-card"><div className="section-title"><div className="stage-heading"><span className="stage-icon">{icon}</span><div><p className="eyebrow">Applicant journey</p><h2>{title}</h2></div></div><span>{badge}</span></div>{children}</section>
}

function SubmissionMessage({ applicationNo, email, status }: { applicationNo: string; email: string; status: string }) {
  return <div className="submission-message"><b>Application submitted successfully.</b><span>Application number: <strong>{applicationNo}</strong></span><span>Save this number with your personal email: {email}</span><small>Current status: {status.replaceAll('_', ' ')}. You can return anytime using the application number and email.</small></div>
}

function CorrectionNotice({ history }: { history: any[] }) {
  const correction = [...history].reverse().find(item => item.action === 'request_correction')
  return <div className="applicant-notice"><b>Action required: correction requested by the Admission Office</b><br />{correction?.reason || 'Please review and update the requested application details.'}<br /><small>Update the relevant details or replace the requested documents below, then select <b>Resubmit corrected application</b>.</small></div>
}


async function encodeFile(file: File) {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ''
  for (let index = 0; index < bytes.length; index += 8192) binary += String.fromCharCode(...bytes.subarray(index, index + 8192))
  return btoa(binary)
}
