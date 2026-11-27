import { useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import type { Appointment, Doctor, SlotAvailability, VisitType } from '../types'
import PatientChat from '../components/PatientChat'

function defaultAppointmentDate(): string {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  if (date.getDay() === 0) date.setDate(date.getDate() + 1)
  return date.toISOString().slice(0, 10)
}

function displayTime(value: string): string {
  return value.slice(0, 5)
}

export default function PatientWorkspace() {
  const { session } = useAuth()
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [doctorId, setDoctorId] = useState('')
  const [speciality, setSpeciality] = useState('')
  const [visitType, setVisitType] = useState<VisitType>('new')
  const [appointmentDate, setAppointmentDate] = useState(defaultAppointmentDate)
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
  const [fact, setFact] = useState<string | null>(null)
  const [factCaveat, setFactCaveat] = useState<string | null>(null)
  const [factLoading, setFactLoading] = useState(false)

  const token = session?.token ?? ''
  const selectedDoctor = useMemo(
    () => doctors.find((doctor) => doctor.id === doctorId),
    [doctors, doctorId],
  )

  useEffect(() => {
    let ignore = false
    setLoading(true)
    Promise.all([api.doctors(token), api.patientAppointments(token)])
      .then(([doctorList, appointmentList]) => {
        if (ignore) return
        setDoctors(doctorList)
        setAppointments(appointmentList)
        setDoctorId((current) => current || doctorList[0]?.id || '')
        setSpeciality((current) => current || doctorList[0]?.specialities[0] || '')
      })
      .catch((caught) => {
        if (!ignore) setError(caught instanceof ApiError ? caught.message : 'Could not load your clinic data.')
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })
    api
      .factOfTheDay(token)
      .then((factResponse) => {
        if (ignore) return
        setFact(factResponse.fact)
        setFactCaveat(factResponse.caveat)
      })
      .catch(() => {
        // Fact is non-critical; a later Refresh can retry. Never block doctors/appointments.
      })
    return () => {
      ignore = true
    }
  }, [token])

  useEffect(() => {
    setSpeciality(selectedDoctor?.specialities[0] ?? '')
  }, [selectedDoctor])

  useEffect(() => {
    if (!doctorId || !appointmentDate) return
    let ignore = false
    setSearching(true)
    setStartTime('')
    api
      .slots(token, doctorId, appointmentDate, visitType)
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
  }, [token, doctorId, appointmentDate, visitType])

  async function refreshAppointments() {
    const appointmentList = await api.patientAppointments(token)
    setAppointments(appointmentList)
  }

  async function refreshSlots() {
    if (!doctorId || !appointmentDate) return
    const result = await api.slots(token, doctorId, appointmentDate, visitType)
    setAvailability(result)
    setStartTime(result.slots[0] ?? '')
  }

  async function refreshFact() {
    setFactLoading(true)
    try {
      const response = await api.factOfTheDay(token, fact ?? undefined)
      setFact(response.fact)
      setFactCaveat(response.caveat)
    } catch {
      // Keep existing fact on failure; backend fallback already covers missing keys
    } finally {
      setFactLoading(false)
    }
  }

  async function book(event: React.FormEvent) {
    event.preventDefault()
    const requestedTime = directTime || startTime
    setError(null)
    setEmergency(null)
    setSuccess(null)
    setBusy(true)
    try {
      const appointment = await api.bookAsPatient(token, {
        doctor_id: doctorId,
        speciality,
        visit_type: visitType,
        date: appointmentDate,
        start_time: requestedTime,
        reason: reason.trim(),
      })
      setDirectTime('')
      if (appointment.emergency) setEmergency(appointment.emergency)
      setSuccess(`Booked appointment ${appointment.id}.`)
      await Promise.all([refreshAppointments(), refreshSlots()])
    } catch (caught) {
      if (caught instanceof ApiError && caught.emergency) setEmergency(caught.emergency)
      setError(caught instanceof ApiError ? caught.message : 'Booking failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  async function cancel(appointment: Appointment) {
    setError(null)
    setEmergency(null)
    setSuccess(null)
    setBusy(true)
    try {
      const result = await api.cancelAppointment(token, appointment.id)
      if ('result' in result && result.result === 'to_staff') {
        setSuccess(`Cancellation sent to Staff for approval (${result.approval_request.id}). The appointment remains booked.`)
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

  async function handleChatChanged() {
    await Promise.all([refreshAppointments(), refreshSlots()])
  }

  if (loading) return <p>Loading your appointments…</p>

  return (
    <section className="workspace">
      <h2>Your appointments</h2>
      <div className="card fact-card">
        <h3>Fact of the Day</h3>
        {fact ? <p>{fact}</p> : <p>Loading eye-health fact…</p>}
        {factCaveat && <p className="caveat">{factCaveat}</p>}
        <button type="button" onClick={() => void refreshFact()} disabled={factLoading}>
          {factLoading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>
      {emergency && <p className="error" role="alert">{emergency}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {success && <p className="success" role="status">{success}</p>}

      <form id="book" className="card booking-form" onSubmit={book}>
        <h3>Book an appointment</h3>
        <div className="form-grid">
          <label>
            Doctor
            <select
              value={doctorId}
              onChange={(event) => setDoctorId(event.target.value)}
              required
            >
              {doctors.map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.name}
                </option>
              ))}
            </select>
          </label>

          <label>
            Speciality
            <select
              value={speciality}
              onChange={(event) => setSpeciality(event.target.value)}
              required
            >
              {(selectedDoctor?.specialities ?? []).map((item) => (
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
              value={appointmentDate}
              onChange={(event) => setAppointmentDate(event.target.value)}
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
            What is the reason for your visit? (required, max 300 characters)
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

      <PatientChat onChanged={handleChatChanged} />

      <div className="table-card">
        <h3>Appointment history</h3>
        {appointments.length === 0 ? (
          <p>No appointments yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Time</th>
                <th>Doctor</th>
                <th>Speciality</th>
                <th>Visit</th>
                <th>Status</th>
                <th>Staff request</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {appointments.map((appointment) => (
                <tr key={appointment.id} data-appointment-id={appointment.id}>
                  <td>{appointment.date}</td>
                  <td>
                    {displayTime(appointment.start_time)}–{displayTime(appointment.end_time)}
                  </td>
                  <td>{appointment.doctor_name}</td>
                  <td>{appointment.speciality}</td>
                  <td>{appointment.visit_type === 'new' ? 'New' : 'Follow-up'}</td>
                  <td>{appointment.status}</td>
                  <td>
                    {appointment.approval_status
                      ? `${appointment.approval_action ?? ''} ${appointment.approval_status}`.trim()
                      : '—'}
                  </td>
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
