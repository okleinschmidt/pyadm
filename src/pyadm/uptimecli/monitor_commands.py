"""Monitor commands: list, inspect, create, edit, pause/resume and delete."""

from typing import Any, Dict, List, Optional

import click

from pyadm import output
from pyadm.table import echo_json, echo_table, render_table, rows_from, select_fields
from pyadm.uptimecli.click_commands import (
    confirm_change,
    echo_details,
    get_client,
    run,
    uptimecli,
)
from pyadm.uptimecli.uptime import enum_value, status_name

DEFAULT_FIELDS = ["id", "name", "type", "target", "interval", "active", "status"]

# The monitor types of Uptime Kuma 1.23. Listed here rather than imported from
# uptime_kuma_api so that '--help' works without the package installed.
MONITOR_TYPES = [
    "http", "keyword", "json-query", "port", "ping", "dns", "docker", "push",
    "group", "grpc-keyword", "real-browser", "steam", "gamedig", "mqtt",
    "kafka-producer", "sqlserver", "postgres", "mysql", "mongodb", "radius",
    "redis", "tailscale-ping",
]

HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


def format_notifications(value: Any) -> str:
    """Render the attached notifications, which the API returns as list or map."""
    if isinstance(value, dict):
        return ", ".join(str(key) for key, enabled in value.items() if enabled)
    if isinstance(value, list):
        return ", ".join(str(entry) for entry in value)
    return ""


# Which field holds the target, per monitor type. Uptime Kuma stores a default
# "https://" in 'url' for every monitor, so a type that does not check a URL
# has to be looked up by its own field rather than by "first field that is set".
TARGET_FIELDS = {
    "http": ("url",),
    "keyword": ("url",),
    "json-query": ("url",),
    "real-browser": ("url",),
    "grpc-keyword": ("grpcUrl",),
    "port": ("hostname",),
    "ping": ("hostname",),
    "dns": ("hostname",),
    "steam": ("hostname",),
    "gamedig": ("hostname",),
    "mqtt": ("hostname",),
    "radius": ("hostname",),
    "tailscale-ping": ("hostname",),
    "docker": ("docker_container",),
    "sqlserver": ("databaseConnectionString",),
    "postgres": ("databaseConnectionString",),
    "mysql": ("databaseConnectionString",),
    "mongodb": ("databaseConnectionString",),
    "redis": ("databaseConnectionString",),
    "kafka-producer": ("kafkaProducerBrokers",),
    # A group has children rather than a target, and a push monitor is called
    # by the monitored host itself.
    "group": (),
    "push": (),
}

# Beyond this a target is shortened, unless --full was given. Long enough for
# a hostname or a plain URL, short enough to keep the columns aligned.
TARGET_MAX_LENGTH = 60


def shorten(value: str, limit: int = TARGET_MAX_LENGTH) -> str:
    """Cut an over-long value, keeping its beginning."""
    if limit <= 0 or len(value) <= limit:
        return value
    return value[:limit - 3] + "..."


def monitor_target(monitor: Dict[str, Any]) -> str:
    """What a monitor watches, whatever its type calls that field."""
    monitor_type = str(enum_value(monitor.get("type")) or "")
    keys = TARGET_FIELDS.get(
        monitor_type,
        # An unknown type: fall back to the fields the known ones use.
        ("url", "grpcUrl", "hostname", "docker_container", "databaseConnectionString"),
    )
    for key in keys:
        value = monitor.get(key)
        if not value:
            continue
        if key == "hostname":
            broker = str(value)
            return f"{broker}:{monitor['port']}" if monitor.get("port") else broker
        if isinstance(value, list):
            return ", ".join(str(entry) for entry in value)
        return str(value)
    return ""


def monitor_rows(monitors: List[Dict[str, Any]], statuses: Dict[Any, str],
                 full: bool = False) -> List[Dict[str, Any]]:
    """Flatten monitors into the fields the table and -o/--output know about."""
    rows = []
    for monitor in monitors:
        rows.append({
            "id": monitor.get("id"),
            "name": monitor.get("name", ""),
            "type": enum_value(monitor.get("type")) or "",
            "target": monitor_target(monitor) if full
                      else shorten(monitor_target(monitor)),
            "interval": monitor.get("interval", ""),
            "active": output.monitor_status(
                "active" if monitor.get("active", True) else "paused"
            ),
            "status": output.monitor_status(statuses.get(monitor.get("id"), "")),
            "parent": monitor.get("parent") or "",
            "description": (monitor.get("description") or "") if full
                           else shorten(monitor.get("description") or ""),
            "tags": ", ".join(
                str(tag.get("name", "")) for tag in monitor.get("tags") or []
            ),
            "retries": monitor.get("maxretries", ""),
        })
    return rows


def current_statuses(client) -> Dict[Any, str]:
    """Last heartbeat status per monitor ID, as a name ('up', 'down', ...)."""
    statuses: Dict[Any, str] = {}
    for monitor_id, beats in (run(client.heartbeats) or {}).items():
        if not beats:
            continue
        try:
            key = int(monitor_id)
        except (TypeError, ValueError):
            key = monitor_id
        statuses[key] = status_name(beats[-1].get("status"))
    return statuses


@uptimecli.group("monitor", context_settings={'help_option_names': ['-h', '--help']})
def monitor():
    """Create and manage monitors.

    \b
    Examples:
        pyadm uptime monitor list
        pyadm uptime monitor list --down
        pyadm uptime monitor search vpn
        pyadm uptime monitor show web
        pyadm uptime monitor add web --url https://example.org -N "Ops mail"
        pyadm uptime monitor add db --type port --hostname db.example.org --port 5432
        pyadm uptime monitor beats web --hours 6
        pyadm uptime monitor pause web
    """
    pass


def listing_options(command):
    """The filters, sorting and output options of 'monitor list' and 'monitor search'."""
    for option in reversed([
        click.option("--type", "-t", "monitor_type", default=None,
                     help="Only monitors of this type"),
        click.option("--tag", default=None, help="Only monitors carrying this tag"),
        click.option("--down", is_flag=True, help="Only monitors that are currently down"),
        click.option("--paused", is_flag=True, help="Only paused monitors"),
        click.option("--sort", default="name", show_default=True,
                     type=click.Choice(["id", "name", "type", "status"]),
                     help="Sort by this column"),
        click.option("--full", is_flag=True,
                     help="Show long targets in full instead of shortened"),
        click.option("--output", "-o", "fields_option", default=None,
                     help="Comma-separated list of columns to show"),
        click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON"),
    ]):
        command = option(command)
    return command


def echo_monitors(search, monitor_type, tag, down, paused, sort, full,
                  fields_option, as_json, empty: str) -> None:
    """Filter, sort and print the monitor listing."""
    client = get_client()
    monitors = run(client.list_monitors)
    statuses = current_statuses(client)

    if monitor_type:
        wanted = monitor_type.strip().lower()
        monitors = [
            m for m in monitors if str(enum_value(m.get("type"))).lower() == wanted
        ]
    if tag:
        wanted = tag.strip().lower()
        monitors = [
            m for m in monitors
            if any(wanted == str(t.get("name", "")).lower() for t in m.get("tags") or [])
        ]
    if search:
        needle = search.strip().lower()
        monitors = [
            m for m in monitors
            if needle in str(m.get("name", "")).lower()
            or needle in monitor_target(m).lower()
            or needle in str(enum_value(m.get("type"))).lower()
        ]
    if down:
        monitors = [m for m in monitors if statuses.get(m.get("id")) == "down"]
    if paused:
        monitors = [m for m in monitors if not m.get("active", True)]

    if as_json:
        echo_json(monitors)
        return

    sort_keys = {
        "id": lambda m: m.get("id") or 0,
        "name": lambda m: str(m.get("name", "")).lower(),
        "type": lambda m: str(enum_value(m.get("type")) or ""),
        "status": lambda m: statuses.get(m.get("id"), ""),
    }
    monitors = sorted(monitors, key=sort_keys[sort])

    fields = select_fields(fields_option, DEFAULT_FIELDS)
    echo_table(rows_from(monitor_rows(monitors, statuses, full), fields), fields,
               empty=empty)


@monitor.command("list")
@click.option("--search", "-s", default=None, help="Filter by name, target or type")
@listing_options
def list_monitors(search, monitor_type, tag, down, paused, sort, full,
                  fields_option, as_json):
    """List the monitors of the instance.

    \b
    Examples:
        pyadm uptime monitor list
        pyadm uptime monitor list --down
        pyadm uptime monitor list --type http --tag prod
        pyadm uptime monitor list --sort id --full
    """
    echo_monitors(search, monitor_type, tag, down, paused, sort, full,
                  fields_option, as_json, empty="No monitors found.")


@monitor.command("search")
@click.argument("term")
@listing_options
def search_monitors(term, monitor_type, tag, down, paused, sort, full,
                    fields_option, as_json):
    """Find monitors whose name, target or type contains TERM.

    The same listing as 'monitor list', with the search term as an argument
    instead of an option. All filters of the listing apply here as well.

    \b
    Examples:
        pyadm uptime monitor search vpn
        pyadm uptime monitor search datenreisende.org --full
        pyadm uptime monitor search k3s --down
    """
    echo_monitors(term, monitor_type, tag, down, paused, sort, full,
                  fields_option, as_json,
                  empty=f"No monitors matching '{term}'.")


@monitor.command("show")
@click.argument("monitor_id")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def show_monitor(monitor_id, as_json):
    """Show one monitor in detail. MONITOR_ID is an ID or a name."""
    client = get_client()
    data = run(client.resolve_monitor, monitor_id)
    if as_json:
        echo_json(data)
        return

    statuses = current_statuses(client)
    uptimes = run(client.uptime).get(data.get("id"), {}) or {}

    def percent(window: Any) -> str:
        value = uptimes.get(window)
        if value is None:
            return ""
        return f"{float(value) * 100:.2f}%"

    echo_details([
        ("Id", data.get("id")),
        ("Name", data.get("name")),
        ("Type", enum_value(data.get("type"))),
        ("Target", monitor_target(data)),
        ("Description", data.get("description") or ""),
        ("Status", output.monitor_status(statuses.get(data.get("id"), ""))),
        ("Active", output.monitor_status("active" if data.get("active", True) else "paused")),
        ("Interval", f"{data.get('interval')}s" if data.get("interval") else ""),
        ("Retries", data.get("maxretries")),
        ("Retry interval", f"{data.get('retryInterval')}s" if data.get("retryInterval") else ""),
        ("Upside down", "yes" if data.get("upsideDown") else "no"),
        ("Uptime 24h", percent(24)),
        ("Uptime 30d", percent(720)),
        ("Tags", ", ".join(str(t.get("name", "")) for t in data.get("tags") or [])),
        ("Notifications", format_notifications(data.get("notificationIDList"))),
    ])


@monitor.command("beats")
@click.argument("monitor_id")
@click.option("--hours", "-H", default=24, show_default=True,
              help="How many hours of history to show")
@click.option("--limit", "-l", default=20, show_default=True,
              help="Show only the most recent N beats (0 for all)")
@click.option("--important", is_flag=True, help="Only status changes")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def monitor_beats(monitor_id, hours, limit, important, as_json):
    """Show recent heartbeats of a monitor. MONITOR_ID is an ID or a name."""
    client = get_client()
    resolved = run(client.resolve_monitor, monitor_id)
    beats = run(client.monitor_beats, int(resolved["id"]), hours)

    if important:
        beats = [beat for beat in beats if beat.get("important")]
    if limit:
        beats = beats[-limit:]

    if as_json:
        echo_json(beats)
        return

    rows = [
        [beat.get("time", ""),
         output.monitor_status(status_name(beat.get("status"))),
         "" if beat.get("ping") is None else f"{beat.get('ping')} ms",
         beat.get("msg") or ""]
        for beat in beats
    ]
    echo_table(rows, ["time", "status", "ping", "msg"],
               empty=f"No heartbeats in the last {hours} hours.")


# Options shared by 'monitor add' and 'monitor edit'. The defaults live in
# 'add' only: an edit must not silently reset a field the user did not name.
def monitor_options(creating: bool):
    """Attach the monitor fields as options, with defaults only when creating."""

    def decorator(command):
        for option in reversed([
            click.option("--type", "-t", "monitor_type", type=click.Choice(MONITOR_TYPES),
                         default="http" if creating else None,
                         show_default=creating, help="Monitor type"),
            click.option("--url", "-u", default=None,
                         help="URL to check (http, keyword, json-query, real-browser)"),
            click.option("--hostname", "-H", default=None,
                         help="Host to check (port, ping, dns, steam, mqtt, radius)"),
            click.option("--port", "-P", type=int, default=None, help="Port to check"),
            click.option("--keyword", "-k", default=None,
                         help="Keyword the response must contain (keyword monitors)"),
            click.option("--invert-keyword", is_flag=True, default=None,
                         help="Fail when the keyword is present instead"),
            click.option("--json-path", default=None, help="JSON path (json-query monitors)"),
            click.option("--expected-value", default=None,
                         help="Expected value at the JSON path (json-query monitors)"),
            click.option("--docker-container", default=None,
                         help="Container name (docker monitors)"),
            click.option("--docker-host", type=int, default=None,
                         help="Docker host ID (docker monitors)"),
            click.option("--dns-resolve-server", default=None,
                         help="Resolver to ask (dns monitors)"),
            click.option("--dns-resolve-type", default=None,
                         help="Record type to resolve (dns monitors)"),
            click.option("--description", "-d", default=None, help="Free-text description"),
            click.option("--interval", "-i", type=int, default=60 if creating else None,
                         show_default=creating, help="Check interval in seconds"),
            click.option("--retries", type=int, default=1 if creating else None,
                         show_default=creating, help="Retries before the monitor goes down"),
            click.option("--retry-interval", type=int, default=None,
                         help="Seconds between retries (default: the check interval)"),
            click.option("--resend-interval", type=int, default=None,
                         help="Resend the notification every N checks while down"),
            click.option("--method", type=click.Choice(HTTP_METHODS, case_sensitive=False),
                         default=None, help="HTTP method"),
            click.option("--body", default=None, help="HTTP request body"),
            click.option("--headers", default=None, help="HTTP request headers as JSON"),
            click.option("--accepted-status", default=None,
                         help="Accepted status code ranges, e.g. '200-299,404'"),
            click.option("--max-redirects", type=int, default=None,
                         help="How many redirects to follow"),
            click.option("--ignore-tls", is_flag=True, default=None,
                         help="Ignore TLS/SSL certificate errors"),
            click.option("--expiry-notification", is_flag=True, default=None,
                         help="Warn before the TLS certificate expires"),
            click.option("--upside-down", is_flag=True, default=None,
                         help="Treat a failing check as up and the other way round"),
            click.option("--parent", "-p", default=None,
                         help="Put the monitor into this group monitor (ID or name)"),
            click.option("--notification", "-N", "notifications", multiple=True,
                         help="Notification to attach (ID or name, repeatable)"),
            click.option("--tag", "tags", multiple=True,
                         help="Tag to attach (ID or name, repeatable)"),
        ]):
            command = option(command)
        return command

    return decorator


def collect_monitor_payload(client, options: Dict[str, Any],
                            name: Optional[str] = None,
                            creating: bool = False) -> Dict[str, Any]:
    """Translate the command line options into the API's field names."""
    mapping = {
        "monitor_type": "type",
        "url": "url",
        "hostname": "hostname",
        "port": "port",
        "keyword": "keyword",
        "invert_keyword": "invertKeyword",
        "json_path": "jsonPath",
        "expected_value": "expectedValue",
        "docker_container": "docker_container",
        "docker_host": "docker_host",
        "dns_resolve_server": "dns_resolve_server",
        "dns_resolve_type": "dns_resolve_type",
        "description": "description",
        "interval": "interval",
        "retries": "maxretries",
        "retry_interval": "retryInterval",
        "resend_interval": "resendInterval",
        "body": "body",
        "headers": "headers",
        "max_redirects": "maxredirects",
        "ignore_tls": "ignoreTls",
        "expiry_notification": "expiryNotification",
        "upside_down": "upsideDown",
    }

    payload: Dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    for option_name, field in mapping.items():
        value = options.get(option_name)
        if value is not None:
            payload[field] = value

    if options.get("method"):
        payload["method"] = str(options["method"]).upper()
    if options.get("accepted_status"):
        payload["accepted_statuscodes"] = [
            code.strip() for code in str(options["accepted_status"]).split(",") if code.strip()
        ]
    if options.get("parent"):
        payload["parent"] = int(run(client.resolve_monitor, options["parent"])["id"])
    if options.get("notifications"):
        payload["notificationIDList"] = run(client.resolve_notifications,
                                            list(options["notifications"]))

    # A new monitor retries at its check interval unless told otherwise. On an
    # edit the stored retry interval is left alone: only what was asked for
    # changes.
    if creating and "interval" in payload and "retryInterval" not in payload:
        payload["retryInterval"] = payload["interval"]

    return payload


@monitor.command("add")
@click.argument("name")
@monitor_options(creating=True)
@click.option("--paused", is_flag=True, help="Create the monitor in paused state")
@click.option("--dry-run", is_flag=True, help="Show what would be created")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def add_monitor(name, paused, dry_run, as_json, **options):
    """Create a monitor named NAME.

    \b
    Examples:
        pyadm uptime monitor add web --url https://example.org
        pyadm uptime monitor add api --type keyword --url https://api.example.org \\
            --keyword '"status":"ok"' --interval 120
        pyadm uptime monitor add db --type port --hostname db.example.org --port 5432
        pyadm uptime monitor add gw --type ping --hostname 10.0.0.1 -N "Ops mail"
    """
    client = get_client()
    payload = collect_monitor_payload(client, options, name=name, creating=True)
    tags = run(client.resolve_tags, list(options.get("tags") or []))

    if dry_run:
        rows = [[key, payload[key]] for key in sorted(payload)]
        if tags:
            rows.append(["tags", ", ".join(str(tag.get("name")) for tag in tags)])
        click.echo(f"Would create monitor '{name}':")
        click.echo(render_table(rows, ["field", "value"]))
        return

    monitor_id = run(client.add_monitor, **payload)
    for tag in tags:
        run(client.add_monitor_tag, int(tag["id"]), monitor_id)
    if paused:
        run(client.pause_monitor, monitor_id)

    if as_json:
        echo_json(run(client.get_monitor, monitor_id))
        return
    click.echo(
        f"Created monitor '{name}' (ID {monitor_id})"
        f"{' in paused state' if paused else ''}."
    )


@monitor.command("edit")
@click.argument("monitor_id")
@click.option("--name", default=None, help="New name")
@monitor_options(creating=False)
@click.option("--dry-run", is_flag=True, help="Show what would be changed")
def edit_monitor(monitor_id, name, dry_run, **options):
    """Change a monitor. MONITOR_ID is an ID or a name.

    Only the options you pass are changed; everything else stays as it is.

    \b
    Examples:
        pyadm uptime monitor edit web --interval 120
        pyadm uptime monitor edit web --url https://new.example.org
    """
    client = get_client()
    resolved = run(client.resolve_monitor, monitor_id)
    payload = collect_monitor_payload(client, options, name=name)
    tags = run(client.resolve_tags, list(options.get("tags") or []))

    if not payload and not tags:
        raise click.ClickException("Nothing to change. Pass at least one option.")

    if dry_run:
        rows = [[key, payload[key]] for key in sorted(payload)]
        if tags:
            rows.append(["tags", ", ".join(str(tag.get("name")) for tag in tags)])
        click.echo(f"Would change monitor '{resolved.get('name')}' (ID {resolved.get('id')}):")
        click.echo(render_table(rows, ["field", "value"]))
        return

    # edit_monitor reads the monitor first and merges, so only the changed
    # fields have to be sent.
    if payload:
        run(client.edit_monitor, int(resolved["id"]), **payload)
    for tag in tags:
        run(client.add_monitor_tag, int(tag["id"]), int(resolved["id"]))
    click.echo(f"Updated monitor '{resolved.get('name')}' (ID {resolved.get('id')}).")


def _set_monitor_state(monitor_ids, all_monitors, yes, dry_run, resume: bool) -> None:
    """Shared body of 'monitor pause' and 'monitor resume'."""
    client = get_client()
    verb = "Resume" if resume else "Pause"

    if all_monitors:
        monitors = run(client.list_monitors)
        monitors = [m for m in monitors if bool(m.get("active", True)) != resume]
    elif monitor_ids:
        monitors = run(client.resolve_monitors, list(monitor_ids))
    else:
        raise click.ClickException("Name at least one monitor, or pass --all.")

    if not monitors:
        click.echo(f"No monitors to {verb.lower()}.")
        return

    names = ", ".join(f"{m.get('name')} (ID {m.get('id')})" for m in monitors)
    if dry_run:
        click.echo(f"Would {verb.lower()} {len(monitors)} monitor(s): {names}")
        return
    if len(monitors) > 1 or all_monitors:
        confirm_change(f"{verb} {len(monitors)} monitor(s): {names}?", yes)

    action = client.resume_monitor if resume else client.pause_monitor
    for entry in monitors:
        run(action, int(entry["id"]))
        click.echo(f"{verb}d monitor '{entry.get('name')}' (ID {entry.get('id')}).")


@monitor.command("pause")
@click.argument("monitor_ids", metavar="[MONITOR]...", nargs=-1)
@click.option("--all", "-a", "all_monitors", is_flag=True, help="Pause every active monitor")
@click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation")
@click.option("--dry-run", is_flag=True, help="Show what would be paused")
def pause_monitor(monitor_ids, all_monitors, yes, dry_run):
    """Pause monitors. MONITOR is an ID or a name, repeatable."""
    _set_monitor_state(monitor_ids, all_monitors, yes, dry_run, resume=False)


@monitor.command("resume")
@click.argument("monitor_ids", metavar="[MONITOR]...", nargs=-1)
@click.option("--all", "-a", "all_monitors", is_flag=True, help="Resume every paused monitor")
@click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation")
@click.option("--dry-run", is_flag=True, help="Show what would be resumed")
def resume_monitor(monitor_ids, all_monitors, yes, dry_run):
    """Resume paused monitors. MONITOR is an ID or a name, repeatable."""
    _set_monitor_state(monitor_ids, all_monitors, yes, dry_run, resume=True)


@monitor.command("delete")
@click.argument("monitor_ids", metavar="MONITOR...", nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted")
def delete_monitor(monitor_ids, yes, dry_run):
    """Delete monitors, including their history. MONITOR is an ID or a name."""
    client = get_client()
    monitors = run(client.resolve_monitors, list(monitor_ids))
    names = ", ".join(f"{m.get('name')} (ID {m.get('id')})" for m in monitors)

    if dry_run:
        click.echo(f"Would delete {len(monitors)} monitor(s): {names}")
        return

    confirm_change(
        f"Delete {len(monitors)} monitor(s) and their history: {names}?", yes
    )
    for entry in monitors:
        run(client.delete_monitor, int(entry["id"]))
        click.echo(f"Deleted monitor '{entry.get('name')}' (ID {entry.get('id')}).")
