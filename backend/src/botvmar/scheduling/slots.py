"""Slot-based scheduling helpers.

A "slot" is a daily wall-clock time written as `"HH:MM"` (server timezone).
Each platform owns a list of slots and a `jitter_min` window. The worker
fires a cycle for the platform when:

    slot_start <= now < slot_start + jitter_min   AND
    no run has been started in this window yet
"""

from __future__ import annotations

from datetime import datetime, time, timedelta


def parse_slot(slot_str: str) -> time | None:
    """Parse `"HH:MM"`. Returns None on invalid input.

    Lenient: ignores surrounding whitespace, accepts both `9:05` and `09:05`.
    """
    if not slot_str:
        return None
    try:
        parts = slot_str.strip().split(":")
        if len(parts) != 2:
            return None
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return time(h, m)
    except (ValueError, AttributeError):
        pass
    return None


def slot_window(slot: time, on_date: datetime, jitter_min: int) -> tuple[datetime, datetime]:
    """Return `(start, end)` for a slot anchored on the date of `on_date`.

    The window length is `max(jitter_min, 1)` minutes — never zero so the
    worker always has at least one tick to catch the slot.
    """
    base = on_date.replace(
        hour=slot.hour, minute=slot.minute,
        second=0, microsecond=0,
    )
    return (base, base + timedelta(minutes=max(jitter_min, 1)))


def is_slot_due(
    slots: list[str],
    now: datetime,
    last_run: datetime | None,
    jitter_min: int,
) -> bool:
    """True when `now` falls inside a slot's window and no run started in it."""
    for slot_str in slots:
        slot = parse_slot(slot_str)
        if slot is None:
            continue
        start, end = slot_window(slot, now, jitter_min)
        if start <= now < end:
            if last_run is None or last_run < start:
                return True
    return False


def next_slot_after(
    slots: list[str],
    now: datetime,
    jitter_min: int = 0,
) -> datetime | None:
    """Datetime of the next slot start strictly after `now`. None if no valid slots.

    Used to size the worker's sleep so it wakes up close to the next slot
    rather than ticking every minute when nothing is due for hours.
    """
    candidates: list[datetime] = []
    for slot_str in slots:
        slot = parse_slot(slot_str)
        if slot is None:
            continue
        today = now.replace(
            hour=slot.hour, minute=slot.minute,
            second=0, microsecond=0,
        )
        if today > now:
            candidates.append(today)
        # Always include tomorrow's occurrence as a fallback
        candidates.append(today + timedelta(days=1))
    return min(candidates) if candidates else None
