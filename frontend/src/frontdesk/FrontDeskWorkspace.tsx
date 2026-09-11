import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { FiTrash2, FiCamera, FiUpload } from "react-icons/fi";
import { Html5Qrcode } from "html5-qrcode";
import { Modal } from "../modules/kit";

const tabs: any = {
  frontdesk_dashboard: "Dashboard",
  frontdesk_visitors: "Visitor Management",
  frontdesk_verify: "Verify / Scan",
  frontdesk_appointments: "Appointments",
  frontdesk_helpdesk: "Helpdesk",
  frontdesk_calls: "Telephony / Calls",
  frontdesk_directory: "Directory",
  frontdesk_delegations: "Delegations",
};
const states = [
  "PRE_REGISTERED",
  "EXPECTED",
  "ARRIVED",
  "ID_VERIFIED",
  "HOST_PENDING",
  "HOST_CONFIRMED",
  "PASS_ISSUED",
  "CHECKED_IN",
  "CHECKED_OUT",
  "CANCELLED",
  "DECLINED",
  "NO_SHOW",
  "SECURITY_REVIEW",
  "EXPIRED",
];
export default function FrontDeskWorkspace({ view }: { view: string }) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState<any>({});
  const load = () => {
    setError("");
    const call =
      view === "frontdesk_dashboard"
        ? api.frontdeskDashboard()
        : view === "frontdesk_visitors"
          ? api.frontdeskVisitors()
          : view === "frontdesk_appointments"
            ? api.frontdeskAppointments()
            : view === "frontdesk_helpdesk"
              ? api.frontdeskTickets()
              : view === "frontdesk_calls"
                ? api.frontdeskCalls()
                : view === "frontdesk_delegations"
                  ? api.frontdeskDelegations()
                  : api.frontdeskDirectory();
    call.then(setData).catch((e: any) => setError(e.message));
  };
  useEffect(load, [view]);
  if (error)
    return (
      <div className="empty-state">
        <h3>Unable to load Front Office</h3>
        <p>{error}</p>
      </div>
    );
  if (!data)
    return (
      <div className="center-load">
        <div className="spinner" />
      </div>
    );
  if (view === "frontdesk_dashboard") return <Dashboard data={data} />;
  if (view === "frontdesk_visitors")
    return <Visitors data={data} reload={load} />;
  if (view === "frontdesk_verify") return <Verify />;
  if (view === "frontdesk_appointments") return <Appointments data={data} reload={load} />;
  if (view === "frontdesk_helpdesk") return <Helpdesk data={data} reload={load} />;
  if (view === "frontdesk_calls") return <Calls data={data} />;
  if (view === "frontdesk_delegations") return <Delegations />;
  return <Directory data={data} />;
}
function Dashboard({ data }: any) {
  const kpis = data?.kpis || {
    expected_visitors: 0,
    checked_in: 0,
    appointments_today: 0,
    enquiries: 0,
    overdue_tickets: 0,
  };
  return (
    <div className="fade-in">
      <div className="page-head frontdesk-dashboard-head">
        <h1>Front Office Dashboard</h1>
        <p>Receive | Identify | Assist | Schedule | Route | Track | Close | Audit</p>
      </div>
      <div className="kpi-row frontdesk-kpi-row">
        {Object.entries(kpis).map(([k, v]) => (
          <div className="kpi" key={k}>
            <div className="kpi-v">{String(v)}</div>
            <div className="kpi-l">{k.replaceAll("_", " ")}</div>
          </div>
        ))}
      </div>
      <div className="frontdesk-chart-grid">
        <DashboardChart title="Visitor movement" rows={data?.charts?.visitor_status || []} />
        <DashboardChart title="Helpdesk routing" rows={data?.charts?.ticket_categories || []} />
      </div>
      <div className="frontdesk-dashboard-panels">
        <Table
          title="Today's appointments"
          rows={data?.appointments || []}
          cols={["reference", "visitor_name", "host_name", "status"]}
        />
      </div>
    </div>
  );
}
function DashboardChart({ title, rows }: any) {
  const max = Math.max(1, ...rows.map((row: any) => row.value || 0));
  return <div className="card card-pad frontdesk-chart"><h3>{title}</h3>{rows.map((row: any) => <div className="frontdesk-chart-row" key={row.label}><div><span>{row.label}</span><b>{row.value}</b></div><div className="frontdesk-chart-track"><span style={{ width: `${(row.value / max) * 100}%` }} /></div></div>)}</div>;
}
function Visitors({ data, reload }: any) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [purpose, setPurpose] = useState("");
  const [mode, setMode] = useState("walk_in");
  const [selected, setSelected] = useState<any>(null);
  const [editing, setEditing] = useState(false);
  const [visitorForm, setVisitorForm] = useState<any>({});
  const [visitorSearch, setVisitorSearch] = useState("");
  const [actionError, setActionError] = useState("");
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const visibleVisitors = (data.visitors || []).filter((visitor: any) =>
    visitor.name?.toLowerCase().includes(visitorSearch.trim().toLowerCase())
  );
  async function create() {
    if (!name || !email) return;
    setCreating(true); setActionError("");
    try {
      await api.createFrontdeskVisitor({ name, email, purpose, mode });
      setName(""); setEmail(""); setPurpose(""); reload();
    } catch (e: any) { setActionError(e.message); }
    finally { setCreating(false); }
  }
  function openVisitor(visitor: any) {
    setSelected(visitor);
    setVisitorForm({
      name: visitor.name || "", email: visitor.email || "", contact: visitor.contact || "",
      category: visitor.category || "General Visitor", purpose: visitor.purpose || "",
      host_name: visitor.host_name || "", department: visitor.department || "",
      expected_at: visitor.expected_at || null,
    });
    setEditing(false); setActionError("");
  }
  async function saveVisitor() {
    if (!visitorForm.name?.trim() || !visitorForm.email?.trim()) {
      setActionError("Visitor name and email are required."); return;
    }
    setSaving(true); setActionError("");
    try {
      const updated = await api.updateFrontdeskVisitor(selected.id, visitorForm);
      setSelected(updated); setEditing(false); reload();
    } catch (e: any) {
      setActionError(e.message);
    } finally { setSaving(false); }
  }
  async function deleteVisitor() {
    if (!window.confirm("Delete visitor " + selected.name + "? This cannot be undone.")) return;
    setSaving(true); setActionError("");
    try {
      await api.deleteFrontdeskVisitor(selected.id);
      setSelected(null); reload();
    } catch (e: any) {
      setActionError(e.message);
    } finally { setSaving(false); }
  }
  const campusPresence = selected?.mode === "pre_registered" && !selected?.checked_in_at
    ? "Not came"
    : selected?.checked_out_at || selected?.status === "CHECKED_OUT"
      ? "Went out"
      : "Still in campus";
  return (
    <div className="fade-in">
      <div className="page-head">
        <h1>Visitor Management</h1>
        <p>Register and track visitors without overriding host or security decisions.</p>
      </div>
      <div className="card card-pad frontdesk-visitor-form">
        <h3>Register visitor</h3>
        <div className="form-row">
          <input className="inp" placeholder="Visitor name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="inp" type="email" placeholder="Visitor email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input className="inp" placeholder="Purpose" value={purpose} onChange={(e) => setPurpose(e.target.value)} />
          <select className="select" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="walk_in">Walk-in</option>
            <option value="pre_registered">Pre-registered</option>
          </select>
          <button className="btn btn-brass" onClick={create} disabled={creating}>{creating ? "Registering..." : "Register & email QR"}</button>
        </div>
        {creating && <p className="hint">Creating the visitor pass and sending the QR email...</p>}
        {actionError && <p className="hint" style={{ color: "var(--crimson)" }}>{actionError}</p>}
      </div>
      <div className="card card-pad" style={{ marginTop: 18 }}>
        <input className="inp" placeholder="Search visitor by name" value={visitorSearch} onChange={e => setVisitorSearch(e.target.value)} />
      </div>
      <Table
        title="Visitors"
        rows={visibleVisitors}
        cols={["reference", "name", "email", "category", "status", "pass_number"]}
        onRowClick={openVisitor}
      />
      {selected && (
        <Modal
          title="Visitor details"
          onClose={() => setSelected(null)}
          footer={
            <>
              <button className="btn btn-out" onClick={() => setSelected(null)} disabled={saving}>Close</button>
              <button className="btn btn-out" onClick={() => setEditing(!editing)} disabled={saving}>{editing ? "Cancel edit" : "Edit"}</button>
              {editing && <button className="btn btn-brass" onClick={saveVisitor} disabled={saving}>{saving ? "Saving..." : "Save changes"}</button>}
              <button className="btn btn-crimson" onClick={deleteVisitor} disabled={saving}><FiTrash2 /> Delete</button>
            </>
          }
        >
          {actionError && <p className="hint" style={{ color: "var(--crimson)" }}>{actionError}</p>}
          {editing ? (
            <div className="grid-2">
              <VisitorField label="Name" value={visitorForm.name} onChange={(value: string) => setVisitorForm({ ...visitorForm, name: value })} />
              <VisitorField label="Email" type="email" value={visitorForm.email} onChange={(value: string) => setVisitorForm({ ...visitorForm, email: value })} />
              <VisitorField label="Contact" value={visitorForm.contact} onChange={(value: string) => setVisitorForm({ ...visitorForm, contact: value })} />
              <VisitorField label="Category" value={visitorForm.category} onChange={(value: string) => setVisitorForm({ ...visitorForm, category: value })} />
              <VisitorField label="Host name" value={visitorForm.host_name} onChange={(value: string) => setVisitorForm({ ...visitorForm, host_name: value })} />
              <VisitorField label="Department" value={visitorForm.department} onChange={(value: string) => setVisitorForm({ ...visitorForm, department: value })} />
              <label style={{ gridColumn: "1 / -1" }}>Purpose<textarea className="inp" value={visitorForm.purpose} onChange={e => setVisitorForm({ ...visitorForm, purpose: e.target.value })} /></label>
            </div>
          ) : (
            <div className="grid-2">
              {[
                ["Campus presence", campusPresence],
                ["Reference", selected.reference], ["Status", selected.status], ["Email", selected.email],
                ["Contact", selected.contact], ["Category", selected.category], ["Purpose", selected.purpose],
                ["Host", selected.host_name], ["Department", selected.department],
                ["Pass number", selected.pass_number], ["Visit type", selected.mode],
              ].filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== "").map(([label, value]) => (
                <div key={String(label)}><small>{label}</small><p>{String(value)}</p></div>
              ))}
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}
function VisitorField({ label, value, onChange, type = "text" }: any) {
  return <label>{label}<input className="inp" type={type} value={value} onChange={e => onChange(e.target.value)} /></label>;
}
function qrPass(value: string) {
  const match = value.match(/PASS-[A-Z0-9-]+/i);
  return match ? match[0].toUpperCase() : "";
}
function Verify() {
  const [pass, setPass] = useState("");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const scanInProgress = useRef(false);

  async function scan(value = pass) {
    const scannedPass = qrPass(value.trim());
    if (!scannedPass) {
      setError("This is not a valid ICMS visitor QR code.");
      return;
    }
    setBusy(true); setError(""); setResult(null);
    try {
      setResult(await api.scanFrontdeskPass(scannedPass));
      setPass("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
      scanInProgress.current = false;
    }
  }
  async function scanUploadedFile(event: any) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true); setError(""); setResult(null);
    const scanner = new Html5Qrcode("frontdesk-qr-upload");
    try {
      const decodedText = await scanner.scanFile(file, true);
      await scan(decodedText);
    } catch (e: any) {
      setError("The uploaded image does not contain a readable visitor QR code.");
    } finally {
      setBusy(false);
      scanner.clear().catch(() => undefined);
    }
  }
  useEffect(() => {
    if (!cameraOpen) return;
    let disposed = false;
    const scanner = new Html5Qrcode("frontdesk-qr-reader");
    const start = async () => {
      try {
        await scanner.start(
          { facingMode: "environment" },
          { fps: 10, qrbox: { width: 250, height: 250 } },
          (decodedText) => {
            if (scanInProgress.current) return;
            const scannedPass = qrPass(decodedText);
            if (!scannedPass) {
              setError("This is not a valid ICMS visitor QR code.");
              return;
            }
            scanInProgress.current = true;
            setCameraOpen(false);
            scan(scannedPass);
          },
          () => undefined
        );
      } catch (e: any) {
        if (!disposed) {
          setError("Camera access could not start. Allow camera permission, then try again.");
          setCameraOpen(false);
        }
      }
    };
    start();
    return () => {
      disposed = true;
      scanner.stop().catch(() => undefined).finally(() => scanner.clear().catch(() => undefined));
    };
  }, [cameraOpen]);

  return (
    <div className="fade-in">
      <div className="page-head">
        <h1>Verify / Scan</h1>
        <p>Scan with the camera, upload a QR image, or enter the visitor pass number manually.</p>
      </div>
      <div className="card card-pad">
        <div className="form-row frontdesk-scan-actions">
          <input className="inp" placeholder="Enter visitor pass number" value={pass} onChange={(e) => setPass(e.target.value)} onKeyDown={(e) => e.key === "Enter" && scan()} />
          <button className="btn btn-brass" onClick={() => scan()} disabled={busy}>{busy ? "Scanning..." : "Scan pass"}</button>
          <button className="btn btn-out" onClick={() => { setError(""); setResult(null); setCameraOpen(!cameraOpen); }} disabled={busy}><FiCamera /> {cameraOpen ? "Stop camera" : "Open QR camera"}</button>
          <label className="btn btn-out" style={{ cursor: busy ? "not-allowed" : "pointer" }}><FiUpload /> Upload QR image<input type="file" accept="image/*" onChange={scanUploadedFile} disabled={busy} style={{ display: "none" }} /></label>
        </div>
        {cameraOpen && <div style={{ maxWidth: 440, margin: "18px auto 0" }}><div id="frontdesk-qr-reader" /></div>}
        <div id="frontdesk-qr-upload" style={{ display: "none" }} />
        {error && <p className="hint" style={{ color: "var(--crimson)" }}>{error}</p>}
        {result && (
          <div className="snap">
            <span>Scan complete</span>
            <b>{result.action === "CHECK_IN" ? "Checked in" : "Checked out"} - {result.visitor?.name}</b>
            <small>{result.message}</small>
          </div>
        )}
      </div>
    </div>
  );
}
function Delegations() {
  const [rows, setRows] = useState<any[]>([]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.frontdeskDelegations().then((r: any) => setRows(r.delegations || [])).catch((e: any) => setError(e.message)); }, []);
  const filtered = rows.filter(row => [row.reference_code, row.subject, row.policy_type, row.to_name, row.to_office].join(" ").toLowerCase().includes(query.toLowerCase()));
  return <div className="fade-in">
    <div className="page-head"><h1>Delegations</h1><p>Read-only register of delegated authority.</p></div>
    <div className="card card-pad"><input className="inp" placeholder="Search delegation, policy or recipient" value={query} onChange={e => setQuery(e.target.value)} /><p className="hint">View-only: Front Desk cannot create, edit, or revoke delegations.</p>{error && <p className="hint" style={{color:"var(--crimson)"}}>{error}</p>}</div>
    <Table title="Delegation register" rows={filtered.map(row => ({...row, recipient:row.to_name, authority:row.authority_label, delegation_status:row.status_meta?.label || row.status}))} cols={["reference_code","subject","recipient","authority","window_label","delegation_status"]} onRowClick={setSelected} />
    {selected && <Modal title="Delegation details" onClose={() => setSelected(null)} footer={<button className="btn btn-out" onClick={() => setSelected(null)}>Close</button>}><div className="grid-2">{[["Reference",selected.reference_code],["Status",selected.status_meta?.label || selected.status],["Policy type",selected.policy_type],["Subject",selected.subject],["Delegated by",selected.from_name],["Delegated to",selected.to_name],["Recipient office",selected.to_office],["Authority",selected.authority_label],["Scope",selected.resource_scope_label],["Valid period",selected.window_label],["Notes",selected.notes || selected.reason]].filter(([,v])=>v).map(([l,v])=><div key={String(l)}><small>{l}</small><p>{String(v)}</p></div>)}</div></Modal>}
  </div>;
}
function Directory({ data }: any) {
  const [query, setQuery] = useState("");
  const people = (data.people || []).filter((person: any) => person.name?.toLowerCase().includes(query.trim().toLowerCase()));
  return <div className="fade-in">
    <div className="page-head"><h1>Directory</h1><p>Find employees and their Front Desk contact details.</p></div>
    <div className="card card-pad"><input className="inp" placeholder="Search by employee name" value={query} onChange={e => setQuery(e.target.value)} /></div>
    <Table title="People directory" rows={people} cols={["name", "email", "contact"]} />
  </div>;
}
function Helpdesk({ data, reload }: any) {
  const [form, setForm] = useState<any>({ category: "General", priority: "normal", source: "walk_in" });
  const [error, setError] = useState("");
  async function submit() {
    if (!form.requester?.trim() || !form.subject?.trim()) {
      setError("Requester name and ticket subject are required.");
      return;
    }
    setError("");
    try {
      await api.createFrontdeskTicket(form);
      setForm({ category: "General", priority: "normal", source: "walk_in" });
      reload();
    } catch (e: any) { setError(e.message); }
  }
  return <div className="fade-in">
    <div className="page-head"><h1>Helpdesk</h1><p>Create and track Front Desk service requests.</p></div>
    <div className="card card-pad frontdesk-ticket-form">
      <h3>Create ticket</h3>
      <div className="grid-2">
        <label>Requester name<input className="inp" value={form.requester || ""} onChange={e => setForm({ ...form, requester: e.target.value })} /></label>
        <label>Contact / email<input className="inp" value={form.contact || ""} onChange={e => setForm({ ...form, contact: e.target.value })} /></label>
        <label>Category<select className="select" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}><option>General</option><option>Facilities</option><option>IT support</option><option>Student Affairs</option></select></label>
        <label>Priority<select className="select" value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })}><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label>
        <label style={{ gridColumn: "1 / -1" }}>Subject<input className="inp" value={form.subject || ""} onChange={e => setForm({ ...form, subject: e.target.value })} /></label>
        <label style={{ gridColumn: "1 / -1" }}>Description<textarea className="inp" rows={3} value={form.description || ""} onChange={e => setForm({ ...form, description: e.target.value })} /></label>
      </div>
      {error && <p className="hint" style={{ color: "var(--crimson)" }}>{error}</p>}
      {form.category === "Facilities" && <p className="hint">This ticket will be routed to Facilities &amp; Maintenance.</p>}
      {form.category === "IT support" && <p className="hint">This ticket will be routed to IT Management.</p>}
      {form.category === "Student Affairs" && <p className="hint">This ticket will be routed to Dean Student Affairs.</p>}
      <button className="btn btn-brass" onClick={submit}>Create ticket</button>
    </div>
    <Table title="Helpdesk queue" rows={data.tickets || []} cols={["number", "requester", "category", "assigned_office", "priority", "status"]} />
  </div>;
}
function Calls({ data }: any) {
  return <div className="fade-in">
    <div className="page-head"><h1>Telephony / Calls</h1><p>Recent Front Desk call activity.</p></div>
    <Table title="Call logs" rows={data.calls || []} cols={["caller", "contact", "recipient", "outcome", "status"]} />
  </div>;
}
function Appointments({ data, reload }: any) {
  const [form, setForm] = useState<any>({});
  const [people, setPeople] = useState<any[]>([]);
  const [hostSearch, setHostSearch] = useState("");
  const [showHosts, setShowHosts] = useState(false);
  const [error, setError] = useState("");
  const hostPickerRef = useRef<HTMLLabelElement>(null);

  useEffect(() => {
    api.frontdeskEmployees().then((response: any) => setPeople(response.employees || [])).catch((e: any) => setError(e.message));
  }, []);
  useEffect(() => {
    const closeHostPicker = (event: MouseEvent) => {
      if (hostPickerRef.current && !hostPickerRef.current.contains(event.target as Node)) setShowHosts(false);
    };
    document.addEventListener("mousedown", closeHostPicker);
    return () => document.removeEventListener("mousedown", closeHostPicker);
  }, []);

  const matchingPeople = people.filter(person =>
    [person.name, person.email, person.contact].some(value => String(value || "").toLowerCase().includes(hostSearch.trim().toLowerCase()))
  ).slice(0, 50);

  function selectHost(person: any) {
    setForm({ ...form, host_name: person.name, host_user_id: person.id });
    setHostSearch(person.name); setShowHosts(false);
  }
  async function submit() {
    if (!form.visitor_name || !form.contact || !form.host_name || !form.starts_at) {
      setError("Visitor name, email, employee and visit date are required."); return;
    }
    setError("");
    try {
      await api.createFrontdeskAppointment(form);
      setForm({}); setHostSearch(""); reload();
    } catch (e: any) { setError(e.message); }
  }
  return <div className="fade-in">
    <div className="page-head"><h1>Appointments</h1><p>Schedule a visitor with an employee and their planned visit date.</p></div>
    <div className="card card-pad frontdesk-appointment-form">
      <h3>Add appointment</h3>
      <div className="grid-2">
        <label>Visitor name<input className="inp" value={form.visitor_name || ""} onChange={e => setForm({ ...form, visitor_name: e.target.value })} /></label>
        <label>Visitor email<input className="inp" type="email" value={form.contact || ""} onChange={e => setForm({ ...form, contact: e.target.value })} /></label>
        <label className="frontdesk-host-picker" ref={hostPickerRef}>
          Whom to meet
          <input className="inp" placeholder="Search employees by name or email" value={hostSearch} onFocus={() => setShowHosts(true)} onChange={e => { setHostSearch(e.target.value); setShowHosts(true); }} />
          {showHosts && <div className="frontdesk-host-menu">
            {!matchingPeople.length ? <div className="empty" style={{ padding: 14 }}>No employees found</div> : matchingPeople.map(person => (
              <button key={person.id} type="button" className="frontdesk-host-option" onClick={() => selectHost(person)}>
                <b>{person.name}</b><small>{[person.designation, person.email || person.contact].filter(Boolean).join(" - ")}</small>
              </button>
            ))}
          </div>}
        </label>
        <label>Visit date &amp; time<input className="inp" type="datetime-local" value={form.starts_at || ""} onChange={e => setForm({ ...form, starts_at: e.target.value })} /></label>
      </div>
      {form.host_name && <p className="hint">Selected employee: <b>{form.host_name}</b></p>}
      {error && <p className="hint" style={{ color: "var(--crimson)" }}>{error}</p>}
      <button className="btn btn-brass" onClick={submit}>Schedule appointment</button>
    </div>
    <Table title="Appointments" rows={data.appointments || []} cols={["reference", "visitor_name", "contact", "host_name", "starts_at", "status"]} />
  </div>;
}
function Table({ title, rows = [], cols = [], onRowClick }: any) {
  return (
    <div className="card" style={{ marginTop: 18 }}>
      <div className="card-h">
        <h3>{title}</h3>
      </div>
      <div className="tbl-scroll">
        {!rows.length ? (
          <div className="empty" style={{ padding: 24 }}>
            No records
          </div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                {cols.map((c: string) => (
                  <th key={c}>{c.replaceAll("_", " ")}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r: any, i: number) => (
                <tr key={r.id || i} onClick={() => onRowClick?.(r)} style={{cursor:onRowClick ? "pointer" : undefined}}>
                  {cols.map((c: string) => (
                    <td key={c}>{r[c] == null ? "â€”" : String(r[c])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}









