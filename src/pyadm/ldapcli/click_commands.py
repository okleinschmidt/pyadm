import click
import json
import ldap

from pyadm.config import config


defaults = {
    "server": "ldap://localhost",
    "base_dn": "dc=example,dc=org",
    "username": "root@example.org",
    "password": "s3cur3_p455w0rd"
}

click_options = {}

# ldap wrapper function(s)
def ldap_search(click_options, search_filter, attributes=[]):
    try: 
        ldap_connection = ldap.initialize(click_options["server"])
        ldap_connection.simple_bind(click_options["username"], click_options["password"])
        base_dn = click_options["base_dn"]
        
        result = ldap_connection.search_s(base_dn, ldap.SCOPE_SUBTREE, search_filter, attributes)
        return result
    except ldap.LDAPError as e:
        raise click.ClickException(f"LDAP search failed: {e}")

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
    search_filter = f"(cn={username})"
    try:
        if all:
            result = ldap_search(click_options, search_filter)
        else:
            attributes = ['cn', 'mail', 'memberOf']
            result = ldap_search(click_options, search_filter, attributes)

        if result:
            dn, user_info = result[0]
            # decode bytecode values to utf-8, otherwise every value will have a b' in front.
            user_info = {attr: [value.decode('utf-8') for value in values] for attr, values in user_info.items()}
            
            if json_output:
                print(json.dumps(user_info, default=str, indent=4))
            else:
                if 'memberOf' in user_info:
                    user_info['memberOf'] = [f"- {group}" for group in user_info['memberOf']]
                if 'objectClass' in user_info:
                    user_info['objectClass'] = [f"- {objectclass}" for objectclass in user_info['objectClass']]
               
                for attr, values in user_info.items():
                    if attr == 'memberOf':
                        print(f"{attr}:")
                        for group in values:
                            print(f"  {group}")
                    elif attr == 'objectClass':
                        print(f"{attr}:")
                        for objectclass in values:
                            print(f"  {objectclass}")
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
@click.argument('user_cn')
@click.option('--all', '-a', is_flag=True, default=None, help="Show all attributes")
@click.option('--json', '-j', 'json_output', is_flag=True, default=None, help="Output as JSON")
def groups(user_cn, json_output, all):
    search_filter = f"(cn={user_cn})"
    try:
        if all:
            result = ldap_search(click_options, search_filter)
        else:
            attributes = ['memberOf']
            result = ldap_search(click_options, search_filter, attributes)

        if result:
            dn, group_info = result[0]
            # decode bytecode values to utf-8, otherwise every value will have a b' in front.            
            group_info = {attr: [value.decode('utf-8') for value in values] for attr, values in group_info.items()}
            if json_output:
                print(json.dumps(group_info, default=str, indent=4))
            else:
                if 'memberOf' in group_info:
                    group_info['memberOf'] = [f"- {group}" for group in group_info['memberOf']]
               
                for attr, values in group_info.items():
                    if attr == 'memberOf':
                        print(f"{attr}:")
                        for group in values:
                            print(f"  {group}")
                    else:
                        print(f"{attr}: {', '.join(values)}")
        else:
            raise click.ClickException(f"No user found with UID '{username}'.")
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
            result = ldap_search(click_options, search_filter)
        else:
            attributes = ['cn', 'description', 'member']
            result = ldap_search(click_options, search_filter, attributes)

        if result:
            dn, group_info = result[0]
            # decode bytecode values to utf-8, otherwise every value will have a b' in front.            
            group_info = {attr: [value.decode('utf-8') for value in values] for attr, values in group_info.items()}
            if json_output:
                print(json.dumps(group_info, default=str, indent=4))
            else:
                if 'member' in group_info:
                    group_info['member'] = [f"- {group}" for group in group_info['member']]
                if 'objectClass' in group_info:
                    group_info['objectClass'] = [f"- {objectclass}" for objectclass in group_info['objectClass']]
               
                for attr, values in group_info.items():
                    if attr == 'member':
                        print(f"{attr}:")
                        for group in values:
                            print(f"  {group}")
                    elif attr == 'objectClass':
                        print(f"{attr}:")
                        for objectclass in values:
                            print(f"  {objectclass}")
                    else:
                        print(f"{attr}: {', '.join(values)}")
        else:
            raise click.ClickException(f"No user found with UID '{username}'.")
    except click.ClickException as e:
        raise e
    except Exception as e:
        raise click.ClickException(f"An error occurred: {e}")
