import { lazy, Suspense, useState } from 'react'
import Landing from './Landing'
import Login from './Login'
import { getUser } from './api'

// Keep the public entry path small; authenticated and applicant applications
// are loaded only after the visitor selects that path.
const App = lazy(() => import('./App'))
const ApplicantPortal = lazy(() => import('./admissions/ApplicantPortal'))

export default function Root() {
  const startsInApplicantPortal = new URLSearchParams(window.location.search).get('portal') === 'applicant'
  const [view, setView] = useState<'landing' | 'login' | 'app' | 'applicant'>(getUser() ? 'app' : startsInApplicantPortal ? 'applicant' : 'landing')
  const openWorkspace = () => {
    // A previous deep-link must not override the default workspace after a
    // fresh authentication.  Every role therefore starts at its overview.
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)
    setView('app')
  }
  const signOut = () => {
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)
    setView('landing')
  }

  return (
    <>
      {view === 'landing' && <Landing onSignIn={() => setView('login')} onApply={() => setView('applicant')} />}
      {view === 'login' && <Login onDone={openWorkspace} onBack={() => setView('landing')} />}
      {view === 'applicant' && <Suspense fallback={<div className="center-load"><div className="spinner" /></div>}><ApplicantPortal onBack={() => setView('landing')} /></Suspense>}
      {view === 'app' && <Suspense fallback={<div className="center-load"><div className="spinner" /></div>}><App onLogout={signOut} /></Suspense>}
    </>
  )
}
