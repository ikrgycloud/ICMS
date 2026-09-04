import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Empty, Modal, Spinner, money } from './kit'

type TabKey = 'all' | 'active' | 'expiring' | 'inactive'

const PAGE_SIZE = 5

export default function ChairmanDelegation({ user }: { user: any }) {
  const [tab, setTab] = useState<TabKey>('all')
  const [policyType, setPolicyType] = useState('all')
  const [delegatedTo, setDelegatedTo] = useState('all')
  const [status, setStatus] = useState('all')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [selectedRow, setSelectedRow] = useState<any>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let active = true

    async function load() {
      setLoading(true)
      setError('')
      try {
        const response = await api.chairmanDelegations({
          tab,
          policy_type: policyType,
          delegated_to: delegatedTo,
          status,
          start,
          end,
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
        setError(err?.message || 'We could not load the delegation workspace.')
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [delegatedTo, end, page, policyType, query, reloadKey, start, status, tab])

  function resetFilters() {
    setPolicyType('all')
    setDelegatedTo('all')
    setStatus('all')
    setStart('')
    setEnd('')
    setQuery('')
    setPage(1)
  }

  if (loading && !data) return <Spinner />

  if (error && !data) {
    return (
      <div className="chair-panel fade-in">
        <div className="chair-panel-head"><h3>Delegation unavailable</h3></div>
        <div className="card-pad">
          <p style={{ color: 'var(--txt-soft)', lineHeight: 1.7, marginBottom: 16 }}>{error}</p>
          <button className="btn btn-crimson" onClick={() => setReloadKey(key => key + 1)} type="button">Try again</button>
        </div>
      </div>
    )
  }

  const rows = data?.delegations || []
  const pagination = data?.pagination || {}
  const filters = data?.filters || {}
  const tabs = data?.tabs || []
  const summary = data?.summary || {}

  return (
    <div className="chair-delegations fade-in">
      <section className="chair-head-shell chair-delegations-head">
        <div className="chair-head-top">
          <div className="chair-topline">
            <h1>{data?.title || 'Delegation'}</h1>
            <p>{data?.subtitle}</p>
          </div>

          <button className="btn btn-crimson chair-request-btn" onClick={() => setShowCreate(true)} type="button">
            + Create New Delegation
          </button>
        </div>
      </section>

      <div className="chair-delegation-kpis">
        <SummaryCard tone="violet" icon="total" value={summary.total || 0} label="Total Delegations" sub="All time" />
        <SummaryCard tone="green" icon="active" value={summary.active || 0} label="Active" sub="Currently active" />
        <SummaryCard tone="amber" icon="expiring" value={summary.expiring || 0} label="Expiring Soon" sub="Within 30 days" />
        <SummaryCard tone="red" icon="inactive" value={summary.inactive || 0} label="Revoked / Expired" sub="Inactive" />
      </div>

      <div className="chair-delegation-tabs">
        {tabs.map((item: any) => (
          <button
            key={item.key}
            className={`chair-delegation-tab ${tab === item.key ? 'active' : ''}`}
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

      <section className="chair-panel chair-delegation-filter-panel">
        <div className="chair-delegation-filter-grid">
          <FilterSelect
            label="Policy Type"
            value={policyType}
            options={filters.policy_types || []}
            onChange={value => {
              setPolicyType(value)
              setPage(1)
            }}
          />
          <FilterSelect
            label="Delegated To"
            value={delegatedTo}
            options={filters.delegated_to || []}
            onChange={value => {
              setDelegatedTo(value)
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

          <label className="chair-delegation-range">
            <span className="chair-delegation-filter-label">Date Range</span>
            <span className="chair-delegation-range-box">
              <DelegationGlyph kind="calendar" />
              <input type="date" value={start} onChange={event => { setStart(event.target.value); setPage(1) }} />
              <span className="chair-delegation-range-sep">to</span>
              <input type="date" value={end} onChange={event => { setEnd(event.target.value); setPage(1) }} />
            </span>
          </label>

          <label className="chair-delegation-search">
            <span className="chair-delegation-filter-label">Search</span>
            <span className="chair-delegation-search-box">
              <DelegationGlyph kind="search" />
              <input
                value={query}
                onChange={event => {
                  setQuery(event.target.value)
                  setPage(1)
                }}
                placeholder="Search delegations..."
              />
            </span>
          </label>
        </div>

        <div className="chair-delegation-filter-foot">
          <button className="chair-delegation-reset" onClick={resetFilters} type="button">
            <DelegationGlyph kind="reset" />
            <span>Reset</span>
          </button>
        </div>
      </section>

      <section className="chair-panel chair-delegation-table-panel">
        {error && <div className="chair-delegation-inline-error">{error}</div>}

        {loading ? (
          <Spinner />
        ) : rows.length === 0 ? (
          <Empty icon="[]" text="No delegations match the current filters." />
        ) : (
          <>
            <div className="chair-delegation-table-wrap">
              <table className="chair-delegation-table">
                <thead>
                  <tr>
                    <th>Policy / Subject</th>
                    <th>Delegated To</th>
                    <th>Authority</th>
                    <th>Limit</th>
                    <th>Validity</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row: any) => (
                    <tr key={row.id}>
                      <td data-label="Policy / Subject">
                        <div className="chair-delegation-subject">
                          <span className="chair-delegation-subject-icon"><DelegationGlyph kind={row.icon || 'shield'} /></span>
                          <div>
                            <strong>{row.subject}</strong>
                            <small>{row.reference_code} · {row.policy_type}</small>
                          </div>
                        </div>
                      </td>
                      <td data-label="Delegated To">
                        <div className="chair-delegation-target">
                          <strong>{row.to_name}</strong>
                          <small>{row.to_office || row.to_role} · {row.delegated_to_type}</small>
                        </div>
                      </td>
                      <td data-label="Authority">
                        <span className="chair-delegation-authority">{humanizeAccess(row.authority_label)}</span>
                      </td>
                      <td data-label="Limit" className="mono">{money(row.limit)}</td>
                      <td data-label="Validity">
                        <div className="chair-delegation-validity">
                          <strong>{formatDate(row.start)}</strong>
                          <small>to {formatDate(row.end)}</small>
                        </div>
                      </td>
                      <td data-label="Status">
                        <span className={`chair-delegation-status ${row.status_meta.tone}`}>{row.status_meta.label}</span>
                      </td>
                      <td data-label="Action">
                        <button className="chair-delegation-open" onClick={() => setSelectedRow(row)} type="button">View</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="chair-delegation-table-foot">
              <span>Showing {pagination.showing_from || 0} to {pagination.showing_to || 0} of {pagination.total || 0} delegations</span>

              <div className="chair-delegation-pagination">
                <button
                  className="chair-delegation-page-btn"
                  disabled={(pagination.page || 1) <= 1}
                  onClick={() => setPage((pagination.page || 1) - 1)}
                  type="button"
                >
                  <DelegationGlyph kind="left" />
                </button>
                {(pagination.visible_pages || []).map((entry: number) => (
                  <button
                    key={entry}
                    className={`chair-delegation-page-btn ${entry === pagination.page ? 'active' : ''}`}
                    onClick={() => setPage(entry)}
                    type="button"
                  >
                    {entry}
                  </button>
                ))}
                <button
                  className="chair-delegation-page-btn"
                  disabled={(pagination.page || 1) >= (pagination.total_pages || 1)}
                  onClick={() => setPage((pagination.page || 1) + 1)}
                  type="button"
                >
                  <DelegationGlyph kind="right" />
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      {showCreate && (
        <CreateDelegationModal
          form={data?.form}
          onClose={() => setShowCreate(false)}
          onDone={(delegation: any) => {
            setShowCreate(false)
            setSelectedRow(delegation)
            setReloadKey(key => key + 1)
          }}
        />
      )}

      {selectedRow && (
        <DelegationDetailModal
          row={selectedRow}
          user={user}
          onClose={() => setSelectedRow(null)}
          onDone={(next: any) => {
            setSelectedRow(next)
            setReloadKey(key => key + 1)
          }}
        />
      )}
    </div>
  )
}

function SummaryCard({ tone, icon, value, label, sub }: any) {
  return (
    <div className={`chair-delegation-summary ${tone}`}>
      <div className="chair-delegation-summary-icon"><DelegationGlyph kind={icon} /></div>
      <div className="chair-delegation-summary-copy">
        <strong>{value}</strong>
        <span>{label}</span>
        <small>{sub}</small>
      </div>
    </div>
  )
}

function FilterSelect({ label, value, options, onChange }: any) {
  return (
    <label className="chair-delegation-select">
      <span className="chair-delegation-filter-label">{label}</span>
      <select value={value} onChange={event => onChange(event.target.value)}>
        {options.map((option: any) => (
          <option key={option.key} value={option.key}>{option.label}</option>
        ))}
      </select>
    </label>
  )
}

function LegacyCreateDelegationModal({ form, onClose, onDone }: any) {
  const policies = form?.policies || []
  const recipients = form?.recipients || []
  const defaults = form?.defaults || {}
  const delegatedToTypes = form?.delegated_to_types || []

  const [policyKey, setPolicyKey] = useState(policies[0]?.key || '')
  const [recipientId, setRecipientId] = useState(recipients[0]?.id || '')
  const [delegatedToType, setDelegatedToType] = useState('')
  const [start, setStart] = useState(defaults.start || '')
  const [end, setEnd] = useState(defaults.end || '')
  const [limit, setLimit] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (policies[0]?.key && !policyKey) setPolicyKey(policies[0].key)
    if (recipients[0]?.id && !recipientId) setRecipientId(recipients[0].id)
  }, [policies, policyKey, recipientId, recipients])

  const selectedPolicy = useMemo(
    () => policies.find((item: any) => item.key === policyKey) || null,
    [policies, policyKey],
  )
  const selectedRecipient = useMemo(
    () => recipients.find((item: any) => item.id === recipientId) || null,
    [recipientId, recipients],
  )

  useEffect(() => {
    if (selectedPolicy && !delegatedToType) {
      setDelegatedToType(selectedPolicy.delegated_to_type_default || 'Individual')
    }
    if (selectedPolicy && selectedPolicy.default_limit != null && !limit) {
      setLimit(String(selectedPolicy.default_limit))
    }
  }, [delegatedToType, limit, selectedPolicy])

  async function submit() {
    if (!policyKey || !recipientId) {
      setError('Select a policy and recipient before saving.')
      return
    }
    if (!start || !end) {
      setError('Select the delegation date range.')
      return
    }
    if (end < start) {
      setError('End date must be after the start date.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const response = await api.chairmanCreateDelegation({
        policy_key: policyKey,
        to_user_id: recipientId,
        delegated_to_type: delegatedToType || selectedPolicy?.delegated_to_type_default || 'Individual',
        start,
        end,
        limit: limit ? Number(limit) : null,
        reason: reason.trim(),
      })
      onDone(response.delegation)
    } catch (err: any) {
      setError(err?.message || 'We could not create the delegation.')
      setBusy(false)
    }
  }

  return (
    <Modal
      title="Create Delegation"
      onClose={busy ? () => {} : onClose}
      className="chair-delegation-modal"
      footer={(
        <>
          <button className="btn btn-out" disabled={busy} onClick={onClose} type="button">Cancel</button>
          <button className="btn btn-crimson" disabled={busy} onClick={submit} type="button">
            {busy ? 'Saving...' : 'Create Delegation'}
          </button>
        </>
      )}
    >
      {error && <div className="chair-delegation-inline-error">{error}</div>}

      <div className="chair-delegation-form-grid">
        <Field label="Policy / Subject">
          <select className="select" value={policyKey} onChange={event => {
            setPolicyKey(event.target.value)
            setLimit('')
            setDelegatedToType('')
          }}>
            {policies.map((item: any) => (
              <option key={item.key} value={item.key}>{item.subject} · {item.policy_type}</option>
            ))}
          </select>
        </Field>

        <Field label="Delegated To">
          <select className="select" value={recipientId} onChange={event => setRecipientId(event.target.value)}>
            {recipients.map((item: any) => (
              <option key={item.id} value={item.id}>{item.label} · {item.office}</option>
            ))}
          </select>
        </Field>

        <Field label="Delegated To Type">
          <select className="select" value={delegatedToType} onChange={event => setDelegatedToType(event.target.value)}>
            {delegatedToTypes.map((item: any) => (
              <option key={item.key} value={item.key}>{item.label}</option>
            ))}
          </select>
        </Field>

        <Field label="Delegated Access">
          <div className="chair-delegation-preview-chip">{humanizeAccess(selectedPolicy?.authority || '-')}</div>
        </Field>

        <Field label="Start Date">
          <input className="inp" type="date" value={start} onChange={event => setStart(event.target.value)} />
        </Field>

        <Field label="End Date">
          <input className="inp" type="date" value={end} onChange={event => setEnd(event.target.value)} />
        </Field>

        <Field label="Limit">
          <input className="inp mono" value={limit} onChange={event => setLimit(event.target.value)} placeholder="Optional amount ceiling" />
        </Field>

        <Field label="Reason">
          <textarea className="inp chair-delegation-textarea" rows={4} value={reason} onChange={event => setReason(event.target.value)} placeholder="Why this authority is being delegated." />
        </Field>
      </div>

      {selectedPolicy && (
        <div className="chair-delegation-preview">
          <div className="chair-delegation-preview-row">
            <strong>{selectedPolicy.subject}</strong>
            <span>{selectedPolicy.policy_type}</span>
          </div>
          <div className="chair-delegation-preview-body">
            <small>Resource scope</small>
            <span>{selectedPolicy.resource_scope || '*'}</span>
          </div>
          {selectedRecipient && (
            <div className="chair-delegation-preview-body">
              <small>Recipient</small>
              <span>{selectedRecipient.label} · {selectedRecipient.office}</span>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}

function CreateDelegationModal({ form, onClose, onDone }: any) {
  const policyTypes = form?.policy_types || []
  const recipients = form?.recipients || []
  const scopes = form?.delegation_scopes || []
  const accessLevels = form?.access_levels || []
  const reviewFrequencies = form?.review_frequencies || []
  const subjectSuggestions = form?.subject_suggestions || []
  const defaults = form?.defaults || {}
  const defaultPolicyType = policyTypes.find((item: any) => item.key !== '__new__')?.key || policyTypes[0]?.key || ''

  const [subject, setSubject] = useState('')
  const [policyTypeKey, setPolicyTypeKey] = useState(defaultPolicyType)
  const [newPolicyType, setNewPolicyType] = useState('')
  const [description, setDescription] = useState('')
  const [recipientId, setRecipientId] = useState(recipients[0]?.id || '')
  const [scopeKey, setScopeKey] = useState(scopes[0]?.key || '')
  const [accessKey, setAccessKey] = useState(accessLevels[0]?.key || '')
  const [start, setStart] = useState(defaults.start || '')
  const [end, setEnd] = useState(defaults.end || '')
  const [reviewFrequencyKey, setReviewFrequencyKey] = useState(defaults.review_frequency_key || 'none')
  const [limit, setLimit] = useState('')
  const [notes, setNotes] = useState('')
  const [attachment, setAttachment] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (defaultPolicyType && !policyTypeKey) setPolicyTypeKey(defaultPolicyType)
    if (recipients[0]?.id && !recipientId) setRecipientId(recipients[0].id)
    if (scopes[0]?.key && !scopeKey) setScopeKey(scopes[0].key)
    if (accessLevels[0]?.key && !accessKey) setAccessKey(accessLevels[0].key)
  }, [accessKey, accessLevels, defaultPolicyType, policyTypeKey, recipientId, recipients, scopeKey, scopes])

  const selectedRecipient = useMemo(
    () => recipients.find((item: any) => item.id === recipientId) || null,
    [recipientId, recipients],
  )
  const selectedPolicyType = useMemo(
    () => policyTypes.find((item: any) => item.key === policyTypeKey) || null,
    [policyTypeKey, policyTypes],
  )
  const selectedScope = useMemo(
    () => scopes.find((item: any) => item.key === scopeKey) || null,
    [scopeKey, scopes],
  )
  const selectedAccess = useMemo(
    () => accessLevels.find((item: any) => item.key === accessKey) || null,
    [accessKey, accessLevels],
  )
  const selectedReview = useMemo(
    () => reviewFrequencies.find((item: any) => item.key === reviewFrequencyKey) || null,
    [reviewFrequencies, reviewFrequencyKey],
  )
  const subjectTemplate = useMemo(() => {
    const clean = subject.trim().toLowerCase()
    if (!clean) return null
    return subjectSuggestions.find((item: any) => String(item.subject || '').trim().toLowerCase() === clean) || null
  }, [subject, subjectSuggestions])

  useEffect(() => {
    if (!subjectTemplate) return
    if (!limit && subjectTemplate.default_limit != null) {
      setLimit(String(subjectTemplate.default_limit))
    }
    if (subjectTemplate.scope_key) {
      setScopeKey(subjectTemplate.scope_key)
    }
    if (subjectTemplate.access_key) {
      setAccessKey(subjectTemplate.access_key)
    }
    if (subjectTemplate.policy_type_key && policyTypeKey !== '__new__') {
      setPolicyTypeKey(subjectTemplate.policy_type_key)
    }
  }, [limit, policyTypeKey, subjectTemplate])

  async function onAttachmentChange(event: any) {
    const file = event.target.files?.[0]
    if (!file) {
      setAttachment(null)
      return
    }
    const name = String(file.name || '').toLowerCase()
    if (!(name.endsWith('.pdf') || name.endsWith('.doc') || name.endsWith('.docx'))) {
      setError('Only PDF, DOC or DOCX files can be attached.')
      event.target.value = ''
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('Attachments must be 10MB or smaller.')
      event.target.value = ''
      return
    }
    try {
      const dataUrl = await readFileAsDataUrl(file)
      setAttachment({
        name: file.name,
        mime_type: file.type || '',
        size: file.size,
        data_b64: dataUrl.split(',', 2)[1] || '',
      })
      setError('')
    } catch {
      setError('We could not read the attachment. Please try again.')
      event.target.value = ''
    }
  }

  async function submit() {
    if (!subject.trim()) {
      setError('Enter a policy or delegation subject.')
      return
    }
    if (!policyTypeKey) {
      setError('Select a policy type before saving.')
      return
    }
    if (policyTypeKey === '__new__' && !newPolicyType.trim()) {
      setError('Enter the new policy type name.')
      return
    }
    if (!recipientId || !scopeKey || !accessKey) {
      setError('Select the recipient, delegation scope and delegated access before saving.')
      return
    }
    if (!start || !end) {
      setError('Select the delegation date range.')
      return
    }
    if (end < start) {
      setError('End date must be after the start date.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const response = await api.chairmanCreateDelegation({
        subject: subject.trim(),
        policy_type_key: policyTypeKey,
        new_policy_type: newPolicyType.trim(),
        description: description.trim(),
        to_user_id: recipientId,
        delegation_scope_key: scopeKey,
        access_key: accessKey,
        start,
        end,
        limit: limit ? Number(limit) : null,
        review_frequency_key: reviewFrequencyKey || 'none',
        notes: notes.trim(),
        attachment,
      })
      onDone(response.delegation)
    } catch (err: any) {
      setError(err?.message || 'We could not create the delegation.')
      setBusy(false)
    }
  }

  return (
    <Modal
      title="Create New Delegation"
      onClose={busy ? () => {} : onClose}
      className="chair-delegation-modal"
      footer={(
        <>
          <button className="btn btn-out" disabled={busy} onClick={onClose} type="button">Cancel</button>
          <button className="btn btn-crimson" disabled={busy} onClick={submit} type="button">
            {busy ? 'Saving...' : 'Create Delegation'}
          </button>
        </>
      )}
    >
      {error && <div className="chair-delegation-inline-error">{error}</div>}

      <div className="chair-delegation-form-grid">
        <div className="chair-delegation-section">
          <div className="chair-delegation-section-title">Policy / Delegation Details</div>

          <Field label="Policy / Subject" required>
            <>
              <input
                className="inp"
                list="chair-delegation-subjects"
                value={subject}
                onChange={event => setSubject(event.target.value)}
                placeholder="e.g. Leave Approval Policy"
              />
              <datalist id="chair-delegation-subjects">
                {subjectSuggestions.map((item: any) => (
                  <option key={`${item.policy_type}-${item.subject}`} value={item.subject} />
                ))}
              </datalist>
            </>
          </Field>

          <Field label="Policy Type" required>
            <select className="select" value={policyTypeKey} onChange={event => setPolicyTypeKey(event.target.value)}>
              {policyTypes.map((item: any) => (
                <option key={item.key} value={item.key}>{item.label}</option>
              ))}
            </select>
          </Field>

          {policyTypeKey === '__new__' && (
            <Field label="New Policy Type" required>
              <input
                className="inp"
                value={newPolicyType}
                onChange={event => setNewPolicyType(event.target.value)}
                placeholder="Enter the new policy type"
              />
            </Field>
          )}

          <Field label="Description" className="chair-delegation-span-2">
            <textarea
              className="inp chair-delegation-textarea chair-delegation-textarea-compact"
              rows={3}
              value={description}
              onChange={event => setDescription(event.target.value)}
              placeholder="Brief description of the policy or delegation"
            />
          </Field>
        </div>

        <div className="chair-delegation-section">
          <div className="chair-delegation-section-title">Delegation Details</div>

          <div className="chair-delegation-form-split">
            <Field label="Delegated To" required>
              <select className="select" value={recipientId} onChange={event => setRecipientId(event.target.value)}>
                {recipients.map((item: any) => (
                  <option key={item.id} value={item.id}>{item.label} Â· {item.office}</option>
                ))}
              </select>
            </Field>

            <Field label="Delegation Scope" required>
              <select className="select" value={scopeKey} onChange={event => setScopeKey(event.target.value)}>
                {scopes.map((item: any) => (
                  <option key={item.key} value={item.key}>{item.label}</option>
                ))}
              </select>
            </Field>
          </div>

          <div className="chair-delegation-form-split">
            <Field label="Delegated Access" required>
              <select className="select" value={accessKey} onChange={event => setAccessKey(event.target.value)}>
                {accessLevels.map((item: any) => (
                  <option key={item.key} value={item.key}>{item.label}</option>
                ))}
              </select>
            </Field>

            <Field label="Approval Limit">
              <input
                className="inp mono"
                value={limit}
                onChange={event => setLimit(event.target.value)}
                placeholder="Enter financial or operational limit"
              />
            </Field>
          </div>

          <div className="chair-delegation-form-split">
            <Field label="Effective From" required>
              <input className="inp" type="date" value={start} onChange={event => setStart(event.target.value)} />
            </Field>

            <Field label="Effective Till" required>
              <input className="inp" type="date" value={end} onChange={event => setEnd(event.target.value)} />
            </Field>
          </div>

          <Field label="Review Frequency">
            <select className="select" value={reviewFrequencyKey} onChange={event => setReviewFrequencyKey(event.target.value)}>
              {reviewFrequencies.map((item: any) => (
                <option key={item.key} value={item.key}>{item.label}</option>
              ))}
            </select>
          </Field>

          <Field label="Notes / Conditions" className="chair-delegation-span-2">
            <textarea
              className="inp chair-delegation-textarea chair-delegation-textarea-compact"
              rows={3}
              value={notes}
              onChange={event => setNotes(event.target.value)}
              placeholder="Add any additional notes or conditions"
            />
          </Field>

          <Field label="Attachments" className="chair-delegation-span-2">
            <div className="chair-delegation-upload">
              <label className="chair-delegation-upload-btn">
                <input type="file" accept=".pdf,.doc,.docx" onChange={onAttachmentChange} />
                <span>Upload Document</span>
              </label>
              <span className="chair-delegation-upload-note">
                {attachment?.name ? `${attachment.name} Â· ${Math.round((attachment.size || 0) / 1024)} KB` : 'PDF, DOC, DOCX up to 10MB'}
              </span>
            </div>
          </Field>
        </div>
      </div>

      <div className="chair-delegation-preview">
        <div className="chair-delegation-preview-row">
          <strong>{subject.trim() || 'Delegation preview'}</strong>
          <span>{policyTypeKey === '__new__' ? (newPolicyType.trim() || 'New policy type') : (selectedPolicyType?.label || 'Policy type')}</span>
        </div>
        <div className="chair-delegation-preview-body">
          <small>Delegated to</small>
          <span>{selectedRecipient ? `${selectedRecipient.label} Â· ${selectedRecipient.office}` : 'Select office or staff'}</span>
        </div>
        <div className="chair-delegation-preview-body">
          <small>Delegated access</small>
          <span>{selectedAccess?.label || 'Select access'}</span>
        </div>
        <div className="chair-delegation-preview-body">
          <small>Delegation scope</small>
          <span>{selectedScope?.label || 'Select scope'}</span>
        </div>
        <div className="chair-delegation-preview-body">
          <small>Review frequency</small>
          <span>{selectedReview?.label || 'None'}</span>
        </div>
        {!!description.trim() && (
          <div className="chair-delegation-preview-body">
            <small>Description</small>
            <span>{description.trim()}</span>
          </div>
        )}
        {!!notes.trim() && (
          <div className="chair-delegation-preview-body">
            <small>Notes</small>
            <span>{notes.trim()}</span>
          </div>
        )}
      </div>
    </Modal>
  )
}

function DelegationDetailModal({ row, user, onClose, onDone }: { row: any; user: any; onClose: () => void; onDone: (row: any) => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const attachmentHref = row?.attachment?.data_b64
    ? `data:${row.attachment.mime_type || 'application/octet-stream'};base64,${row.attachment.data_b64}`
    : ''

  async function revoke() {
    setBusy(true)
    setError('')
    try {
      const response = await api.revokeDelegation(row.id)
      onDone(response)
    } catch (err: any) {
      setError(err?.message || 'We could not revoke that delegation.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title="Delegation Details"
      onClose={busy ? () => {} : onClose}
      className="chair-delegation-modal chair-delegation-detail-modal"
      footer={(
        <>
          <button className="btn btn-out" disabled={busy} onClick={onClose} type="button">Close</button>
          {row.from === user.username && row.active && (
            <button className="btn btn-rose" disabled={busy} onClick={revoke} type="button">Revoke Delegation</button>
          )}
        </>
      )}
    >
      {error && <div className="chair-delegation-inline-error">{error}</div>}

      <div className="chair-delegation-detail">
        <div className="chair-delegation-detail-grid">
          <Meta label="Reference">{row.reference_code || '-'}</Meta>
          <Meta label="Policy Type">{row.policy_type}</Meta>
          <Meta label="Delegated Access">{humanizeAccess(row.authority_label)}</Meta>
          <Meta label="Limit">{money(row.limit)}</Meta>
        </div>

        <div className="chair-delegation-note">
          <strong>{row.subject}</strong>
          <span>{row.description || row.reason || 'No additional note was captured for this delegation.'}</span>
        </div>

        <div className="chair-delegation-detail-grid">
          <Meta label="Delegated To">{row.to_name}</Meta>
          <Meta label="Role / Office">{row.to_office || row.to_role}</Meta>
          <Meta label="Validity">{formatDate(row.start)} to {formatDate(row.end)}</Meta>
          <Meta label="Status">{row.status_meta.label}</Meta>
        </div>

        <div className="chair-delegation-preview">
          <div className="chair-delegation-preview-body">
            <small>Delegation scope</small>
            <span>{row.resource_scope_label || row.resource_scope || '*'}</span>
          </div>
          <div className="chair-delegation-preview-body">
            <small>Delegated to type</small>
            <span>{row.delegated_to_type}</span>
          </div>
          <div className="chair-delegation-preview-body">
            <small>Review frequency</small>
            <span>{row.review_frequency_label || 'None'}</span>
          </div>
          {!!row.notes && (
            <div className="chair-delegation-preview-body">
              <small>Notes / Conditions</small>
              <span>{row.notes}</span>
            </div>
          )}
          {!!attachmentHref && (
            <div className="chair-delegation-preview-body">
              <small>Attachment</small>
              <a className="chair-delegation-link" href={attachmentHref} download={row.attachment.name}>{row.attachment.name}</a>
            </div>
          )}
          {!!row.expiring_in_days && (
            <div className="chair-delegation-preview-body">
              <small>Expires in</small>
              <span>{row.expiring_in_days} days</span>
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}

function Field({ label, children, required = false, className = '' }: any) {
  return (
    <label className={`form-row ${className}`.trim()}>
      <span>{label}{required ? ' *' : ''}</span>
      {children}
    </label>
  )
}

function Meta({ label, children }: any) {
  return (
    <div className="chair-delegation-meta">
      <small>{label}</small>
      <strong>{children}</strong>
    </div>
  )
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function humanizeAccess(value: string) {
  const raw = String(value || '').trim()
  if (!raw) return '-'
  return raw
    .split(':')
    .map(part => part.replace(/_/g, ' '))
    .map(part => part.replace(/\b\w/g, char => char.toUpperCase()))
    .join(' · ')
}

function readFileAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error || new Error('file_read_failed'))
    reader.readAsDataURL(file)
  })
}

function DelegationGlyph({ kind }: { kind: string }) {
  switch (kind) {
    case 'total':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="6" y="4" width="12" height="16" rx="2" /><path d="M9 8h6M9 12h6M9 16h4" /></svg>
    case 'active':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="5" y="4" width="14" height="16" rx="2" /><path d="m9 12 2 2 4-5" /></svg>
    case 'expiring':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M9 3h6M10 3v4l-4.5 8.1A2 2 0 0 0 7.3 18h9.4a2 2 0 0 0 1.8-2.9L14 7V3" /><path d="M9 14h6" /></svg>
    case 'inactive':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9" /><path d="m9 9 6 6M15 9l-6 6" /></svg>
    case 'search':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="11" cy="11" r="6" /><path d="m20 20-3.5-3.5" /></svg>
    case 'reset':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M20 6v6h-6" /><path d="M20 12a8 8 0 1 1-2.34-5.66L20 8.5" /></svg>
    case 'left':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m15 18-6-6 6-6" /></svg>
    case 'right':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m9 6 6 6-6 6" /></svg>
    case 'calendar':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 3v4M16 3v4M3 10h18" /></svg>
    case 'finance':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3v18" /><path d="M16.5 7.5c0-1.93-2.01-3.5-4.5-3.5s-4.5 1.57-4.5 3.5S9.51 11 12 11s4.5 1.57 4.5 3.5S14.49 18 12 18s-4.5-1.57-4.5-3.5" /></svg>
    case 'people':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>
    case 'academy':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m3 8 9-4 9 4-9 4-9-4Z" /><path d="M7 10v4c0 1.7 2.2 3 5 3s5-1.3 5-3v-4" /></svg>
    case 'shield':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 4 5 7v5c0 4.2 2.9 7.9 7 8.9 4.1-1 7-4.7 7-8.9V7l-7-3Z" /><path d="M9.5 12 11 13.5l3.5-4" /></svg>
    default:
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8" /></svg>
  }
}
