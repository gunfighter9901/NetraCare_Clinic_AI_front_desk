import { useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import type { Appointment, Doctor, PatientSummary, SlotAvailability, StaffApprovalRequest, UrgentCase, VisitType } from '../types'
import StaffSearchDebug from '../components/StaffSearchDebug'

function defaultAppointmentDate(): string {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  if (date.getDay() === 0) date.setDate(date.getDate() + 1)
  return date.toISOString().slice(0, 10)
}

function displayTime(value: string): string {
  return value.slice(0, 5)
}

export default function StaffWorkspace() {
  const { session } = useAuth()
  const [patients, setPatients] = useState<PatientSummary[]>([])
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [urgents, setUrgents] = useState<UrgentCase[]>([])
  const [approvals, setApprovals] = useState<StaffApprovalRequest[]>([])
  const [filterDate, setFilterDate] = useState(defaultAppointmentDate)
  const [filterDoctorId, setFilterDoctorId] = useState('')
  const [patientMode, setPatientMode] = useState<'existing' | 'walk_in'>('existing')
  const [patientId, setPatientId] = useState('')
  const [walkInName, setWalkInName] = useState('')
  const [walkInMobile, setWalkInMobile] = useState('')
  const [doctorId, setDoctorId] = useState('')
  const [speciality, setSpeciality] = useState('')
  const [visitType, setVisitType] = useState<VisitType>('new')
  const [bookingDate, setBookingDate] = useState(defaultAppointmentDate)
  const [availability, setAvailability] = useState<SlotAvailability | null>(null)
  const [startTime, setStartTime] = useState('')
  const [directTime, setDirectTime] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [emergency, setEmergency] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [busy, setBusy] = useState(false)

  const token = session?.token ?? ''
  const allSpecialities = useMemo(
    () => [...new Set(doctors.flatMap((doctor) => doctor.specialities))].sort(),
    [doctors],
  )

  useEffect(() => {
    let ignore = false
    setLoading(true)
    Promise.all([api.staffPatients(token), api.doctors(token), api.urgentCases(token), api.staffApprovals(token)])
      .then(([patientList, doctorList, urgentList, approvalList]) => {
        if (ignore) return
        setPatients(patientList)
        setDoctors(doctorList)
        setUrgents(urgentList)
        setApprovals(approvalList)
        setPatientId((current) => current || patientList[0]?.id || '')
        setDoctorId((current) => current || doctorList[0]?.id || '')
        setFilterDoctorId((current) => current || doctorList[0]?.id || '')
        setSpeciality((current) => current || doctorList[0]?.specialities[0] || '')
      })
      .catch((caught) => {
        if (!ignore) setError(caught instanceof ApiError ? caught.message : 'Could not load Staff data.')
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })
    return () => {
      ignore = true
    }
  }, [token])

  useEffect(() => {
    if (!filterDate || !filterDoctorId) return
    let ignore = false
    api
      .staffAppointments(token, filterDate, filterDoctorId)
      .then((appointmentList) => {
        if (!ignore) setAppointments(appointmentList)
      })
      .catch((caught) => {
        if (!ignore) setError(caught instanceof ApiError ? caught.message : 'Could not load the clinic schedule.')
      })
    return () => {
      ignore = true
    }
  }, [token, filterDate, filterDoctorId])

  useEffect(() => {
    if (!doctorId || !bookingDate) return
    let ignore = false
    setSearching(true)
    setStartTime('')
    api
      .slots(token, doctorId, bookingDate, visitType)
      .then((result) => {
        if (!ignore) {
          setAvailability(result)
          setStartTime(result.slots[0] ?? '')
        }
      })
      .catch((caught) => {
        if (!ignore) setError(caught instanceof ApiError ? caught.message : 'Could not load free slots.')
      })
      .finally(() => {
        if (!ignore) setSearching(false)
      })
    return () => {
      ignore = true
    }
  }, [token, doctorId, bookingDate, visitType])

  async function refreshAppointments() {
    const [appointmentList, urgentList, approvalList] = await Promise.all([
      api.staffAppointments(token, filterDate, filterDoctorId),
      api.urgentCases(token),
      api.staffApprovals(token),
    ])
    setAppointments(appointmentList)
    setUrgents(urgentList)
    setApprovals(approvalList)
  }

  async function refreshSlots() {
    if (!doctorId || !bookingDate) return
    const result = await api.slots(token, doctorId, bookingDate, visitType)
    setAvailability(result)
    setStartTime(result.slots[0] ?? '')
  }

  async function book(event: React.FormEvent) {
    event.preventDefault()
    const requestedTime = directTime || startTime
    setError(null)
    setEmergency(null)
    setSuccess(null)
    setBusy(true)
    try {
      const appointment = await api.bookAsStaff(token, {
        patient_id: patientMode === 'existing' ? patientId : undefined,
        walk_in_name: patientMode === 'walk_in' ? walkInName : undefined,
        walk_in_mobile: patientMode === 'walk_in' ? walkInMobile : undefined,
        doctor_id: doctorId,
        speciality,
        visit_type: visitType,
        date: bookingDate,
        start_time: requestedTime,
        reason: reason.trim(),
      })
      setDirectTime('')
      if (appointment.emergency) setEmergency(appointment.emergency)
      setSuccess(`Booked appointment ${appointment.id} for ${appointment.patient_name}.`)
      await Promise.all([refreshAppointments(), refreshSlots()])
    } catch (caught) {
      if (caught instanceof ApiError && caught.emergency) setEmergency(caught.emergency)
      setError(caught instanceof ApiError ? caught.message : 'Booking failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  async function markSeen(urgentId: string) {
    setBusy(true)
    try {
      await api.markUrgentSeen(token, urgentId)
      await refreshAppointments()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not mark urgent case seen.')
    } finally {
      setBusy(false)
    }
  }

  async function cancel(appointment: Appointment) {
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      const result = await api.cancelAppointment(token, appointment.id)
      if ('result' in result && result.result === 'to_staff') {
        setSuccess(`Queued for approval (${result.approval_request.id}).`)
      } else {
        setSuccess(`Cancelled appointment ${(result as Appointment).id}.`)
      }
      await Promise.all([refreshAppointments(), refreshSlots()])
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Cancellation failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  async function decideApproval(requestId: string, approve: boolean) {
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      const decided = approve
        ? await api.approveApproval(token, requestId)
        : await api.rejectApproval(token, requestId)
      setSuccess(`${decided.action} ${decided.id} ${decided.status}.`)
      await refreshAppointments()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Approval decision failed.')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p>Loading Staff tools…</p>

  return (
    <section className="workspace">
      <h2>Clinic appointments</h2>
      {emergency && <p className="error" role="alert">{emergency}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {success && <p className="success" role="status">{success}</p>}

      {urgents.length > 0 && (
        <div className="card urgent-card">
          <h3>Urgent cases ({urgents.length})</h3>
          {urgents.map((urgent) => (
            <div key={urgent.id} className="error">
              <p><strong>{urgent.patient_name ?? 'Walk-in'} · {urgent.patient_mobile ?? ''}</strong> <span className="role-badge">{urgent.origin === 'chat' ? 'chat' : 'booking'}</span> — {urgent.reason_text} [{urgent.category}]</p>
              <button type="button" onClick={() => void markSeen(urgent.id)} disabled={busy}>
                Mark seen
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="card approval-card">
        <h3>Staff approvals ({approvals.length})</h3>
        {approvals.length === 0 ? (
          <p>No pending late cancellations or reschedules.</p>
        ) : (
          approvals.map((item) => (
            <div key={item.id} data-approval-id={item.id}>
              <p>
                <strong>{item.patient_name ?? item.patient_id}</strong> — {item.action} {item.appointment_id}
                {item.target_doctor_id ? ` → ${item.target_doctor_name ?? item.target_doctor_id} ${item.target_date ?? ''} ${item.target_start_time ?? ''}` : ''}
                {' '}[{item.status}]
              </p>
              <button type="button" onClick={() => void decideApproval(item.id, true)} disabled={busy}>
                Approve
              </button>
              <button type="button" onClick={() => void decideApproval(item.id, false)} disabled={busy}>
                Reject
              </button>
            </div>
          ))
        )}
      </div>

      <div className="card filter-card">
        <div className="form-grid">
          <label>
            Date
            <input
              type="date"
              value={filterDate}
              onChange={(event) => setFilterDate(event.target.value)}
            />
          </label>
          <label>
            Doctor
            <select
              value={filterDoctorId}
              onChange={(event) => setFilterDoctorId(event.target.value)}
            >
              {doctors.map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <form className="card booking-form" onSubmit={book}>
        <h3>Book for a patient</h3>
        <div className="patient-mode">
          <label className="checkbox-label">
            <input
              type="radio"
              name="patient-mode"
              checked={patientMode === 'existing'}
              onChange={() => setPatientMode('existing')}
            />
            Existing patient
          </label>
          <label className="checkbox-label">
            <input
              type="radio"
              name="patient-mode"
              checked={patientMode === 'walk_in'}
              onChange={() => setPatientMode('walk_in')}
            />
            Walk-in
          </label>
        </div>

        {patientMode === 'existing' ? (
          <label>
            Patient
            <select value={patientId} onChange={(event) => setPatientId(event.target.value)} required>
              {patients.map((patient) => (
                <option key={patient.id} value={patient.id}>
                  {patient.name} · {patient.mobile}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <div className="form-grid">
            <label>
              Walk-in name
              <input
                value={walkInName}
                onChange={(event) => setWalkInName(event.target.value)}
                required
              />
            </label>
            <label>
              Walk-in mobile
              <input
                value={walkInMobile}
                onChange={(event) => setWalkInMobile(event.target.value)}
                required
              />
            </label>
          </div>
        )}

        <div className="form-grid">
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
          <label>
            Speciality
            <select value={speciality} onChange={(event) => setSpeciality(event.target.value)} required>
              {allSpecialities.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Visit type
            <select
              value={visitType}
              onChange={(event) => setVisitType(event.target.value as VisitType)}
              required
            >
              <option value="new">New consultation (20 min)</option>
              <option value="follow_up">Follow-up (10 min)</option>
            </select>
          </label>
          <label>
            Date
            <input
              type="date"
              value={bookingDate}
              onChange={(event) => setBookingDate(event.target.value)}
              required
            />
          </label>
          <label>
            Free time
            <select
              value={startTime}
              onChange={(event) => setStartTime(event.target.value)}
              required
              disabled={searching || availability?.slots.length === 0}
            >
              {(availability?.slots ?? []).map((slot) => (
                <option key={slot} value={slot}>
                  {displayTime(slot)}
                </option>
              ))}
            </select>
          </label>

          <label>
            Direct time (optional)
            <input
              type="time"
              step={600}
              value={directTime}
              onChange={(event) => setDirectTime(event.target.value)}
            />
          </label>

          <label>
            Reason for visit (required, max 300 characters)
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={300}
              required
            />
          </label>
        </div>

        <p className={availability?.slots.length ? 'success' : 'error'}>
          {searching ? 'Finding free slots…' : availability?.message}
        </p>
        <button className="primary" type="submit" disabled={busy || !(directTime || startTime)}>
          Book appointment
        </button>
      </form>

      <StaffSearchDebug />

      <div className="table-card">
        <h3>
          {filterDate} · {doctors.find((doctor) => doctor.id === filterDoctorId)?.name ?? ''}
        </h3>
        {appointments.length === 0 ? (
          <p>No appointments for this doctor and date.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Patient</th>
                <th>Reason</th>
                <th>Speciality</th>
                <th>Visit</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {appointments.map((appointment) => (
                <tr key={appointment.id} data-appointment-id={appointment.id}>
                  <td>
                    {displayTime(appointment.start_time)}–{displayTime(appointment.end_time)}
                  </td>
                  <td>{appointment.patient_name}</td>
                  <td>{appointment.reason ?? ''} {appointment.is_urgent ? <strong>Urgent</strong> : null}</td>
                  <td>{appointment.speciality}</td>
                  <td>{appointment.visit_type === 'new' ? 'New' : 'Follow-up'}</td>
                  <td>{appointment.status}</td>
                  <td>
                    {appointment.status === 'booked' && (
                      <button type="button" onClick={() => void cancel(appointment)} disabled={busy}>
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
