import { type ReactNode, useEffect, useState } from 'react'
import { api } from '../api'
import { Spinner, money } from '../modules/kit'

type SectionState<T> = {
  data: T
  loading: boolean
  error: string
}

type SectionKey = 'classes' | 'announcements' | 'tasks' | 'assessments' | 'digitalId'

const EMPTY_CLASSES: any[] = []
const EMPTY_ANNOUNCEMENTS: any[] = []
const EMPTY_TASKS: any[] = []
const EMPTY_ASSESSMENTS: any[] = []

export default function StudentHome({ user, go }: { user: any; go: (v: string) => void }) {
  const [home, setHome] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [sections, setSections] = useState<Record<SectionKey, SectionState<any>>>({
    classes: { data: EMPTY_CLASSES, loading: true, error: '' },
    announcements: { data: EMPTY_ANNOUNCEMENTS, loading: true, error: '' },
    tasks: { data: EMPTY_TASKS, loading: true, error: '' },
    assessments: { data: EMPTY_ASSESSMENTS, loading: true, error: '' },
    digitalId: { data: null, loading: true, error: '' },
  })

  useEffect(() => {
    let active = true

    async function load() {
      setLoading(true)
      setError('')
      setSections({
        classes: { data: EMPTY_CLASSES, loading: true, error: '' },
        announcements: { data: EMPTY_ANNOUNCEMENTS, loading: true, error: '' },
        tasks: { data: EMPTY_TASKS, loading: true, error: '' },
        assessments: { data: EMPTY_ASSESSMENTS, loading: true, error: '' },
        digitalId: { data: null, loading: true, error: '' },
      })

      const [homeRes, digitalIdRes, classesRes, announcementsRes, tasksRes, assessmentsRes] = await Promise.allSettled([
        api.studentHome(),
        api.studentDigitalId(),
        api.studentTodayClasses(),
        api.studentAnnouncements(),
        api.studentTasks(),
        api.studentUpcomingAssessments(),
      ])

      if (!active) return

      if (homeRes.status !== 'fulfilled') {
        setHome(null)
        setError('The student portal could not resolve a linked profile for this login.')
        setLoading(false)
        return
      }

      setHome(homeRes.value)
      setSections({
        classes: settledSection(classesRes, 'classes'),
        announcements: settledSection(announcementsRes, 'announcements'),
        tasks: settledSection(tasksRes, 'tasks'),
        assessments: settledSection(assessmentsRes, 'assessments'),
        digitalId: settledSection(digitalIdRes, 'digitalId'),
      })
      setLoading(false)
    }

    load()
    return () => {
      active = false
    }
  }, [reloadKey])

  if (loading) return <Spinner />

  if (error || !home) {
    return (
      <div className="card fade-in">
        <div className="card-h"><h3>Student overview unavailable</h3></div>
        <div className="card-pad">
          <p style={{ color: 'var(--txt-soft)', lineHeight: 1.7 }}>
            {error || 'The student overview is unavailable for this session.'}
          </p>
          <button className="btn btn-crimson" onClick={() => setReloadKey(key => key + 1)} type="button">
            Try again
          </button>
        </div>
      </div>
    )
  }

  const profile = home.profile || {}
  const kpis = home.kpis || {}
  const digitalId = sections.digitalId.data?.digital_id || home.digital_id || null
  const initials = getInitials(profile.name || user.name || 'S')
  const backlogSubjects = kpis.backlog_subjects || profile.backlog_subjects || []
  const backlogPreview = formatBacklogPreview(backlogSubjects)

  return (
    <div className="student-overview fade-in">
      <div className="student-hero-grid">
        <StudentProfileBanner
          initials={initials}
          profile={profile}
          kpis={kpis}
          backlogPreview={backlogPreview}
        />
        <DigitalIdCard initials={initials} digitalId={digitalId} />
      </div>

      <div className="student-kpi-grid">
        <StudentKpiCard
          tone="violet"
          icon="results"
          label="CGPA"
          value={kpis.cgpa != null ? `${Number(kpis.cgpa).toFixed(2)} / 10` : '-'}
          sub={kpis.cgpa_label || (kpis.cgpa != null && kpis.cgpa >= 8 ? 'Excellent' : 'Current standing')}
        />
        <StudentKpiCard
          tone="rose"
          icon="backlogs"
          label="Current Backlogs"
          value={String(kpis.current_backlogs ?? 0)}
          sub={backlogPreview || kpis.backlog_label || 'No active backlog'}
        />
        <StudentKpiCard
          tone="amber"
          icon="fees"
          label="Fee Balance"
          value={money(kpis.fee_balance)}
          sub={(kpis.fee_balance || 0) > 0 && kpis.fee_due_date ? `Due by ${formatDate(kpis.fee_due_date)}` : (kpis.fee_label || 'No dues')}
        />
        <StudentKpiCard
          tone="blue"
          icon="library"
          label="Library Loans"
          value={`${kpis.library_loans ?? 0} / ${kpis.loan_limit || 5}`}
          sub={kpis.library_label || ((kpis.library_loans || 0) > 0 ? 'Active loans' : '0 active loans')}
        />
      </div>

      <div className="student-lower-grid">
        <PanelCard
          title="Today's Classes"
          actionLabel="View Full Schedule"
          onAction={() => go('academics')}
        >
          <TodayClassesPanel state={sections.classes} />
        </PanelCard>

        <PanelCard
          title="Announcements"
          actionLabel="View All"
          onAction={() => go('calendar')}
        >
          <AnnouncementsPanel state={sections.announcements} />
        </PanelCard>

        <div className="student-right-stack">
          <PanelCard
            title="My Tasks"
            actionLabel="View All"
            onAction={() => go('academics')}
          >
            <TasksPanel state={sections.tasks} />
          </PanelCard>

          <PanelCard
            title="Upcoming Quiz / Test"
            actionLabel="View All"
            onAction={() => go('examinations')}
          >
            <UpcomingAssessmentsPanel state={sections.assessments} />
          </PanelCard>
        </div>
      </div>
    </div>
  )
}

function settledSection(result: PromiseSettledResult<any>, key: SectionKey): SectionState<any> {
  if (result.status !== 'fulfilled') {
    return {
      data: key === 'classes' ? EMPTY_CLASSES
        : key === 'announcements' ? EMPTY_ANNOUNCEMENTS
        : key === 'tasks' ? EMPTY_TASKS
        : key === 'assessments' ? EMPTY_ASSESSMENTS
        : null,
      loading: false,
      error: 'This panel is unavailable right now.',
    }
  }

  const payload = result.value || {}
  switch (key) {
    case 'classes':
      return { data: payload.classes || EMPTY_CLASSES, loading: false, error: '' }
    case 'announcements':
      return { data: payload.announcements || EMPTY_ANNOUNCEMENTS, loading: false, error: '' }
    case 'tasks':
      return { data: payload.tasks || EMPTY_TASKS, loading: false, error: '' }
    case 'assessments':
      return { data: payload.assessments || EMPTY_ASSESSMENTS, loading: false, error: '' }
    case 'digitalId':
      return { data: payload, loading: false, error: '' }
  }
}

function StudentProfileBanner({
  initials,
  profile,
  kpis,
  backlogPreview,
}: {
  initials: string
  profile: any
  kpis: any
  backlogPreview: string
}) {
  const badges = [
    profile.student_type || 'Regular',
    profile.hosteller ? 'Hosteller' : '',
    profile.scholarship ? 'Scholarship' : '',
  ].filter(Boolean)

  return (
    <section className="student-profile-banner">
      <div className="student-profile-copy">
        <div className="student-avatar">{initials}</div>
        <div className="student-profile-text">
          <div className="student-profile-name">{profile.name}</div>
          <div className="student-profile-subline">
            <span className="mono">{profile.roll_no}</span>
            <span>{profile.program || profile.department}</span>
          </div>
          <div className="student-profile-meta">
            <span>{profile.study_year_label ? `${profile.study_year_label} Year` : `Semester ${profile.semester}`}</span>
            <span>Semester {profile.semester}</span>
            <span>Batch {profile.batch}</span>
            {profile.section ? <span>Section {profile.section}</span> : null}
          </div>
          <div className="student-badge-row">
            {badges.map((badge: string) => (
              <span key={badge} className={`student-badge ${badge === 'Scholarship' ? 'accent' : ''}`}>{badge}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="student-profile-stats">
        <ProfileStat
          label="CGPA"
          value={kpis.cgpa != null ? `${Number(kpis.cgpa).toFixed(2)} / 10` : '-'}
          detail={kpis.cgpa_label || 'Current standing'}
        />
        <ProfileStat
          label="Current Backlogs"
          value={String(kpis.current_backlogs ?? 0)}
          detail={backlogPreview || kpis.backlog_label || 'No active backlog'}
        />
      </div>
    </section>
  )
}

function ProfileStat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="student-profile-stat">
      <div className="student-profile-stat-value">{value}</div>
      <div className="student-profile-stat-label">{label}</div>
      {detail ? <div className="student-profile-stat-detail">{detail}</div> : null}
    </div>
  )
}

function DigitalIdCard({ initials, digitalId }: { initials: string; digitalId: any }) {
  if (!digitalId) {
    return (
      <section className="student-digital-shell">
        <div className="student-digital-title">Digital ID</div>
        <div className="student-digital-empty">Digital ID unavailable</div>
      </section>
    )
  }

  const qrMatrix = buildQrMatrix(String(digitalId.verification_payload || 'ICMS:ID'))
  const barcodeValue = String(digitalId.card_number || digitalId.student_id || '')

  return (
    <section className="student-digital-shell">
      <div className="student-digital-title">Digital ID</div>
      <div className="student-id-card">
        <div className="student-id-card-top">
          <div>
            <div className="student-id-brand">ICMS</div>
            <div className="student-id-sub">Identity Card</div>
          </div>
          <div className="student-id-dots">...</div>
        </div>

        <div className="student-id-main">
          <div className="student-id-person">
            <div className="student-id-avatar">{initials}</div>
            <div>
              <div className="student-id-name">{digitalId.student_name}</div>
              <div className="student-id-roll mono">{digitalId.student_id}</div>
            </div>
          </div>
          <QrCode matrix={qrMatrix} />
        </div>

        <div className="student-id-barcode-wrap">
          <Barcode value={barcodeValue} />
          <div className="student-id-card-number mono">{digitalId.card_number}</div>
        </div>
      </div>

      <div className="student-digital-meta">
        <MetaRow label="Programme" value={digitalId.programme || '-'} />
        <MetaRow
          label="Year / Semester"
          value={`${digitalId.study_year ? `${ordinal(digitalId.study_year)} Year` : 'Year'} / Semester ${digitalId.semester || '-'}`}
        />
        <MetaRow label="Blood Group" value={digitalId.blood_group || '-'} />
        <MetaRow label="Valid Until" value={formatDate(digitalId.valid_until)} />
      </div>

      <div className={`student-id-valid ${digitalId.status_label === 'Valid' ? 'ok' : 'bad'}`}>
        {digitalId.status_label}: {formatDate(digitalId.valid_until)}
      </div>
    </section>
  )
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="student-meta-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function StudentKpiCard({
  tone,
  icon,
  label,
  value,
  sub,
}: {
  tone: string
  icon: string
  label: string
  value: string
  sub: string
}) {
  return (
    <article className="student-kpi-card">
      <div className={`student-kpi-icon ${tone}`}>
        <PortalGlyph kind={icon} />
      </div>
      <div className="student-kpi-copy">
        <div className="student-kpi-label">{label}</div>
        <div className="student-kpi-value">{value}</div>
        <div className="student-kpi-sub">{sub}</div>
      </div>
    </article>
  )
}

function PanelCard({
  title,
  actionLabel,
  onAction,
  children,
}: {
  title: string
  actionLabel?: string
  onAction?: () => void
  children: ReactNode
}) {
  return (
    <section className="student-panel">
      <div className="student-panel-head">
        <h3>{title}</h3>
        {actionLabel && onAction && (
          <button className="student-panel-link" onClick={onAction} type="button">
            {actionLabel}
          </button>
        )}
      </div>
      <div className="student-panel-body">{children}</div>
    </section>
  )
}

function TodayClassesPanel({ state }: { state: SectionState<any[]> }) {
  if (state.loading) return <InlineState text="Loading today's classes..." />
  if (state.error) return <InlineState tone="error" text={state.error} />
  if (!state.data.length) {
    return <EmptyPanelState title="No classes scheduled for today" sub="New timetable entries from the academic office will appear here." />
  }

  return (
    <div className="student-list">
      {state.data.slice(0, 5).map((item: any, index: number) => (
        <div className="student-class-row" key={item.timetable_entry_id}>
          <div className="student-class-slot">{toClock(item.start_time)} - {toClock(item.end_time)}</div>
          <span className={`student-class-marker tone-${index % 5}`} />
          <div className="student-class-copy">
            <div className="student-class-title">{item.course_code} - {item.course_title}</div>
            <div className="student-row-meta">{item.source_label}</div>
            <div className="student-class-sub">{joinParts([item.room, item.faculty])}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function AnnouncementsPanel({ state }: { state: SectionState<any[]> }) {
  if (state.loading) return <InlineState text="Loading announcements..." />
  if (state.error) return <InlineState tone="error" text={state.error} />
  if (!state.data.length) {
    return <EmptyPanelState title="No new announcements" sub="Department and student-affairs updates will appear here." />
  }

  return (
    <div className="student-list">
      {state.data.slice(0, 4).map((item: any) => (
        <div className="student-simple-row" key={item.id}>
          <div className="student-row-icon amber">
            <PortalGlyph kind="support" />
          </div>
          <div className="student-row-copy">
            <div className="student-row-title">
              {item.title}
              {item.is_new && <span className="student-mini-badge">New</span>}
            </div>
            <div className="student-row-sub">{joinParts([item.source_label || item.source_office, relativeTime(item.published_at)])}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function TasksPanel({ state }: { state: SectionState<any[]> }) {
  if (state.loading) return <InlineState text="Loading tasks..." />
  if (state.error) return <InlineState tone="error" text={state.error} />
  if (!state.data.length) {
    return <EmptyPanelState title="No pending tasks" sub="Faculty-published coursework will appear here automatically." />
  }

  return (
    <div className="student-list">
      {state.data.slice(0, 3).map((item: any) => (
        <div className="student-task-row" key={item.id}>
          <div className="student-row-copy">
            <div className="student-row-title">{item.title}</div>
            <div className="student-row-sub">{joinParts([item.course_title || item.course_code, item.source_label])}</div>
          </div>
          <span className={`student-status-pill ${urgencyTone(item.urgency)}`}>{item.urgency || 'Open'}</span>
        </div>
      ))}
    </div>
  )
}

function UpcomingAssessmentsPanel({ state }: { state: SectionState<any[]> }) {
  if (state.loading) return <InlineState text="Loading upcoming assessments..." />
  if (state.error) return <InlineState tone="error" text={state.error} />
  if (!state.data.length) {
    return <EmptyPanelState icon="calendar" title="No upcoming quizzes or tests" sub="Faculty and examination schedules will appear here once published." />
  }

  return (
    <div className="student-list">
      {state.data.slice(0, 3).map((item: any) => (
        <div className="student-assessment-row" key={item.id}>
          <div className="student-row-copy">
            <div className="student-row-title">
              {item.name}
              <span className="student-type-pill">{String(item.type || 'quiz').toUpperCase()}</span>
            </div>
            <div className="student-row-sub">{joinParts([item.course_title || item.course_code, item.source_label])}</div>
          </div>
          <div className="student-assessment-meta">
            <span>{formatDate(item.scheduled_at)}</span>
            <span>{timeRange(item.scheduled_at, item.end_at)}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

function InlineState({ text, tone = 'normal' }: { text: string; tone?: 'normal' | 'error' }) {
  return <div className={`student-inline-state ${tone}`}>{text}</div>
}

function EmptyPanelState({
  icon = 'spark',
  title,
  sub,
}: {
  icon?: 'spark' | 'calendar'
  title: string
  sub: string
}) {
  return (
    <div className="student-empty-state">
      <div className={`student-empty-icon ${icon}`}>
        <PortalGlyph kind={icon === 'calendar' ? 'calendar' : 'support'} />
      </div>
      <strong>{title}</strong>
      <span>{sub}</span>
    </div>
  )
}

function getInitials(name: string) {
  return name
    .split(' ')
    .filter(Boolean)
    .map(part => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function formatDate(value?: string, withTime = false) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('en-IN', withTime
    ? { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { day: '2-digit', month: 'short', year: 'numeric' },
  ).format(parsed)
}

function relativeTime(value?: string) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  const diffMs = Date.now() - parsed.getTime()
  const diffHours = Math.round(diffMs / (1000 * 60 * 60))
  if (diffHours < 24) {
    const hours = Math.max(diffHours, 1)
    return `${hours} hour${hours === 1 ? '' : 's'} ago`
  }
  const diffDays = Math.round(diffHours / 24)
  return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`
}

function toClock(value?: string) {
  if (!value) return '-'
  const [hours, minutes] = String(value).split(':').map(Number)
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return value
  const suffix = hours >= 12 ? 'PM' : 'AM'
  const twelve = hours % 12 || 12
  return `${String(twelve).padStart(2, '0')}:${String(minutes).padStart(2, '0')} ${suffix}`
}

function urgencyTone(value: string) {
  const key = String(value || '').toLowerCase()
  if (key.includes('overdue') || key.includes('today')) return 'danger'
  if (key.includes('tomorrow')) return 'warn'
  return 'ok'
}

function formatBacklogPreview(subjects: any[]) {
  if (!subjects.length) return ''
  const preview = subjects.slice(0, 2)
    .map(item => [item.subject_code, item.subject_title].filter(Boolean).join(' - '))
    .filter(Boolean)
    .join(' / ')
  return subjects.length > 2 ? `${preview} / +${subjects.length - 2} more` : preview
}

function joinParts(parts: Array<string | undefined | null>) {
  return parts.map(part => String(part || '').trim()).filter(Boolean).join(' / ')
}

function ordinal(value?: number | string) {
  const parsed = Number(value || 0)
  if (!parsed) return ''
  if (parsed % 100 >= 10 && parsed % 100 <= 20) return `${parsed}th`
  const suffix = parsed % 10 === 1 ? 'st' : parsed % 10 === 2 ? 'nd' : parsed % 10 === 3 ? 'rd' : 'th'
  return `${parsed}${suffix}`
}

function timeRange(start?: string, end?: string) {
  if (!start) return '-'
  const first = new Date(start)
  if (Number.isNaN(first.getTime())) return start
  const startText = new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit' }).format(first)
  if (!end) return startText
  const second = new Date(end)
  if (Number.isNaN(second.getTime())) return startText
  return `${startText} - ${new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit' }).format(second)}`
}

function PortalGlyph({ kind }: { kind: string }) {
  switch (kind) {
    case 'courses':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 0 4 23V5.5Z" /><path d="M12 3v18" /></svg>
    case 'attendance':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m5 12 4 4 10-10" /></svg>
    case 'fees':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 5h9" /><path d="M7 9h7" /><path d="M9 5c0 6 5 4 5 9 0 2-2 4-5 4" /></svg>
    case 'library':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M6 4h12v16H6z" /><path d="M9 4v16" /></svg>
    case 'results':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 4h10l3 3v13H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" /><path d="M15 4v3h3M9 13h6M9 17h4" /></svg>
    case 'backlogs':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8" /><path d="M12 8v5" /><path d="M12 16h.01" /></svg>
    case 'support':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3 4 7v6c0 5 3.4 7.8 8 9 4.6-1.2 8-4 8-9V7l-8-4Z" /><path d="M9 12h6M12 9v6" /></svg>
    case 'calendar':
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 3v4M17 3v4M4 9h16" /><rect x="4" y="5" width="16" height="16" rx="2" /></svg>
    default:
      return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="8" /></svg>
  }
}

function QrCode({ matrix }: { matrix: boolean[][] }) {
  const size = matrix.length
  const cell = 4
  const padding = 4
  const view = size * cell + padding * 2
  const rects: ReactNode[] = []

  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < size; col += 1) {
      if (!matrix[row][col]) continue
      rects.push(
        <rect
          key={`${row}-${col}`}
          x={padding + col * cell}
          y={padding + row * cell}
          width={cell}
          height={cell}
          rx="0.6"
          fill="#0d1018"
        />,
      )
    }
  }

  return (
    <svg className="student-qr" viewBox={`0 0 ${view} ${view}`} aria-label="Student verification QR">
      <rect x="0" y="0" width={view} height={view} rx="10" fill="#fffdfc" />
      {rects}
    </svg>
  )
}

function Barcode({ value }: { value: string }) {
  const pattern = buildCode39Pattern(value)
  const narrow = 2
  const wide = 4
  const height = 44
  let cursor = 0
  const bars: ReactNode[] = []

  pattern.split('').forEach((token, index) => {
    const width = token === 'w' ? wide : narrow
    if (index % 2 === 0) {
      bars.push(<rect key={index} x={cursor} y="0" width={width} height={height} rx="1" fill="#f6f2f2" />)
    }
    cursor += width
  })

  return (
    <svg className="student-barcode" viewBox={`0 0 ${cursor} ${height}`} aria-label="Student barcode">
      <rect x="0" y="0" width={cursor} height={height} rx="8" fill="transparent" />
      {bars}
    </svg>
  )
}

const ALPHA = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:'
const QR_DATA_CODEWORDS = 19
const QR_EC_CODEWORDS = 7
const QR_SIZE = 21
const FORMAT_L_MASK_0 = 0b111011111000100

function buildQrMatrix(rawValue: string) {
  const value = String(rawValue || 'ICMS:ID').toUpperCase().replace(/[^0-9A-Z $%*+\-./:]/g, '')
  const dataCodewords = buildDataCodewords(value.slice(0, 25))
  const ecCodewords = buildErrorCodewords(dataCodewords, QR_EC_CODEWORDS)
  const codewords = [...dataCodewords, ...ecCodewords]
  const bits: number[] = []

  codewords.forEach(codeword => {
    for (let bit = 7; bit >= 0; bit -= 1) {
      bits.push((codeword >> bit) & 1)
    }
  })

  const modules = Array.from({ length: QR_SIZE }, () => Array(QR_SIZE).fill(false))
  const reserved = Array.from({ length: QR_SIZE }, () => Array(QR_SIZE).fill(false))

  const setFunction = (row: number, col: number, dark: boolean) => {
    modules[row][col] = dark
    reserved[row][col] = true
  }

  placeFinder(0, 0, setFunction)
  placeFinder(0, QR_SIZE - 7, setFunction)
  placeFinder(QR_SIZE - 7, 0, setFunction)

  for (let i = 8; i < QR_SIZE - 8; i += 1) {
    setFunction(6, i, i % 2 === 0)
    setFunction(i, 6, i % 2 === 0)
  }

  setFunction(8, QR_SIZE - 8, true)

  reserveFormatAreas(reserved)

  let bitIndex = 0
  let upwards = true
  for (let col = QR_SIZE - 1; col > 0; col -= 2) {
    if (col === 6) col -= 1
    for (let offset = 0; offset < QR_SIZE; offset += 1) {
      const row = upwards ? QR_SIZE - 1 - offset : offset
      for (let inner = 0; inner < 2; inner += 1) {
        const currentCol = col - inner
        if (reserved[row][currentCol]) continue
        const bit = bitIndex < bits.length ? bits[bitIndex] : 0
        bitIndex += 1
        const masked = ((row + currentCol) % 2 === 0) ? bit ^ 1 : bit
        modules[row][currentCol] = Boolean(masked)
      }
    }
    upwards = !upwards
  }

  applyFormatBits(modules, reserved)
  return modules
}

function placeFinder(top: number, left: number, setFunction: (row: number, col: number, dark: boolean) => void) {
  for (let row = -1; row <= 7; row += 1) {
    for (let col = -1; col <= 7; col += 1) {
      const rr = top + row
      const cc = left + col
      if (rr < 0 || rr >= QR_SIZE || cc < 0 || cc >= QR_SIZE) continue
      const edge = row === -1 || row === 7 || col === -1 || col === 7
      const border = row === 0 || row === 6 || col === 0 || col === 6
      const core = row >= 2 && row <= 4 && col >= 2 && col <= 4
      setFunction(rr, cc, !edge && (border || core))
    }
  }
}

function reserveFormatAreas(reserved: boolean[][]) {
  for (let i = 0; i <= 8; i += 1) {
    reserved[8][i] = true
    reserved[i][8] = true
  }
  for (let i = 0; i < 8; i += 1) {
    reserved[QR_SIZE - 1 - i][8] = true
    reserved[8][QR_SIZE - 1 - i] = true
  }
}

function applyFormatBits(modules: boolean[][], reserved: boolean[][]) {
  const bits = FORMAT_L_MASK_0

  for (let i = 0; i <= 5; i += 1) modules[8][i] = Boolean((bits >> i) & 1)
  modules[8][7] = Boolean((bits >> 6) & 1)
  modules[8][8] = Boolean((bits >> 7) & 1)
  modules[7][8] = Boolean((bits >> 8) & 1)
  for (let i = 9; i < 15; i += 1) modules[14 - i][8] = Boolean((bits >> i) & 1)

  for (let i = 0; i < 8; i += 1) modules[QR_SIZE - 1 - i][8] = Boolean((bits >> i) & 1)
  for (let i = 8; i < 15; i += 1) modules[8][QR_SIZE - 15 + i] = Boolean((bits >> i) & 1)

  for (let i = 0; i < QR_SIZE; i += 1) {
    reserved[8][i] = true
    reserved[i][8] = true
  }
}

function buildDataCodewords(value: string) {
  const bits: number[] = []
  pushBits(bits, 0b0010, 4)
  pushBits(bits, value.length, 9)

  for (let i = 0; i < value.length; i += 2) {
    const first = ALPHA.indexOf(value[i])
    if (i + 1 < value.length) {
      const second = ALPHA.indexOf(value[i + 1])
      pushBits(bits, first * 45 + second, 11)
    } else {
      pushBits(bits, first, 6)
    }
  }

  const capacity = QR_DATA_CODEWORDS * 8
  pushBits(bits, 0, Math.min(4, capacity - bits.length))
  while (bits.length % 8 !== 0) bits.push(0)

  const codewords: number[] = []
  for (let i = 0; i < bits.length; i += 8) {
    let codeword = 0
    for (let bit = 0; bit < 8; bit += 1) {
      codeword = (codeword << 1) | bits[i + bit]
    }
    codewords.push(codeword)
  }

  const pads = [0xec, 0x11]
  let padIndex = 0
  while (codewords.length < QR_DATA_CODEWORDS) {
    codewords.push(pads[padIndex % 2])
    padIndex += 1
  }
  return codewords
}

function pushBits(target: number[], value: number, width: number) {
  for (let bit = width - 1; bit >= 0; bit -= 1) {
    target.push((value >> bit) & 1)
  }
}

function buildErrorCodewords(dataCodewords: number[], degree: number) {
  const generator = rsGenerator(degree)
  const message = [...dataCodewords, ...new Array(degree).fill(0)]

  for (let i = 0; i < dataCodewords.length; i += 1) {
    const factor = message[i]
    if (factor === 0) continue
    for (let j = 0; j < generator.length; j += 1) {
      message[i + j] ^= gfMul(generator[j], factor)
    }
  }

  return message.slice(dataCodewords.length)
}

function rsGenerator(degree: number) {
  let poly = [1]
  for (let i = 0; i < degree; i += 1) {
    poly = polyMultiply(poly, [1, GF_EXP[i]])
  }
  return poly
}

function polyMultiply(left: number[], right: number[]) {
  const output = new Array(left.length + right.length - 1).fill(0)
  for (let i = 0; i < left.length; i += 1) {
    for (let j = 0; j < right.length; j += 1) {
      output[i + j] ^= gfMul(left[i], right[j])
    }
  }
  return output
}

const GF_EXP = (() => {
  const table = new Array(512).fill(0)
  let value = 1
  for (let i = 0; i < 255; i += 1) {
    table[i] = value
    value <<= 1
    if (value & 0x100) value ^= 0x11d
  }
  for (let i = 255; i < 512; i += 1) table[i] = table[i - 255]
  return table
})()

const GF_LOG = (() => {
  const table = new Array(256).fill(0)
  for (let i = 0; i < 255; i += 1) table[GF_EXP[i]] = i
  return table
})()

function gfMul(a: number, b: number) {
  if (a === 0 || b === 0) return 0
  return GF_EXP[GF_LOG[a] + GF_LOG[b]]
}

const CODE39: Record<string, string> = {
  '0': 'nnnwwnwnn',
  '1': 'wnnwnnnnw',
  '2': 'nnwwnnnnw',
  '3': 'wnwwnnnnn',
  '4': 'nnnwwnnnw',
  '5': 'wnnwwnnnn',
  '6': 'nnwwwnnnn',
  '7': 'nnnwnnwnw',
  '8': 'wnnwnnwnn',
  '9': 'nnwwnnwnn',
  A: 'wnnnnwnnw',
  B: 'nnwnnwnnw',
  C: 'wnwnnwnnn',
  D: 'nnnnwwnnw',
  E: 'wnnnwwnnn',
  F: 'nnwnwwnnn',
  G: 'nnnnnwwnw',
  H: 'wnnnnwwnn',
  I: 'nnwnnwwnn',
  J: 'nnnnwwwnn',
  K: 'wnnnnnnww',
  L: 'nnwnnnnww',
  M: 'wnwnnnnwn',
  N: 'nnnnwnnww',
  O: 'wnnnwnnwn',
  P: 'nnwnwnnwn',
  Q: 'nnnnnnwww',
  R: 'wnnnnnwwn',
  S: 'nnwnnnwwn',
  T: 'nnnnwnwwn',
  U: 'wwnnnnnnw',
  V: 'nwwnnnnnw',
  W: 'wwwnnnnnn',
  X: 'nwnnwnnnw',
  Y: 'wwnnwnnnn',
  Z: 'nwwnwnnnn',
  '-': 'nwnnnnwnw',
  '.': 'wwnnnnwnn',
  ' ': 'nwwnnnwnn',
  '$': 'nwnwnwnnn',
  '/': 'nwnwnnnwn',
  '+': 'nwnnnwnwn',
  '%': 'nnnwnwnwn',
  '*': 'nwnnwnwnn',
}

function buildCode39Pattern(rawValue: string) {
  const value = `*${String(rawValue || '').toUpperCase().replace(/[^0-9A-Z ./$+%-]/g, '')}*`
  return value
    .split('')
    .map(char => CODE39[char] || CODE39['-'])
    .join('n')
}
