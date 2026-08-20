import './landing.css'

const AUDIENCES = [
  {
    icon: '🎓', title: 'For Students',
    body: 'Your academic home — enrolled courses, live attendance, published results, fee statements and receipts, library loans, hostel and transport, all in one personalized dashboard.',
    tags: ['My courses', 'Attendance', 'Results', 'Fees'],
  },
  {
    icon: '📚', title: 'For Faculty & Staff',
    body: 'Teach and administer with clarity. See only the sections you teach, mark attendance, enter marks, manage advisees, raise requests — with approvals routed to the right authority automatically.',
    tags: ['My sections', 'Gradebook', 'Approvals', 'Leave'],
  },
  {
    icon: '🏛', title: 'For Leadership',
    body: 'From HODs to the Governing Body — institution-wide analytics, governance dashboards, budget and audit oversight, each scoped precisely to the authority of the office.',
    tags: ['Analytics', 'Governance', 'Audit', 'Budgets'],
  },
]

const LEVELS = [
  { tag: 'LEVEL 1', name: 'Governance', count: 'Chairman · Trustees', color: '#6b4fb0' },
  { tag: 'LEVEL 2', name: 'Executive', count: 'Vice Chairman', color: '#3d5a99' },
  { tag: 'LEVEL 3', name: 'Campus Leadership', count: '3 offices', color: '#0d9488' },
  { tag: 'LEVEL 4', name: 'Academic Leadership', count: 'Principal · Deans', color: '#b98a3e' },
  { tag: 'LEVEL 5', name: 'Faculty', count: 'Professors · Lecturers', color: '#c07a2e' },
  { tag: 'LEVEL 6', name: 'Academic Admin', count: 'Exams · Admissions', color: '#2f9e6a' },
  { tag: 'LEVEL 7', name: 'Operations', count: '14 support offices', color: '#3d6fb3' },
  { tag: 'LEVEL 8', name: 'Students & External', count: 'Students · Parents · Alumni', color: '#8a1f2b' },
]

const FEATURES = [
  { n: '01', h: 'Every role sees its own world', p: 'A student sees their courses and fees; a lecturer sees only the sections they teach; a parent sees one ward. Access is computed per request, never a filtered copy of one admin screen.' },
  { n: '02', h: 'Segregation of duties, enforced', p: 'The person who requests can never approve their own request; entering marks is never the same as publishing results. The engine guarantees it structurally.' },
  { n: '03', h: 'Approvals that route themselves', p: 'Approval limits live in configuration. Above the threshold, a request escalates automatically to the office with the authority to decide — no hardcoded amounts.' },
  { n: '04', h: 'A tamper-evident record', p: 'Every decision — allow, deny, recommend or escalate — is written to an append-only, hash-chained audit ledger that can be verified end to end.' },
]

const AUTH_FACTORS = ['Role', 'Permission', 'Org-Scope', 'Approval-Limit', 'Delegation', 'Workflow', 'Time-Validity']

const PIPELINE = [
  'Authenticate — OIDC / MFA',
  'Resolve tenant & organizational scope',
  'Check permission · action × resource',
  'Verify approval limit & delegation',
  'Enforce segregation of duties',
  'Decide & write to hash-chained audit',
]

export default function Landing({ onSignIn }: { onSignIn: () => void }) {
  return (
    <div className="lp">
      {/* top utility bar */}
      <div className="lp-top">
        <div className="wrap">
          <div className="tl"><span>◆ ICMS University Group</span></div>
          <div>
            <a href="#audiences">Portals</a>
            <a href="#offices">Offices</a>
            <a href="#platform">Platform</a>
            <a href="#" onClick={e => { e.preventDefault(); onSignIn() }}>Sign in</a>
          </div>
        </div>
      </div>

      {/* nav */}
      <nav className="lp-nav">
        <div className="wrap">
          <div className="lp-brand">
            <div className="lp-seal">IC</div>
            <div>
              <div className="lp-brand-name">ICMS</div>
              <div className="lp-brand-sub">Management System</div>
            </div>
          </div>
          <div className="lp-links">
            <a href="#audiences">For You</a>
            <a href="#offices">40 Offices</a>
            <a href="#platform">The Platform</a>
            <button className="lp-signin" onClick={onSignIn}>Sign in</button>
          </div>
        </div>
      </nav>

      {/* hero */}
      <header className="lp-hero">
        <div className="wrap">
          <div>
            <span className="lp-eyebrow">Integrated University Management</span>
            <h1>The whole university,<br />in <em>one</em> place.</h1>
            <p className="lede">
              One platform for every office — from the Governing Body to the student
              portal. Students, faculty, and leadership each sign in to a workspace
              built for exactly what they do, governed by a single authority engine
              that always knows who may do what.
            </p>
            <div className="lp-hero-cta">
              <button className="lp-btn-gold" onClick={onSignIn}>Sign in to your portal →</button>
              <a className="lp-btn-ghost" href="#audiences">Explore the portals</a>
            </div>
          </div>

          <div className="lp-portal-card">
            <h3>Choose your portal</h3>
            <div className="pc-sub">Forty offices across eight levels — sign in to yours.</div>
            <div className="lp-portal-list">
              <button className="lp-portal" onClick={onSignIn}>
                <span className="pi">🎓</span>
                <div><div className="pt">Student</div><div className="ps">Courses · attendance · results · fees</div></div>
                <span className="pa">→</span>
              </button>
              <button className="lp-portal" onClick={onSignIn}>
                <span className="pi">📚</span>
                <div><div className="pt">Faculty &amp; Staff</div><div className="ps">Teaching · approvals · administration</div></div>
                <span className="pa">→</span>
              </button>
              <button className="lp-portal" onClick={onSignIn}>
                <span className="pi">👪</span>
                <div><div className="pt">Parent / Guardian</div><div className="ps">Your ward's progress &amp; fees</div></div>
                <span className="pa">→</span>
              </button>
              <button className="lp-portal" onClick={onSignIn}>
                <span className="pi">🏛</span>
                <div><div className="pt">Administration</div><div className="ps">Leadership, finance &amp; governance</div></div>
                <span className="pa">→</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* stat strip */}
      <section className="lp-stats">
        <div className="wrap">
          <div className="lp-stat"><div className="sv">40</div><div className="sl">Offices</div></div>
          <div className="lp-stat"><div className="sv">268</div><div className="sl">Internal roles</div></div>
          <div className="lp-stat"><div className="sv">8</div><div className="sl">Authority levels</div></div>
          <div className="lp-stat"><div className="sv">12</div><div className="sl">Integrations</div></div>
        </div>
      </section>

      {/* audiences */}
      <section className="lp-sec" id="audiences">
        <div className="wrap">
          <div className="lp-sec-head">
            <div className="lp-kicker">Built for everyone on campus</div>
            <h2>A different experience for every role</h2>
            <p>No two logins are alike. Each person signs in to a workspace scoped to their
              own data and their own responsibilities — not one shared screen with buttons hidden.</p>
          </div>
          <div className="lp-aud">
            {AUDIENCES.map((a, i) => (
              <div className="lp-aud-card" key={i}>
                <div className="lp-aud-top">{a.icon}</div>
                <div className="lp-aud-body">
                  <h3>{a.title}</h3>
                  <p>{a.body}</p>
                  <div className="lp-aud-tags">{a.tags.map(t => <span key={t}>{t}</span>)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* offices / levels */}
      <section className="lp-sec alt" id="offices">
        <div className="wrap">
          <div className="lp-sec-head">
            <div className="lp-kicker">One organization, eight levels</div>
            <h2>Forty offices, mapped to real authority</h2>
            <p>The institution's structure is modeled faithfully — every office reports upward,
              carries its own scope, and inherits the shared authority engine.</p>
          </div>
          <div className="lp-levels">
            {LEVELS.map((l, i) => (
              <div className="lp-level" key={i} style={{ ['--lc' as any]: l.color }}>
                <div className="lt">{l.tag}</div>
                <div className="ln">{l.name}</div>
                <div className="lc">{l.count}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* platform / authority engine */}
      <section className="lp-sec" id="platform">
        <div className="wrap">
          <div className="lp-split">
            <div>
              <div className="lp-kicker">The authority engine</div>
              <h2 style={{ fontFamily: 'var(--ff-d)', fontSize: 38, fontWeight: 500, letterSpacing: '-.015em', lineHeight: 1.12, marginBottom: 10 }}>
                Correct by construction, <em>provable</em> after the fact.
              </h2>
              <p style={{ fontSize: 16, color: 'var(--txt-soft)', marginBottom: 20, lineHeight: 1.65 }}>
                Every action in the system passes through one engine that computes effective
                authority from independent, configurable factors — then records the decision permanently.
              </p>
              <div className="lp-feat-list">
                {FEATURES.map(f => (
                  <div className="lp-feat" key={f.n}>
                    <div className="fn">{f.n}</div>
                    <div>
                      <h4>{f.h}</h4>
                      <p>{f.p}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="lp-visual">
              <div className="vh">Authority composition</div>
              <div className="lp-authchip">
                {AUTH_FACTORS.map((f, i) => (
                  <span key={f}>
                    {f}{i < AUTH_FACTORS.length - 1 ? '' : ''}
                  </span>
                ))}
              </div>
              <div className="lp-eq">= <em>Effective authority</em>, per request</div>
              <div className="lp-flow">
                {PIPELINE.map((p, i) => (
                  <div className="lp-flow-row" key={i}><span className="fd" />{p}</div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="lp-cta">
        <div className="wrap">
          <h2>Sign in to your office.</h2>
          <p>Forty demo accounts are ready — students, faculty, deans, finance, IT and more.
            Each opens a completely different, fully working workspace.</p>
          <button className="lp-btn-gold" onClick={onSignIn}>Continue to sign in →</button>
        </div>
      </section>

      {/* footer */}
      <footer className="lp-foot">
        <div className="wrap">
          <div className="lp-foot-grid">
            <div>
              <div className="fbrand">
                <div className="lp-seal">IC</div>
                <div className="fbrand-name">ICMS</div>
              </div>
              <p>An integrated college / university management system — one multi-tenant platform
                for an entire institution group, on a single configurable authority engine.</p>
            </div>
            <div>
              <h5>Portals</h5>
              <a href="#" onClick={e => { e.preventDefault(); onSignIn() }}>Students</a>
              <a href="#" onClick={e => { e.preventDefault(); onSignIn() }}>Faculty &amp; Staff</a>
              <a href="#" onClick={e => { e.preventDefault(); onSignIn() }}>Parents</a>
              <a href="#" onClick={e => { e.preventDefault(); onSignIn() }}>Administration</a>
            </div>
            <div>
              <h5>Platform</h5>
              <a href="#platform">Authority engine</a>
              <a href="#offices">40 offices</a>
              <a href="#audiences">Role portals</a>
              <a href="#platform">Integrations</a>
            </div>
            <div>
              <h5>Institution</h5>
              <a href="#">About</a>
              <a href="#">Academics</a>
              <a href="#">Admissions</a>
              <a href="#">Contact</a>
            </div>
          </div>
          <div className="lp-foot-bottom">
            <span>© {new Date().getFullYear()} ICMS University Group. All rights reserved.</span>
            <span>Privacy · Terms · Accessibility</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
