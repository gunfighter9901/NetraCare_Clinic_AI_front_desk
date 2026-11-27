# patient-fact Specification

## Purpose

Gives patients a brief general eye-health fact on login without providing medical advice or treatment guidance.

## Requirements

### Requirement: Show a Fact of the Day on patient login
The system SHALL show each authenticated patient a Fact of the Day card with one general eye-health fact of no more than two sentences, plus the code-rendered caveat "General information, not medical advice".

#### Scenario: Patient login shows fact with caveat
- **WHEN** any patient logs in
- **THEN** the workspace shows a Fact card with a short general fact and "General information, not medical advice" under it

### Requirement: Refresh returns a different fact
The system SHALL accept the currently displayed fact as refresh input, ask the model for a different fact, and display the new result with the same caveat.

#### Scenario: Refresh changes the fact
- **WHEN** the patient clicks Refresh on the Fact card
- **THEN** a different fact appears with the caveat still shown

### Requirement: Restrict fact content to general information
Facts SHALL contain only general, friendly eye-health information and SHALL NOT name conditions to watch for, suggest treatment, or mention medicines or product names.

#### Scenario: Fact content stays non-clinical
- **WHEN** facts are generated across logins and refreshes
- **THEN** no fact names a condition, suggests treatment, or mentions a medicine or product

### Requirement: Fall back safely when fact generation is unavailable
The system SHALL show a fixed safe fallback fact with the same caveat when the LLM call fails or no API key is configured, without blocking login or appointments.

#### Scenario: Missing key still allows login
- **WHEN** the backend restarts without an API key and a patient logs in
- **THEN** the Fact card shows its fallback message and the patient can continue booking
