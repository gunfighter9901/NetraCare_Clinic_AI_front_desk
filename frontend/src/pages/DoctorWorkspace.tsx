import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import type { Appointment, DoctorSummary, PatientHistoryItem } from '../types'

function defaultScheduleDate(): string {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  if (date.getDay() === 0) date.setDate(date.getDate() + 1)
  return date.toISOString().slice(0, 10)
}

function displayTime(value: string): string {
  return value.slice(0, 5)
}

export default function DoctorWorkspace() {
  const { session } = useAuth()
  const [scheduleDate, setScheduleDate] = useState(defaultScheduleDate)
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [doctorNote, setDoctorNote] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [summary, setSummary] = useState<DoctorSummary | null>(null)
  const [history, setHistory] = useState<PatientHistoryItem[]>([])
  const [summaryLoading, setSummaryLoading] = useState(false)
  const token = session?.token ?? ''

  useEffect(() => {
    if (!scheduleDate) return
    let ignore = false
    setLoading(true)
    api
      .doctorAppointments(token, scheduleDate)
      .then((appointmentList) => {
        if (!ignore) setAppointments(appointmentList)
      })
      .catch((caught) => {
        if (!ignore) setError(caught instanceof ApiError ? caught.message : 'Could not load your schedule.')
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })
    return () => {
      ignore = true
    }
  }, [token, scheduleDate])

  async function refreshSchedule() {
    const appointmentList = await api.doctorAppointments(token, scheduleDate)
    setAppointments(appointmentList)
  }

  async function complete(appointment: Appointment) {
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      const completed = await api.completeAppointment(token, appointment.id, doctorNote.trim())
      setDoctorNote('')
      setSuccess(`Completed visit ${completed.id}.`)
      await refreshSchedule()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Completion failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  async function openPatient(appointment: Appointment) {
    setSelectedId(appointment.id)
    setSummary(null)
    setHistory([])
    setSummaryLoading(true)
    setError(null)
    try {
      const [summaryResponse, historyResponse] = await Promise.all([
        api.appointmentSummary(token, appointment.id),
        api.patientHistory(token, appointment.patient_id),
      ])
      setSummary(summaryResponse)
      setHistory(historyResponse)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not load summary.')
    } finally {
      setSummaryLoading(false)
    }
  }

  return (
    <section className="workspace">
      <h2>Your schedule</h2>
      {error && <p className="error" role="alert">{error}</p>}
      {success && <p className="success" role="status">{success}</p>}

      <div className="card filter-card">
        <label>
          Date
          <input
            type="date"
            value={scheduleDate}
            onChange={(event) => setScheduleDate(event.target.value)}
          />
        </label>
        <label>
          Doctor note for completion (required)
          <textarea
            value={doctorNote}
            onChange={(event) => setDoctorNote(event.target.value)}
            placeholder="Short note, e.g. VA 6/9, review 6 months"
          />
        </label>
      </div>

      <div className="table-card">
        <h3>{scheduleDate}</h3>
        {loading ? (
          <p>Loading your schedule…</p>
        ) : appointments.length === 0 ? (
          <p>No appointments on this date.</p>
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
                    <button type="button" onClick={() => void openPatient(appointment)} disabled={busy}>
                      Open patient
                    </button>
                    {appointment.status === 'booked' && (
                      <button type="button" onClick={() => void complete(appointment)} disabled={busy || !doctorNote.trim()}>
                        Complete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selectedId && (
        <div className="card summary-card">
          <h3>Patient summary</h3>
          {summaryLoading ? (
            <p>Loading summary…</p>
          ) : summary ? (
            <>
              <p><em>{summary.label}</em></p>
              <p>{summary.summary}</p>
              {history.length > 0 && (
                <>
                  <h4>Past notes</h4>
                  {history.map((item) => (
                    <div key={item.id}>
                      <p><strong>{item.date} · {item.doctor_name} ({item.speciality})</strong></p>
                      <p>Reason: {item.reason ?? ''}</p>
                      <p>Note: {item.doctor_note ?? ''}</p>
                    </div>
                  ))}
                </>
              )}
            </>
          ) : (
            <p>Select Open patient to load the summary.</p>
          )}
        </div>
      )}
    </section>
  )
}
