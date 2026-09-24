"""Click commands for the Kimai module."""

from datetime import datetime
from typing import Any, Dict, List, Optional

import click
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pyadm import output
from pyadm.table import echo_json, echo_table, render_table
from pyadm.config import cluster_config
from pyadm.context_utils import register_context_commands
from pyadm.kimaicli.booking import PRESET_PREFIX
from pyadm.kimaicli.kimai import KimaiClient, KimaiError, entity_name

# Holds the context selected on the group, for the commands to pick up.
selected_context: Dict[str, Optional[str]] = {"name": None}


@click.group("kimai", context_settings={'help_option_names': ['-h', '--help']})
@click.option("--context", "-c", default=None, help="Select Kimai context name")
def kimaicli(context):
    """Track time in Kimai: master data, timesheets and recurring bookings.

    \b
    Examples:
        pyadm kimai ping                          # Verify URL and credentials
        pyadm kimai projects                      # List projects
        pyadm kimai activities -p "Internal"      # Activities of a project
        pyadm kimai timesheet list                # Recent timesheet entries
        pyadm kimai timesheet start -p 1 -a 2     # Start tracking now
        pyadm kimai timesheet stop                # Stop what is running
        pyadm kimai book -p 1 -a 2 -s 09:00+2h    # Book a slot today

    \b
    Recurring bookings:
        pyadm kimai book --preset saturday --month 2026-10
        pyadm kimai book -p "Support" -a "Maintenance" \\
            -s "09:00-11:45|Slot 1" -s "11:45-14:30|Slot 2" \\
            --start-month 2026-01 --end-month 2026-03 -w sat --dry-run

    \b
    Multi-instance usage:
        pyadm kimai -c work projects
        pyadm kimai context use work
    """
    selected_context["name"] = context


def get_client() -> KimaiClient:
    """Build a client for the active Kimai context."""
    try:
        cfg = cluster_config.get_cluster(selected_context["name"], prefix="KIMAI")
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    output.init_colors(cfg)
    try:
        return KimaiClient(cfg)
    except KimaiError as exc:
        raise click.ClickException(str(exc)) from exc


def get_context_config() -> Dict[str, str]:
    """Configuration section of the active Kimai context."""
    try:
        return cluster_config.get_cluster(selected_context["name"], prefix="KIMAI")
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


def get_timezone(name: Optional[str] = None) -> ZoneInfo:
    """Resolve the timezone to book in: option, context config, then system local."""
    candidate = name or get_context_config().get("timezone")
    if not candidate:
        local = datetime.now().astimezone().tzinfo
        return local if local is not None else ZoneInfo("UTC")
    try:
        return ZoneInfo(str(candidate).strip())
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise click.ClickException(f"Unknown timezone '{candidate}': {exc}") from exc


def run(action, *args, **kwargs):
    """Call the API and turn Kimai errors into clean Click errors."""
    try:
        return action(*args, **kwargs)
    except KimaiError as exc:
        raise click.ClickException(str(exc)) from exc


def echo_listing(rows: List[List[Any]], headers: List[str], as_json: bool,
                 json_data: Any, empty: str = "No entries found.") -> None:
    """Print a listing as a table, or the raw API data when --json was given."""
    if as_json:
        echo_json(json_data)
        return
    echo_table(rows, headers, empty=empty)


@kimaicli.group("context", context_settings={'help_option_names': ['-h', '--help']})
def kimai_context():
    """Manage saved Kimai contexts."""
    pass


register_context_commands(kimai_context, "KIMAI", "Kimai")


# ----------------------------------------------------------------------
# Instance information
# ----------------------------------------------------------------------
@kimaicli.command("ping")
def ping():
    """Check that the configured Kimai instance answers and accepts the credentials."""
    client = get_client()
    run(client.ping)
    user = run(client.me)
    click.echo(
        f"OK - {client.base_url} (user: {entity_name(user.get('username'), 'unknown')})"
    )


@kimaicli.command("version")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def version(as_json):
    """Show version information about the Kimai instance."""
    data = run(get_client().version)
    if as_json:
        echo_json(data)
        return
    for key, value in data.items():
        click.echo(f"{key}: {value}")


@kimaicli.command("me")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def me(as_json):
    """Show the user the API credentials belong to."""
    data = run(get_client().me)
    if as_json:
        echo_json(data)
        return
    for label, value in [
        ("Id", data.get("id")),
        ("Username", data.get("username")),
        ("Alias", data.get("alias") or ""),
        ("Title", data.get("title") or ""),
        ("Timezone", data.get("timezone") or ""),
        ("Language", data.get("language") or ""),
        ("Roles", ", ".join(data.get("roles") or [])),
        ("Enabled", data.get("enabled")),
    ]:
        click.echo(f"{label}: {'' if value is None else value}")


# ----------------------------------------------------------------------
# Master data
# ----------------------------------------------------------------------
VISIBILITY = click.Choice(["visible", "hidden", "all"])
VISIBILITY_VALUES = {"visible": "1", "hidden": "2", "all": "3"}


@kimaicli.command("customers")
@click.option("--visibility", type=VISIBILITY, default="visible", help="Which customers to list")
@click.option("--search", "-s", default=None, help="Filter by name")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def customers(visibility, search, as_json):
    """List customers."""
    data = run(get_client().list_customers, visible=VISIBILITY_VALUES[visibility], term=search)
    rows = [
        [c.get("id"), c.get("name"), c.get("number") or "", c.get("country") or "",
         "yes" if c.get("visible") else "no"]
        for c in data
    ]
    echo_listing(rows, ["id", "name", "number", "country", "visible"], as_json, data,
                 empty="No customers found.")


@kimaicli.command("projects")
@click.option("--customer", "-C", default=None, help="Limit to a customer (ID or name)")
@click.option("--visibility", type=VISIBILITY, default="visible", help="Which projects to list")
@click.option("--search", "-s", default=None, help="Filter by name")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def projects(customer, visibility, search, as_json):
    """List projects, optionally limited to one customer."""
    client = get_client()
    customer_id = None
    if customer:
        customer_id = run(client.resolve_customer, customer).get("id")
    data = run(
        client.list_projects,
        customer=customer_id,
        visible=VISIBILITY_VALUES[visibility],
        term=search,
    )
    rows = [
        [p.get("id"), p.get("name"), entity_name(p.get("customer")),
         "yes" if p.get("visible") else "no"]
        for p in data
    ]
    echo_listing(rows, ["id", "name", "customer", "visible"], as_json, data,
                 empty="No projects found.")


@kimaicli.command("activities")
@click.option("--project", "-p", default=None, help="Limit to a project (ID or name)")
@click.option("--visibility", type=VISIBILITY, default="visible", help="Which activities to list")
@click.option("--search", "-s", default=None, help="Filter by name")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def activities(project, visibility, search, as_json):
    """List activities, optionally limited to one project."""
    client = get_client()
    project_id = None
    if project:
        project_id = run(client.resolve_project, project).get("id")
    data = run(
        client.list_activities,
        project=project_id,
        visible=VISIBILITY_VALUES[visibility],
        term=search,
    )
    rows = [
        [a.get("id"), a.get("name"),
         entity_name(a.get("project"), "(global)") if a.get("project") else "(global)",
         "yes" if a.get("visible") else "no"]
        for a in data
    ]
    echo_listing(rows, ["id", "name", "project", "visible"], as_json, data,
                 empty="No activities found.")


@kimaicli.command("tags")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def tags(as_json):
    """List the tags known to the instance."""
    data = run(get_client().list_tags)
    if as_json:
        echo_json(data)
        return
    if not data:
        click.echo("No tags found.")
        return
    for tag in data:
        click.echo(tag)


@kimaicli.command("users")
@click.option("--visibility", type=VISIBILITY, default="visible", help="Which users to list")
@click.option("--json", "-j", "as_json", is_flag=True, help="Output as JSON")
def users(visibility, as_json):
    """List users (needs admin permissions)."""
    data = run(get_client().list_users, visible=VISIBILITY_VALUES[visibility])
    rows = [
        [u.get("id"), u.get("username"), u.get("alias") or "",
         "yes" if u.get("enabled") else "no"]
        for u in data
    ]
    echo_listing(rows, ["id", "username", "alias", "enabled"], as_json, data,
                 empty="No users found.")


@kimaicli.command("presets")
def presets():
    """List the recurring booking presets defined in the configuration."""
    from pyadm.kimaicli.book_commands import list_presets

    entries = list_presets()
    if not entries:
        click.echo(
            f"No booking presets found. Add a [{PRESET_PREFIX}<name>] section with "
            f"'pyadm config edit' (see 'pyadm config generate')."
        )
        return
    rows = [
        [name, cfg.get("project", ""), cfg.get("activity", ""),
         " ".join(cfg.get("slots", "").split()), cfg.get("weekdays", "")]
        for name, cfg in entries
    ]
    click.echo(render_table(rows, ["preset", "project", "activity", "slots", "weekdays"]))


# Import the command groups so they register with the Click group
from pyadm.kimaicli.timesheet_commands import *  # noqa: E402,F401,F403
from pyadm.kimaicli.book_commands import *  # noqa: E402,F401,F403
