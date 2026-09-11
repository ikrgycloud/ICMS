import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, Modal, PageHead, Pill, Spinner } from "./kit";

export default function AcademicCoordinatorNotices() {
  const [rows, setRows] = useState<any[] | null>(null),
    [canPublish, setCanPublish] = useState(false),
    [error, setError] = useState(""),
    [selected, setSelected] = useState<any>(null),
    [show, setShow] = useState(false),
    [message, setMessage] = useState("");
  const load = () => {
    setError("");
    api
      .academicAnnouncements()
      .then((r: any) => {
        setRows(Array.isArray(r?.announcements) ? r.announcements : []);
        setCanPublish(!!r?.can_publish);
      })
      .catch((e: any) =>
        setError(e.message || "Unable to load academic notices"),
      );
  };
  useEffect(() => {
    load();
  }, []);
  if (!rows)
    return error ? (
      <div className="calendar-banner warn">{error}</div>
    ) : (
      <Spinner />
    );
  return (
    <div className="fade-in academic-notices-page">
      <PageHead
        title="Academic Notices"
        sub="Create and manage targeted academic communications."
        right={
          <div className="notices-header-actions">
            <button className="btn btn-out" onClick={load}>
              Refresh
            </button>
            {canPublish && (
              <button
                className="btn btn-crimson"
                onClick={() => setShow(true)}
              >
                Create Notice
              </button>
            )}
          </div>
        }
      />

      {message && (
        <div className="calendar-banner success notices-banner">
          {message}
        </div>
      )}

      {error && (
        <div className="calendar-banner warn notices-banner">
          {error}
        </div>
      )}

      <section className="notice-overview">
        <div>
          <span className="notice-eyebrow">ACADEMIC COMMUNICATIONS</span>
          <h2>Notice board</h2>
          <p>
            Keep students and academic groups informed with clear,
            targeted announcements.
          </p>
        </div>

        <div className="notice-overview-count">
          <strong>{rows.length}</strong>
          <span>{rows.length === 1 ? "Notice" : "Notices"}</span>
        </div>
      </section>

      <section className="notice-content">
        <div className="notice-section-head">
          <div>
            <span className="notice-eyebrow">PUBLISHED COMMUNICATIONS</span>
            <h2>Academic notices</h2>
          </div>
          <span className="notice-count-label">
            {rows.length} {rows.length === 1 ? "item" : "items"}
          </span>
        </div>

        {!rows.length ? (
          <div className="notice-empty">
            <div className="notice-empty-icon">N</div>
            <h3>No academic notices yet</h3>
            <p>
              Published academic communications will appear here.
            </p>
            {canPublish && (
              <button
                className="btn btn-crimson"
                onClick={() => setShow(true)}
              >
                Create first notice
              </button>
            )}
          </div>
        ) : (
          <div className="notice-list">
            {rows.map((item: any, index) => (
              <article
                className="notice-item"
                key={item?.id || `notice-${index}`}
              >
                <div className="notice-item-main">
                  <div className="notice-item-icon">
                    {String(item?.title || "N")
                      .trim()
                      .charAt(0)
                      .toUpperCase() || "N"}
                  </div>

                  <div className="notice-item-copy">
                    <div className="notice-item-topline">
                      <span className="notice-type">
                        Academic notice
                      </span>
                      <Pill s={String(item?.status || "Unknown")} />
                    </div>

                    <h3>{item?.title || "Untitled notice"}</h3>

                    <p>
                      {item?.body || "No message content"}
                    </p>

                    <div className="notice-meta">
                      <span>
                        <b>Audience</b>
                        {item?.audience || "Unspecified"}
                      </span>

                      {item?.program && (
                        <span>
                          <b>Program</b>
                          {item.program}
                        </span>
                      )}

                      {item?.section && (
                        <span>
                          <b>Section</b>
                          {item.section}
                        </span>
                      )}

                      <span>
                        <b>Created</b>
                        {date(item?.created_at)}
                      </span>
                    </div>
                  </div>

                  <div className="notice-item-action">
                    <button
                      className="linkish notice-details"
                      onClick={() => setSelected(item)}
                    >
                      View details →
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {selected && (
        <Modal
          title={String(selected?.title || "Academic Notice")}
          onClose={() => setSelected(null)}
        >
          <div className="notice-detail">
            <div className="notice-detail-hero">
              <div className="notice-detail-icon">
                {String(selected?.title || "N")
                  .trim()
                  .charAt(0)
                  .toUpperCase() || "N"}
              </div>

              <div>
                <span className="notice-eyebrow">
                  ACADEMIC NOTICE
                </span>
                <h3>
                  {selected?.title || "Untitled notice"}
                </h3>
                <div className="notice-detail-status">
                  <Pill
                    s={String(selected?.status || "Unknown")}
                  />
                </div>
              </div>
            </div>

            <div className="notice-detail-grid">
              <Info
                l="Audience"
                v={selected?.audience}
              />
              <Info
                l="Created by"
                v={selected?.created_by}
              />
              <Info
                l="Published"
                v={date(selected?.published_at)}
              />
              <Info
                l="Created"
                v={date(selected?.created_at)}
              />
              <Info
                l="Updated"
                v={date(selected?.updated_at)}
              />
              {selected?.program && (
                <Info l="Program" v={selected.program} />
              )}
              {selected?.section && (
                <Info l="Section" v={selected.section} />
              )}
            </div>

            <div className="notice-message">
              <span className="notice-eyebrow">MESSAGE</span>
              <p>
                {selected?.body || "No message content"}
              </p>
            </div>
          </div>
        </Modal>
      )}

      {show && (
        <NoticeModal
          onClose={() => setShow(false)}
          onSaved={() => {
            setShow(false);
            setMessage("Academic notice published.");
            load();
          }}
        />
      )}

      <style>{`
        .academic-notices-page {
          --notice-burgundy: #741f32;
          --notice-text: #30262a;
          --notice-muted: #887c81;
          --notice-line: #e8e1e3;
          --notice-soft: #faf7f8;
        }

        .notices-header-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .notices-banner {
          margin-top: 16px;
        }

        .notice-eyebrow {
          display: block;
          color: #9a858c;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: .11em;
        }

        .notice-overview {
          margin-top: 28px;
          padding: 24px 26px;
          border: 1px solid var(--notice-line);
          border-radius: 14px;
          background: #fff;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 24px;
        }

        .notice-overview h2 {
          margin: 7px 0 5px;
          color: var(--notice-text);
          font-size: 21px;
        }

        .notice-overview p {
          max-width: 650px;
          margin: 0;
          color: var(--notice-muted);
          font-size: 12px;
          line-height: 1.6;
        }

        .notice-overview-count {
          min-width: 92px;
          padding-left: 22px;
          border-left: 2px solid #e4d8dc;
          display: flex;
          flex-direction: column;
          justify-content: center;
        }

        .notice-overview-count strong {
          color: var(--notice-burgundy);
          font-size: 28px;
          line-height: 1;
        }

        .notice-overview-count span {
          margin-top: 5px;
          color: var(--notice-muted);
          font-size: 10px;
          font-weight: 700;
        }

        .notice-content {
          margin-top: 28px;
        }

        .notice-section-head {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          gap: 20px;
          margin-bottom: 14px;
        }

        .notice-section-head h2 {
          margin: 6px 0 0;
          color: var(--notice-text);
          font-size: 18px;
        }

        .notice-count-label {
          color: #9b9095;
          font-size: 11px;
        }

        .notice-list {
          display: flex;
          flex-direction: column;
          gap: 9px;
        }

        .notice-item {
          border: 1px solid var(--notice-line);
          border-radius: 11px;
          background: #fff;
          overflow: hidden;
          transition: border-color .18s ease, box-shadow .18s ease;
        }

        .notice-item:hover {
          border-color: #d6c3c9;
          box-shadow: 0 5px 18px rgba(54, 28, 36, .05);
        }

        .notice-item-main {
          display: grid;
          grid-template-columns: 42px minmax(0, 1fr) auto;
          align-items: center;
          gap: 15px;
          padding: 17px 18px;
        }

        .notice-item-icon,
        .notice-detail-icon {
          width: 40px;
          height: 40px;
          border-radius: 10px;
          background: #f7eef1;
          color: var(--notice-burgundy);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 14px;
          font-weight: 800;
        }

        .notice-item-copy {
          min-width: 0;
        }

        .notice-item-topline {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 5px;
        }

        .notice-type {
          color: #9a8e93;
          font-size: 9px;
          font-weight: 800;
          letter-spacing: .06em;
          text-transform: uppercase;
        }

        .notice-item-copy h3 {
          margin: 0;
          color: var(--notice-text);
          font-size: 14px;
          line-height: 1.35;
        }

        .notice-item-copy p {
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
          margin: 5px 0 0;
          color: #7e7277;
          font-size: 11px;
          line-height: 1.55;
        }

        .notice-meta {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 7px 18px;
          margin-top: 10px;
        }

        .notice-meta span {
          color: #665a5f;
          font-size: 10px;
        }

        .notice-meta b {
          margin-right: 5px;
          color: #a09599;
          font-size: 9px;
          font-weight: 700;
        }

        .notice-item-action {
          align-self: center;
          padding-left: 10px;
        }

        .notice-details {
          white-space: nowrap;
          font-size: 11px;
          font-weight: 800;
        }

        .notice-empty {
          padding: 58px 24px;
          border: 1px solid var(--notice-line);
          border-radius: 12px;
          background: #fff;
          text-align: center;
        }

        .notice-empty-icon {
          width: 44px;
          height: 44px;
          margin: 0 auto 12px;
          border-radius: 50%;
          background: #f7eef1;
          color: var(--notice-burgundy);
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
        }

        .notice-empty h3 {
          margin: 0;
          color: var(--notice-text);
          font-size: 15px;
        }

        .notice-empty p {
          margin: 7px 0 16px;
          color: var(--notice-muted);
          font-size: 11px;
        }

        .notice-detail {
          padding-top: 2px;
        }

        .notice-detail-hero {
          display: flex;
          align-items: center;
          gap: 13px;
          padding: 3px 0 20px;
          border-bottom: 1px solid var(--notice-line);
        }

        .notice-detail-icon {
          width: 46px;
          height: 46px;
          flex: 0 0 46px;
        }

        .notice-detail-hero h3 {
          margin: 6px 0 7px;
          color: var(--notice-text);
          font-size: 17px;
        }

        .notice-detail-status {
          display: flex;
          align-items: center;
        }

        .notice-detail-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 9px;
          margin-top: 18px;
        }

        .notice-message {
          margin-top: 18px;
          padding: 16px;
          border: 1px solid var(--notice-line);
          border-radius: 9px;
          background: var(--notice-soft);
        }

        .notice-message p {
          margin: 9px 0 0;
          color: #4b3f44;
          font-size: 12px;
          line-height: 1.7;
          white-space: pre-wrap;
        }

        @media (max-width: 700px) {
          .notice-overview {
            align-items: flex-start;
            flex-direction: column;
            padding: 19px;
          }

          .notice-overview-count {
            width: 100%;
            padding: 11px 0 0;
            border-left: 0;
            border-top: 1px solid var(--notice-line);
          }

          .notice-item-main {
            grid-template-columns: 36px minmax(0, 1fr);
            padding: 14px;
          }

          .notice-item-icon {
            width: 36px;
            height: 36px;
          }

          .notice-item-action {
            grid-column: 2;
            padding: 0;
          }

          .notice-meta {
            gap: 6px 12px;
          }

          .notice-detail-grid {
            grid-template-columns: 1fr;
          }

          .notices-header-actions {
            flex-wrap: wrap;
          }
        }
      `}</style>
    </div>
  );
}

function date(v?: string) {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}
function Info({ l, v }: { l: string; v: any }) {
  return (
    <div className="snap">
      <span>{l}</span>
      <b>{String(v || "—")}</b>
    </div>
  );
}
function NoticeModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
      title: "",
      body: "",
      audience: "all_students",
      department_id: "",
      program_id: "",
      section_id: "",
      expires_at: "",
    }),
    [programs, setPrograms] = useState<any[]>([]),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false);
  useEffect(() => {
    api
      .academicPrograms()
      .then((r: any) =>
        setPrograms(Array.isArray(r?.programs) ? r.programs : []),
      )
      .catch(() => setPrograms([]));
    return undefined;
  }, []);
  async function submit() {
    if (saving) return;
    try {
      if (!f.title.trim() || !f.body.trim())
        throw Error("Title and message are required");
      setSaving(true);
      setError("");
      await api.publishAnnouncement(f);
      onSaved();
    } catch (e: any) {
      setError(e.message || "Unable to publish notice");
      setSaving(false);
    }
  }
  return (
    <Modal
      title="Publish academic notice"
      onClose={onClose}
      footer={
        <button className="btn btn-crimson" disabled={saving} onClick={submit}>
          {saving ? "Publishing..." : "Publish"}
        </button>
      }
    >
      <div className="form-row">
        <label>Title</label>
        <input
          className="inp"
          value={f.title}
          onChange={(e) => setF({ ...f, title: e.target.value })}
        />
      </div>
      <div className="form-row">
        <label>Message</label>
        <textarea
          className="inp"
          value={f.body}
          onChange={(e) => setF({ ...f, body: e.target.value })}
        />
      </div>
      <div className="form-row">
        <label>Audience</label>
        <select
          className="select"
          value={f.audience}
          onChange={(e) => setF({ ...f, audience: e.target.value })}
        >
          <option value="all_students">All students</option>
          <option value="department">Department</option>
          <option value="program">Program</option>
          <option value="section">Section</option>
        </select>
      </div>
      {f.audience === "program" && (
        <div className="form-row">
          <label>Program</label>
          <select
            className="select"
            value={f.program_id}
            onChange={(e) => setF({ ...f, program_id: e.target.value })}
          >
            <option value="">Select program</option>
            {programs.map((p) => (
              <option value={p.id} key={p.id}>
                {p.code} · {p.name}
              </option>
            ))}
          </select>
        </div>
      )}
      {error && <div className="calendar-banner warn">{error}</div>}
    </Modal>
  );
}
