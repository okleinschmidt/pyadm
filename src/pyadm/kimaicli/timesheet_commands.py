"""Timesheet commands: list, inspect, create, start/stop and delete entries."""

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

import click

from pyadm.kimaicli.booking import (
    BookingError,
    parse_date,
    parse_duration,
    parse_tags,
    parse_time,
)
from pyadm.kimaicli.click_commands import (
    echo_listing,
    get_client,
    get_timezone,
    kimaicli,
    run,
)
from pyadm.table import echo_json
from pyadm.kimaicli.kimai import entity_id, entity_name, parse_api_datetime


def format_duration(seconds: Optional[Any]) -> str:
    """Render a duration in seconds as 'H:MM'."""
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return ""
    sign = "-" if total < 0 else ""
    total = abs(total)
    return f"{sign}{total // 3600}:{(total % 3600) // 60:02d}"


def local_datetime(value: Any, tzinfo) -> Optional[datetime]:
    """Parse an API datetime and move it into the display timezone."""
    if not isinstance(value, str) or not value:
        return None
    parsed = parse_api_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tzinfo)
    return parsed.astimezone(tzinfo)


def format_tags(value: Any) -> str:
    """Render the tags of an entry, which the API returns as list or string."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ",".join(str(tag) for tag in value)
    return ""


class NameLookup:
    """Maps project and activity IDs to names.

    The timesheet collection endpoint returns bare IDs rather than nested
    objects, so the names are fetched once and reused for the whole table.
    """

    def __init__(self, client):
        self._client = client
        self._projects: Optional[Dict[int, str]] = None
        self._activities: Optional[Dict[int, str]] = None

    @staticmethod
    def _index(items: List[Dict[str, Any]]) -> Dict[int, str]:
        return {item["id"]: entity_name(item.get("name")) for item in items if item.get("id")}

    def _lookup(self, cache_name: str, fetch) -> Dict[int, str]:
        if getattr(self, cache_name) is None:
            try:
                setattr(self, cache_name, self._index(fetch(visible="3")))
            except Exception:
                # Names are a convenience; fall back to the raw IDs on failure
                setattr(self, cache_name, {})
        return getattr(self, cache_name)

    def name(self, value: Any, kind: str) -> str:
        identifier = entity_id(value)
        if isinstance(value, dict) or identifier is None:
            return entity_name(value)
        if kind == "project":
            mapping = self._lookup("_projects", self._client.list_projects)
        else:
            mapping = self._lookup("_activities", self._client.list_activities)
        return mapping.get(identifier, str(identifier))


def timesheet_rows(entries: List[Dict[str, Any]], tzinfo, names: Optional[NameLookup] = None) -> List[List[Any]]:
    """Build the table rows for a list of timesheet entries."""
    rows = []
    for entry in entries:
        begin = local_datetime(entry.get("begin"), tzinfo)
        end = local_datetime(entry.get("end"), tzinfo)
        project = entry.get("project")
        activity = entry.get("activity")
        rows.append([
            entry.get("id"),
            begin.strftime("%Y-%m-%d") if begin else "",
            begin.strftime("%H:%M") if begin else "",
            end.strftime("%H:%M") if end else "running",
            format_duration(entry.get("duration")),
            names.name(project, "project") if names else entity_name(project),
            names.name(activity, "activity") if names else entity_name(activity),
            (entry.get("description") or "").splitlines()[0] if entry.get("description") else "",
            format_tags(entry.get("tags")),
        ])
    return rows


TIMESHEET_HEADERS = [
    "id", "date", "begin", "end", "duration", "project", "activity", "description", "tags",
]


@kimaicli.group("timesheet", context_settings={'help_option_names': ['-h', '--help']})
def timesheet():
    """Work with timesheet entries.

    \b
    Examples:
        pyadm kimai timesheet list --days 14
        pyadm kimai timesheet add -p 1 -a 2 --date 2026-09-18 -b 09:00 -d 3h
        pyadm kimai timesheet start -p "Support" -a "Maintenance"
        pyadm kimai timesheet stop
        pyadm kimai timesheet delete 4711
    """
    pass


@timesheet.command("list")
@click.option("--days", "-n", type=int, default=7, show_default=True,
              help="Look back this many days (ignored with --from/--to)")
@click.option("--from", "date_from", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--to", "date_to", default=None, help="End date (YYYY-MM-DD)")
@click.option("--project", "-p", default=None, help="Limit to a project (ID or name)")
@click.option("--activity", "-a", default=None, help="Limit to an activity (ID or name)")
@click.option("--user", "-u", default=None, help="Limit to a user ID ('all' for every user)")
@click.option("--limit", "-l", type=int, default=100, show_default=True, help="Maximum entries")
@click.option("--timezone", "tz_name", default=None, help="Timezone for display")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def list_timesheets(days, date_from, date_to, project, activity, user, limit, tz_name, as_json):
    """List timesheet entries, most recent first."""
    client = get_client()
    tzinfo = get_timezone(tz_name)

    try:
        if date_from or date_to:
            if not (date_from and date_to):
                raise BookingError("--from and --to must be used together.")
            start = datetime.combine(parse_date(date_from), time(0, 0), tzinfo=tzinfo)
            end = datetime.combine(parse_date(date_to), time(0, 0), tzinfo=tzinfo) + timedelta(days=1)
        else:
            end = datetime.now(tzinfo) + timedelta(days=1)
            start = datetime.combine(
                (end - timedelta(days=days + 1)).date(), time(0, 0), tzinfo=tzinfo
            )
    except BookingError as exc:
        raise click.ClickException(str(exc)) from exc

    project_id = run(client.resolve_project, project).get("id") if project else None
    activity_id = run(client.resolve_activity, activity, project_id).get("id") if activity else None

    entries = run(
        client.list_timesheets,
        begin=start,
        end=end,
        project=project_id,
        activity=activity_id,
        user=user,
        size=limit,
    )
    echo_listing(
        timesheet_rows(entries, tzinfo, NameLookup(client)),
        TIMESHEET_HEADERS, as_json, entries,
        empty="No timesheet entries found.",
    )

    if entries and not as_json:
        total = sum(int(e.get("duration") or 0) for e in entries)
        click.echo(f"\n{len(entries)} entries, total {format_duration(total)} h")


@timesheet.command("show")
@click.argument("timesheet_id", type=int)
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def show_timesheet(timesheet_id, as_json):
    """Show a single timesheet entry.

    TIMESHEET_ID: Numeric ID of the entry
    """
    client = get_client()
    entry = run(client.get_timesheet, timesheet_id)
    if as_json:
        echo_json(entry)
        return
    tzinfo = get_timezone()
    names = NameLookup(client)
    begin = local_datetime(entry.get("begin"), tzinfo)
    end = local_datetime(entry.get("end"), tzinfo)
    for label, value in [
        ("Id", entry.get("id")),
        ("Begin", begin.strftime("%Y-%m-%d %H:%M") if begin else ""),
        ("End", end.strftime("%Y-%m-%d %H:%M") if end else "running"),
        ("Duration", format_duration(entry.get("duration"))),
        ("Project", names.name(entry.get("project"), "project")),
        ("Activity", names.name(entry.get("activity"), "activity")),
        ("Description", entry.get("description") or ""),
        ("Tags", format_tags(entry.get("tags"))),
        ("Billable", entry.get("billable")),
        ("Exported", entry.get("exported")),
    ]:
        click.echo(f"{label}: {'' if value is None else value}")


@timesheet.command("active")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def active_timesheets(as_json):
    """Show the timesheet entries that are currently running."""
    client = get_client()
    entries = run(client.active_timesheets)
    echo_listing(
        timesheet_rows(entries, get_timezone(), NameLookup(client)),
        TIMESHEET_HEADERS, as_json, entries,
        empty="No running timesheet entry.",
    )


@timesheet.command("add")
@click.option("--project", "-p", required=True, help="Project (ID or name)")
@click.option("--activity", "-a", required=True, help="Activity (ID or name)")
@click.option("--date", "day", default=None, help="Date (YYYY-MM-DD, default: today)")
@click.option("--begin", "-b", required=True, help="Start time (HH:MM)")
@click.option("--end", "-e", default=None, help="End time (HH:MM)")
@click.option("--duration", "-d", default=None, help="Duration, e.g. 2h45m (instead of --end)")
@click.option("--description", "-m", default="", help="Description of the entry")
@click.option("--tags", "-t", default=None, help="Comma-separated tags")
@click.option("--user-id", type=int, default=None, help="Book for another user (needs permissions)")
@click.option("--timezone", "tz_name", default=None, help="Timezone of the given times")
def add_timesheet(project, activity, day, begin, end, duration, description, tags, user_id, tz_name):
    """Add a finished timesheet entry.

    \b
    Examples:
        pyadm kimai timesheet add -p 1 -a 2 -b 09:00 -d 3h -m "Consulting"
        pyadm kimai timesheet add -p Support -a Maintenance --date 2026-09-18 -b 09:00 -e 12:30
    """
    if bool(end) == bool(duration):
        raise click.ClickException("Provide exactly one of --end or --duration.")

    client = get_client()
    tzinfo = get_timezone(tz_name)
    try:
        target_day = parse_date(day) if day else date.today()
        begin_time = parse_time(begin)
        start = datetime.combine(target_day, begin_time, tzinfo=tzinfo)
        if duration:
            finish = start + parse_duration(duration)
        else:
            finish = datetime.combine(target_day, parse_time(end), tzinfo=tzinfo)
            if finish <= start:
                # An end before the begin means the entry runs past midnight
                finish += timedelta(days=1)
    except BookingError as exc:
        raise click.ClickException(str(exc)) from exc

    project_obj = run(client.resolve_project, project)
    activity_obj = run(client.resolve_activity, activity, project_obj.get("id"))

    created = run(
        client.create_timesheet,
        begin=start,
        end=finish,
        project_id=project_obj["id"],
        activity_id=activity_obj["id"],
        description=description,
        tags=parse_tags(tags),
        user_id=user_id,
    )
    click.echo(
        f"Created entry {created.get('id')}: {start.strftime('%Y-%m-%d %H:%M')} - "
        f"{finish.strftime('%H:%M')} "
        f"({entity_name(project_obj.get('name'))} / {entity_name(activity_obj.get('name'))})"
    )


@timesheet.command("start")
@click.option("--project", "-p", required=True, help="Project (ID or name)")
@click.option("--activity", "-a", required=True, help="Activity (ID or name)")
@click.option("--begin", "-b", default=None, help="Start time (HH:MM, default: now)")
@click.option("--description", "-m", default="", help="Description of the entry")
@click.option("--tags", "-t", default=None, help="Comma-separated tags")
@click.option("--timezone", "tz_name", default=None, help="Timezone of the given time")
def start_timesheet(project, activity, begin, description, tags, tz_name):
    """Start tracking time now (leaves the entry running)."""
    client = get_client()
    tzinfo = get_timezone(tz_name)
    try:
        start = (
            datetime.combine(date.today(), parse_time(begin), tzinfo=tzinfo)
            if begin else datetime.now(tzinfo)
        )
    except BookingError as exc:
        raise click.ClickException(str(exc)) from exc

    project_obj = run(client.resolve_project, project)
    activity_obj = run(client.resolve_activity, activity, project_obj.get("id"))
    created = run(
        client.create_timesheet,
        begin=start.replace(microsecond=0),
        end=None,
        project_id=project_obj["id"],
        activity_id=activity_obj["id"],
        description=description,
        tags=parse_tags(tags),
    )
    click.echo(
        f"Started entry {created.get('id')} at {start.strftime('%H:%M')} "
        f"({entity_name(project_obj.get('name'))} / {entity_name(activity_obj.get('name'))})"
    )


@timesheet.command("stop")
@click.argument("timesheet_id", type=int, required=False)
def stop_timesheet(timesheet_id):
    """Stop a running entry.

    TIMESHEET_ID: Entry to stop. Without it, every running entry is stopped.
    """
    client = get_client()
    if timesheet_id is not None:
        targets = [{"id": timesheet_id}]
    else:
        targets = run(client.active_timesheets)
        if not targets:
            click.echo("No running timesheet entry.")
            return

    for entry in targets:
        stopped = run(client.stop_timesheet, entry["id"])
        click.echo(
            f"Stopped entry {entry['id']} "
            f"(duration {format_duration(stopped.get('duration'))} h)"
        )


@timesheet.command("restart")
@click.argument("timesheet_id", type=int)
def restart_timesheet(timesheet_id):
    """Start a new running entry with the project/activity of an existing one.

    TIMESHEET_ID: Entry to copy
    """
    restarted = run(get_client().restart_timesheet, timesheet_id)
    click.echo(f"Restarted as entry {restarted.get('id')}.")


@timesheet.command("delete")
@click.argument("timesheet_ids", type=int, nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation")
def delete_timesheet(timesheet_ids, yes):
    """Delete timesheet entries.

    TIMESHEET_IDS: One or more numeric entry IDs
    """
    client = get_client()
    if not yes:
        ids = ", ".join(str(i) for i in timesheet_ids)
        click.confirm(f"Delete timesheet entries {ids}?", abort=True)
    for timesheet_id in timesheet_ids:
        run(client.delete_timesheet, timesheet_id)
        click.echo(f"Deleted entry {timesheet_id}.")
