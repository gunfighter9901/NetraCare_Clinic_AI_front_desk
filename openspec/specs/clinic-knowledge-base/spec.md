# clinic-knowledge-base Specification

## Purpose

Provides a rebuildable, document-grounded clinic knowledge base with inspectable keyword and semantic retrieval for Patient answers and Staff diagnostics.

## Requirements

### Requirement: Chunk clinic documents by section
The system SHALL split the three supplied documents at `##` headings before subdividing sections longer than the configured chunk size. Every chunk SHALL retain text from only one section and carry stable `chunk_id`, `source`, and `section` metadata.

#### Scenario: Source sections remain identifiable
- **WHEN** the supplied documents are chunked after the data pack 4 policy replaces its data pack 3 copy
- **THEN** all 40 source sections are represented, including "Booking through the chat assistant" and "If your doctor is on leave", every chunk identifies its source file and heading, and no chunk crosses a section boundary

#### Scenario: Long sections are subdivided
- **WHEN** a section exceeds the approximately 1,000-character chunk target
- **THEN** it is split with approximately 100 characters of overlap while shorter sections remain intact
### Requirement: Build and reuse a persistent Weaviate collection
The system SHALL store the canonical chunks and their Weaviate vectors in the configured Cloud collection through one explicit build command. Requests SHALL reuse the built collection rather than rebuilding it, and document or embedding-model changes SHALL require an explicit rebuild.

#### Scenario: Index is built independently of chat traffic
- **WHEN** an operator runs the index-build command and then serves retrieval requests
- **THEN** the persisted Weaviate collection contains the canonical chunks and serving those requests does not re-embed or recreate it

#### Scenario: Source documents remain unchanged
- **WHEN** the index is built or rebuilt
- **THEN** the three supplied Markdown files retain their original content

### Requirement: Provide punctuation-insensitive keyword retrieval
Keyword retrieval SHALL operate over the same Weaviate collection as vector retrieval and SHALL match exact terms independently of trailing punctuation and case.

#### Scenario: Punctuation does not prevent a doctor-name match
- **WHEN** Staff searches for "Menon?"
- **THEN** keyword retrieval treats the query as matching chunks containing "Menon"

#### Scenario: Exact report terminology is found
- **WHEN** the query is "Should I bring my HbA1c report?"
- **THEN** keyword retrieval ranks `procedures.md` section `Diabetic eye check` first

### Requirement: Combine keyword and vector rankings equally
The system SHALL combine keyword and vector results with equal weight and return the top four distinct canonical chunks. A chunk ranked highly by either retrieval method SHALL remain eligible for the hybrid result.

#### Scenario: Semantic wording reaches the relevant procedure
- **WHEN** the query is "Can my kid have breakfast on the morning of the operation to straighten his eye?"
- **THEN** vector and hybrid results include `procedures.md` section `Squint surgery` in their top four even when keyword search does not

#### Scenario: Hybrid results have stable identities
- **WHEN** keyword and vector searches return overlapping chunks
- **THEN** the hybrid result deduplicates them by `chunk_id` and returns at most four chunks

### Requirement: Expose Staff-only search diagnostics
The system SHALL provide Staff with keyword-only, vector-only, and hybrid top-four results for a query. Each result SHALL include chunk ID, file, section, and a score labeled by its scoring semantics; Patient and Doctor access SHALL be refused.

#### Scenario: Staff compares retrieval methods
- **WHEN** Staff submits a search-debug query
- **THEN** the response contains three ranked lists and distinguishes keyword scores, vector scores or distances, and hybrid fused scores

#### Scenario: Non-Staff calls search debug directly
- **WHEN** a Patient, Doctor, or unauthenticated caller requests search diagnostics
- **THEN** the system refuses the request without returning document chunks
