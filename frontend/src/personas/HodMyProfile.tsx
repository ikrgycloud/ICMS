import { useEffect, useState } from 'react';
import { api } from '../api';
import { Empty, Spinner } from '../modules/kit';

type Profile = Record<string, string>;
const editableKeys = ['email', 'phone', 'office_hours'];

export default function HodMyProfile() {
  const [data, setData] = useState<any>(null);
  const [draft, setDraft] = useState<Profile>({});
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const load = async () => {
    setError('');
    try {
      const response = await api.hodProfile();
      setData(response);
      setDraft(editable(response.profile));
    } catch (reason: any) { setError(reason.message || 'Your HOD profile could not be loaded.'); }
  };
  useEffect(() => { load(); }, []);
  if (error && !data) return <Empty icon="!" text={error} />;
  if (!data) return <Spinner />;
  const profile = data.profile;
  if (!profile) return <Empty icon="!" text="Your HOD profile is not available." />;
  const initials = String(profile.name || 'H').split(/\s+/).slice(0, 2).map((part: string) => part[0]).join('').toUpperCase();
  const cancel = () => { setDraft(editable(profile)); setEditing(false); setError(''); };
  const save = async () => {
    setSaving(true); setError(''); setNotice('');
    try {
      await api.updateHodProfile(draft);
      await load();
      setEditing(false);
      setNotice('Profile changes were saved.');
    } catch (reason: any) { setError(reason.message || 'Profile changes could not be saved.'); }
    finally { setSaving(false); }
  };

  return <main className="hod-reports-page fade-in">
    <header className="hod-courses-heading"><div><p>Self-service profile</p><h1>My Profile</h1><span>Your authenticated Head of Department profile. Employment and authority details are read-only.</span></div>{!editing ? <button className="btn btn-out" type="button" onClick={() => { setDraft(editable(profile)); setEditing(true); }}>Edit contact details</button> : <div style={{ display: 'flex', gap: 8 }}><button className="btn btn-out" type="button" onClick={cancel} disabled={saving}>Cancel</button><button className="btn btn-primary" type="button" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</button></div>}</header>
    {error && <p className="hod-allocation-message error">{error}</p>}{notice && <p className="hod-allocation-message">{notice}</p>}
    <section style={heroStyle}><div style={avatarStyle}>{initials || 'H'}</div><div style={{ flex: 1 }}><p style={eyebrowStyle}>Head of Department</p><h2 style={{ margin: '3px 0 6px', color: '#17345f' }}>{display(profile.name)}</h2><p style={{ margin: 0, color: '#61718b' }}>{display(profile.designation)} · {display(profile.department)} · {display(profile.campus)}</p><small style={{ color: '#61718b' }}>Employee ID: {display(profile.employee_id)}</small></div><span className="hod-request-status active">{display(profile.status)}</span></section>
    <div style={gridStyle}>
      <Section title="Personal Information" rows={[["Full name", profile.name], ["Employee ID", profile.employee_id]]} />
      <Section title="Contact Information"><Field label="Email" value={draft.email} fallback={profile.email} editing={editing} type="email" onChange={value => setDraft({ ...draft, email: value })} /><Field label="Phone" value={draft.phone} fallback={profile.phone} editing={editing} type="tel" onChange={value => setDraft({ ...draft, phone: value })} /></Section>
      <Section title="Employment Information" rows={[["Designation", profile.designation], ["Department", profile.department], ["Campus", profile.campus], ["Joining date", profile.date_joined], ["Employment status", profile.status]]} />
      <Section title="Academic / Professional Information"><Field label="Office hours" value={draft.office_hours} fallback={profile.office_hours} editing={editing} type="text" onChange={value => setDraft({ ...draft, office_hours: value })} /></Section>
      <Section title="Account / Role" rows={[["Username", profile.username], ["Base role", profile.office], ["Responsibility", profile.leadership_role]]} />
    </div>
  </main>;
}

function Section({ title, rows, children }: { title: string; rows?: [string, any][]; children?: any }) {
  return <section className="hod-planning-table-card" style={{ padding: 20 }}><header><h2>{title}</h2></header><div style={{ display: 'grid', gap: 12 }}>{rows?.map(([label, value]) => <ReadOnly key={label} label={label} value={value} />)}{children}</div></section>;
}
function ReadOnly({ label, value }: { label: string; value: any }) { return <div><span style={labelStyle}>{label}</span><b style={valueStyle}>{display(value)}</b></div>; }
function Field({ label, value, fallback, editing, type, onChange }: any) { return <div><span style={labelStyle}>{label}</span>{editing ? <input className="inp" type={type} value={value ?? ''} onChange={event => onChange(event.target.value)} aria-label={label} /> : <b style={valueStyle}>{display(fallback)}</b>}</div>; }
function editable(profile: any): Profile { return Object.fromEntries(editableKeys.map(key => [key, profile?.[key] || ''])); }
function display(value: any) { return value === null || value === undefined || value === '' ? '—' : String(value); }

const heroStyle = { display: 'flex', alignItems: 'center', gap: 18, padding: 24, marginBottom: 16, border: '1px solid #dbe5f0', borderRadius: 14, background: '#fff' } as const;
const avatarStyle = { width: 64, height: 64, borderRadius: '50%', display: 'grid', placeItems: 'center', background: '#17345f', color: '#fff', fontSize: 22, fontWeight: 800 } as const;
const eyebrowStyle = { margin: 0, color: '#61718b', fontSize: 12, fontWeight: 700, letterSpacing: '.07em', textTransform: 'uppercase' } as const;
const gridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 } as const;
const labelStyle = { display: 'block', color: '#61718b', fontSize: 12, marginBottom: 4 } as const;
const valueStyle = { display: 'block', color: '#17345f' } as const;
