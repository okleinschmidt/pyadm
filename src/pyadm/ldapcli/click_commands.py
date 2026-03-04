import click
import logging
from typing import Optional
from pyadm.config import cluster_config
from pyadm.context_utils import register_context_commands
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


register_context_commands(ldap_context, "LDAP", "LDAP")


# Import commands from separate files to register with Click
from pyadm.ldapcli.user_commands import *
from pyadm.ldapcli.group_commands import *
from pyadm.ldapcli.member_commands import *
