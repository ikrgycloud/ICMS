import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast, Empty, GatedBtn } from './kit'

/** Operational marks workspace. Principal oversight is intentionally separate. */
export default function Examinations({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null), [sel, setSel] = useState<any>(null)
  const [assessments, setAssessments] = useState<any>(null), [asmt, setAsmt] = useState<any>(null)
  const [roster, setRoster] = useState<any[]>([]), [scores, setScores] = useState<Record<string, string>>({})
  const [decision, setDecision] = useState<any>(null)
  const reloadSections = () => api.examSections().then(setData).catch(() => {})
  useEffect(() => { reloadSections() }, [])
  function openSection(section: any) {
    setSel(section); setAsmt(null); setAssessments(null); setRoster([]); setScores({})
    api.examAssessments(section.id).then(result => { setAssessments(result); setRoster(result.roster || []) })
  }
  function refreshSection() {
    if (!sel) return
    api.examAssessments(sel.id).then(result => { setAssessments(result); setRoster(result.roster || []) })
    reloadSections()
  }
  function selectAssessment(assessment: any) {
    setAsmt(assessment)
    setScores(Object.fromEntries((assessment.marks || []).map((mark: any) => [mark.student_id, String(mark.score)])))
  }
  async function saveDraft() {
    const marks: Record<string, number> = {}
    Object.entries(scores).forEach(([id, score]) => { if (score !== '') marks[id] = Number(score) })
    try { const result = await api.enterMarks({ assessment_id: asmt.id, marks }); setDecision(result.decision); refreshSection() }
    catch (error: any) { setDecision({ outcome: 'DENY', reason: error.message }) }
  }
  async function submitMarks() {
    try { const result = await api.submitMarks(asmt.id); setDecision(result.decision); refreshSection() }
    catch (error: any) { setDecision({ outcome: 'DENY', reason: error.message }) }
  }
  async function publishResult() {
    try { const result = await api.publishResult(sel.id); setDecision(result.decision); refreshSection() }
    catch (error: any) { setDecision({ outcome: 'DENY', reason: error.message }) }
  }
  if (!data) return <Spinner />
  const state = String(asmt?.marks_state || 'draft')
  const canEdit = !!assessments?.permissions?.enter_marks && ['draft', 'returned'].includes(state)
  const canSubmit = !!assessments?.permissions?.submit_marks && ['draft', 'returned'].includes(state)
  return <div className="fade-in">
    <PageHead title="Examinations" sub="Faculty draft and submit marks; HOD verifies; Examination Controller approves and publishes results." />
    <div className="sod-banner"><span className="sod-i">&#9878;</span><div><b>Segregation of duties.</b> Faculty submit marks, HOD verifies them, and only the Examination Controller can publish results. Your server-authorised page actions are shown below.</div></div>
    <div className="split">
      <div className="card" style={{ flex: '0 0 340px' }}><div className="card-h"><h3>Sections</h3></div><div className="list">{data.sections.map((section: any) => <button key={section.id} className={`list-item ${sel?.id === section.id ? 'on' : ''}`} onClick={() => openSection(section)}><div><div className="li-title mono">{section.course_code} · {section.section}</div><div className="li-sub">{section.assessments} assessments · {String(section.marks_status || 'draft').replace(/_/g, ' ')}</div></div><span className={`pill s-${section.result_status}`}>{section.result_status}</span></button>)}</div></div>
      <div className="card" style={{ flex: 1 }}>
        {!sel && <Empty icon="M" text="Select a section to enter or review marks." />}
        {sel && <><div className="card-h"><h3>{sel.course_code} · Section {sel.section}</h3><GatedBtn can={!!sel.can_publish_result && !!data.permissions?.publish_result && !!caps.publish_result} kind="rose" onClick={publishResult}>Publish result</GatedBtn></div><div className="card-pad">
          {assessments && <div className="asmt-tabs">{assessments.assessments.map((assessment: any) => <button key={assessment.id} className={`asmt-tab ${asmt?.id === assessment.id ? 'on' : ''}`} onClick={() => selectAssessment(assessment)}>{assessment.name} <span className="hint">/{assessment.max_marks} · {assessment.entered} entered · {String(assessment.marks_state || 'draft').replace(/_/g, ' ')}</span></button>)}{!assessments.assessments.length && <div className="empty">No assessments configured for this section.</div>}</div>}
          {asmt && <><div className="mark-actions" style={{ justifyContent: 'space-between' }}><span className="hint"><b>{asmt.name}</b> · max {asmt.max_marks} · marks state: {state.replace(/_/g, ' ')}</span><div style={{ display: 'flex', gap: 8 }}>{canEdit && <button className="btn btn-brass" onClick={saveDraft}>Save draft</button>}{canSubmit && <button className="btn btn-crimson" onClick={submitMarks}>Submit marks</button>}</div></div><div className="tbl-scroll"><table className="tbl"><thead><tr><th>Roll No</th><th>Name</th><th>Score</th></tr></thead><tbody>{roster.map((student: any) => <tr key={student.student_id}><td className="mono">{student.roll_no}</td><td>{student.name}</td><td><input className="inp inp-sm" type="number" disabled={!canEdit} max={asmt.max_marks} min="0" placeholder="—" value={scores[student.student_id] ?? ''} onChange={event => setScores({ ...scores, [student.student_id]: event.target.value })} /></td></tr>)}</tbody></table></div></>}
        </div></>}
      </div>
    </div>
    {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
  </div>
}
