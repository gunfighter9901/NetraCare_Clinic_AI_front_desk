# appointment-management Specification

## Purpose

Provides safe appointment availability, booking, cancellation, and visit completion while making the backend's clinic rules authoritative for every role.

## Requirements

### Requirement: Generate bookable free slots
For a doctor, date, and visit type, the system SHALL return available start times on 10-minute marks. New consultations SHALL occupy 20 minutes and follow-ups 10 minutes. Slots SHALL respect the booking window, clinic calendar, OPD session, session end, and overlapping booked appointments.

#### Scenario: Surgery session has no free slots
- **WHEN** free slots are requested for Dr. Rao on a Thursday morning
- **THEN** no morning start times are offered because that session is SURGERY

#### Scenario: Booked time disappears
- **WHEN** a Patient successfully books a returned start time and requests the same doctor, date, and visit type again
- **THEN** any newly conflicting start time is no longer returned

#### Scenario: No suitable availability
- **WHEN** no suitable slot is free for the requested search
- **THEN** the system returns an empty availability result with a clear no-slot message rather than offering unavailable times

### Requirement: Enforce valid start times and booking window
Booking SHALL refuse start times not on a 10-minute mark, appointments before the clinic clock, and appointments more than 30 calendar days after it. Exactly 30 days ahead SHALL remain allowed.

#### Scenario: Invalid start mark
- **WHEN** a booking starts at 09:05
- **THEN** it is refused with reason code INVALID_START_TIME

#### Scenario: Past or excessive future date
- **WHEN** a booking is before the clinic clock or 31 days ahead
- **THEN** it is refused with IN_PAST or BEYOND_30_DAYS respectively

#### Scenario: Exact booking-window boundary
- **WHEN** an otherwise valid booking is exactly 30 days after the clinic clock's date
- **THEN** the booking-window rule allows it

### Requirement: Enforce clinic hours and session boundaries
The system SHALL refuse bookings on Sundays, listed holidays, outside 09:00–13:00 or 14:00–18:00, and bookings whose duration ends after their session. Appointments ending exactly at 13:00 or 18:00 SHALL be allowed.

#### Scenario: Clinic is closed
- **WHEN** a booking is requested on a Sunday or a date in `holidays.csv`
- **THEN** it is refused with CLINIC_CLOSED or HOLIDAY respectively

#### Scenario: Outside a session
- **WHEN** a booking starts before 09:00, during 13:00–14:00, or at or after 18:00
- **THEN** it is refused with OUTSIDE_SESSION

#### Scenario: Appointment crosses session end
- **WHEN** a new consultation starts at 12:50 or 17:50
- **THEN** it is refused with ENDS_AFTER_SESSION

#### Scenario: Appointment ends exactly at session end
- **WHEN** a new consultation starts at 12:40 or 17:40 in an OPD session
- **THEN** the duration and session-boundary rules allow it

### Requirement: Enforce doctor schedule and speciality
The system SHALL refuse booking when the selected doctor is OFF, in SURGERY, or does not cover the requested speciality for that session.

#### Scenario: Doctor is off
- **WHEN** a Patient requests Dr. Iyer on a Thursday
- **THEN** the booking is refused with DOCTOR_OFF and a message explaining that she is not at the clinic on Thursdays

#### Scenario: Doctor is operating
- **WHEN** a Patient requests Dr. Rao on Thursday morning
- **THEN** the booking is refused with SURGERY_SESSION

#### Scenario: Speciality mismatch
- **WHEN** a Patient requests Glaucoma with Dr. Khan
- **THEN** the booking is refused with SPECIALITY_MISMATCH

### Requirement: Prevent overlapping doctor appointments
The backend SHALL refuse a new booking that overlaps any booked appointment for the same doctor, using start-inclusive and end-exclusive intervals. Identical starts and partial overlaps SHALL both be refused, while adjacent appointments SHALL be allowed.

#### Scenario: Same start time
- **WHEN** another Patient requests a doctor's already booked 09:00 start
- **THEN** the booking is refused with DOUBLE_BOOKED

#### Scenario: Partial overlap
- **WHEN** a requested appointment would overlap part of a booked 09:00–09:20 consultation
- **THEN** it is refused with DOUBLE_BOOKED

#### Scenario: Adjacent appointments
- **WHEN** one appointment ends exactly when another begins
- **THEN** the overlap rule does not refuse the second appointment

### Requirement: Limit active bookings per patient speciality
Each patient SHALL have at most one booked appointment in a given speciality at a time, regardless of doctor or visit type. Cancelled and completed appointments SHALL NOT count as active.

#### Scenario: Duplicate active speciality
- **WHEN** a Patient with a booked Cataract appointment requests another Cataract appointment
- **THEN** it is refused with ACTIVE_BOOKING_EXISTS

#### Scenario: Different speciality
- **WHEN** the same Patient requests an otherwise valid appointment in a different speciality
- **THEN** the active-booking rule allows it

### Requirement: Enforce follow-up eligibility
A follow-up SHALL require a completed visit in the requested speciality and SHALL use the doctor from the patient's latest completed visit in that speciality. Completed visits SHALL include data pack 2 past visits in addition to visits completed in the app. New consultations SHALL remain available when no such visit exists.

#### Scenario: No previous visit
- **WHEN** a Patient with no completed visit in a speciality requests a follow-up
- **THEN** it is refused with NO_PREVIOUS_VISIT

#### Scenario: Different doctor
- **WHEN** a Patient whose latest Cataract visit was completed by Dr. Rao requests a Cataract follow-up with Dr. Iyer
- **THEN** it is refused with FOLLOW_UP_DIFFERENT_DOCTOR

#### Scenario: Correct follow-up doctor
- **WHEN** that Patient requests an otherwise valid Cataract follow-up with Dr. Rao
- **THEN** it is allowed and occupies 10 minutes

#### Scenario: Past-visit history enables Retina follow-up
- **WHEN** Asha Verma (P01) requests a Retina follow-up with Dr. Shah after data pack 2 loading
- **THEN** the follow-up rule allows it based on her completed Retina history with Dr. Shah

### Requirement: Book for Patients and Staff
The backend SHALL allow Patients to book for their authenticated identity and Staff to book for any existing patient. Staff SHALL also be able to create a synthetic walk-in patient from name and mobile before booking. Every booking SHALL provide a trimmed non-empty reason of at most 300 characters, run the red-flag safety check before clinic-rule evaluation, and carry Urgent tagging when the reason is a red flag. Staff MUST NOT bypass other booking rules.

#### Scenario: Staff books an existing patient
- **WHEN** Staff selects a patient and submits an otherwise valid appointment
- **THEN** the appointment is booked for that patient

#### Scenario: Staff books a walk-in
- **WHEN** Staff supplies a new mobile number and patient name with a valid appointment
- **THEN** the system creates the patient and books the appointment for that patient

#### Scenario: Staff submits an invalid booking
- **WHEN** Staff requests a time or speciality that breaks a clinic booking rule
- **THEN** the same refusal and reason code apply as for a Patient booking

#### Scenario: Booking without a reason is refused
- **WHEN** a Patient or Staff submits a booking without a reason, with only whitespace, or with more than 300 characters
- **THEN** the booking is refused without running the red-flag check or creating an appointment

#### Scenario: Red-flag booking preserves urgency through rule refusal
- **WHEN** a red-flag reason passes reason validation but fails a clinic rule such as a surgery session
- **THEN** the emergency response is shown first, the booking is refused with the applicable clinic reason code, and the urgent case remains

### Requirement: Apply cancellation cutoff by role
Patients SHALL cancel their own booked appointments until two hours before start. Inside two hours, the system SHALL create a Staff approval request and return `to_staff` with `INSIDE_2_HOURS`; the appointment SHALL remain booked. Staff SHALL cancel any booked appointment directly. Inactive appointments SHALL return NOT_ACTIVE.

#### Scenario: Patient cancels before cutoff
- **WHEN** a Patient cancels their booked appointment two hours or more before it starts
- **THEN** the appointment becomes cancelled and no approval request is created

#### Scenario: Patient cancels inside cutoff
- **WHEN** a Patient cancels their booked appointment less than two hours before start
- **THEN** one pending approval request is saved, the response is `to_staff` with `INSIDE_2_HOURS`, and the appointment remains booked

#### Scenario: Staff cancels inside cutoff
- **WHEN** Staff cancels that same booked appointment directly rather than through an approval request
- **THEN** the appointment becomes cancelled

#### Scenario: Appointment already inactive
- **WHEN** cancellation targets a completed or already cancelled appointment
- **THEN** it is refused with NOT_ACTIVE and no approval request is created
### Requirement: Release cancelled appointment capacity
A cancelled appointment SHALL stop blocking doctor availability and SHALL NOT count as an active booking for the patient.

#### Scenario: Cancelled slot is booked by someone else
- **WHEN** an appointment is cancelled and another Patient requests the same otherwise valid time
- **THEN** the new booking can succeed and the cancelled record remains unchanged

### Requirement: Provide Doctor schedules and completion
Doctors SHALL view their own appointments for a chosen day with patient, time, speciality, visit type, and status. A Doctor SHALL mark their own booked visit completed; completion SHALL make it eligible for the follow-up rules and inactive for cancellation. Completion SHALL require a trimmed non-empty doctor note saved with the appointment and visible in patient history. Schedules SHALL show each appointment's reason and Urgent tag where applicable.

#### Scenario: Doctor views a day
- **WHEN** Dr. Rao selects a date
- **THEN** his schedule lists his appointments chronologically with the patient and visit details

#### Scenario: Doctor completes a visit
- **WHEN** Dr. Rao marks his booked Cataract appointment completed
- **THEN** its status becomes completed and that Patient may book a Cataract follow-up with Dr. Rao but not Dr. Iyer

#### Scenario: Completion without a note is refused
- **WHEN** a doctor attempts to mark a booked visit completed with an empty or whitespace-only note
- **THEN** the completion is refused and the appointment remains booked

#### Scenario: Saved note appears in history
- **WHEN** a doctor completes a visit with a valid note
- **THEN** the saved note appears in that patient's completed history and future summaries

### Requirement: Return stable refusal results
Every booking, cancellation, and reschedule SHALL be decided on the backend through the shared rule path. A refusal SHALL leave appointment data unchanged and include the applicable reason code and plain-words message. A valid late Patient action SHALL return `to_staff` rather than being represented as an executed action or ordinary refusal.

#### Scenario: API caller bypasses the browser
- **WHEN** a caller submits an invalid booking, cancellation, or reschedule directly to the API
- **THEN** the backend returns the same outcome and reason code as the equivalent browser or agent attempt

#### Scenario: Red-flag check failure leaves state unchanged
- **WHEN** the red-flag check fails and the booking is refused with the retry message
- **THEN** no appointment, urgent-case side effects beyond the mandated refusal, or walk-in patient persist from that attempt
### Requirement: Satisfy the selected deterministic rule suite
With the clinic clock fixed at 2026-11-02 10:00 and the required fresh data-pack seed for each case, the system SHALL produce the expected outcome and reason code for T01–T38. T32 and T37 SHALL produce `to_staff` with a pending request rather than an ordinary refusal.

#### Scenario: Selected data-pack cases execute independently
- **WHEN** each case T01 through T38 runs against its fresh data-pack state
- **THEN** its allowed, refused, rescheduled, or `to_staff` outcome and nonempty expected reason code match the CSV, and refused reschedules preserve the original appointment

### Requirement: Reschedule appointments atomically
The system SHALL validate a replacement with the original excluded from overlap and active-speciality checks, then cancel the original and create the replacement in one transaction. Ownership, follow-up, schedule, duration, and booking-window rules SHALL remain authoritative.

#### Scenario: Replacement passes all rules
- **WHEN** a Patient reschedules their booked appointment to an otherwise valid doctor, date, and start time
- **THEN** the original becomes cancelled and one replacement is booked with the original speciality, visit type, reason, and urgency metadata

#### Scenario: Original does not block its own replacement
- **WHEN** an otherwise valid replacement overlaps the original or remains in the same Patient speciality
- **THEN** the original is excluded from those two checks while every other appointment and rule still applies

#### Scenario: Replacement is refused
- **WHEN** the replacement violates a clinic rule or cannot be persisted
- **THEN** the entire reschedule is rolled back, the original remains booked exactly as before, and no replacement remains
### Requirement: Persist late-action approval requests
The system SHALL save a pending request for an otherwise actionable Patient cancellation or reschedule inside two hours. It SHALL store the requested action and any reschedule target, return `to_staff`, keep the original booked, and allow at most one pending request per appointment.

#### Scenario: Late reschedule creates one request
- **WHEN** a Patient confirms a late reschedule whose replacement currently passes all non-cutoff rules
- **THEN** the original remains booked and one pending request containing the replacement doctor, date, and start is returned as `to_staff`

#### Scenario: Invalid late reschedule is not queued
- **WHEN** a late reschedule's replacement violates another clinic rule
- **THEN** that rule refusal is returned, no approval request is created, and the original remains unchanged

#### Scenario: Duplicate pending request is prevented
- **WHEN** a Patient requests another late action for an appointment that already has a pending request
- **THEN** no second request is created and the existing request and appointment remain unchanged
### Requirement: Decide Staff approval requests
Staff SHALL list and decide pending requests. Approval SHALL revalidate and execute the stored action as Staff in one transaction; rejection SHALL only mark the request rejected. Staff SHALL bypass the Patient cutoff but no other appointment rule.

#### Scenario: Staff approves a late cancellation
- **WHEN** Staff approves a pending cancellation for an appointment that is still booked
- **THEN** the appointment becomes cancelled and the request becomes approved in the same successful outcome

#### Scenario: Staff approves a late reschedule
- **WHEN** Staff approves a pending reschedule whose target is still valid
- **THEN** the original is cancelled, the replacement is booked, and the request is approved atomically

#### Scenario: Approval target has become invalid
- **WHEN** Staff approves a request whose original is no longer booked or whose target now breaks a rule
- **THEN** the refusal is returned, the request remains pending, and no appointment changes are committed

#### Scenario: Staff rejects a request
- **WHEN** Staff rejects a pending cancellation or reschedule
- **THEN** the request becomes rejected and the original appointment remains booked and unchanged

#### Scenario: Request is decided twice
- **WHEN** an approve or reject operation targets a request that is no longer pending
- **THEN** the operation is refused without repeating the appointment action or changing the recorded decision
### Requirement: Expose own approval request status
Patient appointment results SHALL include the latest Staff request action and status for that appointment. Patients SHALL receive request information only for their own appointments, and availability or appointment tools SHALL identify requests awaiting Staff.

#### Scenario: Patient sees a pending late action
- **WHEN** a Patient views an appointment with a pending Staff request
- **THEN** its booked status remains visible together with the requested action and pending approval status

#### Scenario: Patient sees the Staff decision
- **WHEN** Staff approves or rejects a Patient's request and the Patient views their appointments again
- **THEN** the corresponding approved or rejected request status is visible without exposing another Patient's requests
