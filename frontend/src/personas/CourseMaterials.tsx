import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Empty, Modal, Spinner } from "../modules/kit";
const pdf = (m: any) =>
  m.material_type === "pdf" ||
  String(m.resource_url).toLowerCase().includes(".pdf");
export function FacultyMaterials() {
  const [d, setD] = useState<any>(null),
    [s, setS] = useState<any[]>([]),
    [q, setQ] = useState(""),
    [sec, setSec] = useState("all"),
    [show, setShow] = useState(false),
    [f, setF] = useState<any>({
      section_id: "",
      title: "",
      material_type: "pdf",
      resource_url: "",
      status: "published",
    });
  const load = () =>
    api
      .facultyMaterials()
      .then(setD)
      .catch(() => setD({ materials: [] }));
  useEffect(() => {
    load();
    api.facultySections().then((x: any) => setS(x.sections || []));
  }, []);
  if (!d) return <Spinner />;
  const all = d.materials || [],
    rows = all.filter(
      (m: any) =>
        (sec === "all" || m.section_id === sec) &&
        (!q ||
          `${m.title} ${m.course_code}`
            .toLowerCase()
            .includes(q.toLowerCase())),
    ),
    published = all.filter((m: any) => m.status === "published").length;
  return (
    <main className="assess-workspace fade-in">
      <section className="assess-heading">
        <h1>Course Materials</h1>
        <p>
          Upload, organize, and share resources for your assigned courses and
          sections.
        </p>
      </section>
      <section className="assess-kpis">
        {[
          [
            "▤",
            new Set(all.map((m: any) => m.course_code)).size,
            "Assigned Courses",
          ],
          ["▧", all.length, "Total Materials"],
          ["☁", published, "Published Resources"],
          ["✎", all.length - published, "Draft Resources"],
        ].map(([i, v, l]) => (
          <article className="assess-kpi" key={String(l)}>
            <i>{i}</i>
            <div>
              <b>{v}</b>
              <small>{l}</small>
            </div>
          </article>
        ))}
      </section>
      <div className="assess-notice">
        ⓘ Materials are visible only to students enrolled in the selected
        section when published.
      </div>
      <div className="assess-filters">
        <select value={sec} onChange={(e) => setSec(e.target.value)}>
          <option value="all">All Sections</option>
          {s.map((x: any) => (
            <option value={x.id} key={x.id}>
              {x.course_code} · {x.section}
            </option>
          ))}
        </select>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search materials..."
        />
        <button
          className="btn btn-crimson"
          onClick={() => setShow(true)}
          type="button"
        >
          ＋ Upload Material
        </button>
      </div>
      <article className="assess-register">
        <header>
          <h2>Material Library</h2>
        </header>
        <div className="assess-table-wrap">
          <table className="assess-table">
            <thead>
              <tr>
                <th>Course</th>
                <th>Section</th>
                <th>Title</th>
                <th>Type</th>
                <th>Uploaded On</th>
                <th>Visibility</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((m: any) => (
                <tr key={m.id}>
                  <td>
                    <b>{m.course_code}</b>
                    <span>{m.course_title}</span>
                  </td>
                  <td>{m.section}</td>
                  <td>{m.title}</td>
                  <td>{m.material_type}</td>
                  <td>
                    {m.uploaded_at
                      ? new Date(m.uploaded_at).toLocaleDateString()
                      : "—"}
                  </td>
                  <td>
                    <em>{m.status}</em>
                  </td>
                  <td>
                    {pdf(m) ? (
                      <a href={m.resource_url} target="_blank" rel="noreferrer">
                        View PDF
                      </a>
                    ) : (
                      <a href={m.resource_url} target="_blank" rel="noreferrer">
                        Open
                      </a>
                    )}
                  </td>
                </tr>
              ))}
              {!rows.length && (
                <tr>
                  <td colSpan={7}>No materials match the selected filters.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </article>
      {show && (
        <Modal
          title="Upload PDF Material"
          onClose={() => setShow(false)}
          footer={
            <button
              className="btn btn-crimson"
              onClick={async () => {
                await api.createFacultyMaterial(f);
                setShow(false);
                load();
              }}
              type="button"
            >
              Save Material
            </button>
          }
        >
          <div className="form-row">
            <label>Section</label>
            <select
              className="select"
              value={f.section_id}
              onChange={(e) => setF({ ...f, section_id: e.target.value })}
            >
              <option value="">Select section</option>
              {s.map((x: any) => (
                <option value={x.id} key={x.id}>
                  {x.course_code} · {x.section}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <label>Title</label>
            <input
              className="inp"
              value={f.title}
              onChange={(e) => setF({ ...f, title: e.target.value })}
            />
          </div>
          <div className="form-row">
            <label>PDF URL</label>
            <input
              className="inp"
              value={f.resource_url}
              onChange={(e) => setF({ ...f, resource_url: e.target.value })}
            />
          </div>
        </Modal>
      )}
    </main>
  );
}
export function StudentMaterials() {
  const [d, setD] = useState<any>(null);
  useEffect(() => {
    api
      .studentMaterials()
      .then(setD)
      .catch(() => setD({ materials: [] }));
  }, []);
  if (!d) return <Spinner />;
  return (
    <main className="assess-workspace fade-in">
      <section className="assess-heading">
        <h1>Course Materials</h1>
        <p>Published resources from your enrolled sections.</p>
      </section>
      {d.materials.map((m: any) => (
        <article className="card card-pad" key={m.id}>
          <b>{m.title}</b>
          <p>
            {m.course_code} · Section {m.section}
          </p>
          <a href={m.resource_url} target="_blank" rel="noreferrer">
            {pdf(m) ? "View PDF" : "Open resource"}
          </a>
        </article>
      ))}
      {!d.materials.length && (
        <Empty text="No published materials are available." />
      )}
    </main>
  );
import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner } from '../modules/kit'

const titleCase = (value: string) => value ? value.replace(/[_-]/g, ' ').replace(/\b\w/g, item => item.toUpperCase()) : 'Document'
const isPdf = (material: any) => material.material_type === 'pdf' || /\.pdf(?:$|[?#])/i.test(String(material.resource_url || ''))

function Review({ material, onClose }: { material: any; onClose: () => void }) {
  const url = String(material.resource_url || '').trim()
  return <Modal title={material.title || 'Course Material'} onClose={onClose} footer={<><button className="btn btn-out" onClick={onClose} type="button">Close</button>{url && <a className="btn btn-crimson" href={url} target="_blank" rel="noreferrer">Open source</a>}</>}>
    <div className="material-review-meta"><span>{material.course_code} · Section {material.section}</span><span>{titleCase(material.material_type)}</span><span>{material.topic || 'General'}</span></div>
    {material.description && <p>{material.description}</p>}
    {isPdf(material) && url ? <iframe className="material-pdf-preview" title={`Preview of ${material.title}`} src={url} /> : <p>{url ? 'Use Open source to view this material.' : 'No resource is attached yet.'}</p>}
  </Modal>
}

export function FacultyMaterials() {
  const [data, setData] = useState<any>(null), [sections, setSections] = useState<any[]>([]), [query, setQuery] = useState(''), [sectionId, setSectionId] = useState('all'), [preview, setPreview] = useState<any>(null), [showUpload, setShowUpload] = useState(false), [saving, setSaving] = useState(false), [error, setError] = useState('')
  const blank = { section_id: '', title: '', description: '', material_type: 'pdf', resource_url: '', topic: '', status: 'published' }
  const [form, setForm] = useState(blank)
  const load = () => api.facultyMaterials().then(setData).catch(() => setData({ materials: [] }))
  useEffect(() => { load(); api.facultySections().then((result: any) => setSections(result.sections || [])) }, [])
  if (!data) return <Spinner />
  const materials = data.materials || [], rows = materials.filter((material: any) => (sectionId === 'all' || material.section_id === sectionId) && (!query.trim() || `${material.title} ${material.topic} ${material.course_code}`.toLowerCase().includes(query.trim().toLowerCase())))
  const save = async () => { if (!form.section_id || !form.title.trim() || !form.resource_url.trim()) return setError('Select a section, enter a title, and add a resource link.'); setSaving(true); setError(''); try { await api.createFacultyMaterial(form); setShowUpload(false); setForm(blank); load() } catch (caught: any) { setError(caught.message || 'The material could not be saved.') } finally { setSaving(false) } }
  return <main className="assess-workspace fade-in"><section className="assess-heading"><h1>Course Materials</h1><p>Upload, organize, and share resources for your assigned courses and sections.</p></section><section className="assess-kpis">{[['Assigned Courses', new Set(materials.map((m: any) => m.course_code)).size], ['Total Materials', materials.length], ['Published Resources', materials.filter((m: any) => m.status === 'published').length], ['Draft Resources', materials.filter((m: any) => m.status !== 'published').length]].map(([label, value]) => <article className="assess-kpi" key={String(label)}><div><b>{value}</b><small>{label}</small></div></article>)}</section><div className="assess-filters"><select value={sectionId} onChange={event => setSectionId(event.target.value)}><option value="all">All Sections</option>{sections.map(section => <option value={section.id} key={section.id}>{section.course_code} · {section.section}</option>)}</select><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search materials..." /><button className="btn btn-crimson" onClick={() => { setError(''); setShowUpload(true) }} type="button">Upload Material</button></div><article className="assess-register"><header><h2>Material Library</h2></header><div className="assess-table-wrap"><table className="assess-table"><thead><tr><th>Course</th><th>Section</th><th>Title</th><th>Topic</th><th>Type</th><th>Visibility</th><th>Action</th></tr></thead><tbody>{rows.map(material => <tr key={material.id}><td>{material.course_code}</td><td>{material.section}</td><td><b>{material.title}</b></td><td>{material.topic || '-'}</td><td>{titleCase(material.material_type)}</td><td>{material.status}</td><td><button onClick={() => setPreview(material)} type="button">Open</button></td></tr>)}{!rows.length && <tr><td colSpan={7}>No materials match your filters.</td></tr>}</tbody></table></div></article></main>
}

export function StudentMaterials() {
  const [data, setData] = useState<any>(null), [preview, setPreview] = useState<any>(null)
  useEffect(() => { api.studentMaterials().then(setData).catch(() => setData({ materials: [] })) }, [])
  if (!data) return <Spinner />
  return <main className="assess-workspace fade-in"><section className="assess-heading"><h1>Course Materials</h1><p>Published resources from your enrolled sections.</p></section><section className="material-student-grid">{data.materials.map((material: any) => <article className="card card-pad material-student-card" key={material.id}><span>{titleCase(material.material_type)}</span><h3>{material.title}</h3><p>{material.course_code} · Section {material.section}</p><button onClick={() => setPreview(material)} type="button">Open material</button></article>)}</section>{!data.materials.length && <Empty text="No published materials are available." />}{preview && <Review material={preview} onClose={() => setPreview(null)} />}</main>
}
