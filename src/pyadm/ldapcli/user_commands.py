import click
import json
import sys
import logging
import csv as _csv
from pyadm.ldapcli.click_commands import ldapcli, get_ldap_client


# Show information about a user
@ldapcli.command("user")
@click.argument("username", metavar="[UID, CN, MAIL]")
@click.option("--all", "-a", is_flag=True, default=None, help="Show all attributes")
@click.option("--json", "-j", "json_output", is_flag=True, default=None, help="Output as JSON")
@click.option("--csv", is_flag=True, default=None, help="Output as CSV")
@click.option("--attributes", "-A", default=None, help="Comma-separated list of attributes to show")
@click.option("--add-to-group", "-G", default=None, help="Add user to the specified group (by CN or DN)")
@click.option("--remove-from-group", "-R", default=None, help="Remove user from the specified group (by CN or DN)")
@click.option("--add-to-groups", default=None, help="Add user to multiple groups (comma-separated)")
@click.option("--remove-from-groups", default=None, help="Remove user from multiple groups (comma-separated)")
@click.option("--set-password", "-P", default=None, help="Set password for the user")
@click.option("--reset-password", is_flag=True, default=None, help="Reset password with random value and show it")
@click.option("--force-password-change", is_flag=True, default=None, help="Force user to change password at next login")
@click.option("--enable", is_flag=True, default=None, help="Enable user account")
@click.option("--disable", is_flag=True, default=None, help="Disable user account")
@click.option("--lock", is_flag=True, default=None, help="Lock user account")
@click.option("--unlock", is_flag=True, default=None, help="Unlock user account")
@click.option("--set-attribute", multiple=True, help="Set user attribute (format: attribute=value)")
@click.option("--set-expiry", default=None, help="Set account expiry date (format: YYYY-MM-DD)")
@click.option("--move-to", default=None, help="Move user to specified OU (by DN)")
@click.option("--clone-to", default=None, help="Clone user to new username")
def user(username, json_output, csv, all, attributes, add_to_group, remove_from_group, add_to_groups, 
         remove_from_groups, set_password, reset_password, force_password_change, enable, disable, 
         lock, unlock, set_attribute, set_expiry, move_to, clone_to):
    """
    Show information about a user specified by [UID], [CN], or [MAIL].
    """
    try:
        ldap_client = get_ldap_client()
        
        # Get user info first as most operations need the DN
        user_result = None
        user_dn = None
        
        # Check if user exists for operations that need it
        if (add_to_group or remove_from_group or add_to_groups or remove_from_groups or
            set_password or reset_password or force_password_change or enable or disable or 
            lock or unlock or set_attribute or set_expiry or move_to or clone_to):
            user_result = ldap_client.get_user(username)
            if not user_result:
                raise click.ClickException(f"No user found with identifier '{username}'.")
            user_dn = user_result[0].entry_dn
        
        # Handle set password
        if set_password:
            success = ldap_client.set_user_password(user_dn, set_password)
            if success:
                click.echo(f"Password for user '{username}' set successfully.")
            else:
                raise click.ClickException(f"Failed to set password for user '{username}'.")
            return
            
        # Handle password reset with random password
        if reset_password:
            import random
            import string
            chars = string.ascii_letters + string.digits + "!@#$%^&*()"
            random_password = ''.join(random.choice(chars) for _ in range(16))
            success = ldap_client.set_user_password(user_dn, random_password)
            if success:
                click.echo(f"Password for user '{username}' reset successfully.")
                click.echo(f"New password: {random_password}")
            else:
                raise click.ClickException(f"Failed to reset password for user '{username}'.")
            return
            
        # Handle force password change
        if force_password_change:
            success = ldap_client.set_attribute(user_dn, "pwdLastSet", "0")
            if success:
                click.echo(f"User '{username}' will be required to change password at next login.")
            else:
                raise click.ClickException(f"Failed to set password change requirement for '{username}'.")
            return
            
        # Handle enable account
        if enable:
            success = ldap_client.set_attribute(user_dn, "userAccountControl", "512")  # Normal account
            if success:
                click.echo(f"User account '{username}' enabled successfully.")
            else:
                raise click.ClickException(f"Failed to enable user account '{username}'.")
            return
            
        # Handle disable account
        if disable:
            success = ldap_client.set_attribute(user_dn, "userAccountControl", "514")  # Disabled account
            if success:
                click.echo(f"User account '{username}' disabled successfully.")
            else:
                raise click.ClickException(f"Failed to disable user account '{username}'.")
            return
            
        # Handle lock account
        if lock:
            success = ldap_client.set_attribute(user_dn, "lockoutTime", "1")
            if success:
                click.echo(f"User account '{username}' locked successfully.")
            else:
                raise click.ClickException(f"Failed to lock user account '{username}'.")
            return
            
        # Handle unlock account
        if unlock:
            success = ldap_client.set_attribute(user_dn, "lockoutTime", "0")
            if success:
                click.echo(f"User account '{username}' unlocked successfully.")
            else:
                raise click.ClickException(f"Failed to unlock user account '{username}'.")
            return
            
        # Handle set expiry
        if set_expiry:
            import datetime
            try:
                expiry_date = datetime.datetime.strptime(set_expiry, "%Y-%m-%d")
                # Convert to Active Directory format (100-nanosecond intervals since Jan 1, 1601)
                import time
                ad_timestamp = str(int((time.mktime(expiry_date.timetuple()) + 11644473600) * 10000000))
                success = ldap_client.set_attribute(user_dn, "accountExpires", ad_timestamp)
                if success:
                    click.echo(f"Account expiry for '{username}' set to {set_expiry}.")
                else:
                    raise click.ClickException(f"Failed to set account expiry for '{username}'.")
            except ValueError:
                raise click.ClickException(f"Invalid date format. Use YYYY-MM-DD.")
            return
            
        # Handle move user
        if move_to:
            success = ldap_client.move_user(user_dn, move_to)
            if success:
                click.echo(f"User '{username}' moved to '{move_to}' successfully.")
            else:
                raise click.ClickException(f"Failed to move user '{username}' to '{move_to}'.")
            return
            
        # Handle clone user
        if clone_to:
            success = ldap_client.clone_user(user_dn, clone_to)
            if success:
                click.echo(f"User '{username}' cloned to '{clone_to}' successfully.")
            else:
                raise click.ClickException(f"Failed to clone user '{username}' to '{clone_to}'.")
            return
            
        # Handle set attributes
        if set_attribute:
            for attr_pair in set_attribute:
                if "=" not in attr_pair:
                    raise click.ClickException(f"Invalid attribute format. Use 'attribute=value'.")
                
                attr, value = attr_pair.split("=", 1)
                success = ldap_client.set_attribute(user_dn, attr.strip(), value.strip())
                if success:
                    click.echo(f"Attribute '{attr}' for user '{username}' set to '{value}'.")
                else:
                    raise click.ClickException(f"Failed to set attribute '{attr}' for user '{username}'.")
            return
            
        # Handle add to multiple groups
        if add_to_groups:
            groups = [g.strip() for g in add_to_groups.split(",") if g.strip()]
            success_count = 0
            for group in groups:
                # Check if group_dn is a DN or CN
                if "dc=" in group.lower():
                    group_dn = group
                else:
                    # It's a CN, get the DN
                    group_result = ldap_client.get_group_members(group)
                    if not group_result:
                        click.echo(f"Warning: No group found with CN '{group}'. Skipping.")
                        continue
                    group_dn = group_result[0].entry_dn
                    
                success = ldap_client.add_user_to_group(user_dn, group_dn)
                if success:
                    success_count += 1
                    click.echo(f"User '{username}' added to group '{group}'.")
                else:
                    click.echo(f"Warning: Failed to add user '{username}' to group '{group}'.")
            
            if success_count > 0:
                click.echo(f"Added user to {success_count} group(s) successfully.")
            else:
                raise click.ClickException("Failed to add user to any of the specified groups.")
            return
            
        # Handle remove from multiple groups
        if remove_from_groups:
            groups = [g.strip() for g in remove_from_groups.split(",") if g.strip()]
            success_count = 0
            for group in groups:
                # Check if group_dn is a DN or CN
                if "dc=" in group.lower():
                    group_dn = group
                else:
                    # It's a CN, get the DN
                    group_result = ldap_client.get_group_members(group)
                    if not group_result:
                        click.echo(f"Warning: No group found with CN '{group}'. Skipping.")
                        continue
                    group_dn = group_result[0].entry_dn
                    
                success = ldap_client.remove_user_from_group(user_dn, group_dn)
                if success:
                    success_count += 1
                    click.echo(f"User '{username}' removed from group '{group}'.")
                else:
                    click.echo(f"Warning: Failed to remove user '{username}' from group '{group}'.")
            
            if success_count > 0:
                click.echo(f"Removed user from {success_count} group(s) successfully.")
            else:
                raise click.ClickException("Failed to remove user from any of the specified groups.")
            return
            
        # Handle add to group
        if add_to_group:
            # Check if group_dn is a DN or CN
            if "dc=" in add_to_group.lower():
                group_dn = add_to_group
            else:
                # It's a CN, get the DN
                group_result = ldap_client.get_group_members(add_to_group)
                if not group_result:
                    raise click.ClickException(f"No group found with CN '{add_to_group}'.")
                group_dn = group_result[0].entry_dn
                
            success = ldap_client.add_user_to_group(user_dn, group_dn)
            if success:
                click.echo(f"User '{username}' added to group '{add_to_group}'.")
            else:
                raise click.ClickException(f"Failed to add user '{username}' to group '{add_to_group}'.")
            return
            
        # Handle remove from group
        if remove_from_group:
            # Check if group_dn is a DN or CN
            if "dc=" in remove_from_group.lower():
                group_dn = remove_from_group
            else:
                # It's a CN, get the DN
                group_result = ldap_client.get_group_members(remove_from_group)
                if not group_result:
                    raise click.ClickException(f"No group found with CN '{remove_from_group}'.")
                group_dn = group_result[0].entry_dn
                
            success = ldap_client.remove_user_from_group(user_dn, group_dn)
            if success:
                click.echo(f"User '{username}' removed from group '{remove_from_group}'.")
            else:
                raise click.ClickException(f"Failed to remove user '{username}' from group '{remove_from_group}'.")
            return

        # Original user info display code
        if all:
            attrs = ["*"]
        elif attributes:
            attrs = [a.strip() for a in attributes.split(",") if a.strip()]
        else:
            attrs = ["cn", "mail", "memberOf"]
        result = ldap_client.get_user(username, attrs)
        if result:
            if json_output:
                print(result[0].entry_to_json())
            elif csv:
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
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise click.ClickException(f"An error occurred: {e}")


# Check if a user exists
@ldapcli.command("user-exists")
@click.argument("username", metavar="[UID, CN, MAIL]")
def user_exists(username):
    """
    Check if a user exists by [UID], [CN], or [MAIL].
    """
    try:
        exists = get_ldap_client().user_exists(username)
        if exists:
            click.echo(f"User '{username}' exists.")
        else:
            click.echo(f"User '{username}' does not exist.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise click.ClickException(f"An error occurred: {e}")