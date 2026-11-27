# Backend Known Issues — for future agent (not part of frontend cleanup)

Date: 2026-11-27. Scope: `remove-frontend-for-cleanup` deleted only the UI tree
(`frontend/`, UI skill, lock files) plus headless doc/CORS updates.

## 2026-11-27 backend bug-fix pass (done, 178 tests green)

The collection failures described below in §1 are resolved and no longer reproduce:
`python -m pytest -q` → **178 passed**. Fixed in this pass:

- `app/schemas.py`: `AppointmentView` moved above `ToStaffResponse` so the
  `appointment` field is a resolved model instead of a `ForwardRef`
  (broken on older Python; silently worked on 3.14+ only via lazy rebuild).
  `approval_view` return annotation corrected to `StaffApprovalRequestView`.
- `app/routers/appointments.py` (`create_appointment`): `EntityNotFound` →
  404 and `InvalidActor` → 400 instead of an uncaught 500 on bad `doctor_id`.
- `app/routers/staff.py`: unknown doctor/patient in staff booking → 404
  (was 400); reject-approval refusal now returns the same
  `{result, reason_code, message}` 409 body as approve.
- `app/services/scheduling.py`: `find_slots` / `search_availability` no longer
  `IndexError` (500) on a doctor with zero specialities.
- `app/rules.py` + `app/services/appointments.py`: cancelling/rescheduling a
  past `BOOKED` appointment now returns `NOT_ACTIVE` instead of routing to
  Staff (`INSIDE_2_HOURS`); stale past `BOOKED` rows no longer block new
  bookings via `ACTIVE_BOOKING_EXISTS` (only upcoming appointments count).
  Reschedule `NOT_ACTIVE` message verb fixed ("rescheduled").
- `app/routers/common.py`: `appointment_view` tolerates missing
  patient/doctor relationships instead of `AttributeError` 500.
- `app/routers/doctors.py`: `GET /doctors` now populates `opd_days`
  (was always `None`) and returns sorted specialities.
- `app/main.py`: `allow_credentials=False` with wildcard CORS origins
  (browsers reject wildcard + credentials).

## 1. `pytest` collection failures (original note — now fixed, see above)

```bash
cd backend && python -m pytest -q
```

Result at cleanup time: 24 collection errors, run interrupted.

- `app/schemas.py:141 in ToStaffResponse` → `NameError: name 'AppointmentView' is not defined`
- Multiple service/test modules → `NameError: name 'RuleDecision' is not defined`

No longer reproduces on Python 3.15 (deferred annotations) and the schema
ordering is fixed regardless.

## 2. Pre-existing dirty file (do not attribute to cleanup)

`backend/app/routers/appointments.py` was already modified before cleanup:
adds `try/except LookupError → HTTPException 404` around `find_slots()` in
`available_slots`. Cleanup did not make this edit — keep it (still present).

## 3. CORS note from cleanup

`backend/app/main.py` uses `allow_origins=["*"]` with a headless comment.
When the rebuilt UI lands, tighten this to the real origin(s).

## 4. Known residual risks (deliberately deferred — need design decisions)

- No DB-level uniqueness on `(doctor_id, date, start_time)` and no row
  locks: concurrent double-booking / double-approval is possible under
  parallel workers (SQLite `BEGIN IMMEDIATE` serializes single-process).
  Fix needs a unique constraint + `IntegrityError` handling.
- `next_source_id` is max-plus-one in Python: concurrent inserts can collide
  on IDs (`IntegrityError` → 500). Same fix as above.
- `AuthSession` tokens never expire; no rate limiting; chat/doctor-history
  endpoints are intentionally broad (any doctor can read any patient's
  completed history — flag for product before tightening).
- `approve_request` on an invalid target leaves the request `PENDING`
  (staff must reject manually); RAG rebuild is delete-then-ingest with no
  rollback. Both acceptable for a classroom seed-data app.

## 5. Dev servers

Restart backend with:

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload
```
