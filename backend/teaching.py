"""Shared teaching-allocation and class-session helpers."""
from datetime import date, datetime, time

from sqlalchemy import or_

import domain_models as D


ACTIVE_ALLOCATION_STATUSES = {"active"}


def active_allocations_for_faculty(s, faculty_id: str, on_date: date | None = None):
    on_date = on_date or date.today()
    return (s.query(D.TeachingAllocation)
            .filter(D.TeachingAllocation.faculty_id == faculty_id,
                    D.TeachingAllocation.status.in_(ACTIVE_ALLOCATION_STATUSES),
                    or_(D.TeachingAllocation.effective_from == None,
                        D.TeachingAllocation.effective_from <= on_date),
                    or_(D.TeachingAllocation.effective_to == None,
                        D.TeachingAllocation.effective_to >= on_date))
            .all())


def active_allocation_for_section(s, section_id: str, on_date: date | None = None):
    on_date = on_date or date.today()
    return (s.query(D.TeachingAllocation)
            .filter(D.TeachingAllocation.section_id == section_id,
                    D.TeachingAllocation.status.in_(ACTIVE_ALLOCATION_STATUSES),
                    or_(D.TeachingAllocation.effective_from == None,
                        D.TeachingAllocation.effective_from <= on_date),
                    or_(D.TeachingAllocation.effective_to == None,
                        D.TeachingAllocation.effective_to >= on_date))
            .order_by(D.TeachingAllocation.is_coordinator.desc(), D.TeachingAllocation.created_at.desc())
            .first())


def faculty_owns_section(s, faculty_id: str, section_id: str, on_date: date | None = None) -> bool:
    return any(row.section_id == section_id for row in active_allocations_for_faculty(s, faculty_id, on_date))


def faculty_active_sections(s, faculty_id: str, on_date: date | None = None):
    ids = {row.section_id for row in active_allocations_for_faculty(s, faculty_id, on_date)}
    return s.query(D.Section).filter(D.Section.id.in_(ids)).all() if ids else []


def faculty_workload(s, faculty_id: str, on_date: date | None = None) -> float:
    return round(sum(float(row.workload_units or 0) for row in active_allocations_for_faculty(s, faculty_id, on_date)), 2)


def sync_section_faculty(s, section_id: str, on_date: date | None = None):
    section = s.query(D.Section).get(section_id)
    allocation = active_allocation_for_section(s, section_id, on_date)
    if section:
        section.faculty_person_id = allocation.faculty_id if allocation else None
    return allocation


def allocation_for_timetable(s, timetable_entry, on_date: date | None = None):
    return active_allocation_for_section(s, timetable_entry.section_id, on_date)


def class_session_for_timetable(s, timetable_entry, session_date: date, allocation=None):
    existing = (s.query(D.ClassSession)
                .filter(D.ClassSession.timetable_entry_id == timetable_entry.id,
                        D.ClassSession.session_date == session_date)
                .first())
    if existing:
        return existing
    allocation = allocation or allocation_for_timetable(s, timetable_entry, session_date)
    if not allocation:
        return None
    start = datetime.combine(session_date, time.fromisoformat(timetable_entry.start_time))
    end = datetime.combine(session_date, time.fromisoformat(timetable_entry.end_time))
    session = D.ClassSession(
        id=f"session_{timetable_entry.id}_{session_date.isoformat()}",
        tenant_id=timetable_entry.tenant_id,
        allocation_id=allocation.id,
        timetable_entry_id=timetable_entry.id,
        section_id=timetable_entry.section_id,
        faculty_id=allocation.faculty_id,
        session_date=session_date,
        scheduled_start=start,
        scheduled_end=end,
        room=timetable_entry.room,
        status="scheduled",
    )
    s.add(session)
    s.flush()
    return session


def timetable_conflicts(s, faculty_id: str, day_of_week: int, start_time: str, end_time: str,
                        exclude_section_id: str | None = None):
    conflicts = []
    for allocation in active_allocations_for_faculty(s, faculty_id):
        if exclude_section_id and allocation.section_id == exclude_section_id:
            continue
        entries = (s.query(D.TimetableEntry)
                   .filter(D.TimetableEntry.section_id == allocation.section_id,
                           D.TimetableEntry.day_of_week == day_of_week,
                           D.TimetableEntry.status == "active")
                   .all())
        for entry in entries:
            if start_time < entry.end_time and end_time > entry.start_time:
                conflicts.append(entry)
    return conflicts
