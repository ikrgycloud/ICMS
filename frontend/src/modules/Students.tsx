<<<<<<< HEAD
import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, GatedBtn, DecisionToast, Modal } from './kit'

const DEPTS = ['', 'CSE', 'ECE', 'MEC', 'CIV', 'EEE', 'MAT', 'MGT', 'HSS']

export default function Students({ caps }: { caps: any }) {
  const [q, setQ] = useState('')
  const [dept, setDept] = useState('')
  const [view, setView] = useState<any>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [decision, setDecision] = useState<any>(null)
  const [form, setForm] = useState({ name: '', dept_code: 'CSE', batch: '2025', semester: 1, program_level: 'UG' })

  function load() { api.students(q, dept).then(setView).catch(() => {}) }
  useEffect(() => { load() }, [])

  async function submit() {
    try {
      const r = await api.addStudent(form)
      setDecision(r.decision)
      setShowAdd(false)
      setForm({ ...form, name: '' })
      load()
    } catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }) }
  }

  if (!view) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead title="Student records" sub={`${view?.total ?? 0} students · scope-filtered to your authority`}
        right={<GatedBtn can={!!caps.add} onClick={() => setShowAdd(true)}>+ Admit student</GatedBtn>} />

      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <input className="inp" style={{ maxWidth: 320 }} placeholder="Search name or roll no…"
          value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()} />
        <select className="select" value={dept} onChange={e => { setDept(e.target.value) }}>
          {DEPTS.map(d => <option key={d} value={d}>{d || 'All departments'}</option>)}
        </select>
        <button className="btn btn-out" onClick={load}>Apply</button>
      </div>

      <div className="card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr>
              <th>Roll No</th><th>Name</th><th>Dept</th><th>Batch</th><th>Sem</th><th>CGPA</th><th>Status</th><th>Flags</th>
            </tr></thead>
            <tbody>
              {(view?.students || []).map((s: any) => (
                <tr key={s.id}>
                  <td className="mono">{s.roll_no}</td>
                  <td><b>{s.name}</b></td>
                  <td>{s.dept}</td>
                  <td>{s.batch}</td>
                  <td>{s.semester}</td>
                  <td><span className={`cgpa ${s.cgpa >= 8 ? 'good' : s.cgpa >= 6.5 ? 'ok' : 'low'}`}>{s.cgpa.toFixed(2)}</span></td>
                  <td><span className={`pill s-${s.status}`}>{s.status}</span></td>
                  <td>
                    {s.hosteller && <span className="tag">Hosteller</span>}
                    {s.scholarship && <span className="tag tag-brass">Scholarship</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showAdd && (
        <Modal title="Admit new student" onClose={() => setShowAdd(false)}
          footer={<>
            <button className="btn btn-out" onClick={() => setShowAdd(false)}>Cancel</button>
            <button className="btn btn-brass" onClick={submit} disabled={!form.name}>Admit</button>
          </>}>
          <div className="form-row"><label>Full name</label>
            <input className="inp" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></div>
          <div className="grid-2">
            <div className="form-row"><label>Department</label>
              <select className="select" value={form.dept_code} onChange={e => setForm({ ...form, dept_code: e.target.value })}>
                {DEPTS.filter(Boolean).map(d => <option key={d}>{d}</option>)}
              </select></div>
            <div className="form-row"><label>Level</label>
              <select className="select" value={form.program_level} onChange={e => setForm({ ...form, program_level: e.target.value })}>
                <option>UG</option><option>PG</option>
              </select></div>
          </div>
          <div className="grid-2">
            <div className="form-row"><label>Batch year</label>
              <input className="inp" value={form.batch} onChange={e => setForm({ ...form, batch: e.target.value })} /></div>
            <div className="form-row"><label>Semester</label>
              <input className="inp" type="number" value={form.semester} onChange={e => setForm({ ...form, semester: Number(e.target.value) })} /></div>
          </div>
          <p className="hint">This action passes through the authority engine and is written to the audit log.</p>
        </Modal>
      )}

      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
=======
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Modal, PageHead, Spinner } from './kit'

const emptyFilters={academicYear:'',program:'',studyYear:'',semester:'',section:'',risk:''}
export default function Students({ caps: _caps }: { caps?: any }){
 const [q,setQ]=useState(''),[dept,setDept]=useState(''),[page,setPage]=useState(1),[data,setData]=useState<any>(null),[filters,setFilters]=useState<any>({...emptyFilters,risk:sessionStorage.getItem('principal-student-risk')||''}),[error,setError]=useState(''),[mode,setMode]=useState<'overview'|'list'|'analysis'>('overview'),[profile,setProfile]=useState<any>(null),[full,setFull]=useState(false)
 const load=(query=q,department=dept,p=page,f=filters)=>{setError('');return api.students(query,department,p,25,f).then(setData).catch((e:any)=>setError(e.message||'Unable to load students.'))}
 useEffect(()=>{sessionStorage.removeItem('principal-student-risk');load()},[])
 const summary=data?.summary||{}, rows=data?.students||[], options=data?.filter_options||{academic_years:[],programs:[],departments:[],study_years:[],semesters:[],sections:[]}
 const applyQuick=(risk:string)=>{const next={...filters,risk};setFilters(next);setPage(1);setMode('list');load(q,dept,1,next)}
 const apply=()=>{setPage(1);setMode('list');load(q,dept,1)}
 if(!data)return error?<div className="empty-state"><h3>Students could not be loaded</h3><p>{error}</p><button className="btn btn-crimson" onClick={()=>load()}>Retry</button></div>:<Spinner/>
 return <div className="fade-in students-ref"><PageHead title={mode==='overview'?'Students — Overall Overview':mode==='analysis'?'Backlog Analysis':'Students'} sub="Campus-scoped, read-only Principal oversight of student population, performance and academic risk."/>
 <div className="students-context">Academic context and filter choices are loaded from student records within your authorized campus.</div>
 <div className="students-kpis"><Metric n={summary.all_students} t="Total Students"/><Metric n={summary.at_risk} t="At Risk"/><Metric n={summary.attendance_available?summary.attendance_risk:'Unavailable'} t="Attendance Risk"/><Metric n={summary.academic_risk} t="Academic Risk"/><Metric n={summary.average_attendance==null?'Unavailable':`${summary.average_attendance}%`} t="Average Attendance"/><Metric n={summary.average_cgpa??'Unavailable'} t="Average CGPA"/></div>
 <div className="student-quick-tabs">{[['','All Students'],['at-risk','At Risk'],['academic','Academic Risk'],['backlogs','Backlogs'],['no-backlogs','No Backlogs']].map(([v,t])=><button key={t} className={filters.risk===v?'active':''} onClick={()=>applyQuick(v)}>{t}{v==='backlogs'?` (${summary.backlogs})`:v==='no-backlogs'?` (${summary.no_backlogs})`:''}</button>)}<button onClick={()=>setMode('analysis')}>View Backlog Analysis</button></div>
 <div className="students-filter"><label>Academic Year<select className="select" value={filters.academicYear} onChange={e=>setFilters({...filters,academicYear:e.target.value})}><option value="">All Academic Years</option>{options.academic_years.map((x:string)=><option key={x} value={x}>{x}</option>)}</select></label><label>Program<select className="select" value={filters.program} onChange={e=>setFilters({...filters,program:e.target.value})}><option value="">All Programs</option>{options.programs.map(([id,name]:any)=><option key={id} value={id}>{name}</option>)}</select></label><label>Department<select className="select" value={dept} onChange={e=>setDept(e.target.value)}><option value="">All Departments</option>{options.departments.map(([code,name]:any)=><option key={code} value={code}>{code} · {name}</option>)}</select></label><label>Study Year<select className="select" value={filters.studyYear} onChange={e=>{const value=e.target.value;setFilters({...filters,studyYear:value,semester:''})}}><option value="">All Years</option>{options.study_years.map((x:number)=><option key={x} value={x}>{x}{x===1?'st':x===2?'nd':x===3?'rd':'th'} Year</option>)}</select></label><label>Semester<select className="select" value={filters.semester} onChange={e=>setFilters({...filters,semester:e.target.value,studyYear:''})}><option value="">All Semesters</option>{options.semesters.map((x:number)=><option key={x} value={x}>Semester {x}</option>)}</select></label><label>Section<select className="select" value={filters.section} onChange={e=>setFilters({...filters,section:e.target.value})}><option value="">All Sections</option>{options.sections.map((x:string)=><option key={x} value={x}>{x}</option>)}</select></label><input className="inp" placeholder="Search name, roll no. or email" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&apply()}/><button className="btn btn-crimson" onClick={apply}>Apply</button><button className="btn btn-out" onClick={()=>{setQ('');setDept('');setFilters(emptyFilters);setPage(1);setMode('overview');load('','',1,emptyFilters)}}>Clear</button></div>
 {mode==='overview'?<Overview s={summary} onList={()=>setMode('list')} onAnalysis={()=>setMode('analysis')}/>:mode==='analysis'?<Analysis s={summary} back={()=>setMode('overview')}/>:<List rows={rows} data={data} q={q} dept={dept} page={page} load={load} setPage={setPage} open={(x:any)=>api.studentProfile(x.id).then(p=>{setProfile(p);setFull(false)})}/>} 
 {profile&&<Modal title={full?'Student 360°':'Student Profile'} onClose={()=>setProfile(null)} footer={!full?<button className="btn btn-crimson" onClick={()=>setFull(true)}>View Full Profile</button>:undefined}><Profile data={profile} full={full}/></Modal>}</div>
}
function Metric({n,t}:any){return <div className="students-kpi"><div><span>{t}</span><b>{n}</b></div></div>}
function Overview({s,onList,onAnalysis}:any){return <div className="students-overview"><section className="card card-pad"><h3>Backlog Status</h3><div className="grid-3"><div className="snap"><span>Students with Current Backlogs</span><b>{s.backlogs}</b></div><div className="snap"><span>No Current Backlog</span><b>{s.no_backlogs}</b></div><button className="btn btn-out" onClick={onAnalysis}>View Backlog Analysis</button></div></section><section className="card card-pad"><h3>Academic & Attendance Coverage</h3><p>Attendance is available for {s.attendance_available} students. Backlog values are derived from published subject outcomes; development sample outcomes are labelled in the profile.</p><button className="btn btn-crimson" onClick={onList}>Browse Student List</button></section></div>}
function Analysis({s,back}:any){return <div className="card card-pad"><div className="card-h"><h3>Backlog Analysis</h3><button className="btn btn-out" onClick={back}>Back to Overview</button></div><p>Current backlog students: <b>{s.backlogs}</b>. Department × Semester drill-down requires broader published result coverage. Existing development samples are shown only in individual profiles and are not used to fabricate a matrix.</p></div>}
function List({rows,data,q,dept,page,load,setPage,open}:any){return <div className="students-table-card"><div className="students-table-head"><span>Showing {rows.length?(data.page-1)*data.page_size+1:0}–{Math.min(data.page*data.page_size,data.total)} of {data.total}</span><span>Read-only Principal view</span></div><div className="tbl-scroll"><table className="tbl students-table"><thead><tr><th>Roll No.</th><th>Student</th><th>Program</th><th>Department</th><th>Year</th><th>Semester</th><th>Section</th><th>Attendance</th><th>CGPA</th><th>Current Backlogs</th><th>Backlog Status</th><th>Risk</th><th>Action</th></tr></thead><tbody>{rows.map((x:any)=><tr key={x.id}><td className="mono">{x.roll_no}</td><td><b>{x.name}</b><small>{x.email||'Unavailable'}</small></td><td>{x.program||'Unavailable'}</td><td>{x.department_name||x.dept}</td><td>{Math.ceil(x.semester/2)}</td><td>{x.semester}</td><td>{x.section}</td><td>{x.attendance_pct==null?'Unavailable':`${x.attendance_pct}%`}</td><td>{Number(x.cgpa).toFixed(2)}</td><td>{x.current_backlogs}</td><td>{x.backlog_status}</td><td><Risk x={x}/></td><td><button className="btn btn-out student-view" onClick={()=>open(x)}>View</button></td></tr>)}</tbody></table></div><div className="student-pagination"><button className="btn btn-out" disabled={data.page<=1} onClick={()=>{const n=page-1;setPage(n);load(q,dept,n)}}>Previous</button><span>Page {data.page} of {data.total_pages}</span><button className="btn btn-out" disabled={data.page>=data.total_pages} onClick={()=>{const n=page+1;setPage(n);load(q,dept,n)}}>Next</button></div></div>}
function Risk({x}:any){const label=x.current_backlogs?'At Risk':x.cgpa<6.5?'Academic Risk':x.attendance_pct!=null&&x.attendance_pct<75?'Attendance Risk':'Normal';return <span className="student-risk warning">{label}</span>}
function Profile({data,full}:any){const s=data.student;return <div className="calendar-detail"><h3>{s.name}</h3><div className="snap"><span>Roll no. / Status</span><b>{s.roll_no} · {s.status}</b></div><div className="snap"><span>Academic Context</span><b>{s.program||'Unavailable'} · {s.department||'Unavailable'} · Semester {s.semester} · Section {s.section}</b></div><div className="snap"><span>Attendance / CGPA / Current Backlogs</span><b>{s.attendance_pct==null?'Unavailable':`${s.attendance_pct}%`} / {Number(s.cgpa).toFixed(2)} / {s.current_backlogs}</b></div>{full&&<><h4>Academic & Backlog History</h4>{data.backlog_history.length?data.backlog_history.map((x:any)=><div className="snap" key={`${x.subject_code}-${x.attempt}`}><span>{x.subject_code} · attempt {x.attempt} · {x.source}</span><b>{x.outcome}</b></div>):<p>No published subject result history is available.</p>}<h4>Attendance</h4><p>{data.attendance.length?`${data.attendance.length} recorded attendance entries available.`:'No attendance records available.'}</p><h4>Welfare / Discipline & Grievances</h4><p>{data.limitations.welfare}</p></>}</div>}
>>>>>>> 22ee34d (updated code to branch)
