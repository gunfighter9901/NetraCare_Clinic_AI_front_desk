import { useMemo, useState } from 'react'
import { CalendarDays, RefreshCw } from 'lucide-react'
import { api, ApiError } from '../api/client'
import type { Appointment, Doctor, FactResponse, ToStaffResponse } from '../api/client'
import { useAsync, errorMessage, type ViewState } from '../hooks/useAsync'
import { useSession } from '../context/SessionContext'
import ChatPanel from '../components/ChatPanel'
import {
  ConfirmDialog,
  EmptyState,
  InlineAlert,
  LoadingState,
  RetryState,
  StatusBadge,
  appointmentTone,
  formatDateTime,
} from '../components/ui'

function isToStaff(value: Appointment | ToStaffResponse): value is ToStaffResponse {
  return (value as ToStaffResponse).result === 'to_staff'
}

function todayPlus(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

export default function PatientWorkspace() {
  const { session } = useSession()
  const token = session?.token ?? ''
  const [bookingKey, setBookingKey] = useState(0)
  const [chatKey, setChatKey] = useState(0)

  const doctorsQuery = useAsync((signal) => api.doctors(token, signal), [token])
  const appointmentsQuery = useAsync((signal) => api.patientAppointments(token, signal), [token, bookingKey])
  const factQuery = useAsync((signal) => api.factOfTheDay(token, undefined, signal), [token])

  const doctors: Doctor[] = doctorsQuery.state.status === 'success' ? doctorsQuery.state.data : []

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h1>Your eye care</h1>
          <p>Book visits, manage appointments, and ask the clinic assistant.</p>
        </div>
      </div>
      <div className="workspace">
        <BookingCard
          key={`book-${bookingKey}`}
          token={token}
          doctors={doctors}
          doctorsState={doctorsQuery.state.status}
          onBooked={() => setBookingKey((n) => n + 1)}
        />
        <AppointmentsCard
          token={token}
          query={appointmentsQuery.state}
          onChanged={() => {
            setBookingKey((n) => n + 1)
            setChatKey((n) => n + 1)
          }}
        />
        <ChatPanel key={chatKey} token={token} onDataChanged={() => setBookingKey((n) => n + 1)} />
        <FactCard query={factQuery.state} token={token} />
      </div>
    </div>
  )
}

function BookingCard({
  token,
  doctors,
  doctorsState,
  onBooked,
}: {
  token: string
  doctors: Doctor[]
  doctorsState: string
  onBooked: () => void
}) {
  const [doctorId, setDoctorId] = useState('')
  const [visitType, setVisitType] = useState<'new' | 'follow_up'>('new')
  const [date, setDate] = useState(() => todayPlus(2))
  const [slot, setSlot] = useState('')
  const [reason, setReason] = useState('')
  const [slots, setSlots] = useState<string[] | null>(null)
  const [slotsMessage, setSlotsMessage] = useState<string | null>(null)
  const [loadingSlots, setLoadingSlots] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [emergency, setEmergency] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const doctor = useMemo(() => doctors.find((d) => d.id === doctorId), [doctors, doctorId])
  const [speciality, setSpeciality] = useState('')

  async function loadSlots() {
    if (!doctorId) return
    setError(null)
    setEmergency(null)
    setSuccess(null)
    setLoadingSlots(true)
    try {
      const result = await api.slots(token, doctorId, date, visitType)
      setSlots(result.slots)
      setSlotsMessage(result.message)
      setSlot('')
    } catch (err) {
      setError(errorMessage(err))
      setSlots(null)
    } finally {
      setLoadingSlots(false)
    }
  }

  async function book() {
    if (!doctor || !slot || !reason.trim()) return
    setError(null)
    setEmergency(null)
    setSuccess(null)
    setSubmitting(true)
    try {
      const result = await api.bookAsPatient(token, {
        doctor_id: doctor.id,
        speciality: speciality || doctor.specialities[0],
        visit_type: visitType,
        date,
        start_time: slot,
        reason: reason.trim(),
      })
      if (result.emergency) setEmergency(result.emergency)
      setSuccess(`Booked with ${result.doctor_name} on ${formatDateTime(result.date, result.start_time)}.`)
      setReason('')
      setSlot('')
      setSlots(null)
      onBooked()
    } catch (err) {
      if (err instanceof ApiError && err.emergency) setEmergency(err.emergency)
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="card" aria-label="Book an appointment">
      <h2><CalendarDays size={18} aria-hidden="true" style={{ verticalAlign: '-3px', marginRight: 8 }} />Book an appointment</h2>
      {doctorsState === 'loading' && <LoadingState label="Loading doctors" />}
      {doctorsState === 'error' && <InlineAlert tone="error">Could not load doctors. Please reload the page.</InlineAlert>}
      {doctorsState !== 'loading' && doctorsState !== 'error' && (
        <>
          <div className="form-group">
            <label htmlFor="book-doctor">Doctor</label>
            <select
              id="book-doctor"
              value={doctorId}
              onChange={(e) => {
                setDoctorId(e.target.value)
                setSpeciality('')
                setSlots(null)
              }}
            >
              <option value="">Choose…</option>
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} — {d.specialities.join(', ')}
                </option>
              ))}
            </select>
          </div>
          {doctor && (
            <div className="form-group">
              <label htmlFor="book-speciality">Speciality</label>
              <select id="book-speciality" value={speciality || doctor.specialities[0]} onChange={(e) => setSpeciality(e.target.value)}>
                {doctor.specialities.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="form-group">
            <label htmlFor="book-visit">Visit type</label>
            <select id="book-visit" value={visitType} onChange={(e) => setVisitType(e.target.value as 'new' | 'follow_up')}>
              <option value="new">New consultation (20 min)</option>
              <option value="follow_up">Follow-up (10 min)</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="book-date">Date</label>
            <input id="book-date" type="date" value={date} min={todayPlus(0)} max={todayPlus(30)} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div style={{ marginBottom: 20 }}>
            <button type="button" className="btn btn-secondary" onClick={() => void loadSlots()} disabled={!doctorId || loadingSlots}>
              {loadingSlots ? 'Finding slots…' : 'Find free slots'}
            </button>
            {slotsMessage && <p className="meta" style={{ marginTop: 8 }}>{slotsMessage}</p>}
            {slots && slots.length > 0 && (
              <div className="form-group" style={{ marginTop: 12 }}>
                <label htmlFor="book-slot">Time</label>
                <select id="book-slot" value={slot} onChange={(e) => setSlot(e.target.value)}>
                  <option value="">Choose…</option>
                  {slots.map((s) => (
                    <option key={s} value={s}>
                      {s.slice(0, 5)}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {slots && slots.length === 0 && <EmptyState>No free slots for this choice. Try another day or doctor.</EmptyState>}
          </div>
          <div className="form-group">
            <label htmlFor="book-reason">Reason for visit</label>
            <textarea
              id="book-reason"
              rows={3}
              maxLength={300}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Describe briefly why you need this visit"
            />
            <span className={`char-count${reason.length >= 280 ? ' over' : ''}`}>{reason.length}/300</span>
          </div>
          {emergency && (
            <div style={{ marginBottom: 12 }}>
              <div className="emergency" role="alert">
                {emergency}
              </div>
            </div>
          )}
          {error && (
            <div style={{ marginBottom: 12 }}>
              <InlineAlert tone="error">{error}</InlineAlert>
            </div>
          )}
          {success && (
            <div style={{ marginBottom: 12 }}>
              <InlineAlert tone="success">{success}</InlineAlert>
            </div>
          )}
          <button type="button" className="btn btn-primary" disabled={!doctor || !slot || !reason.trim() || submitting} onClick={() => void book()}>
            {submitting ? 'Booking…' : 'Book appointment'}
          </button>
        </>
      )}
    </section>
  )
}

function AppointmentsCard({
  token,
  query,
  onChanged,
}: {
  token: string
  query: ViewState<Appointment[]>
  onChanged: () => void
}) {
  const [dialog, setDialog] = useState<
    | null
    | { kind: 'cancel' | 'reschedule'; appointment: Appointment }
  >(null)
  const [rescheduleDate, setRescheduleDate] = useState(() => todayPlus(3))
  const [rescheduleTime, setRescheduleTime] = useState('10:00:00')
  const [pending, setPending] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function doCancel(appointment: Appointment) {
    setActionError(null)
    setPending(true)
    try {
      const result = await api.cancelAppointment(token, appointment.id)
      if (isToStaff(result)) {
        setNotice('Sent to Staff for approval. Your appointment remains booked for now.')
      } else {
        setNotice(`Appointment on ${result.date} cancelled.`)
      }
      onChanged()
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setPending(false)
      setDialog(null)
    }
  }

  async function doReschedule(appointment: Appointment) {
    setActionError(null)
    setPending(true)
    try {
      const result = await api.rescheduleAppointment(token, appointment.id, {
        doctor_id: appointment.doctor_id,
        date: rescheduleDate,
        start_time: rescheduleTime,
      })
      if (isToStaff(result)) {
        setNotice('Sent to Staff for approval. Your appointment remains booked for now.')
      } else {
        setNotice(`Rescheduled to ${formatDateTime(result.date, result.start_time)}.`)
      }
      onChanged()
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setPending(false)
      setDialog(null)
    }
  }

  return (
    <section className="card" aria-label="Your appointments">
      <h2><CalendarDays size={18} aria-hidden="true" style={{ verticalAlign: '-3px', marginRight: 8 }} />Your appointments</h2>
      {notice && (
        <div style={{ marginBottom: 12 }}>
          <InlineAlert tone="success">{notice}</InlineAlert>
        </div>
      )}
      {actionError && (
        <div style={{ marginBottom: 12 }}>
          <InlineAlert tone="error">{actionError}</InlineAlert>
        </div>
      )}
      {query.status === 'loading' && <LoadingState label="Loading appointments" />}
      {query.status === 'error' && <InlineAlert tone="error">{query.message}</InlineAlert>}
      {query.status === 'empty' && <EmptyState>No appointments yet. Book your first visit above.</EmptyState>}
      {query.status === 'success' && (
        <div className="row-list">
          {query.data.map((a) => (
            <div key={a.id} className="entity-row">
              <div className="entity-row-head">
                <strong>
                  {a.doctor_name} · {a.speciality}
                </strong>
                <span style={{ display: 'flex', gap: 6 }}>
                  <StatusBadge tone={appointmentTone(a.status)}>{a.status}</StatusBadge>
                  {a.is_urgent && <StatusBadge tone="danger">urgent</StatusBadge>}
                  {a.approval_status === 'pending' && <StatusBadge tone="warning">staff review</StatusBadge>}
                </span>
              </div>
              <span className="meta mono">
                {formatDateTime(a.date, a.start_time)}–{a.end_time.slice(0, 5)} · {a.visit_type === 'new' ? 'New' : 'Follow-up'}
              </span>
              {a.approval_action && (
                <span className="meta">
                  Request: {a.approval_action} · {a.approval_status}
                </span>
              )}
              {a.status === 'booked' && (
                <span className="entity-row-actions">
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => setDialog({ kind: 'reschedule', appointment: a })}>
                    Reschedule
                  </button>
                  <button type="button" className="btn btn-danger btn-sm" onClick={() => setDialog({ kind: 'cancel', appointment: a })}>
                    Cancel
                  </button>
                </span>
              )}
            </div>
          ))}
        </div>
      )}
      {dialog?.kind === 'cancel' && (
        <ConfirmDialog
          title="Cancel this appointment?"
          body={
            <p>
              {dialog.appointment.doctor_name} on {formatDateTime(dialog.appointment.date, dialog.appointment.start_time)}.
              Inside two hours this goes to Staff instead.
            </p>
          }
          confirmLabel="Yes, cancel"
          danger
          pending={pending}
          onConfirm={() => void doCancel(dialog.appointment)}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.kind === 'reschedule' && (
        <ConfirmDialog
          title="Reschedule this appointment?"
          body={
            <>
              <p className="meta" style={{ marginBottom: 12 }}>
                Same doctor, new time. Inside two hours this goes to Staff instead.
              </p>
              <div className="form-group">
                <label htmlFor="resched-date">New date</label>
                <input id="resched-date" type="date" value={rescheduleDate} min={todayPlus(0)} max={todayPlus(30)} onChange={(e) => setRescheduleDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label htmlFor="resched-time">New time</label>
                <input id="resched-time" type="time" step={600} value={rescheduleTime.slice(0, 5)} onChange={(e) => setRescheduleTime(`${e.target.value}:00`)} />
              </div>
            </>
          }
          confirmLabel="Reschedule"
          pending={pending}
          onConfirm={() => void doReschedule(dialog.appointment)}
          onClose={() => setDialog(null)}
        />
      )}
    </section>
  )
}

function FactCard({ query, token }: { query: ViewState<FactResponse>; token: string }) {
  const [fact, setFact] = useState<{ fact: string; caveat: string } | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const current = fact ?? (query.status === 'success' ? query.data : null)

  async function refresh() {
    setPending(true)
    setError(null)
    try {
      setFact(await api.factOfTheDay(token, current?.fact))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="card card-compact" aria-label="Fact of the day">
      <div className="entity-row-head" style={{ marginBottom: 8 }}>
        <h2 style={{ margin: 0 }}>Fact of the day</h2>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => void refresh()} disabled={pending}>
          {pending ? 'Refreshing…' : (<><RefreshCw size={14} aria-hidden="true" /> Refresh</>)}
        </button>
      </div>
      {query.status === 'loading' && !current && <LoadingState label="Loading fact" />}
      {query.status === 'error' && !current && <RetryState message={query.message} onRetry={() => void refresh()} />}
      {error && (
        <div style={{ marginBottom: 8 }}>
          <InlineAlert tone="error">{error}</InlineAlert>
        </div>
      )}
      {current && (
        <>
          <p>{current.fact}</p>
          <p className="meta" style={{ marginTop: 8 }}>
            {current.caveat}
          </p>
        </>
      )}
    </section>
  )
}
