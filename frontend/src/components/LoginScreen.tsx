import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import type { DoctorOption, Role } from '../types'

const ROLE_LABELS: Record<Role, string> = {
  patient: 'Patient',
  staff: 'Staff',
  doctor: 'Doctor',
}

export default function LoginScreen() {
  const { loginPatient, loginDoctor, loginStaff } = useAuth()
  const [role, setRole] = useState<Role>('patient')
  const [doctors, setDoctors] = useState<DoctorOption[]>([])
  const [mobile, setMobile] = useState('')
  const [patientName, setPatientName] = useState('')
  const [doctorId, setDoctorId] = useState('')
  const [staffName, setStaffName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let ignore = false
    api
      .doctorOptions()
      .then((options) => {
        if (!ignore) {
          setDoctors(options)
          setDoctorId((current) => current || options[0]?.id || '')
        }
      })
      .catch(() => {
        if (!ignore) setError('Could not load the doctor list. Is the backend running?')
      })
    return () => {
      ignore = true
    }
  }, [])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (role === 'patient') await loginPatient(mobile, patientName)
      else if (role === 'doctor') await loginDoctor(doctorId)
      else await loginStaff(staffName)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Login failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-page">
      <h1>NetraCare</h1>
      <p className="subtitle">Synthetic eye-clinic scheduling · classroom demo</p>

      <div className="role-tabs" role="tablist" aria-label="Login role">
        {(['patient', 'staff', 'doctor'] as Role[]).map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={role === item}
            className={role === item ? 'active' : ''}
            onClick={() => {
              setRole(item)
              setError(null)
            }}
          >
            {ROLE_LABELS[item]}
          </button>
        ))}
      </div>

      <form className="card login-card" onSubmit={submit}>
        {role === 'patient' && (
          <>
            <label>
              Mobile number
              <input
                value={mobile}
                onChange={(event) => setMobile(event.target.value)}
                inputMode="numeric"
                placeholder="9000000001"
                required
              />
            </label>
            <label>
              Name
              <input
                value={patientName}
                onChange={(event) => setPatientName(event.target.value)}
                placeholder="Asha Verma"
                required
              />
            </label>
          </>
        )}

        {role === 'doctor' && (
          <label>
            Doctor
            <select value={doctorId} onChange={(event) => setDoctorId(event.target.value)} required>
              {doctors.map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.name}
                </option>
              ))}
            </select>
          </label>
        )}

        {role === 'staff' && (
          <label>
            Staff name
            <input
              value={staffName}
              onChange={(event) => setStaffName(event.target.value)}
              placeholder="Front Desk"
              required
            />
          </label>
        )}

        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" type="submit" disabled={busy}>
          {busy ? 'Signing in…' : `Sign in as ${ROLE_LABELS[role]}`}
        </button>
      </form>
    </main>
  )
}
