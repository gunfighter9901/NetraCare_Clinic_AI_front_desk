# red-flag-safety Specification

## Purpose

Detects urgent eye symptoms in booking reasons, blocks silent booking on uncertainty, and tracks urgent cases for Staff follow-up.

## Requirements

### Requirement: Classify booking reasons into red-flag categories
The system SHALL evaluate every booking reason with the `check_red_flags` chain before clinic-rule checks, returning structured `red_flag`, `category`, and `why` with temperature 0. It SHALL treat current or very recent acute episodes as red flags, including transient loss that has recovered.

#### Scenario: Each mandated red-flag wording triggers emergency handling
- **WHEN** a booking reason is "I suddenly can't see from my left eye", "It feels like a curtain is coming down over my right eye", "Seeing flashes of light and lots of floaters since yesterday", "Got floor cleaner in my eye while mopping", or "Severe eye pain with headache and I feel sick"
- **THEN** the result is `red_flag true` with the matching category `sudden_vision_loss`, `curtain_or_shadow`, `floaters_or_flashes`, `chemical_or_injury`, or `severe_pain_headache_haloes` respectively

#### Scenario: Non-urgent and negated wordings do not flag
- **WHEN** a booking reason is "Routine eye test and new glasses", "No sudden loss of vision but I want a check-up", or "Gradual loss of vision over two years"
- **THEN** the result is `red_flag false` with category none

#### Scenario: Uncertain wording defaults to urgent
- **WHEN** the reason is ambiguous about whether it matches a red-flag category
- **THEN** the system flags it as a red flag rather than allowing silent booking

### Requirement: Fail closed when the red-flag check cannot complete
The system SHALL refuse the booking when the red-flag call times out, errors, or returns unparsable output, creating no appointment and no walk-in patient.

#### Scenario: Red-flag service failure blocks booking
- **WHEN** the red-flag check fails during a Patient or Staff booking attempt
- **THEN** the booking is refused with "We couldn't check your reason just now. Please try again, or call the clinic if it's urgent." and no appointment or patient record is created

### Requirement: Persist urgent cases independently of booking outcome
The system SHALL save an urgent case with patient identity or walk-in snapshot, reason text, category, model reason, and timestamp before running clinic-rule checks, and SHALL retain it whether the booking is allowed or refused.

#### Scenario: Red flag with refused clinic rule still leaves urgent case
- **WHEN** a red-flag reason is booked with Dr. Rao on a Thursday morning surgery session
- **THEN** the screen shows the emergency response first, the booking is refused by the surgery rule, and an urgent case with the correct category remains at the top of the Staff view

#### Scenario: Red-flag walk-in without an existing patient is retained safely
- **WHEN** Staff books a red-flag reason for a new walk-in mobile and the clinic-rule check refuses it
- **THEN** the urgent case is retained with name and mobile snapshots while no new patient record is retained

### Requirement: Acknowledge urgent cases without erasing history
The system SHALL list unseen urgent cases first in Staff view in red until Staff marks them seen, and SHALL retain the Urgent tag on an already booked appointment after acknowledgement.

#### Scenario: Staff marks an urgent case seen
- **WHEN** Staff marks an unseen urgent case as seen
- **THEN** it leaves the urgent list while any appointment booked from it keeps its Urgent tag

### Requirement: Check every Patient chat message before answering
After request validation, the system SHALL run existing red-flag classification on each original typed chat message before agent reasoning, retrieval, answer generation, or any new appointment operation. A red flag SHALL stop that message's workflow with the existing emergency response and no sources.

#### Scenario: Chat red flag produces only emergency handling
- **WHEN** a Patient sends "A curtain came down over my left eye an hour ago"
- **THEN** the exact emergency response is shown in red, one matching urgent case is saved, and no agent, search, grounded answer, or appointment action occurs

#### Scenario: Non-red-flag message continues safely
- **WHEN** the original typed chat message is classified as non-urgent
- **THEN** the tool-calling agent or grounded-answer workflow may continue

#### Scenario: Red-flag message arrives during pending confirmation
- **WHEN** a Patient types a red-flag message while an earlier mutation awaits confirmation
- **THEN** the earlier action is declined without mutation and the new message produces only emergency handling, one urgent case, and no tool calls

#### Scenario: Card response is not a typed message
- **WHEN** a Patient sends only `confirm=true` or `confirm=false` for a pending action
- **THEN** the stored action resumes without classifying the card response as new clinical text
### Requirement: Fail closed when chat safety cannot be checked
When red-flag classification of a typed chat message times out, errors, or cannot be parsed, the system SHALL return "We couldn't check your message just now. Please try again, or call the clinic if it's urgent." and SHALL NOT answer or perform later chat steps.

#### Scenario: Missing chat-model configuration fails at the safety step
- **WHEN** a Patient sends an otherwise valid typed message while the safety chain is unavailable
- **THEN** the exact chat safety failure message appears and no agent, retrieval, answer, urgent case, appointment, or approval request is produced

#### Scenario: Safety fails after an earlier action is declined
- **WHEN** classification fails for a typed message that replaced a pending confirmation
- **THEN** the pending mutation has not executed and the new message produces only the exact safety failure response

#### Scenario: Booking failure wording remains unchanged
- **WHEN** the safety chain fails during an existing booking workflow
- **THEN** the booking retains its established "couldn't check your reason" behavior rather than using the chat message wording
### Requirement: Record urgent-case provenance and complete chat text
Urgent cases SHALL distinguish `booking` from `chat` origin. A chat-origin case SHALL retain the authenticated Patient snapshot, original message up to 500 characters without truncation, category, model rationale, and timestamp; existing booking cases SHALL retain their prior behavior and be backfilled as `booking`.

#### Scenario: Chat urgent case is Staff-visible
- **WHEN** a red-flag chat message creates an urgent case
- **THEN** the unseen case records `chat` origin and the complete original message and appears through the existing Staff triage and acknowledgement workflow

#### Scenario: Existing database is upgraded additively
- **WHEN** an existing database containing booking urgent cases is migrated
- **THEN** prior cases and appointment links remain intact, their origin becomes `booking`, and no chat or appointment history is invented

#### Scenario: Chat urgency does not require an appointment
- **WHEN** a red-flag chat workflow ends with the emergency response
- **THEN** the chat-origin urgent case persists without creating an appointment or Urgent appointment tag
