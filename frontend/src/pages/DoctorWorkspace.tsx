import { useState } from 'react'
import { api } from '../api/client'
import type { Appointment, DoctorSummary, PatientHistoryItem } from '../api/client'
import { useAsync, errorMessage } from '../hooks/useAsync'
import { useSession } from '../context/SessionContext'
import {
  ConfirmDialog,
  EmptyState,
  InlineAlert,
  LoadingState,
  StatusBadge,
  appointmentTone,
  formatDateTime,
} from '../components/ui'

function todayString(): string {
  return new Date().toISOString().slice(0, 10)
}

export default function DoctorWorkspace() {
  const { session } = useSession()
  const token = session?.token ?? ''
  const [date, setDate] = useState(todayString())
  const [cycle, setCycle] = useState(0)
  const refresh = () => setCycle((n) => n + 1)

  const scheduleQuery = useAsync((signal) => api.doctorAppointments(token, date, signal), [token, date, cycle])

  const [completing, setCompleting] = useState<Appointment | null>(null)
  const [note, setNote] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const [selectedPatient, setSelectedPatient] = useState<{ id: string; name: string } | null>(null)

  async function complete() {
    if (!completing || !note.trim()) return
    setPending(true)
    setError(null)
    try {
      await api.completeAppointment(token, completing.id, note.trim())
      setNotice(`Visit for ${completing.patient_name} marked completed.`)
      setCompleting(null)
      setNote('')
      refresh()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h1>Your schedule</h1>
          <p>Today&apos;s visits, intake notes, and AI summaries.</p>
        </div>
      </div>
      <div className="workspace">
        <section className="card" aria-label="Day schedule">
          <h2>Day schedule</h2>
          <div className="form-group" style={{ maxWidth: 260 }}>
            <label htmlFor="doctor-date">Date</label>
            <input id="doctor-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          {notice && (
            <div style={{ marginBottom: 12 }}>
              <InlineAlert tone="success">{notice}</InlineAlert>
            </div>
          )}
          {error && (
            <div style={{ marginBottom: 12 }}>
              <InlineAlert tone="error">{error}</InlineAlert>
            </div>
          )}
          {scheduleQuery.state.status === 'loading' && <LoadingState label="Loading schedule" />}
          {scheduleQuery.state.status === 'error' && <InlineAlert tone="error">{scheduleQuery.state.message}</InlineAlert>}
          {scheduleQuery.state.status === 'empty' && <EmptyState>No appointments on this date.</EmptyState>}
          {scheduleQuery.state.status === 'success' && (
            <div className="row-list">
              {scheduleQuery.state.data.map((a) => (
                <div key={a.id} className="entity-row">
                  <div className="entity-row-head">
                    <strong>
                      {a.start_time.slice(0, 5)}–{a.end_time.slice(0, 5)} · {a.patient_name}
                    </strong>
                    <span style={{ display: 'flex', gap: 6 }}>
                      <StatusBadge tone={appointmentTone(a.status)}>{a.status}</StatusBadge>
                      {a.is_urgent && <StatusBadge tone="danger">urgent</StatusBadge>}
                    </span>
                  </div>
                  <span className="meta">
                    {a.speciality} · {a.visit_type === 'new' ? 'New' : 'Follow-up'}
                  </span>
                  {a.reason && <p style={{ fontSize: '0.92rem' }}>Reason: {a.reason}</p>}
                  <span className="entity-row-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setSelectedPatient({ id: a.patient_id, name: a.patient_name })}
                    >
                      Patient file
                    </button>
                    {a.status === 'booked' && (
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={() => {
                          setCompleting(a)
                          setNote('')
                          setError(null)
                        }}
                      >
                        Complete visit
                      </button>
                    )}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {selectedPatient && (
          <PatientFileCard
            key={selectedPatient.id}
            token={token}
            patient={selectedPatient}
            onClose={() => setSelectedPatient(null)}
          />
        )}
      </div>

      {completing && (
        <ConfirmDialog
          title={`Complete visit — ${completing.patient_name}`}
          body={
            <>
              <p className="meta" style={{ marginBottom: 12 }}>
                {formatDateTime(completing.date, completing.start_time)} · {completing.speciality}. A short note is
                required and will be saved with the visit.
              </p>
              <div className="form-group">
                <label htmlFor="complete-note">Doctor note</label>
                <textarea
                  id="complete-note"
                  rows={4}
                  maxLength={2000}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Findings, advice given, follow-up plan…"
                />
                <span className={`char-count${note.length >= 1900 ? ' over' : ''}`}>{note.length}/2000</span>
              </div>
            </>
          }
          confirmLabel="Mark completed"
          pending={pending}
          onConfirm={() => void complete()}
          onClose={() => {
            if (!pending) {
              setCompleting(null)
              setNote('')
            }
          }}
        />
      )}
    </div>
  )
}

function PatientFileCard({
  token,
  patient,
  onClose,
}: {
  token: string
  patient: { id: string; name: string }
  onClose: () => void
}) {
  const { session } = useSession()
  const historyQuery = useAsync((signal) => api.patientHistory(token, patient.id, signal), [token, patient.id])
  const [summaryFor, setSummaryFor] = useState<string | null>(null)

  const history: PatientHistoryItem[] =
    historyQuery.state.status === 'success' ? historyQuery.state.data : []

  return (
    <section className="card" aria-label={`Patient file for ${patient.name}`}>
      <div className="entity-row-head" style={{ marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>{patient.name} — completed visits</h2>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
          Close
        </button>
      </div>
      {historyQuery.state.status === 'loading' && <LoadingState label="Loading history" />}
      {historyQuery.state.status === 'error' && <InlineAlert tone="error">{historyQuery.state.message}</InlineAlert>}
      {historyQuery.state.status === 'empty' && <EmptyState>No completed visits on record.</EmptyState>}
      {historyQuery.state.status === 'success' && (
        <div className="row-list">
          {history.map((item) => (
            <div key={item.id} className="entity-row">
              <div className="entity-row-head">
                <strong>
                  {item.date} · {item.doctor_name}
                </strong>
                <StatusBadge tone="neutral">{item.speciality}</StatusBadge>
              </div>
              {item.reason && (
                <p style={{ fontSize: '0.92rem' }}>
                  <span className="meta">Reason: </span>
                  {item.reason}
                </p>
              )}
              {item.doctor_note && (
                <p style={{ fontSize: '0.92rem' }}>
                  <span className="meta">Note: </span>
                  {item.doctor_note}
                </p>
              )}
              <span className="entity-row-actions">
                {/* Summaries are scoped to the signed-in doctor's own visits —
                    the API refuses other doctors' appointments by design. */}
                {item.doctor_id === session?.doctorId ? (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setSummaryFor(summaryFor === item.id ? null : item.id)}
                  >
                    {summaryFor === item.id ? 'Hide AI summary' : 'AI summary'}
                  </button>
                ) : (
                  <span className="meta">Summary available to {item.doctor_name}</span>
                )}
              </span>
              {summaryFor === item.id && <SummaryBlock key={item.id} token={token} appointmentId={item.id} />}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function SummaryBlock({ token, appointmentId }: { token: string; appointmentId: string }) {
  const summaryQuery = useAsync((signal) => api.appointmentSummary(token, appointmentId, signal), [token, appointmentId])

  if (summaryQuery.state.status === 'loading') return <LoadingState label="Generating summary" />
  if (summaryQuery.state.status === 'error')
    return <InlineAlert tone="error">Summary unavailable. See the notes above.</InlineAlert>
  if (summaryQuery.state.status !== 'success') return null
  const summary: DoctorSummary = summaryQuery.state.data
  return (
    <div className="alert alert-info" role="status">
      <span>
        <strong>{summary.label}</strong>
        <br />
        {summary.summary}
        {summary.fallback && (
          <>
            <br />
            <span className="meta">Fallback summary — AI unavailable.</span>
          </>
        )}
      </span>
    </div>
  )
}
