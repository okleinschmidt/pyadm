"""Date, slot and preset handling for recurring Kimai bookings.

Kept free of Click so the rules that decide *which* entries would be created
can be reasoned about (and reused) on their own.
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pyadm.kimaicli.kimai import entity_id, parse_api_datetime

# Configuration sections holding reusable booking definitions.
PRESET_PREFIX = "BOOKING_"

WEEKDAY_NAMES = {
    "mon": 0, "monday": 0, "mo": 0, "1": 0,
    "tue": 1, "tuesday": 1, "tu": 1, "2": 1,
    "wed": 2, "wednesday": 2, "we": 2, "3": 2,
    "thu": 3, "thursday": 3, "th": 3, "4": 3,
    "fri": 4, "friday": 4, "fr": 4, "5": 4,
    "sat": 5, "saturday": 5, "sa": 5, "6": 5,
    "sun": 6, "sunday": 6, "su": 6, "7": 6,
}

WEEKDAY_GROUPS = {
    "weekdays": [0, 1, 2, 3, 4],
    "workdays": [0, 1, 2, 3, 4],
    "weekend": [5, 6],
    "all": [0, 1, 2, 3, 4, 5, 6],
    "daily": [0, 1, 2, 3, 4, 5, 6],
}

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

DURATION_PATTERN = re.compile(
    r"^(?:(?P<hours>\d+(?:\.\d+)?)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?$",
    re.IGNORECASE,
)


class BookingError(ValueError):
    """Raised for invalid booking input (times, dates, slots, presets)."""


@dataclass(frozen=True)
class Slot:
    """One bookable block of a day."""

    begin: time
    duration: timedelta
    description: str = ""
    project: Optional[str] = None
    activity: Optional[str] = None

    @property
    def end(self) -> time:
        """End time of the slot, for display purposes only."""
        reference = datetime.combine(date(2000, 1, 1), self.begin) + self.duration
        return reference.time()

    def label(self) -> str:
        return f"{self.begin.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"


def parse_time(value: str) -> time:
    """Parse 'HH:MM' or 'HH:MM:SS'."""
    try:
        return time.fromisoformat(value.strip())
    except ValueError as exc:
        raise BookingError(f"Invalid time '{value}'. Use HH:MM.") from exc


def parse_date(value: str) -> date:
    """Parse 'YYYY-MM-DD', or the shorthands 'today' and 'yesterday'."""
    text = value.strip().lower()
    if text == "today":
        return date.today()
    if text == "yesterday":
        return date.today() - timedelta(days=1)
    if text == "tomorrow":
        return date.today() + timedelta(days=1)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise BookingError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


def parse_month(value: str) -> Tuple[int, int]:
    """Parse 'YYYY-MM' into a (year, month) pair."""
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m")
    except ValueError as exc:
        raise BookingError(f"Invalid month '{value}'. Use YYYY-MM.") from exc
    return parsed.year, parsed.month


def parse_duration(value: str) -> timedelta:
    """Parse '2h45m', '165m', '2:45' or a plain number of minutes."""
    text = value.strip().lower()
    if not text:
        raise BookingError("Duration cannot be empty.")

    if ":" in text:
        parts = text.split(":")
        if len(parts) > 3 or not all(p.isdigit() for p in parts):
            raise BookingError(f"Invalid duration '{value}'. Use HH:MM or 2h45m.")
        parts += ["0"] * (3 - len(parts))
        hours, minutes, seconds = (int(p) for p in parts)
        return timedelta(hours=hours, minutes=minutes, seconds=seconds)

    if text.isdigit():
        return timedelta(minutes=int(text))

    match = DURATION_PATTERN.match(text)
    if not match or not any(match.groupdict().values()):
        raise BookingError(
            f"Invalid duration '{value}'. Use e.g. 2h45m, 90m, 1.5h or 2:45."
        )
    return timedelta(
        hours=float(match.group("hours") or 0),
        minutes=int(match.group("minutes") or 0),
        seconds=int(match.group("seconds") or 0),
    )


def parse_tags(value: Optional[str]) -> List[str]:
    """Split a comma-separated tag list."""
    if not value:
        return []
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def parse_weekdays(values: Sequence[str]) -> List[int]:
    """Turn weekday names, ranges ('mon-fri') and groups ('weekdays') into indexes."""
    selected: List[int] = []

    def add(index: int) -> None:
        if index not in selected:
            selected.append(index)

    for raw in values:
        for token in str(raw).replace(" ", "").split(","):
            if not token:
                continue
            key = token.lower()
            if key in WEEKDAY_GROUPS:
                for index in WEEKDAY_GROUPS[key]:
                    add(index)
                continue
            if "-" in key:
                start_name, _, end_name = key.partition("-")
                if start_name not in WEEKDAY_NAMES or end_name not in WEEKDAY_NAMES:
                    raise BookingError(f"Invalid weekday range '{token}'.")
                start, end = WEEKDAY_NAMES[start_name], WEEKDAY_NAMES[end_name]
                # Ranges wrap around the week, so 'sat-sun' and 'fri-mon' both work
                index = start
                while True:
                    add(index)
                    if index == end:
                        break
                    index = (index + 1) % 7
                continue
            if key not in WEEKDAY_NAMES:
                raise BookingError(
                    f"Invalid weekday '{token}'. Use mon..sun, a range like mon-fri, "
                    f"or a group like weekdays/weekend/all."
                )
            add(WEEKDAY_NAMES[key])

    return sorted(selected)


def format_weekdays(weekdays: Sequence[int]) -> str:
    return ", ".join(WEEKDAY_LABELS[day] for day in sorted(weekdays))


def parse_slot(spec: str) -> Slot:
    """
    Parse a slot specification.

    Format: ``TIMES[|description[|project[|activity]]]`` where TIMES is either
    ``BEGIN-END`` (e.g. ``09:00-11:45``) or ``BEGIN+DURATION`` (``09:00+2h45m``).
    The optional project/activity override the command-wide defaults, which is
    what makes a day of differing blocks bookable in one go.
    """
    fields = [field.strip() for field in str(spec).split("|")]
    times = fields[0]
    description = fields[1] if len(fields) > 1 else ""
    project = fields[2] if len(fields) > 2 and fields[2] else None
    activity = fields[3] if len(fields) > 3 and fields[3] else None

    if "+" in times:
        begin_text, _, duration_text = times.partition("+")
        begin = parse_time(begin_text)
        duration = parse_duration(duration_text)
    elif "-" in times:
        begin_text, _, end_text = times.partition("-")
        begin = parse_time(begin_text)
        end = parse_time(end_text)
        duration = datetime.combine(date.min, end) - datetime.combine(date.min, begin)
        if duration <= timedelta(0):
            # An end before the begin means the slot runs past midnight
            duration += timedelta(days=1)
    else:
        raise BookingError(
            f"Invalid slot '{spec}'. Use BEGIN-END (09:00-11:45) or "
            f"BEGIN+DURATION (09:00+2h45m)."
        )

    if duration <= timedelta(0):
        raise BookingError(f"Slot '{spec}' has a zero or negative duration.")

    return Slot(
        begin=begin,
        duration=duration,
        description=description,
        project=project,
        activity=activity,
    )


def days_in_month_range(
    start_month: Tuple[int, int], end_month: Tuple[int, int]
) -> List[date]:
    """Every day from the first of *start_month* to the last of *end_month*."""
    if start_month > end_month:
        raise BookingError("The start month must not be after the end month.")
    start = date(start_month[0], start_month[1], 1)
    last_day = calendar.monthrange(end_month[0], end_month[1])[1]
    end = date(end_month[0], end_month[1], last_day)
    return days_in_range(start, end)


def days_in_range(start: date, end: date) -> List[date]:
    """Every day from *start* to *end*, inclusive."""
    if start > end:
        raise BookingError("The start date must not be after the end date.")
    days: List[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def filter_weekdays(days: Sequence[date], weekdays: Sequence[int]) -> List[date]:
    """Keep only the days falling on one of *weekdays* (empty means keep all)."""
    if not weekdays:
        return list(days)
    wanted = set(weekdays)
    return [day for day in days if day.weekday() in wanted]


def select_dates(
    *,
    dates: Sequence[str] = (),
    months: Sequence[str] = (),
    start_month: Optional[str] = None,
    end_month: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    weekdays: Sequence[int] = (),
    today: Optional[date] = None,
) -> List[date]:
    """
    Work out which days to book from the mutually exclusive date selectors.

    Exactly one selector may be used: explicit dates, months, a month range,
    a date range, or nothing at all (which means today).
    """
    selectors = [
        bool(dates),
        bool(months),
        bool(start_month or end_month),
        bool(date_from or date_to),
    ]
    if sum(selectors) > 1:
        raise BookingError(
            "Use only one of --date, --month, --start-month/--end-month or --from/--to."
        )

    if dates:
        chosen = sorted({parse_date(value) for value in dates})
        # Explicit dates are taken at face value; a weekday filter would only
        # silently drop what the user typed out by hand.
        return chosen

    if months:
        chosen = []
        for month in months:
            year, month_number = parse_month(month)
            chosen.extend(days_in_month_range((year, month_number), (year, month_number)))
        return filter_weekdays(sorted(set(chosen)), weekdays)

    if start_month or end_month:
        if not (start_month and end_month):
            raise BookingError("--start-month and --end-month must be used together.")
        chosen = days_in_month_range(parse_month(start_month), parse_month(end_month))
        return filter_weekdays(chosen, weekdays)

    if date_from or date_to:
        if not (date_from and date_to):
            raise BookingError("--from and --to must be used together.")
        chosen = days_in_range(parse_date(date_from), parse_date(date_to))
        return filter_weekdays(chosen, weekdays)

    return [today or date.today()]


def has_duplicate(
    entries: Sequence[Dict[str, Any]],
    *,
    begin: datetime,
    end: datetime,
    project_id: int,
    activity_id: int,
) -> bool:
    """Whether *entries* already contains exactly this booking."""
    target_begin = begin.astimezone(timezone.utc)
    target_end = end.astimezone(timezone.utc)
    local_tz = begin.tzinfo or timezone.utc

    for entry in entries:
        begin_raw, end_raw = entry.get("begin"), entry.get("end")
        if not isinstance(begin_raw, str) or not isinstance(end_raw, str):
            continue

        entry_begin = parse_api_datetime(begin_raw)
        entry_end = parse_api_datetime(end_raw)
        if entry_begin.tzinfo is None:
            entry_begin = entry_begin.replace(tzinfo=local_tz)
        if entry_end.tzinfo is None:
            entry_end = entry_end.replace(tzinfo=local_tz)

        if entry_begin.astimezone(timezone.utc) != target_begin:
            continue
        if entry_end.astimezone(timezone.utc) != target_end:
            continue
        if entity_id(entry.get("project")) == project_id and \
                entity_id(entry.get("activity")) == activity_id:
            return True

    return False


def split_preset_slots(value: str) -> List[str]:
    """Split the 'slots' value of a preset section into single specifications."""
    specs: List[str] = []
    for line in value.splitlines():
        for spec in line.split(","):
            # A slot may carry a description with spaces, but never a comma
            spec = spec.strip()
            if spec:
                specs.append(spec)
    return specs
