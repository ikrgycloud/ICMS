import { useState, useEffect } from 'react'
import { api } from '../api'
import { PageHead, Spinner, DecisionToast, Empty, GatedBtn } from './kit'

export default function Examinations({ caps }: { caps: any }) {
  const [data, setData] = useState<any>(null)
  const [sel, setSel] = useState<any>(null)
  const [assessments, setAssessments] = useState<any>(null)
  const [asmt, setAsmt] = useState<any>(null)
  const [roster, setRoster] = useState<any[]>([])
  const [scores, setScores] = useState<Record<string, string>>({})
  const [decision, setDecision] = useState<any>(null)

  useEffect(() => { api.examSections().then(setData).catch(() => {}) }, [])

  function openSection(s: any) {
    setSel(s); setAsmt(null); setAssessments(null); setRoster([])
    api.examAssessments(s.id).then(setAssessments)
    api.attendanceRoster(s.id).then(r => setRoster(r.roster))
  }

  async function enter() {
    const marks: Record<string, number> = {}
    Object.entries(scores).forEach(([k, v]) => { if (v !== '') marks[k] = Number(v) })
    try {
      const r = await api.enterMarks({ assessment_id: asmt.id, marks })
      setDecision(r.decision)
      api.examAssessments(sel.id).then(setAssessments)
    } catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }) }
  }

  async function publish() {
    try {
      const r = await api.publishResult(sel.id)
      setDecision(r.decision)
      api.examSections().then(setData)
    } catch (e: any) { setDecision({ outcome: 'DENY', reason: e.message }) }
  }

  if (!data) return <Spinner />

  return (
    <div className="fade-in">
      <PageHead title="Examinations" sub="Marks entry and result publication are separate authorities (segregation of duties)" />

      <div className="sod-banner">
        <span className="sod-i">⚖</span>
        <div>
          <b>Segregation of duties.</b> Faculty may <em>enter</em> marks; only the Examination Controller may <em>publish</em> results.
          Your role here: marks entry {caps.enter_marks ? <span className="yes">permitted</span> : <span className="no">not permitted</span>},
          result publication {caps.publish_result ? <span className="yes">permitted</span> : <span className="no">not permitted</span>}.
        </div>
      </div>

      <div className="split">
        <div className="card" style={{ flex: '0 0 340px' }}>
          <div className="card-h"><h3>Sections</h3></div>
          <div className="list">
            {data.sections.map((s: any) => (
              <button key={s.id} className={`list-item ${sel?.id === s.id ? 'on' : ''}`} onClick={() => openSection(s)}>
                <div>
                  <div className="li-title mono">{s.course_code} · {s.section}</div>
                  <div className="li-sub">{s.assessments} assessments</div>
                </div>
                <span className={`pill s-${s.result_status}`}>{s.result_status}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="card" style={{ flex: 1 }}>
          {!sel && <Empty icon="📝" text="Select a section" />}
          {sel && (
            <>
              <div className="card-h">
                <h3>{sel.course_code} · Section {sel.section}</h3>
                <GatedBtn can={!!caps.publish_result} kind="rose" onClick={publish}>Publish result</GatedBtn>
              </div>
              <div className="card-pad">
                {assessments && (
                  <div className="asmt-tabs">
                    {assessments.assessments.map((a: any) => (
                      <button key={a.id} className={`asmt-tab ${asmt?.id === a.id ? 'on' : ''}`}
                        onClick={() => { setAsmt(a); setScores({}) }}>
                        {a.name} <span className="hint">/{a.max_marks} · {a.entered} entered</span>
                      </button>
                    ))}
                    {assessments.assessments.length === 0 && <div className="empty">No assessments for this section</div>}
                  </div>
                )}

                {asmt && (
                  <>
                    <div className="mark-actions" style={{ justifyContent: 'space-between' }}>
                      <span className="hint">Entering: <b>{asmt.name}</b> (max {asmt.max_marks})</span>
                      {caps.enter_marks && <button className="btn btn-brass" onClick={enter}>Save marks</button>}
                    </div>
                    <div className="tbl-scroll">
                      <table className="tbl">
                        <thead><tr><th>Roll No</th><th>Name</th><th>Score</th></tr></thead>
                        <tbody>
                          {roster.map((x: any) => (
                            <tr key={x.student_id}>
                              <td className="mono">{x.roll_no}</td>
                              <td>{x.name}</td>
                              <td>
                                <input className="inp inp-sm" type="number" disabled={!caps.enter_marks}
                                  max={asmt.max_marks} placeholder="—"
                                  value={scores[x.student_id] ?? ''}
                                  onChange={e => setScores({ ...scores, [x.student_id]: e.target.value })} />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {decision && <DecisionToast decision={decision} onClose={() => setDecision(null)} />}
    </div>
  )
}
