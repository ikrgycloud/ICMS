import { useState } from 'react'
import Landing from './Landing'
import Login from './Login'
import App from './App'
import { getUser } from './api'
import Onboarding from './Onboarding'

export default function Root() {
  if (window.location.pathname === '/onboarding') return <Onboarding />
  const [view, setView] = useState<'landing' | 'login' | 'app'>(getUser() ? 'app' : 'landing')

  return (
    <>
      {view === 'landing' && <Landing onSignIn={() => setView('login')} />}
      {view === 'login' && <Login onDone={() => setView('app')} onBack={() => setView('landing')} />}
      {view === 'app' && <App onLogout={() => setView('landing')} />}
    </>
  )
}
