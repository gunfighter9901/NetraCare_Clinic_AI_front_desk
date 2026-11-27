from datetime import date

from app.clock import FixedClock
from app.models import VisitType
from app.services.scheduling import search_availability
from datetime import datetime

NOW = FixedClock(datetime(2026, 11, 2, 10, 0))


def test_speciality_search_spans_doctors_and_caps_at_ten(seeded_db) -> None:
    agg = search_availability(
        seeded_db,
        visit_type=VisitType.NEW,
        clock=NOW,
        speciality="General",
        start_date=date(2026, 11, 3),
        end_date=date(2026, 11, 10),
    )
    assert len(agg.slots) <= 10
    assert agg.slots == sorted(agg.slots, key=lambda s: (s.date, s.start_time, s.doctor_id))
    assert agg.searched_doctors >= 2


def test_session_filter_and_duration_respected(seeded_db) -> None:
    agg = search_availability(
        seeded_db,
        visit_type=VisitType.FOLLOW_UP,
        clock=NOW,
        doctor_id="D1",
        start_date=date(2026, 11, 3),
        end_date=date(2026, 11, 3),
        session="PM",
    )
    for slot in agg.slots:
        assert 14 * 60 <= slot.start_time.hour * 60 + slot.start_time.minute < 18 * 60
        assert slot.start_time.minute % 10 == 0


def test_empty_range_and_window_boundaries(seeded_db) -> None:
    # Sunday only.
    agg = search_availability(
        seeded_db,
        visit_type=VisitType.NEW,
        clock=NOW,
        doctor_id="D1",
        start_date=date(2026, 11, 9 - 7 if False else 9),  # placeholder
        end_date=date(2026, 11, 9),
    ) if False else None
    sunday = date(2026, 11, 9)  # Sunday + holiday in seed? 9 Nov is holiday
    agg2 = search_availability(
        seeded_db, visit_type=VisitType.NEW, clock=NOW, doctor_id="D1",
        start_date=sunday, end_date=sunday,
    )
    assert agg2.slots == []
    assert "No suitable" in agg2.message or "closed" in agg2.message.lower() or "No" in agg2.message
    # Beyond 30 days truncated.
    far = search_availability(
        seeded_db, visit_type=VisitType.NEW, clock=NOW, speciality="General",
        start_date=date(2026, 11, 2), end_date=date(2026, 12, 20),
    )
    assert all(s.date <= date(2026, 12, 2) for s in far.slots)
