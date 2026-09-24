"""Book recurring tasks onto a project.

This is the generalised form of the "book two fixed Saturday slots" script:
project, activity, times and the days to hit are all free to choose, and a
recurring set of slots can be stored as a preset in the configuration.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import click

from pyadm.config import cluster_config
from pyadm.kimaicli.booking import (
    PRESET_PREFIX,
    BookingError,
    Slot,
    format_weekdays,
    has_duplicate,
    parse_slot,
    parse_tags,
    parse_weekdays,
    select_dates,
    split_preset_slots,
)
from pyadm.kimaicli.click_commands import get_client, get_timezone, kimaicli, run
from pyadm.kimaicli.kimai import entity_name
from pyadm.table import render_table


def list_presets() -> List[Tuple[str, Dict[str, str]]]:
    """All booking presets from the configuration, as (name, section) pairs."""
    cluster_config.reload()
    presets = []
    for section in cluster_config.config.sections():
        if section.upper().startswith(PRESET_PREFIX):
            presets.append((section[len(PRESET_PREFIX):], dict(cluster_config.config[section])))
    return sorted(presets, key=lambda entry: entry[0].lower())


def load_preset(name: str) -> Dict[str, str]:
    """Look up a preset section by its name (case-insensitive)."""
    wanted = name.strip().lower()
    presets = list_presets()
    for preset_name, cfg in presets:
        if preset_name.lower() == wanted:
            return cfg
    available = ", ".join(preset_name for preset_name, _ in presets) or "none defined"
    raise click.ClickException(
        f"Unknown booking preset '{name}'. Available presets: {available}"
    )


def build_slots(
    slot_specs: Tuple[str, ...],
    begin: Optional[str],
    end: Optional[str],
    duration: Optional[str],
    description: str,
    preset: Dict[str, str],
) -> List[Slot]:
    """
    Turn the slot options into Slot objects.

    Precedence: explicit --slot options, then --begin plus --end/--duration,
    then the preset's slots. Mixing --slot with --begin is rejected rather than
    guessed at.
    """
    if slot_specs and (begin or end or duration):
        raise BookingError("Use either --slot or --begin/--end/--duration, not both.")

    specs: List[str] = list(slot_specs)

    if not specs and begin:
        if bool(end) == bool(duration):
            raise BookingError("With --begin, provide exactly one of --end or --duration.")
        separator, value = ("-", end) if end else ("+", duration)
        specs = [f"{begin}{separator}{value}"]

    from_preset = False
    if not specs and preset.get("slots"):
        specs = split_preset_slots(preset["slots"])
        from_preset = True

    if not specs:
        raise BookingError(
            "No slot given. Use --slot '09:00-11:45', --begin/--duration, or a preset."
        )

    slots = [parse_slot(spec) for spec in specs]

    # --description labels slots that carry none of their own, so a single
    # description still covers every slot of the day. Against a preset it wins
    # outright: what was typed now beats what the config file remembers.
    fallback = description or preset.get("description", "")
    override = bool(description) and from_preset
    if fallback:
        slots = [
            slot if slot.description and not override else Slot(
                begin=slot.begin,
                duration=slot.duration,
                description=fallback,
                project=slot.project,
                activity=slot.activity,
            )
            for slot in slots
        ]
    return slots


class EntityResolver:
    """Resolves project/activity names to IDs, looking each one up only once."""

    def __init__(self, client):
        self.client = client
        self._projects: Dict[str, Dict[str, Any]] = {}
        self._activities: Dict[Tuple[str, Optional[int]], Dict[str, Any]] = {}

    def project(self, value: str) -> Dict[str, Any]:
        key = str(value).strip().lower()
        if key not in self._projects:
            self._projects[key] = run(self.client.resolve_project, value)
        return self._projects[key]

    def activity(self, value: str, project_id: Optional[int]) -> Dict[str, Any]:
        key = (str(value).strip().lower(), project_id)
        if key not in self._activities:
            self._activities[key] = run(self.client.resolve_activity, value, project_id)
        return self._activities[key]


@kimaicli.command("book")
@click.option("--preset", "-P", default=None,
              help=f"Load defaults from a [{PRESET_PREFIX}<name>] config section")
@click.option("--project", "-p", default=None, help="Project (ID or name)")
@click.option("--activity", "-a", default=None, help="Activity (ID or name)")
@click.option("--slot", "-s", "slot_specs", multiple=True,
              help="Slot as BEGIN-END or BEGIN+DURATION, optionally "
                   "'|description|project|activity'. Repeatable.")
@click.option("--begin", "-b", default=None, help="Start time of a single slot (HH:MM)")
@click.option("--end", "-e", default=None, help="End time of a single slot (HH:MM)")
@click.option("--duration", "-d", default=None, help="Duration of a single slot, e.g. 2h45m")
@click.option("--description", "-m", default="", help="Description for slots without one")
@click.option("--tags", "-t", default=None, help="Comma-separated tags")
@click.option("--date", "dates", multiple=True, help="Book this date (YYYY-MM-DD). Repeatable.")
@click.option("--month", "months", multiple=True, help="Book a whole month (YYYY-MM). Repeatable.")
@click.option("--start-month", default=None, help="First month of a range (YYYY-MM)")
@click.option("--end-month", default=None, help="Last month of a range (YYYY-MM)")
@click.option("--from", "date_from", default=None, help="First day of a range (YYYY-MM-DD)")
@click.option("--to", "date_to", default=None, help="Last day of a range (YYYY-MM-DD)")
@click.option("--weekday", "-w", "weekdays", multiple=True,
              help="Only these weekdays: mon..sun, ranges (mon-fri) or groups "
                   "(weekdays/weekend/all). Repeatable.")
@click.option("--user-id", type=int, default=None, help="Book for another user (needs permissions)")
@click.option("--timezone", "tz_name", default=None, help="Timezone of the given times")
@click.option("--dry-run", is_flag=True, help="Show what would be booked, create nothing")
@click.option("--no-duplicate-check", is_flag=True,
              help="Do not check for identical existing entries")
@click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation")
def book(preset, project, activity, slot_specs, begin, end, duration, description, tags,
         dates, months, start_month, end_month, date_from, date_to, weekdays, user_id,
         tz_name, dry_run, no_duplicate_check, yes):
    """Book one or more recurring slots onto a project.

    Days are chosen with exactly one of --date, --month, --start-month/--end-month
    or --from/--to (default: today) and are narrowed by --weekday. Identical
    entries that already exist are skipped, so a run can safely be repeated.

    \b
    A single block today:
        pyadm kimai book -p "Support" -a "Maintenance" -b 09:00 -d 3h

    \b
    Two blocks on every Saturday of a quarter:
        pyadm kimai book -p 42 -a 7 \\
            -s "09:00-11:45|Weekend shift 1" -s "11:45-14:30|Weekend shift 2" \\
            --start-month 2026-01 --end-month 2026-03 -w sat

    \b
    A daily stand-up on working days, from a stored preset:
        pyadm kimai book --preset standup --month 2026-10

    \b
    Different projects within one day:
        pyadm kimai book -p "Support" -a "Maintenance" \\
            -s "09:00-12:00" -s "13:00-17:00|Rollout|Infrastructure|Deployment" \\
            --date 2026-09-21
    """
    preset_cfg = load_preset(preset) if preset else {}

    try:
        slots = build_slots(slot_specs, begin, end, duration, description, preset_cfg)

        default_project = project or preset_cfg.get("project")
        default_activity = activity or preset_cfg.get("activity")
        if not default_project and any(slot.project is None for slot in slots):
            raise BookingError("No project given. Use --project or a preset.")
        if not default_activity and any(slot.activity is None for slot in slots):
            raise BookingError("No activity given. Use --activity or a preset.")

        weekday_values = list(weekdays) or (
            [preset_cfg["weekdays"]] if preset_cfg.get("weekdays") else []
        )
        selected_weekdays = parse_weekdays(weekday_values)

        target_dates = select_dates(
            dates=dates,
            months=months,
            start_month=start_month,
            end_month=end_month,
            date_from=date_from,
            date_to=date_to,
            weekdays=selected_weekdays,
        )
    except BookingError as exc:
        raise click.ClickException(str(exc)) from exc

    if not target_dates:
        weekday_hint = (
            f" matching {format_weekdays(selected_weekdays)}" if selected_weekdays else ""
        )
        raise click.ClickException(f"No days{weekday_hint} in the selected period.")

    tag_list = parse_tags(tags) if tags is not None else parse_tags(preset_cfg.get("tags"))
    if user_id is None and preset_cfg.get("user_id"):
        try:
            user_id = int(preset_cfg["user_id"])
        except ValueError as exc:
            raise click.ClickException(
                f"Invalid user_id '{preset_cfg['user_id']}' in preset section."
            ) from exc

    client = get_client()
    tzinfo = get_timezone(tz_name or preset_cfg.get("timezone"))
    resolver = EntityResolver(client)

    # Resolve names once up front, so a typo fails before anything is created
    planned: List[Dict[str, Any]] = []
    for slot in slots:
        project_obj = resolver.project(slot.project or default_project)
        activity_obj = resolver.activity(
            slot.activity or default_activity, project_obj.get("id")
        )
        planned.append({
            "slot": slot,
            "project": project_obj,
            "activity": activity_obj,
        })

    rows: List[List[Any]] = []
    to_create: List[Dict[str, Any]] = []
    skipped = 0

    for target_date in target_dates:
        existing = []
        if not no_duplicate_check:
            existing = run(client.list_timesheets_for_day, target_date, tzinfo)

        for entry in planned:
            slot: Slot = entry["slot"]
            start = datetime.combine(target_date, slot.begin, tzinfo=tzinfo)
            finish = start + slot.duration

            duplicate = not no_duplicate_check and has_duplicate(
                existing,
                begin=start,
                end=finish,
                project_id=entry["project"]["id"],
                activity_id=entry["activity"]["id"],
            )
            if duplicate:
                skipped += 1
            else:
                to_create.append({**entry, "begin": start, "end": finish})

            rows.append([
                target_date.isoformat(),
                start.strftime("%a"),
                f"{start.strftime('%H:%M')}-{finish.strftime('%H:%M')}",
                f"{slot.duration.total_seconds() / 3600:.2f}h",
                entity_name(entry["project"].get("name")),
                entity_name(entry["activity"].get("name")),
                slot.description,
                "skip (exists)" if duplicate else ("dry-run" if dry_run else "book"),
            ])

    total_hours = sum(
        entry["slot"].duration.total_seconds() for entry in to_create
    ) / 3600

    click.echo(render_table(
        rows,
        ["date", "day", "time", "hours", "project", "activity", "description", "action"],
    ))
    click.echo(
        f"\n{len(target_dates)} day(s), {len(to_create)} entries to create "
        f"({total_hours:.2f} h), {skipped} already present."
    )

    if dry_run:
        click.echo("DRY-RUN: nothing was created.")
        return

    if not to_create:
        click.echo("Nothing to do.")
        return

    if not yes and len(to_create) > 1:
        click.confirm(f"Create {len(to_create)} timesheet entries?", abort=True)

    created_count = 0
    for entry in to_create:
        created = run(
            client.create_timesheet,
            begin=entry["begin"],
            end=entry["end"],
            project_id=entry["project"]["id"],
            activity_id=entry["activity"]["id"],
            description=entry["slot"].description,
            tags=tag_list,
            user_id=user_id,
        )
        created_count += 1
        click.echo(
            f"Created entry {created.get('id')}: "
            f"{entry['begin'].strftime('%Y-%m-%d %H:%M')}-{entry['end'].strftime('%H:%M')} "
            f"({entity_name(entry['project'].get('name'))} / "
            f"{entity_name(entry['activity'].get('name'))})"
        )

    click.echo(f"\nDone: {created_count} created, {skipped} skipped.")
