import type {
  ActorResponse,
  Appointment,
  AppointmentRequest,
  AuthResponse,
  ChatReply,
  Doctor,
  DoctorOption,
  DoctorSummary,
  FactResponse,
  PatientHistoryItem,
  PatientSummary,
  SearchDebugResponse,
  SlotAvailability,
  StaffApprovalRequest,
  StaffAppointmentRequest,
  ToStaffResponse,
  UrgentCase,
} from './types'

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

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

async function request<T>(path: string, method = 'GET', payload?: unknown, token?: string): Promise<T> {
  const headers: Record<string, string> = {}
  if (payload !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: payload === undefined ? undefined : JSON.stringify(payload),
  })

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

function withToken(token: string | null) {
  return token ?? ''
}

export const api = {
  doctorOptions: () => request<DoctorOption[]>('/auth/doctor-options'),

  loginPatient: (mobile: string, name: string) =>
    request<AuthResponse>('/auth/patient', 'POST', { mobile, name }),

  loginDoctor: (doctorId: string) =>
    request<AuthResponse>('/auth/doctor', 'POST', { doctor_id: doctorId }),

  loginStaff: (name: string) => request<AuthResponse>('/auth/staff', 'POST', { name }),

  me: (token: string) => request<ActorResponse>('/auth/me', 'GET', undefined, token),

  logout: (token: string) => request<void>('/auth/logout', 'POST', {}, token),

  doctors: (token: string) => request<Doctor[]>('/doctors', 'GET', undefined, token),

  slots: (
    token: string,
    doctorId: string,
    appointmentDate: string,
    visitType: 'new' | 'follow_up',
  ) =>
    request<SlotAvailability>(
      `/slots?doctor_id=${encodeURIComponent(doctorId)}&appointment_date=${appointmentDate}&visit_type=${visitType}`,
      'GET',
      undefined,
      token,
    ),

  patientAppointments: (token: string) =>
    request<Appointment[]>('/appointments', 'GET', undefined, token),

  bookAsPatient: (token: string, payload: AppointmentRequest) =>
    request<Appointment & { emergency?: string; urgent_case_id?: string | null }>(
      '/appointments',
      'POST',
      payload,
      token,
    ),

  cancelAppointment: (token: string, appointmentId: string) =>
    request<Appointment | ToStaffResponse>(`/appointments/${appointmentId}/cancel`, 'POST', {}, token),

  rescheduleAppointment: (token: string, appointmentId: string, payload: { doctor_id: string; date: string; start_time: string }) =>
    request<Appointment | ToStaffResponse>(`/appointments/${appointmentId}/reschedule`, 'POST', payload, token),

  staffApprovals: (token: string) =>
    request<StaffApprovalRequest[]>('/staff/approvals', 'GET', undefined, token),

  approveApproval: (token: string, requestId: string) =>
    request<StaffApprovalRequest>(`/staff/approvals/${requestId}/approve`, 'POST', {}, token),

  rejectApproval: (token: string, requestId: string) =>
    request<StaffApprovalRequest>(`/staff/approvals/${requestId}/reject`, 'POST', {}, token),

  staffPatients: (token: string) => request<PatientSummary[]>('/staff/patients', 'GET', undefined, token),

  staffAppointments: (token: string, date?: string, doctorId?: string) => {
    const params = new URLSearchParams()
    if (date) params.set('appointment_date', date)
    if (doctorId) params.set('doctor_id', doctorId)
    const query = params.toString()
    return request<Appointment[]>(
      `/staff/appointments${query ? `?${query}` : ''}`,
      'GET',
      undefined,
      token,
    )
  },

  bookAsStaff: (token: string, payload: StaffAppointmentRequest) =>
    request<Appointment & { emergency?: string; urgent_case_id?: string | null }>(
      '/staff/appointments',
      'POST',
      payload,
      token,
    ),

  doctorAppointments: (token: string, appointmentDate: string) =>
    request<Appointment[]>(
      `/doctor/appointments?appointment_date=${appointmentDate}`,
      'GET',
      undefined,
      token,
    ),

  completeAppointment: (token: string, appointmentId: string, doctorNote: string) =>
    request<Appointment>(`/appointments/${appointmentId}/complete`, 'POST', { doctor_note: doctorNote }, token),

  factOfTheDay: (token: string, previous?: string) =>
    request<FactResponse>(
      `/fact-of-the-day${previous ? `?previous=${encodeURIComponent(previous)}` : ''}`,
      'GET',
      undefined,
      token,
    ),

  urgentCases: (token: string) => request<UrgentCase[]>('/urgent-cases', 'GET', undefined, token),

  markUrgentSeen: (token: string, urgentId: string) =>
    request<UrgentCase>(`/urgent-cases/${urgentId}/seen`, 'POST', {}, token),

  patientHistory: (token: string, patientId: string) =>
    request<PatientHistoryItem[]>(`/doctor/patients/${patientId}/history`, 'GET', undefined, token),

  appointmentSummary: (token: string, appointmentId: string) =>
    request<DoctorSummary>(`/doctor/appointments/${appointmentId}/summary`, 'GET', undefined, token),

  chat: (token: string, threadId: string, message?: string, confirm?: boolean) =>
    request<ChatReply>('/chat', 'POST', { thread_id: threadId, ...(message !== undefined ? { message } : {}), ...(confirm !== undefined ? { confirm } : {}) }, token),

  searchDebug: (token: string, query: string) =>
    request<SearchDebugResponse>(`/staff/search-debug?q=${encodeURIComponent(query)}`, 'GET', undefined, token),
}

export const authToken = withToken
