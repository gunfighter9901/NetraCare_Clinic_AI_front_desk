/* Sole backend boundary. Views call `api.*`; nothing else constructs URLs.
   Base URL: same-origin `/api` proxy in dev (vite.config.ts), or
   VITE_API_BASE_URL in production. Auth header injected in one place. */

export type Role = 'patient' | 'staff' | 'doctor'
export type VisitType = 'new' | 'follow_up'
export type AppointmentStatus = 'booked' | 'cancelled' | 'completed'

export interface AuthResponse {
  token: string
  role: Role
  patient_id: string | null
  doctor_id: string | null
  display_name: string
}
export interface ActorResponse {
  token?: never
  role: Role
  patient_id: string | null
  doctor_id: string | null
  display_name: string
}
export interface DoctorOption {
  id: string
  name: string
}
export interface Doctor {
  id: string
  name: string
  specialities: string[]
  opd_days?: string[] | null
}
export interface PatientSummary {
  id: string
  name: string
  mobile: string
  year_of_birth: number | null
}
export interface Appointment {
  id: string
  patient_id: string
  patient_name: string
  doctor_id: string
  doctor_name: string
  speciality: string
  visit_type: VisitType
  date: string
  start_time: string
  end_time: string
  status: AppointmentStatus
  created_at: string
  cancelled_at: string | null
  completed_at: string | null
  reason?: string | null
  is_urgent?: boolean
  urgent_case_id?: string | null
  emergency?: string | null
  approval_request_id?: string | null
  approval_action?: 'cancel' | 'reschedule' | null
  approval_status?: 'pending' | 'approved' | 'rejected' | null
}
export interface SlotAvailability {
  doctor_id: string
  date: string
  visit_type: VisitType
  slots: string[]
  message: string
}
export interface AppointmentRequest {
  doctor_id: string
  speciality: string
  visit_type: VisitType
  date: string
  start_time: string
  reason: string
}
export interface StaffAppointmentRequest extends AppointmentRequest {
  patient_id?: string
  walk_in_name?: string
  walk_in_mobile?: string
}
export interface FactResponse {
  fact: string
  caveat: string
}
export interface UrgentCase {
  id: string
  patient_id: string | null
  patient_name: string | null
  patient_mobile: string | null
  reason_text: string
  category: string
  model_why: string | null
  created_at: string
  seen: boolean
  seen_at: string | null
  origin: string
}
export interface DoctorSummary {
  appointment_id: string
  patient_id: string
  summary: string
  label: string
  fallback: boolean
}
export interface ChatSource {
  file: string
  section: string
}
export interface ChatPendingAction {
  action: 'book' | 'cancel' | 'reschedule'
  summary: string
  appointment_id: string | null
  doctor_id: string | null
  doctor_name: string | null
  date: string | null
  start_time: string | null
  speciality: string | null
  visit_type: VisitType | null
}
export interface ChatReply {
  kind: 'emergency' | 'answer'
  message: string
  sources: ChatSource[]
  urgent_case_id: string | null
  urgent_category: string | null
  response_type: string
  pending_action?: ChatPendingAction | null
  approval_request_id?: string | null
}
export interface StaffApprovalRequest {
  id: string
  patient_id: string
  patient_name: string | null
  appointment_id: string
  action: 'cancel' | 'reschedule'
  status: 'pending' | 'approved' | 'rejected'
  target_doctor_id: string | null
  target_doctor_name: string | null
  target_date: string | null
  target_start_time: string | null
  replacement_appointment_id: string | null
  requested_at: string
  decided_at: string | null
  decided_by: string | null
}
export interface ToStaffResponse {
  result: 'to_staff'
  reason_code: string
  message: string
  appointment: Appointment
  approval_request: StaffApprovalRequest
}
export interface SearchDebugChunk {
  chunk_id: string
  source: string
  section: string
  text: string
  score: number | null
  score_kind: string
}
export interface SearchDebugResponse {
  query: string
  keyword: SearchDebugChunk[]
  vector: SearchDebugChunk[]
  hybrid: SearchDebugChunk[]
}
export interface PatientHistoryItem {
  id: string
  date: string
  doctor_id: string
  doctor_name: string
  speciality: string
  visit_type: VisitType
  reason: string | null
  doctor_note: string | null
  status: AppointmentStatus
}

export class ApiError extends Error {
  status: number
  reasonCode: string | null
  emergency: string | null
  urgentCaseId: string | null
  urgentCategory: string | null

  constructor(
    message: string,
    status: number,
    reasonCode: string | null = null,
    emergency: string | null = null,
    urgentCaseId: string | null = null,
    urgentCategory: string | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.reasonCode = reasonCode
    this.emergency = emergency
    this.urgentCaseId = urgentCaseId
    this.urgentCategory = urgentCategory
  }
}

const configuredBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
const API_BASE = configuredBase || '/api'

interface RequestOptions {
  method?: string
  body?: unknown
  token?: string
  signal?: AbortSignal
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.token) headers.Authorization = `Bearer ${options.token}`

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('The clinic server could not be reached. Check your connection and retry.', 0)
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    let reasonCode: string | null = null
    let emergency: string | null = null
    let urgentCaseId: string | null = null
    let urgentCategory: string | null = null
    try {
      const data = await response.json()
      if (data?.message) {
        message = data.message
        reasonCode = data.reason_code ?? data.reasonCode ?? null
        emergency = data.emergency ?? null
        urgentCaseId = data.urgent_case_id ?? data.urgentCaseId ?? null
        urgentCategory = data.urgent_category ?? data.urgentCategory ?? null
      } else if (typeof data?.detail === 'string') {
        message = data.detail
      } else if (data?.emergency) {
        emergency = data.emergency
        message = data.message ?? data.emergency
      }
    } catch {
      // Keep the generic request failure message.
    }
    throw new ApiError(message, response.status, reasonCode, emergency, urgentCaseId, urgentCategory)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const get = <T>(path: string, token?: string, signal?: AbortSignal): Promise<T> =>
  request<T>(path, { token, signal })

const post = <T>(path: string, body: unknown, token?: string, signal?: AbortSignal): Promise<T> =>
  request<T>(path, { method: 'POST', body, token, signal })

export const api = {
  doctorOptions: (signal?: AbortSignal) => get<DoctorOption[]>('/auth/doctor-options', undefined, signal),

  loginPatient: (mobile: string, name: string, signal?: AbortSignal) =>
    post<AuthResponse>('/auth/patient', { mobile, name }, undefined, signal),

  loginDoctor: (doctorId: string, signal?: AbortSignal) =>
    post<AuthResponse>('/auth/doctor', { doctor_id: doctorId }, undefined, signal),

  loginStaff: (name: string, signal?: AbortSignal) =>
    post<AuthResponse>('/auth/staff', { name }, undefined, signal),

  me: (token: string, signal?: AbortSignal) => get<ActorResponse>('/auth/me', token, signal),

  logout: (token: string) => post<void>('/auth/logout', {}, token),

  doctors: (token: string, signal?: AbortSignal) => get<Doctor[]>('/doctors', token, signal),

  slots: (token: string, doctorId: string, appointmentDate: string, visitType: VisitType, signal?: AbortSignal) =>
    get<SlotAvailability>(
      `/slots?doctor_id=${encodeURIComponent(doctorId)}&appointment_date=${appointmentDate}&visit_type=${visitType}`,
      token,
      signal,
    ),

  patientAppointments: (token: string, signal?: AbortSignal) =>
    get<Appointment[]>('/appointments', token, signal),

  bookAsPatient: (token: string, payload: AppointmentRequest, signal?: AbortSignal) =>
    post<Appointment & { emergency?: string; urgent_case_id?: string | null }>('/appointments', payload, token, signal),

  cancelAppointment: (token: string, appointmentId: string, signal?: AbortSignal) =>
    post<Appointment | ToStaffResponse>(`/appointments/${encodeURIComponent(appointmentId)}/cancel`, {}, token, signal),

  rescheduleAppointment: (
    token: string,
    appointmentId: string,
    payload: { doctor_id: string; date: string; start_time: string },
    signal?: AbortSignal,
  ) =>
    post<Appointment | ToStaffResponse>(
      `/appointments/${encodeURIComponent(appointmentId)}/reschedule`,
      payload,
      token,
      signal,
    ),

  staffApprovals: (token: string, signal?: AbortSignal) =>
    get<StaffApprovalRequest[]>('/staff/approvals', token, signal),

  approveApproval: (token: string, requestId: string, signal?: AbortSignal) =>
    post<StaffApprovalRequest>(`/staff/approvals/${encodeURIComponent(requestId)}/approve`, {}, token, signal),

  rejectApproval: (token: string, requestId: string, signal?: AbortSignal) =>
    post<StaffApprovalRequest>(`/staff/approvals/${encodeURIComponent(requestId)}/reject`, {}, token, signal),

  staffPatients: (token: string, signal?: AbortSignal) =>
    get<PatientSummary[]>('/staff/patients', token, signal),

  staffAppointments: (token: string, date?: string, doctorId?: string, signal?: AbortSignal) => {
    const params = new URLSearchParams()
    if (date) params.set('appointment_date', date)
    if (doctorId) params.set('doctor_id', doctorId)
    const query = params.toString()
    return get<Appointment[]>(`/staff/appointments${query ? `?${query}` : ''}`, token, signal)
  },

  bookAsStaff: (token: string, payload: StaffAppointmentRequest, signal?: AbortSignal) =>
    post<Appointment & { emergency?: string; urgent_case_id?: string | null }>(
      '/staff/appointments',
      payload,
      token,
      signal,
    ),

  doctorAppointments: (token: string, appointmentDate: string, signal?: AbortSignal) =>
    get<Appointment[]>(`/doctor/appointments?appointment_date=${appointmentDate}`, token, signal),

  completeAppointment: (token: string, appointmentId: string, doctorNote: string, signal?: AbortSignal) =>
    post<Appointment>(`/appointments/${encodeURIComponent(appointmentId)}/complete`, { doctor_note: doctorNote }, token, signal),

  factOfTheDay: (token: string, previous?: string, signal?: AbortSignal) =>
    get<FactResponse>(
      `/fact-of-the-day${previous ? `?previous=${encodeURIComponent(previous)}` : ''}`,
      token,
      signal,
    ),

  urgentCases: (token: string, signal?: AbortSignal) =>
    get<UrgentCase[]>('/urgent-cases', token, signal),

  markUrgentSeen: (token: string, urgentId: string, signal?: AbortSignal) =>
    post<UrgentCase>(`/urgent-cases/${encodeURIComponent(urgentId)}/seen`, {}, token, signal),

  patientHistory: (token: string, patientId: string, signal?: AbortSignal) =>
    get<PatientHistoryItem[]>(`/doctor/patients/${encodeURIComponent(patientId)}/history`, token, signal),

  appointmentSummary: (token: string, appointmentId: string, signal?: AbortSignal) =>
    get<DoctorSummary>(`/doctor/appointments/${encodeURIComponent(appointmentId)}/summary`, token, signal),

  chat: (token: string, threadId: string, message?: string, confirm?: boolean, signal?: AbortSignal) =>
    post<ChatReply>(
      '/chat',
      { thread_id: threadId, ...(message !== undefined ? { message } : {}), ...(confirm !== undefined ? { confirm } : {}) },
      token,
      signal,
    ),

  searchDebug: (token: string, query: string, signal?: AbortSignal) =>
    get<SearchDebugResponse>(`/staff/search-debug?q=${encodeURIComponent(query)}`, token, signal),
}
