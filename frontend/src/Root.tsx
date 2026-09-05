import { useState } from 'react'
import Landing from './Landing'
import Login from './Login'
import App from './App'
import { getUser } from './api'
import ApplicantPortal from './admissions/ApplicantPortal'

export default function Root() {
  const startsInApplicantPortal = new URLSearchParams(window.location.search).get('portal') === 'applicant'
  const [view, setView] = useState<'landing' | 'login' | 'app' | 'applicant'>(getUser() ? 'app' : startsInApplicantPortal ? 'applicant' : 'landing')

  return (
    <>
      {view === 'landing' && <Landing onSignIn={() => setView('login')} onApply={() => setView('applicant')} />}
      {view === 'login' && <Login onDone={() => setView('app')} onBack={() => setView('landing')} />}
      {view === 'applicant' && <ApplicantPortal onBack={() => setView('landing')} />}
      {view === 'app' && <App onLogout={() => setView('landing')} />}
    </>
  )
}
