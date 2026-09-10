import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, Modal, PageHead, Pill, Spinner } from "./kit";
import CommitteeGovernance from "./CommitteeGovernance";

const WORKSPACE_TAB_GROUPS = [
  { label: "Operations", tabs: [{ key: "allocation", label: "Faculty Allocation" }, { key: "readiness", label: "Timetable Readiness" }, { key: "delivery", label: "Semester Delivery" }] },
  { label: "Quality", tabs: [{ key: "risk", label: "Academic Risk" }, { key: "review", label: "Quality Reviews" }, { key: "action", label: "Corrective Actions" }, { key: "outcomes", label: "CO/PO Attainment" }] },
  { label: "Governance", tabs: [{ key: "governance", label: "Version Control" }, { key: "committee", label: "Committees" }, { key: "planning", label: "Next-semester Planning" }] },
  { label: "Insights", tabs: [{ key: "reports", label: "Reports" }] },
];

export default function DeanAcademicWorkspaces({
  initialTab = "allocation",
}: {
  initialTab?: string;
}) {
  const [data, setData] = useState<any>(null),
    [tab, setTab] = useState(initialTab),
    [error, setError] = useState(""),
    [attainmentLevel, setAttainmentLevel] = useState("course"),
    [attainmentData, setAttainmentData] = useState<any>(null),
    [jobs, setJobs] = useState<any>(null);
  const [show, setShow] = useState(false),
    [form, setForm] = useState<any>({}),
    [riskReviewContext, setRiskReviewContext] = useState<any>(null),
    [reviewFocusId, setReviewFocusId] = useState(""),
    [evidenceAction, setEvidenceAction] = useState<any>(null),
    [evidenceText, setEvidenceText] = useState(""),
    [evidenceError, setEvidenceError] = useState(""),
    [verificationAction, setVerificationAction] = useState<any>(null),
    [verificationNote, setVerificationNote] = useState(""),
    [verificationError, setVerificationError] = useState(""),
    [saving, setSaving] = useState(false),
    [refreshing, setRefreshing] = useState(false),
    [density, setDensity] = useState<"comfortable" | "compact">("comfortable"),
    [query, setQuery] = useState("");
  async function load() {
    setRefreshing(true);
    setError("");
    try {
      const [
        allocations,
        readiness,
        risks,
        reviews,
        actions,
        sections,
        staff,
        committees,
        attainment,
        plans,
        curriculumVersions,
        calendarVersions,
        conflicts,
        workload,
        delivery,
        jobData,
      ] = await Promise.all([
        api.allocationProposals(),
        api.timetableReadiness(),
        api.academicQualityRisks(),
        api.qualityReviews(),
        api.correctiveActions(),
        api.sections(),
        api.facultyStaff("", "", "", 1),
        api.committees(),
        api.attainment(),
        api.nextSemesterPlans(),
        api.curriculumVersions(),
        api.calendarVersions(),
        api.timetableConflicts(),
        api.facultyWorkload(),
        api.deliveryMonitoring(),
        api.monitorJobs(),
      ]);
      setData({
        allocations,
        readiness,
        risks,
        reviews,
        actions,
        sections: sections.sections || [],
        staff: staff.staff || staff.faculty || [],
        committees: committees.committees || [],
        attainment,
        plans: plans.plans || [],
        curriculumVersions: curriculumVersions.versions || [],
        calendarVersions: calendarVersions.versions || [],
        conflicts,
        workload,
        delivery,
      });
      setJobs(jobData);
    } catch (e: any) {
      setError(e.message || "Unable to load workspace");
    } finally {
      setRefreshing(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  // App reuses this workspace component between navigation targets. Keep the
  // visible workspace synchronized when the route changes (timetable versus
  // faculty allocation) instead of retaining the previous tab.
  useEffect(() => {
    setTab(initialTab);
  }, [initialTab]);
  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      event.preventDefault();
      document.querySelector<HTMLInputElement>(".dean-workspace-search input")?.focus();
    };
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);
  if (!data) {
    if (error) return <div className="fade-in"><div className="card card-pad calendar-banner warn"><b>Dean workspace unavailable.</b><p>{error}</p><button className="btn btn-out" onClick={load}>Retry</button></div></div>;
    return <Spinner />;
  }
  async function allocation() {
    setSaving(true);
    try {
      const p = await api.createAllocationProposal(form);
      await api.submitAllocationProposal(
        p.proposal.id,
        p.proposal.status_version,
      );
      setShow(false);
      load();
    } catch (e: any) {
      setError(e.message || "Unable to submit faculty allocation proposal");
    } finally {
      setSaving(false);
    }
  }
  async function review() {
    setSaving(true);
    try {
      const result = await api.createQualityReview(form);
      setShow(false);
      setRiskReviewContext(null);
      setReviewFocusId(result.review_id || "");
      setTab("review");
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to create quality review");
    } finally {
      setSaving(false);
    }
  }
  async function action() {
    setSaving(true);
    try {
      await api.createCorrectiveAction(form.review_id, form);
      setShow(false);
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to assign corrective action");
    } finally {
      setSaving(false);
    }
  }
  async function approve(p: any) {
    setSaving(true);
    try {
      await api.decideAllocationProposal(p.id, "approve", p.status_version);
      await load();
    } catch (e: any) {
      setError(
        e.message || "This proposal cannot be approved by the current user",
      );
    } finally {
      setSaving(false);
    }
  }
  async function resubmitAllocation(p: any) {
    setSaving(true);
    try {
      await api.submitAllocationProposal(p.id, p.status_version);
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to resubmit faculty allocation proposal");
    } finally {
      setSaving(false);
    }
  }
  function openEvidenceVerification(action: any) {
    setVerificationAction(action);
    setVerificationNote("");
    setVerificationError("");
  }
  async function verify() {
    if (!verificationAction) return;
    if (!verificationNote.trim()) {
      setVerificationError("Record what you checked before approving this evidence.");
      return;
    }
    setSaving(true);
    try {
      await api.verifyCorrectiveAction(verificationAction.id, {
        expected_status_version: verificationAction.status_version,
        evidence: verificationAction.evidence,
        verification_result: verificationNote.trim(),
      });
      setVerificationAction(null);
      setVerificationNote("");
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to verify corrective action");
    } finally {
      setSaving(false);
    }
  }
  function openEvidenceSubmission(action: any) {
    setEvidenceAction(action);
    setEvidenceText(action.evidence || "");
    setEvidenceError("");
  }
  async function submitEvidence() {
    if (!evidenceAction) return;
    if (!evidenceText.trim()) {
      setEvidenceError("Describe the completed work and provide the evidence location or reference.");
      return;
    }
    setSaving(true);
    try {
      await api.submitCorrectiveAction(evidenceAction.id, { expected_status_version: evidenceAction.status_version, evidence: evidenceText.trim(), progress: 100, owner_acknowledged: true });
      setEvidenceAction(null);
      setEvidenceText("");
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to submit corrective-action evidence");
    } finally {
      setSaving(false);
    }
  }
  async function refreshAttainment(level: string) {
    setAttainmentLevel(level);
    try { setAttainmentData(await api.attainmentAggregate(level)); }
    catch (e: any) { setError(e.message || "Unable to load attainment summary"); }
  }
  async function transitionReview(review: any, target: string) {
    setSaving(true);
    try {
      await api.transitionQualityReview(review.id, {
        target_state: target,
        expected_status_version: review.status_version,
      });
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to update quality review");
    } finally {
      setSaving(false);
    }
  }
  async function measureReview(review: any) {
    const result = window.prompt("Effectiveness result");
    if (!result) return;
    setSaving(true);
    try {
      await api.recordQualityEffectiveness(review.id, {
        measure: review.effectiveness_measure || "Post-action effectiveness",
        result,
      });
      await load();
    } catch (e: any) {
      setError(e.message || "Unable to record effectiveness result");
    } finally {
      setSaving(false);
    }
  }
  const reviewTransitions: any = {
    OPEN: [["INVESTIGATION", "Investigate"]],
    INVESTIGATION: [
      ["ROOT_CAUSE_CONFIRMED", "Confirm root cause"],
      ["OPEN", "Reopen"],
    ],
    ROOT_CAUSE_CONFIRMED: [["ACTION_PLAN_APPROVED", "Approve action plan"]],
    ACTION_PLAN_APPROVED: [["ACTIONS_IN_PROGRESS", "Start actions"]],
    ACTIONS_IN_PROGRESS: [["EFFECTIVENESS_REVIEW", "Review effectiveness"]],
    EFFECTIVENESS_REVIEW: [
      ["ACTIONS_IN_PROGRESS", "Resume actions"],
      ["CLOSED", "Close"],
    ],
  };
  async function exportReport(type: string, format: string) {
    setSaving(true);
    try {
      await api.academicReport(type, format);
    } catch (e: any) {
      setError(e.message || "Unable to download report");
    } finally {
      setSaving(false);
    }
  }
  const actionableReviews = data.reviews.reviews.filter((review: any) =>
    ["ACTION_PLAN_APPROVED", "ACTIONS_IN_PROGRESS"].includes(review.state),
  );
  const allocationRows = data.allocations.proposals || [];
  const allocationPending = allocationRows.filter((p: any) => ["SUBMITTED", "RESUBMITTED"].includes(p.state)).length;
  const allocationApproved = allocationRows.filter((p: any) => ["APPROVED", "IMPLEMENTED"].includes(p.state)).length;
  const readinessExceptions = data.readiness.exceptions || [];
  const readinessOpen = readinessExceptions.filter((x: any) => x.status !== "RESOLVED");
  const readinessCritical = readinessOpen.filter((x: any) => x.severity === "critical").length;
  const normalizedQuery = query.trim().toLowerCase();
  const matchesQuery = (value: any) => !normalizedQuery || JSON.stringify(value).toLowerCase().includes(normalizedQuery);
  const filteredAllocationRows = allocationRows.filter(matchesQuery);
  const filteredReadinessExceptions = readinessExceptions.filter(matchesQuery);
  const filteredRisks = (data.risks.risks || []).filter(matchesQuery);
  const filteredReviews = data.reviews.reviews.filter((review: any) => (!reviewFocusId || review.id === reviewFocusId) && matchesQuery);
  const filteredActions = data.actions.actions.filter(matchesQuery);
  const workloadFaculty = data.workload?.faculty || [];
  const workloadOverloaded = workloadFaculty.filter((item: any) => item.status === "overload").length;
  const workloadAssigned = workloadFaculty.filter((item: any) => Number(item.workload_units || 0) > 0).length;
  const queuedJobs = (jobs?.jobs || []).filter((job: any) => ["queued", "pending", "running"].includes(String(job.status || "").toLowerCase())).length;
  const openQualityReviews = data.reviews.reviews.filter((review: any) => review.state !== "CLOSED").length;
  const openCorrectiveActions = data.actions.actions.filter((action: any) => action.state !== "CLOSED" && action.state !== "VERIFIED").length;
  const attainmentValues = (data.attainment.course_outcomes || [])
    .map((item: any) => Number(item.attainment))
    .filter((value: number) => Number.isFinite(value));
  const averageAttainment = attainmentValues.length
    ? Math.round(attainmentValues.reduce((sum: number, value: number) => sum + value, 0) / attainmentValues.length)
    : null;
  const open = (kind: string) => {
    setRiskReviewContext(null);
    setReviewFocusId("");
    setForm(
      kind === "allocation"
        ? {
            section_id: data.sections[0]?.id || "",
            faculty_person_id: data.staff[0]?.id || "",
            rationale: "",
          }
        : kind === "review"
          ? {
              title: "",
              metric_key: "academic_readiness",
              deviation: "",
              root_cause: "",
              owner_id: "",
              scope_ref: "",
              scope_level: "department",
            }
          : {
              review_id: actionableReviews[0]?.id || "",
              title: "",
              owner_id: "",
              deadline: "",
            },
    );
    setTab(kind);
    setShow(true);
  };
  const openRiskReview = (risk: any) => {
    setRiskReviewContext(risk);
    setForm({ title: `Academic readiness risk — ${risk.department || "Academic scope"}`, source_key: risk.source_key, metric_key: risk.metric_key, metric_value: risk.metric_value, threshold: risk.threshold, deviation: risk.deviation, root_cause: "", owner_id: "", due_at: "", effectiveness_measure: "" });
    setTab("review");
    setShow(true);
  };
  const activeTabLabel = WORKSPACE_TAB_GROUPS.flatMap((group) => group.tabs).find((item) => item.key === tab)?.label || "Dean Academic Workspaces";
  return (
    <div className={`fade-in dean-workspaces dean-density-${density}`}>
      <PageHead
        title={
          tab === "allocation"
            ? "Faculty Allocation"
            : tab === "readiness"
              ? "Timetable Readiness"
              : tab === "risk"
                ? "Academic Risk"
              : tab === "reports"
                ? "Reports & Analytics"
              : activeTabLabel
        }
        sub={
          tab === "allocation"
            ? "Assign faculty to sections, review workload, and approve independent allocation proposals."
            : tab === "readiness"
              ? "Resolve section, room, and faculty clashes before the timetable is published."
              : tab === "risk"
                ? "Prioritize academic risks by department, assign corrective actions, and track intervention progress."
              : `Manage ${activeTabLabel.toLowerCase()} with governed academic workflows and decision-ready evidence.`
        }
        right={
          <button className={`btn btn-out ${refreshing ? "is-loading" : ""}`} onClick={load} disabled={refreshing}>
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        }
      />
      {error && <div className="calendar-banner warn">{error}</div>}
      <div className="dean-workspace-tabs" role="tablist" aria-label="Dean academic workspaces">
        {WORKSPACE_TAB_GROUPS.map((group) => (
          <div className="dean-workspace-tab-group" key={group.label}>
            <span className="dean-workspace-tab-label">{group.label}</span>
            <div className="dean-workspace-tab-list">
              {group.tabs.map((item) => (
                <button key={item.key} className={`dean-workspace-tab ${tab === item.key ? "on" : ""}`} onClick={() => setTab(item.key)} role="tab" aria-selected={tab === item.key} type="button">
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="dean-workspace-tools">
        <label className="dean-workspace-search"><span>Search workspace</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${activeTabLabel.toLowerCase()}...`} aria-label={`Search ${activeTabLabel}`} /><kbd>/</kbd></label>
        <div className="dean-density-toggle" role="group" aria-label="Workspace density">
          <span>Density</span>
          <button className={density === "comfortable" ? "on" : ""} onClick={() => setDensity("comfortable")} type="button">Comfortable</button>
          <button className={density === "compact" ? "on" : ""} onClick={() => setDensity("compact")} type="button">Compact</button>
        </div>
      </div>
      {tab === "allocation" && (
        <div className="dean-workspace dean-allocation-workspace">
          <div className="dean-workspace-metrics">
            <div className="dean-workspace-metric"><span>Faculty assignments</span><b>{workloadFaculty.length}</b><small>{workloadAssigned} with approved workload</small></div>
            <div className="dean-workspace-metric"><span>Pending approvals</span><b>{allocationPending}</b><small>Independent review required</small></div>
            <div className="dean-workspace-metric"><span>Approved allocations</span><b>{allocationApproved}</b><small>Ready for delivery</small></div>
            <div className="dean-workspace-metric warning"><span>Overloaded faculty</span><b>{workloadOverloaded}</b><small>Needs balancing</small></div>
          </div>
          <section className="card card-pad dean-workspace-table">
          <div className="card-h">
            <div><h3>Faculty allocation proposals</h3><p className="hint">Assign sections, review workload impact, and approve changes independently.</p></div>
            {data.allocations.can_propose && <button
              className="btn btn-crimson"
              onClick={() => open("allocation")}
            >
              Propose allocation
            </button>}
          </div>
          {filteredAllocationRows.map((p: any) => (
            <div className="dean-workspace-row" key={p.id}>
              <span>
                <b>{p.title}</b>
                <br />
                <small>{p.scope_ref || "Institution scope"} · Updated {formatWorkspaceDate(p.updated_at)}</small>
              </span>
              <Pill s={p.state} />
              {["SUBMITTED", "RESUBMITTED"].includes(p.state) &&
                p.submitted_by !== currentUserId() && (
                  <button
                    className="btn btn-sm btn-crimson"
                    disabled={saving}
                    onClick={() => approve(p)}
                  >
                    Approve
                  </button>
                )}
              {["SUBMITTED", "RESUBMITTED"].includes(p.state) &&
                p.submitted_by === currentUserId() && (
                  <span className="hint">Awaiting independent approval</span>
                )}
              {p.state === "RETURNED" && p.submitted_by === currentUserId() && (
                <button className="btn btn-sm btn-crimson" disabled={saving} onClick={() => resubmitAllocation(p)}>
                  Resubmit
                </button>
              )}
            </div>
          ))}
          {!filteredAllocationRows.length && (
            <Empty text={allocationRows.length ? "No proposals match your search" : "No allocation proposals"} />
          )}
          </section>
        </div>
      )}
      {tab === "readiness" && (
        <div className="dean-workspace dean-readiness-workspace">
          <div className="dean-workspace-metrics">
            <div className="dean-workspace-metric"><span>Open exceptions</span><b>{readinessOpen.length}</b><small>Across scoped sections</small></div>
            <div className="dean-workspace-metric danger"><span>Critical conflicts</span><b>{readinessCritical}</b><small>Resolve before publishing</small></div>
            <div className="dean-workspace-metric"><span>Sections checked</span><b>{Number(data.sections?.length || 0)}</b><small>Current academic scope</small></div>
            <div className="dean-workspace-metric success"><span>Decision access</span><b>{data.readiness.can_decide ? "Yes" : "View"}</b><small>{data.readiness.can_decide ? "You can resolve" : "Escalate to owner"}</small></div>
          </div>
          <section className="card card-pad dean-workspace-table">
          <div className="card-h">
            <div><h3>Timetable readiness exceptions</h3><p className="hint">Resolve faculty, room, and section clashes before publishing the timetable.</p></div>
            <b>{readinessOpen.length} open</b>
          </div>
          {filteredReadinessExceptions.map((x: any, i: number) => (
            <div className={`dean-workspace-row dean-readiness-row ${x.severity === "critical" ? "is-critical" : ""}`} key={x.id || i}>
              <span>
                <b>{x.kind.replace(/_/g, " ")}</b>
                <br />
                <small>{x.message}</small>
              </span>
              <span className="row-actions">
                <Pill s={x.severity} />
                {x.status !== "RESOLVED" &&
                  x.id &&
                  data.readiness.can_decide && (
                    <button
                      className="btn btn-sm btn-out"
                      disabled={saving}
                      onClick={async () => {
                        setSaving(true);
                        try {
                          await api.resolveTimetableException(x.id);
                          await load();
                        } catch (e: any) {
                          setError(
                            e.message ||
                              "Unable to resolve readiness exception",
                          );
                        } finally {
                          setSaving(false);
                        }
                      }}
                    >
                      Resolve
                    </button>
                  )}
                {x.status !== "RESOLVED" &&
                  x.id &&
                  !data.readiness.can_decide && (
                    <span className="hint">View only</span>
                  )}
              </span>
            </div>
          ))}
          {!filteredReadinessExceptions.length && (
            <Empty text={readinessExceptions.length ? "No exceptions match your search" : "No readiness exceptions"} />
          )}
          </section>
        </div>
      )}
      {tab === "risk" && (
        <div className="dean-workspace dean-risk-workspace">
          <div className="dean-workspace-metrics">
            <div className="dean-workspace-metric danger"><span>Open academic risks</span><b>{data.risks.risks.length}</b><small>Across scoped departments</small></div>
            <div className="dean-workspace-metric warning"><span>Departments affected</span><b>{new Set(data.risks.risks.map((x: any) => x.scope_ref || x.department)).size}</b><small>Requires Dean attention</small></div>
            <div className="dean-workspace-metric"><span>Quality reviews</span><b>{data.reviews.reviews.length}</b><small>Active review records</small></div>
            <div className="dean-workspace-metric success"><span>Corrective actions</span><b>{data.actions.actions.length}</b><small>Track to closure</small></div>
          </div>
          <section className="card card-pad dean-workspace-table">
            <div className="card-h">
              <div><h3>Academic risk register</h3><p className="hint">Start with the largest performance deviations and move risks into a governed quality review.</p></div>
              <div className="row-actions"><button className="btn btn-sm btn-out" onClick={() => setTab("review")} type="button">Quality reviews</button><button className="btn btn-sm btn-crimson" onClick={() => setTab("action")} type="button">Corrective actions</button></div>
            </div>
            {filteredRisks.map((x: any, i: number) => (
              <div className="dean-workspace-row dean-risk-row" key={x.scope_ref || i}>
                <span><b>{x.department || "Academic scope"}</b><br /><small>{x.deviation || "Performance deviation requires review"}</small></span>
                <Pill s={x.severity || "OPEN"} />
                <button className="btn btn-sm btn-out" onClick={() => openRiskReview(x)} type="button">Review risk</button>
              </div>
            ))}
            {!filteredRisks.length && <Empty text={data.risks.risks.length ? "No risks match your search" : "No academic risks in the current scope"} />}
          </section>
        </div>
      )}
      {tab === "governance" && (
        <section className="card card-pad">
          <div className="card-h">
            <h3>Controlled versions</h3>
            <span className="hint">
              Approved records are published as immutable effective versions.
            </span>
          </div>
          {data.curriculumVersions.map((x: any) => (
            <div className="snap" key={x.id}>
              <span>
                <b>Curriculum · {x.effective_term}</b>
                <br />
                Version {x.version} · {x.course_count} courses
              </span>
              <Pill s={x.status} />
            </div>
          ))}
          {data.calendarVersions.map((x: any) => (
            <div className="snap" key={x.id}>
              <span>
                <b>Calendar · {x.term}</b>
                <br />
                Version {x.version}
              </span>
              <Pill s={x.status} />
            </div>
          ))}
          {!data.curriculumVersions.length && !data.calendarVersions.length && (
            <Empty text="No controlled versions" />
          )}
        </section>
      )}
      {tab === "delivery" && (
        <section className="card card-pad">
          <div className="card-h">
            <h3>Semester delivery monitoring</h3>
            <b>{data.delivery.actionable_exceptions} actionable exceptions</b>
          </div>
          {data.delivery.course_completions.map((x: any) => (
            <div className="snap" key={x.section_id}>
              <span>
                <b>Section {x.section_id}</b>
                <br />
                {x.completion_pct}% complete
              </span>
              <Pill s={x.status} />
            </div>
          ))}
          {data.conflicts.conflicts.slice(0, 6).map((x: any, i: number) => (
            <div className="snap" key={`${x.kind}-${i}`}>
              <span>
                <b>{x.kind.replace(/_/g, " ")}</b>
                <br />
                {x.message}
              </span>
              <Pill s="critical" />
            </div>
          ))}
          {!data.delivery.course_completions.length &&
            !data.conflicts.conflicts.length && (
              <Empty text="No delivery exceptions" />
            )}
        </section>
      )}
      {tab === "review" && (
        <section className="card card-pad">
          <div className="card-h">
            <div><h3>{reviewFocusId ? "Quality review for selected risk" : "Academic quality reviews"}</h3><span className="hint">Open → Investigate → Confirm root cause → Approve action plan → Assign and verify actions → Measure effectiveness → Close.</span></div>
            <div className="row-actions">{reviewFocusId && <button className="btn btn-sm btn-out" onClick={() => setReviewFocusId("")} type="button">Show all</button>}<button className="btn btn-crimson" onClick={() => open("review")}>Create review</button></div>
          </div>
          {filteredReviews.map((r: any) => (
            <div className="snap" key={r.id}>
              <span>
                <b>{r.title}</b>
                <br />
                {r.deviation || r.metric_key}
                {r.closure && r.state !== "CLOSED" && <><br /><small className={r.closure.can_close ? "quality-review-ready" : "quality-review-blocked"}>{r.closure.verified_action_count} of {r.closure.action_count} corrective actions verified · {r.closure.has_effectiveness_measurement ? "Effectiveness recorded" : "Effectiveness not recorded"}<br />{r.closure.message}</small></>}
              </span>
              <span className="row-actions">
                <Pill s={r.state} />
                {(reviewTransitions[r.state] || []).map(
                  ([target, label]: string[]) => target === "EFFECTIVENESS_REVIEW" && !r.closure?.can_enter_effectiveness ? (
                    <button key={target} className="btn btn-sm btn-out" disabled={saving} onClick={() => setTab("action")} title={r.closure?.message}>Open corrective actions</button>
                  ) : (
                    <button
                      key={target}
                      className={`btn btn-sm ${target === "CLOSED" ? "btn-crimson" : "btn-out"}`}
                      disabled={saving || (target === "CLOSED" && !r.closure?.can_close)}
                      title={target === "CLOSED" && !r.closure?.can_close ? r.closure?.message : undefined}
                      onClick={() => transitionReview(r, target)}
                    >
                      {label}
                    </button>
                  ),
                )}
                {r.state === "EFFECTIVENESS_REVIEW" && (
                  <button
                    className="btn btn-sm btn-out"
                    disabled={saving}
                    onClick={() => measureReview(r)}
                  >
                    Measure
                  </button>
                )}
              </span>
            </div>
          ))}
          {!filteredReviews.length && <Empty text={data.reviews.reviews.length ? "No reviews match your search" : "No quality reviews"} />}
        </section>
      )}
      {tab === "action" && (
        <section className="card card-pad">
          <div className="card-h">
            <div><h3>Corrective actions</h3><span className="hint">Owners submit evidence here; an authorized academic reviewer verifies it. The review advances only after every action is verified.</span></div>
            <button
              className="btn btn-crimson"
              disabled={!actionableReviews.length}
              title={
                !actionableReviews.length
                  ? "Approve an action plan before assigning actions"
                  : ""
              }
              onClick={() => open("action")}
            >
              Assign action
            </button>
          </div>
          {filteredActions.map((a: any) => (
            <div className="snap" key={a.id}>
              <span>
                <b>{a.title}</b>
                <br />
                {a.deadline || "No deadline"}<br /><small>Owner: {a.owner_id || "Not assigned"} · {a.state === "EVIDENCE_SUBMITTED" ? "Evidence awaiting verification" : a.state === "VERIFIED" ? "Evidence verified" : "Awaiting owner evidence"}</small>
              </span>
              <span className="row-actions">
                <Pill s={a.state} />
                {['OPEN', 'OVERDUE'].includes(a.state) && a.owner_id === currentUserId() && (
                  <button className="btn btn-sm btn-out" disabled={saving} onClick={() => openEvidenceSubmission(a)}>Submit evidence</button>
                )}
                {a.state === "EVIDENCE_SUBMITTED" && currentOfficeNumber() === 6 && (
                  <button
                    className="btn btn-sm btn-crimson"
                    disabled={saving}
                    onClick={() => openEvidenceVerification(a)}
                  >
                    Review evidence
                  </button>
                )}
                {a.state === "EVIDENCE_SUBMITTED" && currentOfficeNumber() !== 6 && <span className="hint">Submitted to Dean for verification</span>}
              </span>
            </div>
          ))}
          {!filteredActions.length && (
            <Empty text={data.actions.actions.length ? "No actions match your search" : "No corrective actions"} />
          )}
        </section>
      )}
      {tab === "committee" && <CommitteeGovernance />}
      {tab === "outcomes" && (
        <section className="card card-pad">
          <div className="card-h">
            <h3>CO/PO attainment</h3>
            <span className="hint">
              Calculated from mapped assessment evidence.
            </span>
          </div>
          <div className="tabs">
            {[
              "student",
              "section",
              "course",
              "program",
              "department",
              "semester",
            ].map((level) => (
              <button
                className={`tab ${attainmentLevel === level ? "on" : ""}`}
                key={level}
                onClick={() => refreshAttainment(level)}
              >
                {level}
              </button>
            ))}
          </div>
          <div className="kpi-grid">
            <div className="kpi">
              <div className="kpi-val">
                {data.attainment.course_outcomes?.length || 0}
              </div>
              <div className="kpi-label">Course outcomes</div>
            </div>
            <div className="kpi">
              <div className="kpi-val">
                {data.attainment.program_outcomes?.length || 0}
              </div>
              <div className="kpi-label">Program outcomes</div>
            </div>
          </div>
          {(
            attainmentData?.aggregates ||
            data.attainment.course_outcomes ||
            []
          ).map((x: any) => (
            <div className="snap" key={x.id}>
              <span>
                <b>{x.label || x.code}</b>
                <br />
                {x.description || `${x.evidence_count || 0} assessment marks`}
              </span>
              <Pill s={x.attainment == null ? "PENDING" : `${x.attainment}%`} />
            </div>
          ))}
        </section>
      )}
      {tab === "reports" && (
        <div className="dean-report-center">
          <div className="dean-report-summary">
            <div className="dean-report-stat"><span>Open quality reviews</span><b>{openQualityReviews}</b><small>Governed review records</small></div>
            <div className={`dean-report-stat ${openCorrectiveActions ? "warning" : "success"}`}><span>Actions in progress</span><b>{openCorrectiveActions}</b><small>Track to verification</small></div>
            <div className="dean-report-stat"><span>CO attainment</span><b>{averageAttainment == null ? "—" : `${averageAttainment}%`}</b><small>{attainmentValues.length ? "Current mapped evidence" : "No mapped evidence"}</small></div>
            <div className={`dean-report-stat ${(jobs?.dead_letter || 0) ? "danger" : "success"}`}><span>Job delivery health</span><b>{jobs?.dead_letter || 0}</b><small>Dead-letter jobs</small></div>
          </div>
          <div className="dean-report-layout">
            <section className="card dean-report-signal-panel">
              <div className="card-h"><div><h3>Academic signals</h3><p className="hint">The figures most likely to require a decision this week.</p></div><span className="dean-report-scope">Current scope</span></div>
              <div className="dean-report-signals">
                <button type="button" onClick={() => setTab("risk")}><span className="dean-report-signal-icon risk">!</span><span><b>{data.risks.risks.length} academic risks</b><small>Open across scoped departments</small></span><strong>View</strong></button>
                <button type="button" onClick={() => setTab("readiness")}><span className="dean-report-signal-icon warning">~</span><span><b>{readinessOpen.length} timetable exceptions</b><small>{readinessCritical} critical before publishing</small></span><strong>View</strong></button>
                <button type="button" onClick={() => setTab("delivery")}><span className="dean-report-signal-icon neutral">o</span><span><b>{data.delivery.actionable_exceptions} delivery exceptions</b><small>Sections needing follow-up</small></span><strong>View</strong></button>
              </div>
            </section>
            <section className="card dean-report-panel">
              <div className="card-h"><div><h3>Reporting operations</h3><p className="hint">Exports are generated from governed academic records.</p></div></div>
              <div className="dean-report-ops"><div><span>Report service</span><b className="is-healthy">Ready</b></div><div><span>Worker queue</span><b>{queuedJobs} queued</b></div><div><span>Last refresh</span><b>Just now</b></div></div>
            </section>
          </div>
          <section className="card dean-report-catalog">
            <div className="card-h"><div><h3>Report library</h3><p className="hint">Choose a decision-ready report and export it in the format your audience needs.</p></div><span className="dean-report-library-count">4 reports</span></div>
            <div className="dean-report-list">
              {[
                ["approval-aging", "Approval aging", "Pending decisions grouped by age and workflow stage.", "Governance"],
                ["quality-action-aging", "Quality action aging", "Open corrective actions, owners, and time to closure.", "Quality"],
                ["co-po-attainment", "CO / PO attainment", "Outcome attainment from mapped assessment evidence.", "Outcomes"],
                ["semester-comparison", "Semester comparison", "Compare delivery, quality, and academic indicators by term.", "Planning"],
              ].map(([name, title, description, group]) => (
                <div className="dean-report-item" key={name}>
                  <span className="dean-report-file-icon">=</span>
                  <span className="dean-report-item-copy"><b>{title}</b><small>{description}</small></span>
                  <span className="dean-report-item-group">{group}</span>
                  <span className="row-actions dean-report-formats">
                    {["csv", "pdf", "xlsx"].map((format) => <button key={format} className="btn btn-sm btn-out" disabled={saving} onClick={() => exportReport(name, format)}>{format.toUpperCase()}</button>)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
      {tab === "planning" && (
        <section className="card card-pad">
          <div className="card-h">
            <h3>Next-semester plans</h3>
            <span className="hint">
              Quality findings and resource decisions carried into the next
              semester.
            </span>
          </div>
          {data.plans.map((p: any) => (
            <div className="snap" key={p.id}>
              <span>
                <b>{p.title || p.semester || p.id}</b>
                <br />
                {p.state || p.status || "DRAFT"} · {p.scope_ref || "Institution scope"}
              </span>
              <Pill s={p.state || p.status || "DRAFT"} />
            </div>
          ))}
          {!data.plans.length && <Empty text="No next-semester plans" />}
        </section>
      )}
      {show && (
        <Modal
          className={tab === "review" ? "quality-review-modal" : ""}
          title={
            tab === "allocation"
              ? "Propose Faculty Allocation"
              : tab === "review"
                ? (riskReviewContext ? `Review academic risk — ${riskReviewContext.department || "Academic scope"}` : "Create Quality Review")
                : "Assign Corrective Action"
          }
          onClose={() => { setShow(false); if (riskReviewContext) setTab("risk"); setRiskReviewContext(null); }}
          footer={
            <>
              <button className="btn btn-out" onClick={() => { setShow(false); if (riskReviewContext) setTab("risk"); setRiskReviewContext(null); }}>
                Cancel
              </button>
              <button
                className="btn btn-crimson"
                disabled={saving}
                onClick={
                  tab === "allocation"
                    ? allocation
                    : tab === "review"
                      ? review
                      : action
                }
              >
                {saving ? "Saving..." : "Save"}
              </button>
            </>
          }
        >
          {tab === "allocation" ? (
            <>
              <Field label="Section">
                <select
                  className="select"
                  value={form.section_id}
                  onChange={(e) =>
                    setForm({ ...form, section_id: e.target.value })
                  }
                >
                  {data.sections.map((x: any) => (
                    <option key={x.id} value={x.id}>
                      {x.course_code} · {x.section}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Faculty">
                <select
                  className="select"
                  value={form.faculty_person_id}
                  onChange={(e) =>
                    setForm({ ...form, faculty_person_id: e.target.value })
                  }
                >
                  {data.staff.map((x: any) => (
                    <option key={x.id} value={x.id}>
                      {x.name}
                    </option>
                  ))}
                </select>
              </Field>
            </>
          ) : (
            <>
              <Field label="Title">
                <input
                  className="inp"
                  value={form.title}
                  readOnly={!!riskReviewContext}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                />
              </Field>
              {riskReviewContext && <div className="form-row"><label>Detected risk</label><div className="inp">{riskReviewContext.deviation}<br /><small>{riskReviewContext.severity} severity · Current value: {riskReviewContext.metric_value ?? "N/A"} · Threshold: {riskReviewContext.threshold ?? "N/A"}</small></div></div>}
              <Field label="Owner user ID">
                <input
                  className="inp"
                  value={form.owner_id}
                  onChange={(e) =>
                    setForm({ ...form, owner_id: e.target.value })
                  }
                />
              </Field>
              {tab === "action" ? (
                <>
                  <Field label="Review">
                    <select
                      className="select"
                      value={form.review_id}
                      onChange={(e) =>
                        setForm({ ...form, review_id: e.target.value })
                      }
                    >
                      {actionableReviews.map((x: any) => (
                        <option key={x.id} value={x.id}>
                          {x.title}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Deadline">
                    <input
                      className="inp"
                      type="datetime-local"
                      value={form.deadline}
                      onChange={(e) =>
                        setForm({ ...form, deadline: e.target.value })
                      }
                    />
                  </Field>
                </>
              ) : (
                <>
                  <Field label="Deviation">
                    <textarea
                      className="inp"
                      value={form.deviation}
                      onChange={(e) =>
                        setForm({ ...form, deviation: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Root cause">
                    <textarea
                      className="inp"
                      value={form.root_cause}
                      onChange={(e) =>
                        setForm({ ...form, root_cause: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Due date">
                    <input className="inp" type="datetime-local" value={form.due_at || ""} onChange={(e) => setForm({ ...form, due_at: e.target.value })} />
                  </Field>
                  <Field label="Effectiveness measure">
                    <input className="inp" value={form.effectiveness_measure || ""} placeholder="Example: Average CGPA reaches 6.5 or higher" onChange={(e) => setForm({ ...form, effectiveness_measure: e.target.value })} />
                  </Field>
                </>
              )}
            </>
          )}
        </Modal>
      )}
      {evidenceAction && (
        <Modal
          className="quality-evidence-modal"
          title="Submit corrective-action evidence"
          onClose={() => { if (!saving) { setEvidenceAction(null); setEvidenceError(""); } }}
          footer={<><button className="btn btn-out" disabled={saving} onClick={() => { setEvidenceAction(null); setEvidenceError(""); }}>Cancel</button><button className="btn btn-crimson" disabled={saving || !evidenceText.trim()} onClick={submitEvidence}>{saving ? "Submitting..." : "Submit evidence"}</button></>}
        >
          <div className="evidence-action-context"><span>Corrective action</span><b>{evidenceAction.title}</b><small>Due {formatWorkspaceDate(evidenceAction.deadline)} · You are submitting as the assigned owner.</small></div>
          <Field label="Completion evidence">
            <textarea className="inp evidence-textarea" rows={6} value={evidenceText} placeholder="Summarize the completed work and include verifiable references, such as a document URL, meeting record, attendance register, report number, or repository path." onChange={(event) => { setEvidenceText(event.target.value); setEvidenceError(""); }} />
          </Field>
          <p className="hint evidence-guidance">Include what was completed, when it was completed, the outcome, and a reference that the Dean can verify. Submitted evidence becomes part of the action audit trail.</p>
          {evidenceError && <div className="calendar-banner warn">{evidenceError}</div>}
        </Modal>
      )}
      {verificationAction && (
        <Modal
          className="quality-evidence-modal"
          title="Review corrective-action evidence"
          onClose={() => { if (!saving) { setVerificationAction(null); setVerificationError(""); } }}
          footer={<><button className="btn btn-out" disabled={saving} onClick={() => { setVerificationAction(null); setVerificationError(""); }}>Cancel</button><button className="btn btn-crimson" disabled={saving || !verificationNote.trim()} onClick={verify}>{saving ? "Verifying..." : "Verify evidence"}</button></>}
        >
          <div className="evidence-action-context"><span>Corrective action</span><b>{verificationAction.title}</b><small>Submitted by {verificationAction.owner_id} · Review the supplied evidence before verification.</small></div>
          <div className="form-row"><label>Submitted evidence</label><div className="inp evidence-readonly">{verificationAction.evidence}</div></div>
          <Field label="Verification note"><textarea className="inp evidence-textarea" rows={4} value={verificationNote} placeholder="State what you checked and why the evidence is accepted." onChange={(event) => { setVerificationNote(event.target.value); setVerificationError(""); }} /></Field>
          {verificationError && <div className="calendar-banner warn">{verificationError}</div>}
        </Modal>
      )}
    </div>
  );
}
function currentUserId() {
  try {
    return JSON.parse(localStorage.getItem("icms_user") || "{}").id || "";
  } catch {
    return "";
  }
}

function currentOfficeNumber() {
  try {
    return Number(JSON.parse(localStorage.getItem("icms_user") || "{}").office_n || 0);
  } catch {
    return 0;
  }
}

function formatWorkspaceDate(value: string | null | undefined) {
  if (!value) return "recently";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "recently" : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
function Field({ label, children }: any) {
  return (
    <div className="form-row">
      <label>{label}</label>
      {children}
    </div>
  );
}
