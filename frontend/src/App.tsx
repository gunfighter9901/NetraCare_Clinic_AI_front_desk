import LoginScreen from './components/LoginScreen'
import { AuthProvider, useAuth } from './auth'
import DoctorWorkspace from './pages/DoctorWorkspace'
import PatientWorkspace from './pages/PatientWorkspace'
import StaffWorkspace from './pages/StaffWorkspace'

function Workspace() {
  const { session } = useAuth()
  if (!session) return null
  if (session.role === 'patient') return <PatientWorkspace />
  if (session.role === 'staff') return <StaffWorkspace />
  return <DoctorWorkspace />
}

function Application() {
  const { session, ready, logout } = useAuth()

  if (!ready) {
    return (
      <main className="loading-page">
        <p>Restoring your NetraCare session…</p>
      </main>
    )
  }

  if (!session) return <LoginScreen />

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <strong>NetraCare</strong>
          <span className="role-badge">{session.displayName}</span>
        </div>
        <button type="button" onClick={() => void logout()}>
          Log out
        </button>
      </header>
      <Workspace />
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Application />
    </AuthProvider>
  )
}
