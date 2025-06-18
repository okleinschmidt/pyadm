import click
import json
import sys
import logging
from tabulate import tabulate
from pyadm.pvecli.pve_commands import pvecli, get_pve_client


@pvecli.group("storage")
def storage():
    """
    Manage storage on Proxmox VE.
    """
    pass


@storage.command("list")
@click.option("--node", "-n", default=None, help="Filter by node name")
@click.option("--type", "-t", default=None, help="Filter by storage type (dir, nfs, etc.)")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
@click.option("--output", "-o", default=None, help="Comma-separated list of fields to display")
def list_storage(node, type, json_output, output):
    """
    List storage resources.
    """
    try:
        client = get_pve_client()
        storage_list = client.get_storage(node)
        
        # Filter by type if requested
        if type:
            storage_list = [s for s in storage_list if s.get('type') == type]
            
        if json_output:
            click.echo(json.dumps(storage_list, indent=2))
            return
        
        # Determine fields to display
        fields = ['storage', 'type', 'content', 'node', 'active', 'total', 'used', 'avail']
        if output:
            fields = output.split(',')
        
        # Create table data
        table_data = []
        for storage_info in storage_list:
            row = []
            for field in fields:
                if field in storage_info:
                    if field in ['total', 'used', 'avail'] and isinstance(storage_info[field], (int, float)):
                        # Convert bytes to GB for storage
                        row.append(f"{storage_info[field] / (1024**3):.2f} GB")
                    elif field == 'active' and isinstance(storage_info[field], int):
                        row.append("Yes" if storage_info[field] == 1 else "No")
                    else:
                        row.append(storage_info[field])
                else:
                    # Show N/A for missing values
                    row.append("N/A")
            table_data.append(row)
        
        # Print table
        click.echo(tabulate(table_data, headers=fields))
        
    except Exception as e:
        logging.error(f"Error listing storage: {e}")
        raise click.ClickException(f"Error listing storage: {e}")