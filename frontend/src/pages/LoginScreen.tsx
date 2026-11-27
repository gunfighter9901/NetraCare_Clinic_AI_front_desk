import { useState } from 'react'
import { api, ApiError } from '../api/client'
import { useSession } from '../context/SessionContext'
import { useAsync } from '../hooks/useAsync'
import { InlineAlert } from '../components/ui'

type Tab = 'patient' | 'doctor' | 'staff'

export default function LoginScreen() {
  const { login } = useSession()
  const [tab, setTab] = useState<Tab>('patient')
  const [mobile, setMobile] = useState('')
  const [name, setName] = useState('')
  const [doctorId, setDoctorId] = useState('')
  const [staffName, setStaffName] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const doctorsQuery = useAsync((signal) => api.doctorOptions(signal), [tab === 'doctor'])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setPending(true)
    try {
      if (tab === 'patient') {
        const response = await api.loginPatient(mobile.trim(), name.trim())
        login(response.token, response.role, response.patient_id, response.doctor_id, response.display_name)
      } else if (tab === 'doctor') {
        if (!doctorId) throw new ApiError('Please select a doctor.', 400)
        const response = await api.loginDoctor(doctorId)
        login(response.token, response.role, response.patient_id, response.doctor_id, response.display_name)
      } else {
        if (!staffName.trim()) throw new ApiError('Please enter your display name.', 400)
        const response = await api.loginStaff(staffName.trim())
        login(response.token, response.role, response.patient_id, response.doctor_id, response.display_name)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed. Please retry.')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="container-narrow">
      <div className="card">
        <h1 style={{ fontSize: '1.8rem', marginBottom: 4 }}>NetraCare</h1>
        <p className="meta" style={{ marginBottom: 20 }}>
          Eye clinic front desk. Synthetic demo data — no real patient information.
        </p>
        <div role="tablist" aria-label="Login role" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 20 }}>
          {(['patient', 'doctor', 'staff'] as Tab[]).map((role) => (
            <button
              key={role}
              type="button"
              role="tab"
              aria-selected={tab === role}
              className={`btn ${tab === role ? 'btn-primary' : 'btn-secondary'} btn-sm`}
              onClick={() => {
                setTab(role)
                setError(null)
              }}
            >
              {role === 'patient' ? 'Patient' : role === 'doctor' ? 'Doctor' : 'Staff'}
            </button>
          ))}
        </div>
        <form onSubmit={submit}>
          {tab === 'patient' && (
            <>
              <div className="form-group">
                <label htmlFor="login-mobile">Mobile number</label>
                <input
                  id="login-mobile"
                  inputMode="tel"
                  autoComplete="tel"
                  required
                  value={mobile}
                  onChange={(e) => setMobile(e.target.value)}
                  placeholder="e.g. 9000000001"
                />
              </div>
              <div className="form-group">
                <label htmlFor="login-name">Full name</label>
                <input
                  id="login-name"
                  autoComplete="name"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Name registered with the clinic"
                />
              </div>
            </>
          )}
          {tab === 'doctor' && (
            <div className="form-group">
              <label htmlFor="login-doctor">Select doctor</label>
              {doctorsQuery.state.status === 'loading' && <p className="meta">Loading doctors…</p>}
              {doctorsQuery.state.status === 'error' && (
                <InlineAlert tone="error">{doctorsQuery.state.message}</InlineAlert>
              )}
              {(doctorsQuery.state.status === 'success' || doctorsQuery.state.status === 'empty') && (
                <select
                  id="login-doctor"
                  required
                  value={doctorId}
                  onChange={(e) => setDoctorId(e.target.value)}
                >
                  <option value="">Choose…</option>
                  {(doctorsQuery.state.status === 'success' ? doctorsQuery.state.data : []).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.id})
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}
          {tab === 'staff' && (
            <div className="form-group">
              <label htmlFor="login-staff">Display name</label>
              <input
                id="login-staff"
                autoComplete="name"
                required
                value={staffName}
                onChange={(e) => setStaffName(e.target.value)}
                placeholder="e.g. Front Desk"
              />
            </div>
          )}
          {error && (
            <div style={{ marginBottom: 16 }}>
              <InlineAlert tone="error">{error}</InlineAlert>
            </div>
          )}
          <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={pending}>
            {pending ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
