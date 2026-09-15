import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Empty, Modal, PageHead, Pill, Spinner } from "./kit";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function VicePrincipalAcademicApprovals() {
  const [tab, setTab] = useState<"timetable" | "calendar">("timetable");
  const [plans, setPlans] = useState<any[] | null>(null);
  const [calendar, setCalendar] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [kind, setKind] = useState<"timetable" | "calendar">("timetable");
  const [returnOpen, setReturnOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      setError("");
      const [planResult, calendarResult] = await Promise.all([api.timetablePlans(), api.academicCalendar()]);
      setPlans(planResult.plans || []);
      setCalendar(calendarResult.entries || []);
    } catch (err: any) { setError(err.message || "Unable to load academic approval work."); }
  };
  useEffect(() => { void load(); }, []);

  const timetableQueue = useMemo(() => (plans || []).filter((plan) => plan.status === "VP Review"), [plans]);
  const calendarQueue = useMemo(() => calendar.filter((entry) => entry.status === "VP Review"), [calendar]);
  const open = (value: any, valueKind: "timetable" | "calendar") => { setSelected(value); setKind(valueKind); };

  const approve = async () => {
    if (!selected) return;
    try {
      setBusy(true);
      if (kind === "timetable") await api.timetableVpDecision(selected.id, "approve", "VP operational approval confirmed.", selected.version_no);
      else await api.decideAcademicCalendarEntry(selected.id, { action: "approve", reason: "VP operational approval confirmed.", expected_version: selected.version_no });
      setSelected(null); await load();
    } catch (err: any) { setError(err.message || "Unable to record the operational approval."); }
    finally { setBusy(false); }
  };
  const returnForCorrection = async () => {
    if (!selected || !reason.trim()) { setError("A return reason is required."); return; }
    try {
      setBusy(true);
      if (kind === "timetable") await api.timetableVpDecision(selected.id, "return", reason, selected.version_no);
      else await api.decideAcademicCalendarEntry(selected.id, { action: "return", reason, expected_version: selected.version_no });
      setReturnOpen(false); setSelected(null); setReason(""); await load();
    } catch (err: any) { setError(err.message || "Unable to return this academic item."); }
    finally { setBusy(false); }
  };

  if (!plans) return <Spinner />;
  const active = tab === "timetable" ? timetableQueue : calendarQueue;
  return <div className="fade-in vp-academic-approvals">
    <PageHead title="Academic Approvals" sub="Operational approval for academically governed timetables and calendar milestones." right={<button className="btn btn-out" disabled={busy} onClick={() => void load()}>Refresh</button>} />
    {error && <div className="calendar-banner warn">{error}</div>}
    <section className="vp-approval-hero"><div><span>VICE PRINCIPAL · OPERATIONAL CONTROL</span><h2>Approve only after academic governance is complete.</h2><p>Every item here has already passed its required academic stage. Your decision completes operational approval; publication remains with the Academic Coordinator.</p></div><div className="vp-approval-metrics"><div><b>{timetableQueue.length}</b><small>timetable reviews</small></div><div><b>{calendarQueue.length}</b><small>calendar reviews</small></div></div></section>
    <div className="vp-approval-tabs" role="tablist"><button className={tab === "timetable" ? "active" : ""} onClick={() => setTab("timetable")}>Timetable approvals <span>{timetableQueue.length}</span></button><button className={tab === "calendar" ? "active" : ""} onClick={() => setTab("calendar")}>Calendar approvals <span>{calendarQueue.length}</span></button></div>
    <section className="card vp-approval-queue"><div className="card-h"><div><h3>{tab === "timetable" ? "Timetables awaiting operational approval" : "Calendar milestones awaiting operational approval"}</h3><p className="hint">Review the submitted version. Return it when operational constraints need correction.</p></div><Pill s={active.length ? "VP Review" : "Clear"} /></div>{active.length ? <div className="vp-approval-grid">{active.map((item: any) => tab === "timetable" ? <TimetableCard key={item.id} plan={item} onOpen={() => open(item, "timetable")} /> : <CalendarCard key={item.id} entry={item} onOpen={() => open(item, "calendar")} />)}</div> : <Empty text={tab === "timetable" ? "No timetables are awaiting VP operational approval." : "No calendar milestones are awaiting VP operational approval."} />}</section>
    {selected && <Modal title={kind === "timetable" ? `Operational timetable review · ${selected.offering?.course_code || "Course"}` : `Operational calendar review · ${selected.title}`} className="vp-approval-modal" onClose={() => !busy && setSelected(null)} footer={<div className="modal-actions"><button className="btn btn-out" disabled={busy} onClick={() => setSelected(null)}>Close</button><button className="btn btn-out" disabled={busy} onClick={() => { setReturnOpen(true); setReason(""); }}>Return for correction</button><button className="btn btn-crimson" disabled={busy} onClick={() => void approve()}>{busy ? "Saving..." : "Operationally approve"}</button></div>}><ReviewDetail item={selected} kind={kind} /></Modal>}
    {returnOpen && <Modal title="Return for operational correction" onClose={() => !busy && setReturnOpen(false)} footer={<div className="modal-actions"><button className="btn btn-out" disabled={busy} onClick={() => setReturnOpen(false)}>Cancel</button><button className="btn btn-crimson" disabled={busy} onClick={() => void returnForCorrection()}>{busy ? "Returning..." : "Return item"}</button></div>}><p className="hint">State the operational constraint that must be addressed before this item can proceed.</p><label className="form-row">Return reason<textarea className="inp" rows={5} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Example: The room is unavailable for this slot; propose an approved alternative." /></label></Modal>}
    <style>{styles}</style>
  </div>;
}

function TimetableCard({ plan, onOpen }: any) { return <article className="vp-approval-card"><div><span>{plan.offering?.term}</span><h4>{plan.offering?.course_code} · Section {plan.section}</h4><p>{plan.offering?.course_title}</p></div><div className="vp-card-facts"><Fact label="Faculty" value={plan.faculty || "Unassigned"} /><Fact label="Schedule" value={`${DAYS[Number(plan.timetable?.day_of_week)] || "—"} · ${plan.timetable?.start_time || "—"}–${plan.timetable?.end_time || "—"}`} /><Fact label="Location" value={[plan.timetable?.room, plan.timetable?.building].filter(Boolean).join(" · ") || "—"} /></div><button className="btn btn-out" onClick={onOpen}>Review operational fit</button></article>; }
function CalendarCard({ entry, onOpen }: any) { return <article className="vp-approval-card"><div><span>{entry.academic_year} · {entry.term}</span><h4>{entry.title}</h4><p>{entry.category} · {entry.campus || "All Campuses"}</p></div><div className="vp-card-facts"><Fact label="Dates" value={`${entry.start_date} to ${entry.end_date}`} /><Fact label="Scope" value={entry.student_year ? `Year ${entry.student_year}` : "All years"} /><Fact label="Version" value={`Version ${entry.version_no}`} /></div><button className="btn btn-out" onClick={onOpen}>Review operational fit</button></article>; }
function ReviewDetail({ item, kind }: any) { const isPlan = kind === "timetable"; return <div className="vp-review-detail"><div className="vp-review-status"><Pill s={item.status} /><span>{isPlan ? `Plan ${item.id} · Version ${item.version_no}` : `Calendar ${item.id} · Version ${item.version_no}`}</span></div><section><h3>{isPlan ? "Submitted timetable" : "Submitted calendar milestone"}</h3>{isPlan ? <div className="vp-detail-grid"><Fact label="Course" value={`${item.offering?.course_code || "—"} · ${item.offering?.course_title || "—"}`} /><Fact label="Section" value={item.section || "—"} /><Fact label="Faculty" value={item.faculty || "Unassigned"} /><Fact label="Schedule" value={`${DAYS[Number(item.timetable?.day_of_week)] || "—"} · ${item.timetable?.start_time || "—"}–${item.timetable?.end_time || "—"}`} /><Fact label="Room" value={[item.timetable?.room, item.timetable?.building].filter(Boolean).join(" · ") || "—"} /><Fact label="Term" value={item.offering?.term || "—"} /></div> : <div className="vp-detail-grid"><Fact label="Dates" value={`${item.start_date} to ${item.end_date}`} /><Fact label="Category" value={item.category} /><Fact label="Campus" value={item.campus || "All Campuses"} /><Fact label="Scope" value={item.student_year ? `Year ${item.student_year}` : "All years"} /><Fact label="Description" value={item.description || "—"} /></div>}</section><section><h3>Decision boundary</h3><p>Academic review is complete. Approve only if operational delivery is feasible. Approval sends the item back to the Academic Coordinator for controlled publication.</p></section></div>; }
function Fact({ label, value }: any) { return <div><small>{label}</small><b>{value}</b></div>; }
const styles = `.vp-academic-approvals{color:#2c2629}.vp-approval-hero{display:flex;justify-content:space-between;gap:24px;margin:18px 0;padding:28px;border-radius:18px;background:linear-gradient(125deg,#1f3540,#274f5a 60%,#af8337);color:#fff}.vp-approval-hero>div:first-child{max-width:700px}.vp-approval-hero span{font-size:10px;font-weight:800;letter-spacing:.12em;color:#f1d295}.vp-approval-hero h2{margin:7px 0;color:#fff;font-size:25px}.vp-approval-hero p{margin:0;color:#e7f0f2;font-size:13px;line-height:1.55}.vp-approval-metrics{display:flex;align-self:center;gap:8px}.vp-approval-metrics div{min-width:92px;padding:13px;border:1px solid rgba(255,255,255,.25);border-radius:12px;text-align:center;background:rgba(255,255,255,.1)}.vp-approval-metrics b,.vp-approval-metrics small{display:block}.vp-approval-metrics b{font-size:26px}.vp-approval-metrics small{margin-top:3px;font-size:9px;text-transform:uppercase;letter-spacing:.05em;color:#f5dfb4}.vp-approval-tabs{display:flex;gap:8px;margin:22px 0 14px;border-bottom:1px solid #e4e5e5}.vp-approval-tabs button{border:0;border-bottom:3px solid transparent;background:transparent;padding:11px 15px;color:#677075;font-weight:800;cursor:pointer}.vp-approval-tabs button.active{color:#1d5665;border-bottom-color:#257187}.vp-approval-tabs span{margin-left:5px;padding:2px 6px;border-radius:99px;background:#edf1f2;font-size:11px}.vp-approval-queue{margin-top:10px}.vp-approval-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(295px,1fr));gap:14px;padding:16px}.vp-approval-card{display:grid;gap:16px;padding:18px;border:1px solid #dce6e8;border-radius:14px;background:linear-gradient(145deg,#fff,#f7fbfc)}.vp-approval-card span{font-size:10px;font-weight:800;letter-spacing:.08em;color:#54737b;text-transform:uppercase}.vp-approval-card h4{margin:5px 0;font-size:16px}.vp-approval-card p{margin:0;color:#747f82;font-size:12px}.vp-card-facts,.vp-detail-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.vp-card-facts>div,.vp-detail-grid>div{padding:10px;border-radius:9px;background:#eff5f6}.vp-card-facts small,.vp-detail-grid small{display:block;font-size:9px;font-weight:800;letter-spacing:.05em;color:#6d7d82;text-transform:uppercase}.vp-card-facts b,.vp-detail-grid b{display:block;margin-top:5px;font-size:12px;line-height:1.4;color:#2e444a}.vp-review-detail{display:grid;gap:15px;max-height:63vh;overflow:auto}.vp-review-status{display:flex;align-items:center;gap:10px;color:#6d777a;font-size:12px}.vp-review-detail section{padding:15px;border:1px solid #dfe7e9;border-radius:12px}.vp-review-detail h3{margin:0 0 10px;font-size:14px}.vp-review-detail p{margin:5px 0;color:#627075;line-height:1.55;font-size:13px}@media(max-width:650px){.vp-approval-hero{flex-direction:column}.vp-approval-metrics{align-self:stretch}.vp-approval-metrics div{flex:1}.vp-card-facts,.vp-detail-grid{grid-template-columns:1fr}.vp-approval-hero h2{font-size:21px}}`;
