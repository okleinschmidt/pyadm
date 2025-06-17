
import click
import json
import ldap3
import logging
from typing import Any, Dict, List, Optional
from ldap3.core.exceptions import LDAPException
from pyadm.config import cluster_config

def get_ldap_config(selected: Optional[str] = None) -> Dict[str, Any]:
    """
    Get LDAP config dict for the selected server (section) or default.
    """
    return cluster_config.get_cluster(selected, prefix="LDAP")

def prompt_password_if_needed(ctx, param, value):
    if value is not None:
        return click.prompt("Specify the password for authentication", hide_input=True)
    return None

def ldap_connect(cfg: Dict[str, Any], password: Optional[str] = None, skip_tls_verify: Optional[bool] = None, use_starttls: Optional[bool] = None) -> ldap3.Connection:
    """
    Establish and return an LDAP3 connection using the given config.
    """
    server_kwargs = {}
    if skip_tls_verify is None:
        skip_tls_verify = str(cfg.get('skip_tls_verify', 'false')).lower() in ('1', 'true', 'yes', 'on')
    if use_starttls is None:
        use_starttls = str(cfg.get('use_starttls', 'false')).lower() in ('1', 'true', 'yes', 'on')
    if skip_tls_verify:
        server_kwargs['tls'] = ldap3.Tls(validate=ldap3.ssl.CERT_NONE)
    server = ldap3.Server(cfg['server'], **server_kwargs)
    bind_pw = password if password is not None else cfg.get('bind_password')
    if not bind_pw:
        bind_pw = click.prompt("LDAP password for {}".format(cfg.get('bind_username', cfg.get('username', ''))), hide_input=True)
    conn = ldap3.Connection(server, user=cfg.get('bind_username', cfg.get('username')), password=bind_pw, auto_bind=False)
    conn.open()
    if use_starttls:
        conn.start_tls()
    conn.bind()
    return conn

def ldap_search(cfg: Dict[str, Any], search_filter: str, attributes: Optional[List[str]] = None, password: Optional[str] = None) -> List[Any]:
    """
    Perform an LDAP search and return the result entries.
    """
    try:
        conn = ldap_connect(cfg, password=password)
        base_dn = cfg['base_dn']
        conn.search(base_dn, search_filter, attributes=attributes or [])
        return conn.entries
    except LDAPException as e:
        logging.error(f"LDAP search failed: {e}")
        raise click.ClickException(f"LDAP search failed: {e}")
    except Exception as e:
        logging.error(f"LDAP error: {e}")
        raise click.ClickException(f"LDAP error: {e}")


# Holds the selected LDAP server name
selected_ldap = {"name": None}

@click.group("ldap")
@click.option("--server", "-s", default=None, help="Select LDAP server by name (section in config)")
def ldapcli(server):
    """
    Query LDAP/Active Directory. Multi-server support.
    Use --server/-s to select a config section (e.g. [LDAP], [LDAP_PROD], ...).
    """
    selected_ldap["name"] = server

# show information about a user
@ldapcli.command("user")
@click.argument("username", metavar="[UID, CN, MAIL]")
@click.option("--all", "-a", is_flag=True, default=None, help="Show all attributes")
@click.option("--json", "-j", "json_output", is_flag=True, default=None, help="Output as JSON")
@click.option("--csv", is_flag=True, default=None, help="Output as CSV")
@click.option("--attributes", "-A", default=None, help="Comma-separated list of attributes to show")
def user(username, json_output, csv, all, attributes):
    """
    Show information about a user specified by [UID], [CN], or [MAIL].
    """
    cfg = get_ldap_config(selected_ldap["name"])
    search_filter = f"(|(uid={username})(cn={username})(mail={username}))"
    try:
        if all:
            attrs = ["*"]
        elif attributes:
            attrs = [a.strip() for a in attributes.split(",") if a.strip()]
        else:
            attrs = ["cn", "mail", "memberOf"]
        result = ldap_search(cfg, search_filter, attrs)
        if result:
            if json_output:
                print(result[0].entry_to_json())
            elif csv:
                import csv as _csv
                import sys
                user_info = result[0].entry_attributes_as_dict
                writer = _csv.writer(sys.stdout)
                writer.writerow(user_info.keys())
                writer.writerow([", ".join(map(str, v)) for v in user_info.values()])
            else:
                user_info = result[0].entry_attributes_as_dict
                user_info = {str(attr): [str(value) for value in values] for attr, values in user_info.items()}
                for attr, values in sorted(user_info.items()):
                    if attr == "memberOf" or attr == "objectClass":
                        print(f"{attr}:")
                        for group in values:
                            print(f" - {group}")
                    else:
                        print(f"{attr}: {', '.join(values)}")
        else:
            raise click.ClickException(f"No user found with UID '{username}'.")
    except click.ClickException as e:
        raise e
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise click.ClickException(f"An error occurred: {e}")

# show groups a user belongs to
@ldapcli.command("groups")
@click.argument("username", metavar="[UID, CN, MAIL]")
@click.option("--json", "-j", "json_output", is_flag=True, default=None, help="Output as JSON")
@click.option("--csv", is_flag=True, default=None, help="Output as CSV")
def groups(username, json_output, csv):
    """
    Show groups associated with a user specified by [UID], [CN], or [MAIL].
    """
    cfg = get_ldap_config(selected_ldap["name"])
    search_filter = f"(|(uid={username})(cn={username})(mail={username}))"
    try:
        attributes = ["memberOf"]
        result = ldap_search(cfg, search_filter, attributes)
        if result:
            if json_output:
                print(result[0].entry_to_json())
            elif csv:
                import csv as _csv
                import sys
                group_info = result[0].entry_attributes_as_dict
                writer = _csv.writer(sys.stdout)
                writer.writerow(group_info.keys())
                writer.writerow([", ".join(map(str, v)) for v in group_info.values()])
            else:
                group_info = result[0].entry_attributes_as_dict
                group_info = {str(attr): [str(value) for value in values] for attr, values in group_info.items()}
                for attr, values in sorted(group_info.items()):
                    if attr == "memberOf" or attr == "objectClass":
                        print(f"{attr}:")
                        for group in values:
                            print(f" - {group}")
                    else:
                        print(f"{attr}: {', '.join(values)}")
        else:
            raise click.ClickException(f"No user found with UID '{username}'.")
    except click.ClickException as e:
        raise e
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise click.ClickException(f"An error occurred: {e}")

# show members of a group
@ldapcli.command("members")
@click.argument("group_cn", metavar="[GROUP]")
@click.option("--all", "-a", is_flag=True, default=None, help="Show all attributes")
@click.option("--json", "-j", "json_output", is_flag=True, default=None, help="Output as JSON")
@click.option("--csv", is_flag=True, default=None, help="Output as CSV")
def members(group_cn, json_output, csv, all):
    """
    Show members of a group specified by [GROUP].
    """
    cfg = get_ldap_config(selected_ldap["name"])
    search_filter = f"(cn={group_cn})"
    try:
        if all:
            attrs = ["*"]
        else:
            attrs = ["cn", "description", "member"]
        result = ldap_search(cfg, search_filter, attrs)
        if result:
            if json_output:
                print(result[0].entry_to_json())
            elif csv:
                import csv as _csv
                import sys
                group_info = result[0].entry_attributes_as_dict
                writer = _csv.writer(sys.stdout)
                writer.writerow(group_info.keys())
                writer.writerow([", ".join(map(str, v)) for v in group_info.values()])
            else:
                group_info = result[0].entry_attributes_as_dict
                group_info = {str(attr): [str(value) for value in values] for attr, values in group_info.items()}
                for attr, values in sorted(group_info.items()):
                    if attr == "member" or attr == "objectClass":
                        print(f"{attr}:")
                        for group in values:
                            print(f"  - {group}")
                    else:
                        print(f"{attr}: {', '.join(values)}")
        else:
            raise click.ClickException(f"No group found with CN '{group_cn}'.")
    except click.ClickException as e:
        raise e
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise click.ClickException(f"An error occurred: {e}")
