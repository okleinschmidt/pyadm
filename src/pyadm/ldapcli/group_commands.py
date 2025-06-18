import click
import json
import sys
import logging
import csv as _csv
from pyadm.ldapcli.click_commands import ldapcli, get_ldap_client


# Show groups a user belongs to
@ldapcli.command("groups")
@click.argument("name", metavar="[NAME]")
@click.option("--json", "-j", "json_output", is_flag=True, default=None, help="Output as JSON")
@click.option("--csv", is_flag=True, default=None, help="Output as CSV")
@click.option("--all", "-a", is_flag=True, default=None, help="Show all attributes")
@click.option("--attributes", "-A", default=None, help="Comma-separated list of attributes to show")
@click.option("--create", "-c", is_flag=True, default=None, help="Create a new group")
@click.option("--delete", "-d", is_flag=True, default=None, help="Delete the group")
@click.option("--add-member", "-m", default=None, help="Add a user (by DN or CN) to the group")
@click.option("--remove-member", "-r", default=None, help="Remove a user (by DN or CN) from the group")
@click.option("--add-members-from-file", "-f", default=None, help="Add users from file (one DN/CN per line)")
@click.option("--remove-members-from-file", "-F", default=None, help="Remove users from file (one DN/CN per line)")
@click.option("--set-description", default=None, help="Set group description")
@click.option("--rename-to", default=None, help="Rename group to new CN")
@click.option("--move-to", default=None, help="Move group to specified OU (by DN)")
@click.option("--set-attribute", multiple=True, help="Set group attribute (format: attribute=value)")
def groups(name, json_output, csv, all, attributes, create, delete, add_member, remove_member, 
          add_members_from_file, remove_members_from_file, set_description, rename_to, move_to, set_attribute):
    """
    Manage groups in LDAP/Active Directory.
    
    Without options: Show groups associated with a user specified by [NAME].
    With group management options: Treat [NAME] as a group CN instead.
    """
    try:
        ldap_client = get_ldap_client()
        
        # Determine if we're managing a group or showing user's groups
        is_group_management = (create or delete or add_member or remove_member or 
                              add_members_from_file or remove_members_from_file or 
                              set_description or rename_to or move_to or set_attribute)
        
        if create:
            # Create new group
            success = ldap_client.create_group(name, description=set_description)
            if success:
                click.echo(f"Group '{name}' created successfully.")
            else:
                raise click.ClickException(f"Failed to create group '{name}'.")
            return
        
        # For other operations, we need the group DN
        group_result = None
        group_dn = None
        
        if is_group_management:
            group_result = ldap_client.get_group_members(name)
            if not group_result and not create:
                raise click.ClickException(f"No group found with name '{name}'.")
            if group_result:
                group_dn = group_result[0].entry_dn
        
            # Handle delete group
            if delete:
                success = ldap_client.delete_group(group_dn)
                if success:
                    click.echo(f"Group '{name}' deleted successfully.")
                else:
                    raise click.ClickException(f"Failed to delete group '{name}'.")
                return
                
            # Handle set description
            if set_description:
                success = ldap_client.set_attribute(group_dn, "description", set_description)
                if success:
                    click.echo(f"Description for group '{name}' set to '{set_description}'.")
                else:
                    raise click.ClickException(f"Failed to set description for group '{name}'.")
                return
                
            # Handle rename group
            if rename_to:
                success = ldap_client.rename_group(group_dn, rename_to)
                if success:
                    click.echo(f"Group '{name}' renamed to '{rename_to}'.")
                else:
                    raise click.ClickException(f"Failed to rename group '{name}' to '{rename_to}'.")
                return
                
            # Handle move group
            if move_to:
                success = ldap_client.move_group(group_dn, move_to)
                if success:
                    click.echo(f"Group '{name}' moved to '{move_to}'.")
                else:
                    raise click.ClickException(f"Failed to move group '{name}' to '{move_to}'.")
                return
                
            # Handle add member
            if add_member:
                # Check if user_dn is a DN or CN/UID/Mail
                if "dc=" in add_member.lower():
                    user_dn = add_member
                else:
                    # It's a CN/UID/Mail, get the DN
                    user_result = ldap_client.get_user(add_member)
                    if not user_result:
                        raise click.ClickException(f"No user found with identifier '{add_member}'.")
                    user_dn = user_result[0].entry_dn
                    
                success = ldap_client.add_user_to_group(user_dn, group_dn)
                if success:
                    click.echo(f"User '{add_member}' added to group '{name}'.")
                else:
                    raise click.ClickException(f"Failed to add user '{add_member}' to group '{name}'.")
                return
                
            # Handle remove member
            if remove_member:
                # Check if user_dn is a DN or CN/UID/Mail
                if "dc=" in remove_member.lower():
                    user_dn = remove_member
                else:
                    # It's a CN/UID/Mail, get the DN
                    user_result = ldap_client.get_user(remove_member)
                    if not user_result:
                        raise click.ClickException(f"No user found with identifier '{remove_member}'.")
                    user_dn = user_result[0].entry_dn
                    
                success = ldap_client.remove_user_from_group(user_dn, group_dn)
                if success:
                    click.echo(f"User '{remove_member}' removed from group '{name}'.")
                else:
                    raise click.ClickException(f"Failed to remove user '{remove_member}' from group '{name}'.")
                return
                
            # Handle add members from file
            if add_members_from_file:
                try:
                    with open(add_members_from_file, 'r') as file:
                        members = [line.strip() for line in file if line.strip()]
                        
                    success_count = 0
                    for member in members:
                        # Check if member is a DN or CN/UID/Mail
                        if "dc=" in member.lower():
                            user_dn = member
                        else:
                            # It's a CN/UID/Mail, get the DN
                            user_result = ldap_client.get_user(member)
                            if not user_result:
                                click.echo(f"Warning: No user found with identifier '{member}'. Skipping.")
                                continue
                            user_dn = user_result[0].entry_dn
                            
                        success = ldap_client.add_user_to_group(user_dn, group_dn)
                        if success:
                            success_count += 1
                            click.echo(f"User '{member}' added to group '{name}'.")
                        else:
                            click.echo(f"Warning: Failed to add user '{member}' to group '{name}'.")
                    
                    if success_count > 0:
                        click.echo(f"Added {success_count} user(s) to group '{name}' successfully.")
                    else:
                        raise click.ClickException(f"Failed to add any users to group '{name}'.")
                except Exception as e:
                    raise click.ClickException(f"Error processing file: {str(e)}")
                return
                
            # Handle remove members from file
            if remove_members_from_file:
                try:
                    with open(remove_members_from_file, 'r') as file:
                        members = [line.strip() for line in file if line.strip()]
                        
                    success_count = 0
                    for member in members:
                        # Check if member is a DN or CN/UID/Mail
                        if "dc=" in member.lower():
                            user_dn = member
                        else:
                            # It's a CN/UID/Mail, get the DN
                            user_result = ldap_client.get_user(member)
                            if not user_result:
                                click.echo(f"Warning: No user found with identifier '{member}'. Skipping.")
                                continue
                            user_dn = user_result[0].entry_dn
                            
                        success = ldap_client.remove_user_from_group(user_dn, group_dn)
                        if success:
                            success_count += 1
                            click.echo(f"User '{member}' removed from group '{name}'.")
                        else:
                            click.echo(f"Warning: Failed to remove user '{member}' from group '{name}'.")
                    
                    if success_count > 0:
                        click.echo(f"Removed {success_count} user(s) from group '{name}' successfully.")
                    else:
                        raise click.ClickException(f"Failed to remove any users from group '{name}'.")
                except Exception as e:
                    raise click.ClickException(f"Error processing file: {str(e)}")
                return
                
            # Handle set attributes
            if set_attribute:
                for attr_pair in set_attribute:
                    if "=" not in attr_pair:
                        raise click.ClickException(f"Invalid attribute format. Use 'attribute=value'.")
                    
                    attr, value = attr_pair.split("=", 1)
                    success = ldap_client.set_attribute(group_dn, attr.strip(), value.strip())
                    if success:
                        click.echo(f"Attribute '{attr}' for group '{name}' set to '{value}'.")
                    else:
                        raise click.ClickException(f"Failed to set attribute '{attr}' for group '{name}'.")
                return
        
        # Default behavior: show user's groups
        result = ldap_client.get_user_groups(name)
        if result:
            if json_output:
                print(result[0].entry_to_json())
            elif csv:
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
            raise click.ClickException(f"No user found with identifier '{name}'.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise click.ClickException(f"An error occurred: {e}")


# Check if a group exists
@ldapcli.command("group-exists")
@click.argument("group_cn", metavar="[GROUP_CN]")
def group_exists(group_cn):
    """
    Check if a group exists by [GROUP_CN].
    """
    try:
        exists = get_ldap_client().group_exists(group_cn)
        if exists:
            click.echo(f"Group '{group_cn}' exists.")
        else:
            click.echo(f"Group '{group_cn}' does not exist.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise click.ClickException(f"An error occurred: {e}")