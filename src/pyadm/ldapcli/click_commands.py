import click
import json
import ldap3

from ldap3.core.exceptions import LDAPException
from pyadm.config import config


defaults = {
    "server": "ldap://localhost",
    "base_dn": "dc=example,dc=org",
    "username": "root@example.org",
    "password": "s3cur3_p455w0rd"
}

click_options = {}

def ldap_search(click_options, search_filter, attributes=[]):
    try:
        server_url = click_options["server"]
        bind_dn = click_options["username"]
        bind_password = click_options["password"]
    
        server = ldap3.Server(server_url)
        conn = ldap3.Connection(server, user=bind_dn, password=bind_password)
        conn.open()
        conn.bind()
    
        base_dn = click_options["base_dn"]
    
        conn.search(base_dn,
                    search_filter,
                    attributes=attributes)
    
        result_entries = conn.entries
        return result_entries
    except LDAPException as e:
        raise click.ClickException(f"LDAP search failed: {e}")

def sort_memberof(memberof):
    groups = [str(group) for group in memberof]
    return sorted(groups)

# define click commands    
@click.group("ldap", help="Query LDAP/Active Directory")
@click.option('--server', '-s', help='LDAP Server')
@click.option('--base_dn', '-b', help='base_dn')
@click.option('--username', '-u', help="Username")
@click.option('--password', '-p', help="Password  [will prompt if password is empty]", prompt=False, hide_input=True)
def ldapcli(server, base_dn, username, password):
    if not (server or base_dn or username or password):
        click_options["server"] = config["LDAP"]["server"] or defaults["server"]
        click_options["base_dn"] = config["LDAP"]["base_dn"] or defaults["base_dn"]
        click_options["username"] = config["LDAP"]["bind_username"] or defaults["username"]
        click_options["password"] = config["LDAP"]["bind_password"] or defaults["password"]
    else:
        click_options["server"] = server or defaults["server"]
        click_options["base_dn"] = base_dn or defaults["base_dn"]
        click_options["username"] = username or defaults["username"]
        click_options["password"] = password

# show information about a user  
@ldapcli.command("user", help="Show information about [USER]")
@click.argument('username')
@click.option('--all', '-a', is_flag=True, default=None, help="Show all attributes")
@click.option('--json', '-j', 'json_output', is_flag=True, default=None, help="Output as JSON")
def user(username, json_output, all):
    search_filter = f"(|(uid={username})(cn={username}))"
    try:
        if all:
            attributes = ['*']
            result = ldap_search(click_options, search_filter, attributes)
        else:
            attributes = ['cn', 'mail', 'memberOf']
            result = ldap_search(click_options, search_filter, attributes)

        if result:
            if json_output:
                user_info = result[0].entry_to_json()
                print(user_info)
            else:
                user_info = result[0].entry_attributes_as_dict
                user_info = {str(attr): [str(value) for value in values] for attr, values in user_info.items()}
                for attr, values in sorted(user_info.items()):
                    if attr == 'memberOf' or attr == 'objectClass':
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
        raise click.ClickException(f"An error occurred: {e}")

# show groups a user belongs to
@ldapcli.command("groups", help="Show groups for [USER]")
@click.argument('username')
@click.option('--json', '-j', 'json_output', is_flag=True, default=None, help="Output as JSON")
def groups(username, json_output):
    search_filter = f"(|(uid={username})(cn={username}))"
    try:
        attributes = ['memberOf']
        result = ldap_search(click_options, search_filter, attributes)

        if result:

            if json_output:
                group_info = result[0].entry_to_json()
                print(group_info)
            else:
                group_info = result[0].entry_attributes_as_dict
                group_info = {str(attr): [str(value) for value in values] for attr, values in group_info.items()}
                for attr, values in sorted(group_info.items()):
                    if attr == 'memberOf' or attr == 'objectClass':
                        print(f"{attr}:")
                        for group in values:
                            print(f" - {group}")
                    else:
                        print(f"{attr}: {', '.join(values)}")
        else:
            raise click.ClickException(f"No user found with UID '{uid}'.")
    except click.ClickException as e:
        raise e
    except Exception as e:
        raise click.ClickException(f"An error occurred: {e}")

# show members of a group
@ldapcli.command("members", help="Show members of [GROUP]")
@click.argument('group_cn')
@click.option('--all', '-a', is_flag=True, default=None, help="Show all attributes")
@click.option('--json', '-j', 'json_output', is_flag=True, default=None, help="Output as JSON")
def members(group_cn, json_output, all):
    search_filter = f"(cn={group_cn})"
    try:
        if all:
            attributes = ['*']
            result = ldap_search(click_options, search_filter, attributes)
        else:
            attributes = ['cn', 'description', 'member']
            result = ldap_search(click_options, search_filter, attributes)

        if result:
            if json_output:
                group_info = result[0].entry_to_json()
                print(group_info)
            else:
                group_info = result[0].entry_attributes_as_dict
                group_info = {str(attr): [str(value) for value in values] for attr, values in group_info.items()}
                for attr, values in sorted(group_info.items()):
                    if attr == 'member' or attr == 'objectClass':
                        print(f"{attr}:")
                        for group in values:
                            print(f"  - {group}")
                    else:
                        print(f"{attr}: {', '.join(values)}")           
        else:
            raise click.ClickException(f"No user found with UID '{group_cn}'.")
    except click.ClickException as e:
        raise e
    except Exception as e:
        raise click.ClickException(f"An error occurred: {e}")
