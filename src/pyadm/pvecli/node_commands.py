import click
import json
import sys
import logging
from tabulate import tabulate
from pyadm.pvecli.pve_commands import pvecli, get_pve_client


@pvecli.group("node")
def node():
    """
    Manage Proxmox VE nodes.
    """
    pass


@node.command("list")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
@click.option("--output", "-o", default=None, help="Comma-separated list of fields to display")
def list_nodes(json_output, output):
    """
    List all nodes in the cluster.
    """
    try:
        client = get_pve_client()
        nodes = client.get_nodes()
        
        if json_output:
            click.echo(json.dumps(nodes, indent=2))
            return
        
        # Determine fields to display
        fields = ['node', 'status', 'uptime', 'cpu', 'maxmem', 'maxdisk']
        if output:
            fields = output.split(',')
        
        # Create table data
        table_data = []
        for node_info in nodes:
            row = []
            for field in fields:
                if field in node_info:
                    if field == 'uptime' and isinstance(node_info[field], int):
                        # Convert seconds to hours for uptime
                        row.append(f"{node_info[field] / 3600:.2f} hours")
                    elif field in ['maxmem', 'maxdisk'] and isinstance(node_info[field], int):
                        # Convert bytes to GB for memory and disk
                        row.append(f"{node_info[field] / (1024**3):.2f} GB")
                    else:
                        row.append(node_info[field])
                else:
                    row.append("")
            table_data.append(row)
        
        # Print table
        click.echo(tabulate(table_data, headers=fields))
        
    except Exception as e:
        logging.error(f"Error listing nodes: {e}")
        raise click.ClickException(f"Error listing nodes: {e}")


@node.command("status")
@click.argument("node_name")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
def get_node_status(node_name, json_output):
    """
    Get status of a specific node.
    """
    try:
        client = get_pve_client()
        status = client.get_node_status(node_name)
        
        if json_output:
            click.echo(json.dumps(status, indent=2))
        else:
            # Format and display status
            click.echo(f"Node: {node_name}")
            click.echo(f"Status: {status.get('status', 'unknown')}")
            
            if 'uptime' in status:
                uptime_hours = status['uptime'] / 3600
                click.echo(f"Uptime: {uptime_hours:.2f} hours")
                
            if 'loadavg' in status:
                load = status['loadavg']
                if isinstance(load, list) and len(load) >= 3:
                    click.echo(f"Load average: {load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}")
                    
            if 'cpu' in status:
                click.echo(f"CPU usage: {status['cpu']:.2f}%")
                
            if 'memory' in status and 'total' in status['memory']:
                mem_gb = status['memory']['total'] / (1024**3)
                used_gb = status['memory'].get('used', 0) / (1024**3)
                click.echo(f"Memory: {used_gb:.2f} GB used of {mem_gb:.2f} GB")
                
            if 'swap' in status and 'total' in status['swap']:
                swap_gb = status['swap']['total'] / (1024**3)
                used_gb = status['swap'].get('used', 0) / (1024**3)
                click.echo(f"Swap: {used_gb:.2f} GB used of {swap_gb:.2f} GB")
                
    except Exception as e:
        logging.error(f"Error getting node status: {e}")
        raise click.ClickException(f"Error getting node status: {e}")


@node.command("tasks")
@click.argument("node_name")
@click.option("--limit", "-l", default=10, help="Maximum number of tasks to show")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
def list_tasks(node_name, limit, json_output):
    """
    List recent tasks on a node.
    """
    try:
        client = get_pve_client()
        tasks = client.get_tasks(node_name, limit)
        
        if json_output:
            click.echo(json.dumps(tasks, indent=2))
            return
        
        # Display tasks in a table
        table_data = []
        for task in tasks:
            status = task.get('status', '')
            starttime = task.get('starttime', '')
            endtime = task.get('endtime', '')
            
            # Format timestamps for better readability if they are integers
            if isinstance(starttime, int):
                from datetime import datetime
                starttime = datetime.fromtimestamp(starttime).strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(endtime, int):
                from datetime import datetime
                endtime = datetime.fromtimestamp(endtime).strftime('%Y-%m-%d %H:%M:%S')
                
            table_data.append([
                task.get('upid', ''),
                task.get('type', ''),
                status,
                starttime,
                endtime,
                task.get('id', '')
            ])
        
        headers = ['UPID', 'Type', 'Status', 'Start Time', 'End Time', 'ID']
        click.echo(tabulate(table_data, headers=headers))
        
    except Exception as e:
        logging.error(f"Error listing tasks: {e}")
        raise click.ClickException(f"Error listing tasks: {e}")