# clinic-data Specification

## Purpose

Provides the trusted synthetic clinic directory, calendar, and patient records used by every role and by appointment rule evaluation.

## Requirements

### Requirement: Load the Iteration 1 data pack
The system SHALL load doctors, weekly schedules, holidays, and patients from the four supplied CSV files, preserving their source identifiers and values. Data pack 2 SHALL be loaded additionally in normal startup without modifying the supplied CSVs. Repeated loading MUST NOT duplicate records or erase appointments.

#### Scenario: Initial data load
- **WHEN** the application initializes with an empty database
- **THEN** it contains 5 doctors, 60 weekly schedule rows, 30 holidays, and 25 patients, with no appointments

#### Scenario: Repeated data load
- **WHEN** the loader runs again after appointments have been created
- **THEN** reference records remain unique and existing appointments remain unchanged

#### Scenario: Full startup includes completed history
- **WHEN** the application initializes with an empty database and loads both data packs
- **THEN** it contains the Iteration 1 reference records plus 27 completed past visits, profiles for all 25 patients, and no booked appointments

### Requirement: Expose the doctor directory
The system SHALL provide each doctor's identifier, name, and complete speciality list from `doctors.csv` for role-appropriate booking and login workflows.

#### Scenario: Patient views all doctors
- **WHEN** Asha Verma views the doctor directory after logging in
- **THEN** all five doctors appear with the specialities assigned to them in the data pack

### Requirement: Provide the clinic calendar
The system SHALL make weekly OPD, SURGERY, and OFF sessions and listed holiday dates available to slot and booking decisions. Only OPD sessions SHALL be bookable.

#### Scenario: Non-OPD sessions retain their meaning
- **WHEN** scheduling rules inspect Dr. Rao on Thursday morning or Dr. Iyer on Thursday
- **THEN** Dr. Rao's morning is represented as SURGERY and both of Dr. Iyer's sessions are represented as OFF

#### Scenario: Listed clinic holiday
- **WHEN** scheduling rules inspect 2026-11-09
- **THEN** that date is identified as a clinic holiday and is not bookable

### Requirement: Restrict records to synthetic patient data
The system SHALL initialize patient identities only from the supplied synthetic patient data and SHALL support new synthetic patient records created through the allowed login or Staff walk-in workflows.

#### Scenario: Existing synthetic patient
- **WHEN** the system looks up mobile number 9000000001
- **THEN** it resolves Asha Verma with patient identifier P01 and year of birth 1958

### Requirement: Load data pack 2 past visits as completed history
The system SHALL load every `past_visits.csv` row as a completed appointment preserving visit, patient, doctor, speciality, visit type, date, times, reason, and doctor note, without blocking future bookings.

#### Scenario: Asha Verma history supports follow-up checks
- **WHEN** data pack 2 is loaded
- **THEN** Asha Verma (P01) has 3 completed visits with Dr. Shah and Dr. Rao and can book a Retina follow-up with Dr. Shah

### Requirement: Load patient health profiles for summary context
The system SHALL load `patient_profiles.csv` general health and allergies for all 25 patients and make them available for doctor summaries, tolerating missing profiles for newly created patients.

#### Scenario: Profiles cover all seeded patients
- **WHEN** data pack 2 is loaded
- **THEN** every patient P01 through P25 has general-health and allergy values available for summary prompts
