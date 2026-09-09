import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, Modal, PageHead, Pill, Spinner } from "./kit";

const YEARS = [1, 2, 3, 4];
const STATUS_OPTIONS = [
  "Not Started",
  "In Progress",
  "On Track",
  "Delayed",
  "Completed",
  "Gap / Issue",
];

const yearLabel = (year: number) =>
  `${year}${year === 1 ? "st" : year === 2 ? "nd" : year === 3 ? "rd" : "th"} Year`;

export default function AcademicCoordinatorCurriculumExecution({ onNavigate }: { onNavigate?: (view: string) => void }) {
  const [items, setItems] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<any>(null);
  const [issue, setIssue] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [edit, setEdit] = useState<any>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<any>({});
  const [canManage, setCanManage] = useState(false);

  const load = () => {
    setError("");
    api
      .curriculumExecution(filters)
      .then((r: any) => {
        setItems(r.items || []);
        setCanManage(Boolean(r.can_manage));
      })
      .catch((e: any) =>
        setError(e.message || "Unable to load curriculum execution"),
      );
  };

  useEffect(load, [
    filters.academic_year,
    filters.student_year,
    filters.program_id,
    filters.department_id,
    filters.term,
    filters.execution_status,
  ]);

  if (!items) {
    return error ? (
      <div className="calendar-banner warn">{error}</div>
    ) : (
      <Spinner />
    );
  }

  const openIssues = items.reduce(
    (n, x) =>
      n +
      (x.execution_issues || []).filter((i: any) => i.status !== "Resolved")
        .length,
    0,
  );

  const activeYear = String(filters.student_year || "");
  const hasFilters = Boolean(
    filters.academic_year ||
      filters.program_id ||
      filters.term ||
      filters.execution_status,
  );

  const clearFilters = () => {
    setFilters({});
  };

  const setYear = (year?: number) => {
    setFilters({
      ...filters,
      student_year: year ? String(year) : "",
    });
  };

  return (
    <div className="fade-in curriculum-page">
      <style>{styles}</style>

      <PageHead
        title="Curriculum Execution"
        sub="Track approved curriculum delivery across offerings, sections, faculty and timetable readiness."
        right={
          <div className="curriculum-head-actions">
            <button className="btn btn-crimson" onClick={() => onNavigate?.("coordinator_course_offerings")}>
              Create Curriculum
            </button>
            <button className="btn btn-out curriculum-refresh" onClick={load}>
              Refresh
            </button>
          </div>
        }
      />

      <div className="curriculum-space" />

      {message && (
        <div className="calendar-banner success curriculum-banner">
          {message}
        </div>
      )}
      {error && (
        <div className="calendar-banner warn curriculum-banner">{error}</div>
      )}

      {/* Year navigation — intentionally not inside a card */}
      <nav className="curriculum-years" aria-label="Student year">
        <button
          className={`curriculum-year ${!activeYear ? "active" : ""}`}
          onClick={() => setYear()}
        >
          All Years
        </button>
        {YEARS.map((year) => (
          <button
            key={year}
            className={`curriculum-year ${activeYear === String(year) ? "active" : ""}`}
            onClick={() => setYear(year)}
          >
            {yearLabel(year)}
          </button>
        ))}
      </nav>

      {/* Filter toolbar — no enclosing card */}
      <section className="curriculum-filter-area">
        <div className="curriculum-filter-heading">
          <div>
            <h3>Filters</h3>
            <span>Refine the courses you want to monitor.</span>
          </div>
          <div className="curriculum-filter-actions">
            {hasFilters && <button className="curriculum-clear" onClick={clearFilters}>Clear filters</button>}
            <button className="curriculum-clear" onClick={() => setFiltersOpen((open) => !open)}>{filtersOpen ? "Hide filters" : "Filters"}</button>
          </div>
        </div>

        {filtersOpen && <div className="curriculum-filters">
          <FilterField label="Academic Year">
            <select
              className="select curriculum-control"
              value={filters.academic_year || ""}
              onChange={(e) =>
                setFilters({ ...filters, academic_year: e.target.value })
              }
            >
              <option value="">All academic years</option>
              {Array.from(
                new Set(items.map((x) => x.academic_year).filter(Boolean)),
              ).map((v: any) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </FilterField>

          <FilterField label="Program">
            <select
              className="select curriculum-control"
              value={filters.program_id || ""}
              onChange={(e) =>
                setFilters({ ...filters, program_id: e.target.value })
              }
            >
              <option value="">All programs</option>
              {Array.from(
                new Map(
                  items
                    .filter((x) => x.program_id)
                    .map((x) => [
                      String(x.program_id),
                      x.program_code || x.program || "Unknown Program",
                    ]),
                ).entries(),
              ).map(([id, label]) => (
                <option key={id} value={id}>
                  {String(label)}
                </option>
              ))}
            </select>
          </FilterField>

          <FilterField label="Term">
            <select
              className="select curriculum-control"
              value={filters.term || ""}
              onChange={(e) => setFilters({ ...filters, term: e.target.value })}
            >
              <option value="">All terms</option>
              {Array.from(
                new Set(items.map((x) => x.term).filter(Boolean)),
              ).map((v: any) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </FilterField>

          <FilterField label="Execution Status">
            <select
              className="select curriculum-control"
              value={filters.execution_status || ""}
              onChange={(e) =>
                setFilters({ ...filters, execution_status: e.target.value })
              }
            >
              <option value="">All statuses</option>
              {STATUS_OPTIONS.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </FilterField>
        </div>}
      </section>

      {/* KPI summary */}
      <section className="curriculum-kpis">
        <K label="Total Courses" v={items.length} />
        <K
          label="In Progress"
          v={items.filter((x) => x.execution_status === "In Progress").length}
        />
        <K
          label="Completed"
          v={items.filter((x) => x.execution_status === "Completed").length}
        />
        <K label="Open Issues" v={openIssues} />
      </section>

      {/* Main execution list */}
      <section className="curriculum-list-section">
        <div className="curriculum-section-head">
          <div>
            <div className="curriculum-eyebrow">ACADEMIC OPERATIONS</div>
            <h2>Course Execution</h2>
            <p>Monitor completion targets, actual progress and execution issues.</p>
          </div>
          <div className="curriculum-result-count">
            <strong>{items.length}</strong>
            <span>{items.length === 1 ? "course" : "courses"}</span>
          </div>
        </div>

        <div className="curriculum-table-wrap">
          <table className="tbl curriculum-table curriculum-shared-table">
            <thead>
              <tr>
                <th>Course</th>
                <th>Program</th>
                <th>Academic Year</th>
                <th>Semester / Term</th>
                <th>HOD Input</th>
                <th>Faculty</th>
                <th>Execution</th>
                <th aria-label="Action" />
              </tr>
            </thead>
            <tbody>
              {items.map((x) => {
                const hod = x.hod_input;

                return (
                  <tr key={x.id}>
                    <td className="curriculum-course-cell">
                      <strong>{x.course_code || "—"}</strong>
                      <span>{x.course_title || "Course title unavailable"}</span>
                    </td>
                    <td><strong>{x.program_code || x.program || "—"}</strong></td>
                    <td>{x.academic_year || "—"}</td>
                    <td>
                      <strong>{x.semester || "—"}</strong>
                      <span className="curriculum-muted">{x.term || "Term unavailable"}</span>
                    </td>
                    <td><Pill s={hod?.status || "Pending"} /></td>
                    <td>{x.faculty || "No faculty assigned"}</td>
                    <td className="curriculum-execution-cell">
                      <strong>
                        L {x.lab_marks ?? "—"} · M {x.mid_marks ?? "—"} · S {x.semester_marks ?? "—"}
                      </strong>
                      <span>Mid-1 complete: {x.mid1_completion_percentage ?? "—"}%</span>
                      <span>Mid-2 remaining: {x.mid2_remaining_syllabus_percentage ?? "—"}%</span>
                      <span>{x.execution_status || "Not Started"}</span>
                      {x.execution_remarks && <span>{x.execution_remarks}</span>}
                    </td>
                    <td className="curriculum-action-cell">
                      <button
                        className="linkish curriculum-details-btn"
                        onClick={() => setSelected(x)}
                      >
                        View details
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {!items.length && (
          <div className="curriculum-empty">
            <div className="curriculum-empty-mark">—</div>
            <h3>No course offerings found</h3>
            <p>Try changing the year or filters to view other courses.</p>
          </div>
        )}
      </section>

      {selected && (
        <Modal
          title={`${selected.course_code} · Execution details`}
          className="curriculum-details-modal"
          onClose={() => setSelected(null)}
        >
          <div className="curriculum-modal-intro">
            <div>
              <span className="curriculum-modal-code">{selected.course_code}</span>
              <h3>{selected.course_title || "Course"}</h3>
              <p>
                {selected.program || selected.program_code || "—"} · {selected.student_year ? `${selected.student_year} Year` : "Year not set"}
              </p>
            </div>
            <Pill s={selected.execution_status} />
          </div>

          <DetailSection title="Course Overview">
            <Info l="Program" v={selected.program} />
            <Info l="Department" v={selected.department} />
            <Info l="Student year" v={selected.student_year ? `${selected.student_year} Year` : "—"} />
            <Info l="Course code" v={selected.course_code} />
            <Info l="Faculty" v={selected.faculty} />
            <Info
              l="Academic period"
              v={`${selected.academic_year || "—"} · ${selected.term || "—"} · Semester ${selected.semester || "—"}`}
            />
          </DetailSection>

          <DetailSection title="Academic Readiness">
            <Info l="Curriculum status" v={selected.curriculum_status} />
            <Info l="Offering status" v={selected.status} />
            <Info
              l="Section readiness"
              v={`${selected.section_readiness?.created_sections || 0} / ${selected.section_readiness?.required_sections || 0}`}
            />
            <Info l="Faculty allocation" v={selected.faculty_readiness} />
            <Info l="Timetable readiness" v={selected.timetable_readiness} />
          </DetailSection>

          <DetailSection title="Execution">
            <Info l="Execution status" v={selected.execution_status} />
            <Info l="Progress" v={`${selected.progress || 0}%`} />
            <Info l="Lab marks" v={selected.lab_marks} />
            <Info l="Mid marks" v={selected.mid_marks} />
            <Info l="Semester marks" v={selected.semester_marks} />
            <Info l="Mid-1 course completion" v={selected.mid1_completion_percentage == null ? "—" : `${selected.mid1_completion_percentage}%`} />
            <Info l="Mid-2 remaining syllabus" v={selected.mid2_remaining_syllabus_percentage == null ? "—" : `${selected.mid2_remaining_syllabus_percentage}%`} />
            <Info l="Remarks" v={selected.execution_remarks} />
          </DetailSection>

          {canManage && (
            <div className="curriculum-modal-actions">
              <button className="btn btn-out" onClick={() => setEdit(selected)}>
                Edit execution
              </button>
            </div>
          )}

          <section className="curriculum-issues-section">
            <div className="curriculum-issues-head">
              <div>
                <h3>Execution Issues</h3>
                <p>Problems affecting delivery of this course.</p>
              </div>
              <button
                className="btn btn-out"
                onClick={() => setIssue(selected)}
              >
                Record issue
              </button>
            </div>

            <div className="curriculum-issue-list">
              {(selected.execution_issues || []).map((i: any) => (
                <div className="curriculum-issue-item" key={i.id}>
                  <div>
                    <strong>{i.issue_type || "Execution issue"}</strong>
                    <span>{i.responsible_role || "—"}</span>
                  </div>
                  <div>
                    <b>{i.status || "Open"}</b>
                    <p>{i.description || "No description"}</p>
                  </div>
                </div>
              ))}
            </div>

            {!selected.execution_issues?.length && (
              <Empty text="No execution issues recorded." />
            )}
          </section>
        </Modal>
      )}

      {issue && (
        <IssueModal
          offering={issue}
          onClose={() => setIssue(null)}
          onSaved={(m) => {
            setIssue(null);
            setSelected(null);
            setMessage(m);
            load();
          }}
        />
      )}

      {edit && (
        <ExecutionEdit
          offering={edit}
          onClose={() => setEdit(null)}
          onSaved={() => {
            setEdit(null);
            setSelected(null);
            setMessage("Execution updated.");
            load();
          }}
        />
      )}

    </div>
  );
}

function FilterField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="curriculum-filter-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function DetailSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="curriculum-detail-section">
      <div className="curriculum-detail-heading">
        <h3>{title}</h3>
      </div>
      <div className="curriculum-detail-grid">{children}</div>
    </section>
  );
}

function ExecutionEdit({
  offering,
  onClose,
  onSaved,
}: {
  offering: any;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    execution_remarks: offering.execution_remarks || "",
    lab_marks: offering.lab_marks ?? null,
    mid_marks: offering.mid_marks ?? null,
    semester_marks: offering.semester_marks ?? null,
    mid1_completion_percentage: offering.mid1_completion_percentage ?? null,
    mid2_remaining_syllabus_percentage: offering.mid2_remaining_syllabus_percentage ?? null,
  });
  const [error, setError] = useState("");

  return (
    <Modal
      title={`${offering.course_code} · Edit execution`}
      onClose={onClose}
      footer={
        <div className="curriculum-modal-footer">
          <button className="btn btn-out" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-crimson"
            onClick={async () => {
              try {
                await api.updateCurriculumExecution(offering.id, f);
                onSaved();
              } catch (e: any) {
                setError(e.message || "Unable to save execution");
              }
            }}
          >
            Save
          </button>
        </div>
      }
    >
      <div className="curriculum-edit-progress">
        <div>
          <span>Calculated progress</span>
          <strong>{offering.progress || 0}%</strong>
        </div>
        <div className="curriculum-progress-track">
          <span style={{ width: `${Math.max(0, Math.min(100, Number(offering.progress || 0)))}%` }} />
        </div>
      </div>

      <div className="curriculum-edit-grid">
        <div className="form-row">
          <label>Lab marks</label>
          <input
            className="inp"
            type="number"
            min="0"
            value={f.lab_marks ?? ""}
            onChange={(e) => setF({ ...f, lab_marks: e.target.value ? Number(e.target.value) : null })}
          />
        </div>

        <div className="form-row">
          <label>Mid marks</label>
          <input
            className="inp"
            type="number"
            min="0"
            value={f.mid_marks ?? ""}
            onChange={(e) => setF({ ...f, mid_marks: e.target.value ? Number(e.target.value) : null })}
          />
        </div>

        <div className="form-row">
          <label>Semester marks</label>
          <input
            className="inp"
            type="number"
            min="0"
            value={f.semester_marks ?? ""}
            onChange={(e) => setF({ ...f, semester_marks: e.target.value ? Number(e.target.value) : null })}
          />
        </div>

        <div className="form-row">
          <label>Mid-1 course completion (%)</label>
          <input
            className="inp"
            type="number"
            min="0"
            max="100"
            value={f.mid1_completion_percentage ?? ""}
            onChange={(e) => setF({ ...f, mid1_completion_percentage: e.target.value ? Number(e.target.value) : null })}
          />
          <small>Enter 40 or 50 when that percentage of the course is complete by Mid-1.</small>
        </div>

        <div className="form-row">
          <label>Mid-2 remaining syllabus (%)</label>
          <input
            className="inp"
            type="number"
            min="0"
            max="100"
            value={f.mid2_remaining_syllabus_percentage ?? ""}
            onChange={(e) => setF({ ...f, mid2_remaining_syllabus_percentage: e.target.value ? Number(e.target.value) : null })}
          />
          <small>Enter the percentage of syllabus remaining after Mid-2.</small>
        </div>

        <div className="form-row curriculum-edit-full">
          <label>Remarks</label>
          <textarea
            className="inp curriculum-remarks"
            value={f.execution_remarks}
            onChange={(e) =>
              setF({ ...f, execution_remarks: e.target.value })
            }
          />
        </div>
      </div>

      {offering.execution_status !== "Completed" && (
        <div className="curriculum-complete-action">
          <button
            className="btn btn-crimson"
            onClick={async () => {
              try {
                await api.updateCurriculumExecution(offering.id, {
                  ...f,
                  execution_status: "Completed",
                });
                onSaved();
              } catch (e: any) {
                setError(e.message || "Unable to complete execution");
              }
            }}
          >
            Mark Completed
          </button>
        </div>
      )}

      {error && <div className="calendar-banner warn">{error}</div>}
    </Modal>
  );
}

function K({ label, v }: { label: string; v: number }) {
  return (
    <div className="curriculum-kpi">
      <div className="curriculum-kpi-number">{v}</div>
      <div className="curriculum-kpi-label">{label}</div>
    </div>
  );
}

function Info({ l, v }: { l: string; v: any }) {
  return (
    <div className="curriculum-info">
      <span>{l}</span>
      <strong>{String(v || "—")}</strong>
    </div>
  );
}

function IssueModal({
  offering,
  onClose,
  onSaved,
}: {
  offering: any;
  onClose: () => void;
  onSaved: (m: string) => void;
}) {
  const [f, setF] = useState({
    offering_id: offering.id,
    issue_type: "",
    description: "",
    responsible_role: "Curriculum Officer",
    status: "Open",
  });
  const [error, setError] = useState("");

  return (
    <Modal
      title="Record execution issue"
      onClose={onClose}
      footer={
        <div className="curriculum-modal-footer">
          <button className="btn btn-out" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-crimson"
            onClick={async () => {
              try {
                if (!f.issue_type.trim()) throw Error("Issue type is required");
                await api.curriculumExecutionIssue(f);
                onSaved("Execution issue recorded.");
              } catch (e: any) {
                setError(e.message || "Unable to save issue");
              }
            }}
          >
            Save issue
          </button>
        </div>
      }
    >
      <div className="curriculum-edit-grid">
        <div className="form-row">
          <label>Issue type</label>
          <input
            className="inp"
            value={f.issue_type}
            onChange={(e) => setF({ ...f, issue_type: e.target.value })}
            placeholder="e.g. Faculty unavailable"
          />
        </div>

        <div className="form-row">
          <label>Responsible role</label>
          <select
            className="select"
            value={f.responsible_role}
            onChange={(e) =>
              setF({ ...f, responsible_role: e.target.value })
            }
          >
            <option>Curriculum Officer</option>
            <option>HOD</option>
            <option>Dean Academics</option>
          </select>
        </div>

        <div className="form-row curriculum-edit-full">
          <label>Description</label>
          <textarea
            className="inp curriculum-remarks"
            value={f.description}
            onChange={(e) => setF({ ...f, description: e.target.value })}
            placeholder="Describe the issue and its impact on course execution"
          />
        </div>
      </div>

      {error && <div className="calendar-banner warn">{error}</div>}
    </Modal>
  );
}

const styles = `
.curriculum-page {
  width: 100%;
  max-width: 100%;
  color: #241f20;
}
.curriculum-space { height: 22px; }
.curriculum-banner { margin: 0 0 18px; }
.curriculum-refresh { min-width: 88px; }
.curriculum-head-actions { display: flex; align-items: center; gap: 10px; }
.curriculum-create-modal { max-height: 92vh; display: flex; flex-direction: column; }
.curriculum-create-modal .modal-h, .curriculum-create-modal .modal-f { flex: 0 0 auto; }
.curriculum-create-modal .modal-b { min-height: 0; overflow-y: auto; }
.curriculum-details-modal { max-height: 92vh; display: flex; flex-direction: column; }
.curriculum-details-modal .modal-h, .curriculum-details-modal .modal-f { flex: 0 0 auto; }
.curriculum-details-modal .modal-b { min-height: 0; overflow-y: auto; }
.curriculum-create-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 18px; }
.curriculum-create-full { grid-column: 1 / -1; }

.curriculum-years {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 52px;
  border-bottom: 1px solid #e8e2e3;
  overflow-x: auto;
  scrollbar-width: thin;
  margin-bottom: 24px;
}
.curriculum-year {
  appearance: none;
  border: 0;
  background: transparent;
  color: #756d70;
  font: inherit;
  font-weight: 600;
  white-space: nowrap;
  padding: 13px 17px 15px;
  cursor: pointer;
  position: relative;
  transition: color .18s ease, background .18s ease;
  border-radius: 8px 8px 0 0;
}
.curriculum-year:hover { color: #7e1830; background: #faf5f6; }
.curriculum-year.active { color: #7e1830; }
.curriculum-year.active::after {
  content: "";
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: -1px;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: #7e1830;
}

.curriculum-filter-area { margin-bottom: 26px; }
.curriculum-filter-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 14px;
}
.curriculum-filter-heading h3,
.curriculum-section-head h2,
.curriculum-issues-head h3 { margin: 0; }
.curriculum-filter-heading h3 { font-size: 15px; }
.curriculum-filter-heading span,
.curriculum-section-head p,
.curriculum-issues-head p {
  color: #80777a;
  font-size: 13px;
  margin: 4px 0 0;
}
.curriculum-clear {
  border: 0;
  background: transparent;
  color: #7e1830;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  padding: 4px 0;
}
.curriculum-filters {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 14px;
}
.curriculum-filter-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}
.curriculum-filter-field > span {
  font-size: 11px;
  line-height: 1;
  color: #70686b;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
}
.curriculum-control {
  width: 100%;
  min-height: 42px;
  box-sizing: border-box;
}

.curriculum-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 30px;
}
.curriculum-kpi {
  min-height: 86px;
  box-sizing: border-box;
  padding: 17px 19px;
  background: #fff;
  border: 1px solid #e9e3e4;
  border-radius: 10px;
}
.curriculum-kpi-number { font-size: 25px; line-height: 1; font-weight: 800; color: #2d2729; }
.curriculum-kpi-label { margin-top: 8px; color: #81787b; font-size: 12px; font-weight: 600; }

.curriculum-list-section {
  background: #fff;
  border: 1px solid #e8e2e3;
  border-radius: 12px;
  overflow: hidden;
}
.curriculum-section-head {
  min-height: 94px;
  box-sizing: border-box;
  padding: 22px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid #eee9ea;
}
.curriculum-eyebrow {
  color: #8b6a72;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .1em;
  margin-bottom: 6px;
}
.curriculum-section-head h2 { font-size: 18px; }
.curriculum-result-count { text-align: right; white-space: nowrap; }
.curriculum-result-count strong { font-size: 19px; display: block; }
.curriculum-result-count span { color: #8b8285; font-size: 12px; }

.curriculum-table-wrap { width: 100%; overflow-x: auto; }
.curriculum-table { width: 100%; min-width: 1120px; border-collapse: collapse; }
.curriculum-table th {
  padding: 12px 18px;
  background: #fbf9f9;
  color: #81777a;
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .05em;
  white-space: nowrap;
  text-align: left;
  border-bottom: 1px solid #e9e4e5;
}
.curriculum-table td {
  padding: 17px 18px;
  vertical-align: middle;
  border-bottom: 1px solid #eee9ea;
  font-size: 13px;
  color: #3b3537;
}
.curriculum-table tbody tr:last-child td { border-bottom: 0; }
.curriculum-table tbody tr:hover { background: #fdfafb; }
.curriculum-course-cell,
.curriculum-period-cell { min-width: 150px; }
.curriculum-course-cell strong,
.curriculum-period-cell strong { display: block; color: #2c2527; font-size: 13px; }
.curriculum-course-cell span,
.curriculum-period-cell span {
  display: block;
  margin-top: 4px;
  color: #8a8184;
  font-size: 11px;
  line-height: 1.4;
}
.curriculum-date.strong { font-weight: 700; color: #332c2e; white-space: nowrap; }
.curriculum-muted { color: #a39a9d; }
.curriculum-progress-cell { min-width: 105px; }
.curriculum-execution-cell {
  min-width: 155px;
  color: #80777a;
  font-size: 11px;
  line-height: 1.45;
}
.curriculum-execution-cell strong {
  display: block;
  color: #2d2729;
  font-size: 12px;
}
.curriculum-execution-cell span {
  display: block;
}
.curriculum-progress-meta { margin-bottom: 7px; }
.curriculum-progress-meta strong { font-size: 12px; }
.curriculum-progress-track {
  width: 100%;
  height: 6px;
  background: #eee7e9;
  border-radius: 999px;
  overflow: hidden;
}
.curriculum-progress-track > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #7e1830;
  transition: width .25s ease;
}
.curriculum-issue-count,
.curriculum-zero {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 25px;
  height: 25px;
  padding: 0 7px;
  box-sizing: border-box;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
}
.curriculum-issue-count { color: #8a2338; background: #f8e9ed; }
.curriculum-zero { color: #8b8285; background: #f4f1f2; }
.curriculum-action-cell { text-align: right; white-space: nowrap; }
.curriculum-details-btn { font-weight: 700; font-size: 12px; }

.curriculum-empty {
  text-align: center;
  padding: 56px 20px 62px;
  border-top: 0;
}
.curriculum-empty-mark {
  width: 42px;
  height: 42px;
  margin: 0 auto 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #f6f1f2;
  color: #8b6a72;
  font-weight: 800;
}
.curriculum-empty h3 { margin: 0; font-size: 15px; }
.curriculum-empty p { margin: 7px 0 0; color: #8b8285; font-size: 13px; }

.curriculum-modal-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 0 0 22px;
  margin-bottom: 6px;
  border-bottom: 1px solid #eee9ea;
}
.curriculum-modal-code { color: #7e1830; font-size: 11px; font-weight: 800; letter-spacing: .06em; }
.curriculum-modal-intro h3 { margin: 5px 0 4px; font-size: 18px; }
.curriculum-modal-intro p { margin: 0; color: #81787b; font-size: 12px; }
.curriculum-detail-section { padding: 21px 0; border-bottom: 1px solid #eee9ea; }
.curriculum-detail-heading { margin-bottom: 13px; }
.curriculum-detail-heading h3 { margin: 0; font-size: 13px; color: #40383b; }
.curriculum-detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 12px; }
.curriculum-info {
  padding: 11px 13px;
  background: #faf8f8;
  border: 1px solid #eee9ea;
  border-radius: 8px;
  min-width: 0;
}
.curriculum-info span { display: block; color: #898083; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
.curriculum-info strong { display: block; margin-top: 5px; color: #332c2e; font-size: 12px; line-height: 1.4; overflow-wrap: anywhere; }
.curriculum-modal-actions { padding: 18px 0 3px; }
.curriculum-issues-section { padding-top: 22px; }
.curriculum-issues-head { display: flex; align-items: center; justify-content: space-between; gap: 15px; margin-bottom: 15px; }
.curriculum-issues-head h3 { font-size: 14px; }
.curriculum-issue-list { display: grid; gap: 9px; }
.curriculum-issue-item {
  display: grid;
  grid-template-columns: minmax(130px, .65fr) minmax(0, 1.35fr);
  gap: 18px;
  padding: 13px 14px;
  border: 1px solid #eee9ea;
  border-radius: 8px;
  background: #fff;
}
.curriculum-issue-item strong,
.curriculum-issue-item span,
.curriculum-issue-item b,
.curriculum-issue-item p { display: block; }
.curriculum-issue-item strong { font-size: 12px; }
.curriculum-issue-item span { margin-top: 4px; color: #8a8184; font-size: 11px; }
.curriculum-issue-item b { font-size: 11px; color: #7e1830; }
.curriculum-issue-item p { margin: 4px 0 0; color: #71686b; font-size: 12px; line-height: 1.5; }

.curriculum-edit-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 17px 16px; }
.curriculum-edit-full { grid-column: 1 / -1; }
.curriculum-edit-grid .form-row { margin: 0; }
.curriculum-edit-grid .form-row label { display: block; margin-bottom: 7px; font-size: 12px; font-weight: 700; color: #51494c; }
.curriculum-edit-grid .form-row small { display: block; margin-top: 6px; color: #8b8285; font-size: 10px; line-height: 1.4; }
.curriculum-remarks { min-height: 105px; resize: vertical; }
.curriculum-edit-progress {
  padding: 14px 15px;
  margin-bottom: 21px;
  background: #faf7f8;
  border: 1px solid #eee6e8;
  border-radius: 9px;
}
.curriculum-edit-progress > div:first-child { display: flex; align-items: center; justify-content: space-between; margin-bottom: 9px; }
.curriculum-edit-progress span { color: #81777a; font-size: 11px; font-weight: 700; }
.curriculum-edit-progress strong { color: #7e1830; font-size: 15px; }
.curriculum-complete-action { margin-top: 20px; }
.curriculum-modal-footer { display: flex; justify-content: flex-end; gap: 9px; }

@media (max-width: 1000px) {
  .curriculum-filters { grid-template-columns: repeat(2, minmax(150px, 1fr)); }
  .curriculum-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 650px) {
  .curriculum-space { height: 16px; }
  .curriculum-years { margin-bottom: 20px; }
  .curriculum-year { padding-left: 13px; padding-right: 13px; }
  .curriculum-filter-heading { align-items: flex-start; }
  .curriculum-filters { grid-template-columns: 1fr; gap: 12px; }
  .curriculum-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 22px; }
  .curriculum-kpi { min-height: 78px; padding: 14px; }
  .curriculum-kpi-number { font-size: 22px; }
  .curriculum-section-head { padding: 18px 16px; }
  .curriculum-detail-grid { grid-template-columns: 1fr; }
  .curriculum-issue-item { grid-template-columns: 1fr; gap: 9px; }
  .curriculum-edit-grid { grid-template-columns: 1fr; }
  .curriculum-edit-full { grid-column: auto; }
  .curriculum-modal-intro { flex-direction: column; }
}
`;
