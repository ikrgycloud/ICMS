import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Empty, PageHead, Spinner } from "./kit";

type Filters = {
  academicYear: string;
  term: string;
  semester: string;
  year: string;
  branch: string;
  program: string;
  department: string;
  course: string;
  status: string;
};

const initialFilters: Filters = {
  academicYear: "",
  term: "",
  semester: "",
  year: "",
  branch: "",
  program: "",
  department: "",
  course: "",
  status: "",
};

export default function AcademicCoordinatorReports() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [filtersOpen, setFiltersOpen] = useState(true);
  const [previewReport, setPreviewReport] = useState<any>(null);

  useEffect(() => {
    Promise.allSettled([
      api.academicPrograms(),
      api.courseOfferings(),
      api.sections(),
      api.timetablePlans(),
      api.academicConflicts(),
      api.classSessions(),
      api.curriculumExecution(),
      api.academicCalendar(),
      api.academicAnnouncements(),
    ])
      .then((results: any[]) => {
        const value = results.map((result) => (result.status === "fulfilled" ? result.value : {}));
        setData({
          programs: value[0]?.programs || [],
          offerings: value[1]?.offerings || [],
          sections: value[2]?.sections || [],
          plans: value[3]?.plans || [],
          conflicts: value[4]?.conflicts || [],
          sessions: value[5]?.sessions || [],
          execution: value[6]?.items || [],
          calendar: value[7]?.entries || [],
          notices: value[8]?.announcements || [],
        });
      })
      .catch((e: any) => setError(e.message || "Unable to load reports"));
  }, []);

  const options = useMemo(() => {
    if (!data) return {} as any;
    const execution = data.execution || [];

    return {
      academicYear: unique(execution.map((x: any) => x.academic_year)),
      term: unique(execution.map((x: any) => x.term)),
      semester: unique(execution.map((x: any) => x.semester)),
      year: unique(execution.map((x: any) => x.student_year)),
      branch: unique(execution.map((x: any) => x.program_code || x.program)),
      program: unique(execution.map((x: any) => x.program_code || x.program)),
      department: unique(execution.map((x: any) => x.department)),
      course: unique(execution.map((x: any) => x.course_code)),
      status: unique([
        ...execution.map((x: any) => x.execution_status),
        ...data.plans.map((x: any) => x.status),
      ]),
    };
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return null;

    const matches = (row: any) => {
      const year = String(row.student_year || Math.ceil(Number(row.semester || 1) / 2));
      const branch = row.program_code || row.program || "";
      return (
        (!filters.academicYear || row.academic_year === filters.academicYear) &&
        (!filters.term || row.term === filters.term) &&
        (!filters.semester || String(row.semester) === filters.semester) &&
        (!filters.year || year === filters.year) &&
        (!filters.branch || branch === filters.branch) &&
        (!filters.program || branch === filters.program) &&
        (!filters.department || row.department === filters.department) &&
        (!filters.course || row.course_code === filters.course) &&
        (!filters.status || row.execution_status === filters.status)
      );
    };

    const execution = data.execution.filter(matches);
    const ids = new Set(execution.map((row: any) => row.id));
    const sections = data.sections
      .filter((row: any) => !filters.course || row.course_code === filters.course)
      .filter(
        (row: any) => !filters.program || row.program_code === filters.program || row.program === filters.program,
      );

    const offeringIds = new Set(execution.map((row: any) => row.id));
    const plans = data.plans.filter((plan: any) => offeringIds.has(plan.offering_id) || !filters.course);
    const conflicts = data.conflicts.filter((conflict: any) => !filters.status || conflict.status === filters.status);
    const sessions = data.sessions.filter((session: any) => ids.has(session.offering_id) || !filters.course);
    const calendar = data.calendar.filter(
      (row: any) =>
        (!filters.academicYear || row.academic_year === filters.academicYear) &&
        (!filters.term || row.term === filters.term) &&
        (!filters.department || row.department_id === filters.department),
    );

    return { execution, sections, plans, conflicts, sessions, calendar };
  }, [data, filters]);

  if (!data || !filtered) {
    return error ? <div className="calendar-banner warn">{error}</div> : <Spinner />;
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const totalReports = filtered.execution.length + filtered.plans.length + filtered.calendar.length + filtered.conflicts.length;
  const readyToDownload = filtered.plans.filter((row: any) => ["Approved", "Published"].includes(row.status)).length;
  const pendingInputs = filtered.plans.filter((row: any) => ["Draft", "HOD Returned", "VP Returned"].includes(row.status)).length;
  const unresolvedConflicts = filtered.conflicts.filter(
    (row: any) => !["Resolved", "resolved"].includes(row.status),
  ).length;

  const upcomingEvents = filtered.calendar.filter((row: any) => {
    const date = row.start_date || row.date;
    if (!date) return false;
    return new Date(date) >= today;
  }).length;

  const completedThisYear = filtered.calendar.filter((row: any) => {
    const date = row.start_date || row.date;
    const status = String(row.status || "").toLowerCase();
    if (!(status === "completed" || status === "complete") || !date) return false;
    return new Date(date).getFullYear() === new Date().getFullYear();
  }).length;

  const totalOfferings = filtered.execution.length;
  const facultyAllocated = filtered.execution.filter((row: any) => row.faculty && String(row.faculty).trim()).length;

  const programRows = summaryRows(
    filtered.execution,
    (row: any) => row.program_code || row.program || "Unknown",
  );

  const timetableRows = summaryRows(
    filtered.plans,
    (row: any) => row.status || "Unknown",
  );

  const eventRows = summaryRows(
    filtered.calendar,
    (row: any) => row.category || "General",
  );

  const curriculumRows = summaryRows(
    filtered.execution,
    (row: any) => row.execution_status || "Unknown",
  );

  const conflictRows = summaryRows(
    filtered.conflicts,
    (row: any) => row.severity || "Unknown",
  );

  const requestRows = summaryRows(
    filtered.plans,
    (row: any) => row.status || "Unknown",
  );

  const reportRows = [
    {
      name: "Academic Calendar Report",
      type: "academic-calendar",
      category: "Calendar",
      scope: "Academic Coordinator",
      updated: latestDate(filtered.calendar),
      status: filtered.calendar.length ? "Ready" : "No data",
      formats: ["PDF", "Excel"],
      icon: "🗓️",
      colors: ["#dff0ff", "#edf7ff"],
    },
    {
      name: "Course Offerings Report",
      type: "course-offerings",
      category: "Courses & Sections",
      scope: "Academic Coordinator",
      updated: latestDate(filtered.execution),
      status: filtered.execution.length ? "Ready" : "No data",
      formats: ["PDF", "Excel"],
      icon: "📚",
      colors: ["#ebf8f4", "#edf7ff"],
    },
    {
      name: "Faculty Allocation Report",
      type: "faculty-allocation",
      category: "Faculty & Workload",
      scope: "Academic Coordinator",
      updated: latestDate(filtered.execution),
      status: filtered.execution.length ? "Ready" : "No data",
      formats: ["PDF", "Excel"],
      icon: "👥",
      colors: ["#fceae8", "#fff3ed"],
    },
    {
      name: "Timetable Report",
      type: "timetable-report",
      category: "Timetable",
      scope: "Academic Coordinator",
      updated: latestDate(filtered.plans),
      status: filtered.plans.length ? "Ready" : "No data",
      formats: ["PDF", "Excel"],
      icon: "🧭",
      colors: ["#f5f0ff", "#eef7ff"],
    },
    {
      name: "Curriculum Execution Report",
      type: "curriculum-execution",
      category: "Curriculum",
      scope: "Academic Coordinator",
      updated: latestDate(filtered.execution),
      status: filtered.execution.length ? "Ready" : "No data",
      formats: ["PDF", "Excel"],
      icon: "📘",
      colors: ["#ecfdf5", "#edf7ff"],
    },
    {
      name: "Conflict Summary Report",
      type: "conflict-summary",
      category: "Readiness & Exceptions",
      scope: "Academic Coordinator",
      updated: latestDate(filtered.conflicts),
      status: filtered.conflicts.length ? "Ready" : "No data",
      formats: ["PDF", "Excel"],
      icon: "⚠️",
      colors: ["#fff3ee", "#fdf3ff"],
    },
  ];

  const handleViewReport = (report: any) => {
    const nextPreview = buildReportPreview(report, filtered);
    setPreviewReport(nextPreview);

    setTimeout(() => {
      document.getElementById("report-preview")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  };

  const handleDownloadReport = (report: any, format: "pdf" | "xlsx") => {
    const preview = buildReportPreview(report, filtered);
    downloadReport(preview, report.name, format);
  };

  return (
    <div className="fade-in reports-page-shell">
      <style>{styles}</style>
      <PageHead
        title="Reports"
        sub="View and download academic reports for effective academic operations management."
      />

      <div className="reports-page">
        <section className="report-toolbar">
          <div className="report-filter-row">
            <FilterSelect
              label="Academic Year"
              value={filters.academicYear}
              options={options.academicYear || []}
              onChange={(value) => setFilters({ ...filters, academicYear: value })}
            />
            <FilterSelect
              label="Semester"
              value={filters.semester}
              options={options.semester || []}
              onChange={(value) => setFilters({ ...filters, semester: value })}
            />
            <FilterSelect
              label="Department"
              value={filters.department}
              options={options.department || []}
              onChange={(value) => setFilters({ ...filters, department: value })}
            />
            <FilterSelect
              label="Program"
              value={filters.program}
              options={options.program || []}
              onChange={(value) => setFilters({ ...filters, program: value })}
            />
            <FilterSelect
              label="Year"
              value={filters.year}
              options={options.year || []}
              onChange={(value) => setFilters({ ...filters, year: value })}
            />
            <FilterSelect
              label="Section"
              value={filters.course}
              options={options.course || []}
              onChange={(value) => setFilters({ ...filters, course: value })}
            />
            <FilterSelect
              label="Date Range"
              value={filters.term}
              options={options.term || []}
              onChange={(value) => setFilters({ ...filters, term: value })}
            />
          </div>

          <div className="toolbar-actions">
            <button className="ghost-button" onClick={() => setFiltersOpen(!filtersOpen)}>
              {filtersOpen ? "Hide filters" : "Show filters"}
            </button>
            <button className="primary-button" onClick={() => setFilters(initialFilters)}>
              Search reports...
            </button>
          </div>
        </section>

        <section className="stat-grid">
          <StatCard tone="blue" icon="📚" title="Total Reports" value={totalReports} subtitle={`${totalOfferings} offerings`} />
          <StatCard tone="teal" icon="✅" title="Ready to Download" value={readyToDownload} subtitle={`${Math.round((readyToDownload / Math.max(totalReports, 1)) * 100)}% of total`} />
          <StatCard tone="amber" icon="🕒" title="Pending Inputs" value={pendingInputs} subtitle={`${pendingInputs} requiring action`} />
          <StatCard tone="rose" icon="⚠️" title="Unresolved Conflicts" value={unresolvedConflicts} subtitle={`${unresolvedConflicts} requiring review`} />
        </section>

        <section className="reports-table-section">
          <div className="section-head">
            <div>
              <h3>Most Used Reports</h3>
              <small>View and download frequently used academic reports.</small>
            </div>
            <button className="view-all">View All Reports →</button>
          </div>

          <div className="report-cards-grid">
            {reportRows.map((report, index) => (
              <article className="report-card" key={report.name}>
                <div className="report-icon" style={{ background: index % 2 === 0 ? report.colors[0] : report.colors[1] }}>
                  {report.icon}
                </div>
                <div className="report-card-body">
                  <h4>{report.name}</h4>
                  <p>{report.category}</p>
                  <div className="report-card-footer">
                    <span className={report.status === "Ready" ? "status ready" : "status pending"}>{report.status}</span>
                    <small>Last updated: {report.updated}</small>
                  </div>
                  <div className="report-actions">
                    <button className="small-button" onClick={() => handleViewReport(report)}>
                      View
                    </button>
                    <button className="small-button subtle" onClick={() => handleDownloadReport(report, "pdf")}>
                      Download PDF
                    </button>
                    <button className="small-button subtle" onClick={() => handleDownloadReport(report, "xlsx")}>
                      Export Excel
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="all-reports-section">
          <div className="all-reports-head">
            <div>
              <h3>All Reports</h3>
              <small>Complete list of academic reports.</small>
            </div>
            <div className="download-box">
              <h4>Download Formats</h4>
              <p>Reports are available in the following formats:</p>
              <div className="format-pills">
                <span>PDF</span>
                <span>Excel</span>
                <span>CSV</span>
              </div>
            </div>
          </div>

          <div className="report-table-wrap">
            <table className="report-table">
              <thead>
                <tr>
                  <th>Report Name</th>
                  <th>Category</th>
                  <th>Scope</th>
                  <th>Last Updated</th>
                  <th>Format</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {reportRows.map((report) => (
                  <tr key={report.name}>
                    <td>{report.name}</td>
                    <td>{report.category}</td>
                    <td>{report.scope}</td>
                    <td>{report.updated}</td>
                    <td>
                      <div className="format-list">
                        {report.formats.map((format) => (
                          <span key={format} className="format-chip">
                            {format}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className={report.status === "Ready" ? "status ready" : "status pending"}>{report.status}</span>
                    </td>
                    <td>
                      <div className="table-actions">
                        <button className="small-button" onClick={() => handleViewReport(report)}>
                          View
                        </button>
                        <button className="small-button subtle" onClick={() => handleDownloadReport(report, "pdf")}>
                          PDF
                        </button>
                        <button className="small-button subtle" onClick={() => handleDownloadReport(report, "xlsx")}>
                          Excel
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {previewReport && (
          <section id="report-preview" className="all-reports-section preview-section">
            <div className="all-reports-head">
              <div>
                <h3>{previewReport.name}</h3>
                <small>Live report preview generated from the current academic coordinator data.</small>
              </div>
              <button className="ghost-button" onClick={() => setPreviewReport(null)}>
                Close preview
              </button>
            </div>

            <div className="report-table-wrap">
              {previewReport.rows.length ? (
                <table className="report-table">
                  <thead>
                    <tr>
                      {previewReport.headers.map((header: string) => (
                        <th key={header}>{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewReport.rows.map((row: any, index: number) => (
                      <tr key={`${previewReport.name}-${index}`}>
                        {previewReport.headers.map((header: string) => (
                          <td key={`${header}-${index}`}>{row[header] ?? "—"}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <Empty text="No data is available for this report with the current filters." />
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: any[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="filter-box">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {options.map((option) => (
          <option key={String(option)} value={String(option)}>
            {String(option)}
          </option>
        ))}
      </select>
    </label>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  tone,
  icon,
}: {
  title: string;
  value: number;
  subtitle: string;
  tone: "blue" | "teal" | "amber" | "rose";
  icon: string;
}) {
  return (
    <article className={`stat-card ${tone}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-content">
        <h3>{title}</h3>
        <div className="stat-value">{value}</div>
        <small>{subtitle}</small>
      </div>
    </article>
  );
}

function buildReportPreview(report: any, filtered: any) {
  switch (report.type) {
    case "academic-calendar":
      return {
        name: report.name,
        headers: ["Event", "Category", "Department", "Start Date", "Status"],
        rows: (filtered.calendar || []).map((row: any) => ({
          Event: row.title || row.event_name || row.name || "Untitled event",
          Category: row.category || "General",
          Department: row.department || row.department_id || "All",
          "Start Date": row.start_date || row.date || "—",
          Status: row.status || "Scheduled",
        })),
      };
    case "course-offerings":
      return {
        name: report.name,
        headers: ["Branch", "Course", "Section", "Faculty", "Status"],
        rows: (filtered.execution || []).map((row: any) => ({
          Branch: row.program_code || row.program || "Unknown",
          Course: row.course_code || row.course || "—",
          Section: row.section_id || row.section || "—",
          Faculty: row.faculty || row.faculty_name || "Unassigned",
          Status: row.execution_status || "Not started",
        })),
      };
    case "faculty-allocation":
      return {
        name: report.name,
        headers: ["Branch", "Course", "Faculty", "Allocation Status"],
        rows: (filtered.execution || []).map((row: any) => ({
          Branch: row.program_code || row.program || "Unknown",
          Course: row.course_code || row.course || "—",
          Faculty: row.faculty || row.faculty_name || "Unassigned",
          "Allocation Status": row.faculty ? "Allocated" : "Pending",
        })),
      };
    case "timetable-report":
      return {
        name: report.name,
        headers: ["Branch", "Course", "Section", "Faculty", "Status", "Updated"],
        rows: (filtered.plans || []).map((row: any) => ({
          Branch: row.program_code || row.program || row.department || "Unknown",
          Course: row.course_code || row.course || row.section_id || "—",
          Section: row.section_id || row.section || "—",
          Faculty: row.faculty || row.faculty_name || row.instructor || "Unassigned",
          Status: row.status || "Unknown",
          Updated: row.updated_at || row.created_at || row.start_date || "—",
        })),
      };
    case "curriculum-execution":
      return {
        name: report.name,
        headers: ["Branch", "Course", "Student Year", "Curriculum Status"],
        rows: (filtered.execution || []).map((row: any) => ({
          Branch: row.program_code || row.program || "Unknown",
          Course: row.course_code || row.course || "—",
          "Student Year": row.student_year || row.year || "—",
          "Curriculum Status": row.execution_status || "Not started",
        })),
      };
    case "conflict-summary":
      return {
        name: report.name,
        headers: ["Conflict", "Severity", "Status", "Program"],
        rows: (filtered.conflicts || []).map((row: any) => ({
          Conflict: row.title || row.name || row.id || "Conflict",
          Severity: row.severity || "Unknown",
          Status: row.status || "Open",
          Program: row.program_code || row.program || row.department || "Unknown",
        })),
      };
    default:
      return {
        name: report.name,
        headers: ["Label", "Value"],
        rows: [],
      };
  }
}

function downloadReport(preview: any, reportName: string, format: "pdf" | "xlsx") {
  const headers = preview.headers || [];
  const rows = preview.rows || [];
  const slug = (reportName || "report").toLowerCase().replace(/[^a-z0-9]+/g, "-");

  if (format === "pdf") {
    const html = `
      <!doctype html>
      <html>
        <head>
          <meta charset="utf-8" />
          <title>${reportName}</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 24px; color: #1f2937; }
            h1 { font-size: 22px; margin-bottom: 12px; }
            table { border-collapse: collapse; width: 100%; margin-top: 16px; }
            th, td { border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; font-size: 12px; }
            th { background: #f3f4f6; }
          </style>
        </head>
        <body>
          <h1>${reportName}</h1>
          <table>
            <thead>
              <tr>${headers.map((header: string) => `<th>${header}</th>`).join("")}</tr>
            </thead>
            <tbody>
              ${rows
                .map(
                  (row: any) =>
                    `<tr>${headers
                      .map((header: string) => `<td>${String(row[header] ?? "—")}</td>`)
                      .join("")}</tr>`,
                )
                .join("") || "<tr><td colspan=\"${headers.length || 1}\">No data available</td></tr>"}
            </tbody>
          </table>
        </body>
      </html>
    `;

    const blob = new Blob([html], { type: "text/html;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${slug}.html`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    return;
  }

  const csvRows = [headers, ...rows.map((row: any) => headers.map((header) => row[header] ?? ""))]
    .map((line) => line.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(","))
    .join("\n");

  const blob = new Blob([csvRows], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${slug}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function summaryRows(items: any[], getKey: (row: any) => string) {
  const bucket = items.reduce((acc: Record<string, number>, row: any) => {
    const key = getKey(row) || "Unknown";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});

  return Object.entries(bucket)
    .map(([label, value]) => ({ label, value: Number(value) }))
    .sort((a, b) => b.value - a.value);
}

function latestDate(items: any[]) {
  const dates = items
    .map((row: any) => row.updated_at || row.created_at || row.start_date || row.date || row.published_at)
    .filter(Boolean)
    .map((value: string) => new Date(value))
    .filter((value: Date) => !Number.isNaN(value.getTime()));

  if (!dates.length) return new Date().toLocaleDateString();

  const latest = new Date(Math.max(...dates.map((date) => date.getTime())));
  return latest.toLocaleDateString();
}

function unique(values: any[]) {
  return Array.from(new Set(values.filter((value) => value !== undefined && value !== null && value !== ""))).sort(
    (a, b) => String(a).localeCompare(String(b), undefined, { numeric: true }),
  );
}

const styles = `
  .reports-page-shell {
    font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #edf2f7;
    color: #1f2a37;
    min-height: 100%;
  }

  .reports-page {
    padding: 18px 0 30px;
  }

  .report-toolbar {
    background: #ffffff;
    border: 1px solid #dfe7ee;
    border-radius: 16px;
    padding: 18px 20px;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    box-shadow: 0 8px 18px rgba(85, 96, 116, 0.05);
  }

  .report-filter-row {
    display: grid;
    grid-template-columns: repeat(7, minmax(120px, 1fr));
    gap: 12px;
    flex: 1;
  }

  .filter-box {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }

  .filter-box select {
    border: 1px solid #d7e2eb;
    border-radius: 10px;
    background: #f8fafc;
    min-height: 38px;
    padding: 0 10px;
    color: #27364a;
    font-size: 13px;
    font-weight: 600;
  }

  .toolbar-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .ghost-button,
  .primary-button,
  .view-all,
  .small-button {
    border: none;
    border-radius: 10px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .ghost-button {
    background: #eef5ff;
    color: #3c6fc7;
    min-height: 38px;
    padding: 0 14px;
  }

  .primary-button {
    background: linear-gradient(135deg, #2c6bed 0%, #2558c9 100%);
    color: #fff;
    min-height: 38px;
    padding: 0 18px;
    box-shadow: 0 10px 18px rgba(44, 107, 237, 0.22);
  }

  .primary-button:hover,
  .ghost-button:hover,
  .small-button:hover,
  .view-all:hover {
    transform: translateY(-1px);
  }

  .stat-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
    margin-top: 20px;
  }

  .stat-card {
    background: #fff;
    border: 1px solid #dfe7ee;
    border-radius: 16px;
    padding: 18px 18px 16px;
    display: flex;
    align-items: center;
    gap: 14px;
    box-shadow: 0 8px 18px rgba(85, 96, 116, 0.04);
  }

  .stat-card.blue { background: linear-gradient(135deg, #eaf4ff 0%, #edf7ff 100%); }
  .stat-card.teal { background: linear-gradient(135deg, #eefaf3 0%, #eff8f0 100%); }
  .stat-card.amber { background: linear-gradient(135deg, #fff8ea 0%, #fff6df 100%); }
  .stat-card.rose { background: linear-gradient(135deg, #fff0f4 0%, #fff3f7 100%); }

  .stat-icon {
    width: 52px;
    height: 52px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    background: rgba(255, 255, 255, 0.76);
    border: 1px solid rgba(255, 255, 255, 0.8);
  }

  .stat-content {
    flex: 1;
    min-width: 0;
  }

  .stat-content h3 {
    margin: 0;
    font-size: 13px;
    color: #64748b;
    font-weight: 700;
  }

  .stat-value {
    margin-top: 8px;
    font-size: 26px;
    font-weight: 800;
    color: #1e293b;
    line-height: 1.1;
  }

  .stat-content small {
    display: block;
    margin-top: 7px;
    font-size: 12px;
    color: #6b7280;
  }

  .tabs-row {
    margin-top: 22px;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    padding: 8px;
    background: #fff;
    border: 1px solid #dfe7ee;
    border-radius: 14px;
    box-shadow: 0 8px 18px rgba(85, 96, 116, 0.04);
  }

  .tab {
    border: 0;
    background: transparent;
    padding: 10px 14px;
    border-radius: 10px;
    color: #64748b;
    font-weight: 700;
    font-size: 13px;
    cursor: pointer;
  }

  .tab.active {
    background: #eef4ff;
    color: #2d6cdf;
  }

  .overview-grid {
    margin-top: 22px;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
  }

  .overview-panel {
    background: #fff;
    border: 1px solid #dfe7ee;
    border-radius: 16px;
    padding: 18px 18px 14px;
    box-shadow: 0 8px 18px rgba(85, 96, 116, 0.04);
  }

  .overview-panel header {
    margin-bottom: 14px;
  }

  .overview-panel h3 {
    margin: 0;
    font-size: 17px;
    color: #1f2a37;
  }

  .overview-panel small {
    display: block;
    margin-top: 4px;
    color: #64748b;
    font-size: 12px;
  }

  .bar-chart {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .bar-row {
    display: grid;
    grid-template-columns: 130px minmax(0, 1fr) 36px;
    align-items: center;
    gap: 12px;
    min-height: 24px;
  }

  .bar-label {
    font-size: 12px;
    color: #4b5563;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .bar-track {
    width: 100%;
    height: 10px;
    border-radius: 999px;
    overflow: hidden;
    background: #edf2f7;
  }

  .bar-fill {
    height: 100%;
    border-radius: inherit;
  }

  .bar-row b {
    font-size: 12px;
    color: #1f2a37;
    text-align: right;
  }

  .reports-table-section {
    margin-top: 22px;
    background: #fff;
    border: 1px solid #dfe7ee;
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 8px 18px rgba(85, 96, 116, 0.04);
  }

  .section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
  }

  .section-head h3,
  .all-reports-head h3 {
    margin: 0;
    font-size: 17px;
    color: #1f2a37;
  }

  .section-head small,
  .all-reports-head small {
    display: block;
    margin-top: 4px;
    color: #64748b;
    font-size: 12px;
  }

  .view-all {
    background: #f2f6ff;
    color: #2d6cdf;
    padding: 10px 14px;
    font-size: 13px;
  }

  .report-cards-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
  }

  .report-card {
    border: 1px solid #dfe7ee;
    border-radius: 14px;
    background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
    padding: 14px;
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }

  .report-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    flex-shrink: 0;
  }

  .report-card-body {
    flex: 1;
    min-width: 0;
  }

  .report-card-body h4 {
    margin: 0;
    font-size: 14px;
    color: #1f2a37;
  }

  .report-card-body p {
    margin: 6px 0 10px;
    color: #64748b;
    font-size: 12px;
  }

  .report-card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 10px;
  }

  .report-card-footer small {
    color: #64748b;
    font-size: 11px;
  }

  .status {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 4px 8px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }

  .status.ready {
    background: #e7f9ef;
    color: #216b4d;
  }

  .status.pending {
    background: #fff5e8;
    color: #a25a11;
  }

  .report-actions,
  .table-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .small-button {
    background: #edf4ff;
    color: #2d6cdf;
    padding: 6px 8px;
    font-size: 11px;
  }

  .small-button.subtle {
    background: #f8fafc;
    color: #4b5563;
  }

  .all-reports-section {
    margin-top: 22px;
    background: #fff;
    border: 1px solid #dfe7ee;
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 8px 18px rgba(85, 96, 116, 0.04);
  }

  .all-reports-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
    margin-bottom: 14px;
  }

  .download-box {
    border: 1px solid #dfe7ee;
    border-radius: 12px;
    background: #f8fbff;
    padding: 12px 14px;
    min-width: 280px;
  }

  .download-box h4 {
    margin: 0;
    font-size: 13px;
    color: #1f2a37;
  }

  .download-box p {
    margin: 6px 0 10px;
    color: #64748b;
    font-size: 12px;
  }

  .format-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .format-pills span,
  .format-chip {
    border-radius: 999px;
    background: #eaf3ff;
    color: #2d6cdf;
    font-size: 11px;
    padding: 4px 8px;
    font-weight: 700;
  }

  .report-table-wrap {
    overflow-x: auto;
  }

  .report-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .report-table th,
  .report-table td {
    border-bottom: 1px solid #edf2f7;
    text-align: left;
    padding: 12px 10px;
    vertical-align: middle;
  }

  .report-table th {
    background: #f8fafc;
    color: #4b5563;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 800;
  }

  .report-table td {
    color: #1f2a37;
  }

  .format-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  @media (max-width: 1180px) {
    .report-filter-row {
      grid-template-columns: repeat(3, minmax(120px, 1fr));
    }

    .report-cards-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 900px) {
    .report-toolbar {
      flex-direction: column;
      align-items: stretch;
    }

    .toolbar-actions {
      justify-content: space-between;
    }

    .stat-grid,
    .overview-grid,
    .report-cards-grid {
      grid-template-columns: 1fr;
    }

    .bar-row {
      grid-template-columns: 100px minmax(0, 1fr) 28px;
    }

    .all-reports-head {
      flex-direction: column;
    }
  }
`;