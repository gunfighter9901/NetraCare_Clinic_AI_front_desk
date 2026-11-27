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

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
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
