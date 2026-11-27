from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Enum as SqlEnum, ForeignKey, Index, String, Time, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Role(str, Enum):
    PATIENT = "patient"
    STAFF = "staff"
    DOCTOR = "doctor"


class ScheduleStatus(str, Enum):
    OPD = "OPD"
    SURGERY = "SURGERY"
    OFF = "OFF"


class VisitType(str, Enum):
    NEW = "new"
    FOLLOW_UP = "follow_up"

    @property
    def minutes(self) -> int:
        return 20 if self is VisitType.NEW else 10


class AppointmentStatus(str, Enum):
    BOOKED = "booked"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    specialities: Mapped[list[DoctorSpeciality]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan", lazy="selectin"
    )
    schedules: Mapped[list[WeeklySchedule]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )


class DoctorSpeciality(Base):
    __tablename__ = "doctor_specialities"

    doctor_id: Mapped[str] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), primary_key=True
    )
    speciality: Mapped[str] = mapped_column(String(80), primary_key=True)
    doctor: Mapped[Doctor] = relationship(back_populates="specialities")


class WeeklySchedule(Base):
    __tablename__ = "weekly_schedule"

    doctor_id: Mapped[str] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[str] = mapped_column(String(3), primary_key=True)
    session: Mapped[str] = mapped_column(String(2), primary_key=True)
    status: Mapped[ScheduleStatus] = mapped_column(
        SqlEnum(ScheduleStatus, values_callable=lambda items: [item.value for item in items], native_enum=False),
        nullable=False,
    )
    doctor: Mapped[Doctor] = relationship(back_populates="schedules")


class Holiday(Base):
    __tablename__ = "holidays"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mobile: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    year_of_birth: Mapped[int | None] = mapped_column(nullable=True)
    general_health: Mapped[str | None] = mapped_column(String(500), nullable=True)
    allergies: Mapped[str | None] = mapped_column(String(500), nullable=True)

    appointments: Mapped[list[Appointment]] = relationship(back_populates="patient")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"), nullable=False, index=True)
    speciality: Mapped[str] = mapped_column(String(80), nullable=False)
    visit_type: Mapped[VisitType] = mapped_column(
        SqlEnum(VisitType, values_callable=lambda items: [item.value for item in items], native_enum=False),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        SqlEnum(
            AppointmentStatus,
            values_callable=lambda items: [item.value for item in items],
            native_enum=False,
        ),
        nullable=False,
        default=AppointmentStatus.BOOKED,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    doctor_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    urgent_case_id: Mapped[str | None] = mapped_column(
        ForeignKey("urgent_cases.id"), nullable=True, index=True
    )

    patient: Mapped[Patient] = relationship(back_populates="appointments", lazy="joined")
    doctor: Mapped[Doctor] = relationship(lazy="joined")


class UrgentOrigin(str, Enum):
    BOOKING = "booking"
    CHAT = "chat"


class UrgentCase(Base):
    __tablename__ = "urgent_cases"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    patient_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    patient_mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason_text: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    model_why: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    seen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    origin: Mapped[UrgentOrigin] = mapped_column(
        SqlEnum(UrgentOrigin, values_callable=lambda items: [item.value for item in items], native_enum=False),
        nullable=False,
        default=UrgentOrigin.BOOKING,
    )


class ApprovalAction(str, Enum):
    CANCEL = "cancel"
    RESCHEDULE = "reschedule"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StaffApprovalRequest(Base):
    __tablename__ = "staff_approval_requests"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    appointment_id: Mapped[str] = mapped_column(
        ForeignKey("appointments.id"), nullable=False, index=True
    )
    action: Mapped[ApprovalAction] = mapped_column(
        SqlEnum(ApprovalAction, values_callable=lambda items: [item.value for item in items], native_enum=False),
        nullable=False,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        SqlEnum(ApprovalStatus, values_callable=lambda items: [item.value for item in items], native_enum=False),
        nullable=False,
        default=ApprovalStatus.PENDING,
        index=True,
    )
    target_doctor_id: Mapped[str | None] = mapped_column(ForeignKey("doctors.id"), nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    replacement_appointment_id: Mapped[str | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    patient: Mapped[Patient] = relationship(lazy="joined", foreign_keys=[patient_id])
    appointment: Mapped[Appointment] = relationship(
        lazy="joined", foreign_keys=[appointment_id]
    )
    target_doctor: Mapped[Doctor | None] = relationship(lazy="joined", foreign_keys=[target_doctor_id])

    __table_args__ = (
        Index(
            "uq_pending_approval_per_appointment",
            "appointment_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
        ),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    role: Mapped[Role] = mapped_column(
        SqlEnum(Role, values_callable=lambda items: [item.value for item in items], native_enum=False),
        nullable=False,
    )
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    doctor_id: Mapped[str | None] = mapped_column(ForeignKey("doctors.id"), nullable=True)
    staff_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    patient: Mapped[Patient | None] = relationship(lazy="joined")
    doctor: Mapped[Doctor | None] = relationship(lazy="joined")
