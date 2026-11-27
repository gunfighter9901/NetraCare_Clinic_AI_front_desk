# clinic-access Specification

## Purpose

Establishes the three classroom role identities and ensures every protected operation enforces the caller's role and patient ownership on the backend.

## Requirements

### Requirement: Support simple login for three roles
The system SHALL allow Patient login with mobile number and name, Doctor login by selecting a listed doctor, and Staff login with a nonempty display name, without passwords. An existing mobile with a mismatched patient name SHALL be refused; a new mobile SHALL create a patient.

#### Scenario: Existing patient logs in
- **WHEN** Asha Verma enters mobile 9000000001 and her matching name
- **THEN** she receives a Patient session associated with P01

#### Scenario: New patient logs in
- **WHEN** a person enters a previously unknown mobile number and a nonempty name
- **THEN** the system creates a synthetic patient record and establishes a Patient session for that patient

#### Scenario: Existing mobile has wrong name
- **WHEN** a login uses Asha Verma's mobile number with a different patient name
- **THEN** login is refused and no session is established

#### Scenario: Doctor or Staff logs in
- **WHEN** a Doctor selects their listed name or Staff enters a nonempty display name
- **THEN** the system establishes a session with the corresponding role and identity

### Requirement: Authenticate protected API requests
The backend SHALL determine the authenticated role and actor identity for every protected request. Client-supplied role names or patient identifiers MUST NOT override that identity, and unauthenticated requests SHALL be refused.

#### Scenario: Patient calls a Staff-only operation
- **WHEN** an authenticated Patient requests all appointments or attempts a Staff-only booking action
- **THEN** the backend refuses the operation regardless of any role or patient fields in the request

#### Scenario: Doctor requests another doctor's schedule
- **WHEN** an authenticated Doctor requests a schedule belonging to a different doctor
- **THEN** the backend refuses the request

#### Scenario: Protected request has no session
- **WHEN** a caller invokes a protected appointment operation without a valid session
- **THEN** the backend refuses the request without exposing or changing appointment data

### Requirement: Enforce patient appointment ownership
Patients SHALL see only their own appointment list and details and SHALL act only on their own appointments. This restriction SHALL apply to direct API calls as well as browser workflows.

#### Scenario: Patient lists appointments
- **WHEN** a Patient requests appointments and supplies another patient's identifier
- **THEN** the backend does not use that identifier to disclose records and returns only the authenticated Patient's appointments or refuses the request

#### Scenario: Patient cancels another patient's appointment
- **WHEN** a Patient attempts to cancel an appointment owned by someone else
- **THEN** the backend refuses it with reason code NOT_YOUR_APPOINTMENT and leaves the appointment unchanged
