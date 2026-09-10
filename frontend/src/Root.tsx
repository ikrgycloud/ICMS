import { useState } from 'react'
import Landing from './Landing'
import Login from './Login'
import App from './App'
import { getUser } from './api'
import ApplicantPortal from './admissions/ApplicantPortal'

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
      {view === 'applicant' && <ApplicantPortal onBack={() => setView('landing')} />}
      {view === 'app' && <App onLogout={signOut} />}
    </>
  )
}
