import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { Empty, PageHead, Pill, Spinner } from "./kit";

type Filters = { academicYear: string; term: string; semester: string; year: string; branch: string; program: string; department: string; course: string; status: string };
const initialFilters: Filters = { academicYear: "", term: "", semester: "", year: "", branch: "", program: "", department: "", course: "", status: "" };
const label = (year: string) => year === "1" ? "1st Year" : year === "2" ? "2nd Year" : year === "3" ? "3rd Year" : year === "4" ? "4th Year" : year;
const pct = (value: any) => value == null || value === "" ? "—" : `${value}%`;

export default function AcademicCoordinatorReports({ onNavigate }: { onNavigate?: (view: string) => void }) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [filtersOpen, setFiltersOpen] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      api.academicPrograms(), api.courseOfferings(), api.sections(), api.timetablePlans(),
      api.academicConflicts(), api.classSessions(), api.curriculumExecution(),
      api.academicCalendar(), api.academicAnnouncements(),
    ]).then((results: any[]) => {
      const value = results.map((result) => result.status === "fulfilled" ? result.value : {});
      setData({ programs: value[0].programs || [], offerings: value[1].offerings || [], sections: value[2].sections || [], plans: value[3].plans || [], conflicts: value[4].conflicts || [], sessions: value[5].sessions || [], execution: value[6].items || [], calendar: value[7].entries || [], notices: value[8].announcements || [] });
    }).catch((e: any) => setError(e.message || "Unable to load reports"));
  }, []);

  const options = useMemo(() => {
    if (!data) return {};
    const execution = data.execution;
    return {
      academicYear: unique(execution.map((x: any) => x.academic_year)),
      term: unique(execution.map((x: any) => x.term)),
      semester: unique(execution.map((x: any) => x.semester)),
      year: unique(execution.map((x: any) => x.student_year)),
      branch: unique(execution.map((x: any) => x.program_code || x.program)),
      program: unique(execution.map((x: any) => x.program_code || x.program)),
      department: unique(execution.map((x: any) => x.department)),
      course: unique(execution.map((x: any) => x.course_code)),
      status: unique([...execution.map((x: any) => x.execution_status), ...data.plans.map((x: any) => x.status)]),
    };
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return null;
    const matches = (row: any) => {
      const year = String(row.student_year || Math.ceil(Number(row.semester || 1) / 2));
      const branch = row.program_code || row.program || "";
      return (!filters.academicYear || row.academic_year === filters.academicYear) && (!filters.term || row.term === filters.term) && (!filters.semester || String(row.semester) === filters.semester) && (!filters.year || year === filters.year) && (!filters.branch || branch === filters.branch) && (!filters.program || branch === filters.program) && (!filters.department || row.department === filters.department) && (!filters.course || row.course_code === filters.course) && (!filters.status || row.execution_status === filters.status);
    };
    const execution = data.execution.filter(matches);
    const ids = new Set(execution.map((row: any) => row.id));
    const sections = data.sections.filter((row: any) => !filters.course || row.course_code === filters.course).filter((row: any) => !filters.program || row.program_code === filters.program || row.program === filters.program);
    const offeringIds = new Set(execution.map((row: any) => row.id));
    const plans = data.plans.filter((plan: any) => offeringIds.has(plan.offering_id) || !filters.course);
    const conflicts = data.conflicts.filter((conflict: any) => !filters.status || conflict.status === filters.status);
    const sessions = data.sessions.filter((session: any) => ids.has(session.offering_id) || !filters.course);
    const calendar = data.calendar.filter((row: any) => (!filters.academicYear || row.academic_year === filters.academicYear) && (!filters.term || row.term === filters.term) && (!filters.department || row.department_id === filters.department));
    return { execution, sections, plans, conflicts, sessions, calendar, notices: data.notices };
  }, [data, filters]);

  if (!data || !filtered) return error ? <div className="calendar-banner warn">{error}</div> : <Spinner />;
  const activeConflicts = filtered.conflicts.filter((row: any) => !["Resolved", "resolved"].includes(row.status));
  const readyOfferings = filtered.execution.filter((row: any) => row.readiness?.ready).length;
  const scheduled = filtered.execution.filter((row: any) => row.timetable_readiness === "Ready").length;
  const completed = filtered.execution.filter((row: any) => row.execution_status === "Completed").length;
  const facultyReady = filtered.execution.filter((row: any) => row.faculty_readiness === "Ready").length;
  const workflow = [
    ["Course Offerings", filtered.execution.length, "coordinator_course_offerings"],
    ["HOD Input", filtered.execution.filter((row: any) => row.hod_input?.status === "Submitted").length, "coordinator_course_offerings"],
    ["Faculty Allocation", facultyReady, "coordinator_course_offerings"],
    ["Sections", filtered.sections.length, "coordinator_sections"],
    ["Timetable", scheduled, "coordinator_sections"],
    ["HOD Review", filtered.plans.filter((row: any) => row.status === "HOD Review").length, "coordinator_requests"],
    ["VP Review", filtered.plans.filter((row: any) => row.status === "VP Review").length, "coordinator_requests"],
    ["Approved", filtered.plans.filter((row: any) => row.status === "Approved").length, "coordinator_requests"],
    ["Published", filtered.plans.filter((row: any) => row.status === "Published").length, "coordinator_requests"],
  ];

  return <div className="fade-in reports-page">
    <style>{styles}</style>
    <PageHead title="Academic Operations Reports" sub="Read-only operational view of the academic delivery chain." right={<button className="btn btn-out" onClick={() => window.print()}>Print report</button>} />

    <div className="print-report">
      <h1>Academic Coordinator Reports</h1>
      <p className="print-meta">Generated {new Date().toLocaleDateString()} · Filtered academic operations summary</p>
      <PrintSection title="Curriculum completion">
        <PrintTable headers={["Course", "Title", "Expected completion", "Actual completion", "Progress", "Status"]}>
          {filtered.execution.map((row: any) => <tr key={`print-execution-${row.id}`}><td>{row.course_code || "—"}</td><td>{row.course_title || "—"}</td><td>{row.expected_completion_date || "—"}</td><td>{row.actual_completion_date || "—"}</td><td>{row.progress || 0}%</td><td>{row.execution_status || "—"}</td></tr>)}
        </PrintTable>
      </PrintSection>
      <PrintSection title="Section readiness">
        <PrintTable headers={["Course", "Program", "Required sections", "Created sections", "Readiness"]}>
          {filtered.execution.map((row: any) => <tr key={`print-section-${row.id}`}><td>{row.course_code || "—"}</td><td>{row.program_code || row.program || "—"}</td><td>{row.section_readiness?.required_sections || 0}</td><td>{row.section_readiness?.created_sections || 0}</td><td>{row.section_readiness?.status || (row.section_readiness?.created_sections >= row.section_readiness?.required_sections ? "Ready" : "In progress")}</td></tr>)}
        </PrintTable>
      </PrintSection>
      <PrintSection title="Faculty allocation">
        <PrintTable headers={["Course", "Faculty", "Allocation status"]}>
          {filtered.execution.map((row: any) => <tr key={`print-faculty-${row.id}`}><td>{row.course_code || "—"}</td><td>{row.faculty || "No faculty assigned"}</td><td>{row.faculty_readiness || "Not Ready"}</td></tr>)}
        </PrintTable>
      </PrintSection>
      <PrintSection title="Timetable operations">
        <PrintTable headers={["Metric", "Count", "Details"]}>
          <tr><td>Scheduled offerings</td><td>{scheduled}</td><td>Ready for timetable</td></tr>
          <tr><td>Draft / returned plans</td><td>{filtered.plans.filter((row: any) => ["Draft", "HOD Returned", "VP Returned"].includes(row.status)).length}</td><td>Needs work</td></tr>
          <tr><td>Published plans</td><td>{filtered.plans.filter((row: any) => row.status === "Published").length}</td><td>Live</td></tr>
        </PrintTable>
      </PrintSection>
      <PrintSection title="Conflict summary">
        <PrintTable headers={["Severity", "Active conflicts"]}>
          {["Critical", "High", "Medium"].map((severity) => <tr key={`print-conflict-${severity}`}><td>{severity}</td><td>{filtered.conflicts.filter((row: any) => row.severity === severity && row.status !== "Resolved").length}</td></tr>)}
        </PrintTable>
      </PrintSection>
      <PrintSection title="Academic calendar">
        <PrintTable headers={["Date", "Title", "Category", "Status"]}>
          {filtered.calendar.map((row: any, index: number) => <tr key={`print-calendar-${row.id || index}`}><td>{row.start_date || row.date || "—"}</td><td>{row.title || row.name || "—"}</td><td>{row.category || "—"}</td><td>{row.status || "—"}</td></tr>)}
        </PrintTable>
      </PrintSection>
    </div>

    <div className="screen-report">
    <section className="report-filter-bar">
      <div className="report-filter-head"><div><span className="report-kicker">REPORT SCOPE</span><h2>Live filters</h2></div><button className="linkish" onClick={() => setFiltersOpen(!filtersOpen)}>{filtersOpen ? "Hide filters" : "Show filters"}</button></div>
      {filtersOpen && <div className="report-filters">{Object.entries(options).map(([key, values]) => <label key={key}>{pretty(key)}<select className="select" value={(filters as any)[key]} onChange={(e) => setFilters({ ...filters, [key]: e.target.value })}><option value="">All</option>{(values as any[]).map((value) => <option key={String(value)} value={String(value)}>{key === "year" ? label(String(value)) : String(value)}</option>)}</select></label>)}<button className="btn btn-out report-clear" onClick={() => setFilters(initialFilters)}>Clear</button></div>}
    </section>

    <section className="report-kpis"><Kpi label="Offerings ready" value={`${readyOfferings}/${filtered.execution.length}`} hint="Readiness" /><Kpi label="Timetable coverage" value={`${scheduled}/${filtered.execution.length}`} hint="Scheduled" /><Kpi label="Sections" value={filtered.sections.length} hint="Created" /><Kpi label="Active conflicts" value={activeConflicts.length} hint="Needs attention" /><Kpi label="Completed courses" value={completed} hint="Execution" /><Kpi label="Class sessions" value={filtered.sessions.length} hint="Persisted" /></section>

    <ReportSection title="Workflow status" subtitle="Course Offerings → HOD Input → Faculty Allocation → Sections → Timetable → HOD Review → VP Review → Approved → Published"><div className="workflow-strip">{workflow.map(([name, value], index) => <div className="workflow-step" key={name}><span>{index + 1}</span><b>{value}</b><small>{name}</small></div>)}</div></ReportSection>

    <div className="report-grid">
      <ReportSection title="Curriculum completion" subtitle="Expected and actual delivery progress."><div className="report-table-wrap"><table className="report-table"><thead><tr><th>Course</th><th>Expected</th><th>Actual</th><th>Progress</th><th>Status</th></tr></thead><tbody>{filtered.execution.slice(0, 12).map((row: any) => <tr key={row.id}><td><b>{row.course_code}</b><small>{row.course_title}</small></td><td>{row.expected_completion_date || "—"}</td><td>{row.actual_completion_date || "—"}</td><td>{row.progress || 0}%</td><td><Pill s={row.execution_status} /></td></tr>)}</tbody></table></div>{!filtered.execution.length && <Empty text="No curriculum records match the filters." />}</ReportSection>
      <ReportSection title="Section readiness" subtitle="Created sections against HOD requirements."><SummaryRows rows={filtered.execution.slice(0, 8).map((row: any) => ({ label: row.course_code, value: `${row.section_readiness?.created_sections || 0}/${row.section_readiness?.required_sections || 0}`, meta: row.program_code || row.program }))} /><NavButton text="Open sections & timetable" onClick={() => onNavigate?.("coordinator_sections")} /></ReportSection>
    </div>

    <div className="report-grid">
      <ReportSection title="Faculty allocation" subtitle="Allocation readiness by offering."><SummaryRows rows={filtered.execution.slice(0, 8).map((row: any) => ({ label: row.course_code, value: row.faculty_readiness || "Not Ready", meta: row.faculty || "No faculty" }))} /><NavButton text="Open course offerings" onClick={() => onNavigate?.("coordinator_course_offerings")} /></ReportSection>
      <ReportSection title="Timetable operations" subtitle="Persisted plan states and scheduled coverage."><SummaryRows rows={[{ label: "Scheduled offerings", value: scheduled, meta: "Ready" }, { label: "Draft / returned plans", value: filtered.plans.filter((row: any) => ["Draft", "HOD Returned", "VP Returned"].includes(row.status)).length, meta: "Needs work" }, { label: "Published plans", value: filtered.plans.filter((row: any) => row.status === "Published").length, meta: "Live" }]} /><NavButton text="Open sections & timetable" onClick={() => onNavigate?.("coordinator_sections")} /></ReportSection>
    </div>

    <div className="report-grid">
      <ReportSection title="Conflict summary" subtitle="Severity, type, and current status."><SummaryRows rows={["Critical", "High", "Medium"].map((severity) => ({ label: severity, value: filtered.conflicts.filter((row: any) => row.severity === severity && row.status !== "Resolved").length, meta: "Active" }))} /><div className="report-inline-stats"><span>Faculty {filtered.conflicts.filter((row: any) => row.type === "faculty_overlap").length}</span><span>Room {filtered.conflicts.filter((row: any) => ["room_conflict", "lab_conflict"].includes(row.type)).length}</span><span>Resolved {filtered.conflicts.filter((row: any) => row.status === "Resolved").length}</span></div><NavButton text="Open conflict center" onClick={() => onNavigate?.("coordinator_conflicts")} /></ReportSection>
      <ReportSection title="Class session operations" subtitle="Persisted sessions generated for delivery."><SummaryRows rows={[{ label: "Total sessions", value: filtered.sessions.length, meta: "Generated" }, { label: "Completed", value: filtered.sessions.filter((row: any) => ["Completed", "Complete"].includes(row.status)).length, meta: "Delivered" }, { label: "Planned / open", value: filtered.sessions.filter((row: any) => !["Completed", "Complete"].includes(row.status)).length, meta: "Upcoming" }]} /><NavButton text="Open timetable workflow" onClick={() => onNavigate?.("coordinator_sections")} /></ReportSection>
    </div>

    <div className="report-grid">
      <ReportSection title="Academic calendar" subtitle="Live milestones, exam windows, and breaks."><SummaryRows rows={[{ label: "Milestones", value: filtered.calendar.length, meta: "Visible" }, { label: "Exam windows", value: filtered.calendar.filter((row: any) => String(row.category).toLowerCase().includes("exam")).length, meta: "Calendar" }, { label: "Breaks", value: filtered.calendar.filter((row: any) => String(row.category).toLowerCase() === "break").length, meta: "Calendar" }]} /><NavButton text="Open academic calendar" onClick={() => onNavigate?.("academic_calendar")} /></ReportSection>
      <ReportSection title="Academic notices" subtitle="Published communications in the current scope."><SummaryRows rows={filtered.notices.slice(0, 5).map((row: any) => ({ label: row.title, value: row.published_at ? new Date(row.published_at).toLocaleDateString() : "—", meta: row.audience || "Academic" }))} />{!filtered.notices.length && <Empty text="No academic notices available." />}<NavButton text="Open academic notices" onClick={() => onNavigate?.("coordinator_notices")} /></ReportSection>
    </div>
    </div>
  </div>;
}

function unique(values: any[]) { return Array.from(new Set(values.filter((value) => value !== undefined && value !== null && value !== ""))).sort((a, b) => String(a).localeCompare(String(b), undefined, { numeric: true })); }
function pretty(value: string) { return value.replace(/([A-Z])/g, " $1").replace(/^./, (char) => char.toUpperCase()); }
function Kpi({ label, value, hint }: { label: string; value: any; hint: string }) { return <article className="report-kpi"><span>{label}</span><b>{value}</b><small>{hint}</small></article>; }
function ReportSection({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  const sectionRef = useRef<HTMLElement>(null);
  return <section className="report-section" ref={sectionRef}>
    <header><div><h2>{title}</h2><p>{subtitle}</p></div><button className="section-print-btn" onClick={() => printSection(title, sectionRef.current)}>Print / Save PDF</button></header>
    {children}
  </section>;
}
function SummaryRows({ rows }: { rows: { label: string; value: any; meta: any }[] }) { return <div className="summary-rows">{rows.map((row, index) => <div className="summary-row" key={`${row.label}-${index}`}><span>{row.label}</span><b>{row.value}</b><small>{row.meta}</small></div>)}</div>; }
function NavButton(_: { text: string; onClick: () => void }) { return null; }
function PrintSection({ title, children }: { title: string; children: React.ReactNode }) { return <section className="print-section"><h2>{title}</h2>{children}</section>; }
function PrintTable({ headers, children }: { headers: string[]; children: React.ReactNode }) { return <table className="print-table"><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{children}</tbody></table>; }
function printSection(title: string, section: HTMLElement | null) {
  if (!section) return;
  const content = section.cloneNode(true) as HTMLElement;
  content.querySelectorAll("button").forEach((button) => button.remove());
  const printWindow = window.open("", "_blank", "width=1000,height=800");
  if (!printWindow) return;
  printWindow.document.write(`<!doctype html><html><head><title>${title}</title><style>body{font-family:Arial,sans-serif;color:#222;padding:32px}h2{font-size:22px;border-bottom:2px solid #222;padding-bottom:8px}header p{color:#666;font-size:13px}.report-table,.summary-rows{width:100%;border-collapse:collapse}.report-table th,.report-table td{border:1px solid #999;padding:8px;text-align:left;font-size:12px}.report-table th{background:#eee}.summary-row{display:grid;grid-template-columns:1fr auto 180px;border-bottom:1px solid #ccc;padding:10px 0}.summary-row small{color:#666;text-align:right}@media print{body{padding:0}}</style></head><body>${content.outerHTML}</body></html>`);
  printWindow.document.close();
  printWindow.focus();
  printWindow.onload = () => { printWindow.print(); };
}

const styles = `.reports-page{--report-border:#e8e2e4;--report-muted:#81777b;color:#2d2528}.print-report{display:none}.report-filter-bar,.report-section{background:#fff;border:1px solid var(--report-border);border-radius:12px}.report-filter-bar{padding:18px 20px;margin:22px 0}.report-filter-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.report-kicker{color:#8c737a;font-size:10px;font-weight:800;letter-spacing:.08em}.report-filter-head h2{margin:3px 0 0;font-size:17px}.report-filters{display:grid;grid-template-columns:repeat(5,minmax(130px,1fr));gap:12px;margin-top:16px}.report-filters label{display:flex;flex-direction:column;gap:6px;color:#72686c;font-size:11px;font-weight:700;text-transform:uppercase}.report-filters .select{width:100%;min-height:38px}.report-clear{align-self:end;min-height:38px}.report-kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-bottom:18px}.report-kpi{padding:16px;border:1px solid var(--report-border);border-radius:10px;background:#fff}.report-kpi span,.report-kpi small{display:block;color:var(--report-muted);font-size:11px}.report-kpi b{display:block;margin:9px 0 4px;font-size:24px;color:#35282d}.report-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-bottom:18px}.report-section{padding:18px 20px;min-width:0}.report-section header{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:14px}.report-section h2{margin:0;font-size:16px}.report-section header p{margin:5px 0 0;color:var(--report-muted);font-size:12px}.section-print-btn{border:1px solid #7a1f35;border-radius:6px;background:#fff;color:#7a1f35;padding:7px 10px;font-size:11px;font-weight:700;cursor:pointer;white-space:nowrap}.section-print-btn:hover{background:#7a1f35;color:#fff}.workflow-strip{display:grid;grid-template-columns:repeat(9,minmax(0,1fr));gap:5px}.workflow-step{border:0;border-top:3px solid #d8cdd0;background:#faf8f9;padding:12px 7px;text-align:left}.workflow-step span{display:block;color:#9b8e93;font-size:10px}.workflow-step b{display:block;margin:7px 0 3px;color:#7a1f35;font-size:19px}.workflow-step small{display:block;color:#62585c;font-size:10px;line-height:1.3}.report-table-wrap{overflow-x:auto}.report-table{width:100%;border-collapse:collapse;font-size:12px}.report-table th{padding:9px 8px;color:#8a7d82;font-size:10px;text-align:left;text-transform:uppercase;border-bottom:1px solid var(--report-border)}.report-table td{padding:11px 8px;border-bottom:1px solid #f0ecee;white-space:nowrap}.report-table td small{display:block;margin-top:3px;color:var(--report-muted);white-space:normal}.summary-rows{display:flex;flex-direction:column}.summary-row{display:grid;grid-template-columns:minmax(0,1fr) auto 100px;align-items:center;gap:12px;padding:11px 0;border-bottom:1px solid #f0ecee}.summary-row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}.summary-row b{font-size:15px}.summary-row small{color:var(--report-muted);font-size:11px;text-align:right}.report-link{border:0;background:transparent;color:#7a1f35;font-size:12px;font-weight:700;padding:14px 0 0;cursor:pointer}.report-link:hover{text-decoration:underline}.report-inline-stats{display:flex;gap:14px;flex-wrap:wrap;padding-top:14px;color:#766a6f;font-size:11px}.print-report h1{margin:0 0 4px;font-size:24px}.print-meta{margin:0 0 24px;color:#555;font-size:12px}.print-section{margin:0 0 24px;break-inside:avoid}.print-section h2{font-size:17px;border-bottom:2px solid #222;padding-bottom:6px;margin:0 0 10px}.print-table{width:100%;border-collapse:collapse;font-size:10px}.print-table th,.print-table td{border:1px solid #999;padding:6px;text-align:left;vertical-align:top}.print-table th{background:#eee;font-weight:700}@media(max-width:1050px){.report-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.report-filters{grid-template-columns:repeat(3,minmax(130px,1fr))}.workflow-strip{grid-template-columns:repeat(5,minmax(0,1fr))}}@media(max-width:700px){.report-grid{grid-template-columns:1fr}.report-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.report-filters{grid-template-columns:1fr 1fr}.workflow-strip{grid-template-columns:repeat(3,minmax(0,1fr))}.report-section{padding:15px}.summary-row{grid-template-columns:minmax(0,1fr) auto}.summary-row small{grid-column:1/-1;text-align:left}.report-table td{white-space:normal}}@media print{.screen-report,.reports-page>.page-head{display:none!important}.print-report{display:block!important}.reports-page{background:#fff;color:#111}.print-section{page-break-inside:avoid}}`;
