# clinic-web-portal Specification

## Purpose

Delivers complete browser workflows for Patients, Staff, and Doctors while preserving the backend as the authority for identity, data access, and clinic rules.

## Requirements

### Requirement: Provide role-based login screens
The portal SHALL provide Patient mobile-and-name login, Doctor selection from the doctor list, and Staff name login, then show the workflow appropriate to the authenticated role.

#### Scenario: Each role reaches its workspace
- **WHEN** a user successfully logs in as Patient, Staff, or Doctor
- **THEN** the portal displays that role's appointment workspace without requiring manual API calls

### Requirement: Support the Patient browser workflow
Patients SHALL view doctors and specialities, request free slots, book new consultations or eligible follow-ups, view their own appointments, and cancel eligible appointments from the browser. The booking form SHALL require an appointment reason, and the workspace SHALL show the Fact of the Day card with Refresh and the mandated caveat.

#### Scenario: Patient books an appointment
- **WHEN** a Patient selects a doctor, speciality, visit type, date, and returned free time and confirms booking
- **THEN** the portal creates the appointment through the API and displays it in that Patient's appointment list

#### Scenario: Patient cancels an appointment
- **WHEN** a Patient cancels an eligible appointment from their list
- **THEN** the portal shows its cancelled status and does not offer it as active

#### Scenario: Patient sees and refreshes Fact of the Day
- **WHEN** a patient logs in and clicks Refresh on the Fact card
- **THEN** a fact is shown with "General information, not medical advice", and Refresh shows a different fact with the same caveat

#### Scenario: Patient red-flag booking shows emergency first
- **WHEN** a patient books with a red-flag reason
- **THEN** the portal shows the mandated emergency response in red before any booking or refusal outcome

### Requirement: Support the Staff browser workflow
Staff SHALL view every appointment filtered by day and doctor, book for an existing patient or a new walk-in, and cancel any booked appointment, including one inside the Patient cutoff. Staff booking SHALL collect a reason, the schedule SHALL show reasons and Urgent tags, and unseen urgent cases SHALL appear at the top in red until marked seen.

#### Scenario: Staff reviews the clinic day
- **WHEN** Staff chooses a date and doctor
- **THEN** the portal shows all matching appointments and patient details in time order

#### Scenario: Staff books a walk-in
- **WHEN** Staff enters a new patient's name and mobile and selects a valid free slot
- **THEN** the portal books and displays the appointment for the newly created patient

#### Scenario: Staff performs a late cancellation
- **WHEN** Staff cancels a booked appointment less than two hours before start
- **THEN** the portal shows the appointment as cancelled

#### Scenario: Staff triages and clears an urgent case
- **WHEN** a red-flag booking creates an urgent case and Staff marks it seen
- **THEN** the case appears urgently at the top until acknowledgement and then leaves the urgent list

### Requirement: Support the Doctor browser workflow
Doctors SHALL view their own schedule for a chosen day, see the patient assigned to each appointment, and mark their booked visits completed from the browser. Completion SHALL collect a required doctor note, schedules SHALL show reasons and Urgent tags, and opening a scheduled patient SHALL show the AI summary with its label plus full notes below.

#### Scenario: Doctor completes a booked visit
- **WHEN** a Doctor selects one of their booked appointments and marks it completed
- **THEN** the portal refreshes the schedule with completed status

#### Scenario: Doctor completes a visit with a note and reviews summary
- **WHEN** a doctor enters a note while completing a visit and opens a scheduled patient for a summary
- **THEN** completion succeeds only with a non-empty note, and the patient view shows the labeled AI summary above the complete notes

### Requirement: Present rule refusals in plain words
The portal SHALL display backend refusal messages for failed actions and SHALL NOT represent refused or Staff-pending actions as successful. Hiding invalid options SHALL NOT replace backend enforcement. Red-flag emergencies SHALL retain visual priority, and red-flag failures SHALL show the mandated retry message.

#### Scenario: Doctor is unavailable
- **WHEN** a booking attempt is refused because Dr. Iyer is off on Thursday
- **THEN** the portal displays that Dr. Iyer is not at the clinic on Thursdays and the appointment list remains unchanged

#### Scenario: Late Patient cancellation
- **WHEN** a Patient cancels inside two hours
- **THEN** the portal says the request is waiting for Staff, continues to show the appointment as booked, and does not describe it as cancelled or refused

#### Scenario: Red-flag booking refused by clinic rule
- **WHEN** a red-flag reason is booked into a surgery session
- **THEN** the portal shows the emergency response first and then the clinic-rule refusal without showing a successful booking
### Requirement: Provide a Patient chat browser workflow
The Patient workspace SHALL provide chat for sourced answers, appointment tools, pending-action cards, unsupported responses, and service errors. Emergency responses SHALL have red visual priority. The panel SHALL NOT claim that booking is unsupported.

#### Scenario: Patient has a sourced follow-up conversation
- **WHEN** a Patient asks a clinic document question and then asks a contextual follow-up in the same thread
- **THEN** the panel displays the contextual answer with its current-turn document source below it

#### Scenario: Chat red flag is visually distinct
- **WHEN** the backend returns an emergency response and creates a chat-origin urgent case
- **THEN** the panel shows the exact emergency text in red without sources, a normal answer, or a confirmation card

#### Scenario: Chat service failures use their distinct messages
- **WHEN** safety checking, grounded answering, or the agent step limit fails
- **THEN** the panel displays the corresponding exact backend message and does not show a fabricated answer or successful mutation

#### Scenario: Patient confirms a booking card
- **WHEN** the agent returns a pending action and the Patient selects Confirm
- **THEN** the panel sends only the thread ID and true confirmation, displays the actual outcome, and refreshes affected appointments and availability

#### Scenario: Patient declines a booking card
- **WHEN** the Patient selects No on a pending action
- **THEN** the panel sends only the thread ID and false confirmation, no mutation occurs, and the agent's follow-up response is displayed

#### Scenario: Information accompanies a pending action
- **WHEN** one chat turn returns both a sourced answer and a confirmation card
- **THEN** the panel displays the answer, its sources, and the card together
### Requirement: Clear transient chat state at conversation boundaries
The portal SHALL keep visible chat only in current Patient workspace state and generate a fresh thread ID for New chat, logout/login, and Patient switching. It SHALL NOT restore chat from browser or database storage or submit a previous Patient's pending thread.

#### Scenario: New chat starts empty
- **WHEN** a Patient selects New chat
- **THEN** previous messages and cards disappear and the next request contains a new thread ID with no browser-supplied history

#### Scenario: Logout and login do not restore chat
- **WHEN** a Patient logs out and logs back in
- **THEN** the chat panel is empty and a new thread ID is used

#### Scenario: Another Patient cannot inherit chat history
- **WHEN** the authenticated Patient changes within the same browser
- **THEN** no messages, sources, thread state, or pending action from the prior Patient are displayed or submitted
### Requirement: Provide a Staff search-debug view
The Staff workspace SHALL accept a retrieval query and display keyword-only, vector-only, and hybrid top-four results with file, section, chunk identity, and labeled scores. Retrieval failures SHALL be shown without presenting partial results as complete.

#### Scenario: Staff compares exact and semantic retrieval
- **WHEN** Staff submits the HbA1c and Squint surgery acceptance queries
- **THEN** the three result groups identify the expected sections and expose their respective score semantics

#### Scenario: Search-debug request fails
- **WHEN** any retrieval method needed for the debug view cannot complete
- **THEN** the workspace shows a clear failure state rather than labeling incomplete results as a successful comparison

### Requirement: Show urgent-case origin during Staff triage
The existing Staff urgent-case area SHALL identify whether each case came from `booking` or `chat`, while preserving red priority, complete message visibility, and mark-seen behavior.

#### Scenario: Staff acknowledges a chat-origin case
- **WHEN** Staff opens the urgent area after a red-flag chat and marks the case seen
- **THEN** its chat origin and full message are visible before acknowledgement and it then leaves the unseen urgent list

### Requirement: Provide a Staff approval queue
The Staff workspace SHALL list pending late cancellations and reschedules with Patient, original appointment, and any replacement target. Staff SHALL approve or reject each request from the browser and see the actual backend outcome.

#### Scenario: Staff reviews a pending reschedule
- **WHEN** a Patient has a pending late reschedule
- **THEN** Staff see the original appointment and requested doctor, date, and start together with Approve and Reject actions

#### Scenario: Staff approves a request
- **WHEN** Staff selects Approve and the stored action still passes Staff-applicable rules
- **THEN** the portal displays approval, refreshes requests and affected schedules, and does not repeat the action on a second click

#### Scenario: Staff rejects a request
- **WHEN** Staff selects Reject on a pending request
- **THEN** the portal displays rejection and the appointment remains booked

#### Scenario: Approval cannot complete
- **WHEN** the backend refuses approval because the request or appointment became stale
- **THEN** the portal displays the refusal and does not present the request as approved
### Requirement: Show Staff request status in the Patient workspace
Patient appointment rows SHALL display the requested action and latest Staff approval status alongside the appointment's own status. Chat-driven requests and later Staff decisions SHALL be reflected after the affected Patient data is refreshed.

#### Scenario: Late chat cancellation appears in appointment history
- **WHEN** a Patient confirms a late cancellation in chat and the appointment data refreshes
- **THEN** the appointment remains booked and its row shows that cancellation is pending Staff approval

#### Scenario: Patient reviews a Staff decision
- **WHEN** the Patient loads their appointments after Staff approves or rejects a request
- **THEN** the row shows the corresponding approved or rejected request outcome and the appointment's actual current status
