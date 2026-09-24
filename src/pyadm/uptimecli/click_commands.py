"""Click commands for the Uptime Kuma module."""

from datetime import datetime
from typing import Any, Dict, List, Optional

import click

from pyadm import output
from pyadm.config import cluster_config
from pyadm.context_utils import register_context_commands
from pyadm.table import echo_json, echo_table
from pyadm.uptimecli.uptime import UptimeClient, UptimeError, enum_value

# Holds the context selected on the group, for the commands to pick up.
selected_context: Dict[str, Optional[str]] = {"name": None}

# The open client of the running command. Socket.IO keeps a background thread
# alive, so the connection is opened once and closed when the command ends.
_client: Dict[str, Optional[UptimeClient]] = {"instance": None}


@click.group("uptime", context_settings={'help_option_names': ['-h', '--help']})
@click.option("--context", "-c", default=None, help="Select Uptime Kuma context name")
@click.pass_context
def uptimecli(ctx, context):
    """Manage Uptime Kuma: monitors, maintenance windows and notifications.

    \b
    Examples:
        pyadm uptime info                                 # Instance version and settings
        pyadm uptime monitor list                         # List monitors
        pyadm uptime monitor show web                     # Details of one monitor
        pyadm uptime monitor add web --url https://a.org  # Create an HTTP monitor
        pyadm uptime monitor pause web                    # Pause a monitor

    \b
    Downtimes:
        pyadm uptime downtime -m web -m api -d 2h         # Two hours from now
        pyadm uptime downtime -m web -s 22:00 -d 90m      # Tonight at 22:00
        pyadm uptime maintenance list                     # Scheduled windows
        pyadm uptime maintenance add "Patch night" -m web \\
            --strategy recurring-weekday -w sat --window 02:00-04:00

    \b
    Multi-instance usage:
        pyadm uptime -c prod monitor list
        pyadm uptime context use prod
    """
    selected_context["name"] = context
    # Every command runs one connection; close it when the command is done.
    ctx.call_on_close(close_client)


def get_context_config() -> Dict[str, str]:
    """Configuration section of the active Uptime Kuma context."""
    try:
        return cluster_config.get_cluster(selected_context["name"], prefix="UPTIME")
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


def get_client() -> UptimeClient:
    """Connect to the active Uptime Kuma context, reusing an open connection."""
    if _client["instance"] is not None:
        return _client["instance"]

    cfg = get_context_config()
    output.init_colors(cfg)
    try:
        client = UptimeClient(cfg)
        client.connect()
    except UptimeError as exc:
        raise click.ClickException(str(exc)) from exc

    _client["instance"] = client
    return client


def close_client() -> None:
    """Close the connection of the finished command."""
    client = _client["instance"]
    if client is not None:
        client.close()
        _client["instance"] = None


def get_timezone_option() -> Optional[str]:
    """Timezone maintenance windows are scheduled in, if the context sets one."""
    value = (get_context_config().get("timezone") or "").strip()
    return value or None


def local_timezone_name() -> str:
    """Name of the system timezone, for display when the context sets none."""
    tzinfo = datetime.now().astimezone().tzinfo
    return str(tzinfo) if tzinfo else "UTC"


def run(action, *args, **kwargs):
    """Call the API and turn Uptime Kuma errors into clean Click errors."""
    try:
        return action(*args, **kwargs)
    except UptimeError as exc:
        raise click.ClickException(str(exc)) from exc


def echo_listing(rows: List[List[Any]], headers: List[str], as_json: bool,
                 json_data: Any, empty: str = "No entries found.") -> None:
    """Print a listing as a table, or the raw API data when --json was given."""
    if as_json:
        echo_json(json_data)
        return
    echo_table(rows, headers, empty=empty)


def echo_details(pairs: List[tuple]) -> None:
    """Print a single object as 'Label: value' lines."""
    for label, value in pairs:
        click.echo(f"{label}: {'' if value is None else value}")


def confirm_change(message: str, yes: bool) -> None:
    """Ask before a change unless --yes was given."""
    if yes:
        return
    if not click.confirm(message):
        raise click.Abort()


@uptimecli.group("context", context_settings={'help_option_names': ['-h', '--help']})
def uptime_context():
    """Manage saved Uptime Kuma contexts."""
    pass


register_context_commands(uptime_context, "UPTIME", "Uptime Kuma")


# ----------------------------------------------------------------------
# Instance information
# ----------------------------------------------------------------------
@uptimecli.command("ping")
def ping():
    """Check that the configured instance answers and accepts the credentials."""
    client = get_client()
    info = run(client.info)
    monitors = run(client.list_monitors)
    click.echo(
        f"OK - {client.url} (version: {info.get('version', 'unknown')}, "
        f"{len(monitors)} monitors)"
    )


@uptimecli.command("info")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def info(as_json):
    """Show version and configuration of the Uptime Kuma instance."""
    data = run(get_client().info)
    if as_json:
        echo_json(data)
        return
    echo_details([
        ("Url", get_client().url),
        ("Version", data.get("version")),
        ("Latest version", data.get("latestVersion")),
        ("Primary base url", data.get("primaryBaseURL") or ""),
        ("Server timezone", data.get("serverTimezone") or ""),
        ("Timezone offset", data.get("serverTimezoneOffset") or ""),
    ])


@uptimecli.command("notifications")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def notifications(as_json):
    """List the configured notification providers."""
    data = run(get_client().list_notifications)
    rows = [
        [n.get("id"), n.get("name"), enum_value(n.get("type")) or "",
         "yes" if n.get("isDefault") else "no",
         "yes" if n.get("active", True) else "no"]
        for n in data
    ]
    echo_listing(rows, ["id", "name", "type", "default", "active"], as_json, data,
                 empty="No notifications found.")


@uptimecli.command("tags")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def tags(as_json):
    """List the tags known to the instance."""
    data = run(get_client().list_tags)
    rows = [[t.get("id"), t.get("name"), t.get("color") or ""] for t in data]
    echo_listing(rows, ["id", "name", "color"], as_json, data, empty="No tags found.")


@uptimecli.command("status-pages")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def status_pages(as_json):
    """List the status pages of the instance."""
    data = run(get_client().list_status_pages)
    rows = [
        [p.get("id"), p.get("slug") or "", p.get("title") or "",
         "yes" if p.get("published", True) else "no"]
        for p in data
    ]
    echo_listing(rows, ["id", "slug", "title", "published"], as_json, data,
                 empty="No status pages found.")


# Import the command groups so they register with the Click group
from pyadm.uptimecli.monitor_commands import *  # noqa: E402,F401,F403
from pyadm.uptimecli.maintenance_commands import *  # noqa: E402,F401,F403
