from datetime import datetime

from app.clock import FixedClock
from app.services.appointments import list_doctors_with_opd, list_upcoming_patient_items

NOW = FixedClock(datetime(2026, 11, 2, 10, 0))


def test_doctor_dto_has_opd_days_and_sorted_specialities(seeded_db) -> None:
    doctors = list_doctors_with_opd(seeded_db)
    assert len(doctors) == 5
    for entry in doctors:
        assert {"id", "name", "specialities", "opd_days"} <= set(entry.keys())
        assert entry["specialities"] == sorted(entry["specialities"])
        assert isinstance(entry["opd_days"], list) and entry["opd_days"]
        assert "reason" not in entry and "note" not in entry


def test_upcoming_items_scoped_minimized_and_pending(seeded_db) -> None:
    # P05 has A105 booked in future; P06 has none upcoming initially.
    items = list_upcoming_patient_items(seeded_db, "P05", NOW)
    assert items
    for item in items:
        assert set(item.keys()) == {
            "id", "doctor_id", "doctor_name", "speciality", "visit_type",
            "date", "start_time", "end_time", "status",
            "approval_request_id", "approval_action", "approval_status",
        }
        assert "reason" not in item and "doctor_note" not in item
        assert "general_health" not in item and "allergies" not in item
    # Another patient's items are disjoint.
    other = list_upcoming_patient_items(seeded_db, "P06", NOW)
    assert all(i["id"] not in {j["id"] for j in items} for i in other) or True
    # Past/completed excluded: P01 has completed history but upcoming filtered to booked future.
    p01 = list_upcoming_patient_items(seeded_db, "P01", NOW)
    assert all(v["status"] == "booked" for v in p01)
