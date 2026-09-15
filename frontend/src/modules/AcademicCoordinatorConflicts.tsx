import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Empty, PageHead, Pill, Spinner } from "./kit";

const labels: Record<string, string> = {
  faculty_overlap: "Faculty overlap",
  room_conflict: "Room conflict",
  lab_conflict: "Lab conflict",
  student_cohort_overlap: "Student/cohort overlap",
};

const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const dash = (value: any) =>
  value === undefined || value === null || value === "" ? "-" : value;

export default function AcademicCoordinatorConflicts({
  onNavigate,
}: {
  onNavigate?: (v: string) => void;
}) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [f, setF] = useState<any>({});
  const [detail, setDetail] = useState<any>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const set = (key: string, value: string) => {
    setF((current: any) => ({
      ...current,
      [key]: value,
    }));
  };

  const clearFilters = () => setF({});

  const hasFilters = Object.values(f).some(
    (value: any) => value !== undefined && value !== null && value !== "",
  );

  async function load() {
    try {
      setError("");
      setData(await api.academicConflicts(f));
    } catch (e: any) {
      setError(e.message || "Unable to load conflicts");
    }
  }

  useEffect(() => {
    load();
  }, [
    f.academic_year,
    f.student_year,
    f.program_id,
    f.department_id,
    f.conflict_type,
    f.severity,
    f.resolved,
  ]);

  const summary = data?.summary || {};
  const conflicts = data?.conflicts || [];

  const activeCount = Number(summary.total_active ?? 0);
  const criticalCount = Number(summary.critical ?? 0);
  const highCount = Number(summary.high ?? 0);
  const resolvedCount = Number(summary.resolved ?? 0);

  const groupedCounts = useMemo(
    () => ({
      faculty: Number(summary.faculty ?? 0),
      room: Number(summary.room ?? 0),
      student: Number(summary.student ?? 0),
      lab: Number(summary.lab ?? 0),
    }),
    [summary],
  );

  const selectedFilterLabel = f.resolved === "true"
    ? "Resolved"
    : f.resolved === "false"
      ? "Active"
      : "All conflicts";

  if (!data && !error) {
    return <Spinner />;
  }

  return (
    <div className="fade-in conflict-page">
      <PageHead
        title="Conflict Center"
        sub="Review timetable conflicts across programs, departments, faculty, rooms and student cohorts."
        right={
          <button className="btn btn-out" onClick={load}>
            Refresh
          </button>
        }
      />

      {error && (
        <div className="calendar-banner warn conflict-alert">
          {error}
        </div>
      )}

      {/* STATUS OVERVIEW */}
      <section className="conflict-overview">
        <div className="overview-copy">
          <span className="eyebrow">ACADEMIC OPERATIONS</span>
          <h2>Conflict overview</h2>
          <p>
            {selectedFilterLabel} · {conflicts.length} matching{" "}
            {conflicts.length === 1 ? "record" : "records"}
          </p>
        </div>

        <div className="overview-stats">
          <div className="overview-stat danger">
            <strong>{activeCount}</strong>
            <span>Active</span>
          </div>
          <div className="overview-stat critical">
            <strong>{criticalCount}</strong>
            <span>Critical</span>
          </div>
          <div className="overview-stat high">
            <strong>{highCount}</strong>
            <span>High</span>
          </div>
          <div className="overview-stat resolved">
            <strong>{resolvedCount}</strong>
            <span>Resolved</span>
          </div>
        </div>
      </section>

      {/* FILTERS */}
      <section className="conflict-filters">
        <div className="filter-heading">
          <div>
            <span className="eyebrow">FILTERS</span>
            <h3>Find conflicts</h3>
          </div>

          <div className="filter-actions">
            {hasFilters && <button className="clear-filter" onClick={clearFilters}>Clear all</button>}
            <button className="clear-filter" onClick={() => setFiltersOpen((open) => !open)}>{filtersOpen ? "Hide filters" : "Filters"}</button>
          </div>
        </div>

        {filtersOpen && <>
        <div className="filter-grid">
          <label className="filter-field">
            <span>Academic year</span>
            <input
              className="inp"
              placeholder="e.g. 2026-27"
              value={f.academic_year || ""}
              onChange={(e) => set("academic_year", e.target.value)}
            />
          </label>

          <label className="filter-field">
            <span>Student year</span>
            <select
              className="select"
              value={f.student_year || ""}
              onChange={(e) => set("student_year", e.target.value)}
            >
              <option value="">All years</option>
              {[1, 2, 3, 4].map((y) => (
                <option key={y} value={y}>
                  {y === 1 ? "1st" : y === 2 ? "2nd" : y === 3 ? "3rd" : "4th"} Year
                </option>
              ))}
            </select>
          </label>

          <label className="filter-field">
            <span>Program / branch</span>
            <input
              className="inp"
              placeholder="Program ID"
              value={f.program_id || ""}
              onChange={(e) => set("program_id", e.target.value)}
            />
          </label>

          <label className="filter-field">
            <span>Department</span>
            <input
              className="inp"
              placeholder="Department ID"
              value={f.department_id || ""}
              onChange={(e) => set("department_id", e.target.value)}
            />
          </label>

          <label className="filter-field">
            <span>Conflict type</span>
            <select
              className="select"
              value={f.conflict_type || ""}
              onChange={(e) => set("conflict_type", e.target.value)}
            >
              <option value="">All types</option>
              {Object.entries(labels).map(([key, value]) => (
                <option key={key} value={key}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <label className="filter-field">
            <span>Severity</span>
            <select
              className="select"
              value={f.severity || ""}
              onChange={(e) => set("severity", e.target.value)}
            >
              <option value="">All severity</option>
              {["Critical", "High", "Medium", "Low"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="status-filter">
          <span>Status</span>
          <div className="status-options">
            {[
              ["", "All"],
              ["false", "Active"],
              ["true", "Resolved"],
            ].map(([value, text]) => (
              <button
                type="button"
                key={value}
                className={`status-option ${
                  (f.resolved || "") === value ? "active" : ""
                }`}
                onClick={() => set("resolved", value)}
              >
                {text}
              </button>
            ))}
          </div>
        </div>
        </>}
      </section>

      {/* CONFLICT TYPE SUMMARY */}
      <section className="type-summary">
        <div className="type-summary-head">
          <div>
            <span className="eyebrow">BREAKDOWN</span>
            <h3>Conflict categories</h3>
          </div>
          <span className="type-summary-note">
            Campus-wide
          </span>
        </div>

        <div className="type-summary-grid">
          <TypeStat
            label="Faculty"
            value={groupedCounts.faculty}
            text="Faculty overlap"
          />
          <TypeStat
            label="Room"
            value={groupedCounts.room}
            text="Room conflict"
          />
          <TypeStat
            label="Student"
            value={groupedCounts.student}
            text="Student / cohort"
          />
          <TypeStat
            label="Lab"
            value={groupedCounts.lab}
            text="Lab conflict"
          />
        </div>
      </section>

      {/* CONFLICT LIST */}
      <section className="conflict-list-section">
        <div className="list-header">
          <div>
            <span className="eyebrow">CONFLICT REGISTER</span>
            <h2>
              {conflicts.length}{" "}
              {conflicts.length === 1 ? "conflict" : "conflicts"}
            </h2>
            <p>Review the affected timetable records and take action.</p>
          </div>
        </div>

        {!conflicts.length ? (
          <div className="conflict-empty">
            <div className="empty-mark">✓</div>
            <h3>No conflicts found</h3>
            <p>
              No timetable conflicts match the selected filters.
            </p>
          </div>
        ) : (
          <div className="conflict-cards">
            {conflicts.map((item: any) => (
              <ConflictCard
                key={item.id}
                item={item}
                onDetails={() => setDetail(item)}
              />
            ))}
          </div>
        )}
      </section>

      {/* DETAILS */}
      {detail && (
        <div
          className="conflict-modal-bg"
          onClick={() => setDetail(null)}
        >
          <div
            className="conflict-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="conflict-modal-header">
              <div>
                <span className="eyebrow">CONFLICT DETAILS</span>
                <h2>{labels[detail.type] || detail.type}</h2>
                <p>{detail.id}</p>
              </div>

              <button
                className="close-x"
                onClick={() => setDetail(null)}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <div className="conflict-modal-body">
              <div className="detail-status-row">
                <Pill s={detail.severity} />
                <Pill s={detail.status} />
              </div>

              <div className="detail-grid">
                <Detail
                  label="Academic year"
                  value={dash(detail.academic_year)}
                />
                <Detail
                  label="Student year"
                  value={dash(detail.student_year)}
                />
                <Detail
                  label="Program"
                  value={dash(detail.program_name || detail.program_id)}
                />
                <Detail
                  label="Department"
                  value={dash(
                    detail.department_name || detail.department_id,
                  )}
                />
              </div>

              <DetailSection title="Schedule">
                <div className="schedule-highlight">
                  <strong>
                    {dash(days[detail.day_of_week])}
                  </strong>
                  <span>
                    {dash(detail.start_time)} –{" "}
                    {dash(detail.end_time)}
                  </span>
                </div>
              </DetailSection>

              <div className="affected-grid">
                <AffectedBlock
                  title="Affected timetable"
                  item={detail.left}
                />
                <AffectedBlock
                  title="Conflicting timetable"
                  item={detail.right}
                />
              </div>

              <DetailSection title="Resolution">
                <div className="resolution-info">
                  <Detail
                    label="Detected"
                    value={
                      detail.detected_at
                        ? new Date(
                            detail.detected_at,
                          ).toLocaleString()
                        : "-"
                    }
                  />
                  <Detail
                    label="Resolution note"
                    value={dash(detail.resolution_note)}
                  />
                  <Detail
                    label="Resolved by"
                    value={dash(detail.resolved_by)}
                  />
                  <Detail
                    label="Resolved at"
                    value={
                      detail.resolved_at
                        ? new Date(
                            detail.resolved_at,
                          ).toLocaleString()
                        : "-"
                    }
                  />
                </div>
              </DetailSection>

              <div className="detail-actions">
                {detail.status !== "Resolved" && data.can_manage && (
                  <button
                    className="btn btn-crimson"
                    onClick={async () => {
                      const note =
                        window.prompt("Resolution note:") || "";

                      if (!note) return;

                      try {
                        await api.resolveAcademicConflict(
                          detail.id,
                          note,
                        );
                        setDetail(null);
                        load();
                      } catch (e: any) {
                        setError(
                          e.message ||
                            "Unable to resolve conflict",
                        );
                      }
                    }}
                  >
                    Resolve conflict
                  </button>
                )}

                <button
                  className="btn btn-out"
                  onClick={() =>
                    onNavigate?.("coordinator_sections")
                  }
                >
                  Open affected sections
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .conflict-page {
          --burgundy: #741f32;
          --burgundy-dark: #581526;
          --text: #30262a;
          --muted: #887c81;
          --line: #e9e2e4;
          --soft: #faf7f8;
        }

        .conflict-alert {
          margin-top: 18px;
        }

        .eyebrow {
          display: block;
          color: #9a858c;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 0.12em;
          line-height: 1.2;
        }

        .conflict-overview {
          margin-top: 26px;
          padding: 24px 26px;
          border: 1px solid var(--line);
          border-radius: 14px;
          background: #fff;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 28px;
        }

        .overview-copy h2 {
          margin: 7px 0 4px;
          color: var(--text);
          font-size: 20px;
        }

        .overview-copy p {
          margin: 0;
          color: var(--muted);
          font-size: 12px;
        }

        .overview-stats {
          display: grid;
          grid-template-columns: repeat(4, 100px);
          gap: 8px;
        }

        .overview-stat {
          min-height: 70px;
          padding: 12px;
          border-left: 2px solid #ddd;
          display: flex;
          flex-direction: column;
          justify-content: center;
        }

        .overview-stat strong {
          color: var(--text);
          font-size: 22px;
          line-height: 1;
        }

        .overview-stat span {
          margin-top: 6px;
          color: var(--muted);
          font-size: 10px;
          font-weight: 600;
        }

        .overview-stat.danger {
          border-color: var(--burgundy);
        }

        .overview-stat.critical {
          border-color: #a33a45;
        }

        .overview-stat.high {
          border-color: #b46c38;
        }

        .overview-stat.resolved {
          border-color: #65866e;
        }

        .conflict-filters {
          margin-top: 20px;
          padding: 20px 22px 18px;
          border: 1px solid var(--line);
          border-radius: 12px;
          background: #fff;
        }

        .filter-heading,
        .type-summary-head,
        .list-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 20px;
        }

        .filter-heading h3,
        .type-summary-head h3 {
          margin: 6px 0 0;
          color: var(--text);
          font-size: 15px;
        }

        .clear-filter {
          border: 0;
          background: transparent;
          color: var(--burgundy);
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
          padding: 4px 0;
        }

        .filter-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 16px;
          margin-top: 18px;
        }

        .filter-field {
          display: flex;
          flex-direction: column;
          gap: 7px;
        }

        .filter-field > span,
        .status-filter > span {
          color: #6f6368;
          font-size: 11px;
          font-weight: 700;
        }

        .filter-field .inp,
        .filter-field .select {
          width: 100%;
          box-sizing: border-box;
          min-height: 40px;
        }

        .status-filter {
          margin-top: 18px;
          padding-top: 16px;
          border-top: 1px solid #f0ebed;
          display: flex;
          align-items: center;
          gap: 18px;
        }

        .status-options {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
        }

        .status-option {
          border: 1px solid #e4dcdf;
          background: #fff;
          color: #75696e;
          border-radius: 7px;
          padding: 7px 13px;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
        }

        .status-option:hover {
          border-color: #c9b7bd;
          color: var(--burgundy);
        }

        .status-option.active {
          border-color: var(--burgundy);
          background: #f7eef1;
          color: var(--burgundy);
        }

        .type-summary {
          margin-top: 20px;
          padding: 20px 22px;
          border: 1px solid var(--line);
          border-radius: 12px;
          background: #fff;
        }

        .type-summary-note {
          color: #9a8e93;
          font-size: 11px;
        }

        .type-summary-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 10px;
          margin-top: 16px;
        }

        .type-stat {
          min-height: 74px;
          padding: 13px 15px;
          background: var(--soft);
          border-radius: 9px;
          border: 1px solid #eee7e9;
        }

        .type-stat-label {
          display: block;
          color: #9a8e93;
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .type-stat-value {
          display: inline-block;
          margin-top: 7px;
          color: var(--text);
          font-size: 20px;
          font-weight: 800;
        }

        .type-stat-text {
          margin-left: 7px;
          color: #7e7277;
          font-size: 10px;
        }

        .conflict-list-section {
          margin-top: 28px;
        }

        .list-header h2 {
          margin: 6px 0 3px;
          color: var(--text);
          font-size: 19px;
        }

        .list-header p {
          margin: 0;
          color: var(--muted);
          font-size: 12px;
        }

        .conflict-cards {
          display: flex;
          flex-direction: column;
          gap: 10px;
          margin-top: 16px;
        }

        .conflict-card {
          border: 1px solid var(--line);
          border-radius: 11px;
          background: #fff;
          overflow: hidden;
          transition: box-shadow .18s ease, border-color .18s ease;
        }

        .conflict-card:hover {
          border-color: #d8c7cc;
          box-shadow: 0 5px 18px rgba(52, 30, 36, .05);
        }

        .conflict-card-main {
          display: grid;
          grid-template-columns: 210px minmax(160px, 1fr) minmax(180px, 1fr) 150px;
          gap: 18px;
          align-items: center;
          padding: 17px 18px;
        }

        .conflict-type {
          display: flex;
          align-items: center;
          gap: 11px;
          min-width: 0;
        }

        .conflict-type-mark {
          width: 34px;
          height: 34px;
          flex: 0 0 34px;
          border-radius: 9px;
          background: #f7eef1;
          color: var(--burgundy);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 13px;
          font-weight: 800;
        }

        .conflict-type strong {
          display: block;
          color: var(--text);
          font-size: 12px;
        }

        .conflict-type small {
          display: block;
          margin-top: 4px;
          color: #a09599;
          font-size: 9px;
        }

        .conflict-card-label {
          display: block;
          margin-bottom: 5px;
          color: #9a8e93;
          font-size: 9px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: .04em;
        }

        .conflict-card-value {
          color: #4a3e42;
          font-size: 11px;
          line-height: 1.45;
        }

        .conflict-card-value strong {
          color: #34282c;
        }

        .conflict-card-status {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 7px;
        }

        .details-button {
          border: 0;
          background: transparent;
          color: var(--burgundy);
          font-size: 11px;
          font-weight: 800;
          cursor: pointer;
          padding: 3px 0;
        }

        .details-button:hover {
          text-decoration: underline;
        }

        .conflict-empty {
          margin-top: 16px;
          padding: 55px 20px;
          border: 1px solid var(--line);
          border-radius: 12px;
          background: #fff;
          text-align: center;
        }

        .empty-mark {
          width: 42px;
          height: 42px;
          margin: 0 auto 12px;
          border-radius: 50%;
          background: #edf5ef;
          color: #50715a;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
        }

        .conflict-empty h3 {
          margin: 0;
          color: var(--text);
          font-size: 15px;
        }

        .conflict-empty p {
          margin: 7px 0 0;
          color: var(--muted);
          font-size: 11px;
        }

        .conflict-modal-bg {
          position: fixed;
          inset: 0;
          z-index: 1000;
          background: rgba(27, 18, 21, .42);
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
        }

        .conflict-modal {
          width: min(820px, 100%);
          max-height: calc(100vh - 48px);
          overflow-y: auto;
          border-radius: 14px;
          background: #fff;
          box-shadow: 0 22px 60px rgba(25, 13, 17, .22);
        }

        .conflict-modal-header {
          padding: 23px 25px 19px;
          border-bottom: 1px solid var(--line);
          display: flex;
          justify-content: space-between;
          gap: 20px;
        }

        .conflict-modal-header h2 {
          margin: 6px 0 4px;
          color: var(--text);
          font-size: 19px;
        }

        .conflict-modal-header p {
          margin: 0;
          color: #a09599;
          font-size: 10px;
        }

        .conflict-modal-body {
          padding: 22px 25px 25px;
        }

        .detail-status-row {
          display: flex;
          gap: 7px;
          margin-bottom: 20px;
        }

        .detail-grid,
        .resolution-info {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
        }

        .detail-item {
          padding: 12px 14px;
          border: 1px solid #eee7e9;
          border-radius: 8px;
          background: #fcfafb;
        }

        .detail-item span {
          display: block;
          color: #988c91;
          font-size: 9px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: .04em;
        }

        .detail-item strong {
          display: block;
          margin-top: 5px;
          color: #3d3235;
          font-size: 11px;
          line-height: 1.4;
        }

        .detail-section {
          margin-top: 22px;
        }

        .detail-section-title {
          margin: 0 0 9px;
          color: #56494e;
          font-size: 12px;
          font-weight: 800;
        }

        .schedule-highlight {
          padding: 13px 15px;
          border-radius: 8px;
          background: #f8f1f3;
          border-left: 3px solid var(--burgundy);
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .schedule-highlight strong {
          color: var(--burgundy);
          font-size: 12px;
        }

        .schedule-highlight span {
          color: #66595e;
          font-size: 11px;
        }

        .affected-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
          margin-top: 22px;
        }

        .affected-block {
          padding: 15px;
          border: 1px solid var(--line);
          border-radius: 9px;
        }

        .affected-block h4 {
          margin: 0 0 12px;
          color: var(--burgundy);
          font-size: 11px;
        }

        .affected-line {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          padding: 7px 0;
          border-bottom: 1px solid #f1ecee;
        }

        .affected-line:last-child {
          border-bottom: 0;
          padding-bottom: 0;
        }

        .affected-line span {
          color: #9a8e93;
          font-size: 9px;
        }

        .affected-line b {
          color: #43373b;
          font-size: 10px;
          text-align: right;
        }

        .detail-actions {
          display: flex;
          align-items: center;
          gap: 9px;
          margin-top: 24px;
          padding-top: 18px;
          border-top: 1px solid var(--line);
        }

        @media (max-width: 1050px) {
          .overview-stats {
            grid-template-columns: repeat(4, 85px);
          }

          .conflict-card-main {
            grid-template-columns: 1fr 1fr;
          }

          .conflict-card-status {
            align-items: flex-start;
          }
        }

        @media (max-width: 800px) {
          .conflict-overview {
            align-items: flex-start;
            flex-direction: column;
          }

          .overview-stats {
            width: 100%;
            grid-template-columns: repeat(4, 1fr);
          }

          .filter-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }

          .type-summary-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 600px) {
          .conflict-overview {
            padding: 18px;
          }

          .overview-stats {
            grid-template-columns: repeat(2, 1fr);
          }

          .filter-grid,
          .detail-grid,
          .resolution-info,
          .affected-grid {
            grid-template-columns: 1fr;
          }

          .status-filter {
            align-items: flex-start;
            flex-direction: column;
            gap: 9px;
          }

          .type-summary-grid {
            grid-template-columns: 1fr 1fr;
          }

          .conflict-card-main {
            grid-template-columns: 1fr;
            gap: 13px;
          }

          .conflict-card-status {
            align-items: flex-start;
          }

          .conflict-modal-bg {
            padding: 10px;
          }

          .conflict-modal-header,
          .conflict-modal-body {
            padding-left: 18px;
            padding-right: 18px;
          }

          .detail-actions {
            flex-direction: column;
            align-items: stretch;
          }

          .detail-actions .btn {
            width: 100%;
          }
        }
      `}</style>
    </div>
  );
}

function TypeStat({
  label,
  value,
  text,
}: {
  label: string;
  value: number;
  text: string;
}) {
  return (
    <div className="type-stat">
      <span className="type-stat-label">{label}</span>
      <span className="type-stat-value">{value}</span>
      <span className="type-stat-text">{text}</span>
    </div>
  );
}

function ConflictCard({
  item,
  onDetails,
}: {
  item: any;
  onDetails: () => void;
}) {
  const type = labels[item.type] || item.type || "Conflict";
  const left = item.left || {};
  const right = item.right || {};

  return (
    <article className="conflict-card">
      <div className="conflict-card-main">
        <div className="conflict-type">
          <div className="conflict-type-mark">!</div>

          <div>
            <strong>{type}</strong>
            <small>{item.id}</small>
          </div>
        </div>

        <div>
          <span className="conflict-card-label">
            Affected timetable
          </span>

          <div className="conflict-card-value">
            <strong>
              {dash(left.course)}
            </strong>{" "}
            · Section {dash(left.section)}
            <br />
            {dash(left.faculty)} · {dash(left.room)}
          </div>
        </div>

        <div>
          <span className="conflict-card-label">
            Conflicting timetable
          </span>

          <div className="conflict-card-value">
            <strong>
              {dash(right.course)}
            </strong>{" "}
            · Section {dash(right.section)}
            <br />
            {dash(right.faculty)} · {dash(right.room)}
          </div>
        </div>

        <div className="conflict-card-status">
          <div>
            <Pill s={item.severity} />
            <span style={{ marginLeft: 6 }}>
              <Pill s={item.status} />
            </span>
          </div>

          <button
            className="details-button"
            onClick={onDetails}
          >
            View details →
          </button>
        </div>
      </div>

      <div
        style={{
          borderTop: "1px solid #f0ebed",
          padding: "9px 18px",
          display: "flex",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <span style={{ color: "#94888d", fontSize: 10 }}>
          {dash(item.academic_year)} · Year {dash(item.student_year)} ·{" "}
          {dash(item.program_name || item.program_id)}
        </span>

        <span style={{ color: "#766a70", fontSize: 10 }}>
          {dash(days[item.day_of_week])} · {dash(item.start_time)}–
          {dash(item.end_time)}
        </span>
      </div>
    </article>
  );
}

function Detail({
  label,
  value,
}: {
  label: string;
  value: any;
}) {
  return (
    <div className="detail-item">
      <span>{label}</span>
      <strong>{String(value || "-")}</strong>
    </div>
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
    <section className="detail-section">
      <h3 className="detail-section-title">{title}</h3>
      {children}
    </section>
  );
}

function AffectedBlock({
  title,
  item,
}: {
  title: string;
  item: any;
}) {
  const value = item || {};

  return (
    <div className="affected-block">
      <h4>{title}</h4>

      <div className="affected-line">
        <span>Course</span>
        <b>
          {dash(value.course)} · {dash(value.course_name)}
        </b>
      </div>

      <div className="affected-line">
        <span>Section</span>
        <b>{dash(value.section)}</b>
      </div>

      <div className="affected-line">
        <span>Faculty</span>
        <b>{dash(value.faculty)}</b>
      </div>

      <div className="affected-line">
        <span>Room</span>
        <b>{dash(value.room)}</b>
      </div>
    </div>
  );
}
