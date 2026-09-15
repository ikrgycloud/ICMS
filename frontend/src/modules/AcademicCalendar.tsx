import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Empty, Modal, PageHead, Pill, Spinner } from "./kit";

const CATEGORIES = [
  "Planning",
  "Registration",
  "Teaching",
  "Assessment",
  "Examinations",
  "Review",
  "Results",
  "Break",
  "Experiential",
];
const blank = (term = "", academicYear = "") => ({
  id: "",
  term,
  academic_year: academicYear,
  title: "",
  category: "Teaching",
  campus: "All Campuses",
  start_date: new Date().toISOString().slice(0, 10),
  end_date: new Date().toISOString().slice(0, 10),
  description: "",
  status: "published",
  program_id: "", department_id: "", student_year: "",
  start_time: "", end_time: "",
});

export default function AcademicCalendar({ user, caps }: { user: any; caps: any }) {
  const [term, setTerm] = useState(""),
    [data, setData] = useState<any>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [category, setCategory] = useState("All"),
    [campus, setCampus] = useState("All Campuses"),
    [academicYear, setAcademicYear] = useState(""),
    [programId, setProgramId] = useState(""),
    [departmentId, setDepartmentId] = useState(""),
    [studentYear, setStudentYear] = useState(""),
    [filtersOpen, setFiltersOpen] = useState(false),
    [form, setForm] = useState<any>(blank()),
    [detail, setDetail] = useState<any>(null),
    [modal, setModal] = useState(false),
    [returnDetail, setReturnDetail] = useState<any>(null),
    [returnReason, setReturnReason] = useState(""),
    [returnError, setReturnError] = useState(""),
    [saving, setSaving] = useState(false);
  async function load(value = term) {
    setLoading(true);
    try {
      const response = await api.academicCalendar(value, {
        academicYear,
        programId,
        departmentId,
        studentYear,
      });
      const next = response || { entries: [], proposals: [], summary: {}, term_options: [] };
      setData(next);
      if (!value && next?.selected_term) setTerm(next.selected_term);
    } catch (e: any) {
      setError(e.message || "We could not load the academic calendar.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load(term);
  }, [term, academicYear, programId, departmentId, studentYear]);
  const yearOptions = data?.academic_year_options || [];
  const campuses = useMemo<string[]>(
    () => [
      "All Campuses",
      ...Array.from(
        new Set<string>(
          (data?.entries || [])
            .map((x: any) => String(x.campus))
            .filter(Boolean),
        ),
      ),
    ],
    [data],
  );
  const entries = useMemo(
    () =>
      (data?.entries || []).filter(
        (x: any) =>
          (category === "All" || x.category === category) &&
          (campus === "All Campuses" ||
            x.campus === campus ||
            x.campus === "All Campuses"),
      ),
    [data, category, campus],
  );
  const groups = useMemo(
    () =>
      entries.reduce((o: Record<string, any[]>, x: any) => {
        const k = new Date(`${x.start_date}T00:00:00`).toLocaleString("en-IN", {
          month: "long",
          year: "numeric",
        });
        (o[k] ||= []).push(x);
        return o;
      }, {}),
    [entries],
  );
  const pending = useMemo(() => data?.review_inbox || [], [data]);
  const upcoming = useMemo(
    () =>
      (data?.entries || [])
        .filter((x: any) => new Date(`${x.start_date}T00:00:00`) >= new Date())
        .slice(0, 4),
    [data],
  );
  const canEdit = user?.office_n === 17;
  const canDelete = user?.office_n === 17;
  const showCreate = user?.office_n === 17;
  const examConflicts = useMemo(() => {
    const exams = (data?.entries || []).filter((x: any) =>
      /exam/i.test(x.category),
    );
    const conflicts: any[] = [];
    exams.forEach((a: any, i: number) =>
      exams.slice(i + 1).forEach((b: any) => {
        if (
          a.campus !== b.campus &&
          a.campus !== "All Campuses" &&
          b.campus !== "All Campuses"
        )
          return;
        if (a.start_date <= b.end_date && b.start_date <= a.end_date)
          conflicts.push({ a, b });
      }),
    );
    return conflicts;
  }, [data]);
  const canDecide = !!data?.workflow_permissions?.decide;
  function open(x: any) {
    // Drafts and returned records are editable by their coordinator.  An
    // approved record must open in the governed detail view so the sole
    // permitted next action is publication, not an accidental direct edit.
    if (x.editable && canEdit && ["draft", "Dean Returned", "VP Returned"].includes(x.status)) {
      setForm({
        id: x.id,
        term: x.term,
        title: x.title,
        category: x.category,
        campus: x.campus,
        start_date: x.start_date,
        end_date: x.end_date,
        description: x.description || "",
        status: x.status || "published",
        program_id: x.program_id || "", department_id: x.department_id || "", student_year: x.student_year || "", start_time: x.start_time || "", end_time: x.end_time || "",
      });
      setDetail(null);
    } else setDetail(x);
    setModal(true);
  }
  async function save() {
    const title = String(form.title || "").trim();
    const selectedTerm = String(form.term || "").trim();
    const selectedAcademicYear = String(form.academic_year || "").trim();
    if (!title || !selectedTerm || !selectedAcademicYear) {
      setError("Title, term, and academic year are required before saving an academic event.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        title,
        term: selectedTerm,
        academic_year: selectedAcademicYear,
        student_year: form.student_year === "" || form.student_year == null ? null : Number(form.student_year),
        program_id: form.program_id?.trim() || null,
        department_id: form.department_id?.trim() || null,
      };
      form.id
        ? await api.updateAcademicCalendarEntry(form.id, payload)
        : await api.createAcademicCalendarEntry(payload);
      setModal(false);
      await load();
    } catch (e: any) {
      setError(e.message || "Could not save the event.");
    } finally {
      setSaving(false);
    }
  }
  function exportCsv() {
    const header = [
      "Term",
      "Title",
      "Category",
      "Campus",
      "Start date",
      "End date",
      "Status",
      "Description",
    ];
    const esc = (v: any) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const csv = [
      header,
      ...entries.map((x: any) => [
        x.term,
        x.title,
        x.category,
        x.campus,
        x.start_date,
        x.end_date,
        x.status,
        x.description,
      ]),
    ]
      .map((row) => row.map(esc).join(","))
      .join("\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `academic-calendar-${(data?.selected_term || "term").replace(/[^a-z0-9-]/gi, "_")}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }
  async function remove() {
    setSaving(true);
    try {
      await api.deleteAcademicCalendarEntry(form.id);
      setModal(false);
      await load();
    } catch (e: any) {
      setError(e.message || "Could not delete the event.");
    } finally {
      setSaving(false);
    }
  }
  async function decide(proposal: any, decision: string) {
    setSaving(true);
    try {
      await api.decideAcademicCalendarEntry(proposal.id, { action: decision, reason: decision === "approve" ? "" : "Decision recorded by reviewer", expected_version: proposal.version_no });
      setModal(false);
      setDetail(null);
      await load();
    } catch (e: any) {
      if (e?.status === 409) {
        setModal(false);
        setDetail(null);
        await load();
        setError("This calendar is no longer current. The queue was refreshed; reopen the latest version before deciding.");
      } else setError(e.message || "Could not record decision.");
    } finally {
      setSaving(false);
    }
  }
  async function submitDraft() {
    setSaving(true);
    try { await api.submitAcademicCalendarEntry(form.id); setModal(false); await load(); }
    catch (e: any) { setError(e.message || "Could not submit the draft."); }
    finally { setSaving(false); }
  }
  async function returnForRevision() {
    if (!returnDetail || !returnReason.trim()) {
      setReturnError("Enter a clear reason so the Academic Coordinator can revise the event.");
      return;
    }
    setSaving(true);
    try {
      await api.decideAcademicCalendarEntry(returnDetail.id, { action: "return", reason: returnReason.trim(), expected_version: returnDetail.version_no });
      setReturnDetail(null); setReturnReason(""); setReturnError(""); setModal(false); setDetail(null); await load();
    } catch (e: any) {
      if (e?.status === 409) { setReturnDetail(null); setModal(false); setDetail(null); await load(); setError("This calendar is no longer current. The queue was refreshed; reopen the latest version before deciding."); }
      else setReturnError(e.message || "Could not return the calendar.");
    } finally { setSaving(false); }
  }
  if (loading && !data) return <Spinner />;
  return (
    <div className="fade-in academic-calendar-ref">
      <PageHead
        title="Academic Calendar"
        sub="Institution-wide academic dates, examinations, teaching periods, holidays, and academic milestones."
        right={
          <div className="calendar-head-actions academic-filter-bar">
            {showCreate && <button
              className="btn btn-crimson"
              type="button"
              onClick={() => {
                setError("");
                setDetail(null);
                setForm(blank(data?.selected_term || term, academicYear || data?.academic_year_options?.[0] || ""));
                setModal(true);
              }}
            >
              Add academic event
            </button>}
            <button className="btn btn-out" onClick={() => setFiltersOpen((open) => !open)}>
              {filtersOpen ? "Hide filters" : "Filters"}
            </button>
            {filtersOpen && <>
              <label>
                Term / semester
                <select className="select academic-term-select" value={data?.selected_term || ""} onChange={(e) => setTerm(e.target.value)}>
                  {data?.term_options?.map((x: string) => <option key={x}>{x}</option>)}
                </select>
              </label>
              <label>
                Campus
                <select className="select" value={campus} onChange={(e) => setCampus(e.target.value)}>
                  {campuses.map((x) => <option key={x}>{x}</option>)}
                </select>
              </label>
              <label>Academic year<select className="select" value={academicYear} onChange={e => setAcademicYear(e.target.value)}><option value="">All years</option>{yearOptions.map((x: string) => <option key={x}>{x}</option>)}</select></label>
              <label>Student year<select className="select" value={studentYear} onChange={e => setStudentYear(e.target.value)}><option value="">All years</option>{[1,2,3,4].map(x => <option key={x} value={x}>{x} Year</option>)}</select></label>
            </>}
          </div>
        }
      />
      {user?.office_n === 17 && (
        <div className="calendar-banner">
          Academic Coordinator changes are saved as drafts and require approval before publication.
        </div>
      )}
      {error && <div className="calendar-banner warn">{error}</div>}
      {data && (
        <>
          <div className="academic-kpis">
            <Metric i="▣" n={data?.summary?.milestones ?? 0} t="Academic Events" />
            <Metric i="◷" n={upcoming.length} t="Upcoming Events" />
            <Metric i="▤" n={data?.summary?.exam_windows ?? 0} t="Exam Windows" />
            <Metric i="!" n={pending.length} t="Pending Approval" />
            <Metric i="☂" n={data?.summary?.breaks ?? 0} t="Holidays / Breaks" />
          </div>
          {examConflicts.length > 0 && (
            <div className="calendar-banner warn">
              <strong>Exam scheduling conflict{examConflicts.length > 1 ? "s" : ""} detected.</strong>{" "}
              Review overlapping examination windows before approving or publishing changes.
            </div>
          )}
          <div className="acad-layout">
            <section className="card">
              <div className="academic-tabs">
                <button className="active">Timeline</button>
                <span />
                {[
                  "All",
                  "Teaching",
                  "Examinations",
                  "Registration",
                  "Results",
                  "Break",
                  "Review",
                ].map((x) => (
                  <button
                    className={`academic-category ${category === x ? "selected" : ""}`}
                    onClick={() => setCategory(x)}
                    key={x}
                  >
                    {x === "Break" ? "Holidays" : x}
                  </button>
                ))}
              </div>
              <div className="card-h academic-timeline-head">
                <h3>Term Timeline</h3>
                <span className="hint">{entries.length} events</span>
              </div>
              <div className="acad-timeline">
                {!Object.keys(groups).length && (
                  <Empty
                    icon="Calendar"
                    text="No academic milestones match these filters"
                  />
                )}
                {Object.entries(groups).map(([month, list]) => (
                  <div className="acad-month-group" key={month}>
                    <div className="acad-month-title">{month}</div>
                    {(list as any[]).map((x) => (
                      <button
                        className="acad-entry"
                        onClick={() => open(x)}
                        key={x.id}
                      >
                        <div
                          className={`acad-entry-rail ${tone(x.category)}`}
                        />
                        <div className="acad-entry-date">
                          <b>
                            {new Date(
                              `${x.start_date}T00:00:00`,
                            ).toLocaleDateString("en-IN", {
                              day: "2-digit",
                              month: "short",
                            })}
                          </b>
                          <span>{dates(x.start_date, x.end_date)}</span>
                        </div>
                        <div className="acad-entry-copy">
                          <div className="acad-entry-top">
                            <strong>{x.title}</strong>
                            <Pill s={x.status || "published"} />
                          </div>
                          <div className="acad-entry-meta">
                            {x.category} · {x.campus}
                          </div>
                          <p>{x.description}</p>
                        </div>
                        <span className="acad-edit-tag">
                          {x.editable && canEdit ? "Edit" : "View"}
                        </span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            </section>
            <aside className="acad-side">
              <Side
                title={`Requires Your Attention${pending.length ? ` (${pending.length})` : ""}`}
                rows={pending}
                empty="No approvals are waiting"
                open={open}
                showPill
              />
              <Side
                title="Upcoming Academic Activity"
                rows={upcoming}
                empty="No upcoming activity in this term"
                open={open}
              />
              <section className="card">
                <div className="card-h">
                  <h3>Calendar Governance</h3>
                </div>
                <div className="card-pad academic-governance">
                  <div className="snap">
                    <span>Owner</span>
                    <b>Academic Coordinator</b>
                  </div>
                  <div className="snap">
                    <span>Approval authority</span>
                    <b>Dean Academics</b>
                    <b>Vice Principal when operational review is required</b>
                  </div>
                  <div className="snap">
                    <span>Pending changes</span>
                    <b>{pending.length}</b>
                  </div>
                  <p>
                    Changes follow role permissions and are recorded in the
                    audit trail.
                    The Academic Coordinator drafts and publishes. Dean Academics
                    performs governance review, then the Vice Principal performs
                    operational review when the calendar item requires it.
                  </p>
                </div>
              </section>
            </aside>
          </div>
        </>
      )}
      {modal && !detail && (
        <Modal
          className="academic-calendar-event-modal"
          title={form.id ? "Edit Academic Event" : "Propose Academic Event"}
          onClose={() => setModal(false)}
          footer={
            <>
              {form.id && canDelete && (
                <button
                  className="btn btn-rose"
                  disabled={saving}
                  onClick={remove}
                >
                  Delete
                </button>
              )}
              {form.id && user?.office_n === 17 && ["draft", "Dean Returned", "VP Returned"].includes(form.status) && <button className="btn btn-out" disabled={saving} onClick={submitDraft}>Submit for Dean review</button>}
              <button className="btn btn-out" onClick={() => setModal(false)}>
                Cancel
              </button>
              <button
                className="btn btn-crimson"
                disabled={saving}
                onClick={save}
              >
                {saving ? "Saving..." : "Save event"}
              </button>
            </>
          }
        >
          <Field label="Title">
            <input
              className="inp"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </Field>
          <div className="grid-2">
            <Field label="Term">
              <input
                className="inp"
                value={form.term}
                onChange={(e) => setForm({ ...form, term: e.target.value })}
              />
            </Field>
            <Field label="Academic year">
              <input
                className="inp"
                placeholder="e.g. 2026-27"
                value={form.academic_year || ""}
                onChange={(e) => setForm({ ...form, academic_year: e.target.value })}
              />
            </Field>
          </div>
          <div className="grid-2">
            <Field label="Category">
              <select
                className="select"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                {CATEGORIES.map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </Field>
          </div>
          <div className="grid-2">
            <Field label="Student year"><select className="select" value={form.student_year || ""} onChange={e => setForm({ ...form, student_year: e.target.value ? Number(e.target.value) : null })}><option value="">All years</option>{[1,2,3,4].map(x => <option key={x} value={x}>{x} Year</option>)}</select></Field>
          </div>
          <div className="grid-2">
            <Field label="Program / branch ID"><input className="inp" value={form.program_id} onChange={e => setForm({ ...form, program_id: e.target.value })} /></Field>
            <Field label="Department ID"><input className="inp" value={form.department_id} onChange={e => setForm({ ...form, department_id: e.target.value })} /></Field>
          </div>
          <div className="grid-2">
            <Field label="Start time"><input className="inp" type="time" value={form.start_time} onChange={e => setForm({ ...form, start_time: e.target.value })} /></Field>
            <Field label="End time"><input className="inp" type="time" value={form.end_time} onChange={e => setForm({ ...form, end_time: e.target.value })} /></Field>
          </div>
          <div className="grid-2">
            <Field label="Start date">
              <input
                className="inp"
                type="date"
                value={form.start_date}
                onChange={(e) =>
                  setForm({ ...form, start_date: e.target.value })
                }
              />
            </Field>
            <Field label="End date">
              <input
                className="inp"
                type="date"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              />
            </Field>
          </div>
          <Field label="Campus / scope">
            <input
              className="inp"
              value={form.campus}
              onChange={(e) => setForm({ ...form, campus: e.target.value })}
            />
          </Field>
          <Field label="Description">
            <textarea
              className="inp"
              rows={4}
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
            />
          </Field>
        </Modal>
      )}
      {modal && detail && (
        <Modal
          title="Academic Event Details"
          onClose={() => {
            setModal(false);
            setDetail(null);
          }}
          footer={<>{detail.status === "Dean Review" && user?.office_n === 6 && <><button className="btn btn-out" disabled={saving} onClick={() => { setReturnDetail(detail); setReturnReason(""); setReturnError(""); }}>Return</button><button className="btn btn-crimson" disabled={saving} onClick={() => decide(detail, "approve")}>Approve</button></>}{detail.status === "VP Review" && user?.office_n === 5 && <><button className="btn btn-out" disabled={saving} onClick={() => { setReturnDetail(detail); setReturnReason(""); setReturnError(""); }}>Return</button><button className="btn btn-crimson" disabled={saving} onClick={() => decide(detail, "approve")}>Operationally approve</button></>}{detail.status === "Approved" && user?.office_n === 17 && <button className="btn btn-crimson" disabled={saving} onClick={async () => { setSaving(true); try { await api.publishAcademicCalendarEntry(detail.id); setModal(false); setDetail(null); await load(); } catch (e: any) { setError(e.message || "Could not publish the calendar."); } finally { setSaving(false); } }}>Publish calendar</button>}</>}
        >
          <div className="calendar-detail">
            <Pill s={detail.status || "published"} />
            <h3>{detail.title}</h3>
            <p>{detail.description || "No additional notes were provided."}</p>
            <div className="snap">
              <span>Date range</span>
              <b>{dates(detail.start_date, detail.end_date)}</b>
            </div>
            <div className="snap">
              <span>Campus</span>
              <b>{detail.campus}</b>
            </div>
            <div className="snap"><span>Academic year / term</span><b>{detail.academic_year || "All years"} · {detail.term}</b></div>
            <div className="snap"><span>Target</span><b>{detail.program_id || "All programs"} · {detail.department_id || "All departments"} · {detail.student_year ? `${detail.student_year} Year` : "All student years"}</b></div>
            <div className="snap"><span>Time</span><b>{detail.start_time || "Not specified"}{detail.end_time ? ` – ${detail.end_time}` : ""}</b></div>
          </div>
        </Modal>
      )}
      {returnDetail && (
        <Modal
          className="academic-calendar-return-modal"
          title="Return academic event for revision"
          onClose={() => { if (!saving) { setReturnDetail(null); setReturnReason(""); setReturnError(""); } }}
          footer={<><button className="btn btn-out" disabled={saving} onClick={() => { setReturnDetail(null); setReturnReason(""); setReturnError(""); }}>Cancel</button><button className="btn btn-crimson" disabled={saving || !returnReason.trim()} onClick={returnForRevision}>{saving ? "Returning…" : "Return for revision"}</button></>}
        >
          <div className="calendar-return-dialog">
            <Pill s={returnDetail.status} />
            <h4>{returnDetail.title}</h4>
            <p>Explain what must be corrected. Your note is recorded in the workflow audit trail and sent to the Academic Coordinator.</p>
            <Field label="Return reason"><textarea className="inp" rows={4} autoFocus value={returnReason} placeholder="Example: Confirm that the examination preparation dates do not overlap with the teaching period." onChange={e => { setReturnReason(e.target.value); setReturnError(""); }} /></Field>
            {returnError && <div className="calendar-banner warn">{returnError}</div>}
          </div>
        </Modal>
      )}
    </div>
  );
}
function Metric({ i, n, t }: any) {
  return (
    <div className="academic-kpi">
      <i>{i}</i>
      <div>
        <b>{n}</b>
        <span>{t}</span>
      </div>
    </div>
  );
}
function Side({ title, rows, empty, open, showPill }: any) {
  return (
    <section className="card">
      <div className="card-h">
        <h3>{title}</h3>
      </div>
      <div className="card-pad">
        {rows.length ? (
          rows.map((x: any) => (
            <button
              className="academic-side-item"
              onClick={() => open(x)}
              key={x.id}
            >
              <strong>{x.title}</strong>
              <span>
                {dates(x.start_date, x.end_date)} · {x.category}
              </span>
              {showPill && <Pill s={x.status} />}
            </button>
          ))
        ) : (
          <Empty icon="✓" text={empty} />
        )}
      </div>
    </section>
  );
}
function Field({ label, children }: any) {
  return (
    <div className="form-row">
      <label>{label}</label>
      {children}
    </div>
  );
}
function dates(s: string, e: string) {
  const a = new Date(`${s}T00:00:00`),
    b = new Date(`${e}T00:00:00`);
  return s === e
    ? a.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : `${a.toLocaleDateString("en-IN", { day: "2-digit", month: "short" })} – ${b.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}`;
}
function tone(c: string) {
  c = c.toLowerCase();
  return c.includes("exam") || c.includes("assessment")
    ? "linked"
    : c.includes("break") || c.includes("result")
      ? "manual"
      : "academic";
}
