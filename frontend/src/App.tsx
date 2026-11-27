import { useState } from 'react'
import { LogOut } from 'lucide-react'
import { SessionProvider, useSession } from './context/SessionContext'
import LoginScreen from './pages/LoginScreen'
import PatientWorkspace from './pages/PatientWorkspace'
import StaffWorkspace from './pages/StaffWorkspace'
import DoctorWorkspace from './pages/DoctorWorkspace'

function Workspace() {
  const { session } = useSession()
  if (!session) return null
  if (session.role === 'patient') return <PatientWorkspace />
  if (session.role === 'staff') return <StaffWorkspace />
  return <DoctorWorkspace />
}

function RoleTabs({
  active,
  onSelect,
}: {
  active: 'patient' | 'staff' | 'doctor'
  onSelect: (role: 'patient' | 'staff' | 'doctor') => void
}) {
  const { session } = useSession()
  if (!session) return null
  // Single-workspace product: tabs are shown for discoverability but the
  // authenticated role owns its workspace; switching roles needs re-login.
  return (
    <nav aria-label="Workspace" style={{ display: 'flex', gap: 8 }} className="hide-on-mobile">
      {(['patient', 'staff', 'doctor'] as const).map((role) => (
        <button
          key={role}
          type="button"
          className={`btn btn-sm ${active === role ? 'btn-primary' : 'btn-secondary'}`}
          aria-current={active === role ? 'page' : undefined}
          disabled={active !== role}
          title={active === role ? 'Current workspace' : 'Sign in as this role to access'}
          onClick={() => onSelect(role)}
        >
          {role === 'patient' ? 'Patient' : role === 'staff' ? 'Staff' : 'Doctor'}
        </button>
      ))}
    </nav>
  )
}

function Shell() {
  const { session, ready, logout } = useSession()
  const [loggingOut, setLoggingOut] = useState(false)
  const active = session?.role ?? 'patient'

  if (!ready) {
    return (
      <main>
        <div className="container-narrow">
          <p role="status">Restoring your NetraCare session…</p>
        </div>
      </main>
    )
  }

  if (!session) {
    return (
      <main>
        <LoginScreen />
      </main>
    )
  }

  return (
    <div className="app-shell">
      <a href="#workspace" style={{ position: 'absolute', left: -9999 }}>
        Skip to workspace
      </a>
      <div className="app-nav-wrap">
        <header className="app-nav">
          <span className="brand">
            <span className="brand-mark" aria-hidden="true">
              N
            </span>
            NetraCare
          </span>
          <RoleTabs active={active} onSelect={() => undefined} />
          <span className="nav-actions">
            <span className="badge badge-neutral hide-on-mobile">{session.displayName}</span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={loggingOut}
              onClick={() => {
                setLoggingOut(true)
                void logout().finally(() => setLoggingOut(false))
              }}
            >
              {loggingOut ? 'Signing out…' : (<><LogOut size={15} aria-hidden="true" /> Log out</>)}
            </button>
          </span>
        </header>
      </div>
      <main id="workspace">
        <Workspace />
      </main>
      <footer>NetraCare Eye Clinic · Synthetic demo data · No real patient information</footer>
    </div>
  )
}

export default function App() {
  return (
    <SessionProvider>
      <Shell />
    </SessionProvider>
  )
}
