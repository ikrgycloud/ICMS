import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Empty, Modal, PageHead, Pill, Spinner } from "./kit";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const EMPTY_ENTRY = { day_of_week: 0, start_time: "09:00", end_time: "10:00", room: "", building: "", effective_from: "", effective_to: "" };

export default function AcademicCoordinatorTimetable() {
  const [sections, setSections] = useState<any[] | null>(null);
  const [offerings, setOfferings] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [conflicts, setConflicts] = useState<any[]>([]);
  const [year, setYear] = useState(1);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [openBranches, setOpenBranches] = useState<Record<string, boolean>>({});
  const [openCourses, setOpenCourses] = useState<Record<string, boolean>>({});
  const [sectionModal, setSectionModal] = useState(false);
  const [entryModal, setEntryModal] = useState<any>(null);
  const [editingEntry, setEditingEntry] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [sectionForm, setSectionForm] = useState({ offering_id: "", section_code: "A", faculty_id: "", room: "" });
  const [entryForm, setEntryForm] = useState({ ...EMPTY_ENTRY });

  async function load() {
    setError("");
    try {
      const [sectionResult, offeringResult, planResult, conflictResult] = await Promise.all([
        api.sections(), api.courseOfferings(), api.timetablePlans(), api.academicConflicts(),
      ]);
      const loaded = await Promise.all((sectionResult.sections || []).map(async (section: any) => ({
        ...section, timetable: (await api.sectionTimetable(section.id)).entries || [],
      })));
      setSections(loaded);
      setOfferings(offeringResult.offerings || []);
      setPlans(planResult.plans || []);
      setConflicts(conflictResult.conflicts || []);
    } catch (e: any) {
      setError(e.message || "Unable to load sections and timetable");
    }
  }

  useEffect(() => { load(); }, []);

  const visibleSections = useMemo(() => (sections || []).filter((section) => Math.ceil(Number(section.semester || 1) / 2) === year), [sections, year]);
  const branches = useMemo(() => {
    const grouped = new Map<string, any[]>();
    visibleSections.forEach((section) => {
      const name = section.program_code || section.program || section.department || "Unassigned Branch";
      const key = name.toLowerCase();
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key)!.push(section);
    });
    return Array.from(grouped.entries()).map(([key, rows]) => {
      const courseMap = new Map<string, any[]>();
      rows.forEach((section) => {
        const courseKey = String(section.course_id || section.course_code || section.id);
        if (!courseMap.has(courseKey)) courseMap.set(courseKey, []);
        courseMap.get(courseKey)!.push(section);
      });
      return {
        key,
        name: rows[0].program_code || rows[0].program || rows[0].department || "Unassigned Branch",
        courses: Array.from(courseMap.entries()).map(([courseKey, courseRows]) => ({
          key: courseKey, code: courseRows[0].course_code || "—", title: courseRows[0].course_title || "Untitled course", sections: courseRows,
        })),
      };
    }).sort((a, b) => a.name.localeCompare(b.name));
  }, [visibleSections]);

  const planFor = (entryId: string) => plans.find((plan) => String(plan.timetable_entry_id) === String(entryId));
  const conflictsFor = (entryId: string) => conflicts.filter((conflict) => String(conflict.left?.entry_id) === String(entryId) || String(conflict.right?.entry_id) === String(entryId));
  const selectedOffering = offerings.find((row) => row.id === sectionForm.offering_id);
  const offeringFaculty = selectedOffering?.faculty_allocations?.find((row: any) => ["Assigned", "Confirmed"].includes(row.status))?.faculty_id || "";

  async function createSection() {
    if (!selectedOffering) return setError("Select a course offering first");
    setBusy(true);
    try {
      await api.createSection({ course_id: selectedOffering.course_id, ...sectionForm, faculty_id: sectionForm.faculty_id || offeringFaculty });
      setSectionModal(false); setMessage("Section created."); await load();
    } catch (e: any) { setError(e.message || "Unable to create section"); }
    finally { setBusy(false); }
  }

  function openEntry(section: any, entry?: any) {
    setEntryModal(section); setEditingEntry(entry || null);
    setEntryForm(entry ? { day_of_week: entry.day_of_week, start_time: entry.start_time, end_time: entry.end_time, room: entry.room || section.room || "", building: entry.building || "", effective_from: entry.effective_from || "", effective_to: entry.effective_to || "" } : { ...EMPTY_ENTRY, room: section.room || "" });
  }

  async function saveEntry() {
    setBusy(true);
    try {
      if (editingEntry) await api.updateTimetableEntry(editingEntry.id, entryForm);
      else await api.createTimetableEntry(entryModal.id, entryForm);
      setEntryModal(null); setMessage(editingEntry ? "Timetable updated." : "Timetable created."); await load();
    } catch (e: any) { setError(e.message || "Unable to save timetable"); }
    finally { setBusy(false); }
  }

  async function deactivate(entry: any) {
    if (!window.confirm("Deactivate this timetable entry?")) return;
    try { await api.deactivateTimetableEntry(entry.id); setMessage("Timetable entry deactivated."); await load(); }
    catch (e: any) { setError(e.message || "Unable to deactivate timetable"); }
  }

  async function submit(entry: any, section: any) {
    try { await api.submitTimetablePlan({ timetable_entry_id: entry.id, section_id: section.id, offering_id: section.offering_id }); setMessage("Submitted for HOD review."); await load(); }
    catch (e: any) { setError(e.message || "Unable to submit timetable"); }
  }

  async function resolveConflict(conflict: any) {
    const note = window.prompt("Resolution note") || "";
    if (!note.trim()) return;
    try { await api.resolveAcademicConflict(conflict.id, note); setMessage("Conflict resolved."); await load(); }
    catch (e: any) { setError(e.message || "Unable to resolve conflict"); }
  }

  if (!sections) return error ? <div className="calendar-banner warn">{error}</div> : <Spinner />;
  return <div className="fade-in coordinator-timetable">
    <PageHead title="Sections & Timetable" sub="Course Offering → HOD Input / Faculty Allocation → Sections → Timetable → Review" right={<div className="timetable-actions"><button className="btn btn-crimson" onClick={() => { setSectionForm({ offering_id: offerings[0]?.id || "", section_code: "A", faculty_id: "", room: "" }); setSectionModal(true); }}>Create section</button><button className="btn btn-out" onClick={load}>Refresh</button></div>} />
    {error && <div className="calendar-banner warn">{error}</div>}{message && <div className="calendar-banner success">{message}</div>}
    <div className="academic-year-nav">{[1, 2, 3, 4].map((candidate) => { const count = (sections || []).filter((row) => Math.ceil(Number(row.semester || 1) / 2) === candidate).length; return <button key={candidate} className={`academic-year-item ${year === candidate ? "active" : ""}`} onClick={() => { setYear(candidate); setOpenBranches({}); setOpenCourses({}); }}><span>{candidate === 1 ? "1st" : candidate === 2 ? "2nd" : candidate === 3 ? "3rd" : "4th"} Year</span><small>{count} {count === 1 ? "section" : "sections"}</small></button>; })}</div>
    {!branches.length ? <section className="timetable-empty"><Empty text="No sections found for this year." /></section> : <div className="academic-tree">{branches.map((branch) => { const branchOpen = !!openBranches[branch.key]; return <section className={`branch-panel ${branchOpen ? "open" : ""}`} key={branch.key}><button className="branch-header" onClick={() => setOpenBranches({ ...openBranches, [branch.key]: !branchOpen })}><div className="branch-left"><span className="tree-chevron">{branchOpen ? "⌄" : "›"}</span><div><h2>{branch.name}</h2><p>{branch.courses.length} {branch.courses.length === 1 ? "course" : "courses"}</p></div></div><span className="branch-count">{branch.courses.length}</span></button>{branchOpen && <div className="course-list">{branch.courses.map((course: any) => { const courseKey = `${branch.key}-${course.key}`; const courseOpen = !!openCourses[courseKey]; return <div className={`course-panel ${courseOpen ? "open" : ""}`} key={courseKey}><button className="course-header" onClick={() => setOpenCourses({ ...openCourses, [courseKey]: !courseOpen })}><div className="course-header-left"><span className="course-chevron">{courseOpen ? "⌄" : "›"}</span><div><strong>{course.code}</strong><span>{course.title}</span></div></div><span>{course.sections.length} {course.sections.length === 1 ? "section" : "sections"}</span></button>{courseOpen && <div className="section-list">{course.sections.map((section: any) => <SectionCard key={section.id} section={section} planFor={planFor} conflictsFor={conflictsFor} onEdit={openEntry} onDeactivate={deactivate} onSubmit={submit} onResolve={resolveConflict} />)}</div>}</div>; })}</div>}</section>; })}</div>}
    {sectionModal && <Modal title="Create section" onClose={() => setSectionModal(false)} footer={<div className="modal-actions"><button className="btn btn-out" onClick={() => setSectionModal(false)}>Cancel</button><button className="btn btn-crimson" disabled={busy} onClick={createSection}>{busy ? "Creating..." : "Create section"}</button></div>}><div className="form-grid"><label>Course offering<select className="select" value={sectionForm.offering_id} onChange={(e) => setSectionForm({ ...sectionForm, offering_id: e.target.value, faculty_id: "" })}>{offerings.map((row) => <option key={row.id} value={row.id}>{row.course_code} · {row.program_code} · Sem {row.semester}</option>)}</select></label><label>Section code<input className="inp" value={sectionForm.section_code} onChange={(e) => setSectionForm({ ...sectionForm, section_code: e.target.value })} /></label><label>Faculty<select className="select" value={sectionForm.faculty_id || offeringFaculty} onChange={(e) => setSectionForm({ ...sectionForm, faculty_id: e.target.value })}><option value={offeringFaculty}>Use offering allocation</option>{(selectedOffering?.faculty_allocations || []).map((row: any) => <option key={row.faculty_id} value={row.faculty_id}>{row.faculty || row.faculty_id}</option>)}</select></label><label>Room<input className="inp" value={sectionForm.room} onChange={(e) => setSectionForm({ ...sectionForm, room: e.target.value })} /></label></div></Modal>}
    {entryModal && <Modal title={`${editingEntry ? "Edit" : "Create"} timetable · Section ${entryModal.section}`} onClose={() => setEntryModal(null)} footer={<div className="modal-actions"><button className="btn btn-out" onClick={() => setEntryModal(null)}>Cancel</button><button className="btn btn-crimson" disabled={busy} onClick={saveEntry}>{busy ? "Saving..." : "Save timetable"}</button></div>}><div className="form-grid"><label>Day<select className="select" value={entryForm.day_of_week} onChange={(e) => setEntryForm({ ...entryForm, day_of_week: Number(e.target.value) })}>{DAYS.map((day, index) => <option key={day} value={index}>{day}</option>)}</select></label><label>Start time<input className="inp" type="time" value={entryForm.start_time} onChange={(e) => setEntryForm({ ...entryForm, start_time: e.target.value })} /></label><label>End time<input className="inp" type="time" value={entryForm.end_time} onChange={(e) => setEntryForm({ ...entryForm, end_time: e.target.value })} /></label><label>Room<input className="inp" value={entryForm.room} onChange={(e) => setEntryForm({ ...entryForm, room: e.target.value })} /></label><label>Building<input className="inp" value={entryForm.building} onChange={(e) => setEntryForm({ ...entryForm, building: e.target.value })} /></label><label>Effective from<input className="inp" type="date" value={entryForm.effective_from} onChange={(e) => setEntryForm({ ...entryForm, effective_from: e.target.value })} /></label><label>Effective to<input className="inp" type="date" value={entryForm.effective_to} onChange={(e) => setEntryForm({ ...entryForm, effective_to: e.target.value })} /></label></div></Modal>}
    <style>{styles}</style>
  </div>;
}

function SectionCard({ section, planFor, conflictsFor, onEdit, onDeactivate, onSubmit, onResolve }: any) {
  const [open, setOpen] = useState(false);
  return <div className={`section-panel ${open ? "open" : ""}`}><button className="section-header" onClick={() => setOpen(!open)}><div><strong>Section {section.section}</strong><span>Faculty: {section.faculty || "Not assigned"} · Room: {section.room || "Not assigned"}</span></div><span>{section.timetable.length} timetable {section.timetable.length === 1 ? "entry" : "entries"}</span></button>{open && <div className="section-body"><div className="section-toolbar"><span>{section.enrolled || 0}/{section.capacity || "—"} enrolled</span><button className="btn btn-out" onClick={() => onEdit(section)}>Add timetable</button></div>{!section.timetable.length && <Empty text="No timetable entries yet." />}{section.timetable.map((entry: any) => { const plan = planFor(entry.id); const activeConflicts = conflictsFor(entry.id).filter((row: any) => row.status !== "Resolved"); const firstConflict = activeConflicts[0]; return <div className="timetable-entry" key={entry.id}><div><b>{DAYS[entry.day_of_week]} · {entry.start_time}–{entry.end_time}</b><span>{entry.room || "No room"}{entry.building ? ` · ${entry.building}` : ""}</span></div><div className="entry-actions"><Pill s={activeConflicts.length ? "Conflict" : plan?.status || "Draft"} />{firstConflict && <button className="linkish danger" onClick={() => onResolve(firstConflict)}>Resolve conflict{activeConflicts.length > 1 ? ` (${activeConflicts.length})` : ""}</button>}<button className="linkish" onClick={() => onEdit(section, entry)}>Edit</button>{entry.status === "active" && <button className="linkish danger" onClick={() => onDeactivate(entry)}>Deactivate</button>}{entry.status === "active" && (!plan || ["Draft", "HOD Returned", "VP Returned"].includes(plan.status)) && !activeConflicts.length && <button className="btn btn-out" onClick={() => onSubmit(entry, section)}>Submit HOD review</button>}</div></div>; })}</div>}</div>;
}

const styles = `.coordinator-timetable{color:#2d2528}.timetable-actions,.modal-actions,.section-toolbar,.entry-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.academic-year-nav{display:flex;gap:8px;margin:28px 0 24px;border-bottom:1px solid #e9e2e4;overflow-x:auto}.academic-year-item{border:0;background:transparent;min-width:112px;padding:12px 18px 14px;cursor:pointer;color:#6d6266;text-align:left;position:relative}.academic-year-item span,.academic-year-item small{display:block;white-space:nowrap}.academic-year-item span{font-size:14px;font-weight:700}.academic-year-item small{margin-top:4px;color:#968b90;font-size:11px}.academic-year-item.active{color:#741f32}.academic-year-item.active:after{content:"";position:absolute;left:14px;right:14px;bottom:-1px;height:3px;background:#741f32}.academic-tree{display:flex;flex-direction:column;gap:12px}.branch-panel,.course-panel,.section-panel{background:#fff;border:1px solid #e8e1e3;border-radius:10px;overflow:hidden}.branch-panel.open,.course-panel.open,.section-panel.open{border-color:#d8c6cb;box-shadow:0 4px 18px rgba(53,27,34,.05)}.branch-header,.course-header,.section-header{width:100%;border:0;background:#fff;display:flex;align-items:center;justify-content:space-between;gap:14px;cursor:pointer;text-align:left}.branch-header{padding:18px 20px}.course-header{padding:14px 16px}.section-header{padding:13px 15px}.branch-header:hover,.course-header:hover,.section-header:hover{background:#fcf9fa}.branch-left,.course-header-left{display:flex;align-items:center;gap:12px;min-width:0}.branch-header h2{margin:0;font-size:17px}.branch-header p{margin:5px 0 0;color:#8a7d82;font-size:12px}.tree-chevron,.course-chevron{width:28px;height:28px;border-radius:50%;background:#f7f0f2;color:#741f32;display:grid;place-items:center;font-size:19px;flex:0 0 auto}.branch-count{width:30px;height:30px;border-radius:50%;background:#741f32;color:#fff;display:grid;place-items:center;font-size:12px;font-weight:700}.course-header-left>div,.section-header>div:first-child{display:flex;flex-direction:column;gap:4px;min-width:0}.course-header-left span,.section-header span,.section-body,.timetable-entry span{color:#82767b;font-size:12px}.course-list{border-top:1px solid #eee7e9;background:#fbfafb;padding:8px 14px 14px 48px;display:flex;flex-direction:column;gap:8px}.section-list{padding:10px 14px 14px 42px;display:flex;flex-direction:column;gap:8px;background:#fdfbfc}.section-body{padding:13px 15px;border-top:1px solid #eee7e9}.section-toolbar{justify-content:space-between;margin-bottom:12px}.timetable-entry{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:12px;border:1px solid #ebe4e6;border-radius:8px;margin-top:8px}.timetable-entry>div:first-child{display:flex;flex-direction:column;gap:4px}.entry-actions{justify-content:flex-end}.linkish.danger{color:#a3293e}.timetable-empty{background:#fff;border:1px solid #ebe4e6;border-radius:12px;padding:35px 20px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.form-grid label{display:flex;flex-direction:column;gap:7px;color:#5f5559;font-size:12px;font-weight:700}.form-grid .select,.form-grid .inp{width:100%;box-sizing:border-box}.calendar-banner{margin:12px 0}@media(max-width:700px){.course-list,.section-list{padding-left:10px}.timetable-entry{align-items:flex-start;flex-direction:column}.entry-actions{justify-content:flex-start}.form-grid{grid-template-columns:1fr}}`;
