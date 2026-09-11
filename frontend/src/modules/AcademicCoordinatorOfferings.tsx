import { useEffect, useMemo, useState } from "react";
import { FiEdit2, FiEye } from "react-icons/fi";
import { api } from "../api";
import { Empty, Modal, PageHead, Pill, Spinner } from "./kit";

export default function AcademicCoordinatorOfferings() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [selected, setSelected] = useState<any>(null);
  const [error, setError] = useState("");
  const [year, setYear] = useState(0);
  const [academicYear, setAcademicYear] = useState("");
  const [program, setProgram] = useState("");
  const [term, setTerm] = useState("");
  const [faculty, setFaculty] = useState("");
  const [status, setStatus] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [createData, setCreateData] = useState<any>({ courses: [], programs: [], faculty: [] });
  const [createForm, setCreateForm] = useState<any>({
    academic_year: "",
    semester: "",
    department: "",
    program_id: "",
    course_id: "",
    term: "",
    faculty_id: "",
    course_start_date: "",
    expected_completion_date: "",
  });
  const [creating, setCreating] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);

  const load = async () => {
    try {
      setError("");
      const r = await api.courseOfferings();
      setRows(r.offerings || []);
    } catch (e: any) {
      setError(e.message || "Unable to load offerings");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const loadCreateData = async () => {
    setError("");
    if (createData.courses.length) return;
    const [courses, programs, faculty] = await Promise.all([
      api.courses(),
      api.academicPrograms(),
      api.facultyStaff("", "", "teaching", 1, { status: "active" }),
    ]);
    setCreateData({
      courses: courses.courses || [],
      programs: programs.programs || [],
      faculty: faculty.staff || faculty.rows || [],
    });
  };

  const openCreate = async () => {
    setError("");
    setCreateOpen(true);
    try {
      await loadCreateData();
    } catch (e: any) {
      setError(e.message || "Unable to load creation options");
    }
  };

  const openEdit = async (row: any) => {
    setError("");
    try {
      await loadCreateData();
      const allocation = (row.faculty_allocations || [])[0];
      setEditing({
        ...row,
        allocation_id: allocation?.id || "",
        faculty_id: allocation?.faculty_id || "",
        section_id: allocation?.section_id || "",
      });
      setEditOpen(true);
    } catch (e: any) {
      setError(e.message || "Unable to load editing options");
    }
  };

  const createDepartments = Array.from(
    new Set(createData.courses.map((x: any) => x.dept).filter(Boolean)),
  ) as string[];
  const createPrograms = createData.programs.filter((program: any) =>
    createData.courses.some(
      (course: any) =>
        course.program_id === program.id &&
        (!createForm.department || course.dept === createForm.department),
    ),
  );
  const createCourses = createData.courses.filter(
    (course: any) =>
      (!createForm.department || course.dept === createForm.department) &&
      (!createForm.program_id || course.program_id === createForm.program_id) &&
      (!createForm.semester || Number(course.semester) === Number(createForm.semester)),
  );

  const submitCreate = async () => {
    setCreating(true);
    setError("");
    try {
      if (!createForm.academic_year || !createForm.semester || !createForm.program_id || !createForm.course_id || !createForm.term) {
        throw new Error("Academic year, semester, branch, course, and term are required");
      }
      const created = await api.createCourseOffering({
        course_id: createForm.course_id,
        program_id: createForm.program_id,
        academic_year: createForm.academic_year.trim(),
        term: createForm.term.trim(),
        semester: Number(createForm.semester),
      });
      const offering = created.offering;
      if (createForm.faculty_id) {
        await api.createFacultyAllocation(offering.id, { faculty_id: createForm.faculty_id });
      }
      if (createForm.course_start_date || createForm.expected_completion_date) {
        await api.updateCurriculumExecution(offering.id, {
          course_start_date: createForm.course_start_date,
          expected_completion_date: createForm.expected_completion_date,
        });
      }
      setCreateOpen(false);
      setCreateForm({ academic_year: "", semester: "", department: "", program_id: "", course_id: "", term: "", faculty_id: "", course_start_date: "", expected_completion_date: "" });
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to create course offering");
    } finally {
      setCreating(false);
    }
  };

  const submitEdit = async () => {
    if (!editing) return;
    setSavingEdit(true);
    setError("");
    try {
      await api.updateCourseOffering(editing.id, {
        course_id: editing.course_id,
        program_id: editing.program_id,
        academic_year: editing.academic_year.trim(),
        term: editing.term.trim(),
        semester: Number(editing.semester),
      });
      await api.updateCurriculumExecution(editing.id, {
        course_start_date: editing.course_start_date || "",
        expected_completion_date: editing.expected_completion_date || "",
      });
      if (editing.faculty_id) {
        if (editing.allocation_id) {
          await api.updateFacultyAllocation(editing.id, editing.allocation_id, { faculty_id: editing.faculty_id, section_id: editing.section_id || "" });
        } else {
          await api.createFacultyAllocation(editing.id, { faculty_id: editing.faculty_id });
        }
      }
      setEditOpen(false);
      setEditing(null);
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to update course offering");
    } finally {
      setSavingEdit(false);
    }
  };

  async function details(row: any) {
    setSelected({ row, loading: true });
    try {
      const [h, a, r, sections] = await Promise.all([
        api.hodInput(row.id),
        api.facultyAllocations(row.id),
        api.courseOfferingReadiness(row.id),
        api.sections(),
      ]);
      setSelected({
        row,
        hod: h.hod_input,
        allocations: a.allocations || [],
        readiness: r.readiness,
        sections: (sections.sections || []).filter(
          (x: any) => x.offering_id === row.id,
        ),
        loading: false,
      });
    } catch {
      setSelected({
        row,
        hod: row.hod_input,
        allocations: row.faculty_allocations || [],
        readiness: row.readiness,
        sections: row.sections || [],
        loading: false,
      });
    }
  }

  const years = useMemo(
    () =>
      Array.from(
        new Set(
          (rows || [])
            .map((x: any) => Math.ceil(Number(x.semester || 1) / 2))
            .filter(Boolean),
        ),
      ).sort((a: any, b: any) => a - b),
    [rows],
  );

  const visibleRows = useMemo(
    () =>
      (rows || []).filter((x: any) => {
        const studentYear = Math.ceil(Number(x.semester || 1) / 2);
        const allocations = x.faculty_allocations || [];
        return (
          (!year || studentYear === year) &&
          (!academicYear || x.academic_year === academicYear) &&
          (!program ||
            x.program_id === program ||
            x.program_code === program) &&
          (!term || x.term === term) &&
          (!status || x.status === status) &&
          (!faculty ||
            allocations.some(
              (a: any) => String(a.faculty || a.faculty_id) === faculty,
            ))
        );
      }),
    [rows, year, academicYear, program, term, status, faculty],
  );

  const activeFilters = [academicYear, program, term, faculty, status].filter(
    Boolean,
  ).length;

  const clearFilters = () => {
    setAcademicYear("");
    setProgram("");
    setTerm("");
    setFaculty("");
    setStatus("");
    setYear(0);
  };

  if (!rows)
    return error ? (
      <div className="calendar-banner warn">{error}</div>
    ) : (
      <Spinner />
    );

  const programs = Array.from(
    new Map(
      rows
        .filter((x: any) => x.program_id || x.program_code)
        .map((x: any) => [
          String(x.program_id || x.program_code),
          x.program_code || x.program || "Unknown Program",
        ]),
    ).entries(),
  );

  const academicYears = Array.from(
    new Set(rows.map((x: any) => x.academic_year).filter(Boolean)),
  );

  const terms = Array.from(
    new Set(rows.map((x: any) => x.term).filter(Boolean)),
  );

  const faculties = Array.from(
    new Map(
      rows
        .flatMap((x: any) => x.faculty_allocations || [])
        .map((a: any) => [
          String(a.faculty || a.faculty_id),
          a.faculty || a.faculty_id,
        ]),
    ).entries(),
  );

  const statuses = Array.from(
    new Set(rows.map((x: any) => x.status).filter(Boolean)),
  );

  return (
    <div className="fade-in offerings-page">
      <style>{`
        .offerings-page {
          --offer-burgundy: #7a1f35;
          --offer-burgundy-dark: #64182b;
          --offer-border: #e7e8ec;
          --offer-muted: #70747d;
          --offer-soft: #f7f7f9;
        }

        .offerings-page * {
          box-sizing: border-box;
        }

        .offer-create-modal {
          max-height: 92vh;
          display: flex;
          flex-direction: column;
        }

        .offer-create-modal .modal-h,
        .offer-create-modal .modal-f {
          flex: 0 0 auto;
        }

        .offer-create-modal .modal-b {
          min-height: 0;
          overflow-y: auto;
        }

        .offer-details-modal {
          max-height: 92vh;
          display: flex;
          flex-direction: column;
        }

        .offer-details-modal .modal-h,
        .offer-details-modal .modal-f {
          flex: 0 0 auto;
        }

        .offer-details-modal .modal-b {
          min-height: 0;
          overflow-y: auto;
        }

        .offerings-head {
          margin-bottom: 28px;
        }

        .offerings-message {
          margin-bottom: 20px;
        }

        .offerings-year-nav {
          display: flex;
          align-items: center;
          gap: 6px;
          min-height: 48px;
          border-bottom: 1px solid var(--offer-border);
          margin-bottom: 22px;
          overflow-x: auto;
          scrollbar-width: none;
        }

        .offerings-year-nav::-webkit-scrollbar {
          display: none;
        }

        .offerings-year-btn {
          position: relative;
          border: 0;
          background: transparent;
          color: #676b73;
          padding: 12px 18px 14px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          white-space: nowrap;
        }

        .offerings-year-btn:hover {
          color: var(--offer-burgundy);
        }

        .offerings-year-btn.active {
          color: var(--offer-burgundy);
        }

        .offerings-year-btn.active::after {
          content: "";
          position: absolute;
          left: 12px;
          right: 12px;
          bottom: -1px;
          height: 3px;
          border-radius: 3px 3px 0 0;
          background: var(--offer-burgundy);
        }

        .offerings-toolbar {
          display: flex;
          align-items: flex-end;
          gap: 14px;
          flex-wrap: wrap;
          margin-bottom: 26px;
        }

        .offer-filter {
          min-width: 155px;
          flex: 1 1 155px;
        }

        .offer-filter.wide {
          flex-basis: 185px;
        }

        .offer-filter label {
          display: block;
          margin: 0 0 7px 2px;
          color: #666a72;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: .04em;
          text-transform: uppercase;
        }

        .offer-filter .select {
          width: 100%;
          min-height: 42px;
          background: #fff;
          border: 1px solid #dfe1e6;
          border-radius: 9px;
          padding: 0 12px;
          font-size: 13px;
        }

        .offer-filter .select:focus {
          border-color: var(--offer-burgundy);
          outline: none;
          box-shadow: 0 0 0 3px rgba(122,31,53,.08);
        }

        .offer-filter-clear {
          min-height: 42px;
          padding: 0 14px;
          border: 1px solid #dfe1e6;
          border-radius: 9px;
          background: #fff;
          color: #666a72;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          white-space: nowrap;
        }

        .offer-filter-clear:hover {
          color: var(--offer-burgundy);
          border-color: #cfa9b4;
        }

        .offer-filter-count {
          color: var(--offer-burgundy);
          margin-left: 5px;
          font-weight: 700;
        }

        .offer-summary {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          margin-bottom: 15px;
        }

        .offer-summary-title {
          margin: 0;
          color: #202228;
          font-size: 18px;
          font-weight: 700;
        }

        .offer-summary-sub {
          margin: 4px 0 0;
          color: var(--offer-muted);
          font-size: 13px;
        }

        .offer-result-count {
          color: #62666e;
          font-size: 13px;
          white-space: nowrap;
        }

        .offer-table-shell {
          background: #fff;
          border: 1px solid var(--offer-border);
          border-radius: 12px;
          overflow: hidden;
          box-shadow: 0 2px 8px rgba(20,20,30,.025);
        }

        .offer-table-shell .tbl-scroll {
          overflow-x: auto;
        }

        .offer-table-shell .tbl {
          width: 100%;
          min-width: 820px;
          border-collapse: separate;
          border-spacing: 0;
        }

        .offer-table-shell .tbl thead th {
          background: #fafafb;
          color: #6c7078;
          border-bottom: 1px solid var(--offer-border);
          padding: 13px 16px;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: .055em;
          text-transform: uppercase;
          white-space: nowrap;
        }

        .offer-table-shell .tbl tbody td {
          padding: 17px 16px;
          border-bottom: 1px solid #eff0f2;
          color: #33363d;
          font-size: 13px;
          vertical-align: middle;
        }

        .offer-table-shell .tbl tbody tr:last-child td {
          border-bottom: 0;
        }

        .offer-table-shell .tbl tbody tr:hover td {
          background: #fcfbfc;
        }

        .offer-course {
          min-width: 190px;
        }

        .offer-course-code {
          color: #25272d;
          font-size: 14px;
          font-weight: 700;
        }

        .offer-course-title {
          display: block;
          margin-top: 4px;
          color: #777b83;
          font-size: 12px;
          line-height: 1.4;
        }

        .offer-secondary {
          display: block;
          margin-top: 4px;
          color: #858991;
          font-size: 11px;
        }

        .offer-number {
          font-weight: 650;
          color: #34373e;
        }

        .offer-faculty-names {
          display: block;
          max-width: 180px;
          color: #34373e;
          font-size: 12px;
          font-weight: 650;
          line-height: 1.4;
        }

        .offer-date {
          white-space: nowrap;
          color: #5f636b;
          font-size: 12px;
        }

        .offer-view {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: 0;
          background: transparent;
          padding: 7px;
          color: var(--offer-burgundy);
          font-size: 17px;
          cursor: pointer;
          border-radius: 7px;
        }

        .offer-view:hover {
          background: #f7e9ed;
        }

        .offer-empty {
          padding: 42px 20px;
        }

        .offer-modal {
          display: flex;
          flex-direction: column;
          gap: 22px;
        }

        .offer-modal-hero {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 20px;
          padding-bottom: 20px;
          border-bottom: 1px solid var(--offer-border);
        }

        .offer-modal-code {
          color: var(--offer-burgundy);
          font-size: 12px;
          font-weight: 700;
          letter-spacing: .06em;
          text-transform: uppercase;
        }

        .offer-modal-title {
          margin: 5px 0 4px;
          color: #202228;
          font-size: 20px;
          font-weight: 750;
        }

        .offer-modal-meta {
          color: #747880;
          font-size: 12px;
        }

        .offer-modal-section {
          padding-top: 2px;
        }

        .offer-modal-section-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 15px;
          margin-bottom: 12px;
        }

        .offer-modal-section-head h3 {
          margin: 0;
          color: #2b2d33;
          font-size: 14px;
          font-weight: 700;
        }

        .offer-info-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
        }

        .offer-info {
          min-width: 0;
          padding: 12px 13px;
          background: #fafafb;
          border: 1px solid #ececef;
          border-radius: 9px;
        }

        .offer-info span {
          display: block;
          color: #80838b;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: .04em;
          text-transform: uppercase;
          margin-bottom: 5px;
        }

        .offer-info b {
          display: block;
          color: #34363c;
          font-size: 12px;
          line-height: 1.45;
          word-break: break-word;
        }

        .offer-detail-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .offer-detail-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 15px;
          padding: 11px 13px;
          border: 1px solid #ececef;
          border-radius: 9px;
          background: #fff;
        }

        .offer-detail-row span {
          color: #686c74;
          font-size: 12px;
        }

        .offer-detail-row b {
          color: #303238;
          font-size: 12px;
          text-align: right;
        }

        @media (max-width: 900px) {
          .offer-filter {
            flex-basis: calc(50% - 8px);
          }

          .offer-filter.wide {
            flex-basis: calc(50% - 8px);
          }
        }

        @media (max-width: 600px) {
          .offerings-head {
            margin-bottom: 20px;
          }

          .offerings-toolbar {
            gap: 12px;
          }

          .offer-filter,
          .offer-filter.wide {
            flex-basis: 100%;
          }

          .offer-summary {
            align-items: flex-start;
            flex-direction: column;
            gap: 6px;
          }

          .offer-info-grid {
            grid-template-columns: 1fr;
          }

          .offer-modal-hero {
            flex-direction: column;
          }
        }
      `}</style>

      <div className="offerings-head">
        <PageHead
          title="Course Offerings"
          sub="Manage term-specific course offerings, faculty allocation and section readiness."
          right={
            <div className="offerings-head-actions">
              <button className="btn btn-crimson" onClick={openCreate}>Create offering</button>
              <button className="btn btn-out" onClick={load}>Refresh</button>
            </div>
          }
        />
      </div>

      {error && (
        <div className="calendar-banner warn offerings-message">{error}</div>
      )}

      <nav className="offerings-year-nav" aria-label="Student year">
        <button
          className={`offerings-year-btn ${year === 0 ? "active" : ""}`}
          onClick={() => setYear(0)}
        >
          All Years
        </button>

        {[1, 2, 3, 4].map((y) => (
          <button
            key={y}
            className={`offerings-year-btn ${year === y ? "active" : ""}`}
            onClick={() => setYear(year === y ? 0 : y)}
          >
            {y}
            {y === 1 ? "st" : y === 2 ? "nd" : y === 3 ? "rd" : "th"} Year
          </button>
        ))}
      </nav>

      <div className="offerings-toolbar">
        <button className="btn btn-out offer-filter-toggle" onClick={() => setFiltersOpen((open) => !open)}>
          {filtersOpen ? "Hide filters" : "Filters"}
        </button>
        {filtersOpen && <>
        <div className="offer-filter wide">
          <label>Academic Year</label>
          <select
            className="select"
            value={academicYear}
            onChange={(e) => setAcademicYear(e.target.value)}
          >
            <option value="">All academic years</option>
            {academicYears.map((x: any) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </div>

        <div className="offer-filter wide">
          <label>Program</label>
          <select
            className="select"
            value={program}
            onChange={(e) => setProgram(e.target.value)}
          >
            <option value="">All programs</option>
            {programs.map(([id, label]) => (
              <option value={String(id)} key={String(id)}>
                {String(label)}
              </option>
            ))}
          </select>
        </div>

        <div className="offer-filter">
          <label>Term</label>
          <select
            className="select"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
          >
            <option value="">All terms</option>
            {terms.map((x: any) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </div>

        <div className="offer-filter">
          <label>Faculty</label>
          <select
            className="select"
            value={faculty}
            onChange={(e) => setFaculty(e.target.value)}
          >
            <option value="">All faculty</option>
            {faculties.map(([id, label]) => (
              <option value={String(id)} key={String(id)}>
                {String(label)}
              </option>
            ))}
          </select>
        </div>

        <div className="offer-filter">
          <label>Status</label>
          <select
            className="select"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            {statuses.map((x: any) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </div>

        {activeFilters > 0 && (
          <button className="offer-filter-clear" onClick={clearFilters}>
            Clear
            <span className="offer-filter-count">{activeFilters}</span>
          </button>
        )}
        </>}
      </div>

      <div className="offer-summary">
        <div>
          <h2 className="offer-summary-title">Course Offerings</h2>
          <p className="offer-summary-sub">
            Review HOD inputs, faculty assignments and section readiness.
          </p>
        </div>
        <div className="offer-result-count">
          Showing <strong>{visibleRows.length}</strong> of{" "}
          <strong>{rows.length}</strong> offerings
        </div>
      </div>

      <section className="offer-table-shell">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Course</th>
                <th>Program</th>
                <th>Academic Year</th>
                <th>Semester / Term</th>
                <th>Faculty</th>
                <th>Start Date</th>
                <th>End Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((x) => {
                const a = x.faculty_allocations || [];
                const facultyNames = Array.from(
                  new Set(a.map((z: any) => z.faculty || z.faculty_id).filter(Boolean)),
                ).join(", ");

                return (
                  <tr key={x.id}>
                    <td className="offer-course">
                      <div className="offer-course-code">
                        {x.course_code || "—"}
                      </div>
                      <span className="offer-course-title">
                        {x.course_title || "Course title unavailable"}
                      </span>
                    </td>

                    <td>
                      <strong>{x.program_code || x.program || "—"}</strong>
                    </td>

                    <td>{x.academic_year || "—"}</td>

                    <td>
                      <strong>{x.semester || "—"}</strong>
                      <span className="offer-secondary">
                        {x.term || "Term unavailable"}
                      </span>
                    </td>

                    <td>
                      <span className="offer-faculty-names">
                        {facultyNames || "No faculty assigned"}
                      </span>
                    </td>

                    <td className="offer-date">{x.course_start_date || "—"}</td>
                    <td className="offer-date">{x.expected_completion_date || "—"}</td>

                    <td>
                      <button className="offer-view" title="Edit offering" aria-label="Edit offering" onClick={() => openEdit(x)}>
                        <FiEdit2 aria-hidden="true" />
                      </button>
                      <button
                        className="offer-view"
                        title="View details"
                        aria-label="View details"
                        onClick={() => details(x)}
                      >
                        <FiEye aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {!visibleRows.length && (
          <div className="offer-empty">
            <Empty text="No course offerings match the selected filters." />
          </div>
        )}
      </section>

      {selected && (
        <Modal
          title={`${selected.row.course_code} · Sections & Workflow`}
          className="offer-details-modal"
          onClose={() => setSelected(null)}
          footer={<button className="btn btn-crimson" title="Edit offering" aria-label="Edit offering" onClick={() => { setSelected(null); openEdit(selected.row); }}><FiEdit2 aria-hidden="true" /></button>}
        >
          {selected.loading ? (
            <Spinner />
          ) : (
            <div className="offer-modal">
              <div className="offer-modal-hero">
                <div>
                  <div className="offer-modal-code">
                    {selected.row.course_code}
                  </div>
                  <h2 className="offer-modal-title">
                    {selected.row.course_title || "Course Offering"}
                  </h2>
                  <div className="offer-modal-meta">
                    {selected.row.program_code ||
                      selected.row.program ||
                      "Program unavailable"}{" "}
                    · {selected.row.academic_year || "Academic year unavailable"}{" "}
                    · Semester {selected.row.semester || "—"} ·{" "}
                    {selected.row.term || "Term unavailable"}
                  </div>
                </div>

                <Pill
                  s={
                    selected.readiness?.ready
                      ? "Ready"
                      : "Not Ready"
                  }
                />
              </div>

              <DetailSection
                title="HOD Input"
                badge={selected.hod?.status || "Pending"}
              >
                {selected.hod ? (
                  <div className="offer-info-grid">
                    <Info
                      l="Required faculty"
                      v={selected.hod.required_faculty_count}
                    />
                    <Info
                      l="Required sections"
                      v={selected.hod.required_sections}
                    />
                    <Info
                      l="Expected capacity"
                      v={selected.hod.expected_capacity}
                    />
                    <Info
                      l="Lab / Theory"
                      v={selected.hod.delivery_type}
                    />
                    <Info
                      l="Remarks"
                      v={selected.hod.remarks || "—"}
                    />
                  </div>
                ) : (
                  <Empty text="HOD input is pending." />
                )}
              </DetailSection>

              <DetailSection
                title="Faculty Allocation"
                badge={selected.allocations.length ? "Assigned" : "Pending"}
              >
                {selected.allocations.length ? (
                  <div className="offer-detail-list">
                    {selected.allocations.map((a: any) => (
                      <div className="offer-detail-row" key={a.id}>
                        <span>{a.faculty || a.faculty_id}</span>
                        <b>
                          {a.status} · {a.section_id || "Offering-level"}
                        </b>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Empty text="No faculty allocated." />
                )}
              </DetailSection>

              <DetailSection
                title="Sections"
                badge={`${selected.sections.length} created`}
              >
                {selected.sections.length ? (
                  <div className="offer-detail-list">
                    {selected.sections.map((s: any) => (
                      <div className="offer-detail-row" key={s.id}>
                        <span>
                          {s.course_code} · Section {s.section}
                        </span>
                        <b>
                          {s.faculty || "—"} · {s.room || "No room"} ·{" "}
                          {s.schedule || "No schedule"} ·{" "}
                          {s.enrolled || 0}/{s.capacity} ·{" "}
                          {s.faculty === "—" ? "Pending" : "Ready"}
                        </b>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Empty text="No sections associated with this offering." />
                )}
              </DetailSection>

              <DetailSection
                title="Readiness"
                badge={selected.readiness?.ready ? "Ready" : "Not Ready"}
              >
                <div className="offer-info-grid">
                  <Info
                    l="HOD Input"
                    v={
                      selected.readiness?.hod_submitted
                        ? "Complete"
                        : "Pending"
                    }
                  />
                  <Info
                    l="Sections / Capacity"
                    v={
                      selected.readiness?.sections_defined
                        ? "Complete"
                        : "Pending"
                    }
                  />
                  <Info
                    l="Faculty"
                    v={
                      selected.readiness?.faculty_complete
                        ? "Complete"
                        : "Pending"
                    }
                  />
                  <Info
                    l="Overall"
                    v={
                      selected.readiness?.ready
                        ? "Ready for sections"
                        : "Not ready for sections"
                    }
                  />
                </div>
              </DetailSection>

              <DetailSection title="Execution marks">
                <div className="offer-info-grid">
                  <Info l="Lab marks" v={selected.row.lab_marks} />
                  <Info l="Mid marks" v={selected.row.mid_marks} />
                  <Info l="Semester marks" v={selected.row.semester_marks} />
                </div>
              </DetailSection>
            </div>
          )}
        </Modal>
      )}

      {createOpen && (
        <Modal
          title="Create course offering"
          className="offer-create-modal"
          onClose={() => setCreateOpen(false)}
          footer={
            <div className="curriculum-modal-footer">
              <button className="btn btn-out" onClick={() => setCreateOpen(false)}>Cancel</button>
              <button className="btn btn-crimson" disabled={creating} onClick={submitCreate}>
                {creating ? "Creating..." : "Create offering"}
              </button>
            </div>
          }
        >
          <div className="curriculum-create-grid">
            <div className="form-row"><label>Academic year</label><input className="inp" value={createForm.academic_year} onChange={(e) => setCreateForm({ ...createForm, academic_year: e.target.value })} placeholder="e.g. 2026-27" /></div>
            <div className="form-row"><label>Semester</label><select className="select" value={createForm.semester} onChange={(e) => setCreateForm({ ...createForm, semester: e.target.value, course_id: "" })}><option value="">Select semester</option>{Array.from({ length: 8 }, (_, index) => index + 1).map((semester) => <option key={semester} value={semester}>{semester}</option>)}</select></div>
            <div className="form-row"><label>Department</label><select className="select" value={createForm.department} onChange={(e) => setCreateForm({ ...createForm, department: e.target.value, program_id: "", course_id: "" })}><option value="">Select department</option>{createDepartments.map((department) => <option key={department}>{department}</option>)}</select></div>
            <div className="form-row"><label>Branch</label><select className="select" value={createForm.program_id} onChange={(e) => setCreateForm({ ...createForm, program_id: e.target.value, course_id: "" })}><option value="">Select branch</option>{createPrograms.map((program: any) => <option key={program.id} value={program.id}>{program.code} · {program.name}</option>)}</select></div>
            <div className="form-row curriculum-create-full"><label>Course</label><select className="select" value={createForm.course_id} onChange={(e) => setCreateForm({ ...createForm, course_id: e.target.value })}><option value="">Select course</option>{createCourses.map((course: any) => <option key={course.id} value={course.id}>{course.code} · {course.title}</option>)}</select></div>
            <div className="form-row"><label>Term</label><input className="inp" value={createForm.term} onChange={(e) => setCreateForm({ ...createForm, term: e.target.value })} placeholder="e.g. Odd Semester" /></div>
            <div className="form-row"><label>Faculty name</label><select className="select" value={createForm.faculty_id} onChange={(e) => setCreateForm({ ...createForm, faculty_id: e.target.value })}><option value="">Select faculty</option>{createData.faculty.map((person: any) => <option key={person.id} value={person.id}>{person.name}</option>)}</select></div>
            <div className="form-row"><label>Start date</label><input className="inp" type="date" value={createForm.course_start_date} onChange={(e) => setCreateForm({ ...createForm, course_start_date: e.target.value })} /></div>
            <div className="form-row"><label>End date</label><input className="inp" type="date" min={createForm.course_start_date || undefined} value={createForm.expected_completion_date} onChange={(e) => setCreateForm({ ...createForm, expected_completion_date: e.target.value })} /></div>
          </div>
        </Modal>
      )}

      {editOpen && editing && (
        <Modal
          title={`Edit ${editing.course_code || "course offering"}`}
          className="offer-create-modal"
          onClose={() => { setEditOpen(false); setEditing(null); }}
          footer={
            <div className="curriculum-modal-footer">
              <button className="btn btn-out" onClick={() => { setEditOpen(false); setEditing(null); }}>Cancel</button>
              <button className="btn btn-crimson" disabled={savingEdit} onClick={submitEdit}>
                {savingEdit ? "Saving..." : "Save changes"}
              </button>
            </div>
          }
        >
          <div className="curriculum-create-grid">
            <div className="form-row"><label>Academic year</label><input className="inp" value={editing.academic_year || ""} onChange={(e) => setEditing({ ...editing, academic_year: e.target.value })} /></div>
            <div className="form-row"><label>Semester</label><select className="select" value={editing.semester || ""} onChange={(e) => setEditing({ ...editing, semester: e.target.value, course_id: "" })}><option value="">Select semester</option>{Array.from({ length: 8 }, (_, index) => index + 1).map((semester) => <option key={semester} value={semester}>{semester}</option>)}</select></div>
            <div className="form-row"><label>Department</label><select className="select" value={editing.department || ""} onChange={(e) => setEditing({ ...editing, department: e.target.value, program_id: "", course_id: "" })}><option value="">Select department</option>{createDepartments.map((department) => <option key={department}>{department}</option>)}</select></div>
            <div className="form-row"><label>Branch</label><select className="select" value={editing.program_id || ""} onChange={(e) => setEditing({ ...editing, program_id: e.target.value, course_id: "" })}><option value="">Select branch</option>{createData.programs.filter((program: any) => createData.courses.some((course: any) => course.program_id === program.id && (!editing.department || course.dept === editing.department))).map((program: any) => <option key={program.id} value={program.id}>{program.code} · {program.name}</option>)}</select></div>
            <div className="form-row curriculum-create-full"><label>Course</label><select className="select" value={editing.course_id || ""} onChange={(e) => setEditing({ ...editing, course_id: e.target.value })}><option value="">Select course</option>{createData.courses.filter((course: any) => (!editing.department || course.dept === editing.department) && (!editing.program_id || course.program_id === editing.program_id) && (!editing.semester || Number(course.semester) === Number(editing.semester))).map((course: any) => <option key={course.id} value={course.id}>{course.code} · {course.title}</option>)}</select></div>
            <div className="form-row"><label>Term</label><input className="inp" value={editing.term || ""} onChange={(e) => setEditing({ ...editing, term: e.target.value })} /></div>
            <div className="form-row"><label>Faculty name</label><select className="select" value={editing.faculty_id || ""} onChange={(e) => setEditing({ ...editing, faculty_id: e.target.value })}><option value="">No faculty assigned</option>{createData.faculty.map((person: any) => <option key={person.id} value={person.id}>{person.name}</option>)}</select></div>
            <div className="form-row"><label>Start date</label><input className="inp" type="date" value={editing.course_start_date || ""} onChange={(e) => setEditing({ ...editing, course_start_date: e.target.value })} /></div>
            <div className="form-row"><label>End date</label><input className="inp" type="date" min={editing.course_start_date || undefined} value={editing.expected_completion_date || ""} onChange={(e) => setEditing({ ...editing, expected_completion_date: e.target.value })} /></div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function DetailSection({
  title,
  badge,
  children,
}: {
  title: string;
  badge?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="offer-modal-section">
      <div className="offer-modal-section-head">
        <h3>{title}</h3>
        {badge && <Pill s={badge} />}
      </div>
      {children}
    </section>
  );
}

function Info({ l, v }: { l: string; v: any }) {
  return (
    <div className="offer-info">
      <span>{l}</span>
      <b>{String(v ?? "—")}</b>
    </div>
  );
}
