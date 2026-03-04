import click
import logging
from typing import Optional
from tabulate import tabulate
from pyadm.config import cluster_config
from pyadm.ldapcli.ldap import LDAPClient

# Holds the selected LDAP context name
selected_ldap_context = {"name": None}


@click.group("ldap", context_settings={'help_option_names': ['-h', '--help']})
@click.option("--context", "-c", default=None, help="Select LDAP context name")
def ldapcli(context):
    """Query and manage LDAP/Active Directory with multi-server support.
    
    Provides comprehensive tools for user and group management, membership
    queries, and directory operations across multiple LDAP/AD servers.
    
    \b
    Examples:
        pyadm ldap user jdoe                           # Get user information
        pyadm ldap groups jdoe                        # Show user's group memberships
        pyadm ldap members "Domain Admins"            # List group members
        pyadm ldap user --list                        # List all users
        pyadm ldap groups --list                      # List all groups
        pyadm ldap user-exists jdoe                   # Check if user exists
        pyadm ldap group-exists "HR Team"             # Check if group exists
        
    \b
    Multi-server usage:
        pyadm ldap -c production user jdoe          # Use production LDAP context
        pyadm ldap -c staging groups jdoe           # Use staging LDAP context
    """
    selected_ldap_context["name"] = context


def get_ldap_client(password: Optional[str] = None):
    try:
        cfg = cluster_config.get_cluster(selected_ldap_context["name"], prefix="LDAP")
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    return LDAPClient(cfg, password=password)


@ldapcli.group("context", context_settings={'help_option_names': ['-h', '--help']})
def ldap_context():
    """Manage saved LDAP contexts."""
    pass


@ldap_context.command("list")
def list_contexts():
    """List available LDAP contexts."""
    try:
        contexts = cluster_config.list_contexts(prefix="LDAP")
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    if not contexts:
        click.echo("No LDAP contexts found.")
        return

    active = cluster_config.get_active_context(prefix="LDAP")
    rows = []
    for entry in contexts:
        marker = "*" if active and entry["name"].lower() == active.lower() else ""
        rows.append([marker, entry["name"], entry["section"]])
    click.echo(tabulate(rows, headers=["ACTIVE", "CONTEXT", "CONFIG SECTION"], tablefmt="plain"))


@ldap_context.command("current")
def current_context():
    """Show the currently active LDAP context."""
    try:
        resolved = cluster_config.resolve_context(prefix="LDAP")
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{resolved['name']} (section: {resolved['section']})")


@ldap_context.command("use")
@click.argument("context_name")
def use_context(context_name):
    """Switch active LDAP context."""
    try:
        selected = cluster_config.set_active_context(prefix="LDAP", name=context_name)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Active LDAP context set to: {selected}")


# Import commands from separate files to register with Click
from pyadm.ldapcli.user_commands import *
from pyadm.ldapcli.group_commands import *
from pyadm.ldapcli.member_commands import *
