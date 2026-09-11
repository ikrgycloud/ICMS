import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { Empty, PageHead, Spinner } from './kit'

type Tab = 'assessments' | 'marks' | 'results' | 'exceptions' | 'audit'
const label = (value?: string) => String(value || 'not_started').replace(/_/g, ' ')
const dateTime = (value?: string) => value ? new Date(value).toLocaleString() : 'Not recorded'
const Pill = ({ value }: { value?: string }) => <span className={`pill s-${String(value || 'not_started').toLowerCase()}`}>{label(value)}</span>

export default function PrincipalExaminations() {
  const [data, setData] = useState<any>(null), [error, setError] = useState(''), [refreshing, setRefreshing] = useState(false)
  const [selected, setSelected] = useState<any>(null), [detail, setDetail] = useState<any>(null), [detailError, setDetailError] = useState(''), [loadingDetail, setLoadingDetail] = useState(false)
  const [tab, setTab] = useState<Tab>('assessments')
  const [query, setQuery] = useState(''), [academicYear, setAcademicYear] = useState(''), [department, setDepartment] = useState(''), [program, setProgram] = useState('')
  const [course, setCourse] = useState(''), [section, setSection] = useState(''), [semester, setSemester] = useState(''), [assessment, setAssessment] = useState('')
  const [resultStatus, setResultStatus] = useState(''), [marksStatus, setMarksStatus] = useState('')
  const detailRequest = useRef(0)

  const load = async () => {
    if (refreshing) return
    setRefreshing(true); setError('')
    try { setData(await api.examSections()) }
    catch (e: any) { setError(e.message || 'Unable to load examination oversight data.') }
    finally { setRefreshing(false) }
  }
  useEffect(() => { void load() }, [])

  const open = async (nextSection: any) => {
    const requestId = ++detailRequest.current
    setSelected(nextSection); setDetail(null); setDetailError(''); setLoadingDetail(true); setTab('assessments')
    try {
      const response = await api.examSectionOversight(nextSection.id)
      if (detailRequest.current === requestId) setDetail(response)
    } catch (e: any) {
      if (detailRequest.current === requestId) setDetailError(e.message || 'Unable to load examination details.')
    } finally {
      if (detailRequest.current === requestId) setLoadingDetail(false)
    }
  }
  const closeDetail = () => { detailRequest.current += 1; setSelected(null); setDetail(null); setDetailError(''); setLoadingDetail(false) }
  const clearFilters = () => { setQuery(''); setAcademicYear(''); setDepartment(''); setProgram(''); setCourse(''); setSection(''); setSemester(''); setAssessment(''); setResultStatus(''); setMarksStatus('') }
  const sections = data?.sections || []
  const filtered = useMemo(() => sections.filter((row: any) => {
    const searchable = `${row.course_code} ${row.course_title} ${row.section} ${row.faculty?.name || ''}`.toLowerCase()
    return (!query || searchable.includes(query.toLowerCase()))
      && (!academicYear || row.academic_years?.includes(academicYear))
      && (!department || row.department === department) && (!program || row.program === program)
      && (!course || row.course_code === course) && (!section || row.section === section)
      && (!semester || String(row.semester) === semester)
      && (!assessment || row.assessment_names?.includes(assessment))
      && (!resultStatus || row.result_status === resultStatus)
      && (!marksStatus || row.marks_lifecycle_statuses?.includes(marksStatus))
  }), [sections, query, academicYear, department, program, course, section, semester, assessment, resultStatus, marksStatus])
  const options = (key: string) => [...new Set(sections.flatMap((row: any) => Array.isArray(row[key]) ? row[key] : [row[key]]).map((value: any) => String(value || '')).filter(Boolean))].sort()
  const count = (predicate: (row: any) => boolean) => sections.filter(predicate).length
  if (!data && refreshing && !error) return <Spinner />
  return <div className="fade-in exam-oversight">
    <PageHead title="Examinations" sub="Principal examination oversight — readiness, submissions, results, and exceptions" />
    {error && <div className="exam-error"><span>{error}</span><button className="btn btn-out" onClick={() => void load()} disabled={refreshing}>Retry</button></div>}
    {data && <>
      <section className="exam-hero"><div><p className="eyebrow">EXAMINATION OVERSIGHT</p><h2>Academic quality, without bypassing examination controls.</h2><p>Marks entry and result publication remain controlled by authorised faculty and the Examination Controller.</p></div><div className="exam-hero-status"><span>Access</span><b>Read-only oversight</b><small>Actions are authorised by the server.</small></div></section>
      <section className="exam-kpis"><Metric label="Sections" value={sections.length} note="Authorised campus"/><Metric label="Assessments" value={sections.reduce((n: number, row: any) => n + Number(row.assessments || 0), 0)} note="Configured"/><Metric label="Marks pending" value={sections.reduce((n: number, row: any) => n + Number(row.marks_pending || 0), 0)} note="Assessment submissions"/><Metric label="Submitted" value={sections.reduce((n: number, row: any) => n + Number(row.marks_submitted || 0), 0)} note="Awaiting HOD"/><Metric label="Under verification" value={sections.reduce((n: number, row: any) => n + Number(row.marks_under_verification || 0), 0)} note="HOD review"/><Metric label="Approved" value={sections.reduce((n: number, row: any) => n + Number(row.marks_approved || 0), 0)} note="Ready to publish"/><Metric label="Results pending" value={count((row: any) => row.result_status !== 'published')} note="Awaiting publication"/><Metric label="Published" value={count((row: any) => row.result_status === 'published')} note="Result sheets"/><Metric label="Exceptions" value={detail?.exceptions?.filter((row: any) => row.severity !== 'info').length ?? 0} note="Selected section"/></section>
      <section className="exam-overview card"><Info label="Academic year" value={detail?.section?.academic_year || 'Select a section'}/><Info label="Examination period" value={selected?.term || 'Select a section'}/><Info label="Overall readiness" value={sections.length ? 'Monitoring active' : 'No scoped sections'}/><Info label="Policy" value="Segregation of duties enforced"/></section>
      <section className="exam-browser card"><div className="exam-browser-head"><div><p className="eyebrow">SEARCH SECTIONS</p><h3>Section readiness register</h3></div><div className="exam-browser-actions"><span>{filtered.length} matching sections</span><button className="btn btn-out" onClick={() => void load()} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh'}</button></div></div><div className="exam-filters"><input className="inp" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search course, section, or faculty"/><Filter value={academicYear} set={setAcademicYear} blank="All academic years" options={options('academic_years')}/><Filter value={department} set={setDepartment} blank="All departments" options={options('department')}/><Filter value={program} set={setProgram} blank="All programs" options={options('program')}/><Filter value={course} set={setCourse} blank="All courses" options={options('course_code')}/><Filter value={section} set={setSection} blank="All sections" options={options('section')} decorate="Section "/><Filter value={semester} set={setSemester} blank="All semesters" options={options('semester')} decorate="Semester "/><Filter value={assessment} set={setAssessment} blank="All assessments" options={options('assessment_names')}/><Filter value={resultStatus} set={setResultStatus} blank="All result statuses" options={options('result_status')}/><Filter value={marksStatus} set={setMarksStatus} blank="All marks lifecycle states" options={options('marks_lifecycle_statuses')}/><button className="btn btn-out exam-clear-filters" onClick={clearFilters}>Clear All</button></div><div className="tbl-scroll"><table className="tbl exam-table"><thead><tr><th>Course</th><th>Section</th><th>Faculty</th><th>Students</th><th>Assessments</th><th>Marks status</th><th>Result status</th><th></th></tr></thead><tbody>{filtered.map((row: any) => <tr key={row.id}><td><b>{row.course_code}</b><small>{row.course_title}</small></td><td>{row.section}<small>{row.department || 'Department not recorded'} · Sem {row.semester || '—'}</small></td><td>{row.faculty?.name || 'Unassigned'}<small>{row.faculty?.designation || 'Faculty not recorded'}</small></td><td>{row.students}</td><td>{row.assessments}</td><td><StatusSummary values={row.marks_lifecycle_statuses} fallback={row.marks_status}/></td><td><Pill value={row.result_status}/></td><td><button className="btn btn-out" onClick={() => void open(row)}>View</button></td></tr>)}</tbody></table>{!filtered.length && <Empty icon="⌕" text="No sections match the selected filters."/>}</div></section>
      {selected && <div className="exam-detail-backdrop" role="presentation" onMouseDown={closeDetail}><section className="exam-detail card" role="dialog" aria-modal="true" aria-label="Section examination detail" onMouseDown={event => event.stopPropagation()}>{loadingDetail && <Spinner />}{detailError && <div className="exam-detail-error"><h3>Unable to load examination details.</h3><p>{detailError}</p><button className="btn btn-out" onClick={() => void open(selected)} disabled={loadingDetail}>Retry</button></div>}{detail && <Details data={detail} tab={tab} setTab={setTab} close={closeDetail}/>}</section></div>}
    </>}
  </div>
}

function Details({ data, tab, setTab, close }: any) {
  const section = data.section
  return <><div className="exam-detail-head"><div><p className="eyebrow">SECTION DETAIL</p><h3>{section.course_code} · Section {section.section}</h3><p>{section.course_title} · {section.department || 'Department not recorded'} · {section.program || 'Program not recorded'}</p><p>Faculty: <b>{section.faculty?.name || 'Unassigned'}</b>{section.faculty?.designation ? ` · ${section.faculty.designation}` : ''}</p></div><div className="exam-detail-controls"><div><b>{section.students}</b><span>students</span></div><button className="icon-btn" type="button" aria-label="Close examination details" onClick={close}>×</button></div></div><div className="exam-tabs">{([['assessments','Assessments'],['marks','Marks status'],['results','Results'],['exceptions',`Exceptions (${data.exceptions.length})`],['audit','Audit']] as [Tab,string][]).map(([key,text]) => <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{text}</button>)}</div>{tab === 'assessments' && <AssessmentTable items={data.assessments}/>} {tab === 'marks' && <MarksTable items={data.assessments}/>} {tab === 'results' && <Results data={data}/>} {tab === 'exceptions' && <Exceptions data={data}/>} {tab === 'audit' && <Audit rows={data.audit}/>}</>
}
function StatusSummary({ values, fallback }: { values?: string[], fallback?: string }) { const statuses = values?.length ? values : [fallback || 'not_started']; return <span className="exam-status-summary">{statuses.map(value => <Pill key={value} value={value}/>)}</span> }
function AssessmentTable({ items }: any) { return <div className="tbl-scroll">{items.length ? <table className="tbl"><thead><tr><th>Assessment</th><th>Type</th><th>Max marks</th><th>Marks status</th><th>Scheduled</th></tr></thead><tbody>{items.map((item: any) => <tr key={item.id}><td><b>{item.name}</b></td><td>{item.type}</td><td>{item.max_marks}</td><td><Pill value={item.marks_status}/></td><td>{dateTime(item.scheduled_at)}</td></tr>)}</tbody></table> : <Empty icon="▤" text="No assessments configured for this section."/>}</div> }
function MarksTable({ items }: any) { return <div>{!items.length && <Empty icon="▤" text="Assessments must be configured before marks can be reviewed."/>}{items.map((item: any) => <section className="exam-marks-block" key={item.id}><div><h4>{item.name}</h4><span>{item.entered} of {item.marks.length} marks recorded · <Pill value={item.marks_status}/></span></div><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Roll no.</th><th>Student</th><th>Score</th><th>Status</th></tr></thead><tbody>{item.marks.map((mark: any) => <tr key={mark.student_id}><td className="mono">{mark.roll_no}</td><td>{mark.name}</td><td>{mark.score ?? 'Not entered'}</td><td><Pill value={mark.mark_status}/></td></tr>)}</tbody></table></div></section>)}</div> }
function Results({ data }: any) { return <div className="exam-result-panel"><Pill value={data.result.status}/><h4>Result publication</h4><p>{data.result.status === 'published' ? `Published by ${data.result.published_by || 'Examination Controller'} on ${dateTime(data.result.published_at)}.` : 'No result sheet has been published for this section.'}</p><h4>Exam timetable</h4>{data.timetable.length ? <ul>{data.timetable.map((item: any) => <li key={item.id}>{item.exam_type} · {dateTime(item.start_at)} – {dateTime(item.end_at)} · {item.venue || 'Venue not recorded'} <Pill value={item.status}/></li>)}</ul> : <p>No timetable entries are available for this section.</p>}</div> }
function Exceptions({ data }: any) { return <><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Severity</th><th>Issue</th><th>Current owner</th><th>Required action</th><th>Status</th></tr></thead><tbody>{data.exceptions.map((item: any, index: number) => <tr key={index}><td><Pill value={item.severity}/></td><td>{item.issue}</td><td>{item.current_owner}</td><td>{item.required_action}</td><td><Pill value={item.status}/></td></tr>)}</tbody></table></div><div className="exam-limitations"><b>Case registers</b><span>{data.limitations.malpractice}</span><span>{data.limitations.revaluation}</span></div></> }
function Audit({ rows }: any) { return <div className="tbl-scroll">{rows.length ? <table className="tbl"><thead><tr><th>Action</th><th>Actor</th><th>Change</th><th>Time</th></tr></thead><tbody>{rows.map((row: any, index: number) => <tr key={index}><td>{row.action}</td><td>{row.actor}</td><td>{row.previous || '—'} → {row.current || '—'}</td><td>{dateTime(row.at)}</td></tr>)}</tbody></table> : <Empty icon="◷" text="No campus-scoped examination audit entries are available for this section."/>}</div> }
function Metric({ label, value, note }: any) { return <div className="exam-metric"><span>{label}</span><b>{value}</b><small>{note}</small></div> }
function Info({ label, value }: any) { return <div><span>{label}</span><b>{value}</b></div> }
function Filter({ value, set, blank, options, decorate = '' }: any) { return <select className="select" value={value} onChange={e => set(e.target.value)}><option value="">{blank}</option>{options.map((option: string) => <option key={option} value={option}>{decorate}{label(option)}</option>)}</select> }
