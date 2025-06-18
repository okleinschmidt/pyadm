import click
import logging
from typing import Optional
from pyadm.config import cluster_config
from pyadm.ldapcli.ldap import LDAPClient

# Holds the selected LDAP server name
selected_ldap = {"name": None}


@click.group("ldap")
@click.option("--server", "-s", default=None, help="Select LDAP server by name (section in config)")
def ldapcli(server):
    """
    Query LDAP/Active Directory. Multi-server support.
    """
    selected_ldap["name"] = server


def get_ldap_client(password: Optional[str] = None):
    cfg = cluster_config.get_cluster(selected_ldap["name"], prefix="LDAP")
    return LDAPClient(cfg, password=password)


# Import commands from separate files to register with Click
from pyadm.ldapcli.user_commands import *
from pyadm.ldapcli.group_commands import *
from pyadm.ldapcli.member_commands import *
