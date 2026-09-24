"""Maintenance commands: schedule, inspect and end planned downtimes.

Uptime Kuma calls a planned downtime a "maintenance". A maintenance is built
in three steps - create the window, attach the monitors it silences, and
optionally attach the status pages that should announce it - so every command
here does all three and reports the result as one action.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import click

from pyadm.table import echo_json, echo_table, render_table
from pyadm.uptimecli.click_commands import (
    confirm_change,
    echo_details,
    get_client,
    get_timezone_option,
    local_timezone_name,
    run,
    uptimecli,
)
from pyadm.uptimecli.uptime import (
    UptimeError,
    enum_value,
    format_api_datetime,
    format_time_range,
    format_weekdays,
    parse_datetime,
    parse_days_of_month,
    parse_duration,
    parse_time_range,
    parse_weekdays,
)

STRATEGIES = [
    "manual",
    "single",
    "recurring-interval",
    "recurring-weekday",
    "recurring-day-of-month",
    "cron",
]

# Which fields a strategy actually needs, so a missing one can be named.
STRATEGY_REQUIREMENTS = {
    "recurring-weekday": ("--weekday", "weekdays"),
    "recurring-day-of-month": ("--day", "days_of_month"),
}


def maintenance_rows(client, maintenances: Sequence[Dict[str, Any]],
                     with_monitors: bool) -> List[List[Any]]:
    """Build the rows of the maintenance listing."""
    rows = []
    for item in maintenances:
        row = [
            item.get("id"),
            item.get("title", ""),
            enum_value(item.get("strategy")) or "",
            item.get("status", ""),
            schedule_summary(item),
        ]
        if with_monitors:
            monitors = run(client.maintenance_monitors, int(item["id"]))
            row.append(", ".join(str(m.get("name", "")) for m in monitors))
        rows.append(row)
    return rows


def schedule_summary(maintenance: Dict[str, Any]) -> str:
    """One-line description of when a maintenance applies."""
    strategy = enum_value(maintenance.get("strategy"))
    date_range = maintenance.get("dateRange") or []
    time_range = format_time_range(maintenance.get("timeRange") or [])

    if strategy == "manual":
        return "manual"
    if strategy == "single":
        return " - ".join(str(value) for value in date_range if value)
    if strategy == "cron":
        duration = maintenance.get("durationMinutes")
        return f"{maintenance.get('cron', '')} for {duration}m" if duration else str(
            maintenance.get("cron", "")
        )
    if strategy == "recurring-interval":
        return f"every {maintenance.get('intervalDay', 1)}d {time_range}".strip()
    if strategy == "recurring-weekday":
        return f"{format_weekdays(maintenance.get('weekdays') or [])} {time_range}".strip()
    if strategy == "recurring-day-of-month":
        days = ", ".join(
            "last day" if str(day).startswith("lastDay") else str(day)
            for day in maintenance.get("daysOfMonth") or []
        )
        return f"{days} {time_range}".strip()
    return time_range


def attach(client, maintenance_id: int, monitors: Sequence[Dict[str, Any]],
           status_pages: Sequence[Dict[str, Any]]) -> None:
    """Attach monitors and status pages to a freshly created maintenance."""
    run(client.set_maintenance_monitors, maintenance_id, monitors)
    if status_pages:
        run(client.set_maintenance_status_pages, maintenance_id, status_pages)


def describe_window(payload: Dict[str, Any], timezone: str,
                    monitors: Sequence[Dict[str, Any]],
                    status_pages: Sequence[Dict[str, Any]]) -> str:
    """Render what would be created, for --dry-run."""
    date_range = payload.get("dateRange") or []
    rows = [
        ["strategy", enum_value(payload.get("strategy"))],
        ["schedule", schedule_summary(payload)],
        ["starts", date_range[0] if date_range else ""],
    ]
    if len(date_range) > 1 and payload.get("strategy") != "single":
        rows.append(["ends", date_range[1]])
    rows += [
        ["timezone", timezone],
        ["monitors", ", ".join(str(m.get("name")) for m in monitors)],
    ]
    if status_pages:
        rows.append(["status pages", ", ".join(str(p.get("title")) for p in status_pages)])
    return render_table(rows, ["field", "value"])


def build_schedule(strategy: str, start: Optional[str], end: Optional[str],
                   duration: Optional[str], window: Optional[str],
                   weekdays: Sequence[str], days: Sequence[str],
                   interval_day: Optional[int], cron: Optional[str]) -> Dict[str, Any]:
    """Turn the schedule options into the fields the API expects.

    Raises:
        UptimeError: if the options do not describe a usable window
    """
    payload: Dict[str, Any] = {"strategy": strategy}
    now = datetime.now().replace(second=0, microsecond=0)

    begin = parse_datetime(start, now) if start else now
    finish: Optional[datetime] = None
    if end:
        finish = parse_datetime(end, begin)
    elif duration and strategy != "cron":
        # For cron windows the duration is the length of each run, not the
        # end of the date range it recurs in.
        finish = begin + parse_duration(duration)

    if strategy == "manual":
        # A manual maintenance runs until it is ended by hand.
        payload["dateRange"] = [format_api_datetime(begin)]
        return payload

    if strategy == "single":
        if finish is None:
            raise UptimeError(
                "A single maintenance needs an end: pass --duration or --end."
            )
        if finish <= begin:
            raise UptimeError("The end of the window is not after its start.")
        payload["dateRange"] = [format_api_datetime(begin), format_api_datetime(finish)]
        return payload

    # The recurring strategies run inside a date range, with a daily window.
    payload["dateRange"] = [format_api_datetime(begin)] + (
        [format_api_datetime(finish)] if finish else []
    )

    if strategy == "cron":
        if not cron:
            raise UptimeError("A cron maintenance needs --cron, e.g. --cron '30 3 * * *'.")
        payload["cron"] = cron
        payload["durationMinutes"] = int(
            parse_duration(duration).total_seconds() // 60
        ) if duration else 60
        return payload

    if not window:
        raise UptimeError(
            f"A {strategy} maintenance needs a daily time window: "
            f"pass --window HH:MM-HH:MM."
        )
    payload["timeRange"] = parse_time_range(window)

    if strategy == "recurring-interval":
        payload["intervalDay"] = interval_day or 1
    elif strategy == "recurring-weekday":
        if not weekdays:
            raise UptimeError("A recurring-weekday maintenance needs --weekday, e.g. -w sat.")
        payload["weekdays"] = parse_weekdays(weekdays)
    elif strategy == "recurring-day-of-month":
        if not days:
            raise UptimeError(
                "A recurring-day-of-month maintenance needs --day, e.g. --day 1 --day last."
            )
        payload["daysOfMonth"] = parse_days_of_month(days)

    return payload


def create_maintenance(client, title: str, payload: Dict[str, Any],
                       monitors: Sequence[Dict[str, Any]],
                       status_pages: Sequence[Dict[str, Any]],
                       description: str, timezone: Optional[str],
                       paused: bool) -> int:
    """Create the window and attach its monitors and status pages."""
    maintenance_id = run(
        client.add_maintenance,
        title=title,
        description=description or "",
        active=not paused,
        timezoneOption=timezone,
        **payload,
    )
    attach(client, maintenance_id, monitors, status_pages)
    return maintenance_id


def resolve_targets(client, monitor_ids: Sequence[str],
                    status_page_ids: Sequence[str]):
    """Resolve the monitors a window covers and the status pages that show it."""
    if not monitor_ids:
        raise click.ClickException(
            "Name at least one monitor with -m/--monitor: a maintenance without "
            "monitors silences nothing."
        )
    monitors = run(client.resolve_monitors, list(monitor_ids))
    status_pages = run(client.resolve_status_pages, list(status_page_ids)) \
        if status_page_ids else []
    return monitors, status_pages


@uptimecli.group("maintenance", context_settings={'help_option_names': ['-h', '--help']})
def maintenance():
    """Schedule and manage maintenance windows (planned downtimes).

    \b
    Examples:
        pyadm uptime maintenance list
        pyadm uptime maintenance show "Patch night"
        pyadm uptime maintenance add "DB upgrade" -m db -s 22:00 -d 2h
        pyadm uptime maintenance add "Patch night" -m web -m api \\
            --strategy recurring-weekday -w sat --window 02:00-04:00
        pyadm uptime maintenance delete "DB upgrade"
    """
    pass


@maintenance.command("list")
@click.option("--active", "-a", is_flag=True, help="Only windows that are not paused")
@click.option("--monitors", "-M", "with_monitors", is_flag=True,
              help="Also show the monitors of each window (one request per window)")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def list_maintenances(active, with_monitors, as_json):
    """List the maintenance windows of the instance."""
    client = get_client()
    data = run(client.list_maintenances)
    if active:
        data = [item for item in data if item.get("active", True)]

    if as_json:
        echo_json(data)
        return

    headers = ["id", "title", "strategy", "status", "schedule"]
    if with_monitors:
        headers.append("monitors")
    echo_table(maintenance_rows(client, data, with_monitors), headers,
               empty="No maintenance windows found.")


@maintenance.command("show")
@click.argument("maintenance_id")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def show_maintenance(maintenance_id, as_json):
    """Show one maintenance window. MAINTENANCE_ID is an ID or a title."""
    client = get_client()
    data = run(client.resolve_maintenance, maintenance_id)
    monitors = run(client.maintenance_monitors, int(data["id"]))
    pages = run(client.maintenance_status_pages, int(data["id"]))

    if as_json:
        echo_json({"maintenance": data, "monitors": monitors, "status_pages": pages})
        return

    echo_details([
        ("Id", data.get("id")),
        ("Title", data.get("title")),
        ("Description", data.get("description") or ""),
        ("Strategy", enum_value(data.get("strategy"))),
        ("Status", data.get("status")),
        ("Active", "yes" if data.get("active", True) else "no"),
        ("Schedule", schedule_summary(data)),
        ("Timezone", data.get("timezoneOption") or "server default"),
        ("Monitors", ", ".join(str(m.get("name", "")) for m in monitors)),
        ("Status pages", ", ".join(str(p.get("title", "")) for p in pages)),
    ])

    timeslots = data.get("timeslotList") or []
    if timeslots:
        click.echo()
        click.echo(render_table(
            [[slot.get("startDate", ""), slot.get("endDate", "")] for slot in timeslots],
            ["start", "end"],
        ))


def schedule_options(command):
    """Options shared by 'maintenance add' and the 'downtime' shortcut."""
    for option in reversed([
        click.option("--monitor", "-m", "monitor_ids", multiple=True,
                     help="Monitor the window covers (ID or name, repeatable)"),
        click.option("--start", "-s", default=None,
                     help="Start: 'now', 'HH:MM', 'YYYY-MM-DD HH:MM' (default: now)"),
        click.option("--duration", "-d", default=None,
                     help="How long the window lasts, e.g. 2h, 90m, 1h30m"),
        click.option("--end", "-e", default=None, help="End instead of a duration"),
        click.option("--description", "-D", default=None, help="Free-text description"),
        click.option("--status-page", "status_page_ids", multiple=True,
                     help="Status page that announces the window (ID, slug or title)"),
        click.option("--timezone", default=None,
                     help="Timezone the times are given in (default: context or server)"),
        click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation"),
        click.option("--dry-run", is_flag=True, help="Show what would be scheduled"),
    ]):
        command = option(command)
    return command


@maintenance.command("add")
@click.argument("title")
@schedule_options
@click.option("--strategy", type=click.Choice(STRATEGIES), default="single",
              show_default=True, help="How the window recurs")
@click.option("--window", "window", default=None,
              help="Daily time window for recurring strategies, HH:MM-HH:MM")
@click.option("--weekday", "-w", "weekdays", multiple=True,
              help="Weekday for recurring-weekday, e.g. sat or mon-fri (repeatable)")
@click.option("--day", "days", multiple=True,
              help="Day of month for recurring-day-of-month: 1-31 or 'last' (repeatable)")
@click.option("--interval-day", type=int, default=None,
              help="Run every N days (recurring-interval), default 1")
@click.option("--cron", default=None, help="Cron expression for the cron strategy")
@click.option("--paused", is_flag=True, help="Create the window in paused state")
def add_maintenance(title, monitor_ids, start, duration, end, description,
                    status_page_ids, timezone, yes, dry_run, strategy, window,
                    weekdays, days, interval_day, cron, paused):
    """Schedule a maintenance window named TITLE.

    \b
    Examples:
        pyadm uptime maintenance add "DB upgrade" -m db -s "2026-10-04 22:00" -d 2h
        pyadm uptime maintenance add "Patch night" -m web -m api \\
            --strategy recurring-weekday -w sat --window 02:00-04:00
        pyadm uptime maintenance add "Monthly" -m web \\
            --strategy recurring-day-of-month --day 1 --window 01:00-03:00
        pyadm uptime maintenance add "Ad hoc" -m web --strategy manual
    """
    client = get_client()
    monitors, pages = resolve_targets(client, monitor_ids, status_page_ids)

    try:
        payload = build_schedule(strategy, start, end, duration, window,
                                 weekdays, days, interval_day, cron)
    except UptimeError as exc:
        raise click.ClickException(str(exc)) from exc

    zone = timezone or get_timezone_option()
    names = ", ".join(str(m.get("name")) for m in monitors)

    if dry_run:
        click.echo(f"Would schedule maintenance '{title}':")
        click.echo(describe_window(payload, zone or f"{local_timezone_name()} (server default)",
                                   monitors, pages))
        return

    confirm_change(
        f"Schedule '{title}' ({schedule_summary(payload)}) for {len(monitors)} "
        f"monitor(s): {names}?", yes
    )
    maintenance_id = create_maintenance(client, title, payload, monitors, pages,
                                        description, zone, paused)
    click.echo(
        f"Scheduled maintenance '{title}' (ID {maintenance_id}) for {len(monitors)} "
        f"monitor(s): {names}."
    )


@uptimecli.command("downtime")
@schedule_options
@click.option("--title", "-t", default=None,
              help="Title of the window (default: 'Downtime <start>')")
@click.option("--now", "start_now", is_flag=True,
              help="Start immediately (the default when --start is omitted)")
def downtime(monitor_ids, start, duration, end, description, status_page_ids,
             timezone, yes, dry_run, title, start_now):
    """Silence monitors for a while - a one-off maintenance window.

    The shortcut for the common case: take these monitors out of alerting from
    now (or from --start) for --duration. Everything else about maintenance
    windows lives under 'pyadm uptime maintenance'.

    \b
    Examples:
        pyadm uptime downtime -m web -m api -d 2h
        pyadm uptime downtime -m web -s 22:00 -d 90m
        pyadm uptime downtime -m db -s "2026-10-04 22:00" -e "2026-10-05 02:00"
        pyadm uptime downtime -m web -d 30m --dry-run
    """
    if start_now and start:
        raise click.ClickException("Pass either --now or --start, not both.")
    if not duration and not end:
        raise click.ClickException(
            "How long should the downtime last? Pass --duration 2h or --end."
        )

    client = get_client()
    monitors, pages = resolve_targets(client, monitor_ids, status_page_ids)

    try:
        payload = build_schedule("single", start, end, duration, None, (), (), None, None)
    except UptimeError as exc:
        raise click.ClickException(str(exc)) from exc

    begin, finish = payload["dateRange"]
    window_title = title or f"Downtime {begin}"
    zone = timezone or get_timezone_option()
    names = ", ".join(str(m.get("name")) for m in monitors)

    if dry_run:
        click.echo(f"Would schedule downtime '{window_title}':")
        click.echo(describe_window(payload, zone or f"{local_timezone_name()} (server default)",
                                   monitors, pages))
        return

    confirm_change(
        f"Silence {len(monitors)} monitor(s) from {begin} to {finish}: {names}?", yes
    )
    maintenance_id = create_maintenance(client, window_title, payload, monitors, pages,
                                        description, zone, paused=False)
    click.echo(
        f"Scheduled downtime '{window_title}' (ID {maintenance_id}) from {begin} "
        f"to {finish} for: {names}."
    )


def _set_maintenance_state(maintenance_ids, yes, dry_run, resume: bool) -> None:
    """Shared body of 'maintenance pause' and 'maintenance resume'."""
    client = get_client()
    verb = "Resume" if resume else "Pause"
    windows = [run(client.resolve_maintenance, value) for value in maintenance_ids]
    names = ", ".join(f"{w.get('title')} (ID {w.get('id')})" for w in windows)

    if dry_run:
        click.echo(f"Would {verb.lower()} {len(windows)} maintenance window(s): {names}")
        return
    if len(windows) > 1:
        confirm_change(f"{verb} {len(windows)} maintenance window(s): {names}?", yes)

    action = client.resume_maintenance if resume else client.pause_maintenance
    for window in windows:
        run(action, int(window["id"]))
        click.echo(f"{verb}d maintenance '{window.get('title')}' (ID {window.get('id')}).")


@maintenance.command("pause")
@click.argument("maintenance_ids", metavar="MAINTENANCE...", nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation")
@click.option("--dry-run", is_flag=True, help="Show what would be paused")
def pause_maintenance(maintenance_ids, yes, dry_run):
    """Pause maintenance windows. MAINTENANCE is an ID or a title."""
    _set_maintenance_state(maintenance_ids, yes, dry_run, resume=False)


@maintenance.command("resume")
@click.argument("maintenance_ids", metavar="MAINTENANCE...", nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation")
@click.option("--dry-run", is_flag=True, help="Show what would be resumed")
def resume_maintenance(maintenance_ids, yes, dry_run):
    """Resume paused maintenance windows. MAINTENANCE is an ID or a title."""
    _set_maintenance_state(maintenance_ids, yes, dry_run, resume=True)


@maintenance.command("delete")
@click.argument("maintenance_ids", metavar="MAINTENANCE...", nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted")
def delete_maintenance(maintenance_ids, yes, dry_run):
    """Delete maintenance windows. MAINTENANCE is an ID or a title."""
    client = get_client()
    windows = [run(client.resolve_maintenance, value) for value in maintenance_ids]
    names = ", ".join(f"{w.get('title')} (ID {w.get('id')})" for w in windows)

    if dry_run:
        click.echo(f"Would delete {len(windows)} maintenance window(s): {names}")
        return

    confirm_change(f"Delete {len(windows)} maintenance window(s): {names}?", yes)
    for window in windows:
        run(client.delete_maintenance, int(window["id"]))
        click.echo(f"Deleted maintenance '{window.get('title')}' (ID {window.get('id')}).")
