import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
<<<<<<< HEAD
import { Empty, Kpis, Modal, PageHead, Pill, Spinner } from './kit'

const CATEGORIES = ['Planning', 'Registration', 'Teaching', 'Assessment', 'Examinations', 'Review', 'Results', 'Break', 'Experiential']

function blankForm(term = '') {
  const today = new Date().toISOString().slice(0, 10)
  return {
    id: '',
    term,
    title: '',
    category: 'Teaching',
    campus: 'All Campuses',
    start_date: today,
    end_date: today,
    description: '',
    status: 'published',
  }
}

export default function AcademicCalendar({ user, caps }: { user: any; caps: any }) {
  const [term, setTerm] = useState('')
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [detail, setDetail] = useState<any>(null)
  const [form, setForm] = useState<any>(blankForm())

  async function load(targetTerm = term) {
    setLoading(true)
    setError('')
    try {
      const next = await api.academicCalendar(targetTerm)
      setData(next)
      if (!targetTerm && next?.selected_term) {
        setTerm(next.selected_term)
        setForm(blankForm(next.selected_term))
      }
    } catch (err: any) {
      setError(err?.message || 'We could not load the academic calendar.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(term)
  }, [term])

  const groups = useMemo(() => {
    const out: Record<string, any[]> = {}
    ;(data?.entries || []).forEach((entry: any) => {
      const label = new Date(`${entry.start_date}T00:00:00`).toLocaleString('en-IN', { month: 'long', year: 'numeric' })
      ;(out[label] = out[label] || []).push(entry)
    })
    return out
  }, [data])

  const canCreate = Boolean(data?.permissions?.create && caps?.create)
  const canEdit = Boolean(data?.permissions?.edit && caps?.edit)
  const canDelete = Boolean(data?.permissions?.delete && caps?.delete)

  function openCreate() {
    setForm(blankForm(data?.selected_term || term))
    setDetail(null)
    setShowModal(true)
  }

  function openEntry(entry: any) {
    if (entry.editable && canEdit) {
      setForm({
        id: entry.id,
        term: entry.term,
        title: entry.title,
        category: entry.category,
        campus: entry.campus,
        start_date: entry.start_date,
        end_date: entry.end_date,
        description: entry.description || '',
        status: entry.status || 'published',
      })
      setDetail(null)
    } else {
      setDetail(entry)
    }
    setShowModal(true)
  }

  async function saveEntry() {
    setSaving(true)
    try {
      if (form.id) await api.updateAcademicCalendarEntry(form.id, form)
      else await api.createAcademicCalendarEntry(form)
      setShowModal(false)
      setForm(blankForm(data?.selected_term || term))
      await load()
    } catch (err: any) {
      setError(err?.message || 'We could not save the academic calendar entry.')
    } finally {
      setSaving(false)
    }
  }

  async function removeEntry() {
    if (!form.id) return
    setSaving(true)
    try {
      await api.deleteAcademicCalendarEntry(form.id)
      setShowModal(false)
      setForm(blankForm(data?.selected_term || term))
      await load()
    } catch (err: any) {
      setError(err?.message || 'We could not delete the academic calendar entry.')
    } finally {
      setSaving(false)
    }
  }

  if (loading && !data) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead
        title="Academic Calendar"
        sub={`Governed academic timeline for ${user.active_role}. The Vice Chairman, Principal, and Vice Principal typically manage this schedule, while the Chairman retains full control.`}
        right={
          <div className="calendar-head-actions">
            {data?.term_options?.length > 0 && (
              <select className="select academic-term-select" value={data.selected_term} onChange={e => setTerm(e.target.value)}>
                {data.term_options.map((option: string) => <option key={option} value={option}>{option}</option>)}
              </select>
            )}
            {canCreate && <button className="btn btn-crimson" onClick={openCreate} type="button">Add milestone</button>}
          </div>
        }
      />

      {error && <div className="calendar-banner warn">{error}</div>}

      {data && (
        <>
          <Kpis items={[
            { label: 'Selected term', value: data.selected_term || '—' },
            { label: 'Milestones', value: data.summary.milestones },
            { label: 'Exam windows', value: data.summary.exam_windows },
            { label: 'Breaks', value: data.summary.breaks },
          ]} />

          <div className="calendar-banner" style={{ marginTop: 22 }}>
            <strong>Governance model:</strong> {data.summary.governed_by}. The backend enforces edit access and every change is audited and pushed as a live notification.
          </div>

          <div className="acad-layout" style={{ marginTop: 22 }}>
            <section className="card">
              <div className="card-h">
                <h3>Term timeline</h3>
                <span className="hint">{data.term_window.start} to {data.term_window.end}</span>
              </div>
              <div className="acad-timeline">
                {Object.keys(groups).length === 0 && <Empty icon="🗓" text="No academic milestones for this term" />}
                {Object.entries(groups).map(([label, entries]) => (
                  <div className="acad-month-group" key={label}>
                    <div className="acad-month-title">{label}</div>
                    {(entries as any[]).map(entry => (
                      <button className="acad-entry" key={entry.id} onClick={() => openEntry(entry)} type="button">
                        <div className={`acad-entry-rail ${categoryTone(entry.category)}`} />
                        <div className="acad-entry-date">
                          <b>{new Date(`${entry.start_date}T00:00:00`).toLocaleString('en-IN', { day: '2-digit', month: 'short' })}</b>
                          <span>{spanLabel(entry.start_date, entry.end_date)}</span>
                        </div>
                        <div className="acad-entry-copy">
                          <div className="acad-entry-top">
                            <strong>{entry.title}</strong>
                            <Pill s={entry.status || 'published'} />
                          </div>
                          <div className="acad-entry-meta">{entry.category} · {entry.campus}</div>
                          <p>{entry.description}</p>
                        </div>
                        {entry.editable && canEdit && <span className="acad-edit-tag">Edit</span>}
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            </section>

            <div className="acad-side">
              <section className="card">
                <div className="card-h">
                  <h3>Monthly spread</h3>
                  <span className="hint">live count</span>
                </div>
                <div className="card-pad">
                  {(data.months || []).length ? data.months.map((item: any) => (
                    <div className="snap" key={item.label}><span>{item.label}</span><b>{item.count}</b></div>
                  )) : <Empty icon="◇" text="No monthly spread yet" />}
                </div>
              </section>

              <section className="card">
                <div className="card-h">
                  <h3>Editors</h3>
                  <span className="hint">authority-controlled</span>
                </div>
                <div className="card-pad">
                  <div className="chips">
                    {(data.editors || []).map((editor: string) => <span className="chip" key={editor}>{editor}</span>)}
                  </div>
                  <div className="acad-note">
                    Everyone can view the academic calendar through the shared workspace. Only the governing offices above can create, change, or remove entries.
                  </div>
                </div>
              </section>
            </div>
          </div>
        </>
      )}

      {showModal && !detail && (
        <Modal
          title={form.id ? 'Edit Academic Milestone' : 'Add Academic Milestone'}
          onClose={() => {
            setShowModal(false)
            setForm(blankForm(data?.selected_term || term))
          }}
          footer={
            <>
              {form.id && canDelete && <button className="btn btn-rose" onClick={removeEntry} disabled={saving}>Delete</button>}
              <button className="btn btn-out" onClick={() => setShowModal(false)} disabled={saving}>Cancel</button>
              <button className="btn btn-crimson" onClick={saveEntry} disabled={saving}>{saving ? 'Saving...' : 'Save milestone'}</button>
            </>
          }
        >
          <div className="form-row">
            <label>Title</label>
            <input className="inp" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
          </div>
          <div className="grid-2">
            <div className="form-row">
              <label>Term</label>
              <input className="inp" value={form.term} onChange={e => setForm({ ...form, term: e.target.value })} />
            </div>
            <div className="form-row">
              <label>Category</label>
              <select className="select" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                {CATEGORIES.map(option => <option key={option} value={option}>{option}</option>)}
              </select>
            </div>
          </div>
          <div className="grid-2">
            <div className="form-row">
              <label>Start date</label>
              <input className="inp" type="date" value={form.start_date} onChange={e => setForm({ ...form, start_date: e.target.value })} />
            </div>
            <div className="form-row">
              <label>End date</label>
              <input className="inp" type="date" value={form.end_date} onChange={e => setForm({ ...form, end_date: e.target.value })} />
            </div>
          </div>
          <div className="form-row">
            <label>Campus / scope</label>
            <input className="inp" value={form.campus} onChange={e => setForm({ ...form, campus: e.target.value })} />
          </div>
          <div className="form-row">
            <label>Description</label>
            <textarea className="inp" rows={4} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          </div>
        </Modal>
      )}

      {showModal && detail && (
        <Modal title="Milestone details" onClose={() => { setShowModal(false); setDetail(null) }}>
          <div className="calendar-detail">
            <div className="calendar-detail-top">
              <Pill s={detail.status || 'published'} />
              <span className={`calendar-source-chip ${categoryTone(detail.category)}`}>{detail.category}</span>
            </div>
            <h3>{detail.title}</h3>
            <p>{detail.description || 'No additional notes were provided for this milestone.'}</p>
            <div className="snap"><span>Term</span><b>{detail.term}</b></div>
            <div className="snap"><span>Date range</span><b>{spanLabel(detail.start_date, detail.end_date)}</b></div>
            <div className="snap"><span>Campus</span><b>{detail.campus}</b></div>
          </div>
        </Modal>
      )}
    </div>
  )
}

function spanLabel(start: string, end: string) {
  const a = new Date(`${start}T00:00:00`)
  const b = new Date(`${end}T00:00:00`)
  if (start === end) return a.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
  return `${a.toLocaleString('en-IN', { day: '2-digit', month: 'short' })} - ${b.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}`
}

function categoryTone(category: string) {
  const lower = category.toLowerCase()
  if (lower.includes('exam') || lower.includes('assessment')) return 'linked'
  if (lower.includes('break') || lower.includes('result')) return 'manual'
  return 'academic'
}
=======
import { Empty, Modal, PageHead, Pill, Spinner } from './kit'

const CATEGORIES = ['Planning', 'Registration', 'Teaching', 'Assessment', 'Examinations', 'Review', 'Results', 'Break', 'Experiential']
const blank = (term = '') => ({ id: '', term, title: '', category: 'Teaching', campus: 'All Campuses', start_date: new Date().toISOString().slice(0, 10), end_date: new Date().toISOString().slice(0, 10), description: '', status: 'published' })

export default function AcademicCalendar({ caps }: { user: any; caps: any }) {
  const [term, setTerm] = useState(''), [data, setData] = useState<any>(null), [loading, setLoading] = useState(true), [error, setError] = useState('')
  const [category, setCategory] = useState('All'), [campus, setCampus] = useState('All Campuses'), [form, setForm] = useState<any>(blank()), [detail, setDetail] = useState<any>(null), [modal, setModal] = useState(false), [saving, setSaving] = useState(false)
  async function load(value = term) { setLoading(true); try { const next = await api.academicCalendar(value); setData(next); if (!value && next.selected_term) setTerm(next.selected_term) } catch (e:any) { setError(e.message || 'We could not load the academic calendar.') } finally { setLoading(false) } }
  useEffect(() => { load(term) }, [term])
  const campuses = useMemo<string[]>(() => ['All Campuses', ...Array.from(new Set<string>((data?.entries || []).map((x:any) => String(x.campus)).filter(Boolean)))], [data])
  const entries = useMemo(() => (data?.entries || []).filter((x:any) => (category === 'All' || x.category === category) && (campus === 'All Campuses' || x.campus === campus || x.campus === 'All Campuses')), [data, category, campus])
  const groups = useMemo(() => entries.reduce((o:Record<string,any[]>, x:any) => { const k = new Date(`${x.start_date}T00:00:00`).toLocaleString('en-IN',{month:'long',year:'numeric'}); (o[k] ||= []).push(x); return o }, {}), [entries])
  const pending = useMemo(() => (data?.entries || []).filter((x:any) => String(x.status).toLowerCase().includes('pending')), [data])
  const upcoming = useMemo(() => (data?.entries || []).filter((x:any) => new Date(`${x.start_date}T00:00:00`) >= new Date()).slice(0,4), [data])
  const canCreate = !!(data?.permissions?.create && caps?.create), canEdit = !!(data?.permissions?.edit && caps?.edit), canDelete = !!(data?.permissions?.delete && caps?.delete)
  function open(x:any) { if(x.editable && canEdit) { setForm({id:x.id,term:x.term,title:x.title,category:x.category,campus:x.campus,start_date:x.start_date,end_date:x.end_date,description:x.description || '',status:x.status || 'published'}); setDetail(null) } else setDetail(x); setModal(true) }
  async function save() { setSaving(true); try { form.id ? await api.updateAcademicCalendarEntry(form.id,form) : await api.createAcademicCalendarEntry(form); setModal(false); await load() } catch(e:any) { setError(e.message || 'Could not save the event.') } finally { setSaving(false) } }
  async function remove() { setSaving(true); try { await api.deleteAcademicCalendarEntry(form.id); setModal(false); await load() } catch(e:any) { setError(e.message || 'Could not delete the event.') } finally { setSaving(false) } }
  if (loading && !data) return <Spinner />
  return <div className="fade-in academic-calendar-ref"><PageHead title="Academic Calendar" sub="Institution-wide academic dates, examinations, teaching periods, holidays, and academic milestones." right={<div className="calendar-head-actions academic-filter-bar"><label>Academic year<select className="select academic-term-select" value={data?.selected_term || ''} onChange={e=>setTerm(e.target.value)}>{data?.term_options?.map((x:string)=><option key={x}>{x}</option>)}</select></label><label>Campus<select className="select" value={campus} onChange={e=>setCampus(e.target.value)}>{campuses.map(x=><option key={x}>{x}</option>)}</select></label>{canCreate && <button className="btn btn-crimson" onClick={()=>{setForm(blank(data.selected_term));setDetail(null);setModal(true)}}>Add Academic Event</button>}</div>} />
    {error && <div className="calendar-banner warn">{error}</div>}{data && <><div className="academic-kpis"><Metric i="▣" n={data.summary.milestones} t="Academic Events"/><Metric i="◷" n={upcoming.length} t="Upcoming Events"/><Metric i="▤" n={data.summary.exam_windows} t="Exam Windows"/><Metric i="!" n={pending.length} t="Pending Approval"/><Metric i="☂" n={data.summary.breaks} t="Holidays / Breaks"/></div>
    <div className="acad-layout"><section className="card"><div className="academic-tabs"><button className="active">Timeline</button><span/>{['All','Teaching','Examinations','Registration','Results','Break','Review'].map(x=><button className={`academic-category ${category===x?'selected':''}`} onClick={()=>setCategory(x)} key={x}>{x==='Break'?'Holidays':x}</button>)}</div><div className="card-h academic-timeline-head"><h3>Term Timeline</h3><span className="hint">{entries.length} events</span></div><div className="acad-timeline">{!Object.keys(groups).length && <Empty icon="Calendar" text="No academic milestones match these filters"/>}{Object.entries(groups).map(([month,list])=><div className="acad-month-group" key={month}><div className="acad-month-title">{month}</div>{(list as any[]).map(x=><button className="acad-entry" onClick={()=>open(x)} key={x.id}><div className={`acad-entry-rail ${tone(x.category)}`}/><div className="acad-entry-date"><b>{new Date(`${x.start_date}T00:00:00`).toLocaleDateString('en-IN',{day:'2-digit',month:'short'})}</b><span>{dates(x.start_date,x.end_date)}</span></div><div className="acad-entry-copy"><div className="acad-entry-top"><strong>{x.title}</strong><Pill s={x.status || 'published'}/></div><div className="acad-entry-meta">{x.category} · {x.campus}</div><p>{x.description}</p></div><span className="acad-edit-tag">{x.editable && canEdit?'Edit':'View'}</span></button>)}</div>)}</div></section><aside className="acad-side"><Side title={`Requires Your Attention${pending.length?` (${pending.length})`:''}`} rows={pending} empty="No approvals are waiting" open={open} showPill/><Side title="Upcoming Academic Activity" rows={upcoming} empty="No upcoming activity in this term" open={open}/><section className="card"><div className="card-h"><h3>Calendar Governance</h3></div><div className="card-pad academic-governance"><div className="snap"><span>Owner</span><b>Academic Office</b></div><div className="snap"><span>Approval authority</span><b>Principal</b></div><div className="snap"><span>Pending changes</span><b>{pending.length}</b></div><p>Changes follow role permissions and are recorded in the audit trail.</p></div></section></aside></div></>}
    {modal && !detail && <Modal title={form.id?'Edit Academic Event':'Add Academic Event'} onClose={()=>setModal(false)} footer={<>{form.id && canDelete && <button className="btn btn-rose" disabled={saving} onClick={remove}>Delete</button>}<button className="btn btn-out" onClick={()=>setModal(false)}>Cancel</button><button className="btn btn-crimson" disabled={saving} onClick={save}>{saving?'Saving...':'Save event'}</button></>}><Field label="Title"><input className="inp" value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></Field><div className="grid-2"><Field label="Term"><input className="inp" value={form.term} onChange={e=>setForm({...form,term:e.target.value})}/></Field><Field label="Category"><select className="select" value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>{CATEGORIES.map(x=><option key={x}>{x}</option>)}</select></Field></div><div className="grid-2"><Field label="Start date"><input className="inp" type="date" value={form.start_date} onChange={e=>setForm({...form,start_date:e.target.value})}/></Field><Field label="End date"><input className="inp" type="date" value={form.end_date} onChange={e=>setForm({...form,end_date:e.target.value})}/></Field></div><Field label="Campus / scope"><input className="inp" value={form.campus} onChange={e=>setForm({...form,campus:e.target.value})}/></Field><Field label="Description"><textarea className="inp" rows={4} value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></Field></Modal>}{modal && detail && <Modal title="Academic Event Details" onClose={()=>{setModal(false);setDetail(null)}}><div className="calendar-detail"><Pill s={detail.status || 'published'}/><h3>{detail.title}</h3><p>{detail.description || 'No additional notes were provided.'}</p><div className="snap"><span>Date range</span><b>{dates(detail.start_date,detail.end_date)}</b></div><div className="snap"><span>Campus</span><b>{detail.campus}</b></div></div></Modal>}</div>
}
function Metric({i,n,t}:any){return <div className="academic-kpi"><i>{i}</i><div><b>{n}</b><span>{t}</span></div></div>}
function Side({title,rows,empty,open,showPill}:any){return <section className="card"><div className="card-h"><h3>{title}</h3></div><div className="card-pad">{rows.length?rows.map((x:any)=><button className="academic-side-item" onClick={()=>open(x)} key={x.id}><strong>{x.title}</strong><span>{dates(x.start_date,x.end_date)} · {x.category}</span>{showPill&&<Pill s={x.status}/>}</button>):<Empty icon="✓" text={empty}/>}</div></section>}
function Field({label,children}:any){return <div className="form-row"><label>{label}</label>{children}</div>}
function dates(s:string,e:string){const a=new Date(`${s}T00:00:00`),b=new Date(`${e}T00:00:00`);return s===e?a.toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'}):`${a.toLocaleDateString('en-IN',{day:'2-digit',month:'short'})} – ${b.toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'})}`}
function tone(c:string){c=c.toLowerCase();return c.includes('exam')||c.includes('assessment')?'linked':c.includes('break')||c.includes('result')?'manual':'academic'}
>>>>>>> 22ee34d (updated code to branch)
