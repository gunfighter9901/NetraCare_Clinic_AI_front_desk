# patient-chat Specification

## Purpose

Gives Patients a transient, safety-checked conversation that answers from clinic documents with citations and suggests appropriate specialities without diagnosing or taking appointment actions.

## Requirements

### Requirement: Restrict and bound Patient chat input
The system SHALL allow only authenticated Patients to use chat and derive their identity from the session. A request SHALL contain a nonempty `thread_id` and exactly one of a trimmed 1–500 character `message` or a boolean `confirm`; browser-supplied history SHALL NOT be used.

#### Scenario: Non-Patient calls chat directly
- **WHEN** Staff, a Doctor, or an unauthenticated caller submits a chat request
- **THEN** the system refuses it without running safety classification, the agent, retrieval, or an appointment operation

#### Scenario: Invalid message is refused
- **WHEN** a Patient submits an empty message, one longer than 500 characters, or a request without a valid thread ID
- **THEN** the system refuses the request before red-flag classification, retrieval, or appointment operations

#### Scenario: Invalid request mode is refused
- **WHEN** a request contains both `message` and `confirm`, contains neither, or supplies a non-boolean confirmation
- **THEN** the system refuses it without resuming or starting an agent workflow

#### Scenario: Caller cannot select another identity
- **WHEN** a Patient includes another patient's identifier in a chat request
- **THEN** the system ignores or refuses that identifier and never exposes or changes the other patient's details
### Requirement: Answer document questions with trusted citations
For a document answer, the system SHALL use only the four retrieved chunks, produce at most 120 words, and obtain structured `answer`, `source_ids`, and `answered` fields. The system SHALL build and deduplicate citations from retrieved chunk metadata rather than model-written source text.

#### Scenario: Clinic hours include their source
- **WHEN** a Patient asks "What time does the clinic open on Saturday?"
- **THEN** the answer states 9 AM to 6 PM with lunch closure from 1 to 2 PM and cites `clinic_policy_faq.md` section `Timings`

#### Scenario: Procedure answer includes indicative cost and duration
- **WHEN** a Patient asks about cataract surgery cost and overnight stay
- **THEN** the answer gives the documented indicative range per eye and day-care duration without adding unsupported claims, and cites `procedures.md` section `Cataract surgery`

#### Scenario: Multiple chunks from one section produce one citation
- **WHEN** an answer validly uses multiple chunks sharing a file and section
- **THEN** the displayed sources contain that file-and-section citation only once

### Requirement: Return a fixed response for unsupported answers
The system SHALL replace the model answer with "I don't know. Our clinic documents don't cover that. Please ask Staff at the front desk." and no sources when `answered` is false, `source_ids` is empty, or any cited chunk was not retrieved.

#### Scenario: Documents do not cover parking
- **WHEN** a Patient asks "Is there parking at the clinic?"
- **THEN** the fixed unsupported-answer response appears with no sources

#### Scenario: Model invents a citation
- **WHEN** the structured output names even one chunk ID absent from the four retrieved chunks
- **THEN** the entire answer is replaced by the fixed unsupported-answer response and no citations are shown

#### Scenario: Model declares the context insufficient
- **WHEN** the structured output has `answered` set to false
- **THEN** any supplied answer text or source IDs are ignored in favor of the fixed response

### Requirement: Fail safely when grounded answering is unavailable
When retrieval or grounded answer generation times out, errors, or cannot be parsed, the system SHALL return "Sorry, I can't answer just now. Please try again, or ask Staff at the front desk." without fabricating an answer or citations. Retrieval SHALL be invoked only when document search is requested.

#### Scenario: Retrieval service fails
- **WHEN** hybrid retrieval cannot complete after a successful safety check
- **THEN** the Patient receives the generic chat-unavailable response and no document answer or sources

#### Scenario: Structured answer is invalid
- **WHEN** the answer step returns output that cannot be parsed into the required response structure
- **THEN** the Patient receives the generic chat-unavailable response

#### Scenario: Appointment request does not need retrieval
- **WHEN** a Patient asks only for availability or an appointment change while document retrieval is unavailable
- **THEN** the booking workflow can continue without invoking document search
### Requirement: Route symptoms to documented specialities
When a Patient describes an eye problem, the system SHALL suggest a speciality and name every applicable doctor from `doctors.md`, with a source and a statement that the doctor will assess. Children under 16 SHALL route to Paediatric and unsure Patients to General.

#### Scenario: High-pressure wording routes to Glaucoma
- **WHEN** a Patient says their optician reported high eye pressure
- **THEN** the response suggests Glaucoma, names Dr. Meera Iyer, cites `doctors.md`, and says the doctor will assess without identifying a condition the Patient has

#### Scenario: Child routes to Paediatric
- **WHEN** a Patient describes an eye turn in a five-year-old
- **THEN** the response suggests Paediatric or Squint and names Dr. Vikram Menon without adding a diagnosis

#### Scenario: Supplied routing target is met
- **WHEN** rows R01 through R10 of `routing_samples.csv` are evaluated
- **THEN** at least nine responses identify an accepted speciality and none names a likely condition or recommends treatment

### Requirement: Keep chat within clinic information boundaries
The chat SHALL NOT diagnose, personalize treatment or medicines, or answer unrelated non-clinic topics. It SHALL mark costs as indicative, decline non-eye problems, and retrieve slots or change only the authenticated Patient's appointments through the authorized tools and confirmation workflow.

#### Scenario: Patient asks for a diagnosis or product
- **WHEN** a Patient asks whether blurry vision is a cataract or which eye drops to buy
- **THEN** the response does not confirm a condition or name a product and instead offers appropriate document-supported guidance or the fixed unsupported-answer response

#### Scenario: Non-eye problem is declined
- **WHEN** a Patient describes only a skin rash on an arm
- **THEN** the response says NetraCare only looks after eyes and suggests no speciality

#### Scenario: Booking is requested
- **WHEN** a Patient asks the chat to book Dr. Shah at a valid offered time and supplies the visit reason
- **THEN** the chat presents a confirmation card and books only after Confirm, rather than directing the Patient away from chat

#### Scenario: Documented procedure instructions are restated
- **WHEN** a Patient asks about documented preparation or aftercare for a clinic procedure
- **THEN** the chat may restate those instructions with sources without presenting them as a personalized treatment recommendation

### Requirement: Provide service-backed clinic agent tools
The chat SHALL expose typed tools named `search_clinic_docs`, `list_doctors`, `find_slots`, `my_appointments`, `book_appointment`, `cancel_appointment`, and `reschedule_appointment`. Tools SHALL call the same services as the API, return short structured outcomes, and never write directly to the database.

#### Scenario: Tool refusal is a normal result
- **WHEN** a mutation tool reaches a service that refuses the requested action
- **THEN** it returns `result=refused`, the stable reason code, and the plain-words message without throwing away the agent workflow or changing data

#### Scenario: Doctor and appointment discovery is scoped
- **WHEN** the agent calls `list_doctors` or `my_appointments`
- **THEN** it receives doctor IDs, specialities and OPD days, or only the authenticated Patient's upcoming appointments with IDs and pending Staff requests respectively

#### Scenario: Document tool exposes trusted answer metadata
- **WHEN** the agent calls `search_clinic_docs`
- **THEN** the result contains the grounded answer or fixed unsupported message, trusted source metadata, and whether the documents answered the question
### Requirement: Keep Patient identity outside tool arguments
The authenticated Patient identity SHALL be supplied to tools through trusted execution configuration and SHALL NOT appear as an LLM-generated tool argument. Every own-appointment read or mutation SHALL use that identity regardless of identifiers in the conversation.

#### Scenario: Patient targets another Patient's appointment
- **WHEN** a Patient asks to cancel or reschedule an appointment ID owned by someone else and confirms the action
- **THEN** the service refuses it with NOT_YOUR_APPOINTMENT, returns no details about that appointment, and leaves it unchanged

#### Scenario: Message contains a spoofed acting Patient
- **WHEN** message text instructs the agent to act as a different Patient
- **THEN** the authenticated identity still determines every tool result and mutation
### Requirement: Search availability across requested constraints
`find_slots` SHALL accept a doctor or speciality, visit type, date range, and optional AM/PM session. It SHALL return at most 10 valid doctor/date/start results, earliest first, using the shared availability rules.

#### Scenario: Speciality-wide search spans doctors and dates
- **WHEN** the agent requests availability for a speciality without naming a doctor
- **THEN** results identify the available doctor and are ordered by date and start across covering doctors, with no more than 10 entries

#### Scenario: Session filter and duration are respected
- **WHEN** the agent requests PM follow-up slots
- **THEN** only 10-minute follow-up starts within the PM session are returned and every start satisfies schedule, holiday, overlap, and session-end rules

#### Scenario: No suitable availability exists
- **WHEN** the requested constraints have no valid starts within the booking window
- **THEN** the tool returns an empty result with a clear reason or no-slot message and the agent offers no unseen time
### Requirement: Ground agent scheduling in fresh clinic context
Before agent decisions, the system SHALL provide the current clinic date, weekday and time, the inclusive 30-day booking calendar, and Patient scheduling context. The agent SHALL call `find_slots` before offering a time and SHALL never offer a start absent from its results.

#### Scenario: Relative date crosses a holiday
- **WHEN** a Patient requests a relative date or the earliest weekday and a holiday or Sunday intervenes
- **THEN** the agent uses the supplied calendar and availability results rather than guessing a date or offering a closed day

#### Scenario: Nothing is free in the booking window
- **WHEN** no suitable slot appears in the next 30 days
- **THEN** the agent clearly says nothing is free in that window and does not invent an alternative

#### Scenario: Refusal needs an alternative
- **WHEN** a requested booking is refused for a rule such as DOCTOR_OFF or DOUBLE_BOOKED
- **THEN** the agent explains the refusal in plain words and offers only subsequently verified free starts
### Requirement: Route visit type and speciality safely
The agent SHALL obtain a booking reason before a new booking, select follow-up only with the latest completed doctor in that speciality, and otherwise use a new consultation after explaining the difference. Patients under 16 SHALL route to Paediatric with Dr. Menon; symptom routing SHALL preserve the documented Iteration 3 boundaries.

#### Scenario: Requested follow-up has no eligible history
- **WHEN** a Patient requests a follow-up in a speciality with no completed visit
- **THEN** the agent explains that it must be a new 20-minute consultation and obtains the Patient's agreement before booking it as new

#### Scenario: Follow-up names the wrong doctor
- **WHEN** a Patient requests a follow-up with someone other than the latest completing doctor in that speciality
- **THEN** the agent identifies the eligible doctor and does not silently book the ineligible follow-up

#### Scenario: Child describes a symptom
- **WHEN** a Patient under 16 describes an eye problem without naming a speciality
- **THEN** the agent selects Paediatric with Dr. Vikram Menon and names no likely condition

#### Scenario: Reason is missing
- **WHEN** a Patient asks for a new booking without supplying its reason
- **THEN** the agent asks for the reason before requesting a booking confirmation
### Requirement: Exclude unnecessary health details from agent context
Agent context SHALL include only the Patient's name and age, upcoming appointment scheduling fields and request status, and past-visit date, doctor, speciality, and visit type. Doctor notes, health profile, allergies, and unrelated Patient details SHALL NOT be supplied.

#### Scenario: Prompt contains past visits
- **WHEN** the agent needs previous-visit context to choose a follow-up
- **THEN** it receives the permitted scheduling fields without doctor notes, reasons, health profile, or allergies

#### Scenario: Agent lists upcoming appointments
- **WHEN** appointment context is built for the agent
- **THEN** it contains only the authenticated Patient's upcoming scheduling data and Staff request status
### Requirement: Run a bounded tool-calling agent workflow
Each safe typed message SHALL enter an agent workflow that can call tools, consume their structured results, and continue until it has a response. Execution SHALL have a per-message step limit and every model call SHALL have a timeout.

#### Scenario: Multiple tools are needed
- **WHEN** a request needs document information and then availability before booking
- **THEN** the agent consumes the document result and availability result in sequence before presenting the complete outcome

#### Scenario: Step limit is reached
- **WHEN** the agent cannot finish within its configured step limit
- **THEN** the chat returns "Sorry, I can't finish that just now. Please try again, or ask Staff at the front desk." and performs no unconfirmed mutation
### Requirement: Maintain Patient-bound conversation memory
The server SHALL retain transient conversation state by thread for the current process and bind every thread to the authenticated Patient. The browser SHALL send only the new message or confirmation and thread ID; chat state SHALL NOT be saved to the application database.

#### Scenario: Follow-up uses the same thread
- **WHEN** a Patient says "Actually, make it the afternoon" after discussing or booking a morning appointment in the same chat
- **THEN** the agent uses the thread and fresh appointment context to identify the intended appointment and proposes a reschedule rather than a separate cancellation and booking

#### Scenario: Same raw thread ID is used by another Patient
- **WHEN** a different authenticated Patient supplies a thread ID already used by someone else
- **THEN** no earlier messages, Patient details, or pending action from the original thread are exposed or resumed

#### Scenario: Conversation becomes long
- **WHEN** a thread contains more than 20 messages
- **THEN** the model receives at most the latest 20 messages in valid conversation and tool-call groups while the retained thread remains coherent

#### Scenario: Conversation boundary starts a new thread
- **WHEN** the Patient selects New chat or logs out and back in
- **THEN** a new thread ID is used and the visible chat is empty without database restoration
### Requirement: Confirm every appointment mutation
Booking, cancellation, and rescheduling SHALL pause with a one-line action summary before invoking their mutation service. The response SHALL include one `pending_action`; Confirm SHALL resume that stored action, while No SHALL perform no appointment or approval-request mutation.

#### Scenario: Confirmation card precedes booking
- **WHEN** the agent has selected a valid slot and reason for a new booking
- **THEN** the response contains the booking summary and pending action and the database has no new appointment

#### Scenario: Patient confirms the action
- **WHEN** the Patient sends `confirm=true` for the pending thread action
- **THEN** the stored action is revalidated and executed once and the agent explains its actual service outcome

#### Scenario: Patient declines the action
- **WHEN** the Patient sends `confirm=false`
- **THEN** no appointment or Staff approval request changes and the agent asks what the Patient would like instead

#### Scenario: Confirmation has no pending action
- **WHEN** a Patient sends either confirmation value for a thread with no waiting action
- **THEN** the request is refused without invoking the agent or changing appointment data
### Requirement: Replace pending action safely on a typed message
A typed message received while an action awaits confirmation SHALL decline that stored action without executing it, then process the new message through the red-flag and agent workflow. At most one Patient action SHALL await confirmation per thread.

#### Scenario: New ordinary message declines the old card
- **WHEN** a Patient types a different safe request instead of answering the card
- **THEN** the old action performs no mutation and the new request is handled in the same Patient-bound conversation

#### Scenario: New red-flag message declines the old card
- **WHEN** a Patient types a red-flag message while a mutation is pending
- **THEN** the pending mutation does not execute, the exact emergency response and one chat urgent case are produced, and no agent tool call occurs for that message
### Requirement: Compose responses from current-turn trusted results
Response code SHALL assemble the final answer, pending action, and sources from current-turn agent and tool outputs. Sources SHALL come only from validated document tool metadata; historical thread sources SHALL NOT leak into later replies.

#### Scenario: Information and booking share a turn
- **WHEN** a Patient asks a document question and requests a booking in the same message
- **THEN** the initial pending response retains the document answer and its sources together with the confirmation card

#### Scenario: Documents do not support the answer
- **WHEN** the current document tool reports that it did not answer
- **THEN** the final response is exactly "I don't know. Our clinic documents don't cover that. Please ask Staff at the front desk." with no sources

#### Scenario: Later turn has no document search
- **WHEN** a previous turn produced sources and the current turn concerns only appointments
- **THEN** the current response contains no sources carried over from the earlier turn
