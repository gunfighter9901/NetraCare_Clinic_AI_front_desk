# doctor-summary Specification

## Purpose

Helps doctors review a patient quickly by summarizing only recorded history and today's reason, with full notes always visible for verification.

## Requirements

### Requirement: Restrict summaries to the scheduled doctor
The system SHALL allow summary retrieval only for an authenticated doctor and only for an appointment on that doctor's own schedule, refusing patients and other doctors even on direct API calls.

#### Scenario: Patient calls summary directly
- **WHEN** an authenticated patient calls the summary endpoint for any appointment
- **THEN** the request is refused and no summary or other patient's notes are disclosed

#### Scenario: Doctor opens own scheduled patient
- **WHEN** Dr. Iyer opens Lakshmi Nair from an appointment on Dr. Iyer's schedule
- **THEN** the system returns a summary tied to that appointment's reason

### Requirement: Summarize only recorded information within 120 words
The summary SHALL use only the patient profile, calculated age when available, today's appointment reason, and completed visits from all doctors newest first, in no more than 120 words, and SHALL be labeled "AI summary of recorded notes. Check the notes below." with full notes shown underneath.

#### Scenario: Glaucoma history is restated without added advice
- **WHEN** Dr. Iyer opens Lakshmi Nair booked for Glaucoma follow-up
- **THEN** the summary includes today's reason, glaucoma on latanoprost attributed to Dr. Iyer, early cataract attributed to Dr. Rao, and her sulfa allergy, and adds no diagnosis, risk, or advice beyond the notes

#### Scenario: Asthma-related prescribing context is preserved
- **WHEN** Dr. Iyer opens Sunita Rao with an asthma profile and a latanoprost note stating timolol was avoided because of asthma
- **THEN** the summary repeats that latanoprost was started and timolol avoided because of asthma, without adding warnings or advice

#### Scenario: Patient without history states no previous visits
- **WHEN** a doctor opens Aditya Bose who has no past visits
- **THEN** the summary says there are no previous visits on record and invents nothing

### Requirement: Fall back safely when summary generation is unavailable
The system SHALL return "Summary unavailable. See the notes below." with the full notes when the LLM call fails or no API key is configured.

#### Scenario: Missing key still shows notes
- **WHEN** the backend restarts without an API key and a doctor opens a scheduled patient
- **THEN** the summary area shows the fallback message and the complete past notes remain visible
