import click
import logging
from typing import Optional
from pyadm.config import cluster_config
from pyadm.ldapcli.ldap import LDAPClient

# Holds the selected LDAP server name
selected_ldap = {"name": None}


@click.group("ldap", context_settings={'help_option_names': ['-h', '--help']})
@click.option("--server", "-s", default=None, help="Select LDAP server by name (section in config)")
def ldapcli(server):
    """Query and manage LDAP/Active Directory with multi-server support.
    
    Provides comprehensive tools for user and group management, membership
    queries, and directory operations across multiple LDAP/AD servers.
    
    \b
    Examples:
        pyadm ldap user jdoe                           # Get user information
        pyadm ldap groups jdoe                        # Show user's group memberships
        pyadm ldap members "Domain Admins"            # List group members
        pyadm ldap user-exists jdoe                   # Check if user exists
        pyadm ldap group-exists "HR Team"             # Check if group exists
        
    \b
    Multi-server usage:
        pyadm ldap -s production user jdoe            # Use production LDAP server
        pyadm ldap -s staging groups jdoe             # Use staging LDAP server
    """
    selected_ldap["name"] = server


def get_ldap_client(password: Optional[str] = None):
    cfg = cluster_config.get_cluster(selected_ldap["name"], prefix="LDAP")
    return LDAPClient(cfg, password=password)


# Import commands from separate files to register with Click
from pyadm.ldapcli.user_commands import *
from pyadm.ldapcli.group_commands import *
from pyadm.ldapcli.member_commands import *
