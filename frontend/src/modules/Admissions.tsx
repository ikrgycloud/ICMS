import { useEffect, useState } from "react";
import { api } from "../api";
import { PageHead, Spinner, DecisionToast, Modal } from "./kit";
import EligibilityDetailView from "./EligibilityDetailView";

const fresh = {
  name: "",
  academic_year: "",
  campus: "",
  application_open_date: "",
  application_close_date: "",
  status: "DRAFT",
  configuration: {},
};
const emptyRule = {
  cycle_id: "",
  program_id: "",
  quota_code: "",
  rule_key: "FIELD_COMPARISON",
  field: "",
  operator: ">=",
  value: "",
  document_type: "",
  active: true,
};
const emptyQuota = {
  cycle_id: "",
  program_id: "",
  code: "",
  name: "",
  category_code: "",
  description: "",
  priority: 0,
  active: true,
};

export default function Admissions({
  caps,
  initialTab,
  sidebarNavigation = false,
  directorMode = false,
}: {
  caps: any;
  initialTab?: string;
  sidebarNavigation?: boolean;
  directorMode?: boolean;
}) {
  const [apps, setApps] = useState<any>(null),
    [tab, setTab] = useState("applications");
  const [cycles, setCycles] = useState<any[]>([]),
    [programmes, setProgrammes] = useState<any[]>([]),
    [queue, setQueue] = useState<any[]>([]),
    [corrections, setCorrections] = useState<any[]>([]);
  const [notice, setNotice] = useState<any>(null),
    [cycle, setCycle] = useState<any>(null),
    [detail, setDetail] = useState<any>(null);
  const [documentPreview, setDocumentPreview] = useState<any>(null);
  const [binding, setBinding] = useState<any>({}),
    [search, setSearch] = useState("");
  const [eligibility, setEligibility] = useState<any[]>([]),
    [filters, setFilters] = useState<any>({
      cycle_id: "",
      program_id: "",
      campus: "",
      status: "",
      quota_code: "",
      search: "",
    });
  const [rules, setRules] = useState<any[]>([]),
    [quotas, setQuotas] = useState<any[]>([]),
    [rule, setRule] = useState<any>(null),
    [quota, setQuota] = useState<any>(null),
    [eligibilityDetail, setEligibilityDetail] = useState<any>(null);
  const [phase4, setPhase4] = useState<any[]>([]),
    [seatPools, setSeatPools] = useState<any[]>([]);
  const [counselling, setCounselling] = useState<any[]>([]),
    [assessment, setAssessment] = useState<any>(null),
    [counsellingItem, setCounsellingItem] = useState<any>(null);
  const [waitlist, setWaitlist] = useState<any[]>([]),
    [offers, setOffers] = useState<any[]>([]),
    [offerStatus, setOfferStatus] = useState("");
  const [programIntake, setProgramIntake] = useState<any[]>([]),
    [documentStatus, setDocumentStatus] = useState<any[]>([]),
    [phase5Status, setPhase5Status] = useState<any[]>([]),
    [finalApprovals, setFinalApprovals] = useState<any[]>([]);
  const [directorData, setDirectorData] = useState<any>({
    offers: [],
    pools: [],
    counselling: [],
    phase5: [],
  });
  const [seatPool, setSeatPool] = useState<any>(null);
  const [correctionDialog, setCorrectionDialog] = useState<any>(null);
  const [paymentDialog, setPaymentDialog] = useState<any>(null);
  useEffect(() => {
    if (initialTab) setTab(initialTab);
  }, [initialTab]);
  const manage = !!caps.manage_cycle;
  const loadApps = () =>
    api
      .applications()
      .then(setApps)
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadCycles = () => {
    api.admissionCycles().then((x: any) => setCycles(x.cycles || []));
    api
      .admissionProgrammes()
      .then((x: any) => setProgrammes(x.programmes || []));
    api
      .admissionProgramIntake()
      .then((x: any) => setProgramIntake(x.program_intake || []));
  };
  const loadQueue = () =>
    api
      .admissionReviewQueue(search ? { search } : {})
      .then((x: any) => setQueue(x.applications || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadCorrections = () =>
    api
      .admissionCorrections()
      .then((x: any) => setCorrections(x.applications || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadEligibility = () =>
    api
      .eligibilityQueue(filters)
      .then((x: any) => setEligibility(x.applications || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadRules = () =>
    api
      .eligibilityRules(filters.cycle_id)
      .then((x: any) => setRules(x.rules || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadQuotas = () =>
    api
      .eligibilityQuotas(filters.cycle_id)
      .then((x: any) => setQuotas(x.quotas || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadPhase4 = () => {
    api
      .assessmentQueue()
      .then((x: any) => setPhase4(x.applications || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
    api
      .admissionSeatPools(filters.cycle_id)
      .then((x: any) => setSeatPools(x.seat_pools || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  };
  const loadCounselling = () =>
    api
      .counsellingQueue({
        cycle_id: filters.cycle_id,
        program_id: filters.program_id,
      })
      .then((x: any) => setCounselling(x.applications || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadWaitlist = () =>
    api
      .admissionWaitlist()
      .then((x: any) => setWaitlist(x.waitlist || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadOffers = () =>
    api
      .admissionOffers(offerStatus)
      .then((x: any) => setOffers(x.offers || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadProgramIntake = () =>
    api
      .admissionProgramIntake()
      .then((x: any) => setProgramIntake(x.program_intake || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadDocumentStatus = () =>
    api
      .admissionDocumentStatus()
      .then((x: any) => setDocumentStatus(x.documents || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadPhase5Status = () =>
    api
      .admissionPhase5Status()
      .then((x: any) => setPhase5Status(x.applications || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadFinalApprovals = () =>
    api
      .admissionFinalApprovals()
      .then((x: any) => setFinalApprovals(x.final_approvals || []))
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const loadDirectorData = () =>
    api
      .admissionDirectorMonitoring()
      .then((x: any) => {
        const states: any = {
          ISSUED: "OFFERED",
          ACCEPTED: "OFFER_ACCEPTED",
          DECLINED: "OFFER_DECLINED",
          EXPIRED: "OFFER_EXPIRED",
        };
        setDirectorData({
          offers: (x.offers || []).map((offer: any) => ({
            ...offer,
            current_status: states[offer.status] || offer.status,
          })),
          pools: (x.seat_pools || []).map((pool: any) => ({
            ...pool,
            used: pool.active,
            program_name: pool.program,
            quota_name: pool.quota,
          })),
          counselling: x.counselling || [],
        });
      })
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  useEffect(() => {
    void loadApps();
  }, []);
  useEffect(() => {
    if (tab === "cycles") loadCycles();
    if (tab === "corrections") loadCorrections();
    if (tab === "review") loadQueue();
    if (tab === "program_intake") loadProgramIntake();
    if (tab === "document_status") loadDocumentStatus();
    if (tab === "final_approval") loadFinalApprovals();
    if (tab.startsWith("director_")) loadDirectorData();
    if (
      [
        "finance_status",
        "invoices_challans",
        "payment_status",
        "accounts_verification",
        "clearance_status",
        "ready_to_admit",
        "enrollment_queue",
        "student_conversion",
        "enrollment_status",
        "reports",
        "final_approval",
      ].includes(tab)
    )
      loadPhase5Status();
    if (["recommendations", "issued_offers"].includes(tab)) loadOffers();
    if (
      [
        "eligibility",
        "rules",
        "quotas",
        "decisions",
        "counselling",
        "seatpools",
        "waitlist",
        "offers",
      ].includes(tab)
    ) {
      loadCycles();
      if (tab === "eligibility") loadEligibility();
      if (tab === "rules") {
        loadRules();
        loadQuotas();
      }
      if (tab === "quotas") loadQuotas();
      if (tab === "decisions") loadPhase4();
      if (tab === "counselling") loadCounselling();
      if (tab === "seatpools") loadPhase4();
      if (tab === "waitlist") loadWaitlist();
      if (tab === "offers") loadOffers();
    }
  }, [tab]);
  const act = async (fn: () => Promise<any>, reload: () => void = loadApps) => {
    try {
      const r = await fn();
      setNotice(
        r.decision || { outcome: "ALLOW", reason: "Saved successfully" },
      );
      reload();
    } catch (e: any) {
      setNotice({ outcome: "DENY", reason: e.message });
    }
  };
  const runPhase5Action = (action: string, row: any) => {
    const expected = row.status_version;
    const request: Record<string, () => Promise<any>> = {
      resolve: () => api.resolveAdmissionFees(row.id, expected),
      invoice: () => api.issueAdmissionInvoice(row.id, expected),
      verify: () => api.verifyAdmissionPayment(row.id, row.payment_id, { expected_status_version: expected, status: "VERIFIED" }),
      clear: () => api.clearAdmissionFinance(row.id, expected),
      request_final: () => api.requestAdmissionFinalApproval(row.id, expected),
      complete_final: () => api.completeAdmissionFinalApproval(row.id, expected),
      convert: () => api.convertAdmission(row.id, expected),
    };
    if (action === "payment") {
      setPaymentDialog({ row, amount: String(row.balance || row.invoice_amount || ""), reference: "", method: "challan" });
      return;
    }
    act(request[action], loadPhase5Status);
  };
  const submitAdmissionPayment = () => {
    const payment = paymentDialog;
    const amount = Number(payment?.amount);
    if (!amount || amount <= 0 || !payment?.reference?.trim()) {
      setNotice({ outcome: "DENY", reason: "Enter a valid payment amount and payment reference." });
      return;
    }
    act(
      () => api.recordAdmissionPayment(payment.row.id, { expected_status_version: payment.row.status_version, amount, reference: payment.reference.trim(), method: payment.method, challan_id: payment.row.challan_id }),
      () => { setPaymentDialog(null); loadPhase5Status(); },
    );
  };
  const submitCorrection = () => {
    const request = correctionDialog;
    const reason = request?.reason?.trim();
    if (!reason) {
      setNotice({ outcome: "DENY", reason: "Describe the corrections required for the applicant." });
      return;
    }
    act(
      () => api.admissionAction(request.applicationId, "request_correction", request.statusVersion, reason),
      () => {
        setCorrectionDialog(null);
        setDetail(null);
        loadQueue();
        loadApps();
      },
    );
  };
  const saveCycle = () =>
    act(async () => {
      const body = {
        ...cycle,
        application_open_date: cycle.application_open_date
          ? new Date(cycle.application_open_date).toISOString()
          : null,
        application_close_date: cycle.application_close_date
          ? new Date(cycle.application_close_date).toISOString()
          : null,
      };
      const r = cycle.id
        ? await api.updateAdmissionCycle(cycle.id, body)
        : await api.createAdmissionCycle(body);
      setCycle(null);
      return r;
    }, loadCycles);
  const saveRule = () =>
    act(async () => {
      const criteria =
        rule.rule_key === "REQUIRED_DOCUMENT"
          ? { rule_type: rule.rule_key, document_type: rule.document_type }
          : {
              rule_type: rule.rule_key,
              field: rule.field,
              operator: rule.operator,
              value: rule.value,
            };
      const body = {
        cycle_id: rule.cycle_id,
        program_id: rule.program_id || null,
        quota_code: rule.quota_code,
        rule_key: rule.rule_key,
        criteria,
        active: rule.active,
      };
      const r = rule.id
        ? await api.updateEligibilityRule(rule.id, body)
        : await api.createEligibilityRule(body);
      setRule(null);
      return r;
    }, loadRules);
  const saveQuota = () =>
    act(async () => {
      const body = {
        ...quota,
        program_id: quota.program_id || null,
        priority: Number(quota.priority || 0),
      };
      const r = quota.id
        ? await api.updateEligibilityQuota(quota.id, body)
        : await api.createEligibilityQuota(body);
      setQuota(null);
      return r;
    }, loadQuotas);
  const openEligibilityDetail = (id: string) =>
    api
      .eligibilityDetail(id)
      .then(setEligibilityDetail)
      .catch((e) => setNotice({ outcome: "DENY", reason: e.message }));
  const editRule = (r: any) =>
    setRule({
      ...r,
      field: r.criteria?.field || "",
      operator: r.criteria?.operator || ">=",
      value: r.criteria?.value ?? "",
      document_type: r.criteria?.document_type || r.criteria?.value || "",
    });
  if (!apps) return <Spinner />;
  return (
    <div className="fade-in">
      <PageHead
        title="Admissions"
        sub="Cycles, applications, review and eligibility"
        right={
          tab === "cycles" && manage ? (
            <button
              className="btn btn-brass"
              onClick={() => setCycle({ ...fresh })}
            >
              Create cycle
            </button>
          ) : undefined
        }
      />
      {!sidebarNavigation && (
        <div className="tabs">
          <button
            className={`tab ${tab === "applications" ? "on" : ""}`}
            onClick={() => setTab("applications")}
          >
            Applications
          </button>
          <button
            className={`tab ${tab === "review" ? "on" : ""}`}
            onClick={() => setTab("review")}
          >
            Review Queue
          </button>
          <button
            className={`tab ${tab === "cycles" ? "on" : ""}`}
            onClick={() => setTab("cycles")}
          >
            Admission Cycles
          </button>
          {caps.view_eligibility && (
            <>
              <button
                className={`tab ${tab === "eligibility" ? "on" : ""}`}
                onClick={() => setTab("eligibility")}
              >
                Eligibility
              </button>
              <button
                className={`tab ${tab === "rules" ? "on" : ""}`}
                onClick={() => setTab("rules")}
              >
                Eligibility Rules
              </button>
              <button
                className={`tab ${tab === "quotas" ? "on" : ""}`}
                onClick={() => setTab("quotas")}
              >
                Quotas
              </button>
              <button
                className={`tab ${tab === "decisions" ? "on" : ""}`}
                onClick={() => setTab("decisions")}
              >
                Assessments / Allocation
              </button>
              <button
                className={`tab ${tab === "counselling" ? "on" : ""}`}
                onClick={() => setTab("counselling")}
              >
                Counselling
              </button>
              <button
                className={`tab ${tab === "seatpools" ? "on" : ""}`}
                onClick={() => setTab("seatpools")}
              >
                Seat Pools
              </button>
              <button
                className={`tab ${tab === "waitlist" ? "on" : ""}`}
                onClick={() => setTab("waitlist")}
              >
                Waitlist
              </button>
              <button
                className={`tab ${tab === "offers" ? "on" : ""}`}
                onClick={() => setTab("offers")}
              >
                Offers
              </button>
            </>
          )}
        </div>
      )}
      {tab === "applications" && (
        <div className="card">
          <div className="tbl-scroll">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Applicant</th>
                  <th>Programme</th>
                  <th>Canonical status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {apps.applications.map((a: any) => (
                  <tr key={a.id}>
                    <td>
                      <b>{a.name}</b>
                      <div className="hint">{a.email}</div>
                    </td>
                    <td>{a.program}</td>
                    <td>
                      <span
                        className={`pill s-${String(a.current_status || a.status).toLowerCase()}`}
                      >
                        {a.current_status || a.status}
                      </span>
                    </td>
                    <td>
                      {!directorMode && a.current_status === "SUBMITTED" && (
                        <button
                          className="btn btn-sm btn-out"
                          disabled={!caps.verify}
                          onClick={() =>
                            act(() => api.decideApplication(a.id, "verify"))
                          }
                        >
                          Verify
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {tab === "corrections" && (
        <div className="card">
          <div className="card-pad">
            <h3>Corrections</h3>
            <p className="hint">
              Applications requiring applicant correction or awaiting review
              after resubmission.
            </p>
            <div className="tbl-scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Applicant</th>
                    <th>Programme</th>
                    <th>Required corrections</th>
                    <th>Current status</th>
                  </tr>
                </thead>
                <tbody>
                  {corrections.map((a: any) => {
                      return (
                        <tr key={a.id}>
                          <td>
                            <b>{a.applicant_name}</b>
                            <div className="hint">{a.email}</div>
                          </td>
                          <td>{a.program}</td>
                          <td>
                            {a.correction_reason}
                          </td>
                          <td>
                            <span
                              className={`pill s-${String(a.current_status).toLowerCase()}`}
                            >
                              {a.current_status}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      {tab === "review" && (
        <>
          <div className="card" style={{ marginBottom: 12 }}>
            <div className="card-pad">
              <input
                className="inp"
                placeholder="Search applicant or application no."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <button className="btn btn-out" onClick={loadQueue}>
                Apply
              </button>
            </div>
          </div>
          <div className="card">
            <div className="tbl-scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Application</th>
                    <th>Applicant</th>
                    <th>Cycle</th>
                    <th>Documents</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {queue.map((a) => (
                    <tr
                      key={a.id}
                      style={{ cursor: "pointer" }}
                      onClick={() =>
                        api
                          .admissionDetail(a.id)
                          .then(setDetail)
                          .catch((e) =>
                            setNotice({ outcome: "DENY", reason: e.message }),
                          )
                      }
                    >
                      <td className="mono">{a.application_no}</td>
                      <td>{a.applicant_name}</td>
                      <td>{a.cycle}</td>
                      <td>
                        {a.documents.uploaded}/{a.documents.required}
                      </td>
                      <td>
                        <span
                          className={`pill s-${String(a.current_status).toLowerCase()}`}
                        >
                          {a.current_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
      {tab === "eligibility" && (
        <EligibilityQueue
          eligibility={eligibility}
          filters={filters}
          setFilters={setFilters}
          cycles={cycles}
          programmes={programmes}
          programIntake={programIntake}
          load={loadEligibility}
          detail={openEligibilityDetail}
          act={act}
        />
      )}
      {tab === "rules" && (
        <ConfigList
          title="Eligibility Rules"
          items={rules}
          cycles={cycles}
          programmes={programmes}
          cycleId={filters.cycle_id}
          setCycleId={(v: string) => setFilters({ ...filters, cycle_id: v })}
          reload={loadRules}
          canManage={!!caps.manage_eligibility_rules}
          create={() => setRule({ ...emptyRule, cycle_id: filters.cycle_id })}
          edit={editRule}
          kind="rule"
        />
      )}
      {tab === "quotas" && (
        <ConfigList
          title="Quotas"
          items={quotas}
          cycles={cycles}
          programmes={programmes}
          cycleId={filters.cycle_id}
          setCycleId={(v: string) => setFilters({ ...filters, cycle_id: v })}
          reload={loadQuotas}
          canManage={!!caps.manage_quotas}
          create={() => setQuota({ ...emptyQuota, cycle_id: filters.cycle_id })}
          edit={setQuota}
          kind="quota"
        />
      )}
      {tab === "decisions" && (
        <div className="card">
          <div className="card-pad">
            <h3>Assessment, Merit & Allocation</h3>
            <p className="hint">
              All scores, merit and seat availability are calculated by the
              backend.
            </p>
            <div className="tbl-scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Application</th>
                    <th>Status</th>
                    <th>Merit</th>
                    <th>Next step</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {phase4.map((a) => (
                    <tr key={a.id}>
                      <td>
                        {a.name}
                        <div className="hint">{a.program}</div>
                      </td>
                      <td>{a.current_status}</td>
                      <td>{a.merit_score == null ? "Not calculated" : `${a.merit_score} (Rank #${a.merit_rank || "-"})`}</td>
                      <td className="hint">{a.current_status === "ELIGIBLE" ? "Advance to the programme's required assessment, counselling, or allocation stage." : a.current_status === "ASSESSMENT_PENDING" ? "Record the verified entrance assessment." : a.current_status === "ASSESSMENT_QUALIFIED" ? "Continue to the programme's required counselling or seat allocation stage." : a.current_status === "COUNSELLING_PENDING" ? "Complete counselling before seat allocation." : a.current_status === "ALLOCATION_PENDING" ? "Choose an available seat pool for which this applicant is eligible." : "Continue according to the current admission status."}</td>
                      <td>
                        {["ELIGIBLE", "ASSESSMENT_QUALIFIED"].includes(a.current_status) && (
                          <button
                            className="btn btn-sm btn-out"
                            onClick={() =>
                              act(
                                async () => {
                                  const result = await api.advanceAdmissionPhase4(a.id, a.status_version);
                                  return { decision: { outcome: "ALLOW", reason: `Advanced to ${String(result.current_status || "next stage").replaceAll("_", " ")}.` } };
                                },
                                loadPhase4,
                              )
                            }
                          >
                            Advance
                          </button>
                        )}
                        {a.current_status === "ASSESSMENT_PENDING" && (
                          <button
                            className="btn btn-sm btn-brass"
                            onClick={() =>
                              setAssessment({
                                ...a,
                                assessment_type: "ENTRANCE_EXAM",
                                score: "",
                                max_score: "",
                              })
                            }
                          >
                            Record assessment
                          </button>
                        )}
                        {[
                          "ELIGIBLE",
                          "ASSESSMENT_PENDING",
                          "ASSESSMENT_QUALIFIED",
                          "COUNSELLING_PENDING",
                          "ALLOCATION_PENDING",
                        ].includes(a.current_status) && (
                          <button
                            className="btn btn-sm btn-out"
                            onClick={() =>
                              act(
                                async () => {
                                  const result = await api.calculateAdmissionMerit(a.id);
                                  return { decision: { outcome: "ALLOW", reason: `Merit calculated: score ${result.merit_score}, rank #${result.rank}.` } };
                                },
                                loadPhase4,
                              )
                            }
                          >
                            Merit
                          </button>
                        )}
                        {a.current_status === "ALLOCATION_PENDING" &&
                          seatPools
                            .filter(
                              (p) =>
                                p.cycle_id === a.cycle_id &&
                                p.campus === a.campus &&
                                p.program_id === a.program_id &&
                                String(p.status).toLowerCase() === "open" &&
                                p.available > 0 &&
                                (!p.quota_id ||
                                  (a.qualified_quota_ids || []).includes(
                                    p.quota_id,
                                  )),
                            )
                            .map((p) => (
                              <button
                                key={p.id}
                                className="btn btn-sm btn-brass"
                                onClick={() =>
                                  act(
                                    () =>
                                      api.allocateAdmissionSeat(a.id, {
                                        seat_pool_id: p.id,
                                        expected_status_version:
                                          a.status_version,
                                      }),
                                    loadPhase4,
                                  )
                                }
                              >
                                Allocate {p.quota_name || "General"}
                              </button>
                            ))}
                        {a.current_status === "ALLOCATION_PENDING" && !seatPools.some((p) => p.cycle_id === a.cycle_id && p.campus === a.campus && p.program_id === a.program_id && String(p.status).toLowerCase() === "open" && p.available > 0 && (!p.quota_id || (a.qualified_quota_ids || []).includes(p.quota_id))) && (
                          <span className="hint">
                            {(() => {
                              const matching = seatPools.filter((p) => p.cycle_id === a.cycle_id && p.campus === a.campus && p.program_id === a.program_id);
                              if (!matching.length) return "No seat pool is configured for this applicant's cycle, programme, and campus. Create a General pool with the same values.";
                              if (!matching.some((p) => String(p.status).toLowerCase() === "open")) return "A matching seat pool exists, but it is inactive. Edit it and set its status to Active.";
                              if (!matching.some((p) => p.available > 0)) return "All matching seat pools are full. Increase capacity only if more approved intake is available, or use the waitlist.";
                              return "Matching seats are quota-restricted. Create a General pool or ensure the applicant passes eligibility for the selected quota.";
                            })()}
                            {" "}<button className="btn btn-sm btn-out" onClick={() => setTab("seatpools")}>Configure seat pool</button>
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      {tab === "counselling" && (
        <div className="card">
          <div className="card-pad">
            <h3>Counselling Queue</h3>
            <div className="tbl-scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Applicant</th>
                    <th>Programme</th>
                    <th>Merit</th>
                    <th>Preferences</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {counselling.map((a) => (
                    <tr key={a.id}>
                      <td>{a.name}</td>
                      <td>{a.program}</td>
                      <td>
                        {a.merit_score ?? "Not calculated"}{" "}
                        {a.merit_rank ? `· #${a.merit_rank}` : ""}
                      </td>
                      <td>
                        {a.preferences
                          ?.map((p: any) => `#${p.rank}`)
                          .join(", ") || "—"}
                      </td>
                      <td>
                        <button
                          className="btn btn-sm btn-out"
                          onClick={() =>
                            setCounsellingItem({
                              ...a,
                              attendance_status: "attended",
                              remarks: "",
                              preference_rank: 1,
                            })
                          }
                        >
                          Record outcome
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      {tab === "seatpools" && (
        <div className="card">
          <div className="card-pad">
            <h3>Seat Pools</h3>
            <p className="hint">Create one open General pool for each programme and campus before allocating applicants. Add a quota pool only when that quota has its own capacity.</p>
            {caps.manage_seat_pool && (
              <button
                className="btn btn-brass"
                onClick={() =>
                  setSeatPool({
                    cycle_id: filters.cycle_id,
                    campus: "",
                    program_id: "",
                    quota_id: "",
                    capacity: 0,
                    status: "open",
                  })
                }
              >
                Create seat pool
              </button>
            )}
            <div className="tbl-scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Campus</th>
                    <th>Programme</th>
                    <th>Quota</th>
                    <th>Capacity</th>
                    <th>Reserved / allocated</th>
                    <th>Available</th>
                    <th>Waitlisted</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {seatPools.map((p) => (
                    <tr key={p.id}>
                      <td>{p.campus}</td>
                      <td>
                        {programmes.find((x: any) => x.id === p.program_id)
                          ?.name || p.program_id}
                      </td>
                      <td>{p.quota_id || "General"}</td>
                      <td>{p.capacity}</td>
                      <td>{p.used}</td>
                      <td>{p.available}</td>
                      <td>{p.waitlisted}</td>
                      <td>{p.status}</td>
                      <td>
                        <button
                          className="btn btn-sm btn-out"
                          onClick={() => setSeatPool({ ...p })}
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                  {seatPools.length === 0 && (
                    <tr>
                      <td colSpan={9} className="hint">No seat pools are configured for this cycle. Use Create seat pool to add the available intake.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      {tab === "waitlist" && (
        <div className="card">
          <div className="card-pad">
            <h3>Waitlist</h3>
            <div className="tbl-scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Application</th>
                    <th>Applicant</th>
                    <th>Pool</th>
                    <th>Merit rank</th>
                    <th>Position</th>
                    <th>Round</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {waitlist.map((x) => (
                    <tr key={x.id}>
                      <td>{x.application_no}</td>
                      <td>{x.applicant_name}</td>
                      <td className="mono">{x.seat_pool_id}</td>
                      <td>{x.rank ?? "—"}</td>
                      <td>{x.position}</td>
                      <td>{x.round_no}</td>
                      <td>{x.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      {tab === "offers" && (
        <div className="card">
          <div className="card-pad">
            <h3>Offers</h3>
            <p className="hint">Allocated applicants appear here. Send offer issues it immediately. Issued offers appear in the Applicant Portal with their expiry date and Accept / Decline actions.</p>
            <select
              className="inp"
              value={offerStatus}
              onChange={(e) => {
                setOfferStatus(e.target.value);
                setTimeout(loadOffers, 0);
              }}
            >
              <option value="">All offer states</option>
              {[ 
                "ALLOCATED",
                "OFFER_RECOMMENDATION_PENDING",
                "OFFER_APPROVAL_PENDING",
                "OFFERED",
                "OFFER_ACCEPTED",
                "OFFER_DECLINED",
                "OFFER_EXPIRED",
              ].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
            <div className="tbl-scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Applicant</th>
                    <th>Programme</th>
                    <th>State</th>
                    <th>Workflow</th>
                    <th>Offer</th>
                    <th>Joining requests</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {offers.map((a) => (
                    <tr key={a.id}>
                      <td>{a.name}</td>
                      <td>{a.program}</td>
                      <td>{a.current_status}</td>
                      <td>{a.workflow_state || "—"}</td>
                      <td>
                        {a.offer_no || "Not issued"}
                        <div className="hint">{a.expires_at?.slice(0, 10)}</div>
                      </td>
                      <td>
                        {a.joining_preferences?.submitted_at ? <><div>Hostel: {a.joining_preferences.hostel_required ? "Requested" : "Not required"}</div><div>Transport: {a.joining_preferences.transport_required ? `Requested${a.joining_preferences.pickup_point ? ` (${a.joining_preferences.pickup_point})` : ""}` : "Not required"}</div></> : <span className="hint">Not submitted</span>}
                      </td>
                      <td>
                        {a.can_recommend && (
                          <button
                            className="btn btn-sm btn-out"
                            onClick={() =>
                              act(
                                () =>
                                  api.recommendAdmissionOffer(
                                    a.id,
                                    a.status_version,
                                  ),
                                loadOffers,
                              )
                            }
                          >
                            Send offer
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      {tab === "program_intake" && <ProgramIntake rows={programIntake} />}{" "}
      {tab === "document_status" && <DocumentStatus rows={documentStatus} />}{" "}
      {tab === "final_approval" && (
        <FinalApprovalStatus rows={finalApprovals} phase5Rows={phase5Status} onAction={runPhase5Action} />
      )}{" "}
      {tab === "reports" && (
        <AdmissionsReports apps={apps.applications} phase5={phase5Status} />
      )}{" "}
      {tab === "recommendations" && (
        <OfferStatus
          rows={offers.filter((x) =>
            ["OFFER_RECOMMENDATION_PENDING", "OFFER_APPROVAL_PENDING"].includes(
              x.current_status,
            ),
          )}
          title="Offer Recommendations"
        />
      )}{" "}
      {tab === "issued_offers" && (
        <OfferStatus
          rows={offers.filter((x) =>
            [
              "OFFERED",
              "OFFER_ACCEPTED",
              "OFFER_DECLINED",
              "OFFER_EXPIRED",
            ].includes(x.current_status),
          )}
          title="Issued Offers"
        />
      )}{" "}
      {tab.startsWith("director_") && (
        <DirectorMonitoring
          mode={tab}
          apps={apps.applications}
          data={directorData}
        />
      )}{" "}
      {[
        "finance_status",
        "invoices_challans",
        "payment_status",
        "accounts_verification",
        "clearance_status",
      ].includes(tab) && (
        <ApplicantFinanceView rows={phase5Status} mode={tab} onAction={runPhase5Action} />
      )}{" "}
      {[
        "ready_to_admit",
        "enrollment_queue",
        "student_conversion",
        "enrollment_status",
      ].includes(tab) && <FinalAdmissionView rows={phase5Status} mode={tab} onAction={runPhase5Action} />}
      {tab === "cycles" && (
        <Cycles
          cycles={cycles}
          programmes={programmes}
          manage={manage}
          setCycle={setCycle}
          binding={binding}
          setBinding={setBinding}
          act={act}
          loadCycles={loadCycles}
        />
      )}
      {cycle && (
        <CycleModal
          cycle={cycle}
          setCycle={setCycle}
          binding={binding}
          setBinding={setBinding}
          programmes={programmes}
          save={saveCycle}
          act={act}
          loadCycles={loadCycles}
        />
      )}
      {rule && (
        <RuleModal
          rule={rule}
          setRule={setRule}
          cycles={cycles}
          programmes={programmes}
          quotas={quotas}
          save={saveRule}
        />
      )}
      {quota && (
        <QuotaModal
          quota={quota}
          setQuota={setQuota}
          cycles={cycles}
          programmes={programmes}
          save={saveQuota}
        />
      )}
      {assessment && (
        <Modal
          title={`Assessment: ${assessment.name}`}
          onClose={() => setAssessment(null)}
          footer={
            <>
              <button
                className="btn btn-out"
                onClick={() => setAssessment(null)}
              >
                Cancel
              </button>
              <button
                className="btn btn-brass"
                onClick={() =>
                  act(
                    () =>
                      api.recordAdmissionAssessment(assessment.id, {
                        assessment_type: assessment.assessment_type,
                        score: Number(assessment.score),
                        max_score: Number(assessment.max_score),
                        expected_status_version: assessment.status_version,
                      }),
                    () => {
                      setAssessment(null);
                      loadPhase4();
                    },
                  )
                }
              >
                Verify result
              </button>
            </>
          }
        >
          <select
            className="inp"
            value={assessment.assessment_type}
            onChange={(e) =>
              setAssessment({ ...assessment, assessment_type: e.target.value })
            }
          >
            {["ENTRANCE_EXAM", "ACADEMIC_MERIT", "OTHER"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
          <input
            className="inp"
            type="number"
            placeholder="Verified score"
            value={assessment.score}
            onChange={(e) =>
              setAssessment({ ...assessment, score: e.target.value })
            }
          />
          <input
            className="inp"
            type="number"
            placeholder="Maximum score"
            value={assessment.max_score}
            onChange={(e) =>
              setAssessment({ ...assessment, max_score: e.target.value })
            }
          />
        </Modal>
      )}
      {seatPool && (
        <Modal
          title="Seat pool"
          onClose={() => setSeatPool(null)}
          footer={
            <>
              <button className="btn btn-out" onClick={() => setSeatPool(null)}>
                Cancel
              </button>
              <button
                className="btn btn-brass"
                onClick={() =>
                  act(
                    () =>
                      api.createAdmissionSeatPool({
                        ...seatPool,
                        quota_id: seatPool.quota_id || null,
                        capacity: Number(seatPool.capacity),
                        category_code: "",
                        intake_key: "",
                      }),
                    () => {
                      setSeatPool(null);
                      loadPhase4();
                    },
                  )
                }
              >
                Save
              </button>
            </>
          }
        >
          <select
            className="inp"
            value={seatPool.cycle_id}
            onChange={(e) =>
              setSeatPool({ ...seatPool, cycle_id: e.target.value })
            }
          >
            <option value="">Cycle</option>
            {cycles.map((c: any) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <input
            className="inp"
            placeholder="Campus"
            value={seatPool.campus}
            onChange={(e) =>
              setSeatPool({ ...seatPool, campus: e.target.value })
            }
          />
          <select
            className="inp"
            value={seatPool.program_id}
            onChange={(e) =>
              setSeatPool({ ...seatPool, program_id: e.target.value })
            }
          >
            <option value="">Programme</option>
            {programmes.map((p: any) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <select
            className="inp"
            value={seatPool.quota_id || ""}
            onChange={(e) =>
              setSeatPool({ ...seatPool, quota_id: e.target.value })
            }
          >
            <option value="">General quota</option>
            {quotas.map((q: any) => (
              <option key={q.id} value={q.id}>
                {q.name}
              </option>
            ))}
          </select>
          <input
            className="inp"
            type="number"
            placeholder="Capacity"
            value={seatPool.capacity}
            onChange={(e) =>
              setSeatPool({ ...seatPool, capacity: e.target.value })
            }
          />
          <select
            className="inp"
            value={seatPool.status}
            onChange={(e) =>
              setSeatPool({ ...seatPool, status: e.target.value })
            }
          >
            <option value="open">Active</option>
            <option value="closed">Inactive</option>
          </select>
        </Modal>
      )}
      {counsellingItem && (
        <Modal
          title={`Counselling: ${counsellingItem.name}`}
          onClose={() => setCounsellingItem(null)}
          footer={
            <>
              <button
                className="btn btn-out"
                onClick={() => setCounsellingItem(null)}
              >
                Cancel
              </button>
              <button
                className="btn btn-brass"
                onClick={() =>
                  act(
                    () =>
                      api.recordCounselling(counsellingItem.id, {
                        attendance_status: counsellingItem.attendance_status,
                        recommended_program_id: counsellingItem.program_id,
                        preference_rank: Number(
                          counsellingItem.preference_rank,
                        ),
                        remarks: counsellingItem.remarks,
                        expected_status_version: counsellingItem.status_version,
                      }),
                    () => {
                      setCounsellingItem(null);
                      loadCounselling();
                    },
                  )
                }
              >
                Complete counselling
              </button>
            </>
          }
        >
          <p>
            Merit: {counsellingItem.merit_score ?? "Not calculated"} · rank{" "}
            {counsellingItem.merit_rank ?? "—"}
          </p>
          <select
            className="inp"
            value={counsellingItem.attendance_status}
            onChange={(e) =>
              setCounsellingItem({
                ...counsellingItem,
                attendance_status: e.target.value,
              })
            }
          >
            <option value="attended">Attended</option>
            <option value="absent">Absent</option>
          </select>
          <input
            className="inp"
            type="number"
            value={counsellingItem.preference_rank}
            onChange={(e) =>
              setCounsellingItem({
                ...counsellingItem,
                preference_rank: e.target.value,
              })
            }
          />
          <input
            className="inp"
            placeholder="Remarks"
            value={counsellingItem.remarks}
            onChange={(e) =>
              setCounsellingItem({
                ...counsellingItem,
                remarks: e.target.value,
              })
            }
          />
        </Modal>
      )}
      {detail && (
        <Modal
          title={`Review ${detail.application_no}`}
          onClose={() => setDetail(null)}
          footer={
            <>
              <button className="btn btn-out" onClick={() => setDetail(null)}>
                Close
              </button>
              {detail.permitted_actions?.start_review &&
                detail.current_status === "SUBMITTED" && (
                  <button
                    className="btn btn-out"
                    onClick={() =>
                      act(
                        () =>
                          api.admissionAction(
                            detail.id,
                            "start_review",
                            detail.status_version,
                          ),
                        () => {
                          setDetail(null);
                          loadQueue();
                          loadApps();
                        },
                      )
                    }
                  >
                    Start review
                  </button>
                )}
              {detail.permitted_actions?.request_correction &&
                ["SUBMITTED", "RESUBMITTED", "REVIEW_IN_PROGRESS"].includes(
                  detail.current_status,
                ) && (
                  <button
                    className="btn btn-rose"
                    onClick={() =>
                      setCorrectionDialog({
                        applicationId: detail.id,
                        applicationNo: detail.application_no,
                        statusVersion: detail.status_version,
                        reason: "",
                      })
                    }
                  >
                    Request correction
                  </button>
                )}
              {detail.permitted_actions?.complete_document_verification &&
                detail.current_status === "REVIEW_IN_PROGRESS" && (
                  <button
                    className="btn btn-teal"
                    onClick={() =>
                      act(
                        () =>
                          api.admissionAction(
                            detail.id,
                            "complete_document_verification",
                            detail.status_version,
                          ),
                        () => {
                          setDetail(null);
                          loadQueue();
                          loadApps();
                        },
                      )
                    }
                  >
                    Verify documents
                  </button>
                )}
            </>
          }
        >
          <p>
            <b>{detail.applicant_name}</b> · {detail.email}
          </p>
          <p className="hint">
            {detail.current_status} · version {detail.status_version}
          </p>
          <h4>Documents</h4>
          <div className="tbl-scroll">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>File</th>
                  <th>Verification</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(detail.documents || []).map((document: any) => (
                  <tr key={document.id}>
                    <td>{document.document_type}</td>
                    <td>{document.file_name}</td>
                    <td>{document.verification_status || "PENDING"}</td>
                    <td>
                      <button className="btn btn-sm btn-out" onClick={() => api.fetchAdmissionDocument(detail.id, document.id).then((preview) => setDocumentPreview({ ...preview, fileName: document.file_name })).catch((e: any) => setNotice({ outcome: "DENY", reason: e.message }))}>Preview</button>
                      <button className="btn btn-sm btn-out" style={{ marginLeft: 6 }} onClick={() => api.openAdmissionDocument(detail.id, document.id).catch((e: any) => setNotice({ outcome: "DENY", reason: e.message }))}>Open tab</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!(detail.documents || []).length && (
            <p className="hint">No documents have been submitted yet.</p>
          )}
          <h4>Application history</h4>
          <div className="tbl-scroll">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Action</th>
                  <th>From</th>
                  <th>To</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {(detail.history || []).map((item: any, index: number) => (
                  <tr key={`${item.action}-${index}`}>
                    <td>{item.action}</td>
                    <td>{item.from}</td>
                    <td>{item.to}</td>
                    <td>{item.at?.slice(0, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Modal>
      )}
      {documentPreview && (
        <Modal
          title={`Document preview: ${documentPreview.fileName}`}
          onClose={() => { URL.revokeObjectURL(documentPreview.url); setDocumentPreview(null); }}
          className="document-preview-modal"
          footer={<button className="btn btn-out" onClick={() => { URL.revokeObjectURL(documentPreview.url); setDocumentPreview(null); }}>Close preview</button>}
        >
          {documentPreview.mimeType.startsWith("image/") ? (
            <img src={documentPreview.url} alt={documentPreview.fileName} style={{ display: "block", maxWidth: "100%", maxHeight: "70vh", margin: "0 auto" }} />
          ) : documentPreview.mimeType.includes("pdf") ? (
            <iframe title={documentPreview.fileName} src={documentPreview.url} style={{ width: "100%", height: "70vh", border: 0 }} />
          ) : (
            <p className="hint">This file type cannot be previewed in the browser. Use Open tab to view or download it.</p>
          )}
        </Modal>
      )}
      {paymentDialog && (
        <Modal
          title={`Record admission payment: ${paymentDialog.row.application_no}`}
          onClose={() => setPaymentDialog(null)}
          footer={<><button className="btn btn-out" onClick={() => setPaymentDialog(null)}>Cancel</button><button className="btn btn-brass" onClick={submitAdmissionPayment}>Record payment</button></>}
        >
          <p className="hint">Record the payment reference exactly as received. Accounts must verify it before finance clearance.</p>
          <label>Amount</label>
          <input className="inp" type="number" min="0.01" step="0.01" value={paymentDialog.amount} onChange={(e) => setPaymentDialog({ ...paymentDialog, amount: e.target.value })} />
          <label>Payment reference</label>
          <input className="inp" value={paymentDialog.reference} onChange={(e) => setPaymentDialog({ ...paymentDialog, reference: e.target.value })} placeholder="Bank UTR, receipt number, or transaction ID" />
          <label>Method</label>
          <select className="inp" value={paymentDialog.method} onChange={(e) => setPaymentDialog({ ...paymentDialog, method: e.target.value })}><option value="challan">Challan</option><option value="bank_transfer">Bank transfer</option><option value="cash">Cash</option><option value="upi">UPI</option></select>
        </Modal>
      )}
      {correctionDialog && (
        <Modal
          title={`Request correction: ${correctionDialog.applicationNo}`}
          onClose={() => setCorrectionDialog(null)}
          footer={
            <>
              <button className="btn btn-out" onClick={() => setCorrectionDialog(null)}>
                Cancel
              </button>
              <button className="btn btn-rose" onClick={submitCorrection}>
                Send correction request
              </button>
            </>
          }
        >
          <p className="hint">
            Clearly state what the applicant must update, upload, or correct.
            This instruction appears in the applicant portal and Corrections tab.
          </p>
          <textarea
            className="inp"
            rows={6}
            value={correctionDialog.reason}
            onChange={(e) =>
              setCorrectionDialog({ ...correctionDialog, reason: e.target.value })
            }
            placeholder="Example: Upload a clear marksheet and correct the date of birth to match your identity document."
          />
        </Modal>
      )}
      {eligibilityDetail && (
        <EligibilityDetailView
          detail={eligibilityDetail}
          onClose={() => setEligibilityDetail(null)}
        />
      )}
      {notice && (
        <DecisionToast decision={notice} onClose={() => setNotice(null)} />
      )}
    </div>
  );
}

function AdmissionsReports({ apps, phase5 }: any) {
  const groups = [
    [
      "Applications received",
      ["SUBMITTED", "RESUBMITTED", "REVIEW_IN_PROGRESS"],
    ],
    ["Document verified", ["DOCUMENT_VERIFIED"]],
    ["Eligible", ["ELIGIBLE"]],
    [
      "Assessment / counselling",
      ["ASSESSMENT_PENDING", "ASSESSMENT_QUALIFIED", "COUNSELLING_PENDING"],
    ],
    ["Allocated", ["ALLOCATION_PENDING", "ALLOCATED", "WAITLISTED"]],
    ["Offers issued", ["OFFERED"]],
    ["Offers accepted", ["OFFER_ACCEPTED"]],
    [
      "Finance cleared",
      [
        "FINANCE_CLEARED",
        "FINAL_APPROVAL_PENDING",
        "READY_TO_ADMIT",
        "ENROLLED",
      ],
    ],
    ["Enrolled", ["ENROLLED"]],
  ];
  const total = Math.max(
    1,
    ...groups.map(
      ([, states]: any) =>
        apps.filter((x: any) => states.includes(x.current_status)).length,
    ),
  );
  const finance = phase5.reduce(
    (sum: number, x: any) => sum + Number(x.total_paid || x.paid || 0),
    0,
  );
  return (
    <div className="card">
      <div className="card-pad">
        <h3>Admissions Reports</h3>
        <p className="hint">
          Live admissions performance summary from the current database.
        </p>
        <div className="kpi-grid">
          <div className="kpi">
            <div className="kpi-val">{apps.length}</div>
            <div className="kpi-label">Total applications</div>
          </div>
          <div className="kpi">
            <div className="kpi-val">
              {apps.filter((x: any) => x.current_status === "ENROLLED").length}
            </div>
            <div className="kpi-label">Enrolled students</div>
          </div>
          <div className="kpi">
            <div className="kpi-val">
              {
                apps.filter((x: any) => x.current_status === "OFFER_ACCEPTED")
                  .length
              }
            </div>
            <div className="kpi-label">Offers accepted</div>
          </div>
          <div className="kpi">
            <div className="kpi-val">₹{finance.toLocaleString("en-IN")}</div>
            <div className="kpi-label">Recorded fee collection</div>
          </div>
        </div>
        <h4 style={{ marginTop: 24 }}>Application funnel</h4>
        <div className="admission-report-bars">
          {groups.map(([label, states]: any) => {
            const value = apps.filter((x: any) =>
              states.includes(x.current_status),
            ).length;
            return (
              <div key={label}>
                <span>{label}</span>
                <div>
                  <i style={{ width: `${(value / total) * 100}%` }} />
                </div>
                <b>{value}</b>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
function ProgramIntake({ rows }: any) {
  return (
    <div className="card">
      <div className="card-pad">
        <h3>Programs & Intake</h3>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Cycle</th>
                <th>Programme</th>
                <th>Department</th>
                <th>Campus</th>
                <th>Intake</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((x: any) => (
                <tr key={x.id}>
                  <td>
                    {x.cycle}
                    <div className="hint">{x.academic_year}</div>
                  </td>
                  <td>{x.program}</td>
                  <td>{x.department || "—"}</td>
                  <td>{x.campus}</td>
                  <td>{x.intake}</td>
                  <td>{x.active ? "Active" : "Inactive"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
function DocumentStatus({ rows }: any) {
  return (
    <div className="card">
      <div className="card-pad">
        <h3>Document Status</h3>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Application</th>
                <th>Applicant</th>
                <th>Required</th>
                <th>Verified</th>
                <th>Pending</th>
                <th>Correction</th>
                <th>Officer</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((x: any) => (
                <tr key={x.id}>
                  <td className="mono">{x.application_no}</td>
                  <td>{x.applicant_name}</td>
                  <td>{x.required}</td>
                  <td>{x.verified}</td>
                  <td>{x.pending}</td>
                  <td>{x.correction_required ? "Required" : "—"}</td>
                  <td>{x.officers?.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
function OfferStatus({ rows, title }: any) {
  return (
    <div className="card">
      <div className="card-pad">
        <h3>{title}</h3>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Applicant</th>
                <th>Programme</th>
                <th>Status</th>
                <th>Workflow</th>
                <th>Offer</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((x: any) => (
                <tr key={x.id}>
                  <td>{x.name}</td>
                  <td>{x.program}</td>
                  <td>{x.current_status}</td>
                  <td>{x.workflow_state || "—"}</td>
                  <td>{x.offer_no || "Not issued"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
function FinalApprovalStatus({ rows, phase5Rows = [], onAction }: any) {
  return (
    <div className="card">
      <div className="card-pad">
        <h3>Final Admission Approval</h3>
        <p className="hint">
          Final-admission workflows only. Use Approval Inbox for authorised
          workflow decisions.
        </p>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Application</th>
                <th>Applicant</th>
                <th>Programme</th>
                <th>Application status</th>
                <th>Workflow</th>
                <th>Latest decision</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((x: any) => (
                <tr key={x.workflow_id}>
                  <td className="mono">{x.application_no}</td>
                  <td>{x.applicant_name}</td>
                  <td>{x.program}</td>
                  <td>{x.application_status}</td>
                  <td>
                    {x.workflow_state}
                    <div className="hint">{x.workflow_id}</div>
                  </td>
                  <td>
                    {x.latest_decision || "Pending"}{" "}
                    <span className="hint">({x.approval_count})</span>
                  </td>
                  <td>
                    {(() => {
                      const application = phase5Rows.find((row: any) => row.id === x.application_id);
                      return application?.status === "FINAL_APPROVAL_PENDING" && application.checklist?.final_approval_complete ? (
                        <button className="btn btn-sm btn-brass" onClick={() => onAction("complete_final", application)}>Complete approval</button>
                      ) : x.application_status === "FINAL_APPROVAL_PENDING" ? "Approve in Approval Inbox first" : "Complete";
                    })()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
function DirectorMonitoring({ mode, apps, data }: any) {
  const count = (states: string[]) =>
    apps.filter((x: any) => states.includes(x.current_status)).length;
  const offerCount = (states: string[]) =>
    data.offers.filter((x: any) => states.includes(x.current_status)).length;
  const cards =
    mode === "director_funnel"
      ? [
          [
            "Submitted",
            count(["SUBMITTED", "RESUBMITTED", "REVIEW_IN_PROGRESS"]),
          ],
          ["Document verified", count(["DOCUMENT_VERIFIED"])],
          ["Eligible", count(["ELIGIBLE"])],
          ["Allocated", count(["ALLOCATED"])],
          ["Offered", offerCount(["OFFERED"])],
          ["Accepted", offerCount(["OFFER_ACCEPTED"])],
          ["Finance cleared", count(["FINANCE_CLEARED"])],
          ["Ready to admit", count(["READY_TO_ADMIT"])],
          ["Enrolled", count(["ENROLLED"])],
        ]
      : mode === "director_offer_conversion" || mode === "director_offer_status"
        ? [
            ["Recommendation pending", count(["OFFER_RECOMMENDATION_PENDING"])],
            ["Approval pending", count(["OFFER_APPROVAL_PENDING"])],
            ["Offered", offerCount(["OFFERED"])],
            ["Accepted", offerCount(["OFFER_ACCEPTED"])],
            ["Declined", offerCount(["OFFER_DECLINED"])],
            ["Expired", offerCount(["OFFER_EXPIRED"])],
          ]
        : mode === "director_offer_approvals"
          ? [
              [
                "Recommendation pending",
                count(["OFFER_RECOMMENDATION_PENDING"]),
              ],
              ["Approval pending", count(["OFFER_APPROVAL_PENDING"])],
            ]
          : mode === "director_enrollment_progress"
            ? [
                ["Finance cleared", count(["FINANCE_CLEARED"])],
                ["Ready to admit", count(["READY_TO_ADMIT"])],
                ["Enrolled", count(["ENROLLED"])],
              ]
            : mode === "director_eligibility_summary"
              ? [
                  ["Eligible", count(["ELIGIBLE"])],
                  ["Ineligible", count(["INELIGIBLE"])],
                  [
                    "Pending",
                    count(["DOCUMENT_VERIFIED", "ELIGIBILITY_PENDING"]),
                  ],
                  ["Missing / correction", count(["CORRECTION_REQUIRED"])],
                ]
              : mode === "director_counselling_summary"
                ? [
                    ["Pending", count(["COUNSELLING_PENDING"])],
                    [
                      "Completed",
                      data.counselling.filter(
                        (x: any) => x.outcome === "COMPLETED",
                      ).length,
                    ],
                    [
                      "No show",
                      data.counselling.filter(
                        (x: any) => x.attendance_status === "absent",
                      ).length,
                    ],
                    [
                      "Recommendations",
                      data.counselling.filter(
                        (x: any) => x.recommended_program_id,
                      ).length,
                    ],
                  ]
                : mode === "director_allocation_summary"
                  ? [
                      [
                        "Allocated",
                        count([
                          "ALLOCATED",
                          "OFFER_RECOMMENDATION_PENDING",
                          "OFFER_APPROVAL_PENDING",
                          "OFFERED",
                          "OFFER_ACCEPTED",
                        ]),
                      ],
                      ["Waitlisted", count(["WAITLISTED"])],
                      [
                        "Released / expired",
                        count(["OFFER_DECLINED", "OFFER_EXPIRED"]),
                      ],
                      [
                        "Waitlist entries",
                        data.pools.reduce(
                          (n: number, x: any) => n + Number(x.waitlisted || 0),
                          0,
                        ),
                      ],
                    ]
                  : mode === "director_exceptions"
                    ? [
                        [
                          "Corrections required",
                          count(["CORRECTION_REQUIRED"]),
                        ],
                        ["Ineligible", count(["INELIGIBLE"])],
                        [
                          "Offer approval pending",
                          count(["OFFER_APPROVAL_PENDING"]),
                        ],
                        [
                          "Finance / final blockers",
                          count([
                            "PAYMENT_PENDING",
                            "ACCOUNTS_VERIFIED",
                            "FINAL_APPROVAL_PENDING",
                          ]),
                        ],
                      ]
                    : [];
  const poolRows =
    mode === "director_intake_utilization" ||
    mode === "director_quota_utilization"
      ? data.pools
      : [];
  const title = (
    {
      director_funnel: "Application Funnel",
      director_intake_utilization: "Intake & Seat Utilization",
      director_quota_utilization: "Quota Utilization",
      director_offer_conversion: "Offer Conversion",
      director_enrollment_progress: "Enrollment Progress",
      director_offer_approvals: "Offer Approvals",
      director_exceptions: "Escalations / Exceptions",
      director_eligibility_summary: "Eligibility Summary",
      director_counselling_summary: "Counselling Summary",
      director_allocation_summary: "Allocation & Waitlist",
      director_offer_status: "Offer Status",
    } as any
  )[mode];
  return (
    <div className="card">
      <div className="card-pad">
        <h3>{title}</h3>
        {cards.length > 0 && (
          <div className="kpi-grid">
            {cards.map(([label, value]: any) => (
              <div className="kpi" key={label}>
                <div className="kpi-val">{value}</div>
                <div className="kpi-label">{label}</div>
              </div>
            ))}
          </div>
        )}
        {poolRows.length > 0 && (
          <div className="tbl-scroll">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Pool</th>
                  <th>Quota</th>
                  <th>Capacity</th>
                  <th>Active allocations</th>
                  <th>Available</th>
                  <th>Waitlisted</th>
                </tr>
              </thead>
              <tbody>
                {poolRows.map((x: any) => (
                  <tr key={x.id}>
                    <td>
                      {x.program_name || x.program_id}
                      <div className="hint">{x.campus}</div>
                    </td>
                    <td>{x.quota_name || x.quota_id || "General"}</td>
                    <td>{x.capacity}</td>
                    <td>{x.used}</td>
                    <td>{x.available}</td>
                    <td>{x.waitlisted}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
function ApplicantFinanceView({ rows, mode, onAction }: any) {
  const money = (value: any) =>
    `₹${Number(value || 0).toLocaleString("en-IN")}`;
  const titles: any = {
    finance_status: "Finance Status",
    invoices_challans: "Invoices & Challans",
    payment_status: "Payment Status",
    accounts_verification: "Accounts Verification",
    clearance_status: "Finance Clearance",
    ready_to_admit: "Ready to Admit",
    enrollment_status: "Enrollment Status",
  };
  const rowsForMode = () => {
    if (mode === "invoices_challans")
      return rows.filter((x: any) => x.invoice_id || x.challan_no);
    if (mode === "payment_status")
      return rows.filter(
        (x: any) =>
          x.invoice_id ||
          Number(x.paid) > 0 ||
          ["PAYMENT_PENDING", "PAYMENT_RECORDED", "ACCOUNTS_VERIFIED"].includes(
            x.status,
          ),
      );
    if (mode === "accounts_verification")
      return rows.filter((x: any) =>
        [
          "PAYMENT_RECORDED",
          "ACCOUNTS_VERIFIED",
          "FINANCE_CLEARED",
          "FINAL_APPROVAL_PENDING",
          "READY_TO_ADMIT",
          "ENROLLED",
        ].includes(x.status),
      );
    if (mode === "clearance_status")
      return rows.filter((x: any) =>
        [
          "ACCOUNTS_VERIFIED",
          "FINANCE_CLEARED",
          "FINAL_APPROVAL_PENDING",
          "FINAL_APPROVED",
          "READY_TO_ADMIT",
          "ENROLLED",
        ].includes(x.status),
      );
    if (mode === "ready_to_admit")
      return rows.filter((x: any) =>
        ["READY_TO_ADMIT", "FINAL_APPROVED"].includes(x.status),
      );
    if (mode === "enrollment_status")
      return rows.filter((x: any) =>
        ["READY_TO_ADMIT", "ENROLLED"].includes(x.status),
      );
    return rows;
  };
  const data = rowsForMode();
  if (mode === "finance_status") return <Phase5ActionQueue rows={data} onAction={onAction} />;
  const identity = (x: any) => (
    <>
      <td className="mono">{x.application_no}</td>
      <td>
        <b>{x.applicant_name}</b>
        <div className="hint">
          {x.program} · {x.campus}
        </div>
      </td>
    </>
  );
  const empty = (
    <tr>
      <td colSpan={6} className="hint">
        No records are currently at this stage.
      </td>
    </tr>
  );
  if (mode === "invoices_challans")
    return (
      <FinanceCard
        title={titles[mode]}
        sub="Issued admission invoices and generated challans"
      >
        <thead>
          <tr>
            <th>Application</th>
            <th>Applicant / Programme</th>
            <th>Invoice</th>
            <th>Challan</th>
            <th>Amount</th>
            <th>Invoice state</th>
          </tr>
        </thead>
        <tbody>
          {data.length
            ? data.map((x: any) => (
                <tr key={x.id}>
                  {identity(x)}
                  <td className="mono">{x.invoice_id || "Not issued"}</td>
                  <td>
                    <b>{x.challan_no || "Not generated"}</b>
                    <div className="hint">{x.challan_status || "—"}</div>
                  </td>
                  <td>{money(x.invoice_amount)}</td>
                  <td>{x.invoice_status || "PENDING"}</td>
                </tr>
              ))
            : empty}
        </tbody>
      </FinanceCard>
    );
  if (mode === "payment_status")
    return (
      <FinanceCard
        title={titles[mode]}
        sub="Payment collection and outstanding admission balances"
      >
        <thead>
          <tr>
            <th>Application</th>
            <th>Applicant / Programme</th>
            <th>Payable</th>
            <th>Received</th>
            <th>Balance</th>
            <th>Payment stage</th>
          </tr>
        </thead>
        <tbody>
          {data.length
            ? data.map((x: any) => (
                <tr key={x.id}>
                  {identity(x)}
                  <td>{money(x.total_payable || x.invoice_amount)}</td>
                  <td>{money(x.total_paid || x.paid)}</td>
                  <td>
                    <b>{money(x.balance)}</b>
                  </td>
                  <td>{x.status}</td>
                </tr>
              ))
            : empty}
        </tbody>
      </FinanceCard>
    );
  if (mode === "accounts_verification")
    return (
      <FinanceCard
        title={titles[mode]}
        sub="Payments awaiting or completing Accounts verification"
      >
        <thead>
          <tr>
            <th>Application</th>
            <th>Applicant / Programme</th>
            <th>Challan</th>
            <th>Received</th>
            <th>Accounts status</th>
            <th>Next action</th>
          </tr>
        </thead>
        <tbody>
          {data.length
            ? data.map((x: any) => (
                <tr key={x.id}>
                  {identity(x)}
                  <td>{x.challan_no || "—"}</td>
                  <td>{money(x.total_paid || x.paid)}</td>
                  <td>
                    <b>{x.accounts_status || "PENDING"}</b>
                  </td>
                  <td>
                    {x.accounts_status === "VERIFIED"
                      ? "Send to Finance"
                      : "Verify payment"}
                  </td>
                </tr>
              ))
            : empty}
        </tbody>
      </FinanceCard>
    );
  if (mode === "clearance_status")
    return (
      <FinanceCard
        title={titles[mode]}
        sub="Finance clearance before final admission approval"
      >
        <thead>
          <tr>
            <th>Application</th>
            <th>Applicant / Programme</th>
            <th>Payable</th>
            <th>Paid / waived</th>
            <th>Balance</th>
            <th>Clearance status</th>
          </tr>
        </thead>
        <tbody>
          {data.length
            ? data.map((x: any) => (
                <tr key={x.id}>
                  {identity(x)}
                  <td>{money(x.total_payable || x.invoice_amount)}</td>
                  <td>
                    {money((x.total_paid || x.paid) + (x.total_waived || 0))}
                  </td>
                  <td>
                    <b>{money(x.balance)}</b>
                  </td>
                  <td>
                    <b>{x.finance_status || "PENDING"}</b>
                  </td>
                </tr>
              ))
            : empty}
        </tbody>
      </FinanceCard>
    );
  return <Phase5Status rows={data} mode={mode} />;
}

function Phase5ActionQueue({ rows, onAction }: any) {
  const actions: any = {
    OFFER_ACCEPTED: ["resolve", "Resolve fees"], FEE_RESOLUTION_PENDING: ["invoice", "Issue invoice"],
    PAYMENT_PENDING: ["payment", "Record payment"], PAYMENT_RECORDED: ["verify", "Verify payment"],
    ACCOUNTS_VERIFIED: ["clear", "Clear finance"], FINANCE_CLEARED: ["request_final", "Request final approval"],
    FINAL_APPROVAL_PENDING: ["approval", "Approve in Approval Inbox"], READY_TO_ADMIT: ["convert", "Convert to student"],
  };
  return <FinanceCard title="Admission Completion Queue" sub="Perform the next permitted action for each applicant. Server-side role checks remain enforced.">
    <thead><tr><th>Application</th><th>Applicant / Programme</th><th>Current stage</th><th>Finance</th><th>Next action</th></tr></thead>
    <tbody>{rows.length ? rows.map((row: any) => {
      const next = actions[row.status];
      return <tr key={row.id}><td className="mono">{row.application_no}</td><td><b>{row.applicant_name}</b><div className="hint">{row.program} · {row.campus}</div></td><td>{row.status}</td><td>{row.invoice_id ? `Balance ₹${Number(row.balance || 0).toLocaleString("en-IN")}` : "Not invoiced"}</td><td>{next ? next[0] === "approval" ? <span className="hint">{next[1]}</span> : <button className="btn btn-sm btn-brass" onClick={() => onAction(next[0], row)}>{next[1]}</button> : row.status === "ENROLLED" ? "Completed" : "Waiting for applicant or approver"}</td></tr>;
    }) : <tr><td colSpan={5} className="hint">No applicants are currently in the post-offer workflow.</td></tr>}</tbody>
  </FinanceCard>;
}

function FinalAdmissionView({ rows, mode, onAction }: any) {
  const title: any = {
    ready_to_admit: "Ready to Admit",
    enrollment_queue: "Enrollment Queue",
    student_conversion: "Student Conversion",
    enrollment_status: "Enrollment Status",
  };
  const eligible = (statuses: string[]) =>
    rows.filter((x: any) => statuses.includes(x.status));
  const identity = (x: any) => (
    <>
      <td className="mono">{x.application_no}</td>
      <td>
        <b>{x.applicant_name}</b>
        <div className="hint">
          {x.program} · {x.campus}
        </div>
      </td>
    </>
  );
  const empty = (
    <tr>
      <td colSpan={6} className="hint">
        No applicants are currently at this stage.
      </td>
    </tr>
  );
  if (mode === "ready_to_admit") {
    const data = eligible(["FINAL_APPROVED", "READY_TO_ADMIT"]);
    return (
      <FinalCard
        title={title[mode]}
        sub="Applications that have completed the final admission checks"
      >
        <thead>
          <tr>
            <th>Application</th>
            <th>Applicant / Programme</th>
            <th>Documents</th>
            <th>Seat</th>
            <th>Finance</th>
            <th>Ready status</th>
          </tr>
        </thead>
        <tbody>
          {data.length
            ? data.map((x: any) => (
                <tr key={x.id}>
                  {identity(x)}
                  <td>
                    {x.checklist?.documents_verified ? "Verified" : "Pending"}
                  </td>
                  <td>
                    {x.checklist?.active_allocation ? "Allocated" : "Pending"}
                  </td>
                  <td>{x.finance_status || "PENDING"}</td>
                  <td>
                    <b>
                      {x.checklist?.ready ? "READY TO ADMIT" : "CHECK REQUIRED"}
                    </b>
                  </td>
                </tr>
              ))
            : empty}
        </tbody>
      </FinalCard>
    );
  }
  if (mode === "enrollment_queue") {
    const data = eligible(["READY_TO_ADMIT"]);
    return (
      <FinalCard
        title={title[mode]}
        sub="Ready applicants waiting for student account and enrollment creation"
      >
        <thead>
          <tr>
            <th>Application</th>
            <th>Applicant / Programme</th>
            <th>Current status</th>
            <th>Finance clearance</th>
            <th>Student ID</th>
            <th>Queue action</th>
          </tr>
        </thead>
        <tbody>
          {data.length
            ? data.map((x: any) => (
                <tr key={x.id}>
                  {identity(x)}
                  <td>{x.status}</td>
                  <td>{x.finance_status || "PENDING"}</td>
                  <td>{x.student_identifier || "Not created"}</td>
                  <td><button className="btn btn-sm btn-brass" onClick={() => onAction("convert", x)}>Convert to student</button></td>
                </tr>
              ))
            : empty}
        </tbody>
      </FinalCard>
    );
  }
  if (mode === "student_conversion") {
    const data = rows.filter(
      (x: any) =>
        x.conversion_status !== "PENDING" || x.status === "READY_TO_ADMIT",
    );
    return (
      <FinalCard
        title={title[mode]}
        sub="Student account creation and conversion tracking"
      >
        <thead>
          <tr>
            <th>Application</th>
            <th>Applicant / Programme</th>
            <th>Conversion status</th>
            <th>Student ID</th>
            <th>Converted at</th>
            <th>Enrollment state</th>
          </tr>
        </thead>
        <tbody>
          {data.length
            ? data.map((x: any) => (
                <tr key={x.id}>
                  {identity(x)}
                  <td>
                    <b>{x.conversion_status}</b>
                  </td>
                  <td>{x.student_identifier || "Awaiting conversion"}</td>
                  <td>{x.converted_at ? x.converted_at.slice(0, 16) : "—"}</td>
                  <td>{x.status === "READY_TO_ADMIT" ? <button className="btn btn-sm btn-brass" onClick={() => onAction("convert", x)}>Convert to student</button> : x.status}</td>
                </tr>
              ))
            : empty}
        </tbody>
      </FinalCard>
    );
  }
  const data = eligible(["READY_TO_ADMIT", "ENROLLED"]);
  return (
    <FinalCard title={title[mode]} sub="Final applicant enrollment outcomes">
      <thead>
        <tr>
          <th>Application</th>
          <th>Applicant / Programme</th>
          <th>Application status</th>
          <th>Student ID</th>
          <th>Converted at</th>
          <th>Enrollment result</th>
        </tr>
      </thead>
      <tbody>
        {data.length
          ? data.map((x: any) => (
              <tr key={x.id}>
                {identity(x)}
                <td>{x.status}</td>
                <td>{x.student_identifier || "Not yet assigned"}</td>
                <td>{x.converted_at ? x.converted_at.slice(0, 16) : "—"}</td>
                <td>
                  <b>
                    {x.status === "ENROLLED"
                      ? "ENROLLED"
                      : "PENDING ENROLLMENT"}
                  </b>
                </td>
              </tr>
            ))
          : empty}
      </tbody>
    </FinalCard>
  );
}

function FinalCard({ title, sub, children }: any) {
  return (
    <div className="card">
      <div className="card-pad">
        <h3>{title}</h3>
        <p className="hint">{sub}</p>
        <div className="tbl-scroll">
          <table className="tbl">{children}</table>
        </div>
      </div>
    </div>
  );
}
function FinanceCard({ title, sub, children }: any) {
  return (
    <div className="card">
      <div className="card-pad">
        <h3>{title}</h3>
        <p className="hint">{sub}</p>
        <div className="tbl-scroll">
          <table className="tbl">{children}</table>
        </div>
      </div>
    </div>
  );
}
function Phase5Status({ rows, mode }: any) {
  const filtered = rows.filter((x: any) =>
    mode === "ready_to_admit"
      ? ["READY_TO_ADMIT", "FINAL_APPROVED"].includes(x.status)
      : mode === "enrollment_status"
        ? ["READY_TO_ADMIT", "ENROLLED"].includes(x.status)
        : true,
  );
  return (
    <div className="card">
      <div className="card-pad">
        <h3>
          {mode === "finance_status"
            ? "Applicant Finance Status"
            : mode === "invoices_challans"
              ? "Invoices & Challans"
              : mode === "clearance_status"
                ? "Clearance Status"
                : mode === "ready_to_admit"
                  ? "Ready to Admit"
                  : "Enrollment Status"}
        </h3>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Application</th>
                <th>Applicant</th>
                <th>Programme</th>
                <th>Status</th>
                <th>Invoice / Challan</th>
                <th>Payable / Paid / Balance</th>
                <th>Accounts / Finance</th>
                <th>Checklist / Conversion</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((x: any) => (
                <tr key={x.id}>
                  <td className="mono">{x.application_no}</td>
                  <td>{x.applicant_name}</td>
                  <td>
                    {x.program}
                    <div className="hint">{x.campus}</div>
                  </td>
                  <td>{x.status}</td>
                  <td>
                    {x.invoice_id || "—"}
                    <div className="hint">
                      {x.challan_no} · {x.challan_status}
                    </div>
                  </td>
                  <td>
                    {x.total_payable || x.invoice_amount} /{" "}
                    {x.total_paid || x.paid} / {x.balance}
                  </td>
                  <td>
                    {x.accounts_status} / {x.finance_status}
                  </td>
                  <td>
                    {mode === "ready_to_admit"
                      ? x.checklist?.ready
                        ? "Ready"
                        : "Pending"
                      : `${x.conversion_status}${x.student_identifier ? ` · ${x.student_identifier}` : ""}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function EligibilityQueue({
  eligibility,
  filters,
  setFilters,
  cycles,
  programmes,
  load,
  detail,
  act,
}: any) {
  return (
    <>
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="card-pad form-grid">
          <select
            className="inp"
            value={filters.cycle_id}
            onChange={(e) =>
              setFilters({ ...filters, cycle_id: e.target.value })
            }
          >
            <option value="">All cycles</option>
            {cycles.map((c: any) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            className="inp"
            value={filters.program_id}
            onChange={(e) =>
              setFilters({ ...filters, program_id: e.target.value })
            }
          >
            <option value="">All programmes</option>
            {programmes.map((p: any) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <input
            className="inp"
            placeholder="Campus"
            value={filters.campus}
            onChange={(e) => setFilters({ ...filters, campus: e.target.value })}
          />
          <select
            className="inp"
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          >
            <option value="">All statuses</option>
            {[
              "DOCUMENT_VERIFIED",
              "ELIGIBILITY_PENDING",
              "ELIGIBLE",
              "INELIGIBLE",
            ].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
          <input
            className="inp"
            placeholder="Quota code"
            value={filters.quota_code}
            onChange={(e) =>
              setFilters({ ...filters, quota_code: e.target.value })
            }
          />
          <input
            className="inp"
            placeholder="Applicant or application no."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          />
          <button className="btn btn-out" onClick={load}>
            Apply filters
          </button>
        </div>
      </div>
      <div className="card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Application</th>
                <th>Applicant</th>
                <th>Cycle / programme</th>
                <th>Campus</th>
                <th>Documents</th>
                <th>Status</th>
                <th>Last evaluation</th>
                <th>Result</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {eligibility.map((a: any) => (
                <tr key={a.id}>
                  <td className="mono">{a.application_no}</td>
                  <td>{a.applicant_name}</td>
                  <td>
                    {a.cycle}
                    <div className="hint">{a.program}</div>
                  </td>
                  <td>{a.campus}</td>
                  <td>
                    {a.documents.uploaded}/{a.documents.required}
                  </td>
                  <td>{a.status}</td>
                  <td>
                    {a.last_evaluation_at?.slice(0, 16) || "Not evaluated"}
                  </td>
                  <td>{a.eligibility_result}</td>
                  <td>
                    <button
                      className="btn btn-sm btn-out"
                      onClick={() => detail(a.id)}
                    >
                      Detail
                    </button>
                    {a.permitted_actions?.evaluate && (
                      <button
                        className="btn btn-sm btn-brass"
                        onClick={() =>
                          act(
                            () =>
                              api.evaluateEligibility(a.id, a.status_version),
                            () => {
                              load();
                              detail(a.id);
                            },
                          )
                        }
                      >
                        Evaluate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function ConfigList({
  title,
  items,
  cycles,
  programmes,
  cycleId,
  setCycleId,
  reload,
  canManage,
  create,
  edit,
  kind,
}: any) {
  return (
    <>
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="card-pad">
          <select
            className="inp"
            value={cycleId}
            onChange={(e) => setCycleId(e.target.value)}
          >
            <option value="">All cycles</option>
            {cycles.map((c: any) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <button className="btn btn-out" onClick={reload}>
            Filter
          </button>
          {canManage && (
            <button className="btn btn-brass" onClick={create}>
              Create {kind}
            </button>
          )}
        </div>
      </div>
      <div className="card">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              {kind === "rule" ? (
                <tr>
                  <th>Rule type</th>
                  <th>Scope</th>
                  <th>Configured value</th>
                  <th>Status</th>
                  <th>Version</th>
                  <th />
                </tr>
              ) : (
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Scope</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th />
                </tr>
              )}
            </thead>
            <tbody>
              {items.map((x: any) =>
                kind === "rule" ? (
                  <tr key={x.id}>
                    <td>{x.rule_key}</td>
                    <td>
                      {x.quota_code ? `Quota: ${x.quota_code}` : "Mandatory"}
                      <div className="hint">
                        {programmes.find((p: any) => p.id === x.program_id)
                          ?.name || "All cycle programmes"}
                      </div>
                    </td>
                    <td>
                      {x.criteria?.document_type || x.criteria?.field}{" "}
                      {x.criteria?.operator} {x.criteria?.value}
                    </td>
                    <td>{x.active ? "Active" : "Inactive"}</td>
                    <td>v{x.version}</td>
                    <td>
                      {canManage && (
                        <button
                          className="btn btn-sm btn-out"
                          onClick={() => edit(x)}
                        >
                          Edit
                        </button>
                      )}
                    </td>
                  </tr>
                ) : (
                  <tr key={x.id}>
                    <td>{x.code}</td>
                    <td>
                      {x.name}
                      <div className="hint">{x.description}</div>
                    </td>
                    <td>
                      {programmes.find((p: any) => p.id === x.program_id)
                        ?.name || "All cycle programmes"}
                    </td>
                    <td>{x.priority}</td>
                    <td>{x.active ? "Active" : "Inactive"}</td>
                    <td>
                      {canManage && (
                        <button
                          className="btn btn-sm btn-out"
                          onClick={() => edit(x)}
                        >
                          Edit
                        </button>
                      )}
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function Cycles({
  cycles,
  programmes,
  programIntake,
  manage,
  setCycle,
  binding,
  setBinding,
  act,
  loadCycles,
}: any) {
  return (
    <div className="card">
      <div className="tbl-scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th>Cycle</th>
              <th>Bound programmes / intake</th>
              <th>Window</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {cycles.map((c: any) => (
              <tr key={c.id}>
                <td>
                  <b>{c.name}</b>
                  <div className="hint">
                    {c.academic_year} · {c.campus}
                  </div>
                </td>
                <td>
                  {(programIntake || []).filter((item: any) => item.cycle === c.name).length ? (programIntake || []).filter((item: any) => item.cycle === c.name).map((item: any) => <div key={item.id}><b>{item.program}</b><div className="hint">{item.intake} seats · {item.campus}</div></div>) : <span className="hint">No programme bound yet</span>}
                </td>
                <td>
                  {c.application_open_date?.slice(0, 10) || "—"} –{" "}
                  {c.application_close_date?.slice(0, 10) || "—"}
                </td>
                <td>{c.status}</td>
                <td>
                  {manage && (
                    <>
                      <button
                        className="btn btn-sm btn-out"
                        onClick={() =>
                          { setBinding({ campus: c.campus || "", intake: 0, active: true }); setCycle({
                            ...c,
                            application_open_date:
                              c.application_open_date?.slice(0, 16) || "",
                            application_close_date:
                              c.application_close_date?.slice(0, 16) || "",
                          }) }
                        }
                      >
                        Edit
                      </button>
                      {c.status !== "PUBLISHED" && c.status !== "CLOSED" && (
                        <button
                          className="btn btn-sm btn-teal"
                          onClick={() =>
                            act(
                              () => api.publishAdmissionCycle(c.id),
                              loadCycles,
                            )
                          }
                        >
                          Publish
                        </button>
                      )}
                      {c.status === "PUBLISHED" && (
                        <button
                          className="btn btn-sm btn-rose"
                          onClick={() =>
                            act(() => api.closeAdmissionCycle(c.id), loadCycles)
                          }
                        >
                          Close
                        </button>
                      )}
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CycleModal({
  cycle,
  setCycle,
  binding,
  setBinding,
  programmes,
  save,
  act,
  loadCycles,
}: any) {
  return (
    <Modal
      title={cycle.id ? "Edit admission cycle" : "Create admission cycle"}
      onClose={() => setCycle(null)}
      footer={
        <>
          <button className="btn btn-out" onClick={() => setCycle(null)}>
            Cancel
          </button>
          <button className="btn btn-brass" onClick={save}>
            Save
          </button>
        </>
      }
    >
      <input
        className="inp"
        placeholder="Name"
        value={cycle.name}
        onChange={(e) => setCycle({ ...cycle, name: e.target.value })}
      />
      <input
        className="inp"
        placeholder="Academic year"
        value={cycle.academic_year}
        onChange={(e) => setCycle({ ...cycle, academic_year: e.target.value })}
      />
      <input
        className="inp"
        placeholder="Campus"
        value={cycle.campus}
        onChange={(e) => setCycle({ ...cycle, campus: e.target.value })}
      />
      <input
        className="inp"
        type="datetime-local"
        value={cycle.application_open_date}
        onChange={(e) =>
          setCycle({ ...cycle, application_open_date: e.target.value })
        }
      />
      <input
        className="inp"
        type="datetime-local"
        value={cycle.application_close_date}
        onChange={(e) =>
          setCycle({ ...cycle, application_close_date: e.target.value })
        }
      />
      {cycle.id && (
        <>
          <h4>Bind existing programme</h4>
          <select
            className="inp"
            value={binding.program_id || ""}
            onChange={(e) =>
              setBinding({
                ...binding,
                program_id: e.target.value,
                campus: cycle.campus,
                active: true,
              })
            }
          >
            <option value="">Select programme</option>
            {programmes.map((p: any) => (
              <option value={p.id} key={p.id}>
                {p.code} - {p.name}
              </option>
            ))}
          </select>
          <input
            className="inp"
            type="number"
            min="1"
            placeholder="Intake"
            value={binding.intake || ""}
            onChange={(e) =>
              setBinding({
                ...binding,
                intake: Number(e.target.value),
                campus: cycle.campus,
                active: true,
              })
            }
          />
          <button
            className="btn btn-out"
            type="button"
            disabled={!binding.program_id || !Number(binding.intake)}
            onClick={() =>
              act(
                () => api.bindAdmissionProgram(cycle.id, {
                  ...binding,
                  campus: binding.campus || cycle.campus,
                  intake: Number(binding.intake),
                  active: true,
                }),
                () => {
                  setBinding({ campus: cycle.campus || "", intake: 0, active: true });
                  loadCycles();
                },
              )
            }
          >
            Bind programme
          </button>
        </>
      )}
    </Modal>
  );
}

function RuleModal({ rule, setRule, cycles, programmes, quotas, save }: any) {
  return (
    <Modal
      title={rule.id ? "Edit eligibility rule" : "Create eligibility rule"}
      onClose={() => setRule(null)}
      footer={
        <>
          <button className="btn btn-out" onClick={() => setRule(null)}>
            Cancel
          </button>
          <button className="btn btn-brass" onClick={save}>
            Save
          </button>
        </>
      }
    >
      <select
        className="inp"
        value={rule.cycle_id}
        onChange={(e) => setRule({ ...rule, cycle_id: e.target.value })}
      >
        <option value="">Select cycle</option>
        {cycles.map((c: any) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <select
        className="inp"
        value={rule.program_id || ""}
        onChange={(e) => setRule({ ...rule, program_id: e.target.value })}
      >
        <option value="">All cycle programmes</option>
        {programmes.map((p: any) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
      <select
        className="inp"
        value={rule.rule_key}
        onChange={(e) => setRule({ ...rule, rule_key: e.target.value })}
      >
        {[
          "FIELD_COMPARISON",
          "MINIMUM_VALUE",
          "MAXIMUM_VALUE",
          "EQUALS",
          "REQUIRED_DOCUMENT",
        ].map((x) => (
          <option key={x}>{x}</option>
        ))}
      </select>
      {rule.rule_key === "REQUIRED_DOCUMENT" ? (
        <>
          <select
            className="inp"
            value={[
              "Qualifying examination marksheet",
              "Government identity",
              "10th Certificate",
              "12th Certificate",
              "Transfer Certificate",
              "Graduation Certificate",
              "Passport Photograph",
            ].includes(rule.document_type) ? rule.document_type : "__custom__"}
            onChange={(e) =>
              setRule({
                ...rule,
                document_type:
                  e.target.value === "__custom__" ? "" : e.target.value,
              })
            }
          >
            <option value="">Select required document</option>
            <option value="Qualifying examination marksheet">Qualifying examination marksheet</option>
            <option value="Government identity">Government identity / ID proof</option>
            <option value="10th Certificate">10th Certificate</option>
            <option value="12th Certificate">12th Certificate</option>
            <option value="Transfer Certificate">Transfer Certificate</option>
            <option value="Graduation Certificate">Graduation Certificate</option>
            <option value="Passport Photograph">Passport Photograph</option>
            <option value="__custom__">Other document type</option>
          </select>
          {![
            "Qualifying examination marksheet",
            "Government identity",
            "10th Certificate",
            "12th Certificate",
            "Transfer Certificate",
            "Graduation Certificate",
            "Passport Photograph",
          ].includes(rule.document_type) && (
            <input
              className="inp"
              placeholder="Enter the exact applicant document type"
              value={rule.document_type}
              onChange={(e) =>
                setRule({ ...rule, document_type: e.target.value })
              }
            />
          )}
          <p className="hint">Use the same document type shown in the applicant upload form. The rule passes only when that document is uploaded and verified.</p>
        </>
      ) : (
        <>
          <input
            className="inp"
            placeholder="Persisted profile field"
            value={rule.field}
            onChange={(e) => setRule({ ...rule, field: e.target.value })}
          />
          <select
            className="inp"
            value={rule.operator}
            onChange={(e) => setRule({ ...rule, operator: e.target.value })}
          >
            {[">=", "<=", "=="].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
          <input
            className="inp"
            placeholder="Configured value"
            value={rule.value}
            onChange={(e) => setRule({ ...rule, value: e.target.value })}
          />
        </>
      )}
      <select
        className="inp"
        value={rule.quota_code || ""}
        onChange={(e) => setRule({ ...rule, quota_code: e.target.value })}
      >
        <option value="">Mandatory eligibility</option>
        {quotas
          .filter((q: any) => !rule.cycle_id || q.cycle_id === rule.cycle_id)
          .map((q: any) => (
            <option key={q.id} value={q.code}>
              Quota: {q.name} ({q.code})
            </option>
          ))}
      </select>
      <label>
        <input
          type="checkbox"
          checked={rule.active}
          onChange={(e) => setRule({ ...rule, active: e.target.checked })}
        />{" "}
        Active
      </label>
      {rule.id && (
        <p className="hint">
          Current version: {rule.version}. Saving creates the next version.
        </p>
      )}
    </Modal>
  );
}

function QuotaModal({ quota, setQuota, cycles, programmes, save }: any) {
  return (
    <Modal
      title={quota.id ? "Edit quota" : "Create quota"}
      onClose={() => setQuota(null)}
      footer={
        <>
          <button className="btn btn-out" onClick={() => setQuota(null)}>
            Cancel
          </button>
          <button className="btn btn-brass" onClick={save}>
            Save
          </button>
        </>
      }
    >
      <select
        className="inp"
        value={quota.cycle_id}
        onChange={(e) => setQuota({ ...quota, cycle_id: e.target.value })}
      >
        <option value="">Select cycle</option>
        {cycles.map((c: any) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <select
        className="inp"
        value={quota.program_id || ""}
        onChange={(e) => setQuota({ ...quota, program_id: e.target.value })}
      >
        <option value="">All cycle programmes</option>
        {programmes.map((p: any) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
      <input
        className="inp"
        placeholder="Code"
        value={quota.code}
        onChange={(e) => setQuota({ ...quota, code: e.target.value })}
      />
      <input
        className="inp"
        placeholder="Name"
        value={quota.name}
        onChange={(e) => setQuota({ ...quota, name: e.target.value })}
      />
      <input
        className="inp"
        placeholder="Category code"
        value={quota.category_code}
        onChange={(e) => setQuota({ ...quota, category_code: e.target.value })}
      />
      <input
        className="inp"
        type="number"
        placeholder="Priority"
        value={quota.priority}
        onChange={(e) =>
          setQuota({ ...quota, priority: Number(e.target.value) })
        }
      />
      <input
        className="inp"
        placeholder="Description"
        value={quota.description}
        onChange={(e) => setQuota({ ...quota, description: e.target.value })}
      />
      <label>
        <input
          type="checkbox"
          checked={quota.active}
          onChange={(e) => setQuota({ ...quota, active: e.target.checked })}
        />{" "}
        Active
      </label>
    </Modal>
  );
}

function EligibilityDetail({
  detail,
  onClose,
}: {
  detail: any;
  onClose: () => void;
}) {
  const app = detail.application || {};
  const latest = detail.runs?.[0];
  const checks = (id: string, quota?: string | null) =>
    (detail.checks || []).filter(
      (c: any) =>
        c.run_id === id &&
        (quota === undefined ? !c.quota_id : c.quota_id === quota),
    );
  const summary = (x: any[]) =>
    `${x.filter((c) => c.outcome === "PASS").length} pass, ${x.filter((c) => c.outcome === "FAIL").length} fail, ${x.filter((c) => c.outcome === "MISSING_DATA").length} missing`;
  const table = (x: any[]) => (
    <div className="tbl-scroll">
      <table className="tbl">
        <thead>
          <tr>
            <th>Rule</th>
            <th>Expected</th>
            <th>Observed</th>
            <th>Result</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {x.map((c: any, i: number) => (
            <tr key={`${c.rule_id}-${i}`}>
              <td>
                {c.rule} v{c.rule_version}
              </td>
              <td>{JSON.stringify(c.values?.expected)}</td>
              <td>
                {c.values?.observed == null
                  ? "Not supplied"
                  : String(c.values.observed)}
              </td>
              <td>{c.outcome}</td>
              <td>{c.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  const quotaIds = [
    ...new Set(
      (detail.checks || [])
        .filter((c: any) => c.run_id === latest?.id && c.quota_id)
        .map((c: any) => c.quota_id),
    ),
  ];
  return (
    <Modal
      title={`Eligibility: ${app.application_no}`}
      onClose={onClose}
      footer={
        <button className="btn btn-out" onClick={onClose}>
          Close
        </button>
      }
    >
      <h4>Application Summary</h4>
      <p>
        {app.applicant_name} · {app.cycle} · {app.program} · {app.campus}
      </p>
      <p>
        Status: <b>{app.status}</b> · version {app.status_version}
      </p>
      <h4>Overall Result</h4>
      <p>
        <b>{latest?.outcome || "PENDING"}</b>
      </p>
      <h4>Mandatory Eligibility</h4>
      {table(checks(latest?.id))}
      <h4>Quota Eligibility</h4>
      {quotaIds.length ? (
        quotaIds.map((id: any) => {
          const x = checks(latest?.id, id);
          const q = x[0]?.quota;
          return (
            <div key={id}>
              <p>
                <b>
                  {q?.name} ({q?.code})
                </b>{" "}
                —{" "}
                {x.every((c: any) => c.outcome === "PASS")
                  ? "Qualified"
                  : "Not qualified"}
                ; {summary(x)}
              </p>
              {table(x)}
            </div>
          );
        })
      ) : (
        <p className="hint">No quota-specific rules were evaluated.</p>
      )}
      <h4>Evaluation History</h4>
      <div className="tbl-scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th>Run</th>
              <th>Time</th>
              <th>Actor</th>
              <th>Result</th>
              <th>Checks</th>
            </tr>
          </thead>
          <tbody>
            {(detail.runs || []).map((r: any) => (
              <tr key={r.id}>
                <td className="mono">{r.id}</td>
                <td>
                  {r.completed_at?.slice(0, 16) || r.started_at?.slice(0, 16)}
                </td>
                <td>{r.actor_id || "System"}</td>
                <td>{r.outcome}</td>
                <td>
                  {summary(
                    (detail.checks || []).filter((c: any) => c.run_id === r.id),
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}
