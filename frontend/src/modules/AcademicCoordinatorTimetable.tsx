import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Empty, Modal, PageHead, Pill, Spinner } from "./kit";

const DAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];
const EMPTY_ENTRY = {
  day_of_week: 0,
  start_time: "09:00",
  end_time: "10:00",
  room: "",
  building: "",
  effective_from: "",
  effective_to: "",
};

export default function AcademicCoordinatorTimetable() {
  const [sections, setSections] = useState<any[] | null>(null);
  const [offerings, setOfferings] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [conflicts, setConflicts] = useState<any[]>([]);
  const [year, setYear] = useState(1);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [openBranches, setOpenBranches] = useState<Record<string, boolean>>({});
  const [openCourses, setOpenCourses] = useState<Record<string, boolean>>({});
  const [sectionModal, setSectionModal] = useState(false);
  const [entryModal, setEntryModal] = useState<any>(null);
  const [editingEntry, setEditingEntry] = useState<any>(null);
  const [entryError, setEntryError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sectionForm, setSectionForm] = useState({
    offering_id: "",
    section_code: "A",
    room: "",
    capacity: 60,
  });
  const [entryForm, setEntryForm] = useState({ ...EMPTY_ENTRY });
  const [changeModal, setChangeModal] = useState<any>(null);
  const [changeForm, setChangeForm] = useState({
    change_type: "room_change",
    room: "",
    start_time: "",
    end_time: "",
    reason: "",
  });

  async function load() {
    setError("");
    try {
      const [sectionResult, offeringResult, planResult, conflictResult] =
        await Promise.all([
          api.sections(),
          api.courseOfferings(),
          api.timetablePlans(),
          api.academicConflicts(),
        ]);
      const loaded = await Promise.all(
        (sectionResult.sections || []).map(async (section: any) => ({
          ...section,
          timetable: (await api.sectionTimetable(section.id)).entries || [],
        })),
      );
      setSections(loaded);
      setOfferings(offeringResult.offerings || []);
      setPlans(planResult.plans || []);
      setConflicts(conflictResult.conflicts || []);
    } catch (e: any) {
      setError(e.message || "Unable to load sections and timetable");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const visibleSections = useMemo(
    () =>
      (sections || []).filter(
        (section) => Math.ceil(Number(section.semester || 1) / 2) === year,
      ),
    [sections, year],
  );
  const branches = useMemo(() => {
    const grouped = new Map<string, any[]>();
    visibleSections.forEach((section) => {
      const name =
        section.program_code ||
        section.program ||
        section.department ||
        "Unassigned Branch";
      const key = name.toLowerCase();
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key)!.push(section);
    });
    return Array.from(grouped.entries())
      .map(([key, rows]) => {
        const courseMap = new Map<string, any[]>();
        rows.forEach((section) => {
          const courseKey = String(
            section.course_id || section.course_code || section.id,
          );
          if (!courseMap.has(courseKey)) courseMap.set(courseKey, []);
          courseMap.get(courseKey)!.push(section);
        });
        return {
          key,
          name:
            rows[0].program_code ||
            rows[0].program ||
            rows[0].department ||
            "Unassigned Branch",
          courses: Array.from(courseMap.entries()).map(
            ([courseKey, courseRows]) => ({
              key: courseKey,
              code: courseRows[0].course_code || "—",
              title: courseRows[0].course_title || "Untitled course",
              sections: courseRows,
            }),
          ),
        };
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [visibleSections]);

  const planFor = (entryId: string) =>
    plans.find((plan) => String(plan.timetable_entry_id) === String(entryId));
  const conflictsFor = (entryId: string) =>
    conflicts.filter(
      (conflict) =>
        String(conflict.left?.entry_id) === String(entryId) ||
        String(conflict.right?.entry_id) === String(entryId),
    );
  const selectedOffering = offerings.find(
    (row) => row.id === sectionForm.offering_id,
  );
  const eligibleOfferings = useMemo(
    () =>
      offerings.filter((offering: any) => {
        const requested = Number(offering.hod_input?.required_sections || 0);
        const created = Number(offering.sections?.length || 0);
        return (
          String(offering.hod_input?.status || "").toLowerCase() ===
            "submitted" && requested > created
        );
      }),
    [offerings],
  );
  const suggestedCapacity = selectedOffering
    ? Math.max(
        1,
        Math.ceil(
          Number(selectedOffering.hod_input?.expected_capacity || 0) /
            Math.max(
              1,
              Number(selectedOffering.hod_input?.required_sections || 1),
            ),
        ),
      )
    : 60;
  const nextSectionCode = (offering: any) => {
    const used = new Set(
      (offering?.sections || []).map((section: any) =>
        String(section.section || section.section_code || "").toUpperCase(),
      ),
    );
    for (let index = 0; index < 26; index += 1) {
      const code = String.fromCharCode(65 + index);
      if (!used.has(code)) return code;
    }
    return `S${used.size + 1}`;
  };

  function openSectionCreate() {
    const offering = eligibleOfferings[0];
    if (!offering) {
      setError(
        "No offering is ready for section planning. Wait for the HOD to submit department requirements.",
      );
      return;
    }
    const capacity = Math.max(
      1,
      Math.ceil(
        Number(offering.hod_input?.expected_capacity || 0) /
          Math.max(1, Number(offering.hod_input?.required_sections || 1)),
      ),
    );
    setError("");
    setSectionForm({
      offering_id: offering.id,
      section_code: nextSectionCode(offering),
      room: "",
      capacity,
    });
    setSectionModal(true);
  }

  async function createSection() {
    if (!selectedOffering) return setError("Select a course offering first");
    if (!String(sectionForm.section_code || "").trim())
      return setError("Enter a section code.");
    if (
      !Number.isInteger(Number(sectionForm.capacity)) ||
      Number(sectionForm.capacity) < 1
    )
      return setError("Section capacity must be at least 1.");
    setBusy(true);
    try {
      await api.createSection({
        course_id: selectedOffering.course_id,
        ...sectionForm,
        section_code: sectionForm.section_code.trim().toUpperCase(),
        faculty_id: "",
        schedule: "",
      });
      setSectionModal(false);
      setMessage("Section created.");
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to create section");
    } finally {
      setBusy(false);
    }
  }

  function openEntry(section: any, entry?: any) {
    setEntryModal(section);
    setEditingEntry(entry || null);
    setEntryError("");
    setEntryForm(
      entry
        ? {
            day_of_week: entry.day_of_week,
            start_time: entry.start_time,
            end_time: entry.end_time,
            room: entry.room || section.room || "",
            building: entry.building || "",
            effective_from: entry.effective_from || "",
            effective_to: entry.effective_to || "",
          }
        : { ...EMPTY_ENTRY, room: section.room || "" },
    );
  }

  function localSlotConflict() {
    if (
      !entryModal ||
      !sections ||
      !entryForm.start_time ||
      !entryForm.end_time
    )
      return "";
    const overlaps = (
      leftStart: string,
      leftEnd: string,
      rightStart: string,
      rightEnd: string,
    ) => leftStart < rightEnd && rightStart < leftEnd;
    const room = entryForm.room.trim().toLowerCase();
    const matches = sections
      .flatMap((section: any) =>
        (section.timetable || []).map((entry: any) => ({ section, entry })),
      )
      .filter(
        ({ section, entry }: any) =>
          entry.id !== editingEntry?.id &&
          entry.status === "active" &&
          Number(entry.day_of_week) === Number(entryForm.day_of_week) &&
          overlaps(
            entryForm.start_time,
            entryForm.end_time,
            entry.start_time,
            entry.end_time,
          ) &&
          (section.id === entryModal.id ||
            (room &&
              String(entry.room || "")
                .trim()
                .toLowerCase() === room) ||
            (entryModal.faculty &&
              entryModal.faculty !== "—" &&
              section.faculty === entryModal.faculty)),
      );
    if (!matches.length) return "";
    const first = matches[0];
    const reason =
      first.section.id === entryModal.id
        ? "this section"
        : room &&
            String(first.entry.room || "")
              .trim()
              .toLowerCase() === room
          ? `room ${entryForm.room}`
          : `faculty ${entryModal.faculty}`;
    return `This overlaps ${reason}: ${DAYS[first.entry.day_of_week]} ${first.entry.start_time}–${first.entry.end_time}${first.entry.room ? ` in ${first.entry.room}` : ""}. Choose a different time or room.`;
  }

  function suggestedSlots() {
    if (!entryModal || !sections) return [] as any[];
    const suggestions: any[] = [];
    for (let day = 0; day < 5 && suggestions.length < 3; day += 1) {
      for (let hour = 9; hour < 17 && suggestions.length < 3; hour += 1) {
        const start = `${String(hour).padStart(2, "0")}:00`;
        const end = `${String(hour + 1).padStart(2, "0")}:00`;
        const occupied = sections
          .flatMap((section: any) =>
            (section.timetable || []).map((entry: any) => ({ section, entry })),
          )
          .some(
            ({ section, entry }: any) =>
              entry.status === "active" &&
              Number(entry.day_of_week) === day &&
              start < entry.end_time &&
              entry.start_time < end &&
              (section.id === entryModal.id ||
                (entryForm.room &&
                  String(entry.room || "")
                    .trim()
                    .toLowerCase() === entryForm.room.trim().toLowerCase()) ||
                (entryModal.faculty &&
                  entryModal.faculty !== "—" &&
                  section.faculty === entryModal.faculty)),
          );
        if (!occupied) suggestions.push({ day, start, end });
      }
    }
    return suggestions;
  }

  async function saveEntry() {
    if (!entryModal) return;
    setEntryError("");
    if (
      !entryForm.start_time ||
      !entryForm.end_time ||
      entryForm.end_time <= entryForm.start_time
    ) {
      setError("End time must be later than start time.");
      return;
    }
    if (!entryForm.room.trim()) {
      setError("Enter the teaching room before saving the timetable slot.");
      return;
    }
    if (
      entryForm.effective_from &&
      entryForm.effective_to &&
      entryForm.effective_to < entryForm.effective_from
    ) {
      setError("Effective end date cannot be earlier than the start date.");
      return;
    }
    const localConflict = localSlotConflict();
    if (localConflict) {
      setEntryError(localConflict);
      return;
    }
    setBusy(true);
    try {
      if (editingEntry)
        await api.updateTimetableEntry(editingEntry.id, entryForm);
      else await api.createTimetableEntry(entryModal.id, entryForm);
      setEntryModal(null);
      setMessage(editingEntry ? "Timetable updated." : "Timetable created.");
      await load();
    } catch (e: any) {
      if (
        String(e.message || "")
          .toLowerCase()
          .includes("conflict")
      )
        setEntryError(
          e.message || "This timetable slot conflicts with an existing entry.",
        );
      else setError(e.message || "Unable to save timetable");
    } finally {
      setBusy(false);
    }
  }

  async function deactivate(entry: any) {
    if (!window.confirm("Deactivate this timetable entry?")) return;
    try {
      await api.deactivateTimetableEntry(entry.id);
      setMessage("Timetable entry deactivated.");
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to deactivate timetable");
    }
  }

  async function submit(entry: any, section: any) {
    if (!section.faculty || section.faculty === "—") {
      setError(
        "Faculty allocation is awaiting Dean approval. Approve the allocation proposal before submitting this timetable to HOD.",
      );
      return;
    }
    try {
      await api.submitTimetablePlan({
        timetable_entry_id: entry.id,
        section_id: section.id,
        offering_id: section.offering_id,
      });
      setMessage("Submitted for HOD review.");
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to submit timetable");
    }
  }

  async function publish(plan: any) {
    try {
      await api.publishTimetablePlan(plan.id);
      setMessage(
        "Approved timetable published. Professors and enrolled students have been notified.",
      );
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to publish timetable");
    }
  }
  async function createChange() {
    if (!changeModal) return;
    try {
      await api.createTimetableChange({
        timetable_entry_id: changeModal.id,
        expected_version: changeModal.version_no || 1,
        ...changeForm,
      });
      setChangeModal(null);
      setMessage(
        "Change request created. Submit it for HOD review from the change workflow.",
      );
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to create timetable change");
    }
  }

  async function resolveConflict(conflict: any) {
    const note = window.prompt("Resolution note") || "";
    if (!note.trim()) return;
    try {
      await api.resolveAcademicConflict(conflict.id, note);
      setMessage("Conflict resolved.");
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to resolve conflict");
    }
  }

  if (!sections)
    return error ? (
      <div className="calendar-banner warn">{error}</div>
    ) : (
      <Spinner />
    );
  return (
    <div className="fade-in coordinator-timetable">
      <PageHead
        title="Sections & Timetable"
        sub="Build section records from approved HOD requirements, then schedule each section through the governed timetable workflow."
        right={
          <div className="timetable-actions">
            <button className="btn btn-crimson" onClick={openSectionCreate}>
              Create section
            </button>
            <button className="btn btn-out" onClick={load}>
              Refresh
            </button>
          </div>
        }
      />
      {error && <div className="calendar-banner warn">{error}</div>}
      {message && <div className="calendar-banner success">{message}</div>}
      <section className="section-planning-brief">
        <div>
          <span>SECTION PLANNING</span>
          <h3>HOD requirements are the gateway</h3>
          <p>
            Create section records only after the HOD submits requirements.
            Faculty allocation is governed separately; timetable slots are added
            after the section exists.
          </p>
        </div>
        <div className="planning-metric">
          <b>{eligibleOfferings.length}</b>
          <small>offerings ready</small>
        </div>
        <div className="planning-metric">
          <b>{visibleSections.length}</b>
          <small>sections this year</small>
        </div>
      </section>
      <div className="academic-year-nav">
        {[1, 2, 3, 4].map((candidate) => {
          const count = (sections || []).filter(
            (row) => Math.ceil(Number(row.semester || 1) / 2) === candidate,
          ).length;
          return (
            <button
              key={candidate}
              className={`academic-year-item ${year === candidate ? "active" : ""}`}
              onClick={() => {
                setYear(candidate);
                setOpenBranches({});
                setOpenCourses({});
              }}
            >
              <span>
                {candidate === 1
                  ? "1st"
                  : candidate === 2
                    ? "2nd"
                    : candidate === 3
                      ? "3rd"
                      : "4th"}{" "}
                Year
              </span>
              <small>
                {count} {count === 1 ? "section" : "sections"}
              </small>
            </button>
          );
        })}
      </div>
      {!branches.length ? (
        <section className="timetable-empty">
          <Empty text="No sections found for this year." />
        </section>
      ) : (
        <div className="academic-tree">
          {branches.map((branch) => {
            const branchOpen = !!openBranches[branch.key];
            return (
              <section
                className={`branch-panel ${branchOpen ? "open" : ""}`}
                key={branch.key}
              >
                <button
                  className="branch-header"
                  onClick={() =>
                    setOpenBranches({
                      ...openBranches,
                      [branch.key]: !branchOpen,
                    })
                  }
                >
                  <div className="branch-left">
                    <span className="tree-chevron">
                      {branchOpen ? "⌄" : "›"}
                    </span>
                    <div>
                      <h2>{branch.name}</h2>
                      <p>
                        {branch.courses.length}{" "}
                        {branch.courses.length === 1 ? "course" : "courses"}
                      </p>
                    </div>
                  </div>
                  <span className="branch-count">{branch.courses.length}</span>
                </button>
                {branchOpen && (
                  <div className="course-list">
                    {branch.courses.map((course: any) => {
                      const courseKey = `${branch.key}-${course.key}`;
                      const courseOpen = !!openCourses[courseKey];
                      return (
                        <div
                          className={`course-panel ${courseOpen ? "open" : ""}`}
                          key={courseKey}
                        >
                          <button
                            className="course-header"
                            onClick={() =>
                              setOpenCourses({
                                ...openCourses,
                                [courseKey]: !courseOpen,
                              })
                            }
                          >
                            <div className="course-header-left">
                              <span className="course-chevron">
                                {courseOpen ? "⌄" : "›"}
                              </span>
                              <div>
                                <strong>{course.code}</strong>
                                <span>{course.title}</span>
                              </div>
                            </div>
                            <span>
                              {course.sections.length}{" "}
                              {course.sections.length === 1
                                ? "section"
                                : "sections"}
                            </span>
                          </button>
                          {courseOpen && (
                            <div className="section-list">
                              {course.sections.map((section: any) => (
                                <SectionCard
                                  key={section.id}
                                  section={section}
                                  planFor={planFor}
                                  conflictsFor={conflictsFor}
                                  onEdit={openEntry}
                                  onDeactivate={deactivate}
                                  onSubmit={submit}
                                  onPublish={publish}
                                  onResolve={resolveConflict}
                                  onChange={(entry: any) => {
                                    setChangeForm({
                                      change_type: "room_change",
                                      room: "",
                                      start_time: "",
                                      end_time: "",
                                      reason: "",
                                    });
                                    setChangeModal(entry);
                                  }}
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}
      {sectionModal && (
        <Modal
          title="Create section record"
          className="section-create-modal"
          onClose={() => setSectionModal(false)}
          footer={
            <div className="modal-actions">
              <button
                className="btn btn-out"
                onClick={() => setSectionModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-crimson"
                disabled={busy || !selectedOffering}
                onClick={createSection}
              >
                {busy ? "Creating..." : "Create section record"}
              </button>
            </div>
          }
        >
          <div className="section-modal-intro">
            <span>GOVERNED SETUP</span>
            <h4>Start with the HOD-approved plan</h4>
            <p>
              This creates the section only. Assign faculty through the approved
              allocation workflow and add class times in the timetable stage.
            </p>
          </div>
          <div className="form-grid">
            <label>
              Eligible course offering
              <select
                className="select"
                value={sectionForm.offering_id}
                onChange={(e) => {
                  const offering = eligibleOfferings.find(
                    (row: any) => row.id === e.target.value,
                  );
                  setSectionForm({
                    ...sectionForm,
                    offering_id: e.target.value,
                    section_code: offering ? nextSectionCode(offering) : "A",
                    capacity: offering
                      ? Math.max(
                          1,
                          Math.ceil(
                            Number(offering.hod_input?.expected_capacity || 0) /
                              Math.max(
                                1,
                                Number(
                                  offering.hod_input?.required_sections || 1,
                                ),
                              ),
                          ),
                        )
                      : 60,
                  });
                }}
              >
                {eligibleOfferings.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.course_code} · {row.course_title} · {row.program_code}{" "}
                    · Sem {row.semester}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Section code
              <input
                className="inp"
                maxLength={12}
                value={sectionForm.section_code}
                onChange={(e) =>
                  setSectionForm({
                    ...sectionForm,
                    section_code: e.target.value.toUpperCase(),
                  })
                }
              />
            </label>
          </div>
          {selectedOffering && (
            <div className="hod-plan-summary">
              <div>
                <small>HOD section plan</small>
                <b>
                  {selectedOffering.sections?.length || 0} created of{" "}
                  {selectedOffering.hod_input?.required_sections || 0}
                </b>
              </div>
              <div>
                <small>Department capacity target</small>
                <b>
                  {selectedOffering.hod_input?.expected_capacity || 0} students
                </b>
              </div>
              <div>
                <small>Recommended capacity</small>
                <b>{suggestedCapacity} per section</b>
              </div>
            </div>
          )}
          <div className="form-grid">
            <label>
              Section capacity
              <input
                className="inp"
                type="number"
                min="1"
                max="1000"
                value={sectionForm.capacity}
                onChange={(e) =>
                  setSectionForm({
                    ...sectionForm,
                    capacity: Number(e.target.value || 0),
                  })
                }
              />
            </label>
            <label>
              Planning room <em>Optional</em>
              <input
                className="inp"
                placeholder="e.g. LH-204"
                value={sectionForm.room}
                onChange={(e) =>
                  setSectionForm({ ...sectionForm, room: e.target.value })
                }
              />
            </label>
          </div>
          <div className="section-boundary-note">
            <b>What happens next</b>
            <span>
              Faculty allocation → add timetable slot → conflict resolution →
              HOD, Dean and VP review → publication.
            </span>
          </div>
        </Modal>
      )}
      {entryModal && (
        <Modal
          title={`${editingEntry ? "Edit" : "Add"} timetable slot · ${entryModal.course_code || "Course"} · Section ${entryModal.section || "—"}`}
          className="timetable-slot-modal"
          onClose={() => {
            if (!busy) setEntryModal(null);
          }}
          footer={
            <div className="modal-actions">
              <button
                className="btn btn-out"
                disabled={busy}
                onClick={() => setEntryModal(null)}
              >
                Cancel
              </button>
              <button
                className="btn btn-crimson"
                disabled={busy}
                onClick={saveEntry}
              >
                {busy
                  ? "Saving..."
                  : editingEntry
                    ? "Save timetable changes"
                    : "Add timetable slot"}
              </button>
            </div>
          }
        >
          <div className="timetable-modal-intro">
            <span>SECTION SCHEDULING</span>
            <h4>
              {entryModal.course_code} · Section {entryModal.section}
            </h4>
            <p>
              {entryModal.faculty && entryModal.faculty !== "—"
                ? `Faculty: ${entryModal.faculty}. `
                : "Faculty allocation is pending. "}
              Save a room and time, then resolve any detected conflicts before
              submitting for review.
            </p>
          </div>
          {entryModal.timetable?.length > 0 && (
            <div className="existing-slot-list">
              <b>Existing slots for this section</b>
              {entryModal.timetable.map((entry: any) => (
                <span key={entry.id}>
                  {DAYS[entry.day_of_week]} · {entry.start_time}–
                  {entry.end_time} · {entry.room || "Room pending"}
                </span>
              ))}
            </div>
          )}
          <div className="form-grid">
            <label>
              Teaching day
              <select
                className="select"
                value={entryForm.day_of_week}
                onChange={(event) => {
                  setEntryError("");
                  setEntryForm({
                    ...entryForm,
                    day_of_week: Number(event.target.value),
                  });
                }}
              >
                {DAYS.map((day, index) => (
                  <option value={index} key={day}>
                    {day}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Teaching room <em>Required</em>
              <input
                className="inp"
                placeholder="e.g. LH-204"
                value={entryForm.room}
                onChange={(event) => {
                  setEntryError("");
                  setEntryForm({ ...entryForm, room: event.target.value });
                }}
              />
            </label>
            <label>
              Start time
              <input
                className="inp"
                type="time"
                value={entryForm.start_time}
                onChange={(event) => {
                  setEntryError("");
                  setEntryForm({
                    ...entryForm,
                    start_time: event.target.value,
                  });
                }}
              />
            </label>
            <label>
              End time
              <input
                className="inp"
                type="time"
                value={entryForm.end_time}
                onChange={(event) => {
                  setEntryError("");
                  setEntryForm({ ...entryForm, end_time: event.target.value });
                }}
              />
            </label>
            <label>
              Building <em>Optional</em>
              <input
                className="inp"
                placeholder="e.g. Academic Block"
                value={entryForm.building}
                onChange={(event) =>
                  setEntryForm({ ...entryForm, building: event.target.value })
                }
              />
            </label>
            <label>
              Effective from <em>Optional</em>
              <input
                className="inp"
                type="date"
                value={entryForm.effective_from}
                onChange={(event) =>
                  setEntryForm({
                    ...entryForm,
                    effective_from: event.target.value,
                  })
                }
              />
            </label>
            <label>
              Effective to <em>Optional</em>
              <input
                className="inp"
                type="date"
                value={entryForm.effective_to}
                onChange={(event) =>
                  setEntryForm({
                    ...entryForm,
                    effective_to: event.target.value,
                  })
                }
              />
            </label>
          </div>
          {entryError && (
            <div className="timetable-conflict-guidance">
              <div className="conflict-head">
                <span className="conflict-icon">!</span>
                <div>
                  <small>Schedule collision prevented</small>
                  <b>Choose another available teaching slot</b>
                </div>
              </div>
              <span>{entryError}</span>
              <div>
                <small>Suggested conflict-free times</small>
                <span className="conflict-suggestions">
                  {suggestedSlots().map((slot: any) => (
                    <button
                      type="button"
                      key={`${slot.day}-${slot.start}`}
                      onClick={() => {
                        setEntryError("");
                        setEntryForm({
                          ...entryForm,
                          day_of_week: slot.day,
                          start_time: slot.start,
                          end_time: slot.end,
                        });
                      }}
                    >
                      {DAYS[slot.day]} · {slot.start}–{slot.end}
                    </button>
                  ))}
                </span>
              </div>
            </div>
          )}
          <div className="section-boundary-note">
            <b>Next step</b>
            <span>
              Use Conflict Center to resolve any blocking conflicts, then submit
              the saved entry for HOD review.
            </span>
          </div>
        </Modal>
      )}
      {changeModal && (
        <Modal
          title="Request published timetable change"
          onClose={() => setChangeModal(null)}
          footer={
            <div className="modal-actions">
              <button
                className="btn btn-out"
                onClick={() => setChangeModal(null)}
              >
                Cancel
              </button>
              <button className="btn btn-crimson" onClick={createChange}>
                Create Change Request
              </button>
            </div>
          }
        >
          <p className="hint">
            Current: {DAYS[changeModal.day_of_week]} {changeModal.start_time}–
            {changeModal.end_time} · {changeModal.room || "No room"}. This
            controlled request will require HOD, Dean, and VP approval.
          </p>
          <div className="form-grid">
            <label>
              Change type
              <select
                className="select"
                value={changeForm.change_type}
                onChange={(e) =>
                  setChangeForm({ ...changeForm, change_type: e.target.value })
                }
              >
                <option value="room_change">Room change</option>
                <option value="time_change">Time change</option>
                <option value="cancellation">Cancellation</option>
              </select>
            </label>
            {changeForm.change_type === "room_change" && (
              <label>
                Proposed room
                <input
                  className="inp"
                  value={changeForm.room}
                  onChange={(e) =>
                    setChangeForm({ ...changeForm, room: e.target.value })
                  }
                />
              </label>
            )}
            {changeForm.change_type === "time_change" && (
              <>
                <label>
                  New start
                  <input
                    className="inp"
                    type="time"
                    value={changeForm.start_time}
                    onChange={(e) =>
                      setChangeForm({
                        ...changeForm,
                        start_time: e.target.value,
                      })
                    }
                  />
                </label>
                <label>
                  New end
                  <input
                    className="inp"
                    type="time"
                    value={changeForm.end_time}
                    onChange={(e) =>
                      setChangeForm({ ...changeForm, end_time: e.target.value })
                    }
                  />
                </label>
              </>
            )}
            <label>
              Reason
              <textarea
                className="inp"
                value={changeForm.reason}
                onChange={(e) =>
                  setChangeForm({ ...changeForm, reason: e.target.value })
                }
              />
            </label>
          </div>
        </Modal>
      )}
    <style>{styles}</style>
    <style>{conflictStyles}</style>
    </div>
  );
}

function SectionCard({
  section,
  planFor,
  conflictsFor,
  onEdit,
  onDeactivate,
  onSubmit,
  onPublish,
  onResolve,
  onChange,
}: any) {
  const [open, setOpen] = useState(false);
  const timetableCount = Number(section.timetable?.length || 0);
  const facultyAssigned = Boolean(section.faculty && section.faculty !== "—");
  return (
    <div className={`section-panel ${open ? "open" : ""}`}>
      <button className="section-header" onClick={() => setOpen(!open)}>
        <div>
          <strong>Section {section.section}</strong>
          <span>
            Faculty: {section.faculty || "Not assigned"} · Room:{" "}
            {section.room || "Not assigned"}
          </span>
        </div>
        <span
          className={`section-timetable-state ${timetableCount ? "scheduled" : "needs-schedule"}`}
        >
          {timetableCount
            ? `${timetableCount} timetable ${timetableCount === 1 ? "entry" : "entries"}`
            : "No timetable yet · Open to add"}
        </span>
      </button>
      {open && (
        <div className="section-body">
          <div className="section-toolbar">
            <span>
              {section.enrolled || 0}/{section.capacity || "—"} enrolled ·{" "}
              {timetableCount
                ? "Manage timetable slots below"
                : "Create the first class slot to begin scheduling."}
            </span>
            <button className="btn btn-brass" onClick={() => onEdit(section)}>
              Add timetable slot
            </button>
          </div>
          {!timetableCount && (
            <Empty text="No timetable entries yet. Use Add timetable slot to create the first class slot." />
          )}
          {timetableCount > 0 && !facultyAssigned && (
            <div className="timetable-prerequisite" role="status">
              <span aria-hidden="true">!</span>
              <div>
                <b>Faculty allocation approval is required</b>
                <small>
                  The timetable is saved, but it can move to HOD review only after Dean Academics approves the faculty-allocation proposal for this section.
                </small>
              </div>
            </div>
          )}
          {section.timetable.map((entry: any) => {
            const plan = planFor(entry.id);
            const activeConflicts = conflictsFor(entry.id).filter(
              (row: any) => row.status !== "Resolved",
            );
            const firstConflict = activeConflicts[0];
            const published = plan?.status === "Published";
            return (
              <div className="timetable-entry" key={entry.id}>
                <div>
                  <b>
                    {DAYS[entry.day_of_week]} · {entry.start_time}–
                    {entry.end_time}
                  </b>
                  <span>
                    {entry.room || "No room"}
                    {entry.building ? ` · ${entry.building}` : ""}
                  </span>
                </div>
                <div className="entry-actions">
                  <Pill
                    s={
                      activeConflicts.length
                        ? "Conflict"
                        : plan?.status || "Draft"
                    }
                  />
                  {firstConflict && (
                    <button
                      className="linkish danger"
                      onClick={() => onResolve(firstConflict)}
                    >
                      Resolve conflict
                      {activeConflicts.length > 1
                        ? ` (${activeConflicts.length})`
                        : ""}
                    </button>
                  )}
                  {published ? (
                    <button
                      className="btn btn-out"
                      onClick={() => onChange(entry)}
                    >
                      Request Change
                    </button>
                  ) : (
                    <button
                      className="linkish"
                      onClick={() => onEdit(section, entry)}
                    >
                      Edit
                    </button>
                  )}
                  {entry.status === "active" && !published && (
                    <button
                      className="linkish danger"
                      onClick={() => onDeactivate(entry)}
                    >
                      Deactivate
                    </button>
                  )}
                  {entry.status === "active" &&
                    !published &&
                    (!plan ||
                      [
                        "Draft",
                        "HOD Returned",
                        "Dean Returned",
                        "VP Returned",
                      ].includes(plan.status)) &&
                    !activeConflicts.length && (
                      <button
                        className="btn btn-out"
                        disabled={!facultyAssigned}
                        title={facultyAssigned ? "Submit this timetable slot for HOD review" : "Dean approval of the faculty allocation is required first"}
                        onClick={() => onSubmit(entry, section)}
                      >
                        {facultyAssigned
                          ? "Submit HOD review"
                          : "Awaiting faculty approval"}
                      </button>
                    )}
                  {plan?.status === "Approved" && (
                    <button
                      className="btn btn-crimson"
                      onClick={() => onPublish(plan)}
                    >
                      Publish timetable
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const conflictStyles = `.timetable-conflict-guidance{display:grid;gap:11px;margin-top:18px;padding:18px;border:1px solid #efc6cd;border-radius:14px;background:linear-gradient(135deg,#fff6f7,#fff);box-shadow:0 8px 22px rgba(126,39,55,.08);color:#705961}.conflict-head{display:flex;align-items:center;gap:10px}.conflict-icon{width:30px;height:30px;display:grid;place-items:center;border-radius:50%;background:#8b2940;color:#fff;font-weight:800;font-size:16px}.conflict-head small{display:block;color:#8b2940;font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.conflict-head b{display:block;margin-top:2px;color:#3c2730;font-size:14px}.timetable-conflict-guidance>span{font-size:13px;line-height:1.55}.timetable-conflict-guidance>div:last-child{display:grid;gap:8px;padding-top:12px;border-top:1px solid #f1dce0}.timetable-conflict-guidance>div:last-child>small{color:#7c666e;font-weight:800;text-transform:uppercase;font-size:10px;letter-spacing:.06em}.conflict-suggestions{display:flex;gap:8px;flex-wrap:wrap}.conflict-suggestions button{border:1px solid #d8b7bf;border-radius:999px;background:#fff;color:#7d2538;padding:7px 10px;font-weight:800;font-size:12px;cursor:pointer}.conflict-suggestions button:hover{background:#7d2538;color:#fff}`;

const styles = `.coordinator-timetable{color:#2d2528}.timetable-actions,.modal-actions,.section-toolbar,.entry-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.section-planning-brief{display:grid;grid-template-columns:minmax(0,1fr) 135px 135px;gap:1px;margin:20px 0;background:#e4d4d8;border:1px solid #e4d4d8;border-radius:15px;overflow:hidden}.section-planning-brief>div{background:#fff;padding:18px 20px}.section-planning-brief>div:first-child{background:linear-gradient(120deg,#3d1722,#682438);color:#fff}.section-planning-brief span,.section-modal-intro span,.timetable-modal-intro span{display:block;font-size:10px;letter-spacing:.11em;font-weight:800;color:#e8c986}.section-planning-brief h3{margin:6px 0;font-size:18px}.section-planning-brief p{margin:0;color:#f3e8eb;font-size:12px;line-height:1.5}.planning-metric{display:flex;flex-direction:column;justify-content:center}.planning-metric b{font-size:26px;color:#741f32}.planning-metric small{color:#81747a;text-transform:uppercase;font-size:10px;font-weight:800;letter-spacing:.06em}.academic-year-nav{display:flex;gap:8px;margin:28px 0 24px;border-bottom:1px solid #e9e2e4;overflow-x:auto}.academic-year-item{border:0;background:transparent;min-width:112px;padding:12px 18px 14px;cursor:pointer;color:#6d6266;text-align:left;position:relative}.academic-year-item span,.academic-year-item small{display:block;white-space:nowrap}.academic-year-item span{font-size:14px;font-weight:700}.academic-year-item small{margin-top:4px;color:#968b90;font-size:11px}.academic-year-item.active{color:#741f32}.academic-year-item.active:after{content:"";position:absolute;left:14px;right:14px;bottom:-1px;height:3px;background:#741f32}.academic-tree{display:flex;flex-direction:column;gap:12px}.branch-panel,.course-panel,.section-panel{background:#fff;border:1px solid #e8e1e3;border-radius:10px;overflow:hidden}.branch-panel.open,.course-panel.open,.section-panel.open{border-color:#d8c6cb;box-shadow:0 4px 18px rgba(53,27,34,.05)}.branch-header,.course-header,.section-header{width:100%;border:0;background:#fff;display:flex;align-items:center;justify-content:space-between;gap:14px;cursor:pointer;text-align:left}.branch-header{padding:18px 20px}.course-header{padding:14px 16px}.section-header{padding:13px 15px}.branch-header:hover,.course-header:hover,.section-header:hover{background:#fcf9fa}.branch-left,.course-header-left{display:flex;align-items:center;gap:12px;min-width:0}.branch-header h2{margin:0;font-size:17px}.branch-header p{margin:5px 0 0;color:#8a7d82;font-size:12px}.tree-chevron,.course-chevron{width:28px;height:28px;border-radius:50%;background:#f7f0f2;color:#741f32;display:grid;place-items:center;font-size:19px;flex:0 0 auto}.branch-count{width:30px;height:30px;border-radius:50%;background:#741f32;color:#fff;display:grid;place-items:center;font-size:12px;font-weight:700}.course-header-left>div,.section-header>div:first-child{display:flex;flex-direction:column;gap:4px;min-width:0}.course-header-left span,.section-header span,.section-body,.timetable-entry span{color:#82767b;font-size:12px}.section-timetable-state{padding:5px 9px;border-radius:999px;font-weight:700;white-space:nowrap}.section-timetable-state.needs-schedule{background:#fff4dc;color:#8b5b08;border:1px solid #efd497}.section-timetable-state.scheduled{background:#edf8f0;color:#287044;border:1px solid #c9e5d1}.course-list{border-top:1px solid #eee7e9;background:#fbfafb;padding:8px 14px 14px 48px;display:flex;flex-direction:column;gap:8px}.section-list{padding:10px 14px 14px 42px;display:flex;flex-direction:column;gap:8px;background:#fdfbfc}.section-body{padding:13px 15px;border-top:1px solid #eee7e9}.section-toolbar{justify-content:space-between;margin-bottom:12px}.timetable-prerequisite{display:flex;gap:11px;margin:0 0 12px;padding:13px 14px;border:1px solid #e8d3a3;border-radius:11px;background:linear-gradient(120deg,#fff9ec,#fff);color:#665630}.timetable-prerequisite>span{width:24px;height:24px;display:grid;place-items:center;border-radius:50%;background:#9a6b17;color:#fff;font-weight:900;flex:0 0 auto}.timetable-prerequisite b,.timetable-prerequisite small{display:block}.timetable-prerequisite b{font-size:13px;color:#5b481b}.timetable-prerequisite small{margin-top:3px;line-height:1.45;color:#796d51}.timetable-entry{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:12px;border:1px solid #ebe4e6;border-radius:8px;margin-top:8px}.timetable-entry>div:first-child{display:flex;flex-direction:column;gap:4px}.entry-actions{justify-content:flex-end}.linkish.danger{color:#a3293e}.timetable-empty{background:#fff;border:1px solid #ebe4e6;border-radius:12px;padding:35px 20px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.form-grid label{display:flex;flex-direction:column;gap:7px;color:#5f5559;font-size:12px;font-weight:700}.form-grid label em{font-weight:500;color:#8b7e84;font-style:normal}.form-grid .select,.form-grid .inp{width:100%;box-sizing:border-box}.section-modal-intro,.timetable-modal-intro{margin-bottom:17px;padding:16px 17px;border-radius:13px;background:linear-gradient(130deg,#fbf3f5,#fff9eb);border:1px solid #eadde0}.section-modal-intro h4,.timetable-modal-intro h4{margin:5px 0;font-size:16px}.section-modal-intro p,.timetable-modal-intro p{margin:0;color:#75676c;line-height:1.5;font-size:12px}.hod-plan-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;margin:16px 0;background:#e8dfe1;border:1px solid #e8dfe1;border-radius:11px;overflow:hidden}.hod-plan-summary div{padding:12px;background:#fcfbfb}.hod-plan-summary small,.hod-plan-summary b{display:block}.hod-plan-summary small{color:#85787e;font-size:10px;text-transform:uppercase;letter-spacing:.05em;font-weight:800}.hod-plan-summary b{margin-top:5px;font-size:13px;color:#4a3138}.section-boundary-note{display:grid;gap:5px;margin-top:16px;padding:13px 14px;border-left:3px solid #a77820;background:#fffbf2;color:#685d49;font-size:12px;line-height:1.45}.calendar-banner{margin:12px 0}@media(max-width:700px){.section-planning-brief{grid-template-columns:1fr}.course-list,.section-list{padding-left:10px}.timetable-entry{align-items:flex-start;flex-direction:column}.entry-actions{justify-content:flex-start}.form-grid,.hod-plan-summary{grid-template-columns:1fr}.section-timetable-state{white-space:normal;text-align:right}}`;
