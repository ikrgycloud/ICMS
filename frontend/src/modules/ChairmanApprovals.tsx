import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner, money } from './kit'

type TabKey = 'inbox' | 'mine' | 'all'

const PAGE_SIZE = 5

export default function ChairmanApprovals({ user, onChange }: { user: any; onChange: () => void }) {
  const [tab, setTab] = useState<TabKey>('inbox')
  const [semester, setSemester] = useState('all')
  const [status, setStatus] = useState('all')
  const [stage, setStage] = useState('all')
  const [process, setProcess] = useState('all')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showStart, setShowStart] = useState(false)
  const [selectedId, setSelectedId] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let active = true

    async function load() {
      setLoading(true)
      setError('')
      try {
        const response = await api.chairmanApprovals({
          tab,
          semester,
          status,
          stage,
          process,
          q: query,
          page,
          page_size: PAGE_SIZE,
        })
        if (!active) return
        setData(response)
        if (response?.pagination?.page && response.pagination.page !== page) {
          setPage(response.pagination.page)
        }
      } catch (err: any) {
        if (!active) return
        setError(err?.message || 'We could not load the approvals dashboard.')
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [page, process, query, reloadKey, semester, stage, status, tab])

  function resetFilters() {
    setSemester('all')
    setStatus('all')
    setStage('all')
    setProcess('all')
    setQuery('')
    setPage(1)
  }

  if (loading && !data) return <Spinner />

  if (error && !data) {
    return (
      <div className="chair-panel fade-in">
        <div className="chair-panel-head"><h3>Approvals unavailable</h3></div>
        <div className="card-pad">
          <p style={{ color: 'var(--txt-soft)', lineHeight: 1.7, marginBottom: 16 }}>{error}</p>
          <button className="btn btn-crimson" onClick={() => setReloadKey(key => key + 1)} type="button">Try again</button>
        </div>
      </div>
    )
  }

  const rows = data?.requests || []
  const pagination = data?.pagination || {}
  const filters = data?.filters || {}
  const tabs = data?.tabs || []
  const summary = data?.summary || {}

  return (
    <div className="chair-approvals fade-in">
      <section className="chair-head-shell chair-approvals-head">
        <div className="chair-head-top">
          <div className="chair-topline">
            <h1>{data?.title || 'Approvals'}</h1>
            <p>{data?.subtitle}</p>
          </div>

          <button
            className="btn btn-crimson chair-request-btn"
            disabled={!data?.can_initiate}
            onClick={() => setShowStart(true)}
            type="button"
          >
            + Initiate request
          </button>
        </div>
      </section>

      <div className="chair-approval-kpis">
        <SummaryCard
          tone="blue"
          icon="pending"
          value={summary.pending || 0}
          label="Pending"
          sub="Requires your action"
        />
        <SummaryCard
          tone="green"
          icon="approved"
          value={summary.approved || 0}
          label="Approved"
          sub="This month"
        />
        <SummaryCard
          tone="red"
          icon="rejected"
          value={summary.rejected || 0}
          label="Rejected"
          sub="This month"
        />
        <SummaryCard
          tone="amber"
          icon="review"
          value={summary.under_review || 0}
          label="Under Review"
          sub="Awaiting decision"
        />
      </div>

      <section className="chair-panel chair-approval-filter-panel">
        <div className="chair-approval-filter-grid">
          <FilterSelect
            label="Semester"
            value={semester}
            options={filters.semesters || []}
            onChange={value => {
              setSemester(value)
              setPage(1)
            }}
          />
          <FilterSelect
            label="Status"
            value={status}
            options={filters.statuses || []}
            onChange={value => {
              setStatus(value)
              setPage(1)
            }}
          />
          <FilterSelect
            label="Stage"
            value={stage}
            options={filters.stages || []}
            onChange={value => {
              setStage(value)
              setPage(1)
            }}
          />
          <FilterSelect
            label="Process"
            value={process}
            options={filters.processes || []}
            onChange={value => {
              setProcess(value)
              setPage(1)
            }}
          />

          <label className="chair-approval-search">
            <span className="chair-approval-filter-label">Search</span>
            <span className="chair-approval-search-box">
              <ApprovalGlyph kind="search" />
              <input
                value={query}
                onChange={event => {
                  setQuery(event.target.value)
                  setPage(1)
                }}
                placeholder="Search requests..."
              />
            </span>
          </label>
        </div>

        <div className="chair-approval-filter-foot">
          <button className="chair-approval-reset" onClick={resetFilters} type="button">
            <ApprovalGlyph kind="reset" />
            <span>Reset</span>
          </button>
        </div>
      </section>

      <div className="chair-approval-tabs">
        {tabs.map((item: any) => (
          <button
            key={item.key}
            className={`chair-approval-tab ${tab === item.key ? 'active' : ''}`}
            onClick={() => {
              setTab(item.key)
              setPage(1)
            }}
            type="button"
          >
            <span>{item.label}</span>
            <strong>{item.count}</strong>
          </button>
        ))}
      </div>

      <section className="chair-panel chair-approval-table-panel">
        {error && (
          <div className="chair-approval-inline-error">
            {error}
          </div>
        )}

        {loading ? (
          <Spinner />
        ) : rows.length === 0 ? (
          <Empty icon="⛓" text={tab === 'mine' ? 'Your initiated requests will appear here once submitted.' : 'No requests match the selected filters right now.'} />
        ) : (
          <>
            <div className="chair-approval-table-wrap">
              <table className="chair-approval-table">
                <thead>
                  <tr>
                    <th>Process</th>
                    <th>Request</th>
                    <th>Initiator</th>
                    <th>Amount</th>
                    <th>Stage</th>
                    <th>State</th>
                    <th>Received on</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row: any) => (
                    <tr key={row.id}>
                      <td data-label="Process">
                        <div className="chair-approval-process">
                          <span className="chair-approval-process-icon"><ApprovalGlyph kind={processIcon(row.process_key)} /></span>
                          <div>
                            <strong>{row.process_label}</strong>
                            <small>{row.category}</small>
                          </div>
                        </div>
                      </td>
                      <td data-label="Request">
                        <div className="chair-approval-request">
                          <strong>{row.title}</strong>
                          <small>REF: {row.reference_code}</small>
                        </div>
                      </td>
                      <td data-label="Initiator">{row.initiator}</td>
                      <td data-label="Amount" className="mono">{money(row.amount)}</td>
                      <td data-label="Stage">
                        <div className="chair-approval-stage">
                          <span className={`chair-approval-stage-chip ${row.stage.tone}`}>{row.stage.step}/{row.stage.total}</span>
                          <small>{row.stage.label}</small>
                        </div>
                      </td>
                      <td data-label="State">
                        <span className={`chair-approval-state ${row.state.tone}`}>
                          <span className="chair-approval-state-dot" />
                          {row.state.label}
                        </span>
                      </td>
                      <td data-label="Received on">
                        <div className="chair-approval-date">
                          <strong>{formatDate(row.received_on)}</strong>
                          <small>{formatTime(row.received_on)}</small>
                        </div>
                      </td>
                      <td data-label="Action">
                        <button className="chair-approval-open" onClick={() => setSelectedId(row.id)} type="button">Open</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="chair-approval-table-foot">
              <span>Showing {pagination.showing_from || 0} to {pagination.showing_to || 0} of {pagination.total || 0} requests</span>

              <div className="chair-approval-pagination">
                <button
                  className="chair-approval-page-btn"
                  disabled={(pagination.page || 1) <= 1}
                  onClick={() => setPage((pagination.page || 1) - 1)}
                  type="button"
                >
                  <ApprovalGlyph kind="left" />
                </button>
                {(pagination.visible_pages || []).map((entry: number) => (
                  <button
                    key={entry}
                    className={`chair-approval-page-btn ${entry === pagination.page ? 'active' : ''}`}
                    onClick={() => setPage(entry)}
                    type="button"
                  >
                    {entry}
                  </button>
                ))}
                <button
                  className="chair-approval-page-btn"
                  disabled={(pagination.page || 1) >= (pagination.total_pages || 1)}
                  onClick={() => setPage((pagination.page || 1) + 1)}
                  type="button"
                >
                  <ApprovalGlyph kind="right" />
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      {showStart && (
        <StartRequestModal
          form={data?.form}
          onClose={() => setShowStart(false)}
          onDone={workflow => {
            setShowStart(false)
            setTab('mine')
            setPage(1)
            setSelectedId(workflow.id)
            setReloadKey(key => key + 1)
            onChange()
          }}
        />
      )}

      {selectedId && (
        <WorkflowDetailModal
          user={user}
          workflowId={selectedId}
          onClose={() => setSelectedId('')}
          onDone={() => {
            onChange()
            setReloadKey(key => key + 1)
          }}
        />
      )}
    </div>
  )
}

function SummaryCard({ tone, icon, value, label, sub }: any) {
  return (
    <div className={`chair-approval-summary ${tone}`}>
      <div className="chair-approval-summary-icon"><ApprovalGlyph kind={icon} /></div>
      <div className="chair-approval-summary-copy">
        <strong>{value}</strong>
        <span>{label}</span>
        <small>{sub}</small>
      </div>
    </div>
  )
}

function FilterSelect({ label, value, options, onChange }: any) {
  return (
    <label className="chair-approval-select">
      <span className="chair-approval-filter-label">{label}</span>
      <select value={value} onChange={event => onChange(event.target.value)}>
        {options.map((option: any) => (
          <option key={option.key} value={option.key}>{option.label}</option>
        ))}
      </select>
    </label>
  )
}

function StartRequestModal({ form, onClose, onDone }: any) {
  const processes = form?.processes || []
  const semesters = form?.semesters || []
  const [processKey, setProcessKey] = useState(processes[0]?.key || '')
  const [semesterKey, setSemesterKey] = useState(semesters[0]?.key || '')
  const [title, setTitle] = useState('')
  const [amount, setAmount] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (processes[0]?.key && !processKey) setProcessKey(processes[0].key)
    if (semesters[0]?.key && !semesterKey) setSemesterKey(semesters[0].key)
  }, [processKey, processes, semesterKey, semesters])

  const selectedProcess = useMemo(
    () => processes.find((item: any) => item.key === processKey) || null,
    [processKey, processes],
  )
  const selectedSemester = useMemo(
    () => semesters.find((item: any) => item.key === semesterKey) || null,
    [semesterKey, semesters],
  )

  async function submit() {
    if (!title.trim()) {
      setError('Describe the request before submitting.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const response = await api.chairmanInitiateRequest({
        process_key: processKey,
        title: title.trim(),
        semester_key: semesterKey,
        semester_label: selectedSemester?.label || '',
        amount: selectedProcess?.amount && amount ? Number(amount) : undefined,
        notes: notes.trim(),
      })
      onDone(response.workflow)
    } catch (err: any) {
      setError(err?.message || 'We could not submit the request.')
      setBusy(false)
    }
  }

  return (
    <Modal
      title="Initiate request"
      onClose={busy ? () => {} : onClose}
      footer={(
        <>
          <button className="btn btn-out" disabled={busy} onClick={onClose} type="button">Cancel</button>
          <button className="btn btn-crimson" disabled={busy} onClick={submit} type="button">
            {busy ? 'Submitting...' : 'Submit request'}
          </button>
        </>
      )}
      className="chair-approval-modal"
    >
      {error && <div className="chair-approval-inline-error">{error}</div>}

      <div className="chair-approval-form-grid">
        <Field label="Process">
          <select className="select" value={processKey} onChange={event => setProcessKey(event.target.value)}>
            {processes.map((item: any) => (
              <option key={item.key} value={item.key}>{item.label}</option>
            ))}
          </select>
        </Field>

        <Field label="Semester">
          <select className="select" value={semesterKey} onChange={event => setSemesterKey(event.target.value)}>
            {semesters.map((item: any) => (
              <option key={item.key} value={item.key}>{item.label}</option>
            ))}
          </select>
        </Field>

        <Field label="Request title">
          <input className="inp" value={title} onChange={event => setTitle(event.target.value)} placeholder="e.g. Policy & Regulation Updates" />
        </Field>

        {selectedProcess?.amount && (
          <Field label="Amount (₹)">
            <input className="inp mono" value={amount} onChange={event => setAmount(event.target.value)} placeholder="2500000" />
          </Field>
        )}

        <Field label="Notes">
          <textarea className="inp chair-approval-textarea" rows={4} value={notes} onChange={event => setNotes(event.target.value)} placeholder="Add the context that should travel with this request." />
        </Field>
      </div>

      {selectedProcess && (
        <div className="chair-approval-chain-box">
          <div className="chair-approval-chain-head">
            <strong>{selectedProcess.category}</strong>
            <span>Escalates to {selectedProcess.escalation || 'configured authority'}</span>
          </div>
          <div className="chair-approval-chain">
            {selectedProcess.chain.map((node: string, index: number) => (
              <div className="chair-approval-chain-node" key={`${selectedProcess.key}-${index}`}>
                <small>Stage {index + 1}</small>
                <span>{node}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Modal>
  )
}

function WorkflowDetailModal({ workflowId, onClose, onDone }: { workflowId: string; onClose: () => void; onDone: () => void; user: any }) {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [decision, setDecision] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function load() {
      setLoading(true)
      setError('')
      try {
        const response = await api.workflow(workflowId)
        if (!active) return
        setData(response)
      } catch (err: any) {
        if (!active) return
        setError(err?.message || 'We could not open the request details.')
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [workflowId])

  async function decide(action: string) {
    if (!data) return
    setBusy(true)
    setError('')
    try {
      const response = await api.decideWorkflow(workflowId, action, reason)
      setDecision(response.decision)
      setData(response.workflow)
      setReason('')
      onDone()
    } catch (err: any) {
      setError(err?.message || 'We could not record that decision.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title={data?.label || 'Request details'}
      onClose={busy ? () => {} : onClose}
      className="chair-approval-modal chair-approval-detail-modal"
      footer={(
        <button className="btn btn-out" onClick={onClose} type="button">Close</button>
      )}
    >
      {loading ? (
        <Spinner />
      ) : error && !data ? (
        <div className="chair-approval-inline-error">{error}</div>
      ) : data ? (
        <div className="chair-approval-detail">
          <div className="chair-approval-detail-grid">
            <Meta label="Reference">{data.profile?.reference_code || '—'}</Meta>
            <Meta label="Semester">{data.profile?.semester_label || '—'}</Meta>
            <Meta label="Category">{data.profile?.category || '—'}</Meta>
            <Meta label="Amount">{money(data.amount)}</Meta>
          </div>

          <div className="chair-approval-detail-note">
            <strong>{data.title}</strong>
            <span>{data.profile?.notes || 'No additional notes were added to this request.'}</span>
          </div>

          <div className="chair-approval-chain-box">
            <div className="chair-approval-chain-head">
              <strong>Approval chain</strong>
              <span>Escalates to {data.escalation || 'configured authority'}</span>
            </div>
            <div className="chair-approval-chain">
              {(data.chain || []).map((node: string, index: number) => (
                <div className={`chair-approval-chain-node ${index + 1 <= (data.current_stage || 0) ? 'done' : ''}`} key={`${node}-${index}`}>
                  <small>Stage {index + 1}</small>
                  <span>{node}</span>
                </div>
              ))}
            </div>
          </div>

          {decision && (
            <div className="chair-approval-decision-box">
              <strong>{decision.outcome}</strong>
              <span>{decision.reason}</span>
              {decision.escalate_to && <small>Escalated to {decision.escalate_to}</small>}
            </div>
          )}

          {error && data && <div className="chair-approval-inline-error">{error}</div>}

          {!!data.history?.length && (
            <div className="chair-approval-history">
              <div className="chair-approval-detail-title">Decision history</div>
              {data.history.map((item: any, index: number) => (
                <div className="chair-approval-history-row" key={`${item.actor}-${index}`}>
                  <span className={`chair-approval-history-pill ${String(item.decision || '').toLowerCase()}`}>{item.decision}</span>
                  <div>
                    <strong>{item.actor}</strong>
                    <small>{item.stage_label} · {formatDateTime(item.at)}</small>
                    <p>{item.reason}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!['approved', 'executed', 'rejected'].includes(data.state) ? (
            <div className="chair-approval-action-box">
              <Field label="Decision note">
                <input className="inp" value={reason} onChange={event => setReason(event.target.value)} placeholder="Optional note for the audit trail" />
              </Field>

              <div className="chair-approval-action-row">
                <button className="btn btn-teal" disabled={busy} onClick={() => decide('review')} type="button">Review</button>
                <button className="btn btn-crimson" disabled={busy} onClick={() => decide('approve')} type="button">Approve</button>
                <button className="btn btn-rose" disabled={busy} onClick={() => decide('reject')} type="button">Reject</button>
                <button className="btn btn-out" disabled={busy} onClick={() => decide('escalate')} type="button">Escalate</button>
              </div>
            </div>
          ) : (
            <div className="chair-approval-terminal">
              This request is now in a terminal state: <strong>{String(data.state).replace(/_/g, ' ')}</strong>.
            </div>
          )}
        </div>
      ) : null}
    </Modal>
  )
}

function Field({ label, children }: any) {
  return (
    <label className="form-row">
      <span>{label}</span>
      {children}
    </label>
  )
}

function Meta({ label, children }: any) {
  return (
    <div className="chair-approval-meta">
      <small>{label}</small>
      <strong>{children}</strong>
    </div>
  )
}

function processIcon(processKey: string) {
  if (processKey.includes('branch')) return 'document'
  if (processKey.includes('purchase') || processKey.includes('payroll') || processKey.includes('fee')) return 'finance'
  if (processKey.includes('recruit')) return 'people'
  if (processKey.includes('question') || processKey.includes('result')) return 'academy'
  if (processKey.includes('disciplinary')) return 'shield'
  return 'flask'
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

function formatDateTime(value: string) {
  const stamp = new Date(value)
  return `${formatDate(stamp.toISOString())} · ${stamp.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`
}

function ApprovalGlyph({ kind }: { kind: string }) {
  switch (kind) {
    case 'pending':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 4h7l5 5v11a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" /><path d="M14 4v5h5M9 14h6M9 18h6" /></svg>
    case 'approved':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9" /><path d="m8.5 12.5 2.5 2.5 4.5-5" /></svg>
    case 'rejected':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9" /><path d="m9 9 6 6M15 9l-6 6" /></svg>
    case 'review':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5v5l3.5 2" /></svg>
    case 'search':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="11" cy="11" r="6" /><path d="m20 20-3.5-3.5" /></svg>
    case 'reset':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M20 6v6h-6" /><path d="M20 12a8 8 0 1 1-2.34-5.66L20 8.5" /></svg>
    case 'left':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m15 18-6-6 6-6" /></svg>
    case 'right':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m9 6 6 6-6 6" /></svg>
    case 'finance':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3v18" /><path d="M16.5 7.5c0-1.93-2.01-3.5-4.5-3.5s-4.5 1.57-4.5 3.5S9.51 11 12 11s4.5 1.57 4.5 3.5S14.49 18 12 18s-4.5-1.57-4.5-3.5" /></svg>
    case 'people':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>
    case 'academy':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m3 8 9-4 9 4-9 4-9-4Z" /><path d="M7 10v4c0 1.7 2.2 3 5 3s5-1.3 5-3v-4" /></svg>
    case 'shield':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 4 5 7v5c0 4.2 2.9 7.9 7 8.9 4.1-1 7-4.7 7-8.9V7l-7-3Z" /><path d="M9.5 12 11 13.5l3.5-4" /></svg>
    case 'flask':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M10 2v6L4.5 17.5A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-3.5L14 8V2" /><path d="M8 2h8M8 14h8" /></svg>
    default:
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8" /></svg>
  }
}