# NetraCare backend

FastAPI, SQLAlchemy, and SQLite backend for the fictional NetraCare clinic. Use only the supplied synthetic data packs.

## Setup

From this directory with Python 3.11 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Configuration is read from environment variables or an optional `.env` file (see `.env.example`):

- `NETRACARE_DATABASE_URL`, default `sqlite:///./netracare.db`
- `NETRACARE_DATA_PACK_PATH`, default `../Project_Resources/data-pack-Iteration_01`
- `NETRACARE_DATA_PACK_2_PATH`, default `../Project_Resources/data-pack-Iteration_02`
- `NETRACARE_DATA_PACK_3_PATH`, default `../Project_Resources/data-pack-Iteration_03`
- `NETRACARE_CLINIC_TIMEZONE`, default `Asia/Kolkata`
- `NETRACARE_CLINIC_NOW`, optional fixed ISO clinic-local time for deterministic demos/tests
- `NETRACARE_LLM_PROVIDER`, default `gemini` (only Gemini is wired in Iteration 2)
- `NETRACARE_LLM_MODEL`, default `gemini-3.5-flash-lite` (any Gemini chat model name works)
- `NETRACARE_LLM_TIMEOUT_SECONDS`, default `20`
- `GOOGLE_API_KEY` or `GEMINI_API_KEY`, required only for live LLM calls; never commit it
- `WEAVIATE_URL`, Weaviate Cloud cluster URL (scheme is added if omitted); never commit it
- `WEAVIATE_API_KEY`, Weaviate Cloud API key; never commit it
- `NETRACARE_RAG_COLLECTION`, default `NetraCareChunks`
- `NETRACARE_RAG_EMBEDDING_MODEL`, default `Snowflake/snowflake-arctic-embed-m-v1.5`
- `NETRACARE_RAG_CHUNK_SIZE`, default `1000`
- `NETRACARE_RAG_CHUNK_OVERLAP`, default `100`
- `NETRACARE_RAG_TOP_K`, default `4`

Paths are resolved from the directory where the command runs, so run the commands below from `backend/`.

## Initialize the data pack

```bash
python -m app.loader
```

The command creates missing tables, inserts or updates the four main CSV files without deleting appointments, and prints counts. A fresh database reports 5 doctors, 60 weekly schedule rows, 30 holidays, 25 patients, and 0 appointments. Repeating the command is safe and does not duplicate reference rows. Loading data pack 2 (Iteration 2) adds 27 completed past visits and profiles for all 25 patients; see below.

`stretch/appointments_seed.csv` is loaded only by isolated tests through `load_seed_appointments`; normal initialization never loads it.

## Iteration 2 LLM setup

Iteration 2 uses Google Gemini through LangChain (`langchain-google-genai`):

```bash
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY (or GEMINI_API_KEY)
# Optional: change NETRACARE_LLM_MODEL, e.g. gemini-3.5-flash-lite
python -c "from app.llm import get_fact; print('llm import ok')"
```

- Keep the key in `.env` only. `.env` is git-ignored; commit `.env.example` with the key left blank.
- Without a key the app still starts: Fact of the Day and summaries return fixed fallbacks, while bookings are refused with the retry message because the safety check cannot run.
- To switch models, change only `NETRACARE_LLM_MODEL` in `.env`; no code change is needed.
- Never send real patient information to the LLM API; use only synthetic data-pack records.
- Never put the key in frontend `VITE_*` variables; all LLM calls run in the backend.

## Iteration 3 knowledge base (Weaviate)

Patient chat answers from three supplied documents via Weaviate Cloud with
`text2vec-weaviate` model `Snowflake/snowflake-arctic-embed-m-v1.5`.
Set `WEAVIATE_URL` and `WEAVIATE_API_KEY` in `.env` (see `.env.example`;
the URL scheme is added automatically if omitted).

Build or rebuild the `NetraCareChunks` collection with:

```bash
python build_index.py
```

The command chunk-loads `doctors.md`, `procedures.md`, and
`clinic_policy_faq.md` section-first (≈40 chunks), recreates the collection,
and ingests all chunks. Re-run it after editing documents or changing
`NETRACARE_RAG_EMBEDDING_MODEL` or `NETRACARE_RAG_COLLECTION`. Requests never
rebuild the collection; a missing collection surfaces as the normal
chat-unavailable response with a server log telling the operator to rebuild.

## Run

```bash
uvicorn app.main:app --reload
```

The API listens on `http://127.0.0.1:8000`; interactive documentation is at `/docs`.

## Role-oriented API workflow

All protected operations require `Authorization: Bearer <token>` from the matching login.

| Role | Operations |
| --- | --- |
| Any authenticated role | `GET /doctors`, `GET /slots?doctor_id=...&appointment_date=...&visit_type=new|follow_up` |
| Patient | `POST /appointments`, `GET /appointments`, `POST /appointments/{id}/cancel`, `POST /appointments/{id}/reschedule`, `POST /chat` with `{thread_id, message}` or `{thread_id, confirm}` |
| Staff | `GET /staff/patients`, `GET /staff/appointments?appointment_date=...&doctor_id=...`, `POST /staff/appointments`, `POST /appointments/{id}/cancel`, `GET /staff/approvals`, `POST /staff/approvals/{id}/approve`, `POST /staff/approvals/{id}/reject` |
| Doctor | `GET /doctor/appointments?appointment_date=...`, `POST /appointments/{id}/complete` |

Patient requests never select the acting patient: the backend uses the identity from the session. Staff may book for an existing patient or supply `walk_in_name` and `walk_in_mobile`; Staff cannot bypass the booking rules.

A successful mutation returns the appointment. A rule refusal returns HTTP 409 with:

```json
{"result":"refused","reason_code":"DOUBLE_BOOKED","message":"..."}
```

A valid late Patient cancellation or reschedule returns HTTP 202 with a persisted Staff request; the appointment remains booked:

```json
{"result":"to_staff","reason_code":"INSIDE_2_HOURS","appointment":{},"approval_request":{"id":"SR001","status":"pending"}}
```

Rescheduling is atomic: the replacement is evaluated as if the original were cancelled, then the original is cancelled and the replacement booked in one transaction. A refused replacement leaves the original unchanged.

Run automated checks with:

```bash
python -m pytest
```

## Rule outcomes and reason codes

Every booking and cancellation is decided by the backend rule path. A refusal returns the applicable stable reason code plus a plain-words message; allowed actions return the created or changed appointment and no reason code.

| Code | Meaning |
| --- | --- |
| `INVALID_START_TIME` | Start time is not on a 10-minute mark |
| `IN_PAST` | Appointment starts before the clinic clock |
| `BEYOND_30_DAYS` | Appointment is more than 30 days ahead |
| `CLINIC_CLOSED` | The clinic is closed on Sunday |
| `HOLIDAY` | The date is listed in `holidays.csv` |
| `OUTSIDE_SESSION` | Start is before 9 AM, during 1–2 PM, or at/after 6 PM |
| `ENDS_AFTER_SESSION` | The visit would finish after 1 PM or 6 PM |
| `DOCTOR_OFF` | The doctor is not at the clinic in that session |
| `SURGERY_SESSION` | The doctor is operating in that session |
| `SPECIALITY_MISMATCH` | The doctor does not cover the speciality |
| `DOUBLE_BOOKED` | The doctor already has an overlapping booked appointment |
| `ACTIVE_BOOKING_EXISTS` | The patient already has a booked appointment in that speciality |
| `NO_PREVIOUS_VISIT` | Follow-up requested without a completed visit in that speciality |
| `FOLLOW_UP_DIFFERENT_DOCTOR` | Follow-up is not with the latest completing doctor |
| `INSIDE_2_HOURS` | Late Patient action queued for Staff (`to_staff`, HTTP 202); the appointment stays booked |
| `NOT_YOUR_APPOINTMENT` | A patient acted on another patient's appointment |
| `NOT_ACTIVE` | The appointment is already cancelled or completed |

## Deterministic rule suite

Run the selected data-pack cases with:

```bash
python -m pytest tests/test_rule_suite.py -vv
```

The output contains `test_selected_rule_cases[T01]` through `test_selected_rule_cases[T38]`, including atomic rescheduling and Staff approvals. T32 and T37 produce `to_staff` with a pending request rather than an ordinary refusal.

Each case creates its own in-memory database, loads the main CSV files, `stretch/appointments_seed.csv`, and data pack 2 `past_visits.csv`, and fixes the clinic clock at `2026-11-02 10:00`. The command never reads or modifies `netracare.db`.

## Iteration 4 agent

- Install `langgraph>=0.6.11,<0.7` alongside the existing LangChain 0.3 stack (`pip install -e '.[dev]'`).
- Tools live in `app/tools.py`; the three-node graph, prompt, memory, interrupts, and response composition live in `app/agent.py`.
- `POST /chat` uses `{thread_id, message}` or `{thread_id, confirm}`; browser history is not accepted. Threads are namespaced by Patient and held in process memory (`InMemorySaver`). New chat/logout/Patient change starts a new thread.
- Mutation tools interrupt before any service call; Confirm resumes once, No declines, and a typed message while pending declines the old card before handling the new message.
- `search_clinic_docs` uses lazy Weaviate lookup so pure booking turns do not require retrieval. Doctor-leave rebooking (R7) is deferred; the updated FAQ remains informational.

## Synthetic classroom login

Initialize the data pack first, then use these inputs at `POST /auth/patient`, `POST /auth/doctor`, or `POST /auth/staff`:

| Role | Input |
| --- | --- |
| Patient | `{"mobile":"9000000001","name":"Asha Verma"}` |
| Doctor | `{"doctor_id":"D1"}` for Dr. Anand Rao; get all choices from `GET /auth/doctor-options` |
| Staff | `{"name":"Front Desk"}` |

A new Patient mobile creates a synthetic patient. An existing mobile must use the matching name. Login responses contain a bearer token; send it as `Authorization: Bearer <token>` and use `POST /auth/logout` to invalidate it.

**These passwordless logins are for classroom demonstration only, not real security.** Never use real patient information or deploy this identity model as production authentication.
