import click
import json
import ldap3

from ldap3.core.exceptions import LDAPException
from pyadm.config import config

defaults = {
    "server": "ldap://localhost",
    "base_dn": "dc=example,dc=org",
    "username": "root@example.org",
    "password": "s3cur3_p455w0rd",
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

        conn.search(base_dn, search_filter, attributes=attributes)

        result_entries = conn.entries
        return result_entries
    except LDAPException as e:
        raise click.ClickException(f"LDAP search failed: {e}")

# define click commands
@click.group("ldap")
@click.option("--server", "-s", help="Specify the LDAP server.")
@click.option("--base_dn", "-b", help="Specify the base DN (Distinguished Name).")
@click.option("--username", "-u", help="Specify the username for authentication.")
@click.option("--password", "-p", help="Specify the password for authentication. It will prompt if the password is empty.", prompt=False, hide_input=True)
def ldapcli(server, base_dn, username, password):
    """
    Query LDAP/Active Directory.

    This command provides various subcommands to interact with
    an LDAP or Active Directory server. It allows you to perform queries,
    retrieve information, and manage users and groups within the directory.
    
    \b
    To see the available subcommands, run 'pyadm ldap --help'.\r
    Get help for subcommands, run 'pyadm ldap COMMAND --help'.
    
    \b
    Configuration File:\r
    The configuration file allows you to customize various settings for the
    command, such as the LDAP server, base DN, username, password, and other options.

    The default location for the configuration file is `/home/user/.config/pyadm/pyadm.conf`.

    Example configuration file contents:
    
    \b
    [LDAP]
    server = ldaps://dc.example.org
    base_dn = dc=example,dc=org
    bind_username = administrator@example.org
    bind_password = s3cr3t-p455w0rd!
    
    """
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
@ldapcli.command("user")
@click.argument("username", metavar="[UID, CN, MAIL]")
@click.option("--all", "-a", is_flag=True, default=None, help="Show all attributes")
@click.option("--json", "-j", "json_output", is_flag=True, default=None, help="Output as JSON")
def user(username, json_output, all):
    """Show information about a user specified by [UID], [CN], or [MAIL].

    This command allows you to retrieve detailed information about a user
    in the LDAP directory. You can specify the username using their UID,
    CN (Common Name), or MAIL (Email Address).
    
    \b
    Examples:
    $ pyadm ldap user jdoe              # Retrieve information for user with UID 'jdoe'
    $ pyadm ldap user "John Doe"        # Retrieve information for user with CN 'John Doe'
    $ pyadm ldap user jdoe@example.com  # Retrieve information for user with MAIL 'jdoe@example.com'
    """
    search_filter = f"(|(uid={username})(cn={username})(mail={username}))"
    try:
        if all:
            attributes = ["*"]
            result = ldap_search(click_options, search_filter, attributes)
        else:
            attributes = ["cn", "mail", "memberOf"]
            result = ldap_search(click_options, search_filter, attributes)

        if result:
            if json_output:
                user_info = result[0].entry_to_json()
                print(user_info)
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
        raise click.ClickException(f"An error occurred: {e}")

# show groups a user belongs to
@ldapcli.command("groups")
@click.argument("username", metavar="[UID, CN, MAIL]")
@click.option("--json", "-j", "json_output", is_flag=True, default=None, help="Output as JSON")
def groups(username, json_output):
    """
    Show groups associated with a user specified by [UID], [CN], or [MAIL].

    This command allows you to retrieve the groups associated with a user
    in the LDAP directory. You can specify the username using their UID,
    CN (Common Name), or MAIL (Email Address).
    
    \b
    Examples:
    $ pyadm ldap groups jdoe              # Retrieve groups for user with UID 'jdoe'
    $ pyadm ldap groups "John Doe"        # Retrieve groups for user with CN 'John Doe'
    $ pyadm ldap groups jdoe@example.com  # Retrieve groups for user with MAIL 'jdoe@example.com'
    """
    search_filter = f"(|(uid={username})(cn={username}))"
    try:
        attributes = ["memberOf"]
        result = ldap_search(click_options, search_filter, attributes)

        if result:
            if json_output:
                group_info = result[0].entry_to_json()
                print(group_info)
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
            raise click.ClickException(f"No user found with UID '{uid}'.")
    except click.ClickException as e:
        raise e
    except Exception as e:
        raise click.ClickException(f"An error occurred: {e}")

# show members of a group
@ldapcli.command("members")
@click.argument("group_cn", metavar="[GROUP]")
@click.option("--all", "-a", is_flag=True, default=None, help="Show all attributes")
@click.option("--json", "-j", "json_output", is_flag=True, default=None, help="Output as JSON")
def members(group_cn, json_output, all):
    """
    Show members of a group specified by [GROUP].

    This command allows you to retrieve the members of a group in the LDAP
    directory. You can specify the group using its CN (Common Name).

    \b
    Examples:
    $ pyadm ldap members "Developers"     # Retrieve members of the group with CN 'Developers'
    $ pyadm ldap members "Admins"         # Retrieve members of the group with CN 'Admins'
    """
    search_filter = f"(cn={group_cn})"
    try:
        if all:
            attributes = ["*"]
            result = ldap_search(click_options, search_filter, attributes)
        else:
            attributes = ["cn", "description", "member"]
            result = ldap_search(click_options, search_filter, attributes)

        if result:
            if json_output:
                group_info = result[0].entry_to_json()
                print(group_info)
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
            raise click.ClickException(f"No user found with UID '{group_cn}'.")
    except click.ClickException as e:
        raise e
    except Exception as e:
        raise click.ClickException(f"An error occurred: {e}")
