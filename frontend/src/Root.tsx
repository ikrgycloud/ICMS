import { useState } from 'react'
import Landing from './Landing'
import Login from './Login'
import App from './App'
import { getUser } from './api'

export default function Root() {
  const [view, setView] = useState<'landing' | 'login' | 'app'>(getUser() ? 'app' : 'landing')

  return (
    <>
      {view === 'landing' && <Landing onSignIn={() => setView('login')} />}
      {view === 'login' && <Login onDone={() => setView('app')} onBack={() => setView('landing')} />}
      {view === 'app' && <App onLogout={() => setView('landing')} />}
    </>
  )
}
