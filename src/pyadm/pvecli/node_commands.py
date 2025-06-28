import click
import json
import sys
import logging
from tabulate import tabulate
from pyadm.pvecli.pve_commands import pvecli, get_pve_client


@pvecli.group("node", context_settings={'help_option_names': ['-h', '--help']})
def node():
    """Manage Proxmox VE nodes."""
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
                    value = node_info[field]
                    if field == 'uptime' and isinstance(value, (int, float)):
                        # Convert seconds to hours for uptime
                        row.append(f"{value / 3600:.2f} hours")
                    elif field in ['maxmem', 'maxdisk'] and isinstance(value, (int, float)):
                        # Convert bytes to GB for memory and disk
                        row.append(f"{value / (1024**3):.2f} GB")
                    elif field == 'cpu' and isinstance(value, (int, float)):
                        # Format CPU percentage
                        row.append(f"{value:.1f}%")
                    else:
                        row.append(str(value))
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
                uptime_val = status['uptime']
                if isinstance(uptime_val, (int, float)):
                    uptime_hours = uptime_val / 3600
                    click.echo(f"Uptime: {uptime_hours:.2f} hours")
                else:
                    click.echo(f"Uptime: {uptime_val}")
                
            if 'loadavg' in status:
                load = status['loadavg']
                if isinstance(load, list) and len(load) >= 3:
                    # Ensure all load values are numeric
                    try:
                        load_vals = [float(x) for x in load[:3]]
                        click.echo(f"Load average: {load_vals[0]:.2f}, {load_vals[1]:.2f}, {load_vals[2]:.2f}")
                    except (ValueError, TypeError):
                        click.echo(f"Load average: {load}")
                else:
                    click.echo(f"Load average: {load}")
                    
            if 'cpu' in status:
                cpu_val = status['cpu']
                if isinstance(cpu_val, (int, float)):
                    click.echo(f"CPU usage: {cpu_val:.2f}%")
                else:
                    click.echo(f"CPU usage: {cpu_val}")
                
            if 'memory' in status and isinstance(status['memory'], dict) and 'total' in status['memory']:
                try:
                    mem_total = status['memory']['total']
                    mem_used = status['memory'].get('used', 0)
                    if isinstance(mem_total, (int, float)) and isinstance(mem_used, (int, float)):
                        mem_gb = mem_total / (1024**3)
                        used_gb = mem_used / (1024**3)
                        click.echo(f"Memory: {used_gb:.2f} GB used of {mem_gb:.2f} GB")
                    else:
                        click.echo(f"Memory: {mem_used} used of {mem_total}")
                except (TypeError, ValueError):
                    click.echo(f"Memory: {status['memory']}")
                
            if 'swap' in status and isinstance(status['swap'], dict) and 'total' in status['swap']:
                try:
                    swap_total = status['swap']['total']
                    swap_used = status['swap'].get('used', 0)
                    if isinstance(swap_total, (int, float)) and isinstance(swap_used, (int, float)):
                        swap_gb = swap_total / (1024**3)
                        used_swap_gb = swap_used / (1024**3)
                        click.echo(f"Swap: {used_swap_gb:.2f} GB used of {swap_gb:.2f} GB")
                    else:
                        click.echo(f"Swap: {swap_used} used of {swap_total}")
                except (TypeError, ValueError):
                    click.echo(f"Swap: {status['swap']}")
                
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