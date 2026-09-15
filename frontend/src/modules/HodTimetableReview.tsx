import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Empty, Modal, PageHead, Pill, Spinner } from "./kit";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function HodTimetableReview() {
  const [plans, setPlans] = useState<any[] | null>(null);
  const [selected, setSelected] = useState<any>(null);
  const [returnOpen, setReturnOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setError("");
      const result = await api.timetablePlans();
      setPlans(result.plans || []);
    } catch (err: any) {
      setError(err.message || "Unable to load departmental timetable plans.");
    }
  };

  useEffect(() => { void load(); }, []);

  const pending = useMemo(() => (plans || []).filter((plan) => plan.status === "HOD Review"), [plans]);
  const history = useMemo(() => (plans || []).filter((plan) => plan.status !== "HOD Review"), [plans]);

  const decide = async (action: "approve" | "return", decisionReason = "") => {
    if (!selected) return;
    if (action === "return" && !decisionReason.trim()) {
      setError("A return reason is required so the Academic Coordinator can correct the timetable.");
      return;
    }
    try {
      setBusy(true);
      await api.timetableHodDecision(selected.id, action, decisionReason, selected.version_no);
      setSelected(null);
      setReturnOpen(false);
      setReason("");
      await load();
    } catch (err: any) {
      if (err?.status === 409) {
        setSelected(null);
        await load();
        setError("This timetable plan changed while it was open. The review inbox has been refreshed.");
      } else {
        setError(err.message || "Unable to record the HOD decision.");
      }
    } finally {
      setBusy(false);
    }
  };

  if (!plans) return <Spinner />;
  return <div className="fade-in hod-timetable-review">
    <PageHead title="Sections & Timetable" sub="Review departmental timetable plans before they proceed to Dean Academics." right={<button className="btn btn-out" onClick={() => void load()} disabled={busy}>Refresh</button>} />
    {error && <div className="calendar-banner warn">{error}</div>}

    <section className="hod-timetable-hero">
      <div><span>HOD REVIEW INBOX</span><h2>Protect delivery readiness before governance review.</h2><p>Verify the faculty, room, time and departmental delivery fit. Approval routes the exact submitted version to Dean Academics.</p></div>
      <div className="hod-timetable-count"><b>{pending.length}</b><small>awaiting your decision</small></div>
    </section>

    <section className="hod-timetable-section card">
      <div className="card-h"><div><h3>Awaiting HOD review</h3><p className="hint">Only plans at this stage can be approved or returned.</p></div><Pill s={pending.length ? "HOD Review" : "Clear"} /></div>
      {pending.length ? <div className="hod-plan-grid">{pending.map((plan) => <PlanCard key={plan.id} plan={plan} onOpen={() => setSelected(plan)} />)}</div> : <Empty text="No timetable plans are awaiting HOD review." />}
    </section>

    <section className="hod-timetable-section card">
      <div className="card-h"><div><h3>Department timetable history</h3><p className="hint">Published and returned plans remain visible for traceability.</p></div><span className="hint">{history.length} plan{history.length === 1 ? "" : "s"}</span></div>
      {history.length ? <div className="tbl-scroll"><table className="tbl"><thead><tr><th>Course / section</th><th>Faculty</th><th>Scheduled slot</th><th>Status</th><th /></tr></thead><tbody>{history.map((plan) => <tr key={plan.id}><td><b>{plan.offering?.course_code || "Course"} · {plan.section}</b><small>{plan.offering?.course_title} · {plan.offering?.term}</small></td><td>{plan.faculty || "Unassigned"}</td><td>{slot(plan)}</td><td><Pill s={plan.status} /></td><td><button className="btn btn-sm btn-out" onClick={() => setSelected(plan)}>View</button></td></tr>)}</tbody></table></div> : <Empty text="No departmental timetable history yet." />}
    </section>

    {selected && <Modal title={`Timetable review · ${selected.offering?.course_code || "Course"} · Section ${selected.section || "—"}`} className="hod-timetable-modal" onClose={() => !busy && setSelected(null)} footer={<div className="modal-actions"><button className="btn btn-out" disabled={busy} onClick={() => setSelected(null)}>Close</button>{selected.status === "HOD Review" && <><button className="btn btn-out" disabled={busy} onClick={() => { setReturnOpen(true); setReason(""); }}>Return for correction</button><button className="btn btn-crimson" disabled={busy} onClick={() => void decide("approve", "HOD review approved; departmental delivery requirements are met.")}>{busy ? "Saving..." : "Approve / send to Dean"}</button></>}</div>}>
      <div className="hod-detail">
        <div className="hod-detail-status"><Pill s={selected.status} /><span>Plan {selected.id} · Version {selected.version_no}</span></div>
        <section><h3>Submitted timetable</h3><div className="hod-detail-grid"><Detail label="Course" value={`${selected.offering?.course_code || "—"} · ${selected.offering?.course_title || "—"}`} /><Detail label="Section" value={selected.section || "—"} /><Detail label="Faculty" value={selected.faculty || "Unassigned"} /><Detail label="Term" value={selected.offering?.term || "—"} /><Detail label="Day and time" value={slot(selected)} /><Detail label="Location" value={[selected.timetable?.room, selected.timetable?.building].filter(Boolean).join(" · ") || "—"} /></div></section>
        <section><h3>Governance route</h3><p>Academic Coordinator → <b>HOD review</b> → Dean Academics → Vice Principal → Academic Coordinator publication.</p><p>The submitted plan is read-only at this stage. Return it if a change is required.</p></section>
        {selected.reason && <section><h3>Latest decision note</h3><p>{selected.reason}</p></section>}
      </div>
    </Modal>}
    {returnOpen && <Modal title="Return timetable for correction" onClose={() => !busy && setReturnOpen(false)} footer={<div className="modal-actions"><button className="btn btn-out" disabled={busy} onClick={() => setReturnOpen(false)}>Cancel</button><button className="btn btn-crimson" disabled={busy} onClick={() => void decide("return", reason)}>{busy ? "Returning..." : "Return to coordinator"}</button></div>}><p className="hint">Explain exactly what must be corrected. The plan will return to the Academic Coordinator and must be resubmitted.</p><label className="form-row">Reason<textarea className="inp" rows={5} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Example: Move this slot because the assigned faculty member has a departmental commitment at this time." /></label></Modal>}
    <style>{styles}</style>
  </div>;
}

function slot(plan: any) {
  const day = DAYS[Number(plan.timetable?.day_of_week)] || "Day pending";
  return `${day} · ${plan.timetable?.start_time || "—"}–${plan.timetable?.end_time || "—"}`;
}

function Detail({ label, value }: any) { return <div><small>{label}</small><b>{value}</b></div>; }

function PlanCard({ plan, onOpen }: any) {
  return <article className="hod-plan-card"><div className="hod-plan-card-top"><div><span>{plan.offering?.term || "Academic term"}</span><h4>{plan.offering?.course_code || "Course"} · Section {plan.section || "—"}</h4><p>{plan.offering?.course_title || "Timetable plan"}</p></div><Pill s={plan.status} /></div><div className="hod-plan-facts"><Detail label="Faculty" value={plan.faculty || "Unassigned"} /><Detail label="Schedule" value={slot(plan)} /><Detail label="Room" value={plan.timetable?.room || "—"} /></div><button className="btn btn-out" onClick={onOpen}>Review timetable</button></article>;
}

const styles = `.hod-timetable-review{color:#2d2528}.hod-timetable-hero{margin:18px 0;display:flex;justify-content:space-between;gap:28px;padding:28px;border-radius:18px;background:linear-gradient(125deg,#3d1722,#722942 62%,#ae8033);color:#fff}.hod-timetable-hero>div:first-child{max-width:680px}.hod-timetable-hero span{font-size:10px;font-weight:800;letter-spacing:.13em;color:#edcf91}.hod-timetable-hero h2{margin:7px 0;font-size:25px;color:#fff}.hod-timetable-hero p{margin:0;line-height:1.55;font-size:13px;color:#f5e8eb}.hod-timetable-count{min-width:130px;align-self:center;padding:15px;border:1px solid rgba(255,255,255,.26);border-radius:13px;background:rgba(255,255,255,.1);text-align:center}.hod-timetable-count b,.hod-timetable-count small{display:block}.hod-timetable-count b{font-size:32px}.hod-timetable-count small{margin-top:3px;color:#f6dca8;font-size:10px;text-transform:uppercase;letter-spacing:.06em}.hod-timetable-section{margin-top:18px}.hod-plan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px;padding:16px}.hod-plan-card{display:grid;gap:16px;padding:18px;border:1px solid #e7dce0;border-radius:14px;background:linear-gradient(145deg,#fff,#fcf8f9)}.hod-plan-card-top{display:flex;justify-content:space-between;gap:10px}.hod-plan-card-top span{font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#8a6873}.hod-plan-card h4{margin:5px 0;font-size:16px}.hod-plan-card p{margin:0;color:#766a6f;font-size:12px}.hod-plan-facts,.hod-detail-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.hod-plan-facts>div,.hod-detail-grid>div{padding:10px;border-radius:9px;background:#f8f5f6}.hod-plan-facts small,.hod-detail-grid small{display:block;font-size:10px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:#887d82}.hod-plan-facts b,.hod-detail-grid b{display:block;margin-top:5px;font-size:12px;line-height:1.35;color:#412e35}.hod-detail{display:grid;gap:15px;max-height:63vh;overflow:auto}.hod-detail-status{display:flex;gap:10px;align-items:center;color:#75686d;font-size:12px}.hod-detail section{padding:15px;border:1px solid #e8e1e3;border-radius:12px;background:#fff}.hod-detail h3{margin:0 0 10px;font-size:14px}.hod-detail p{margin:6px 0;color:#6f6267;line-height:1.55;font-size:13px}.tbl td small{display:block;margin-top:3px;color:#83767b}@media(max-width:650px){.hod-timetable-hero{flex-direction:column}.hod-plan-facts,.hod-detail-grid{grid-template-columns:1fr}.hod-timetable-count{align-self:stretch}.hod-timetable-hero h2{font-size:21px}}`;
