import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Spinner, LEVEL_COLORS } from "./ui";

const LEVEL_NAMES: Record<number, string> = {
  1: "Governance & apex",
  2: "Executive leadership",
  3: "Campus leadership",
  4: "Institution heads",
  5: "Deputy / associate",
  6: "Academic units",
  7: "Administrative units",
  8: "Support & operations",
};
const PRINCIPAL_LEVEL_NAMES: Record<number, string> = {
  1: "Governance & Apex",
  2: "Executive Leadership",
  3: "Campus Leadership",
  4: "Institution Heads",
  5: "Deputy / Associate",
  6: "Academic Units",
  7: "Administrative Units",
  8: "Support & Operations",
};

export default function Directory({ user }: { user?: any }) {
  const [offices, setOffices] = useState<any[]>([]),
    [q, setQ] = useState(""),
    [level, setLevel] = useState("ALL"),
    [scope, setScope] = useState("ALL"),
    [selected, setSelected] = useState<any>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  async function load() {
    setLoading(true);
    setError("");
    try {
      setOffices(await api.offices());
    } catch (e: any) {
      setError(e.message || "Unable to load the office directory.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  const scopes = useMemo(
    () =>
      Array.from(
        new Set(offices.map((o) => o.scope).filter(Boolean)),
      ).sort() as string[],
    [offices],
  );
  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return offices.filter(
      (o) =>
        (level === "ALL" || String(o.level) === level) &&
        (scope === "ALL" || o.scope === scope) &&
        (!term ||
          [o.name, o.purpose, o.scope, o.reports_to, ...(o.modules || [])]
            .join(" ")
            .toLowerCase()
            .includes(term)),
    );
  }, [offices, q, level, scope]);
  const byLevel = useMemo(
    () =>
      filtered.reduce((all: Record<number, any[]>, o) => {
        (all[o.level] ||= []).push(o);
        return all;
      }, {}),
    [filtered],
  );
  if (loading) return <Spinner />;
  // Principal and Campus Head use the immutable institutional catalogue. It
  // deliberately contains office definitions only, never people or campus HR
  // data, and the detail modal is read-only.
  if (user?.office_n === 3 || user?.office_n === 4) return <PrincipalDirectory offices={offices} />;
  return (
    <div className="fade-in directory-page">
      <div className="page-head directory-head">
        <div>
          <h1>Institution Directory</h1>
          <p>
            Find the right office, understand its services, and follow the
            appropriate reporting path.
          </p>
        </div>
        <span className="directory-status">
          <i />
          Directory verified
        </span>
      </div>
      {error && (
        <div className="calendar-banner warn">
          {error}{" "}
          <button className="btn btn-sm btn-out" onClick={load}>
            Retry
          </button>
        </div>
      )}
      <div className="directory-summary">
        <Metric
          n={offices.length}
          label="Offices"
          sub={`Across ${new Set(offices.map((o) => o.level)).size} authority levels`}
        />
        <Metric
          n={offices.reduce((a, o) => a + Number(o.roles || 0), 0)}
          label="Internal roles"
          sub="Defined in the directory"
        />
        <Metric
          n={scopes.length}
          label="Operating scopes"
          sub="Institutional service areas"
        />
        <Metric
          n={filtered.length}
          label="Visible results"
          sub="Matching current filters"
          accent
        />
      </div>
      <div className="directory-toolbar">
        <label className="directory-search">
          <span>Search directory</span>
          <input
            placeholder="Office, service, module, scope, or reporting line…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search directory"
          />
        </label>
        <label className="directory-level">
          <span>Authority level</span>
          <select value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="ALL">All levels</option>
            {Object.entries(LEVEL_NAMES).map(([id, name]) => (
              <option value={id} key={id}>
                L{id} · {name}
              </option>
            ))}
          </select>
        </label>
        <label className="directory-level">
          <span>Scope</span>
          <select value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="ALL">All scopes</option>
            {scopes.map((x) => (
              <option value={x} key={x}>
                {x}
              </option>
            ))}
          </select>
        </label>
        {(q || level !== "ALL" || scope !== "ALL") && (
          <button
            className="btn btn-out directory-clear"
            onClick={() => {
              setQ("");
              setLevel("ALL");
              setScope("ALL");
            }}
          >
            Clear
          </button>
        )}
      </div>
      {!filtered.length ? (
        <div className="directory-empty">
          <b>No matching offices</b>
          <span>Try another service, scope, or authority-level filter.</span>
        </div>
      ) : (
        Object.keys(byLevel)
          .map(Number)
          .sort((a, b) => a - b)
          .map((lvl) => (
            <section className="directory-level-group" key={lvl}>
              <div className="directory-level-heading">
                <span
                  className="lvl-badge"
                  style={{ background: LEVEL_COLORS[lvl] }}
                >
                  L{lvl}
                </span>
                <div>
                  <h2>{LEVEL_NAMES[lvl]}</h2>
                  <small>Authority level {lvl} of 8</small>
                </div>
                <span className="hint">{byLevel[lvl].length} offices</span>
              </div>
              <div className="office-grid">
                {byLevel[lvl].map((o) => (
                  <button
                    className="office-card"
                    key={o.n}
                    onClick={() => setSelected(o)}
                  >
                    <div className="office-card-top">
                      <span
                        className="oc-n"
                        style={{ background: LEVEL_COLORS[lvl] }}
                      >
                        {o.n}
                      </span>
                      <span className="oc-roles">{o.roles} roles</span>
                    </div>
                    <div className="oc-name">{o.name}</div>
                    <div className="oc-purpose">
                      {o.purpose || "Service profile pending"}
                    </div>
                    <small className="office-scope">
                      {o.scope || "Institution scope"}
                    </small>
                  </button>
                ))}
              </div>
            </section>
          ))
      )}
      {selected && (
        <OfficeDrawer
          office={selected}
          offices={offices}
          onClose={() => setSelected(null)}
          onSelect={setSelected}
        />
      )}
    </div>
  );
}

function PrincipalDirectory({ offices }: { offices: any[] }) {
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState<any>(null)
  const filtered = offices.filter(office => office.name.toLowerCase().includes(q.toLowerCase()) || (office.purpose || '').toLowerCase().includes(q.toLowerCase()))
  const byLevel: Record<number, any[]> = {}
  filtered.forEach(office => { (byLevel[office.level] = byLevel[office.level] || []).push(office) })
  return <div className="fade-in directory-page principal-directory">
    <div className="page-head"><h1>Office Directory</h1><p>All 40 offices across 8 authority levels, {offices.reduce((total, office) => total + office.roles, 0)} internal roles. Each office reports upward per the org chart.</p></div>
    <div className="directory-search"><span aria-hidden="true">⌕</span><input className="inp" placeholder="Search offices..." value={q} onChange={event => setQ(event.target.value)} /></div>
    <div className="directory-levels">{Object.keys(byLevel).map(Number).sort((a, b) => a - b).map(level => { const rows = byLevel[level]; const roles = rows.reduce((total, row) => total + row.roles, 0); return <section className="directory-level" key={level}><header className="directory-level-head"><span className="directory-level-badge" style={{ background: '#8f1736' }}>L{level}</span><div><h2>{PRINCIPAL_LEVEL_NAMES[level]}</h2><p>{rows.length} {rows.length === 1 ? 'Office' : 'Offices'} · {roles} {roles === 1 ? 'Role' : 'Roles'}</p></div></header><div className="directory-office-grid">{rows.map(office => <button className="directory-office-card" type="button" key={office.n} onClick={() => setSelected(office)}><div className="directory-office-top"><span className="directory-office-number">Office {office.n}</span><span className="directory-role-count">{office.roles} {office.roles === 1 ? 'role' : 'roles'}</span></div><strong>{office.name}</strong><p>{office.purpose}</p><span className="directory-office-level">{PRINCIPAL_LEVEL_NAMES[level]}</span></button>)}</div></section>})}</div>
    {!filtered.length && <div className="principal-empty">No offices match your search.</div>}
    {selected && <PrincipalOfficeModal n={selected.n} onClose={() => setSelected(null)} />}
  </div>
}

function PrincipalOfficeModal({ n, onClose }: { n: number; onClose: () => void }) {
  const [office, setOffice] = useState<any>(null)
  useEffect(() => { api.office(n).then(setOffice).catch(() => {}) }, [n])
  return <div className="modal-bg" onClick={onClose}><div className="modal principal-directory-modal" onClick={event => event.stopPropagation()}>{!office ? <div style={{ padding: 50 }}><Spinner /></div> : <><div className="modal-h"><div><div className="directory-modal-title"><span className="lvl-badge" style={{ background: '#8f1736' }}>L{office.level}</span><h3>{office.name}</h3></div><p className="directory-modal-purpose">{office.purpose}</p></div><button className="modal-x" onClick={onClose} aria-label="Close office details">×</button></div><div className="modal-b directory-modal-body"><PrincipalSection title={`Internal roles · ${office.internal_roles.length}`}><div className="directory-role-chips">{office.internal_roles.map((role: string) => <span className="tag" key={role}>{role}</span>)}</div></PrincipalSection><PrincipalSection title="Functionalities"><ul className="bullet-list">{office.functionalities.map((item: string) => <li key={item}>{item}</li>)}</ul></PrincipalSection><PrincipalSection title="Workflows"><ul className="bullet-list">{office.workflows.map((item: string) => <li key={item}>{item}</li>)}</ul></PrincipalSection><PrincipalSection title="Modules"><div className="directory-module-chips">{office.modules.map((item: string) => <span className="tag" key={item}>{item}</span>)}</div></PrincipalSection><div className="directory-modal-meta"><PrincipalSection title="Scope"><span className="mono">{office.scope}</span></PrincipalSection><PrincipalSection title="Reports to"><span>{office.reports_to}</span></PrincipalSection></div></div></>}</div></div>
}

function PrincipalSection({ title, children }: { title: string; children: any }) {
  return <section className="directory-block"><h3>{title}</h3>{children}</section>
}
function Metric({ n, label, sub, accent }: any) {
  return (
    <div className={accent ? "accent" : ""}>
      <b>{n}</b>
      <span>{label}</span>
      <small>{sub}</small>
    </div>
  );
}
function OfficeDrawer({ office, offices, onClose, onSelect }: any) {
  const [detail, setDetail] = useState<any>(null),
    [error, setError] = useState("");
  useEffect(() => {
    setDetail(null);
    setError("");
    api
      .office(office.n)
      .then(setDetail)
      .catch((e: any) =>
        setError(e.message || "Unable to load office details."),
      );
  }, [office.n]);
  const reports = offices.filter((x: any) => x.reports_to === office.name);
  return (
    <div className="directory-drawer-backdrop" onMouseDown={onClose}>
      <aside
        className="directory-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Office details"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="directory-drawer-head">
          <div>
            <span
              className="lvl-badge"
              style={{ background: LEVEL_COLORS[office.level] }}
            >
              L{office.level}
            </span>
            <h2>{office.name}</h2>
            <p>{office.purpose || "Service profile pending"}</p>
          </div>
          <button
            className="close-x"
            onClick={onClose}
            aria-label="Close office details"
          >
            ×
          </button>
        </div>
        {!detail && !error && <Spinner />}
        {error && <div className="calendar-banner warn">{error}</div>}
        {detail && (
          <div className="directory-drawer-body">
            <div className="directory-actions">
              <button
                className="btn btn-out"
                onClick={() =>
                  navigator.clipboard?.writeText(
                    `${office.name} — ${office.scope || "Institution scope"}`,
                  )
                }
              >
                Copy office details
              </button>
              <span className="tag">{detail.scope || "Institution scope"}</span>
            </div>
            <Block title="What this office can help with">
              <ul className="bullet-list">
                {detail.functionalities.length ? (
                  detail.functionalities.map((x: string) => (
                    <li key={x}>{x}</li>
                  ))
                ) : (
                  <li>Service catalogue is being verified.</li>
                )}
              </ul>
            </Block>
            <Block title="Reporting line">
              <p>
                <b>Reports to:</b> {detail.reports_to || "Not assigned"}
              </p>
              {reports.length > 0 && (
                <div className="directory-links">
                  {reports.map((x: any) => (
                    <button key={x.n} onClick={() => onSelect(x)}>
                      {x.name}
                    </button>
                  ))}
                </div>
              )}
            </Block>
            <Block title={`Internal roles · ${detail.internal_roles.length}`}>
              <div className="directory-tags">
                {detail.internal_roles.map((x: string) => (
                  <span className="tag" key={x}>
                    {x}
                  </span>
                ))}
              </div>
            </Block>
            <Block title="Workflows">
              <ul className="bullet-list">
                {detail.workflows.length ? (
                  detail.workflows.map((x: string) => <li key={x}>{x}</li>)
                ) : (
                  <li>No published workflows.</li>
                )}
              </ul>
            </Block>
            <Block title="Owned modules">
              <div className="directory-tags">
                {detail.modules.map((x: string) => (
                  <span className="tag" key={x}>
                    {x}
                  </span>
                ))}
              </div>
            </Block>
            <p className="directory-governance">
              Directory profile is governed by institutional administration.
              Report inaccurate service or reporting information to the system
              administrator.
            </p>
          </div>
        )}
      </aside>
    </div>
  );
}
function Block({ title, children }: any) {
  return (
    <section className="directory-block">
      <h3>{title}</h3>
      {children}
    </section>
  );
}
