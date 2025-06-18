import click
import json
import sys
import logging
import csv as _csv
from pyadm.ldapcli.click_commands import ldapcli, get_ldap_client


# Show members of a group
@ldapcli.command("members")
@click.argument("group_cn", metavar="[GROUP]")
@click.option("--all", "-a", is_flag=True, default=None, help="Show all attributes")
@click.option("--json", "-j", "json_output", is_flag=True, default=None, help="Output as JSON")
@click.option("--csv", is_flag=True, default=None, help="Output as CSV")
@click.option("--count", "-c", is_flag=True, default=None, help="Only show member count")
@click.option("--filter", "-f", default=None, help="Filter members by pattern")
@click.option("--export", "-e", default=None, help="Export member list to file")
@click.option("--recursive", "-r", is_flag=True, default=None, help="Show nested group members")
@click.option("--cn-only", is_flag=True, default=None, help="Show only CN part of DNs")
def members(group_cn, json_output, csv, all, count, filter, export, recursive, cn_only):
    """
    Show members of a group specified by [GROUP].
    """
    try:
        ldap_client = get_ldap_client()
        
        if all:
            attrs = ["*"]
        else:
            attrs = ["cn", "description", "member"]
            
        result = ldap_client.get_group_members(group_cn, attrs)
        if not result:
            raise click.ClickException(f"No group found with CN '{group_cn}'.")
            
        group_info = result[0].entry_attributes_as_dict
        
        # Extract members
        members = group_info.get("member", [])
        
        # Handle recursive membership if requested
        if recursive and members:
            nested_members = set()
            for member in members:
                # Check if member is a group
                if "cn=" in member.lower() and "ou=groups" in member.lower():
                    # Extract group CN
                    member_cn = member.split(",")[0].split("=")[1]
                    # Get members of this group
                    try:
                        nested_result = ldap_client.get_group_members(member_cn)
                        if nested_result:
                            nested_group_members = nested_result[0].entry_attributes_as_dict.get("member", [])
                            nested_members.update(nested_group_members)
                    except Exception:
                        click.echo(f"Warning: Could not get members of nested group '{member_cn}'")
            
            members = list(set(members) | nested_members)
        
        # Filter members if requested
        if filter:
            filtered_members = [m for m in members if filter.lower() in m.lower()]
            members = filtered_members
        
        # Process CN-only if requested
        if cn_only:
            processed_members = []
            for member in members:
                try:
                    # Extract CN from DN
                    cn = member.split(",")[0].split("=")[1]
                    processed_members.append(cn)
                except Exception:
                    processed_members.append(member)
            members = processed_members
        
        # Handle count only
        if count:
            click.echo(f"Group '{group_cn}' has {len(members)} members.")
            return
        
        # Handle export
        if export:
            try:
                with open(export, 'w') as file:
                    for member in members:
                        file.write(f"{member}\n")
                click.echo(f"Members of group '{group_cn}' exported to '{export}'.")
                return
            except Exception as e:
                raise click.ClickException(f"Failed to export members: {str(e)}")
        
        # Display results
        if json_output:
            print(json.dumps({"group": group_cn, "members": members}))
        elif csv:
            writer = _csv.writer(sys.stdout)
            writer.writerow(["Member"])
            for member in members:
                writer.writerow([member])
        else:
            click.echo(f"Group: {group_cn}")
            if "description" in group_info and group_info["description"]:
                click.echo(f"Description: {', '.join(str(d) for d in group_info['description'])}")
            click.echo(f"Members ({len(members)}):")
            for member in members:
                click.echo(f"  - {member}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise click.ClickException(f"An error occurred: {e}")