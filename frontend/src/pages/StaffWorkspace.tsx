import { useMemo, useState } from 'react'
import { AlertTriangle, Search } from 'lucide-react'
import { api } from '../api/client'
import type { Appointment, Doctor, StaffApprovalRequest, UrgentCase } from '../api/client'
import { useAsync, errorMessage, type ViewState } from '../hooks/useAsync'
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

export default function StaffWorkspace() {
  const { session } = useSession()
  const token = session?.token ?? ''
  const [filterDate, setFilterDate] = useState(todayString())
  const [filterDoctor, setFilterDoctor] = useState('')
  const [cycle, setCycle] = useState(0)
  const refresh = () => setCycle((n) => n + 1)

  const doctorsQuery = useAsync((signal) => api.doctors(token, signal), [token])
  const scheduleQuery = useAsync(
    (signal) => api.staffAppointments(token, filterDate || undefined, filterDoctor || undefined, signal),
    [token, filterDate, filterDoctor, cycle],
  )
  const approvalsQuery = useAsync((signal) => api.staffApprovals(token, signal), [token, cycle])
  const urgentQuery = useAsync((signal) => api.urgentCases(token, signal), [token, cycle])

  const doctors: Doctor[] = doctorsQuery.state.status === 'success' ? doctorsQuery.state.data : []
  const unseenUrgent: UrgentCase[] =
    urgentQuery.state.status === 'success' ? urgentQuery.state.data.filter((u) => !u.seen) : []

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h1>Front desk</h1>
          <p>Clinic schedule, walk-in booking, approvals, and urgent cases.</p>
        </div>
      </div>
      {unseenUrgent.length > 0 && (
        <div style={{ marginBottom: 24 }} role="alert">
          <div className="emergency">
            {unseenUrgent.length} unseen urgent case{unseenUrgent.length === 1 ? '' : 's'} — review below.
          </div>
        </div>
      )}
      <div className="workspace">
        <ScheduleCard
          token={token}
          doctors={doctors}
          filterDate={filterDate}
          filterDoctor={filterDoctor}
          onFilterDate={setFilterDate}
          onFilterDoctor={setFilterDoctor}
          query={scheduleQuery.state}
          onChanged={refresh}
        />
        <WalkInCard token={token} doctors={doctors} onBooked={refresh} />
        <ApprovalsCard token={token} query={approvalsQuery.state} onChanged={refresh} />
        <UrgentCard token={token} query={urgentQuery.state} onChanged={refresh} />
        <SearchDebugCard token={token} />
      </div>
    </div>
  )
}

function ScheduleCard({
  token,
  doctors,
  filterDate,
  filterDoctor,
  onFilterDate,
  onFilterDoctor,
  query,
  onChanged,
}: {
  token: string
  doctors: Doctor[]
  filterDate: string
  filterDoctor: string
  onFilterDate: (v: string) => void
  onFilterDoctor: (v: string) => void
  query: ViewState<Appointment[]>
  onChanged: () => void
}) {
  const [cancelling, setCancelling] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const sorted = useMemo(() => {
    if (query.status !== 'success') return []
    return [...query.data].sort((a, b) => (a.date + a.start_time).localeCompare(b.date + b.start_time))
  }, [query])

  async function cancel(id: string) {
    setCancelling(id)
    setError(null)
    try {
      await api.cancelAppointment(token, id)
      setNotice('Appointment cancelled.')
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setCancelling(null)
    }
  }

  return (
    <section className="card" aria-label="Clinic schedule">
      <h2>Clinic schedule</h2>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
        <div>
          <label htmlFor="staff-date">Date</label>
          <input id="staff-date" type="date" value={filterDate} onChange={(e) => onFilterDate(e.target.value)} />
        </div>
        <div>
          <label htmlFor="staff-doctor">Doctor</label>
          <select id="staff-doctor" value={filterDoctor} onChange={(e) => onFilterDoctor(e.target.value)}>
            <option value="">All doctors</option>
            {doctors.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
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
      {query.status === 'loading' && <LoadingState label="Loading schedule" />}
      {query.status === 'error' && <InlineAlert tone="error">{query.message}</InlineAlert>}
      {query.status === 'empty' && <EmptyState>No appointments match these filters.</EmptyState>}
      {query.status === 'success' && (
        <div className="table-wrap">
          <table className="data">
            <caption>
              {sorted.length} appointment{sorted.length === 1 ? '' : 's'}
            </caption>
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Patient</th>
                <th scope="col">Doctor</th>
                <th scope="col">Visit</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((a) => (
                <tr key={a.id}>
                  <td className="mono">
                    {a.date} {a.start_time.slice(0, 5)}
                  </td>
                  <td>
                    {a.patient_name}
                    {a.reason && <div className="meta">{a.reason}</div>}
                  </td>
                  <td>{a.doctor_name}</td>
                  <td>
                    {a.speciality} · {a.visit_type === 'new' ? 'New' : 'Follow-up'}
                    {a.is_urgent && (
                      <>
                        {' '}
                        <StatusBadge tone="danger">urgent</StatusBadge>
                      </>
                    )}
                  </td>
                  <td>
                    <StatusBadge tone={appointmentTone(a.status)}>{a.status}</StatusBadge>
                  </td>
                  <td>
                    {a.status === 'booked' ? (
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        disabled={cancelling === a.id}
                        onClick={() => void cancel(a.id)}
                      >
                        {cancelling === a.id ? 'Cancelling…' : 'Cancel'}
                      </button>
                    ) : (
                      <span className="meta">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function WalkInCard({ token, doctors, onBooked }: { token: string; doctors: Doctor[]; onBooked: () => void }) {
  const [patientId, setPatientId] = useState('')
  const [walkInName, setWalkInName] = useState('')
  const [walkInMobile, setWalkInMobile] = useState('')
  const [doctorId, setDoctorId] = useState('')
  const [speciality, setSpeciality] = useState('')
  const [visitType, setVisitType] = useState<'new' | 'follow_up'>('new')
  const [date, setDate] = useState(todayString())
  const [startTime, setStartTime] = useState('10:00:00')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [emergency, setEmergency] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const patientsQuery = useAsync((signal) => api.staffPatients(token, signal), [token])
  const doctor = doctors.find((d) => d.id === doctorId)

  async function book() {
    setError(null)
    setEmergency(null)
    setSuccess(null)
    if (!patientId && !(walkInName.trim() && walkInMobile.trim())) {
      setError('Select a patient or enter both walk-in name and mobile.')
      return
    }
    if (!doctorId || !reason.trim()) {
      setError('Doctor, time, and reason are required.')
      return
    }
    setSubmitting(true)
    try {
      const result = await api.bookAsStaff(token, {
        doctor_id: doctorId,
        speciality: speciality || doctor?.specialities[0] || '',
        visit_type: visitType,
        date,
        start_time: startTime,
        reason: reason.trim(),
        ...(patientId ? { patient_id: patientId } : { walk_in_name: walkInName.trim(), walk_in_mobile: walkInMobile.trim() }),
      })
      if (result.emergency) setEmergency(result.emergency)
      setSuccess(`Booked for ${result.patient_name} on ${formatDateTime(result.date, result.start_time)}.`)
      onBooked()
    } catch (err) {
      const e = err as { emergency?: string | null }
      if (e && typeof e.emergency === 'string' && e.emergency) setEmergency(e.emergency)
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="card" aria-label="Book for a patient">
      <h2>Book for a patient</h2>
      <div className="form-group">
        <label htmlFor="walkin-patient">Existing patient</label>
        {patientsQuery.state.status === 'success' ? (
          <select id="walkin-patient" value={patientId} onChange={(e) => setPatientId(e.target.value)}>
            <option value="">Walk-in (new patient)…</option>
            {patientsQuery.state.data.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.mobile}
              </option>
            ))}
          </select>
        ) : (
          <p className="meta">Loading patients…</p>
        )}
      </div>
      {!patientId && (
        <>
          <div className="form-group">
            <label htmlFor="walkin-name">Walk-in name</label>
            <input id="walkin-name" value={walkInName} onChange={(e) => setWalkInName(e.target.value)} />
          </div>
          <div className="form-group">
            <label htmlFor="walkin-mobile">Walk-in mobile</label>
            <input id="walkin-mobile" inputMode="tel" value={walkInMobile} onChange={(e) => setWalkInMobile(e.target.value)} />
          </div>
        </>
      )}
      <div className="form-group">
        <label htmlFor="walkin-doctor">Doctor</label>
        <select
          id="walkin-doctor"
          value={doctorId}
          onChange={(e) => {
            setDoctorId(e.target.value)
            setSpeciality('')
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
          <label htmlFor="walkin-speciality">Speciality</label>
          <select id="walkin-speciality" value={speciality || doctor.specialities[0]} onChange={(e) => setSpeciality(e.target.value)}>
            {doctor.specialities.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="form-group">
        <label htmlFor="walkin-visit">Visit type</label>
        <select id="walkin-visit" value={visitType} onChange={(e) => setVisitType(e.target.value as 'new' | 'follow_up')}>
          <option value="new">New consultation (20 min)</option>
          <option value="follow_up">Follow-up (10 min)</option>
        </select>
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <div className="form-group" style={{ flex: 1, minWidth: 160 }}>
          <label htmlFor="walkin-date">Date</label>
          <input id="walkin-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div className="form-group" style={{ flex: 1, minWidth: 160 }}>
          <label htmlFor="walkin-time">Time</label>
          <input id="walkin-time" type="time" step={600} value={startTime.slice(0, 5)} onChange={(e) => setStartTime(`${e.target.value}:00`)} />
        </div>
      </div>
      <div className="form-group">
        <label htmlFor="walkin-reason">Reason</label>
        <textarea id="walkin-reason" rows={2} maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} />
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
      <button type="button" className="btn btn-primary" disabled={submitting} onClick={() => void book()}>
        {submitting ? 'Booking…' : 'Book appointment'}
      </button>
    </section>
  )
}

function ApprovalsCard({
  token,
  query,
  onChanged,
}: {
  token: string
  query: ViewState<StaffApprovalRequest[]>
  onChanged: () => void
}) {
  const [deciding, setDeciding] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmReject, setConfirmReject] = useState<StaffApprovalRequest | null>(null)

  async function decide(request: StaffApprovalRequest, action: 'approve' | 'reject') {
    setDeciding(request.id + action)
    setError(null)
    try {
      if (action === 'approve') await api.approveApproval(token, request.id)
      else await api.rejectApproval(token, request.id)
      setConfirmReject(null)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDeciding(null)
    }
  }

  return (
    <section className="card" aria-label="Pending approvals">
      <h2>Approvals queue</h2>
      {error && (
        <div style={{ marginBottom: 12 }}>
          <InlineAlert tone="error">{error}</InlineAlert>
        </div>
      )}
      {query.status === 'loading' && <LoadingState label="Loading approvals" />}
      {query.status === 'error' && <InlineAlert tone="error">{query.message}</InlineAlert>}
      {query.status === 'empty' && <EmptyState>No pending requests. Late patient cancellations and reschedules will appear here.</EmptyState>}
      {query.status === 'success' && (
        <div className="row-list">
          {query.data.map((r) => (
            <div key={r.id} className="entity-row">
              <div className="entity-row-head">
                <strong>
                  {r.action === 'cancel' ? 'Cancel' : 'Reschedule'} · {r.patient_name ?? r.patient_id}
                </strong>
                <StatusBadge tone="warning">{r.status}</StatusBadge>
              </div>
              <span className="meta mono">
                Appointment {r.appointment_id}
                {r.action === 'reschedule' && r.target_date
                  ? ` → ${r.target_doctor_id} ${r.target_date} ${(r.target_start_time ?? '').slice(0, 5)}`
                  : ''}
              </span>
              <span className="meta">Requested {r.requested_at.replace('T', ' ').slice(0, 16)}</span>
              <span className="entity-row-actions">
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={deciding !== null}
                  onClick={() => void decide(r, 'approve')}
                >
                  {deciding === r.id + 'approve' ? 'Approving…' : 'Approve'}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={deciding !== null}
                  onClick={() => setConfirmReject(r)}
                >
                  Reject
                </button>
              </span>
            </div>
          ))}
        </div>
      )}
      {confirmReject && (
        <ConfirmDialog
          title="Reject this request?"
          body={<p>The appointment stays booked. The patient keeps their original slot.</p>}
          confirmLabel="Reject request"
          danger
          pending={deciding !== null}
          onConfirm={() => void decide(confirmReject, 'reject')}
          onClose={() => setConfirmReject(null)}
        />
      )}
    </section>
  )
}

function UrgentCard({
  token,
  query,
  onChanged,
}: {
  token: string
  query: ViewState<UrgentCase[]>
  onChanged: () => void
}) {
  const [marking, setMarking] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function markSeen(id: string) {
    setMarking(id)
    setError(null)
    try {
      await api.markUrgentSeen(token, id)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setMarking(null)
    }
  }

  return (
    <section className="card" aria-label="Urgent cases">
      <h2><AlertTriangle size={18} aria-hidden="true" style={{ verticalAlign: '-3px', marginRight: 8 }} />Urgent cases</h2>
      {error && (
        <div style={{ marginBottom: 12 }}>
          <InlineAlert tone="error">{error}</InlineAlert>
        </div>
      )}
      {query.status === 'loading' && <LoadingState label="Loading urgent cases" />}
      {query.status === 'error' && <InlineAlert tone="error">{query.message}</InlineAlert>}
      {query.status === 'empty' && <EmptyState>No urgent cases on record.</EmptyState>}
      {query.status === 'success' && (
        <div className="row-list">
          {query.data.map((u) => (
            <div key={u.id} className="entity-row" style={u.seen ? undefined : { borderColor: 'var(--danger)' }}>
              <div className="entity-row-head">
                <strong>
                  {u.patient_name ?? 'Unknown patient'}
                  {u.patient_mobile ? ` · ${u.patient_mobile}` : ''}
                </strong>
                <span style={{ display: 'flex', gap: 6 }}>
                  <StatusBadge tone="info">{u.origin}</StatusBadge>
                  {u.seen ? <StatusBadge tone="neutral">seen</StatusBadge> : <StatusBadge tone="danger">unseen</StatusBadge>}
                </span>
              </div>
              <span className="meta">
                {u.category} · {u.created_at.replace('T', ' ').slice(0, 16)}
              </span>
              <p style={{ fontSize: '0.92rem' }}>{u.reason_text}</p>
              {!u.seen && (
                <span className="entity-row-actions">
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={marking === u.id}
                    onClick={() => void markSeen(u.id)}
                  >
                    {marking === u.id ? 'Marking…' : 'Mark seen'}
                  </button>
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function SearchDebugCard({ token }: { token: string }) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.searchDebug>> | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function search(event: React.FormEvent) {
    event.preventDefault()
    const text = query.trim()
    if (text.length < 2 || pending) return
    setPending(true)
    setError(null)
    try {
      setResult(await api.searchDebug(token, text))
    } catch (err) {
      setError(errorMessage(err))
      setResult(null)
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="card" aria-label="Retrieval inspector">
      <h2>Retrieval inspector</h2>
      <form onSubmit={search} style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <label htmlFor="search-debug-q" className="meta" style={{ position: 'absolute', left: -9999 }}>
          Retrieval query
        </label>
        <input
          id="search-debug-q"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Query (min 2 characters)"
        />
        <button type="submit" className="btn btn-secondary" disabled={query.trim().length < 2 || pending}>
          {pending ? 'Searching…' : (<><Search size={14} aria-hidden="true" /> Search</>)}
        </button>
      </form>
      {error && <InlineAlert tone="error">{error}</InlineAlert>}
      {!error && !result && <EmptyState>Keyword, vector, and hybrid top-four results appear here with labeled scores.</EmptyState>}
      {result && (
        <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          {(
            [
              ['Keyword', result.keyword],
              ['Vector', result.vector],
              ['Hybrid', result.hybrid],
            ] as const
          ).map(([label, chunks]) => (
            <div key={label}>
              <h3 style={{ fontSize: '1rem', marginBottom: 8 }}>{label}</h3>
              {chunks.length === 0 && <p className="meta">No results.</p>}
              <div className="row-list">
                {chunks.map((chunk) => (
                  <div key={`${label}-${chunk.chunk_id}`} className="entity-row">
                    <span className="mono" style={{ fontSize: '0.8rem' }}>
                      {chunk.chunk_id} · {chunk.score_kind} {chunk.score ?? '—'}
                    </span>
                    <span className="meta">
                      {chunk.source} › {chunk.section}
                    </span>
                    <p style={{ fontSize: '0.85rem' }}>{chunk.text}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
